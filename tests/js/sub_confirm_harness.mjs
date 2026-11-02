// Runs the real JD Worker's subscriber-confirmation routes against a fake
// Supabase RPC layer, fake Brevo and fake Google tokeninfo, and prints one
// JSON line for tests/test_sub_confirm.py.
import { copyFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const dir = mkdtempSync(join(tmpdir(), 'subc-'));
copyFileSync(process.argv[2], join(dir, 'worker.mjs'));
const worker = (await import(pathToFileURL(join(dir, 'worker.mjs')))).default;

const env = { SUPABASE_URL: 'https://sb.test', SUPABASE_SERVICE_KEY: 'svc',
              BREVO_API_KEY: 'brevo', GOOGLE_CLIENT_ID: 'ours.apps.googleusercontent.com' };
// inquiries rows: email -> {token, name, confirmed, sent}
const subs = {
  'new@x.in':  { token: '11111111-1111-1111-1111-111111111111', name: 'Asha <b>K', confirmed: false, sent: false },
  'done@x.in': { token: '22222222-2222-2222-2222-222222222222', name: '', confirmed: true, sent: false },
  'g@x.in':    { token: '33333333-3333-3333-3333-333333333333', name: '', confirmed: false, sent: false },
};
const tokens = {
  good:  { aud: env.GOOGLE_CLIENT_ID, iss: 'https://accounts.google.com', email: 'G@x.in', email_verified: 'true' },
  other: { aud: 'someone-else', iss: 'https://accounts.google.com', email: 'g@x.in', email_verified: 'true' },
  unver: { aud: env.GOOGLE_CLIENT_ID, iss: 'accounts.google.com', email: 'g@x.in', email_verified: 'false' },
};
const mail = [];
globalThis.fetch = async (url, opts = {}) => {
  const u = new URL(url);
  const reply = (b, s = 200) => new Response(JSON.stringify(b), { status: s });
  if (u.hostname === 'api.brevo.com') { mail.push(JSON.parse(opts.body)); return reply({}, 201); }
  if (u.hostname === 'oauth2.googleapis.com') {
    const t = tokens[u.searchParams.get('id_token')];
    return t ? reply(t) : reply({ error: 'invalid_token' }, 400);
  }
  const body = JSON.parse(opts.body || '{}');
  const s = subs[String(body.p_email || '').toLowerCase()];
  if (u.pathname === '/rest/v1/rpc/confirm_request') {
    if (!s || s.confirmed || s.sent) return reply([]);
    s.sent = true;
    return reply([{ token: s.token, name: s.name }]);
  }
  if (u.pathname === '/rest/v1/rpc/confirm_google') {
    if (!s) return reply('missing');
    s.confirmed = true; return reply('ok');
  }
  return reply({ error: 'unexpected ' + u.pathname }, 500);
};
const call = async (path, b) => {
  const r = await worker.fetch(new Request('https://w.test' + path, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify(b) }), env);
  return { status: r.status, body: await r.json() };
};
const out = {};
let n = mail.length;
out.fresh = await call('/sub/confirm', { email: 'New@x.in' });
out.fresh.mails = mail.length - n; out.mail = mail[mail.length - 1];
n = mail.length; out.again = await call('/sub/confirm', { email: 'new@x.in' }); out.again.mails = mail.length - n;
n = mail.length; out.confirmed = await call('/sub/confirm', { email: 'done@x.in' }); out.confirmed.mails = mail.length - n;
n = mail.length; out.unknown = await call('/sub/confirm', { email: 'nobody@x.in' }); out.unknown.mails = mail.length - n;
n = mail.length; out.otherClient = await call('/sub/google', { credential: 'other', email: 'g@x.in' });
out.otherClient.mails = mail.length - n; out.otherClient.confirmed = subs['g@x.in'].confirmed;
subs['g@x.in'].sent = false;
n = mail.length; out.unverified = await call('/sub/google', { credential: 'unver', email: 'g@x.in' });
out.unverified.mails = mail.length - n; out.unverified.confirmed = subs['g@x.in'].confirmed;
n = mail.length; out.google = await call('/sub/google', { credential: 'good', email: 'g@x.in' });
out.google.mails = mail.length - n; out.google.confirmed = subs['g@x.in'].confirmed;
console.log(JSON.stringify(out));
