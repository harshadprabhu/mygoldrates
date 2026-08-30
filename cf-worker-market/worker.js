/**
 * MyGoldRates Market API — CORS-open JSON proxy for the app-test Market
 * Pulse view (and anything else that wants live gold/silver data).
 *
 * Endpoints (all GET, all Access-Control-Allow-Origin: *):
 *
 *   /market            — bundled { gold_usd, silver_usd, usd_inr,
 *                        mcx_gold, mcx_silver, updated_at } in one call
 *   /ohlc?sym=XAU      — 90-day daily OHLC candles for XAU or XAG (Stooq)
 *   /calendar          — this week's US economic events (ForexFactory)
 *   /news              — filtered gold + silver headlines (Moneycontrol RSS)
 *   /vendors           — India national bullion reference rates (IBJA)
 *
 * All responses are edge-cached with a TTL tuned to how often the upstream
 * moves, so under load the origin fetch cost per client is near-zero:
 *   /market   — 5s   (spot prices tick fast)
 *   /vendors  — 60s  (IBJA is a daily reference, but we don't want to be
 *                     stuck on the previous day's cache after a mid-day
 *                     bump; a minute is plenty)
 *   /news     — 5min (headlines don't move that fast)
 *   /calendar — 1h   (weekly schedule, one hour is fine)
 *   /ohlc     — 6h   (daily candles regenerate once per session)
 */

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '86400',
};

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36';

function json(body, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...CORS,
      ...extraHeaders,
    },
  });
}

function jsonErr(message, status = 502) {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...CORS },
  });
}

// Small helper — soft-fails a fetch so a single upstream miss never sinks a
// bundled call. Times out at 8s so nothing blocks the worker's 30s cap.
async function safeFetchJson(url, opts = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), opts.timeoutMs || 8000);
  try {
    const r = await fetch(url, {
      cf: { cacheTtl: opts.cacheTtl || 5 },
      headers: { 'user-agent': UA, accept: 'application/json,*/*' },
      signal: ctrl.signal,
    });
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    return null;
  } finally {
    clearTimeout(t);
  }
}

async function safeFetchText(url, opts = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), opts.timeoutMs || 10000);
  try {
    const r = await fetch(url, {
      cf: { cacheTtl: opts.cacheTtl || 60 },
      headers: { 'user-agent': UA, accept: opts.accept || 'text/html,*/*' },
      signal: ctrl.signal,
    });
    if (!r.ok) return null;
    return await r.text();
  } catch (e) {
    return null;
  } finally {
    clearTimeout(t);
  }
}

// Cache API wrapper — a per-endpoint edge cache with a fixed TTL so repeated
// browser hits at 10s cadence collapse into one origin fetch per TTL window.
async function withCache(request, ttlSeconds, computeFn) {
  const cache = caches.default;
  const cacheKey = new Request(request.url, { method: 'GET' });
  const hit = await cache.match(cacheKey);
  if (hit) return hit;
  const fresh = await computeFn();
  if (fresh.status === 200) {
    const cloned = new Response(fresh.body, fresh);
    cloned.headers.set('cache-control', `public, max-age=${ttlSeconds}`);
    await cache.put(cacheKey, cloned.clone());
    return cloned;
  }
  return fresh;
}

// ─── /market ────────────────────────────────────────────────────────────
// Bundles the four calls app-test currently makes in parallel into one
// server-side round-trip. Reduces per-tick browser traffic and lets us
// share the same 5s edge cache across every viewer.
async function handleMarket() {
  const mcxExpiries = mcxCandidateExpiries();
  const [xau, xag, fx, mcxG, mcxS] = await Promise.all([
    safeFetchJson('https://api.gold-api.com/price/XAU'),
    safeFetchJson('https://api.gold-api.com/price/XAG'),
    safeFetchJson('https://open.er-api.com/v6/latest/USD'),
    findMcx('GOLD', mcxExpiries),
    findMcx('SILVER', mcxExpiries),
  ]);
  return json({
    gold_usd: xau?.price ?? null,
    silver_usd: xag?.price ?? null,
    usd_inr: fx?.rates?.INR ?? null,
    mcx_gold: mcxG ? { ltp: mcxG.ltp, expiry: mcxG.expiry, pchg: mcxG.pchg } : null,
    mcx_silver: mcxS ? { ltp: mcxS.ltp, expiry: mcxS.expiry, pchg: mcxS.pchg } : null,
    updated_at: new Date().toISOString(),
  });
}

function mcxCandidateExpiries() {
  const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const now = new Date();
  const out = [];
  for (let m = 0; m < 5; m++) {
    const d = new Date(now.getFullYear(), now.getMonth() + m, 1);
    const ym = months[d.getMonth()] + d.getFullYear();
    for (const day of ['05', '04', '06']) out.push(day + ym);
  }
  return out;
}

async function findMcx(symbol, expiries) {
  for (const exp of expiries) {
    const j = await safeFetchJson(
      `https://priceapi.moneycontrol.com/pricefeed/mcx/commodityfuture/${symbol}?expiry=${exp}`,
      { cacheTtl: 5 }
    );
    if (j?.code === '200' && j?.data?.pricecurrent) {
      const ltp = parseFloat(j.data.pricecurrent);
      if (ltp > 0) {
        return {
          ltp,
          expiry: j.data.EXPIRY || exp,
          pchg: parseFloat(j.data.pricepercentchange || 0),
        };
      }
    }
  }
  return null;
}

// ─── /ohlc ──────────────────────────────────────────────────────────────
// 90-day daily OHLC from Stooq (free, no auth). We use their CSV endpoint
// and parse in the worker so the browser gets clean JSON with a compact
// [{t,o,h,l,c}] shape.
async function handleOhlc(url) {
  const sym = (url.searchParams.get('sym') || 'XAU').toUpperCase();
  const range = parseInt(url.searchParams.get('range') || '90', 10);
  const map = { XAU: 'xauusd', XAG: 'xagusd' };
  const stooqSym = map[sym];
  if (!stooqSym) return jsonErr(`unsupported sym: ${sym}`, 400);
  const now = new Date();
  const past = new Date(now.getTime() - range * 86400000);
  const fmt = d => d.toISOString().slice(0, 10).replace(/-/g, '');
  const stooqUrl = `https://stooq.com/q/d/l/?s=${stooqSym}&d1=${fmt(past)}&d2=${fmt(now)}&i=d`;
  const csv = await safeFetchText(stooqUrl, { accept: 'text/csv', cacheTtl: 21600 });
  if (!csv || csv.startsWith('No data')) return jsonErr('ohlc upstream returned no data', 502);
  const lines = csv.trim().split(/\r?\n/);
  const header = lines.shift();
  if (!/^Date,Open,High,Low,Close/i.test(header || '')) return jsonErr('ohlc upstream format changed', 502);
  const out = [];
  for (const ln of lines) {
    const [date, o, h, l, c] = ln.split(',');
    if (!date || !c) continue;
    const t = Math.floor(new Date(date + 'T00:00:00Z').getTime() / 1000);
    out.push({ t, o: +o, h: +h, l: +l, c: +c });
  }
  return json({ symbol: sym, range_days: range, candles: out, updated_at: new Date().toISOString() });
}

// ─── /calendar ──────────────────────────────────────────────────────────
// This week's US economic events, from FairEconomy's ForexFactory XML feed.
async function handleCalendar() {
  const xml = await safeFetchText(
    'https://nfs.faireconomy.media/ff_calendar_thisweek.xml',
    { accept: 'text/xml', cacheTtl: 3600 }
  );
  if (!xml) return jsonErr('calendar upstream unavailable', 502);
  // Parse <event>…</event> blocks with regex — the feed is small (~30KB)
  // and shallow, so DOM machinery is overkill.
  const events = [];
  const eventRe = /<event>([\s\S]*?)<\/event>/g;
  const field = (block, tag) => {
    const m = block.match(new RegExp(`<${tag}(?:><\\!\\[CDATA\\[([\\s\\S]*?)\\]\\]>|>([\\s\\S]*?))<\\/${tag}>`, 'i'));
    return m ? (m[1] ?? m[2] ?? '').trim() : '';
  };
  let m;
  while ((m = eventRe.exec(xml)) !== null) {
    const block = m[1];
    const country = field(block, 'country');
    if (country && country.toUpperCase() !== 'USD' && country.toUpperCase() !== 'US') continue;
    const dateStr = field(block, 'date');
    const timeStr = field(block, 'time');
    events.push({
      title: field(block, 'title'),
      country: country || 'USD',
      date: dateStr,
      time: timeStr,
      impact: field(block, 'impact'),
      forecast: field(block, 'forecast'),
      previous: field(block, 'previous'),
      actual: field(block, 'actual'),
      url: field(block, 'url'),
    });
  }
  return json({ events, updated_at: new Date().toISOString() });
}

// ─── /news ──────────────────────────────────────────────────────────────
// Gold + silver + bullion headlines from Moneycontrol RSS (business +
// latestnews feeds), deduped and keyword-filtered.
const NEWS_FEEDS = [
  'https://www.moneycontrol.com/rss/business.xml',
  'https://www.moneycontrol.com/rss/latestnews.xml',
];
const NEWS_KEYWORDS = /(gold|silver|bullion|xau|xag|mcx|ibja)/i;

async function handleNews() {
  const bodies = await Promise.all(
    NEWS_FEEDS.map(u => safeFetchText(u, { accept: 'application/xml', cacheTtl: 300 }))
  );
  const seen = new Set();
  const items = [];
  for (const body of bodies) {
    if (!body) continue;
    const itemRe = /<item>([\s\S]*?)<\/item>/g;
    let m;
    while ((m = itemRe.exec(body)) !== null) {
      const block = m[1];
      const grab = tag => {
        const mm = block.match(new RegExp(`<${tag}(?:><!\\[CDATA\\[([\\s\\S]*?)\\]\\]>|>([\\s\\S]*?))<\\/${tag}>`, 'i'));
        return mm ? (mm[1] ?? mm[2] ?? '').trim() : '';
      };
      const title = grab('title');
      const link = grab('link');
      const pub = grab('pubDate');
      if (!title || !link || title.length < 15) continue;
      if (!NEWS_KEYWORDS.test(title)) continue;
      if (seen.has(link)) continue;
      seen.add(link);
      items.push({ title, url: link, source: 'Moneycontrol', published: pub });
    }
  }
  items.sort((a, b) => (new Date(b.published) - new Date(a.published)));
  return json({ items: items.slice(0, 12), updated_at: new Date().toISOString() });
}

// ─── /vendors ───────────────────────────────────────────────────────────
// Live bullion vendor rates. Two data planes wired in parallel:
//
//   * VOTS Broadcast Streaming — a shared bullion-industry price streaming
//     stack (bcast.<dealer>.<tld>/VOTSBroadcastStreaming/Services/xml/
//     GetLiveRateByTemplateID/<templateId>). Response is newline-separated,
//     tab-delimited rows: script_code \t script_name \t buy \t sell \t
//     high \t low. Multiple bullion dealers publish through this service —
//     we probe the known ones (Arihant, Safari, Parker) and use whichever
//     answer this tick. This is the same underlying data finmetpulse.com
//     surfaces in its dealer rate tables.
//
//   * IBJA HTML scrape — national bullion reference rate, kept as a
//     "national" scope row so users see a benchmark alongside the dealers.
//
// Each dealer is queried independently and soft-fails; a single dealer
// down never blocks the others. Row shape is normalized so app-test can
// render one table across sources.
const VOTS_DEALERS = [
  { id: 'arihant',  name: 'Arihant Spot',    city: 'Mumbai',    zone: 'West',
    host: 'bcast.arihantspot.in',
    templates: ['arihant', 'arihantcoins', 'arihantsilver'],
    site: 'https://www.arihantspot.in/' },
  { id: 'safari',   name: 'Safari Bullion',  city: 'Mumbai',    zone: 'West',
    host: 'bcast.safaribullions.com',
    templates: ['safari', 'safaricoins', 'safarisilver'],
    site: 'https://www.safaribullion.com/' },
  { id: 'parker',   name: 'Parker Bullion',  city: 'Ahmedabad', zone: 'West',
    host: 'bcast.parkerbullion.in',
    templates: ['parker', 'parkercoins', 'parkersilver'],
    site: 'https://parkerbullion.in/' },
  { id: 'rsbl',     name: 'RSBL',            city: 'Mumbai',    zone: 'West',
    host: 'bcast.rsbl.co.in',
    templates: ['rsbl', 'rsblcoins', 'rsblsilver'],
    site: 'https://www.rsbl.co.in/' },
  { id: 'amrapali', name: 'Amrapali Spot',   city: 'Ahmedabad', zone: 'West',
    host: 'bcast.amrapalispot.com',
    templates: ['amrapali', 'amrapalicoins', 'amrapalisilver'],
    site: 'https://www.amrapalispot.com/' },
];

// Parse a VOTS tab-delimited body into { code, name, buy, sell, high, low } rows.
// Empty / hyphen fields become null. Skips header noise & malformed lines.
function parseVots(text) {
  if (!text || text === 'Not Found.') return [];
  const out = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/^\t/, '').trim();
    if (!line) continue;
    const cols = line.split('\t').map(s => s.trim());
    if (cols.length < 4) continue;
    const num = v => {
      if (!v || v === '-' || v === '' || v === '0') return null;
      const n = parseFloat(v.replace(/,/g, ''));
      return isFinite(n) && n > 0 ? n : null;
    };
    const code = cols[0], name = cols[1];
    if (!code || !name) continue;
    if (name.toLowerCase() === 'script name') continue;
    out.push({
      code, name,
      buy:  num(cols[2]),
      sell: num(cols[3]),
      high: num(cols[4]),
      low:  num(cols[5]),
    });
  }
  return out;
}

// Reduce a dealer's raw rows into headline gold_999 / gold_995 / silver_999
// numbers by matching common phrasing patterns from their script names.
function extractHeadlineRates(rows) {
  const pick = (predicate, prefer) => {
    const matches = rows.filter(r => predicate(r.name));
    if (!matches.length) return null;
    // Prefer 1kg IND-BIS if available, then any with a sell price.
    const preferred = matches.find(r => prefer.test(r.name) && (r.sell || r.buy));
    const first = preferred || matches.find(r => r.sell || r.buy);
    if (!first) return null;
    return { commodity: first.name, price: first.sell || first.buy };
  };
  const gold999 = pick(n => /999/.test(n) && /GOLD/i.test(n), /1\s*kg|IND-?BIS/i);
  const gold995 = pick(n => /995/.test(n) && /GOLD/i.test(n), /1\s*kg|IND-?BIS/i);
  const silver999 = pick(n => /SILVER/i.test(n) && !/COST|GST/i.test(n), /1\s*kg|IND-?BIS|IMPORTED/i);
  return { gold_999: gold999, gold_995: gold995, silver_999: silver999 };
}

async function fetchOneDealer(d) {
  // Fire all templates in parallel, merge rows.
  const results = await Promise.all(
    d.templates.map(t =>
      safeFetchText(
        `https://${d.host}/VOTSBroadcastStreaming/Services/xml/GetLiveRateByTemplateID/${t}`,
        { accept: 'text/plain', cacheTtl: 5, timeoutMs: 6000 }
      )
    )
  );
  const rows = [];
  for (const body of results) rows.push(...parseVots(body));
  if (!rows.length) return null;
  const headline = extractHeadlineRates(rows);
  return {
    dealer_id: d.id,
    dealer: d.name,
    city: d.city,
    zone: d.zone,
    site: d.site,
    gold_999: headline.gold_999,
    gold_995: headline.gold_995,
    silver_999: headline.silver_999,
    all_rows: rows,      // full grid available for a "show all rates" view
    row_count: rows.length,
    timestamp: new Date().toISOString(),
  };
}

async function fetchIbja() {
  const html = await safeFetchText('https://ibjarates.com/', { accept: 'text/html', cacheTtl: 60 });
  if (!html) return null;
  const text = html.replace(/<[^>]+>/g, ' ');
  const grab = purity => {
    const re = new RegExp(purity + '\\D{0,60}?([\\d,]{6,7})');
    const m = text.match(re);
    if (!m) return null;
    const v = parseFloat(m[1].replace(/,/g, '')) / 10;
    return v >= 8000 && v <= 22000 ? v : null;
  };
  const r999 = grab('999');
  const r916 = grab('916');
  if (!r999 || !r916) return null;
  return {
    dealer_id: 'ibja',
    dealer: 'IBJA',
    city: 'National',
    zone: 'National',
    site: 'https://ibjarates.com/',
    gold_999: { commodity: 'IBJA 999 24K', price: r999 },
    gold_995: null,
    silver_999: null,
    all_rows: [
      { code: 'IBJA999', name: 'IBJA 999 24K', buy: null, sell: r999, high: null, low: null },
      { code: 'IBJA916', name: 'IBJA 916 22K', buy: null, sell: r916, high: null, low: null },
    ],
    row_count: 2,
    timestamp: new Date().toISOString(),
  };
}

async function handleVendors() {
  const [ibja, ...dealers] = await Promise.all([
    fetchIbja(),
    ...VOTS_DEALERS.map(fetchOneDealer),
  ]);
  const vendors = [];
  if (ibja) vendors.push(ibja);
  for (const d of dealers) if (d) vendors.push(d);
  return json({
    vendors,
    count: vendors.length,
    note: vendors.length ? null : 'No vendor feeds responded this tick',
    updated_at: new Date().toISOString(),
  });
}

// ─── router ─────────────────────────────────────────────────────────────

const ROUTES = {
  '/market':   { ttl: 5,     fn: (req) => handleMarket() },
  '/ohlc':     { ttl: 21600, fn: (req, url) => handleOhlc(url) },
  '/calendar': { ttl: 3600,  fn: (req) => handleCalendar() },
  '/news':     { ttl: 300,   fn: (req) => handleNews() },
  '/vendors':  { ttl: 60,    fn: (req) => handleVendors() },
};

async function root() {
  return json({
    name: 'mygoldrates-market-api',
    endpoints: Object.keys(ROUTES),
    updated_at: new Date().toISOString(),
  });
}

export default {
  async fetch(request) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (request.method !== 'GET') {
      return new Response('method not allowed', { status: 405, headers: CORS });
    }
    const url = new URL(request.url);
    if (url.pathname === '/' || url.pathname === '') return root();
    const route = ROUTES[url.pathname];
    if (!route) return new Response('not found', { status: 404, headers: CORS });
    return withCache(request, route.ttl, () => route.fn(request, url));
  },
};
