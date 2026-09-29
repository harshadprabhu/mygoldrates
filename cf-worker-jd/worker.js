/**
 * Jewellers Digest (JD) — the MyGoldRates B2B API.
 * Subscriptions, entitlement, and report delivery.
 *
 * Separate Worker from cf-worker-market on purpose. That one is a public,
 * CORS-open, edge-cached proxy for anonymous readers; this one holds a
 * Razorpay secret, a Supabase service key, and decides who has paid.
 * Different blast radius, different secrets, different cache posture — so
 * a different Worker rather than more routes on the public one.
 *
 * ROUTES
 *   POST /jd/signup        create account + Razorpay subscription
 *                           -> { short_url } for the jeweller to authorise
 *   POST /jd/webhook       Razorpay events (signature-verified, idempotent)
 *   GET  /jd/status        entitlement for the calling API key
 *   GET  /jd/report        short-lived signed URL for the latest workbook
 *   GET  /jd/rates         the rate history as JSON, for programmatic use
 *
 * SECRETS (wrangler secret put …)
 *   SUPABASE_URL, SUPABASE_SERVICE_KEY
 *   RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET
 *   RAZORPAY_PLAN_ID
 *
 * NOTHING here is edge-cached. Caching an entitlement decision or a signed
 * URL would serve one jeweller's access to the next caller.
 */

const JSON_HEADERS = { 'content-type': 'application/json; charset=utf-8' };

// The browser origins allowed to call signup. Same allowlist discipline as
// the market worker: a bare '*' here would let any site drive signups
// against this account's Razorpay keys.
const ALLOWED_ORIGINS = [
  'https://mygoldrates.com',
  'https://www.mygoldrates.com',
];
const PREVIEW_ORIGIN = /^https:\/\/[a-z0-9-]+\.mygoldrates\.pages\.dev$/;

function cors(request) {
  const h = {
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  };
  const o = request?.headers?.get('Origin');
  if (o && (ALLOWED_ORIGINS.includes(o) || PREVIEW_ORIGIN.test(o))) {
    h['Access-Control-Allow-Origin'] = o;
  }
  return h;
}

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    // Explicitly uncacheable everywhere: this Worker's answers are
    // per-caller and time-bound.
    headers: { ...JSON_HEADERS, 'cache-control': 'no-store', ...extra },
  });
}

// ─── crypto helpers ──────────────────────────────────────────────────────
const enc = new TextEncoder();

async function hmacHex(secret, body) {
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(body));
  return [...new Uint8Array(sig)]
    .map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Constant-time string compare.
 *
 * A plain `a === b` on a signature leaks, through timing, how many leading
 * characters an attacker guessed right, which is enough to forge a webhook
 * one character at a time. Comparing every byte regardless of mismatch
 * removes that signal. Length is folded in the same way rather than
 * short-circuiting on it.
 */
function timingSafeEqual(a, b) {
  const A = enc.encode(a), B = enc.encode(b);
  let diff = A.length ^ B.length;
  const n = Math.max(A.length, B.length);
  for (let i = 0; i < n; i++) diff |= (A[i] ?? 0) ^ (B[i] ?? 0);
  return diff === 0;
}

async function sha256Hex(s) {
  const d = await crypto.subtle.digest('SHA-256', enc.encode(s));
  return [...new Uint8Array(d)]
    .map((b) => b.toString(16).padStart(2, '0')).join('');
}

function newApiKey() {
  const raw = crypto.getRandomValues(new Uint8Array(24));
  const body = [...raw].map((b) => b.toString(16).padStart(2, '0')).join('');
  return `mgr_live_${body}`;
}

// ─── Supabase (service role) ─────────────────────────────────────────────
async function sb(env, path, opts = {}) {
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/${path}`, {
    ...opts,
    headers: {
      apikey: env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
      'content-type': 'application/json',
      ...(opts.headers || {}),
    },
  });
  const text = await r.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  return { ok: r.ok, status: r.status, body };
}

// ─── Razorpay ────────────────────────────────────────────────────────────
async function razorpay(env, path, method = 'GET', payload) {
  const auth = btoa(`${env.RAZORPAY_KEY_ID}:${env.RAZORPAY_KEY_SECRET}`);
  const r = await fetch(`https://api.razorpay.com/v1/${path}`, {
    method,
    headers: {
      Authorization: `Basic ${auth}`,
      'content-type': 'application/json',
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const body = await r.json().catch(() => null);
  return { ok: r.ok, status: r.status, body };
}

// ─── entitlement ─────────────────────────────────────────────────────────
// Razorpay's own status vocabulary. `authenticated` means the mandate is set
// up but the first charge has not landed; `active` means it has. Both grant
// access — a jeweller who has authorised an auto-debit has done everything
// asked of them, and making them wait for the first settlement would be a
// poor first impression. `halted` (retries exhausted) and `cancelled` do not.
const LIVE_STATUSES = new Set(['active', 'authenticated']);

async function entitlementFor(env, accountId) {
  const { body } = await sb(env,
    `jd_subscriptions?account_id=eq.${accountId}` +
    `&select=status,current_end,razorpay_subscription_id` +
    `&order=updated_at.desc&limit=1`);
  const s = Array.isArray(body) ? body[0] : null;
  if (!s) return { active: false, reason: 'no subscription' };
  if (!LIVE_STATUSES.has(s.status)) {
    return { active: false, reason: `subscription ${s.status}`, status: s.status };
  }
  // A period that ended is not entitlement, whatever the status says: if a
  // charge silently failed to renew, current_end is the honest signal.
  if (s.current_end && new Date(s.current_end) < new Date()) {
    return { active: false, reason: 'period ended', status: s.status,
             current_end: s.current_end };
  }
  return { active: true, status: s.status, current_end: s.current_end };
}

async function authenticate(env, request) {
  const h = request.headers.get('Authorization') || '';
  const m = h.match(/^Bearer\s+(mgr_live_[a-f0-9]{48})$/);
  if (!m) return { ok: false, error: 'missing or malformed API key' };
  const hash = await sha256Hex(m[1]);
  const { body } = await sb(env,
    `jd_api_keys?key_hash=eq.${hash}&active=is.true` +
    `&select=id,account_id&limit=1`);
  const k = Array.isArray(body) ? body[0] : null;
  if (!k) return { ok: false, error: 'unknown or revoked API key' };
  // Best-effort last-used stamp; never let it fail the request.
  sb(env, `jd_api_keys?id=eq.${k.id}`, {
    method: 'PATCH',
    body: JSON.stringify({ last_used_at: new Date().toISOString() }),
  }).catch(() => {});
  return { ok: true, accountId: k.account_id };
}

async function requireEntitled(env, request) {
  const a = await authenticate(env, request);
  if (!a.ok) return { resp: json({ error: a.error }, 401) };
  const e = await entitlementFor(env, a.accountId);
  if (!e.active) {
    return { resp: json({ error: 'subscription not active', detail: e }, 402) };
  }
  return { accountId: a.accountId, entitlement: e };
}

export default {
  async fetch(request, env) {
    const c = cors(request);
    const wrap = (res) => {
      const out = new Response(res.body, res);
      for (const [k, v] of Object.entries(c)) out.headers.set(k, v);
      return out;
    };
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: c });
    }
    const url = new URL(request.url);
    try {
      switch (`${request.method} ${url.pathname}`) {
        case 'POST /jd/signup':   return wrap(await handleSignup(request, env));
        case 'POST /jd/webhook':  return wrap(await handleWebhook(request, env));
        case 'GET /jd/status':    return wrap(await handleStatus(request, env));
        case 'GET /jd/report':    return wrap(await handleReport(request, env));
        case 'GET /jd/rates':     return wrap(await handleRates(request, env, url));
        default:                   return wrap(json({ error: 'not found' }, 404));
      }
    } catch (e) {
      // Never surface internals to a caller; the message could carry a URL
      // with a key in it.
      console.error('jd worker error', e && e.stack);
      return wrap(json({ error: 'internal error' }, 500));
    }
  },
};

// ─── POST /jd/signup ────────────────────────────────────────────────────
// Creates (or reuses) the account, then a Razorpay subscription, and returns
// the short_url where the jeweller authorises the auto-debit mandate.
//
// The API key is generated and returned HERE, before any money has moved,
// but it grants nothing on its own: every paid route checks entitlement
// separately, and entitlement only turns on when a webhook says the mandate
// is authenticated or charged. Handing the key over up front means the
// jeweller can wire it into their systems while the mandate settles.
async function handleSignup(request, env) {
  let b;
  try { b = await request.json(); } catch { return json({ error: 'bad JSON' }, 400); }

  const email = String(b.email || '').trim().toLowerCase();
  const phone = String(b.phone || '').replace(/\D/g, '');
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: 'valid email required' }, 400);
  }
  const digits = phone.length > 10 && phone.startsWith('91')
    ? phone.slice(2) : phone;
  if (!/^[6-9]\d{9}$/.test(digits)) {
    return json({ error: 'valid 10-digit mobile number required' }, 400);
  }
  if (!env.RAZORPAY_PLAN_ID) {
    return json({ error: 'billing not configured' }, 503);
  }

  // Upsert the account by email so a second signup lands on the same row
  // rather than creating a duplicate that could be charged separately.
  const up = await sb(env, 'jd_accounts?on_conflict=email', {
    method: 'POST',
    headers: { Prefer: 'resolution=merge-duplicates,return=representation' },
    body: JSON.stringify([{
      email,
      business_name: (b.business_name || '').trim() || null,
      phone: `+91${digits}`,
      city: (b.city || '').trim() || null,
      state: (b.state || '').trim() || null,
    }]),
  });
  if (!up.ok) return json({ error: 'could not create account' }, 502);
  const account = Array.isArray(up.body) ? up.body[0] : up.body;

  // total_count is required by Razorpay and is the number of billing cycles
  // the mandate may run for. 120 months is "until cancelled" in practice
  // without claiming an unlimited mandate the customer never agreed to.
  const sub = await razorpay(env, 'subscriptions', 'POST', {
    plan_id: env.RAZORPAY_PLAN_ID,
    total_count: 120,
    customer_notify: 1,
    notes: { account_id: String(account.id), email },
  });
  if (!sub.ok || !sub.body?.id) {
    console.error('razorpay subscription create failed', sub.status);
    return json({ error: 'could not start subscription' }, 502);
  }

  await sb(env, 'jd_subscriptions', {
    method: 'POST',
    headers: { Prefer: 'resolution=merge-duplicates' },
    body: JSON.stringify([{
      account_id: account.id,
      razorpay_subscription_id: sub.body.id,
      razorpay_plan_id: env.RAZORPAY_PLAN_ID,
      razorpay_customer_id: sub.body.customer_id || null,
      status: sub.body.status || 'created',
    }]),
  });

  // Issue an API key once. Only its hash is stored, so this response is the
  // single moment the plaintext exists — it cannot be re-read later.
  const key = newApiKey();
  const ins = await sb(env, 'jd_api_keys', {
    method: 'POST',
    body: JSON.stringify([{
      account_id: account.id,
      key_prefix: key.slice(0, 17),
      key_hash: await sha256Hex(key),
    }]),
  });
  if (!ins.ok) return json({ error: 'could not issue API key' }, 502);

  return json({
    account_id: account.id,
    subscription_id: sub.body.id,
    status: sub.body.status,
    authorise_url: sub.body.short_url,
    api_key: key,
    api_key_notice: 'Shown once. Store it now — it cannot be retrieved later.',
    next: 'Open authorise_url to approve the auto-debit mandate. Access turns '
        + 'on as soon as Razorpay confirms it.',
  });
}

// ─── POST /jd/webhook ───────────────────────────────────────────────────
// Razorpay -> us. Two things matter here and both are security-critical.
//
// 1. SIGNATURE. The body is HMAC-SHA256'd with the webhook secret and sent
//    as X-Razorpay-Signature. Anyone can POST to this URL, so an unverified
//    handler would let a stranger grant themselves a subscription. Verified
//    against the RAW body text — re-serialising parsed JSON would change
//    byte order and break the comparison.
//
// 2. IDEMPOTENCY. Razorpay retries until it gets a 2xx, so every event will
//    arrive more than once. The unique index on jd_webhook_events.event_id
//    is the guard: a duplicate insert conflicts, and we return 200 without
//    reprocessing. Returning non-2xx on a duplicate would make Razorpay
//    retry forever.
async function handleWebhook(request, env) {
  const raw = await request.text();
  const given = request.headers.get('X-Razorpay-Signature') || '';
  if (!env.RAZORPAY_WEBHOOK_SECRET) {
    return json({ error: 'webhook not configured' }, 503);
  }
  const expected = await hmacHex(env.RAZORPAY_WEBHOOK_SECRET, raw);
  if (!timingSafeEqual(given, expected)) {
    // Deliberately terse: an attacker probing this endpoint learns nothing
    // about why their signature was wrong.
    return json({ error: 'invalid signature' }, 401);
  }

  let evt;
  try { evt = JSON.parse(raw); } catch { return json({ error: 'bad JSON' }, 400); }

  // Razorpay's x-razorpay-event-id header is the stable per-delivery id.
  const eventId = request.headers.get('X-Razorpay-Event-Id')
    || `${evt.event}:${evt.payload?.subscription?.entity?.id || ''}:${evt.created_at || ''}`;

  const seen = await sb(env, 'jd_webhook_events', {
    method: 'POST',
    body: JSON.stringify([{ event_id: eventId, event: evt.event, payload: evt }]),
  });
  if (!seen.ok) {
    // 409 is the unique-index conflict: already handled, so acknowledge and
    // stop. Anything else is a real storage failure — return non-2xx so
    // Razorpay retries rather than dropping the event.
    if (seen.status === 409) return json({ ok: true, duplicate: true });
    console.error('webhook store failed', seen.status);
    return json({ error: 'could not record event' }, 500);
  }

  const subEnt = evt.payload?.subscription?.entity;
  const payEnt = evt.payload?.payment?.entity;

  if (subEnt?.id) {
    const patch = {
      status: subEnt.status || 'created',
      last_event_at: new Date().toISOString(),
    };
    if (subEnt.current_start) {
      patch.current_start = new Date(subEnt.current_start * 1000).toISOString();
    }
    if (subEnt.current_end) {
      patch.current_end = new Date(subEnt.current_end * 1000).toISOString();
    }
    if (typeof subEnt.paid_count === 'number') patch.charge_count = subEnt.paid_count;
    await sb(env,
      `jd_subscriptions?razorpay_subscription_id=eq.${subEnt.id}`,
      { method: 'PATCH', body: JSON.stringify(patch) });
  }

  if (payEnt?.id) {
    const { body } = await sb(env,
      `jd_subscriptions?razorpay_subscription_id=eq.${subEnt?.id || ''}` +
      `&select=id,account_id&limit=1`);
    const row = Array.isArray(body) ? body[0] : null;
    await sb(env, 'jd_payments', {
      method: 'POST',
      headers: { Prefer: 'resolution=ignore-duplicates' },
      body: JSON.stringify([{
        account_id: row?.account_id ?? null,
        subscription_id: row?.id ?? null,
        razorpay_payment_id: payEnt.id,
        razorpay_invoice_id: evt.payload?.invoice?.entity?.id ?? null,
        amount_paise: payEnt.amount ?? 0,
        currency: payEnt.currency || 'INR',
        status: payEnt.status || null,
        method: payEnt.method || null,
      }]),
    });
  }

  await sb(env, `jd_webhook_events?event_id=eq.${encodeURIComponent(eventId)}`,
    { method: 'PATCH', body: JSON.stringify({ processed: true }) });

  return json({ ok: true, event: evt.event });
}

// ─── GET /jd/status ─────────────────────────────────────────────────────
async function handleStatus(request, env) {
  const a = await authenticate(env, request);
  if (!a.ok) return json({ error: a.error }, 401);
  const e = await entitlementFor(env, a.accountId);
  return json({ account_id: a.accountId, entitlement: e });
}

// ─── GET /jd/report ─────────────────────────────────────────────────────
// Returns a SHORT-LIVED signed URL rather than the file. The bucket is
// private, so the URL is the only way in, and a 10-minute expiry means a
// link that leaks out of an inbox stops working quickly.
async function handleReport(request, env) {
  const gate = await requireEntitled(env, request);
  if (gate.resp) return gate.resp;

  const list = await fetch(
    `${env.SUPABASE_URL}/storage/v1/object/list/jd-reports`, {
      method: 'POST',
      headers: {
        apikey: env.SUPABASE_SERVICE_KEY,
        Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({ limit: 1, sortBy: { column: 'name', order: 'desc' } }),
    });
  const files = await list.json().catch(() => null);
  const latest = Array.isArray(files) ? files[0] : null;
  if (!latest?.name) {
    return json({ error: 'no report available yet' }, 404);
  }

  const signed = await fetch(
    `${env.SUPABASE_URL}/storage/v1/object/sign/jd-reports/${latest.name}`, {
      method: 'POST',
      headers: {
        apikey: env.SUPABASE_SERVICE_KEY,
        Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({ expiresIn: 600 }),
    });
  const s = await signed.json().catch(() => null);
  if (!s?.signedURL) return json({ error: 'could not sign report URL' }, 502);

  return json({
    report: latest.name,
    url: `${env.SUPABASE_URL}/storage/v1${s.signedURL}`,
    expires_in_seconds: 600,
  });
}

// ─── GET /jd/rates ──────────────────────────────────────────────────────
// The scraped history as JSON, for a jeweller who would rather pull it into
// their own systems than open a spreadsheet.
//
// Only brands currently on the board, and only published rows — the same
// filter the workbook uses, so the API and the spreadsheet can never
// disagree about what the data is.
async function handleRates(request, env, url) {
  const gate = await requireEntitled(env, request);
  if (gate.resp) return gate.resp;

  const days = Math.min(400, Math.max(1, parseInt(url.searchParams.get('days') || '90', 10)));
  const since = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);

  const [{ body: rates }, { body: brands }] = await Promise.all([
    sb(env, `rates?rate_date=gte.${since}&status=eq.published` +
            `&select=rate_date,brand_id,canonical_24k_pre_gst` +
            `&order=rate_date.asc&limit=20000`),
    sb(env, 'brands?active=is.true&select=id,slug,name'),
  ]);
  if (!Array.isArray(rates) || !Array.isArray(brands)) {
    return json({ error: 'upstream unavailable' }, 502);
  }
  const byId = Object.fromEntries(brands.map((b) => [b.id, b]));
  const rows = rates
    .filter((r) => byId[r.brand_id])
    .map((r) => ({
      date: r.rate_date,
      brand: byId[r.brand_id].slug,
      name: byId[r.brand_id].name,
      rate_24k_per_gram_pre_gst: Number(r.canonical_24k_pre_gst),
    }));

  return json({
    from: since,
    days,
    brands: brands.length,
    rows: rows.length,
    note: '24K, pre-GST, per gram, as published by each jeweller. Excludes '
        + 'brands no longer on the board. No bullion benchmark is included: '
        + 'no daily IBJA series is stored, so premium-over-bullion cannot be '
        + 'computed for past dates.',
    data: rows,
  });
}
