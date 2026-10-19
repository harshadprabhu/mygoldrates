// Runs the real JD Worker against an in-memory Supabase and a fake Brevo,
// and prints one JSON line of results for tests/test_jd_login.py to assert.
import { copyFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const src = process.argv[2];
const dir = mkdtempSync(join(tmpdir(), 'jdw-'));
copyFileSync(src, join(dir, 'worker.mjs'));
const worker = (await import(pathToFileURL(join(dir, 'worker.mjs')))).default;

const SB = 'https://sb.test';
const env = { SUPABASE_URL: SB, SUPABASE_SERVICE_KEY: 'svc', JD_SESSION_SECRET: 'x'.repeat(64),
              BREVO_API_KEY: 'brevo', ALERTS_FROM: 'MyGoldRates <alerts@mygoldrates.com>' };
const db = { jd_accounts: [], jd_login_codes: [], jd_subscriptions: [] };
let nextId = 1;
const mail = [];
let storageListBody = null;
let signedName = null;
let issueName = null;

function match(row, params) {
  for (const [k, v] of params) {
    if (['select', 'order', 'limit', 'on_conflict'].includes(k)) continue;
    const i = v.indexOf('.'); const op = v.slice(0, i), val = v.slice(i + 1);
    const cell = row[k] ?? null;
    if (op === 'eq' && String(cell) !== val) return false;
    if (op === 'gte' && !(cell !== null && String(cell) >= val)) return false;
    if (op === 'gt' && !(cell !== null && String(cell) > val)) return false;
    if (op === 'is' && val === 'null' && cell !== null) return false;
    if (op === 'is' && val === 'true' && cell !== true) return false;
  }
  return true;
}

globalThis.fetch = async (url, opts = {}) => {
  const u = new URL(url);
  const method = opts.method || 'GET';
  const reply = (b, s = 200) => new Response(JSON.stringify(b), { status: s });
  if (u.hostname === 'api.brevo.com') { mail.push(JSON.parse(opts.body)); return reply({ messageId: 'm' }, 201); }
  if (u.pathname.startsWith('/storage/v1/object/list/')) {
    storageListBody = JSON.parse(opts.body);
    if (!('prefix' in storageListBody)) return reply({ error: 'prefix required' }, 400);
    return reply([{ name: 'jewellers-digest-2026-10-14.xlsx' },
                  { name: 'jewellers-digest-2026-10-14.json' },
                  { name: 'jewellers-digest-2026-10-13.xlsx' }]);
  }
  if (u.pathname.startsWith('/storage/v1/object/sign/')) {
    signedName = u.pathname.split('/').pop();
    return reply({ signedURL: '/object/sign/jd-reports/x?token=t' });
  }
  if (u.pathname.startsWith('/storage/v1/object/authenticated/')) {
    issueName = u.pathname.split('/').pop();
    return reply({ last: '2026-10-14', trend: { days: 87 } });
  }
  const table = u.pathname.replace('/rest/v1/', '');
  const rows = db[table];
  if (!rows) return reply({ code: 'PGRST205' }, 404);
  const params = [...u.searchParams.entries()];
  if (method === 'GET') {
    let out = rows.filter((r) => match(r, params));
    const order = u.searchParams.get('order');
    if (order) { const [col, dir] = order.split('.'); out.sort((a, b) => (a[col] < b[col] ? -1 : 1) * (dir === 'desc' ? -1 : 1)); }
    const lim = u.searchParams.get('limit'); if (lim) out = out.slice(0, +lim);
    return reply(out);
  }
  if (method === 'POST') {
    for (const r of JSON.parse(opts.body)) rows.push({ id: nextId++, attempts: 0, used_at: null, created_at: new Date().toISOString(), ...r });
    return reply([], 201);
  }
  if (method === 'PATCH') {
    const patch = JSON.parse(opts.body);
    rows.filter((r) => match(r, params)).forEach((r) => Object.assign(r, patch));
    return reply([]);
  }
  return reply({}, 405);
};

const call = async (method, path, body, token) => {
  const headers = { 'content-type': 'application/json', Origin: 'https://mygoldrates.com' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await worker.fetch(new Request(`https://w.test${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined }), env);
  return { status: r.status, j: await r.json().catch(() => null) };
};
const codeFrom = (m) => m.subject.match(/^(\d{6}) /)[1];
const res = {};

db.jd_accounts.push({ id: 900, email: 'owner@shop.in', comp_until: '2099-12-31T00:00:00Z' });
db.jd_accounts.push({ id: 901, email: 'axb@x.com', comp_until: null });

// unknown address: same answer, nothing sent
let r = await call('POST', '/jd/login/start', { email: 'nobody@x.com' });
res.unknown = { status: r.status, body: r.j, mails: mail.length };
// "_" must not act as a wildcard and reach axb@x.com
r = await call('POST', '/jd/login/start', { email: 'a_b@x.com' });
res.wildcard = { status: r.status, mails: mail.length };
// known address: one mail with a code; only a hash is stored
r = await call('POST', '/jd/login/start', { email: 'Owner@Shop.in' });
const code1 = codeFrom(mail.at(-1));
res.known = { status: r.status, body: r.j, mails: mail.length, to: mail.at(-1).to[0].email,
  stored_plain: JSON.stringify(db.jd_login_codes).includes(code1) };
// wrong code counts an attempt
const wrong = code1 === '000000' ? '111111' : '000000';
r = await call('POST', '/jd/login/verify', { email: 'owner@shop.in', code: wrong });
res.wrong = { status: r.status, attempts: db.jd_login_codes.at(-1).attempts };
// right code signs in, once
r = await call('POST', '/jd/login/verify', { email: 'owner@shop.in', code: code1 });
const token = r.j?.token;
res.right = { status: r.status, has_token: /^jds\.900\.\d+\.[a-f0-9]{64}$/.test(token || ''), ent: r.j?.entitlement };
r = await call('POST', '/jd/login/verify', { email: 'owner@shop.in', code: code1 });
res.reuse = { status: r.status };
// the token works on /jd/status and /jd/report
r = await call('GET', '/jd/status', null, token);
res.status = { status: r.status, email: r.j?.email, ent: r.j?.entitlement };
r = await call('GET', '/jd/report', null, token);
res.report = { status: r.status, has_url: !!r.j?.url, list_body: storageListBody, signed: signedName };
r = await call('GET', '/jd/issue', null, token);
res.issue = { status: r.status, name: r.j?.name, read: issueName, last: r.j?.issue?.last };
r = await call('GET', '/jd/issue');
res.issue_anon = { status: r.status };
// a tampered token is refused
const forged = token.replace('jds.900.', 'jds.901.');
r = await call('GET', '/jd/status', null, forged);
res.forged = { status: r.status };
// five wrong guesses burn the code, even for the right one afterwards
await call('POST', '/jd/login/start', { email: 'owner@shop.in' });
const code2 = codeFrom(mail.at(-1));
const bad2 = code2 === '000000' ? '111111' : '000000';
for (let i = 0; i < 5; i++) await call('POST', '/jd/login/verify', { email: 'owner@shop.in', code: bad2 });
r = await call('POST', '/jd/login/verify', { email: 'owner@shop.in', code: code2 });
res.burned = { status: r.status };
// at most 5 codes per hour (2 sent above, 3 more allowed, 6th+ silent)
const before = mail.length;
for (let i = 0; i < 6; i++) await call('POST', '/jd/login/start', { email: 'owner@shop.in' });
res.ratelimit = { sent: mail.length - before };
// expired complimentary access is not access
db.jd_accounts[0].comp_until = '2020-01-01T00:00:00Z';
r = await call('GET', '/jd/report', null, token);
res.expired_comp = { status: r.status };
// an expired code is refused
db.jd_accounts[0].comp_until = '2099-12-31T00:00:00Z';
db.jd_login_codes.length = 0;
await call('POST', '/jd/login/start', { email: 'owner@shop.in' });
const code3 = codeFrom(mail.at(-1));
db.jd_login_codes.at(-1).expires_at = '2020-01-01T00:00:00.000Z';
r = await call('POST', '/jd/login/verify', { email: 'owner@shop.in', code: code3 });
res.expired_code = { status: r.status };
console.log(JSON.stringify(res));
