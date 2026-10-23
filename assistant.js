/* Sona - the MyGoldRates jewellery assistant.
 *
 * Answers in the visitor's browser from /assistant.json, which the site build
 * writes every run from the same data as the pages (assistant_kb.py). No
 * server, no paid AI: questions are matched to an intent (rate, cheapest,
 * compare, making charges, offers, price of a weight, trend, FAQ...) and the
 * answer is filled in with today's real numbers, so it can never invent one.
 *
 * Questions are logged to the private database (redacted: no emails or long
 * numbers) so the owner can see what people ask and approve answers for the
 * ones Sona could not handle; approved answers come back through the
 * knowledge file (data/assistant_answers.json in git).
 */
(function () {
  if (window.__sona) return; window.__sona = 1;
  if (/^\/(analytics|unsubscribe|404)(\.html)?\/?$/.test(location.pathname)) return;

  var SB = (window.GR_SB_URL || '').replace(/\/$/, ''), KEY = window.GR_SB_KEY || '';
  var KB = null, kbWait = null, opened = false, lastCity = null;
  try { lastCity = localStorage.getItem('sona_city'); } catch (_) {}

  // ------------------------------------------------------------ helpers
  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function inr(n) { return '₹' + Math.round(n).toLocaleString('en-IN'); }
  function pct(n) { return (Math.round(n * 10) / 10).toLocaleString('en-IN') + '%'; }
  var K = { '24K': 1, '22K': 22 / 24, '18K': 18 / 24, '14K': 14 / 24 };
  function rate(b, k) { return b.r24 * K[k]; }
  function track(t) { try { if (window.GR_TRACK) window.GR_TRACK('click_events', { page: location.pathname, target: 'sona:' + t, session_id: window.GR_SID || '' }); } catch (_) {} }
  function rpc(fn, body) {
    if (!SB || !KEY) return Promise.resolve(null);
    return fetch(SB + '/rest/v1/rpc/' + fn, { method: 'POST', headers: { 'Content-Type': 'application/json', apikey: KEY, Authorization: 'Bearer ' + KEY }, body: JSON.stringify(body) })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function redact(q) { return String(q).replace(/[^\s@]+@[^\s@]+/g, '[email]').replace(/\+?\d[\d\s-]{6,}\d/g, '[number]').slice(0, 300); }

  function loadKB() {
    if (KB) return Promise.resolve(KB);
    if (kbWait) return kbWait;
    kbWait = fetch('/assistant.json?d=' + new Date().toISOString().slice(0, 13)).then(function (r) { return r.json(); })
      .then(function (d) { KB = d; prep(d); return d; });
    return kbWait;
  }

  // ------------------------------------------------------- understanding
  var CITY_ALIAS = { bangalore: 'bengaluru', bombay: 'mumbai', calcutta: 'kolkata', madras: 'chennai', gurgaon: 'gurugram', vizag: 'visakhapatnam', mysore: 'mysuru', trivandrum: 'thiruvananthapuram', calicut: 'kozhikode', cochin: 'kochi', ernakulam: 'kochi', baroda: 'vadodara', pondicherry: 'puducherry', benaras: 'varanasi', banaras: 'varanasi', poona: 'pune', mangalore: 'mangaluru', hubli: 'hubballi', 'new delhi': 'delhi', ncr: 'delhi' };
  var BRAND_EXTRA = { tbz: 'tbz', 'pn gadgil and sons': 'pngsons', 'png sons': 'pngsons', 'pn gadgil & sons': 'pngsons', 'pn gadgil': 'png', png: 'png', gadgil: 'png', whp: 'whp', 'waman hari': 'whp', ckc: 'ckc', krishniah: 'ckc', 'pc chandra': 'pcchandra', grt: 'grt', avr: 'avr', nac: 'nac', 'jos alukkas': 'josalukkas', joyalukkas: 'joyalukkas', 'joy alukkas': 'joyalukkas' };
  var aliases = [], cityIdx = [];
  function prep(d) {
    aliases = [];
    d.brands.forEach(function (b) {
      var n = b.n.toLowerCase().replace(/[.]/g, '');
      var short = n.replace(/\b(jewell?ers?|jewell?ery|jewels|gold|diamonds?|and|&|sons|swarna mahal|bangaru)\b/g, ' ').replace(/\s+/g, ' ').trim();
      [n, short, b.s].forEach(function (a) { if (a && a.length >= 3) aliases.push([a, b.s]); });
    });
    Object.keys(BRAND_EXTRA).forEach(function (a) { if (d.brands.some(function (b) { return b.s === BRAND_EXTRA[a]; })) aliases.push([a, BRAND_EXTRA[a]]); });
    aliases.sort(function (x, y) { return y[0].length - x[0].length; });     // longest first: "pn gadgil & sons" before "pn gadgil"
    cityIdx = d.cities.map(function (c) { return [c.n.toLowerCase(), c]; }).sort(function (x, y) { return y[0].length - x[0].length; });
  }
  function norm(q) {
    return (' ' + q.toLowerCase() + ' ')
      .replace(/[‘’']/g, '')
      .replace(/\b(24|22|18|14)\s*(?:k|kt|ct|carat|karat|caret)\b/g, ' $1k ')
      .replace(/\b999\b/g, ' 24k ').replace(/\b916\b/g, ' 22k ').replace(/\b750\b/g, ' 18k ')
      .replace(/[?!,;:()]/g, ' ').replace(/\s+/g, ' ');
  }
  function brandsIn(t) {
    var found = [], used = t;
    aliases.forEach(function (a) {
      var rx = new RegExp('(^|[^a-z])' + a[0].replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?=$|[^a-z])');
      if (rx.test(used) && found.indexOf(a[1]) < 0) { found.push(a[1]); used = used.replace(rx, '$1 '); }
    });
    return found.map(function (s) { return KB.brands.filter(function (b) { return b.s === s; })[0]; }).filter(Boolean);
  }
  function cityIn(t) {
    Object.keys(CITY_ALIAS).forEach(function (a) { t = t.replace(new RegExp('\\b' + a + '\\b', 'g'), CITY_ALIAS[a]); });
    for (var i = 0; i < cityIdx.length; i++) if (new RegExp('\\b' + cityIdx[i][0] + '\\b').test(t)) return cityIdx[i][1];
    return null;
  }
  function karatIn(t) { var m = t.match(/\b(24|22|18|14)k\b/); return m ? m[1] + 'K' : null; }
  function weightIn(t) {
    var m = t.match(/(\d+(?:\.\d+)?)\s*(?:g|gm|gms|gram|grams|gr)\b/); if (m) return { g: +m[1], label: m[1] + ' g' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:tola|tolas|tole)\b/); if (m) return { g: +m[1] * 11.664, label: m[1] + ' tola' };
    m = t.match(/\b(?:a|one|1)\s*tola\b/); if (m) return { g: 11.664, label: '1 tola' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:sovereign|sovereigns|pavan|pavun|pawan)\b/); if (m) return { g: +m[1] * 8, label: m[1] + ' sovereign' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b/); if (m) return { g: +m[1] * 1000, label: m[1] + ' kg' };
    return null;
  }
  var CATS = { ring: 'Ring', rings: 'Ring', chain: 'Chain', chains: 'Chain', bangle: 'Bangle', bangles: 'Bangle', kada: 'Bangle', necklace: 'Necklace', haar: 'Necklace', earring: 'Earrings', earrings: 'Earrings', jhumka: 'Earrings', mangalsutra: 'Mangalsutra', pendant: 'Pendant', bracelet: 'Bracelet', coin: 'Coin', coins: 'Coin' };
  function catIn(t) { for (var w in CATS) if (new RegExp('\\b' + w + '\\b').test(t)) return CATS[w]; return null; }
  function has(t, words) { return words.some(function (w) { return new RegExp('\\b' + w + '\\b').test(t); }); }
  var W = {
    rate: ['rate', 'rates', 'price', 'prices', 'bhav', 'bhaav', 'bhaw', 'daam', 'dam', 'kimat', 'keemat', 'kitna', 'kitne', 'cost', 'today', 'aaj', 'current', 'live'],
    cheap: ['cheapest', 'lowest', 'cheap', 'sasta', 'sabse', 'best', 'least', 'minimum', 'lower', 'cheaper', 'where'],
    making: ['making', 'wastage', 'va', 'labour', 'labor', 'mc', 'value addition'],
    offer: ['offer', 'offers', 'discount', 'discounts', 'deal', 'deals', 'sale', 'dhanteras', 'diwali', 'akshaya', 'free', 'cashback', 'promotion'],
    trend: ['trend', 'history', 'yesterday', 'kal', 'week', 'month', 'up', 'down', 'increase', 'decrease', 'change', 'changed', 'chart', 'graph', 'movement', 'rising', 'falling', 'last'],
    compare: ['vs', 'versus', 'compare', 'comparison', 'or', 'better', 'difference', 'between'],
    hello: ['hi', 'hello', 'hey', 'namaste', 'namaskar', 'hii', 'helo', 'good morning', 'good evening'],
    thanks: ['thanks', 'thank', 'thx', 'dhanyavad', 'shukriya', 'great', 'awesome', 'nice', 'ok', 'okay'],
    who: ['who are you', 'what are you', 'your name', 'what can you do', 'help', 'kaun', 'how do you work'],
    silver: ['silver', 'chandi', 'chaandi', 'platinum']
  };

  // ------------------------------------------------------------ answers
  // Each returns {html, chips?, intent}. html is built from KB values only.
  function natBrands() { return KB.brands.filter(function (b) { return b.nat; }); }
  function ranked(list, k) { return list.slice().sort(function (a, b) { return a.r24 - b.r24; }); }
  function rankOf(b, list) { var r = ranked(list); for (var i = 0; i < r.length; i++) if (r[i].s === b.s) return i + 1; return null; }
  function link(u, t) { return '<a href="' + esc(u) + '">' + t + '</a>'; }
  function src() { return '<div class="sn-src">Today’s rates from ' + KB.brands.length + ' jewellers, before GST · ' + esc(KB.date) + '</div>'; }
  function cityBrands(c) {
    var loc = (c && c.loc) || [];
    return KB.brands.filter(function (b) { return b.nat || loc.indexOf(b.s) > -1; });
  }
  function table(rows, k) {
    return '<div class="sn-list">' + rows.map(function (b, i) {
      return '<div class="sn-row"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm">' + (b.u ? link(b.u, esc(b.n)) : esc(b.n)) + (b.nat ? '' : ' <em>local</em>') + '</span><span class="sn-v">' + inr(rate(b, k)) + '<small>/g</small></span></div>';
    }).join('') + '</div>';
  }

  function aMedian(k) {
    var m = KB.med, list = ranked(natBrands());
    var low = list[0];
    return { intent: 'rate', html: '<p>Gold rate in India today, the middle of ' + KB.brands.length + ' jewellers:</p>' +
      '<div class="sn-tiles"><div><b>' + inr(m['24K']) + '</b><span>24K /g</span></div><div class="on"><b>' + inr(m['22K']) + '</b><span>22K /g</span></div><div><b>' + inr(m['18K']) + '</b><span>18K /g</span></div></div>' +
      '<p>Lowest 22K among national jewellers: <b>' + esc(low.n) + '</b> at <b>' + inr(rate(low, '22K')) + '/g</b>.</p>' + src(),
      chips: ['Cheapest 22K today', 'Gold rate in my city', 'Price of 10 g 22K'] };
  }
  function aBrand(b, k) {
    k = k || '22K';
    var list = b.nat ? natBrands() : KB.brands, r = rankOf(b, list), n = list.length;
    var diff = rate(b, k) - KB.med[k];
    var h = '<p><b>' + esc(b.n) + '</b> today:</p><div class="sn-tiles"><div' + (k === '24K' ? ' class="on"' : '') + '><b>' + inr(rate(b, '24K')) + '</b><span>24K /g</span></div><div' + (k === '22K' ? ' class="on"' : '') + '><b>' + inr(rate(b, '22K')) + '</b><span>22K /g</span></div><div' + (k === '18K' ? ' class="on"' : '') + '><b>' + inr(rate(b, '18K')) + '</b><span>18K /g</span></div></div>' +
      '<p>That’s <b>#' + r + ' of ' + n + '</b> ' + (b.nat ? 'national jewellers' : 'jewellers') + ' today — ' + (Math.abs(diff) < 1 ? 'right at' : inr(Math.abs(diff)) + '/g ' + (diff < 0 ? 'below' : 'above')) + ' the market middle for ' + k + '.</p>';
    if (b.mk) h += '<p>Usual making charges: ' + Object.keys(b.mk).map(function (c) { return esc(c.toLowerCase()) + ' ' + pct(b.mk[c]); }).join(', ') + '.</p>';
    if (b.off && b.off.length) h += '<p>Offer on their site: <b>' + esc(b.off[0].h) + '</b>.</p>';
    if (!b.nat && b.st) h += '<p class="sn-dim">Sells in ' + esc(b.st.join(', ')) + '.</p>';
    if (b.u) h += '<p>' + link(b.u, esc(b.n) + '’s 30-day rates →') + '</p>';
    return { intent: 'rate_brand', html: h + src(), chips: [b.n.split(' ')[0] + ' making charges', b.n.split(' ')[0] + ' offers', 'Cheapest 22K today'] };
  }
  function aCity(c, k) {
    k = k || '22K';
    lastCity = c.n; try { localStorage.setItem('sona_city', c.n); } catch (_) {}
    var list = ranked(cityBrands(c)).slice(0, 6), locals = (c.loc || []).length;
    return { intent: 'rate_city', html: '<p>Cheapest ' + k + ' for <b>' + esc(c.n) + '</b> today' + (locals ? ' (national jewellers plus ' + locals + ' that sell in ' + esc(c.st) + ')' : ' (national jewellers)') + ':</p>' + table(list, k) +
      '<p>' + link(c.u, 'Full board for ' + esc(c.n) + ' →') + '</p>' + src(),
      chips: ['Price of 10 g 22K', 'Best offer today', '22K vs 24K?'] };
  }
  function aCheapest(k, c) {
    if (c) return aCity(c, k);
    k = k || '22K';
    var list = ranked(natBrands()).slice(0, 6), hi = ranked(natBrands()).slice(-1)[0];
    var gap = (rate(hi, k) - rate(list[0], k)) * 10;
    return { intent: 'cheapest', html: '<p>Cheapest ' + k + ' among national jewellers today:</p>' + table(list, k) +
      '<p>The gap from cheapest to dearest is <b>' + inr(gap) + '</b> on 10 g — worth checking before you buy.</p>' + src(),
      chips: ['Gold rate in my city', 'Price after offers', 'Making charges compared'] };
  }
  function aCompare(bs, k) {
    k = k || '22K';
    var h = '<p>Side by side today (' + k + '):</p><div class="sn-cmp">' + bs.slice(0, 3).map(function (b) {
      return '<div><div class="sn-cn">' + esc(b.n) + '</div><b>' + inr(rate(b, k)) + '<small>/g</small></b>' +
        '<span>' + inr(rate(b, k) * 10) + ' for 10 g</span>' +
        (b.mk ? '<span>Making ~' + pct(b.mk.Ring || b.mk[Object.keys(b.mk)[0]]) + '</span>' : '<span class="sn-dim">Making: not measured</span>') +
        (b.off && b.off.length ? '<span class="sn-off">' + esc(b.off[0].h) + '</span>' : '') + '</div>';
    }).join('') + '</div>';
    var s = bs.slice(0, 3).sort(function (a, b) { return a.r24 - b.r24; });
    h += '<p><b>' + esc(s[0].n) + '</b> has the lower ' + k + ' rate by <b>' + inr((rate(s[s.length - 1], k) - rate(s[0], k)) * 10) + '</b> on 10 g. The final bill also depends on the making charge for the design you pick.</p>';
    return { intent: 'compare', html: h + src(), chips: ['Price after offers', 'Making charges compared', 'Best offer today'] };
  }
  function aMaking(bs, cat) {
    var withMk = KB.brands.filter(function (b) { return b.mk; });
    if (bs.length) {
      var b = bs[0];
      if (!b.mk) return { intent: 'making', html: '<p>We haven’t measured <b>' + esc(b.n) + '</b>’s making charges yet. We have them for ' + withMk.map(function (x) { return esc(x.n); }).join(', ') + '.</p><p>' + link('/making-charges-comparison', 'Making charges compared →') + '</p>' };
      return { intent: 'making', html: '<p><b>' + esc(b.n) + '</b>’s usual making charges (median of real products, % of gold value):</p><div class="sn-list">' +
        Object.keys(b.mk).map(function (c) { return '<div class="sn-row"><span class="sn-nm">' + esc(c) + '</span><span class="sn-v">' + pct(b.mk[c]) + '</span></div>'; }).join('') + '</div>' +
        '<p class="sn-dim">Varies by design; it’s the most negotiable part of the bill.</p><p>' + link('/making-charges-comparison', 'Compare all jewellers →') + '</p>',
        chips: [b.n.split(' ')[0] + ' offers', 'Price after offers', 'Cheapest 22K today'] };
    }
    var c = cat && cat !== 'Coin' ? cat : 'Ring';
    var rows = withMk.filter(function (b) { return b.mk[c] != null; }).sort(function (a, b) { return a.mk[c] - b.mk[c]; });
    if (!rows.length) { c = 'Ring'; rows = withMk.filter(function (b) { return b.mk.Ring != null; }).sort(function (a, b) { return a.mk.Ring - b.mk.Ring; }); }
    return { intent: 'making', html: '<p>Lowest making charges on a <b>' + esc(c.toLowerCase()) + '</b> (median of real products):</p><div class="sn-list">' +
      rows.slice(0, 6).map(function (b, i) { return '<div class="sn-row"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm">' + esc(b.n) + '</span><span class="sn-v">' + pct(b.mk[c]) + '</span></div>'; }).join('') + '</div>' +
      '<p>' + link('/making-charges-comparison', 'Every jeweller and category →') + '</p>',
      chips: ['Price after offers', 'Best offer today', 'What are making charges?'] };
  }
  function aOffers(bs) {
    if (bs.length) {
      var b = bs[0];
      if (!b.off || !b.off.length) return { intent: 'offers', html: '<p>No offer is published as text on <b>' + esc(b.n) + '</b>’s website today. ' + link('/gold-offers-today', 'See who has offers →') + '</p>' };
      return { intent: 'offers', html: '<p>Offers on <b>' + esc(b.n) + '</b>’s website today:</p>' + b.off.map(function (o) {
        return '<div class="sn-card"><b>' + esc(o.h) + '</b><q>' + esc(o.t) + '</q><p>' + o.m + '</p><a href="' + esc(o.u) + '" target="_blank" rel="nofollow noopener">Their page ↗</a></div>';
      }).join('') + '<p>' + link('/gold-offers-today', 'All jewellers’ offers compared →') + '</p>', chips: ['Price after offers', 'Cheapest 22K today'] };
    }
    var rows = (KB.ring || []).slice(0, 5);
    var h = '<p>The real test of an offer is the final price. A 10 g 22K ring today, after offers, with GST:</p>' +
      (rows.length ? '<div class="sn-list">' + rows.map(function (r, i) { return '<div class="sn-row"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm">' + esc(r.n) + (r.p ? ' <em>' + r.p + '% off making</em>' : '') + '</span><span class="sn-v">' + inr(r.a) + '</span></div>'; }).join('') + '</div>' : '');
    var withOff = KB.brands.filter(function (b) { return b.off && b.off.length; });
    h += '<p>' + withOff.length + ' jewellers have offers on their sites today, e.g. ' + withOff.slice(0, 4).map(function (b) { return esc(b.n) + ': ' + esc(b.off[0].h); }).join('; ') + '.</p>' +
      '<p>' + link('/gold-offers-today', 'Every offer, and what it really means →') + '</p>';
    return { intent: 'offers', html: h, chips: ['Is 20% off making a good deal?', 'Making charges compared', 'Cheapest 22K today'] };
  }
  function aPrice(w, k, bs, cat) {
    k = k || (cat === 'Coin' ? '24K' : '22K');
    var b = bs[0] || ranked(natBrands())[0], who = bs[0] ? esc(b.n) : 'the cheapest national jeweller (' + esc(b.n) + ')';
    var gold = rate(b, k) * w.g;
    var mkp = b.mk ? (cat && b.mk[cat] != null ? b.mk[cat] : (b.mk.Ring != null ? b.mk.Ring : null)) : null;
    if (cat === 'Coin' || (k === '24K' && !cat)) mkp = null;   // 24K: coins and bars
    var mk = mkp != null ? gold * mkp / 100 : 0, gst = (gold + mk) * 0.03;
    var h = '<p>' + esc(w.label) + ' of ' + k + ' at ' + who + ' today:</p><div class="sn-bill">' +
      '<div><span>Gold (' + (Math.round(w.g * 1000) / 1000) + ' g × ' + inr(rate(b, k)) + ')</span><b>' + inr(gold) + '</b></div>' +
      (mkp != null ? '<div><span>Making (~' + pct(mkp) + (cat && b.mk[cat] != null ? ', ' + esc(cat.toLowerCase()) : ', typical') + ')</span><b>' + inr(mk) + '</b></div>' : '') +
      '<div><span>GST 3%</span><b>' + inr(gst) + '</b></div><div class="sn-tot"><span>Total</span><b>' + inr(gold + mk + gst) + '</b></div></div>' +
      (mkp == null && cat !== 'Coin' && k !== '24K' ? '<p class="sn-dim">Making charges not included — add the jeweller’s charge for your design (often 8–25%).</p>' : '') + src();
    return { intent: 'price', html: h, chips: ['Same at another jeweller', 'Price after offers', 'Cheapest 22K today'] };
  }
  function aTrend(k) {
    k = k || '22K';
    var h = KB.hist || [], f = K[k];
    if (h.length < 2) return { intent: 'trend', html: '<p>Not enough history yet. ' + link('/gold-rate-history', 'Gold rate history →') + '</p>' };
    var last = h[h.length - 1][1] * f;
    function back(n) { var i = Math.max(0, h.length - 1 - n); return h[i][1] * f; }
    function chg(v) { var d = last - v, p = d / v * 100; return '<b class="' + (d >= 0 ? 'up' : 'dn') + '">' + (d >= 0 ? '▲ ' : '▼ ') + inr(Math.abs(d)) + ' (' + pct(Math.abs(p)) + ')</b>'; }
    var pts = h.slice(-30).map(function (x) { return x[1]; }), mn = Math.min.apply(null, pts), mx = Math.max.apply(null, pts);
    var sv = '<svg class="sn-spark" viewBox="0 0 240 48" preserveAspectRatio="none"><polyline fill="none" stroke="#e7bf5a" stroke-width="2" stroke-linejoin="round" points="' +
      pts.map(function (v, i) { return (i * 240 / Math.max(1, pts.length - 1)).toFixed(1) + ',' + (44 - (mx === mn ? 20 : (v - mn) / (mx - mn) * 40)).toFixed(1); }).join(' ') + '"/></svg>';
    return { intent: 'trend', html: '<p>' + k + ' market middle: <b>' + inr(last) + '/g</b> today.</p>' + sv +
      '<div class="sn-list"><div class="sn-row"><span class="sn-nm">vs previous day</span><span class="sn-v">' + chg(back(1)) + '</span></div>' +
      '<div class="sn-row"><span class="sn-nm">vs 7 days ago</span><span class="sn-v">' + chg(back(7)) + '</span></div>' +
      '<div class="sn-row"><span class="sn-nm">vs 30 days ago</span><span class="sn-v">' + chg(back(30)) + '</span></div></div>' +
      '<p class="sn-dim">Past moves, not a forecast — nobody can reliably predict tomorrow’s price. ' + link('/gold-rate-history', 'Full history →') + '</p>',
      chips: ['Set a price alert', 'Cheapest 22K today', 'Is now a good time to buy?'] };
  }
  function aAlerts() {
    return { intent: 'alerts', html: '<p>Get the cheapest jeweller and today’s rate every morning, free — and an email the day 22K drops to your price.</p><button class="sn-cta" data-sn="subscribe">Get free daily alerts</button>' };
  }
  function words(t) { return t.split(/\s+/).filter(function (w) { return w.length > 2 && !/^(the|and|for|what|how|are|you|your|with|does|this|that|from|have|can|why|which|about|gold|is|of)$/.test(w); }); }
  function scoreDoc(t, q, keys) {
    var ws = words(t), qs = norm(q), s = 0;
    ws.forEach(function (w) { if (qs.indexOf(' ' + w) > -1) s += 1; if ((keys || []).indexOf(w) > -1) s += 1.5; });
    return s / Math.max(3, Math.sqrt(words(qs).length + 1) * 2);
  }
  function aSearch(t) {
    var best = null, bs = 0;
    (KB.learned || []).forEach(function (d) { var s = scoreDoc(t, d.q, []) * 1.2; if (s > bs) { bs = s; best = d; } });
    KB.faq.forEach(function (d) { var s = scoreDoc(t, d.q, d.k); if (s > bs) { bs = s; best = d; } });
    if (best && bs >= 0.6) return { intent: 'faq', score: bs, html: '<p>' + esc(best.a) + '</p>' + (best.u ? '<p>' + link(best.u, 'Read more →') + '</p>' : ''), chips: ['Cheapest 22K today', 'Best offer today'] };
    var g = null, gs = 0;
    KB.guides.forEach(function (d) { var s = scoreDoc(t, d.t + ' ' + d.d, []); if (s > gs) { gs = s; g = d; } });
    if (g && gs >= 0.6) return { intent: 'guide', score: gs, html: '<p>This guide covers it: <b>' + esc(g.t) + '</b> — ' + esc(g.d) + '</p><p>' + link(g.u, 'Read the guide →') + '</p>' };
    return null;
  }

  function answer(q) {
    var t = norm(q), k = karatIn(t), bs = brandsIn(t), c = cityIn(t), w = weightIn(t), cat = catIn(t);
    if (/\b(my city|near me|nearby|mere sheher|mere shahar|my area)\b/.test(t) && !c) {
      if (lastCity) c = KB.cities.filter(function (x) { return x.n === lastCity; })[0];
      if (!c) return { intent: 'ask_city', html: '<p>Which city are you in?</p>', chips: ['Mumbai', 'Delhi', 'Bengaluru', 'Chennai', 'Hyderabad', 'Kolkata', 'Pune', 'Lucknow'] };
    }
    if (has(t, W.silver) && !has(t, ['gold', 'sona'])) return { intent: 'silver', html: '<p>I cover gold for now — jewellers’ 22K, 24K and 18K rates. Silver is on its way.</p>', chips: ['Gold rate today', 'Cheapest 22K today'] };
    if (has(t, ['alert', 'alerts', 'notify', 'subscribe', 'email me', 'whatsapp', 'set a price'])) return aAlerts();
    if (bs.length >= 2) return aCompare(bs, k);
    var strong = aSearch(t);                 // a question the FAQ answers word for word
    if (strong && strong.score >= 1.0 && !w && !bs.length && !c) return strong;
    if (has(t, W.offer) || /\bafter offers?\b/.test(t)) return aOffers(bs);
    if (has(t, W.making) && !w) return aMaking(bs, cat);
    if (w) return aPrice(w, k, bs, cat);
    if (has(t, W.trend) && !bs.length) return aTrend(k);
    var search = aSearch(t);
    if (search && search.score > 0.9) return search;
    if (has(t, W.cheap)) return aCheapest(k, c);
    if (bs.length) return aBrand(bs[0], k);
    if (c) return aCity(c, k);
    if (search) return search;
    if (has(t, W.rate) || k || /\b(gold|sona)\b/.test(t)) return aMedian(k);
    if (has(t, W.hello)) return { intent: 'hello', html: '<p>Namaste! 🙏 I’m Sona. Ask me anything about buying gold — today’s rates at ' + KB.brands.length + ' jewellers, your city, making charges, offers or a price for any weight.</p>', chips: SUGGEST };
    if (has(t, W.thanks)) return { intent: 'thanks', html: '<p>Happy to help! Anything else?</p>', chips: ['Cheapest 22K today', 'Best offer today'] };
    if (W.who.some(function (x) { return t.indexOf(x) > -1; })) return { intent: 'about', html: '<p>I’m Sona, MyGoldRates’ assistant. I answer from today’s real data — ' + KB.brands.length + ' jewellers’ published rates, making charges measured from real products, and the offers on their websites — so I never guess a number.</p>', chips: SUGGEST };
    return null;
  }

  // --------------------------------------------------------------- UI
  var SUGGEST = ['Cheapest 22K today', 'Gold rate in my city', 'Tanishq vs Kalyan', 'Best offer today', 'Price of 10 g 22K chain', '22K vs 24K?'];
  var CSS = '' +
    '.sn-fab{position:fixed;right:16px;bottom:calc(18px + env(safe-area-inset-bottom));z-index:8500;display:flex;align-items:center;gap:9px;height:52px;padding:0 18px 0 7px;border:0;border-radius:999px;cursor:pointer;color:#1a1405;font:700 14.5px/1 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:linear-gradient(135deg,#ffe9a8,#e7bf5a 45%,#b98a24);box-shadow:0 10px 30px rgba(185,138,36,.45),0 0 0 1px rgba(255,255,255,.25) inset;transition:transform .2s}' +
    '.sn-fab:hover{transform:translateY(-2px)}.sn-fab .sn-orb{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#1a1405;color:#f0d080;font-size:18px}' +
    '.sn-fab .sn-ping{position:absolute;top:-3px;right:-3px;width:12px;height:12px;border-radius:50%;background:#2fd18b;box-shadow:0 0 0 0 rgba(47,209,139,.7);animation:snPing 2s infinite}' +
    '@keyframes snPing{0%{box-shadow:0 0 0 0 rgba(47,209,139,.7)}70%{box-shadow:0 0 0 10px rgba(47,209,139,0)}100%{box-shadow:0 0 0 0 rgba(47,209,139,0)}}' +
    'html.sona-bnav .sn-fab{bottom:calc(78px + env(safe-area-inset-bottom))}' +
    'html.sona-open .sn-fab{display:none}@media(max-width:560px){html.sona-open,html.sona-open body{overflow:hidden}}' +
    '.sn-ad{position:relative;overflow:hidden;border-radius:18px;padding:18px;margin:14px 12px;color:#f3eadb;background:radial-gradient(120% 90% at 100% 0%,rgba(231,191,90,.28),transparent 60%),linear-gradient(160deg,#1c160c,#0f0c08);border:1px solid rgba(240,208,128,.3);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}' +
    '.sn-ad .sn-adk{display:inline-flex;align-items:center;gap:6px;font-size:10.5px;font-weight:800;letter-spacing:.12em;color:#1a1405;background:linear-gradient(135deg,#f6d77d,#d4a63c);border-radius:999px;padding:3px 9px}' +
    '.sn-ad h3{font:800 21px/1.25 Georgia,serif;margin:10px 0 4px;padding-right:58px;color:#fff3d6}.sn-ad p{margin:0 0 12px;font-size:13.5px;color:#cfc4ad;line-height:1.5}' +
    '.sn-ad .sn-adq{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:12px}.sn-ad .sn-adq button{border:1px solid rgba(240,208,128,.35);background:rgba(231,191,90,.1);color:#f0d080;border-radius:999px;padding:7px 12px;font-size:12.5px;font-weight:600;cursor:pointer}' +
    '.sn-ad .sn-adgo{border:0;border-radius:12px;padding:12px 18px;font-weight:800;font-size:14px;cursor:pointer;color:#1a1405;background:linear-gradient(135deg,#f6d77d,#d4a63c 55%,#b98a24);box-shadow:0 8px 22px rgba(212,166,60,.3)}' +
    '.sn-ad .sn-adav{position:absolute;right:16px;top:16px;width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;font:800 21px Georgia,serif;color:#1a1405;background:radial-gradient(circle at 30% 30%,#fff3c4,#e7bf5a 45%,#9c7316);box-shadow:0 0 0 6px rgba(231,191,90,.12)}' +
    '@media(max-width:520px){.sn-fab{height:50px;padding:0 6px}.sn-fab .sn-lbl{display:none}}' +
    '.sn-panel{position:fixed;right:18px;bottom:18px;z-index:9500;width:410px;height:min(680px,calc(100vh - 36px));display:none;flex-direction:column;border-radius:24px;overflow:hidden;color:#f3eadb;font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:radial-gradient(130% 60% at 100% 0%,rgba(231,191,90,.16),transparent 60%),#120f0a;border:1px solid rgba(240,208,128,.22);box-shadow:0 30px 80px rgba(0,0,0,.6)}' +
    'html.sona-open .sn-panel{display:flex;animation:snIn .28s cubic-bezier(.2,.8,.3,1)}@keyframes snIn{from{opacity:0;transform:translateY(18px) scale(.98)}to{opacity:1;transform:none}}' +
    '@media(max-width:560px){.sn-panel{right:0;bottom:0;width:100%;height:100%;height:100dvh;border-radius:0;border:0}}' +
    '.sn-hd{display:flex;align-items:center;gap:11px;padding:14px 14px 12px 16px;border-bottom:1px solid rgba(240,208,128,.12)}' +
    '.sn-av{position:relative;width:42px;height:42px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font:800 19px Georgia,serif;color:#1a1405;background:radial-gradient(circle at 30% 30%,#fff3c4,#e7bf5a 45%,#9c7316)}' +
    '.sn-av:after{content:"";position:absolute;right:0;bottom:1px;width:10px;height:10px;border-radius:50%;background:#2fd18b;border:2px solid #120f0a}' +
    '.sn-hd b{display:block;font-size:15.5px}.sn-hd span{font-size:11.5px;color:#a99f8b}.sn-x{margin-left:auto;width:34px;height:34px;border-radius:50%;border:0;background:rgba(255,255,255,.07);color:#f3eadb;font-size:18px;cursor:pointer}' +
    '.sn-body{flex:1;overflow-y:auto;padding:16px 14px 8px;scroll-behavior:smooth}' +
    '.sn-m{display:flex;margin:0 0 12px}.sn-m.me{justify-content:flex-end}' +
    '.sn-b{max-width:88%;padding:10px 13px;border-radius:18px 18px 18px 6px;background:rgba(255,255,255,.06);border:1px solid rgba(240,208,128,.1)}' +
    '.sn-m.me .sn-b{border-radius:18px 18px 6px 18px;background:linear-gradient(135deg,#f6d77d,#d4a63c);color:#1a1405;border:0;font-weight:600}' +
    '.sn-b p{margin:0 0 8px}.sn-b p:last-child{margin-bottom:0}.sn-b a{color:#f0d080;font-weight:600;text-decoration:none}.sn-b em{font-style:normal;font-size:10.5px;color:#a99f8b;border:1px solid rgba(240,208,128,.25);border-radius:6px;padding:0 5px}' +
    '.sn-tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:4px 0 10px}.sn-tiles div{background:rgba(0,0,0,.25);border:1px solid rgba(240,208,128,.12);border-radius:12px;padding:8px 6px;text-align:center}' +
    '.sn-tiles div.on{border-color:#e7bf5a;background:rgba(231,191,90,.12)}.sn-tiles b{display:block;font-size:14.5px}.sn-tiles span{font-size:10.5px;color:#a99f8b}' +
    '.sn-list{background:rgba(0,0,0,.22);border:1px solid rgba(240,208,128,.1);border-radius:12px;margin:4px 0 10px;overflow:hidden}' +
    '.sn-row{display:flex;align-items:center;gap:8px;padding:7px 10px;border-bottom:1px solid rgba(240,208,128,.07);font-size:13px}.sn-row:last-child{border-bottom:0}' +
    '.sn-rk{width:20px;height:20px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;background:rgba(231,191,90,.15);color:#f0d080}.sn-row:first-child .sn-rk{background:#e7bf5a;color:#1a1405}' +
    '.sn-nm{flex:1;min-width:0}.sn-v{font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}.sn-v small{font-weight:400;color:#a99f8b}' +
    '.sn-v .up{color:#5ad59a}.sn-v .dn{color:#f08f8f}.sn-dim{color:#a99f8b;font-size:12.5px}.sn-src{font-size:10.5px;color:#7f7663;margin-top:6px}' +
    '.sn-cmp{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:6px;margin:4px 0 10px}.sn-cmp>div{background:rgba(0,0,0,.25);border:1px solid rgba(240,208,128,.12);border-radius:12px;padding:9px}' +
    '.sn-cmp .sn-cn{font-size:12px;color:#a99f8b;margin-bottom:2px}.sn-cmp b{display:block;font-size:16px}.sn-cmp span{display:block;font-size:11.5px;color:#cfc4ad;margin-top:2px}.sn-cmp .sn-off{color:#5ad59a}' +
    '.sn-bill{background:rgba(0,0,0,.22);border:1px solid rgba(240,208,128,.12);border-radius:12px;padding:6px 10px;margin:4px 0 10px}.sn-bill div{display:flex;justify-content:space-between;gap:10px;padding:5px 0;font-size:13px}.sn-bill span{color:#cfc4ad}.sn-bill .sn-tot{border-top:1px dashed rgba(240,208,128,.3);margin-top:3px;padding-top:8px;font-size:15px}.sn-bill .sn-tot b{color:#f0d080}' +
    '.sn-card{background:rgba(0,0,0,.22);border:1px solid rgba(240,208,128,.12);border-radius:12px;padding:9px 10px;margin:0 0 8px}.sn-card q{display:block;font-style:italic;color:#cfc4ad;font-size:12.5px;margin:3px 0}.sn-card p{font-size:12.5px;color:#d9cfba}' +
    '.sn-spark{width:100%;height:48px;margin:2px 0 8px}' +
    '.sn-cta{width:100%;border:0;border-radius:12px;padding:11px;cursor:pointer;font-weight:800;color:#1a1405;background:linear-gradient(135deg,#f6d77d,#d4a63c 55%,#b98a24)}' +
    '.sn-fb{display:flex;gap:6px;margin-top:6px}.sn-fb button{border:1px solid rgba(240,208,128,.2);background:none;color:#a99f8b;border-radius:999px;padding:2px 9px;font-size:12px;cursor:pointer}.sn-fb button.on{background:rgba(231,191,90,.2);color:#f0d080}' +
    '.sn-chips{display:flex;gap:7px;overflow-x:auto;padding:4px 14px 10px;scrollbar-width:none}.sn-chips::-webkit-scrollbar{display:none}' +
    '.sn-chip{flex:none;border:1px solid rgba(240,208,128,.3);background:rgba(231,191,90,.08);color:#f0d080;border-radius:999px;padding:7px 12px;font-size:12.5px;font-weight:600;cursor:pointer;white-space:nowrap}.sn-chip:hover{background:rgba(231,191,90,.18)}' +
    '.sn-in{display:flex;gap:8px;padding:10px 12px calc(12px + env(safe-area-inset-bottom));border-top:1px solid rgba(240,208,128,.12)}' +
    '.sn-in input{flex:1;min-width:0;border:1px solid rgba(240,208,128,.22);background:rgba(255,255,255,.05);color:#f3eadb;border-radius:999px;padding:12px 16px;font-size:15px;outline:none}.sn-in input:focus{border-color:#e7bf5a}' +
    '.sn-send{width:46px;height:46px;flex:none;border:0;border-radius:50%;cursor:pointer;color:#1a1405;font-size:18px;background:linear-gradient(135deg,#f6d77d,#d4a63c)}' +
    '.sn-typing span{display:inline-block;width:7px;height:7px;margin:0 2px;border-radius:50%;background:#e7bf5a;animation:snDot 1s infinite}.sn-typing span:nth-child(2){animation-delay:.15s}.sn-typing span:nth-child(3){animation-delay:.3s}' +
    '@keyframes snDot{0%,80%,100%{opacity:.25;transform:translateY(0)}40%{opacity:1;transform:translateY(-3px)}}' +
    '.sn-foot{text-align:center;font-size:10px;color:#6f6754;padding:0 0 8px}' +
    '.sn-ban{position:relative;z-index:50;display:flex;align-items:center;justify-content:center;gap:10px;padding:9px 40px 9px 14px;font:600 13px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#1a1405;background:linear-gradient(90deg,#b98a24,#f6d77d 50%,#b98a24);background-size:200% 100%;animation:snShine 6s linear infinite;cursor:pointer;text-align:center}' +
    '@keyframes snShine{to{background-position:-200% 0}}.sn-ban .nw{flex:none;background:#1a1405;color:#f0d080;border-radius:999px;padding:2px 8px;font-size:10.5px;letter-spacing:.08em}.sn-ban u{text-underline-offset:2px}' +
    '.sn-ban .bx{position:absolute;right:8px;top:50%;transform:translateY(-50%);width:26px;height:26px;border:0;border-radius:50%;background:rgba(26,20,5,.12);color:#1a1405;cursor:pointer;font-size:14px}';

  var panel, body, chips, input;
  function ui() {
    if (panel) return;
    panel = document.createElement('div'); panel.className = 'sn-panel'; panel.id = 'sonaPanel';
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Sona, the jewellery assistant');
    panel.innerHTML = '<div class="sn-hd"><div class="sn-av">S</div><div><b>Sona</b><span>Jewellery assistant · answers from today’s real rates</span></div><button class="sn-x" id="sonaClose" aria-label="Close">×</button></div>' +
      '<div class="sn-body" aria-live="polite"></div><div class="sn-chips"></div>' +
      '<form class="sn-in"><input id="sonaInput" type="text" autocomplete="off" maxlength="200" placeholder="Ask about rates, jewellers, offers…" aria-label="Your question"><button class="sn-send" id="sonaSend" aria-label="Send">➤</button></form>' +
      '<div class="sn-foot">Free · answers from published data, not advice</div>';
    document.body.appendChild(panel);
    body = $('.sn-body', panel); chips = $('.sn-chips', panel); input = $('#sonaInput', panel);
    $('#sonaClose', panel).onclick = close;
    $('form', panel).onsubmit = function (e) { e.preventDefault(); ask(input.value); };
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && opened) close(); });
    panel.addEventListener('click', function (e) {
      var c = e.target.closest('.sn-chip'); if (c) { ask(c.textContent); return; }
      var s = e.target.closest('[data-sn="subscribe"]');
      if (s) { close(); if (window.GR_OPEN_SUBPOP) window.GR_OPEN_SUBPOP(); else location.href = '/inquiry'; track('subscribe'); return; }
      var f = e.target.closest('.sn-fb button');
      if (f && !f.parentNode.getAttribute('data-done')) {
        f.classList.add('on'); f.parentNode.setAttribute('data-done', '1');
        var id = f.parentNode.getAttribute('data-id');
        if (id) rpc('bot_feedback', { p_id: +id, p_sid: window.GR_SID || '', p_helpful: f.getAttribute('data-v') === '1' });
      }
    });
  }
  function setChips(list) { chips.innerHTML = (list || []).map(function (c) { return '<button class="sn-chip" type="button">' + esc(c) + '</button>'; }).join(''); }
  function bubble(html, me) {
    var m = document.createElement('div'); m.className = 'sn-m' + (me ? ' me' : '');
    m.innerHTML = '<div class="sn-b">' + html + '</div>'; body.appendChild(m);
    body.scrollTop = body.scrollHeight; return m;
  }
  function ask(q) {
    q = String(q || '').trim(); if (!q) return;
    input.value = ''; bubble(esc(q), true); setChips([]);
    var typing = bubble('<span class="sn-typing"><span></span><span></span><span></span></span>');
    loadKB().then(function () {
      var a = null;
      try { a = answer(q); } catch (e) { a = null; }
      var ok = !!a;
      if (!a) a = { intent: 'unknown', html: '<p>I’m still learning that one — I’ve noted your question so we can add a proper answer soon. Meanwhile, I’m good at these:</p>', chips: SUGGEST };
      setTimeout(function () {
        typing.remove();
        var m = bubble(a.html + '<div class="sn-fb"><button type="button" data-v="1" aria-label="Helpful">👍</button><button type="button" data-v="0" aria-label="Not helpful">👎</button></div>');
        setChips(a.chips || SUGGEST);
        rpc('log_bot_question', { p_q: redact(q), p_intent: a.intent, p_answered: ok, p_page: location.pathname, p_sid: window.GR_SID || '' })
          .then(function (id) { if (id) $('.sn-fb', m).setAttribute('data-id', id); });
        track(ok ? 'answered' : 'unanswered');
      }, 350 + Math.min(600, a.html.length / 6));
    }).catch(function () { typing.remove(); bubble('<p>I couldn’t load today’s data. Please check your connection and try again.</p>'); });
  }
  function open(q) {
    ui();
    if (!opened) {
      opened = true; document.documentElement.classList.add('sona-open');
      if (!body.childNodes.length) {
        bubble('<p>Namaste! 🙏 I’m <b>Sona</b>, your jewellery assistant.</p><p>Ask me anything about buying gold — today’s rate at any jeweller, the cheapest in your city, making charges, offers, or the price of any weight. I answer from today’s real data.</p>');
        setChips(SUGGEST);
      }
      track('open'); loadKB();
      if (window.innerWidth > 560) setTimeout(function () { try { input.focus(); } catch (_) {} }, 200);
    }
    if (q) ask(q);
  }
  function close() { opened = false; document.documentElement.classList.remove('sona-open'); }
  window.GR_ASK = open;

  // ---------------------------------------------------- launcher & banner
  function mount() {
    if (document.querySelector('.bnav')) document.documentElement.classList.add('sona-bnav');
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    var fab = document.createElement('button');
    fab.className = 'sn-fab'; fab.id = 'sonaFab'; fab.type = 'button'; fab.setAttribute('aria-label', 'Ask Sona, the jewellery assistant');
    fab.innerHTML = '<span class="sn-orb">✨</span><span class="sn-lbl">Ask Sona</span><span class="sn-ping"></span>';
    fab.onclick = function () { open(); };
    document.body.appendChild(fab);
    var seen = null; try { seen = localStorage.getItem('sona_ban'); } catch (_) {}
    if (!seen) {
      var b = document.createElement('div'); b.className = 'sn-ban'; b.id = 'sonaBanner';
      b.innerHTML = '<span class="nw">NEW</span><span>Meet <b>Sona</b>, our new gold-rate assistant — ask about any jeweller, city, making charge or offer. <u>Try it</u></span><button class="bx" type="button" aria-label="Dismiss">×</button>';
      b.onclick = function (e) {
        if (e.target.closest('.bx')) { b.remove(); try { localStorage.setItem('sona_ban', '1'); } catch (_) {} return; }
        open(); track('banner');
      };
      document.body.insertBefore(b, document.body.firstChild);
    }
    if (/[?&]ask=1\b/.test(location.search) || location.hash === '#ask') setTimeout(function () { open(); }, 400);
    // Feature cards on the pages: <button data-ask="question"> opens Sona with it.
    document.addEventListener('click', function (e) {
      var el = e.target.closest && e.target.closest('[data-ask]');
      if (!el) return;
      e.preventDefault(); track('card'); open(el.getAttribute('data-ask') || '');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
