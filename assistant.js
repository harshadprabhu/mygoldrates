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
 *
 * Voice and languages, also free: the browser's own speech recognition
 * (tap the mic) and its own voices (read aloud), in English and nine Indian
 * languages. A question in an Indian script is turned into the words this
 * engine knows by sona_lang.js; replies come from sona_i18n.js. The build
 * puts all three in one file, /assistant.js.
 */
(function () {
  if (window.__sona) return; window.__sona = 1;
  var TEST = !!window.__SONA_TEST;
  if (!TEST && /^\/(analytics|unsubscribe|404)(\.html)?\/?$/.test(location.pathname)) return;

  var SB = (window.GR_SB_URL || '').replace(/\/$/, ''), KEY = window.GR_SB_KEY || '';
  var KB = null, kbWait = null, opened = false, home = null, wantHome = false, wantOffer = false;
  // "My city" is the visitor's own city: one they said they live in, picked
  // when Sona asked, or the nearest to the phone's location (worked out on
  // the device, only when they tap for it). Never just the last city asked
  // about - that was 'sona_city', dropped here.
  try { home = localStorage.getItem('sona_home'); localStorage.removeItem('sona_city'); } catch (_) {}
  var LG = window.SONA_LANG, STR = window.SONA_STR || {};
  // Language is automatic. Each reply is in the language of its question
  // (the script it is written in). The browser's free speech recogniser
  // must be told which language to listen for, so the mic listens in the
  // last Indian language Sona read or heard from this visitor - at first the
  // phone's own language, else Hindi, whose recogniser also takes English.
  // A visitor can pin one language instead (PICK).
  var PICK = '', HEARD = '', PHONE = '';
  try { PICK = localStorage.getItem('sona_pick') || ''; HEARD = localStorage.getItem('sona_heard') || ''; } catch (_) {}
  if (!STR[PICK]) PICK = '';
  if (!STR[HEARD]) HEARD = '';
  (navigator.languages || [navigator.language || '']).some(function (l) {
    var c = String(l).slice(0, 2).toLowerCase();
    if (STR[c] && c !== 'en') { PHONE = c; return true; }
    return false;
  });
  function uiLang() { return PICK || HEARD || PHONE || 'en'; }
  function micLang() { return PICK || HEARD || PHONE || 'hi'; }
  var LANG = uiLang(), RL = LANG;      // the language of the labels; of this reply
  // Text in the reply language, falling back to English: t('city_h', {c: 'Pune'}).
  function fill(s, v) { return String(s).replace(/\{(\w+)\}/g, function (_, n) { return v && v[n] != null ? v[n] : ''; }); }
  function t(k, v) { return fill((STR[RL] && STR[RL][k]) || (STR.en && STR.en[k]) || k, v); }
  function en(k, v) { return fill((STR.en && STR.en[k]) || k, v); }
  // Urdu reads right to left.
  function rtl(c) { return (LG ? LG.LANGS : []).some(function (x) { return x.c === c && x.rtl; }); }
  function langName(c) { var l = (LG ? LG.LANGS : []).filter(function (x) { return x.c === c; })[0]; return l ? l.n : c; }

  // ------------------------------------------------------------ helpers
  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  // A price stays "₹12,958" inside right-to-left (Urdu) text too.
  function inr(n) { return '<bdi dir="ltr">₹' + Math.round(n).toLocaleString('en-IN') + '</bdi>'; }
  function pct(n) { return (Math.round(n * 10) / 10).toLocaleString('en-IN') + '%'; }
  var K = { '24K': 1, '22K': 22 / 24, '18K': 18 / 24, '14K': 14 / 24 };
  function rate(b, k) { return b.r24 * K[k]; }
  // For speaking: "12,879 rupees", "22 carat".
  function sInr(n) { return Math.round(n).toLocaleString('en-IN') + ' ' + t('rupees'); }
  function sK(k) { return String(k).replace('K', '') + ' ' + t('carat'); }
  function catName(c) { return (STR[RL] && STR[RL]['c_' + c]) || (STR.en && STR.en['c_' + c]) || String(c).toLowerCase(); }
  function wLabel(w) { return t('u_' + w.u, { n: w.n }); }
  function track(what) { try { if (window.GR_TRACK) window.GR_TRACK('click_events', { page: location.pathname, target: 'sona:' + what, session_id: window.GR_SID || '' }); } catch (_) {} }
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
  // Spoken names that are not how the site spells them.
  var SPOKEN = { dilli: 'delhi', bambai: 'mumbai', bambay: 'mumbai', kalkatta: 'kolkata', madras: 'chennai', banglore: 'bengaluru',
    amdavad: 'ahmedabad', vadodra: 'vadodara', koyambuthur: 'coimbatore', kovai: 'coimbatore', trichy: 'tiruchirappalli',
    tiruchi: 'tiruchirappalli', thiruvananthapuram: 'thiruvananthapuram', kashi: 'varanasi', prayagraj: 'allahabad',
    gurgaon: 'gurugram', bhagyanagar: 'hyderabad', belgaum: 'belagavi', vishakhapatnam: 'visakhapatnam', kozhikkode: 'kozhikode' };
  var aliases = [], cityIdx = [], VOCAB = [];
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
    // Names to match by sound in a question asked in an Indian script.
    if (LG) {
      var words = [];
      aliases.forEach(function (a) { words = words.concat(a[0].split(/[\s&]+/)); });
      d.cities.forEach(function (c) { words = words.concat(c.n.toLowerCase().split(/\s+/)); });
      VOCAB = LG.vocabOf(words.concat(Object.keys(CITY_ALIAS)));
      Object.keys(SPOKEN).forEach(function (s) { VOCAB.push([LG.key(s), SPOKEN[s]]); });
    }
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
    var m = t.match(/(\d+(?:\.\d+)?)\s*(?:g|gm|gms|gram|grams|gr)\b/); if (m) return { g: +m[1], n: m[1], u: 'g' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:tola|tolas|tole)\b/); if (m) return { g: +m[1] * 11.664, n: m[1], u: 'tola' };
    m = t.match(/\b(?:a|one|1)\s*tola\b/); if (m) return { g: 11.664, n: '1', u: 'tola' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:sovereign|sovereigns|pavan|pavun|pawan)\b/); if (m) return { g: +m[1] * 8, n: m[1], u: 'sov' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b/); if (m) return { g: +m[1] * 1000, n: m[1], u: 'kg' };
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
  // Each returns {html, say?, chips?, intent}. html is built from KB values
  // only; say is the same answer in a sentence or two, for reading aloud.
  function natBrands() { return KB.brands.filter(function (b) { return b.nat; }); }
  function ranked(list, k) { return list.slice().sort(function (a, b) { return a.r24 - b.r24; }); }
  function rankOf(b, list) { var r = ranked(list); for (var i = 0; i < r.length; i++) if (r[i].s === b.s) return i + 1; return null; }
  function link(u, tx) { return '<a href="' + esc(u) + '">' + tx + '</a>'; }
  function src() { return '<div class="sn-src">' + t('src', { n: KB.brands.length, d: esc(KB.date) }) + '</div>'; }
  // A suggestion chip: shown in the reply language, asked in English.
  function chip(k, v) { return { l: t('ch_' + k, v), q: en('ch_' + k, v) }; }
  function chips(keys) { return keys.map(function (k) { return chip(k); }); }
  function suggest() { return chips(SUGGEST); }
  function cityBrands(c) {
    var loc = (c && c.loc) || [];
    return KB.brands.filter(function (b) { return b.nat || loc.indexOf(b.s) > -1; });
  }
  function table(rows, k) {
    return '<div class="sn-list">' + rows.map(function (b, i) {
      return '<div class="sn-row"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm">' + (b.u ? link(b.u, esc(b.n)) : esc(b.n)) + (b.nat ? '' : ' <em>local</em>') + '</span><span class="sn-v">' + inr(rate(b, k)) + '<small>/g</small></span></div>';
    }).join('') + '</div>';
  }
  function tiles(m, k) {
    return '<div class="sn-tiles">' + ['24K', '22K', '18K'].map(function (x) {
      return '<div' + (x === k ? ' class="on"' : '') + '><b>' + inr(m[x]) + '</b><span>' + x + ' /g</span></div>';
    }).join('') + '</div>';
  }

  // Shops and banks whose prices Sona does not track ("999 rate on Amazon"):
  // say so, give today's jeweller rate to compare, and a Google search the
  // visitor opens themselves - Sona never quotes a price from the web.
  var STORES = { amazon: 'Amazon', flipkart: 'Flipkart', myntra: 'Myntra', ajio: 'AJIO', 'tata cliq': 'Tata CLiQ', tatacliq: 'Tata CLiQ',
    nykaa: 'Nykaa', meesho: 'Meesho', jiomart: 'JioMart', mmtc: 'MMTC-PAMP', augmont: 'Augmont', safegold: 'SafeGold',
    sbi: 'SBI', hdfc: 'HDFC Bank', icici: 'ICICI Bank', axis: 'Axis Bank', kotak: 'Kotak Bank', 'post office': 'the post office',
    bank: 'banks', banks: 'banks', zepto: 'Zepto', blinkit: 'Blinkit', swiggy: 'Swiggy Instamart', bigbasket: 'BigBasket' };
  function storeIn(t) { for (var s in STORES) if (new RegExp('\\b' + s + '\\b').test(t)) return STORES[s]; return null; }
  var rawQ = '';
  function gLink(q) {
    return '<p><a class="sn-g" href="https://www.google.com/search?q=' + encodeURIComponent(q || rawQ) + '" target="_blank" rel="noopener nofollow">\ud83d\udd0e Google</a></p>';
  }
  function aOutside(store, k) {
    k = k || '24K';
    var en = 'I don\'t track ' + store + (/s$/.test(store) ? '\'' : '\'s') + ' prices - my rates come from jewellers\' own websites. To compare, here is today\'s middle rate at ' +
      KB.brands.length + ' jewellers. Tap Google to look up ' + store + '.';
    return { intent: 'outside', en: en, html: '<p>' + esc(en) + '</p>' + tiles(KB.med, k) + gLink(), say: en,
      chips: chips(['cheap22', 'bestoff']) };
  }
  function aMedian(k) {
    k = k || '22K';
    var m = KB.med, low = ranked(natBrands())[0];
    return { intent: 'rate', html: '<p>' + t('med_h', { n: KB.brands.length }) + '</p>' + tiles(m, k) +
      '<p>' + t('med_low', { b: esc(low.n), p: inr(rate(low, '22K')) }) + '</p>' + src(),
      say: t('say_med', { k: sK(k), p: sInr(m[k]), n: KB.brands.length, b: low.n, q: sInr(rate(low, k)) }),
      chips: chips(['cheap22', 'mycity', 'p10']) };
  }
  function aBrand(b, k) {
    k = k || '22K';
    var list = b.nat ? natBrands() : KB.brands, r = rankOf(b, list), n = list.length;
    var diff = rate(b, k) - KB.med[k];
    var rel = Math.abs(diff) < 1 ? t('rel_at', { k: k }) : t(diff < 0 ? 'rel_below' : 'rel_above', { k: k, p: inr(Math.abs(diff)) });
    var h = '<p>' + t('brand_h', { b: esc(b.n) }) + '</p>' + tiles({ '24K': rate(b, '24K'), '22K': rate(b, '22K'), '18K': rate(b, '18K') }, k) +
      '<p>' + t('brand_rank', { r: r, n: n, rel: rel }) + '</p>';
    if (b.mk) h += '<p>' + t('brand_mk', { list: Object.keys(b.mk).map(function (c) { return esc(catName(c)) + ' ' + pct(b.mk[c]); }).join(', ') }) + '</p>';
    if (b.off && b.off.length) h += '<p>' + t('brand_off', { o: esc(b.off[0].h) }) + '</p>';
    if (!b.nat && b.st) h += '<p class="sn-dim">' + t('brand_st', { s: esc(b.st.join(', ')) }) + '</p>';
    if (b.u) h += '<p>' + link(b.u, t('brand_link', { b: esc(b.n) })) + '</p>';
    var nm = b.n.split(' ')[0];
    return { intent: 'rate_brand', html: h + src(), say: t('say_brand', { b: b.n, k: sK(k), p: sInr(rate(b, k)), r: r, n: n }),
      chips: [chip('bmk', { b: nm }), chip('boff', { b: nm }), chip('cheap22')] };
  }
  function aCity(c, k) {
    k = k || '22K';
    var list = ranked(cityBrands(c)).slice(0, 6), locals = (c.loc || []).length;
    var note = locals ? t('city_loc', { l: locals, s: esc(c.st) }) : t('city_nat');
    return { intent: 'rate_city', html: '<p>' + t('city_h', { k: k, c: esc(c.n), note: note }) + '</p>' + table(list, k) +
      '<p>' + link(c.u, t('city_link', { c: esc(c.n) })) + '</p>' + src(),
      say: t('say_city', { c: c.n, k: sK(k), b: list[0].n, p: sInr(rate(list[0], k)) }),
      chips: chips(['p10', 'bestoff', 'k22v24']).concat(c.n === home ? [{ l: t('ch_chcity'), q: '#city' }] : []) };
  }
  function setHome(c) { home = c.n; try { localStorage.setItem('sona_home', c.n); } catch (_) {} }
  // Which city? The visitor's next city answer becomes their own.
  function askCity(msg) {
    wantHome = true;
    var geo = typeof navigator !== 'undefined' && navigator.geolocation;
    return { intent: 'ask_city', html: '<p>' + t(msg) + '</p>', say: t(msg),
      chips: (geo ? [{ l: '📍 ' + t('ch_loc'), q: '#loc' }] : []).concat(['Mumbai', 'Delhi', 'Bengaluru', 'Chennai', 'Hyderabad', 'Kolkata', 'Pune', 'Lucknow']
        .map(function (n) { return { l: n, q: n }; })) };
  }
  // The covered city nearest a point (the knowledge file's centres, "g").
  function nearest(la, lo) {
    var r = Math.PI / 180, best = null, bd = 1e9;
    KB.cities.forEach(function (c) {
      if (!c.g) return;
      var x = Math.sin((c.g[0] - la) * r / 2), y = Math.sin((c.g[1] - lo) * r / 2);
      var d = 12742 * Math.asin(Math.sqrt(x * x + Math.cos(la * r) * Math.cos(c.g[0] * r) * y * y));
      if (d < bd) { bd = d; best = c; }
    });
    return best;
  }
  // all: every national jeweller, cheapest to dearest ("compare jewellers").
  function aCheapest(k, c, all) {
    if (c) return aCity(c, k);
    k = k || '22K';
    var list = ranked(natBrands()).slice(0, all ? 99 : 6), hi = ranked(natBrands()).slice(-1)[0];
    var gap = (rate(hi, k) - rate(list[0], k)) * 10;
    return { intent: 'cheapest', html: '<p>' + t('cheap_h', { k: k }) + '</p>' + table(list, k) +
      '<p>' + t('cheap_gap', { p: inr(gap) }) + '</p>' + src(),
      say: t('say_cheap', { k: sK(k), b: list[0].n, p: sInr(rate(list[0], k)), q: sInr(gap) }),
      chips: chips(['mycity', 'afteroff', 'mkcmp']) };
  }
  function aCompare(bs, k) {
    k = k || '22K';
    var h = '<p>' + t('cmp_h', { k: k }) + '</p><div class="sn-cmp">' + bs.slice(0, 3).map(function (b) {
      return '<div><div class="sn-cn">' + esc(b.n) + '</div><b>' + inr(rate(b, k)) + '<small>/g</small></b>' +
        '<span>' + t('cmp_10', { p: inr(rate(b, k) * 10) }) + '</span>' +
        (b.mk ? '<span>' + t('cmp_mk', { p: pct(b.mk.Ring || b.mk[Object.keys(b.mk)[0]]) }) + '</span>' : '<span class="sn-dim">' + t('cmp_nomk') + '</span>') +
        (b.off && b.off.length ? '<span class="sn-off">' + esc(b.off[0].h) + '</span>' : '') + '</div>';
    }).join('') + '</div>';
    var s = bs.slice(0, 3).sort(function (a, b) { return a.r24 - b.r24; });
    var gap = (rate(s[s.length - 1], k) - rate(s[0], k)) * 10;
    h += '<p>' + t('cmp_win', { b: esc(s[0].n), k: k, p: inr(gap) }) + '</p>';
    return { intent: 'compare', html: h + src(), say: t('say_cmp', { b: s[0].n, p: sInr(gap), k: sK(k) }),
      chips: chips(['afteroff', 'mkcmp', 'bestoff']) };
  }
  function aMaking(bs, ct) {
    var withMk = KB.brands.filter(function (b) { return b.mk; });
    if (bs.length) {
      var b = bs[0];
      if (!b.mk) return { intent: 'making', html: '<p>' + t('mk_none', { b: esc(b.n), list: withMk.map(function (x) { return esc(x.n); }).join(', ') }) + '</p><p>' + link('/making-charges-comparison', t('mk_link')) + '</p>',
        say: t('say_mk_none', { b: b.n }) };
      var c1 = ct && b.mk[ct] != null ? ct : (b.mk.Ring != null ? 'Ring' : Object.keys(b.mk)[0]);
      return { intent: 'making', html: '<p>' + t('mk_brand_h', { b: esc(b.n) }) + '</p><div class="sn-list">' +
        Object.keys(b.mk).map(function (c) { return '<div class="sn-row"><span class="sn-nm">' + esc(catName(c)) + '</span><span class="sn-v">' + pct(b.mk[c]) + '</span></div>'; }).join('') + '</div>' +
        (b.mo && b.mo.u ? '<p>' + t('off_mo', { p: pct(b.mo.u) }) + '</p>' : '') +
        '<p class="sn-dim">' + t('mk_note') + '</p><p>' + link('/making-charges-comparison', t('mk_all')) + '</p>',
        say: t('say_mk_brand', { b: b.n, c: catName(c1), p: pct(b.mk[c1]) }),
        chips: [chip('boff', { b: b.n.split(' ')[0] }), chip('afteroff'), chip('cheap22')] };
    }
    var c = ct && ct !== 'Coin' ? ct : 'Ring', miss = null;      // miss: asked for, not measured
    var rows = withMk.filter(function (b) { return b.mk[c] != null; }).sort(function (a, b) { return a.mk[c] - b.mk[c]; });
    if (!rows.length) { miss = c; c = 'Ring'; rows = withMk.filter(function (b) { return b.mk.Ring != null; }).sort(function (a, b) { return a.mk.Ring - b.mk.Ring; }); }
    return { intent: 'making', html: '<p>' + (miss ? t('mk_nocat', { c: esc(catName(miss)), r: esc(catName(c)) }) : t('mk_h', { c: esc(catName(c)) })) + '</p><div class="sn-list">' +
      rows.slice(0, 6).map(function (b, i) { return '<div class="sn-row"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm">' + esc(b.n) + '</span><span class="sn-v">' + pct(b.mk[c]) + '</span></div>'; }).join('') + '</div>' +
      '<p>' + link('/making-charges-comparison', t('mk_every')) + '</p>',
      say: rows.length ? t('say_mk', { c: catName(c), b: rows[0].n, p: pct(rows[0].mk[c]) }) : '',
      chips: chips(['afteroff', 'bestoff', 'whatmk']) };
  }
  function aOffers(bs) {
    if (bs.length) {
      var b = bs[0];
      // the making-charge offer seen on the jeweller's own products (Tanishq)
      var mo = b.mo && b.mo.u && !b.mo.f ? '<p>' + t('off_mo', { p: pct(b.mo.u) }) + '</p>' : '';
      if (!b.off || !b.off.length) return { intent: 'offers', html: (mo || '<p>' + t('off_none', { b: esc(b.n) }) + '</p>') + '<p>' + link('/gold-offers-today', t('off_see')) + '</p>',
        say: mo ? t('off_mo', { p: pct(b.mo.u) }).replace(/<[^>]+>/g, '') : t('say_off_none', { b: b.n }) };
      return { intent: 'offers', html: '<p>' + t('off_brand_h', { b: esc(b.n) }) + '</p>' + b.off.map(function (o) {
        return '<div class="sn-card"><b>' + esc(o.h) + '</b><q>' + esc(o.t) + '</q><p>' + o.m + '</p><a href="' + esc(o.u) + '" target="_blank" rel="nofollow noopener">' + t('off_page') + '</a></div>';
      }).join('') + mo + '<p>' + link('/gold-offers-today', t('off_all')) + '</p>',
        say: t('say_off_brand', { b: b.n, n: b.off.length }), chips: chips(['afteroff', 'cheap22']) };
    }
    // Every jeweller with an offer today, A to Z, each with its own offers:
    // no jeweller is singled out. The ring price after offers is one line,
    // because only an offer on every design can be priced into it.
    var withOff = KB.brands.filter(function (b) { return b.off && b.off.length; })
      .sort(function (a, b) { return a.n.localeCompare(b.n); });
    var ring = (KB.ring || [])[0];
    var h = '<p>' + t('off_all_h', { n: withOff.length }) + '</p><div class="sn-list">' + withOff.map(function (b) {
      return '<div class="sn-row sn-orow"><span class="sn-nm"><b>' + esc(b.n) + '</b>' +
        b.off.slice(0, 3).map(function (o) { return '<small>' + esc(o.h) + '</small>'; }).join('') + '</span></div>';
    }).join('') + '</div>' +
      (ring ? '<p class="sn-dim">' + t('off_ring', { b: esc(ring.n), p: inr(ring.a) }) + '</p>' : '') +
      '<p>' + link('/gold-offers-today', t('off_every')) + '</p>';
    return { intent: 'offers', html: h, say: ring ? t('say_off_all', { n: withOff.length, b: ring.n, p: sInr(ring.a) }) : '',
      chips: chips(['goodmk', 'mkcmp', 'cheap22']) };
  }
  // "best offer on a ring": every jeweller with a measured making charge for
  // that piece, priced for 10 g of 22K (or the weight asked) after its flat
  // making-charge offer today; an "up to" offer (some designs only) is shown
  // as the best case beside it, never ranked on.
  var BO_CATS = ['Ring', 'Earrings', 'Bangle', 'Mangalsutra'];
  function aBestOffer(c, w) {
    w = w || { g: 10, n: '10', u: 'g' };
    var rows = KB.brands.filter(function (b) { return b.mk && b.mk[c] != null && rate(b, '22K'); }).map(function (b) {
      var gold = rate(b, '22K') * w.g, mk = b.mk[c], mo = b.mo || {}, f = mo.f || 0, u = mo.u || 0;
      var after = mk * (1 - f / 100);
      return { b: b, mk: mk, f: f, u: u, after: after, tot: (gold + gold * after / 100) * 1.03,
        best: u > f ? (gold + gold * mk * (1 - u / 100) / 100) * 1.03 : null };
    }).sort(function (a, b) { return a.tot - b.tot; });
    var others = BO_CATS.filter(function (x) { return x !== c; }).map(function (x) { return { l: catName(x), q: 'best offer ' + x.toLowerCase() }; });
    if (rows.length < 2) return { intent: 'best_offer', html: '<p>' + t('bo_none', { c: esc(catName(c)) }) + ' ' + link('/gold-offers-today', t('off_see')) + '</p>',
      say: t('bo_none', { c: catName(c) }), chips: others };
    var h = '<p>' + t('bo_h', { w: esc(wLabel(w)), c: esc(catName(c)) }) + '</p><div class="sn-list">' + rows.slice(0, 8).map(function (r, i) {
      var mk = pct(r.mk) + (r.f ? ' → ' + pct(r.after) + ' (−' + pct(r.f) + ')' : r.u ? '' : ' · ' + t('bo_noff'));
      var up = r.best != null ? '<small>(' + t('bo_upto') + ' −' + pct(r.u) + '* → ' + inr(r.best) + ')</small>' : '';
      return '<div class="sn-row sn-orow"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm"><b>' + esc(r.b.n) + '</b><small>' + mk + '</small>' + up +
        '</span><span class="sn-v">' + inr(r.tot) + '</span></div>';
    }).join('') + '</div><p class="sn-dim">' + t('bo_note') + '</p>';
    var top = bill(rows[0].b, c, w);                 // the breakup for #1
    if (top) h += '<p>' + t('bo_bill_h', { w: esc(wLabel(w)), c: esc(catName(c)), b: esc(rows[0].b.n) }) + '</p>' + top.html;
    h += '<p>' + link('/making-charges-comparison', t('mk_every')) + ' · ' + link('/gold-offers-today', t('off_see')) + '</p>';
    return { intent: 'best_offer', html: h, say: t('say_bo', { w: wLabel(w), c: catName(c), b: rows[0].b.n, p: sInr(rows[0].tot) }), chips: others };
  }
  // Gold around the world: spot per gram in the country's currency (from the
  // knowledge file's "intl"), the karat or unit people there buy in, the rupee
  // equivalent and India's own middle rate beside it. Reference prices.
  var COUNTRY = {
    dubai: 'AE', uae: 'AE', emirates: 'AE', 'abu dhabi': 'AE', sharjah: 'AE',
    saudi: 'SA', 'saudi arabia': 'SA', riyadh: 'SA', jeddah: 'SA', ksa: 'SA',
    usa: 'US', america: 'US', 'united states': 'US', 'new york': 'US',
    cambodia: 'KH', 'phnom penh': 'KH', kazakhstan: 'KZ', almaty: 'KZ', astana: 'KZ',
    russia: 'RU', moscow: 'RU'
  };
  var CTRY = {
    AE: { p: 'dubai', n: 'UAE (Dubai)', c: 'AED', s: 'AED ', k: '22K', f: 22 / 24 },
    SA: { p: 'saudi-arabia', n: 'Saudi Arabia', c: 'SAR', s: 'SAR ', k: '21K', f: 21 / 24 },
    US: { p: 'usa', n: 'USA', c: 'USD', s: '$', oz: true },
    KH: { p: 'cambodia', n: 'Cambodia', c: 'KHR', s: '៛', chi: true },
    KZ: { p: 'kazakhstan', n: 'Kazakhstan', c: 'KZT', s: '₸', k: '585 (14K)', f: 0.585 },
    RU: { p: 'russia', n: 'Russia', c: 'RUB', s: '₽', k: '585 (14K)', f: 0.585 }
  };
  function countryIn(t) {
    for (var w in COUNTRY) if (new RegExp('\\b' + w + '\\b').test(t)) return COUNTRY[w];
    return null;
  }
  function money(sym, v) { return sym + (v >= 1000 ? Math.round(v).toLocaleString('en-US') : v.toFixed(2)); }
  function aIntl(code) {
    var I = KB.intl, w = CTRY[code];
    if (!I || !w) return null;
    var fx = w.c === 'USD' ? 1 : I.fx[w.c], inrFx = I.fx.INR;
    if (!(fx > 0)) return null;
    var g = I.usd_g * fx, rows = '<div class="sn-row"><span class="sn-nm">24K</span><span class="sn-v">' + money(w.s, g) + '/g</span></div>';
    if (w.k) rows += '<div class="sn-row"><span class="sn-nm">' + w.k + '</span><span class="sn-v">' + money(w.s, g * w.f) + '/g</span></div>';
    if (w.oz) rows += '<div class="sn-row"><span class="sn-nm">24K, troy oz</span><span class="sn-v">' + money('$', I.usd_g * 31.1034768) + '</span></div>';
    if (w.chi) rows += '<div class="sn-row"><span class="sn-nm">24K, chi (3.75 g)</span><span class="sn-v">' + money('$', I.usd_g * 3.75) + '</span></div>';
    var h = '<p>' + t('intl_h', { c: esc(w.n) }) + '</p><div class="sn-list">' + rows + '</div>';
    if (inrFx > 0) {
      var inr10 = I.usd_g * inrFx * 10, ind10 = KB.med['24K'] * 10, x = Math.round(Math.abs(ind10 / inr10 - 1) * 100);
      h += '<p>' + t('intl_inr', { p: inr(inr10) }) + '</p>' +
        (x ? '<p>' + t(ind10 > inr10 ? 'intl_more' : 'intl_less', { p: inr(ind10), x: x, c: esc(w.n) }) + '</p>' : '');
    }
    h += '<p class="sn-dim">' + t('intl_note') + '</p><p>' + link('/gold-rate-today-in-' + w.p, w.n + ' vs India →') + ' · ' + link('/gold-rate-around-the-world', 'Gold around the world →') + '</p>';
    return { intent: 'intl', html: h, say: t('say_intl', { c: w.n, p: money(w.s, g) }),
      chips: ['AE', 'SA', 'US', 'RU'].filter(function (x) { return x !== code; }).map(function (x) { return { l: CTRY[x].n, q: 'gold rate in ' + CTRY[x].n }; }) };
  }
  // An approximate bill for one jeweller and piece: gold at its rate today,
  // its making charge (the typical one when not measured there), the offer
  // on making (a flat offer applied; an "up to" one only shown), GST, total.
  function bill(b, c, w) {
    var r22 = rate(b, '22K'), gold = r22 * w.g, typ = false, mk = b.mk && b.mk[c] != null ? b.mk[c] : null;
    if (mk == null) {
      var all = KB.brands.filter(function (x) { return x.mk && x.mk[c] != null; }).map(function (x) { return x.mk[c]; }).sort(function (a, z) { return a - z; });
      if (!all.length) return null;
      mk = all[Math.floor(all.length / 2)]; typ = true;
    }
    var mo = b.mo || {}, f = typ ? 0 : (mo.f || 0), u = typ ? 0 : (mo.u || 0);
    var mkAmt = gold * mk / 100, off = mkAmt * f / 100, after = mkAmt - off, gst = (gold + after) * 0.03, tot = gold + after + gst;
    var best = u > f ? (gold + mkAmt * (1 - u / 100)) * 1.03 : null;
    var h = '<div class="sn-bill">' +
      '<div><span>' + t('price_gold', { g: Math.round(w.g * 1000) / 1000, p: inr(r22) }) + '</span><b>' + inr(gold) + '</b></div>' +
      '<div><span>' + (typ ? t('bo_mk_typ', { p: pct(mk) }) : t('bo_mk', { p: pct(mk) })) + '</span><b>' + inr(mkAmt) + '</b></div>' +
      (f ? '<div><span>' + t('bo_off', { p: pct(f) }) + '</span><b>−' + inr(off) + '</b></div>' +
           '<div><span>' + t('bo_mk_after') + '</span><b>' + inr(after) + '</b></div>' : '') +
      '<div><span>GST 3%</span><b>' + inr(gst) + '</b></div>' +
      '<div class="sn-tot"><span>' + t('price_total') + '</span><b>≈ ' + inr(tot) + '</b></div></div>' +
      (!f && u ? '<p class="sn-dim">' + t('bo_off_upto', { p: pct(u) }) + '</p>' : '') +
      (!f && !u && !typ ? '<p class="sn-dim">' + t('bo_off_none') + '</p>' : '') +
      (best ? '<p>' + t('bo_best_case', { p: inr(best) }) + '</p>' : '') +
      '<p class="sn-dim">' + t('bo_disc') + '</p>';
    return { html: h, tot: tot };
  }
  // "best deal at Tanishq (on a ring)": that jeweller's approximate bill
  function aBrandDeal(b, c, w) {
    if (!b.r24) return aOffers([b]);
    if (!c || c === 'Coin' || BO_CATS.indexOf(c) < 0) return { intent: 'ask_cat', html: '<p>' + t('bo_ask_b', { b: esc(b.n) }) + '</p>', say: t('bo_ask_b', { b: b.n }),
      chips: BO_CATS.map(function (x) { return { l: catName(x), q: 'best deal ' + x.toLowerCase() + ' at ' + b.n }; }) };
    w = w || { g: 10, n: '10', u: 'g' };
    var bl = bill(b, c, w);
    if (!bl) return aOffers([b]);
    return { intent: 'brand_deal', html: '<p>' + t('bo_bill_h', { w: esc(wLabel(w)), c: esc(catName(c)), b: esc(b.n) }) + '</p>' + bl.html +
      '<p>' + link('/making-charges-comparison', t('mk_every')) + ' · ' + link('/gold-offers-today', t('off_see')) + '</p>',
      say: t('say_bo_bill', { b: b.n, w: wLabel(w), c: catName(c), p: sInr(bl.tot) }),
      chips: BO_CATS.filter(function (x) { return x !== c; }).map(function (x) { return { l: catName(x), q: 'best deal ' + x.toLowerCase() + ' at ' + b.n }; }).concat([{ l: t('ch_bestoff'), q: 'best offer ' + c.toLowerCase() }]) };
  }
  // Which piece? The next answer is priced (see wantOffer in answer()).
  function askOfferCat() {
    wantOffer = true;
    return { intent: 'ask_cat', html: '<p>' + t('bo_ask') + '</p>', say: t('bo_ask'),
      chips: BO_CATS.map(function (c) { return { l: catName(c), q: 'best offer ' + c.toLowerCase() }; }) };
  }
  function aPrice(w, k, bs, ct) {
    k = k || (ct === 'Coin' ? '24K' : '22K');
    var b = bs[0] || ranked(natBrands())[0], who = bs[0] ? esc(b.n) : t('price_who', { b: esc(b.n) });
    var gold = rate(b, k) * w.g;
    var mkp = b.mk ? (ct && b.mk[ct] != null ? b.mk[ct] : (b.mk.Ring != null ? b.mk.Ring : null)) : null;
    if (ct === 'Coin' || (k === '24K' && !ct)) mkp = null;   // 24K: coins and bars
    var mk = mkp != null ? gold * mkp / 100 : 0, gst = (gold + mk) * 0.03, tot = gold + mk + gst;
    var h = '<p>' + t('price_h', { w: esc(wLabel(w)), k: k, who: who }) + '</p><div class="sn-bill">' +
      '<div><span>' + t('price_gold', { g: Math.round(w.g * 1000) / 1000, p: inr(rate(b, k)) }) + '</span><b>' + inr(gold) + '</b></div>' +
      (mkp != null ? '<div><span>' + t('price_mk', { p: pct(mkp), c: ct && b.mk[ct] != null ? esc(catName(ct)) : t('price_typ') }) + '</span><b>' + inr(mk) + '</b></div>' : '') +
      '<div><span>GST 3%</span><b>' + inr(gst) + '</b></div><div class="sn-tot"><span>' + t('price_total') + '</span><b>' + inr(tot) + '</b></div></div>' +
      (mkp == null && ct !== 'Coin' && k !== '24K' ? '<p class="sn-dim">' + t('price_nomk') + '</p>' : '') + src();
    return { intent: 'price', html: h, say: t('say_price', { w: wLabel(w), k: sK(k), b: b.n, p: sInr(tot) }),
      chips: chips(['another', 'afteroff', 'cheap22']) };
  }
  function aTrend(k) {
    k = k || '22K';
    var h = KB.hist || [], f = K[k];
    if (h.length < 2) return { intent: 'trend', html: '<p>' + t('trend_none') + ' ' + link('/gold-rate-history', t('hist_link')) + '</p>', say: t('trend_none') };
    var last = h[h.length - 1][1] * f;
    function back(n) { var i = Math.max(0, h.length - 1 - n); return h[i][1] * f; }
    function chg(v) { var d = last - v, p = d / v * 100; return '<b class="' + (d >= 0 ? 'up' : 'dn') + '">' + (d >= 0 ? '▲ ' : '▼ ') + inr(Math.abs(d)) + ' (' + pct(Math.abs(p)) + ')</b>'; }
    var pts = h.slice(-30).map(function (x) { return x[1]; }), mn = Math.min.apply(null, pts), mx = Math.max.apply(null, pts);
    var sv = '<svg class="sn-spark" viewBox="0 0 240 48" preserveAspectRatio="none"><polyline fill="none" stroke="#e7bf5a" stroke-width="2" stroke-linejoin="round" points="' +
      pts.map(function (v, i) { return (i * 240 / Math.max(1, pts.length - 1)).toFixed(1) + ',' + (44 - (mx === mn ? 20 : (v - mn) / (mx - mn) * 40)).toFixed(1); }).join(' ') + '"/></svg>';
    var d1 = last - back(1);
    return { intent: 'trend', html: '<p>' + t('trend_h', { k: k, p: inr(last) }) + '</p>' + sv +
      '<div class="sn-list"><div class="sn-row"><span class="sn-nm">' + t('vs1') + '</span><span class="sn-v">' + chg(back(1)) + '</span></div>' +
      '<div class="sn-row"><span class="sn-nm">' + t('vs7') + '</span><span class="sn-v">' + chg(back(7)) + '</span></div>' +
      '<div class="sn-row"><span class="sn-nm">' + t('vs30') + '</span><span class="sn-v">' + chg(back(30)) + '</span></div></div>' +
      '<p class="sn-dim">' + t('trend_note') + ' ' + link('/gold-rate-history', t('full_hist')) + '</p>',
      say: t(Math.abs(d1) < 1 ? 'say_trend_same' : d1 > 0 ? 'say_trend_up' : 'say_trend_dn', { k: sK(k), p: sInr(last), q: sInr(Math.abs(d1)) }),
      chips: chips(['alert', 'cheap22', 'goodtime']) };
  }
  function aAlerts() {
    return { intent: 'alerts', html: '<p>' + t('alerts') + '</p><button class="sn-cta" data-sn="subscribe">' + t('alerts_cta') + '</button>', say: t('alerts') };
  }
  function words(s) { return s.split(/\s+/).filter(function (w) { return w.length > 2 && !/^(the|and|for|what|how|are|you|your|with|does|this|that|from|have|can|why|which|about|gold|is|of)$/.test(w); }); }
  function scoreDoc(s, q, keys) {
    var ws = words(s), qs = norm(q), n = 0;
    ws.forEach(function (w) { if (qs.indexOf(' ' + w) > -1) n += 1; if ((keys || []).indexOf(w) > -1) n += 1.5; });
    return n / Math.max(3, Math.sqrt(words(qs).length + 1) * 2);
  }
  // FAQ and approved answers are written in English: `en` carries the text
  // so it can be translated on the visitor's device, where the browser can.
  // One FAQ answer by its question (b: a jeweller to link as well).
  function faqQ(q, b) {
    var d = KB.faq.filter(function (f) { return f.q === q; })[0];
    if (!d) return null;
    return { intent: 'faq', score: 2, en: d.a, html: '<p>' + esc(d.a) + '</p>' + (d.u ? '<p>' + link(d.u, t('more')) + '</p>' : ''),
      say: d.a, chips: b ? [chip('boff', { b: b.n.split(' ')[0] }), chip('cheap22')] : chips(['cheap22', 'bestoff']) };
  }
  function aSearch(s) {
    var best = null, bs = 0;
    (KB.learned || []).forEach(function (d) { var v = scoreDoc(s, d.q, []) * 1.2; if (v > bs) { bs = v; best = d; } });
    KB.faq.forEach(function (d) { var v = scoreDoc(s, d.q, d.k); if (v > bs) { bs = v; best = d; } });
    if (best && bs >= 0.6) return { intent: 'faq', score: bs, en: best.a, html: '<p>' + esc(best.a) + '</p>' + (best.u ? '<p>' + link(best.u, t('more')) + '</p>' : ''),
      say: best.a, chips: chips(['cheap22', 'bestoff']) };
    var g = null, gs = 0;
    KB.guides.forEach(function (d) { var v = scoreDoc(s, d.t + ' ' + d.d, []); if (v > gs) { gs = v; g = d; } });
    if (g && gs >= 0.6) return { intent: 'guide', score: gs, en: g.t + '. ' + g.d,
      html: '<p>' + t('guide_h', { t: esc(g.t), d: esc(g.d) }) + '</p><p>' + link(g.u, t('guide_link')) + '</p>', say: g.t + '. ' + g.d };
    return null;
  }

  function answer(q) {
    var tx = norm(q), k = karatIn(tx), bs = brandsIn(tx), c = cityIn(tx), w = weightIn(tx), ct = catIn(tx);
    var mine = /\b(my city|near me|nearby|mere sheher|mere shahar|my area)\b/.test(tx);
    if (c && (wantHome || mine || /\b(i am in|i'm in|im in|i live in|i stay in)\b/.test(tx))) setHome(c);
    wantHome = false;
    var offerAsk = wantOffer; wantOffer = false;
    if (offerAsk && ct && ct !== 'Coin') return aBestOffer(ct, w);
    if (mine && !c) {
      c = home && KB.cities.filter(function (x) { return x.n === home; })[0];
      if (!c) return askCity('ask_city');
    }
    if (has(tx, W.silver) && !has(tx, ['gold', 'sona'])) return { intent: 'silver', html: '<p>' + t('silver') + '</p>', say: t('silver'), chips: chips(['rate', 'cheap22']) };
    if (has(tx, ['unsubscribe', 'opt out'])) return faqQ('How do I unsubscribe from the emails?');
    if (has(tx, ['alert', 'alerts', 'notify', 'subscribe', 'email me', 'whatsapp', 'set a price'])) return aAlerts();
    // "gold rate tomorrow", "will gold go up": nobody can say - the honest answer
    if (/\b(tomorrow|next (week|month|year)|forecast|predict|prediction)\b/.test(tx) ||
        /\bwill\b.*\b(go|rise|fall|increase|decrease|drop|come down|go up|go down)\b/.test(tx)) return faqQ('Is now a good time to buy gold?');
    // "is Tanishq gold pure", "is CaratLane trustworthy": the hallmark, not a ranking
    if (bs.length === 1 && has(tx, ['pure', 'purity', 'trust', 'trustworthy', 'genuine', 'reliable', 'safe', 'fake', 'quality', 'honest', 'real', 'original']) &&
        !has(tx, W.making) && !has(tx, W.offer)) return faqQ('Is this jeweller\'s gold pure and trustworthy?', bs[0]);
    // "1 gram gold jewellery" is imitation jewellery, not a weight
    if (/\b(1|one|ek) ?(gram|gm|g) gold (jewell?ery|jewelry|chain|bangles?|necklace|set|ornaments?)\b|\b(imitation|gold plated|gold covering)\b/.test(tx))
      return faqQ('What is 1 gram gold jewellery?');
    if (has(tx, ['free']) && has(tx, ['website', 'site', 'sona', 'app', 'service', 'this', 'it'])) return faqQ('Is this website free?');
    // "what is 916 / 22K gold", "what is carat": a meaning, not the day's rate
    var meaning = /\b(what is|whats|what does|meaning|means|mean|matlab|mhanje)\b/.test(tx) && !has(tx, W.rate) && !w && !bs.length && !c;
    if (meaning && k) return faqQ({ '22K': 'What is 916 gold?', '18K': 'Is 18K gold good for jewellery?', '14K': 'Is 14K gold real gold?' }[k] ||
                                  'What is the difference between 22K and 24K gold?');
    if (meaning && /\b(carat|karat|caret)\b/.test(tx)) return faqQ('What is the difference between carat and karat?');
    // "gold rate in Dubai", "saudi gold price", "रूस में सोने का भाव": that country's reference price
    var ctry = countryIn(tx);
    if (ctry && !bs.length && KB.intl && !/\b(duty|customs|carry|allowed|allowance|limit|bring|import|cheaper|cheap|costlier|saving|worth)\b/.test(tx)) {
      var ia = aIntl(ctry); if (ia) return ia;
    }
    var store = storeIn(tx);
    if (store && !has(tx, ['digital', 'etf', 'loan', 'emi', 'scheme', 'bond', 'bonds', 'sgb'])) return aOutside(store, k);
    // "gold rate per gram 18 carat": that karat's rate, not its explainer
    if (k && /\b(rate|rates|price|bhav|dar|per gram|today|aaj)\b/.test(tx) && !meaning && !bs.length && !c && !w &&
        !has(tx, W.cheap) && !has(tx, W.making) && !has(tx, W.offer) && !has(tx, W.trend) && !has(tx, ['difference', 'vs', 'versus', 'better'])) return aMedian(k);
    // "are your rates accurate", "how do you get the rates"
    if (/\b(accurate|correct|reliable|authentic|source|sources|come from|how do you get|where do you get|how do you collect)\b/.test(tx) &&
        /\b(rates?|prices?|data|figures)\b/.test(tx) && !bs.length && !c) return faqQ('Where do these rates come from?');
    if (bs.length >= 2) return aCompare(bs, k);
    var across = has(tx, ['compare', 'comparison', 'compared', 'difference', 'differ', 'gap', 'vs', 'versus', 'across', 'other', 'all']);
    if (has(tx, W.making) && (has(tx, W.cheap) || across) && !w) return aMaking(bs, ct);    // "lowest making charge", "compare making charges": the ranking
    // "what is wastage / VA": the explanation; "making charges on bangles", "making kitna hai": the figures
    if (has(tx, W.making) && !w && !bs.length && !ct && /\b(what is|what are|whats|meaning|explain|define|matlab|mhanje)\b/.test(tx))
      return faqQ('What are making charges?');
    if (has(tx, W.making) && !w && (ct || /\b(how much|kitna|kitni|kitne|kiti)\b/.test(tx))) return aMaking(bs, ct);
    // "compare jewellers", "rate difference between jewellers": all of them, cheapest first
    if (across && /\b(jewell?ers|jewelers|shops|stores|brands|showrooms)\b/.test(tx) && !bs.length && !w &&
        !has(tx, W.offer) && !has(tx, W.making) && !/\b(why|kyon|kyun|kyu)\b/.test(tx)) return aCheapest(k, c, true);
    // "best deal at Tanishq", "Indriya ring final price with offer": that jeweller's approximate bill
    if (bs.length === 1 && (has(tx, W.offer) || /\b(bill|breakup|break up|final price|total cost|total price)\b/.test(tx)) &&
        /\b(best|deal|deals|bill|breakup|break up|calculate|final|total|kitna|kitne|kitni)\b/.test(tx)) return aBrandDeal(bs[0], ct, w);
    // "best offer", "best offer on bangles", "which jeweller is cheapest after offers on a ring": the calculator
    if (has(tx, W.offer) && !bs.length && !c && (ct ? ct !== 'Coin' : /\b(best|cheapest|lowest|calculate|which|kaunsa|konsa|kaunsi|sabse)\b/.test(tx)))
      return ct ? aBestOffer(ct, w) : askOfferCat();
    var strong = aSearch(tx);                // a question the FAQ answers word for word
    if (strong && strong.score >= 1.0 && !w && !bs.length && !c) return strong;
    if (has(tx, W.offer) || /\bafter offers?\b/.test(tx)) return aOffers(bs);
    if (has(tx, W.making) && !w) return aMaking(bs, ct);
    if (w) return aPrice(w, k, bs, ct);
    if (has(tx, W.trend) && !bs.length) return aTrend(k);
    var search = aSearch(tx);
    if (search && search.score > 0.9) return search;
    if (search && /\b(dubai|uae|abroad|singapore|overseas|foreign)\b/.test(tx)) return search;   // not "cheapest here"
    if (has(tx, W.cheap)) return aCheapest(k, c);
    if (bs.length) return aBrand(bs[0], k);
    if (c) return aCity(c, k);
    if (search) return search;
    if (has(tx, W.rate) || k) return aMedian(k);
    // "gold" alone, or "gold today": the rate. A real question about gold that
    // nothing above covers is better left unanswered (and learned) than
    // answered with the day's rate.
    if (/\b(gold|sona)\b/.test(tx) && (!/\b(what|how|why|when|can|could|is|are|should|do|does|which|kya|kaise|kyun|kay|kasa|kashi)\b/.test(tx) ||
        tx.split(/\s+/).length <= 3)) return aMedian(k);
    if (has(tx, W.hello)) return { intent: 'hello', html: '<p>' + t('hello', { n: KB.brands.length }) + '</p>', say: t('hello', { n: KB.brands.length }), chips: suggest() };
    if (has(tx, W.thanks)) return { intent: 'thanks', html: '<p>' + t('thanks') + '</p>', say: t('thanks'), chips: chips(['cheap22', 'bestoff']) };
    if (W.who.some(function (x) { return tx.indexOf(x) > -1; })) return { intent: 'about', html: '<p>' + t('about', { n: KB.brands.length }) + '</p>', say: t('about', { n: KB.brands.length }), chips: suggest() };
    return null;
  }
  // A question in any language: Indian scripts are first turned into the
  // words above (sona_lang.js); the reply comes in the asker's language.
  // chip: a suggestion tapped (asked in English, shown in the visitor's language).
  // "in Hindi", "marathi madhe sanga": a language asked for by name is kept
  // (as if picked from the menu); Hindi or Marathi typed in English letters
  // is answered in that language unless the visitor picked one.
  var justPicked = false;
  function understand(q, chip, spoken) {
    justPicked = false;
    var req = !chip && LG && LG.asked(q);
    if (req && STR[req.c]) {
      PICK = req.c; try { localStorage.setItem('sona_pick', PICK); } catch (_) {}
      LANG = uiLang(); RL = PICK; justPicked = true;
      if (panel) labels();
      track('lang_ask_' + PICK);
      q = req.rest;
      if (!q.trim()) return '';
    }
    // On Auto, each question's own words decide its language (Hindi and
    // Marathi told apart word by word), so the visitor can switch freely and
    // the mic follows; a language the visitor chose stays put.
    var d = LG && (LG.detect(q, PICK || HEARD, !!PICK) || (PICK ? null : LG.roman(q)));
    if (d && STR[d]) {
      RL = d;
      if (!PICK && d !== HEARD) {                 // she now listens and labels in it too
        HEARD = d; LANG = d; try { localStorage.setItem('sona_heard', d); } catch (_) {}
        if (panel) labels();
        RL = d;
      }
    } else RL = chip ? LANG : (PICK || 'en');
    if (LG && LG.isIndic(q)) return LG.understand(q, VOCAB, RL).text;
    return q;
  }
  // The answer to a question as typed; a bare "in Marathi" gets a hello in it.
  function reply(q, chip, spoken) {
    rawQ = q;
    var tx = understand(q, chip, spoken);
    if (!tx && justPicked) return { tx: tx, a: { intent: 'lang', html: '<p>' + t('greet1') + '</p><p>' + t('greet2') + '</p>',
      say: (t('greet1') + ' ' + t('greet2')).replace(/<[^>]+>/g, ''), chips: suggest() } };
    return { tx: tx, a: answer(tx) };
  }

  // ------------------------------------------------------------- avatar
  // Sona's face, drawn in SVG (no image to download): ivory-and-gold helmet,
  // black visor, glowing gold eyes, headphone ears, a bun with a gold band
  // and a forehead jewel. CSS brings her to life: she bobs, blinks and
  // smiles while idle, and talks (mouth moving, eyes glancing) while a reply
  // is being written - add the class "sona-talk" to any element holding her.
  var avN = 0;
  function avatar(full) {
    var p = 'sv' + (++avN) + '-';
    return '<svg class="sona-svg" viewBox="0 0 120 ' + (full ? 132 : 120) + '" aria-hidden="true" focusable="false"><defs>' +
      '<radialGradient id="' + p + 's" cx="38%" cy="28%" r="78%"><stop offset="0" stop-color="#fffaf0"/><stop offset=".55" stop-color="#f1e2c4"/><stop offset="1" stop-color="#c9a46c"/></radialGradient>' +
      '<linearGradient id="' + p + 'g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff0b8"/><stop offset=".45" stop-color="#e3b44f"/><stop offset="1" stop-color="#9c6b14"/></linearGradient>' +
      '<radialGradient id="' + p + 'v" cx="42%" cy="32%" r="80%"><stop offset="0" stop-color="#33271a"/><stop offset="1" stop-color="#0a0705"/></radialGradient>' +
      '<radialGradient id="' + p + 'e" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#fff8d6"/><stop offset=".55" stop-color="#ffd25e"/><stop offset="1" stop-color="#e3971a"/></radialGradient>' +
      '<filter id="' + p + 'f" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>' +
      '<g class="sv-bob">' +
      (full ? '<rect x="52" y="96" width="16" height="12" rx="4" fill="url(#' + p + 'g)"/><path d="M30 132 C34 112 48 104 60 104 C72 104 86 112 90 132Z" fill="url(#' + p + 's)"/><path d="M44 107 Q60 116 76 107" stroke="url(#' + p + 'g)" stroke-width="2.4" fill="none"/>' +
        '<circle cx="60" cy="121" r="6.5" fill="url(#' + p + 'g)"/><text x="60" y="124.6" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="9" fill="#5a3d08">S</text>' : '') +
      '<ellipse cx="60" cy="15" rx="13" ry="10" fill="url(#' + p + 's)"/><rect x="46" y="19" width="28" height="5.5" rx="2.7" fill="url(#' + p + 'g)"/>' +
      '<g class="sv-ear"><circle cx="17" cy="61" r="11" fill="url(#' + p + 'g)"/><circle cx="17" cy="61" r="6.6" fill="#2a1d0c"/><circle class="sv-glow" cx="17" cy="61" r="3.8" fill="#ffd25e"/></g>' +
      '<g class="sv-ear"><circle cx="103" cy="61" r="11" fill="url(#' + p + 'g)"/><circle cx="103" cy="61" r="6.6" fill="#2a1d0c"/><circle class="sv-glow" cx="103" cy="61" r="3.8" fill="#ffd25e"/></g>' +
      '<circle cx="60" cy="60" r="42" fill="url(#' + p + 's)"/>' +
      '<ellipse cx="60" cy="64" rx="33.5" ry="27.5" fill="none" stroke="url(#' + p + 'g)" stroke-width="2.6"/>' +
      '<ellipse cx="60" cy="64" rx="31" ry="25" fill="url(#' + p + 'v)"/>' +
      '<path d="M37 55 Q43 42 58 40" stroke="rgba(255,255,255,.16)" stroke-width="3.2" fill="none" stroke-linecap="round"/>' +
      '<path d="M60 25 L65.5 31.5 L60 38 L54.5 31.5Z" fill="url(#' + p + 'g)"/><circle cx="60" cy="31.5" r="1.8" fill="#fff6d0"/>' +
      '<g class="sv-eyes"><g filter="url(#' + p + 'f)"><ellipse class="sv-eye" cx="48" cy="62" rx="5.4" ry="6.6" fill="url(#' + p + 'e)"/><ellipse class="sv-eye" cx="72" cy="62" rx="5.4" ry="6.6" fill="url(#' + p + 'e)"/></g>' +
      '<circle class="sv-eye" cx="50" cy="59.6" r="1.6" fill="#fff"/><circle class="sv-eye" cx="74" cy="59.6" r="1.6" fill="#fff"/></g>' +
      '<ellipse cx="39.5" cy="73" rx="4.6" ry="2.6" fill="#ff8f7d" opacity=".42"/><ellipse cx="80.5" cy="73" rx="4.6" ry="2.6" fill="#ff8f7d" opacity=".42"/>' +
      '<path class="sv-smile" d="M51 74 Q60 82.5 69 74" stroke="#ffd25e" stroke-width="2.7" fill="none" stroke-linecap="round" filter="url(#' + p + 'f)"/>' +
      '<ellipse class="sv-talk" cx="60" cy="76.5" rx="5" ry="3.6" fill="#ffd25e" filter="url(#' + p + 'f)"/>' +
      '</g></svg>';
  }
  window.GR_SONA_AVATAR = avatar;

  // --------------------------------------------------------------- UI
  var SUGGEST = ['cheap22', 'mycity', 'tvk', 'bestoff', 'p10chain', 'k22v24'];      // chip keys (sona_i18n.js ch_*)
  var CSS = '' +
    '.sn-fab{position:fixed;right:16px;bottom:calc(18px + env(safe-area-inset-bottom));z-index:8500;display:flex;align-items:center;gap:9px;height:52px;padding:0 18px 0 7px;border:0;border-radius:999px;cursor:pointer;color:#1a1405;font:700 14.5px/1 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:linear-gradient(135deg,#ffe9a8,#e7bf5a 45%,#b98a24);box-shadow:0 10px 30px rgba(185,138,36,.45),0 0 0 1px rgba(255,255,255,.25) inset;transition:transform .2s}' +
    '.sn-fab:hover{transform:translateY(-2px)}.sn-fab .sn-orb{width:42px;height:42px;flex:none;margin:-2px 0;filter:drop-shadow(0 2px 4px rgba(90,60,0,.35))}' +
    '.sn-fab .sn-ping{position:absolute;top:-3px;right:-3px;width:12px;height:12px;border-radius:50%;background:#2fd18b;box-shadow:0 0 0 0 rgba(47,209,139,.7);animation:snPing 2s infinite}' +
    '@keyframes snPing{0%{box-shadow:0 0 0 0 rgba(47,209,139,.7)}70%{box-shadow:0 0 0 10px rgba(47,209,139,0)}100%{box-shadow:0 0 0 0 rgba(47,209,139,0)}}' +
    'html.sona-bnav .sn-fab{bottom:calc(78px + env(safe-area-inset-bottom))}' +
    '.sona-svg{display:block;width:100%;height:100%;overflow:visible}' +
    '.sona-svg .sv-bob{animation:svBob 3.4s ease-in-out infinite}' +
    '@keyframes svBob{0%,100%{transform:translateY(0)}50%{transform:translateY(-2.5px)}}' +
    '.sona-svg .sv-eyes{transform-box:fill-box;transform-origin:center;animation:svHappy 9s ease-in-out infinite}' +
    '@keyframes svHappy{0%,58%,74%,100%{transform:scaleY(1)}62%,70%{transform:translateY(-1px) scaleY(.5)}}' +
    '.sona-svg .sv-eye{transform-box:fill-box;transform-origin:center;animation:svBlink 4.7s infinite}' +
    '@keyframes svBlink{0%,90%,100%{transform:scaleY(1)}93%{transform:scaleY(.08)}96%{transform:scaleY(1)}}' +
    '.sona-svg .sv-glow{animation:svGlow 2.6s ease-in-out infinite}@keyframes svGlow{50%{opacity:.35}}' +
    '.sona-svg .sv-smile{transition:opacity .15s}.sona-svg .sv-talk{opacity:0;transform-box:fill-box;transform-origin:center}' +
    '.sona-talk .sona-svg .sv-smile{opacity:0}.sona-talk .sona-svg .sv-talk{opacity:1;animation:svTalk .24s ease-in-out infinite alternate}' +
    '@keyframes svTalk{from{transform:scaleY(.25) scaleX(.9)}to{transform:scaleY(1.15) scaleX(1)}}' +
    '.sona-talk .sona-svg .sv-eyes{animation:svLook 1.6s ease-in-out infinite}' +
    '@keyframes svLook{0%,100%{transform:translateX(0)}30%{transform:translateX(-2.4px)}70%{transform:translateX(2.4px)}}' +
    '@media(prefers-reduced-motion:reduce){.sona-svg *{animation:none!important}}' +
    '.sn-m.bot{gap:8px;align-items:flex-end}.sn-mav{width:30px;height:30px;flex:none;margin-bottom:2px;filter:drop-shadow(0 3px 6px rgba(0,0,0,.4))}' +
    '.sn-ban .sn-banav{width:26px;height:26px;flex:none}' +
    'html.sona-open .sn-fab{display:none}@media(max-width:560px){html.sona-open,html.sona-open body{overflow:hidden}}' +
    '.sn-ad{position:relative;overflow:hidden;border-radius:18px;padding:18px;margin:14px 12px;color:#f3eadb;background:radial-gradient(120% 90% at 100% 0%,rgba(231,191,90,.28),transparent 60%),linear-gradient(160deg,#1c160c,#0f0c08);border:1px solid rgba(240,208,128,.3);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}' +
    '.sn-ad .sn-adk{display:inline-flex;align-items:center;gap:6px;font-size:10.5px;font-weight:800;letter-spacing:.12em;color:#1a1405;background:linear-gradient(135deg,#f6d77d,#d4a63c);border-radius:999px;padding:3px 9px}' +
    '.sn-ad h3{font:800 21px/1.25 Georgia,serif;margin:10px 0 4px;padding-right:84px;color:#fff3d6}.sn-ad p{margin:0 0 12px;font-size:13.5px;color:#cfc4ad;line-height:1.5}' +
    '.sn-ad .sn-adq{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:12px}.sn-ad .sn-adq button{border:1px solid rgba(240,208,128,.35);background:rgba(231,191,90,.1);color:#f0d080;border-radius:999px;padding:7px 12px;font-size:12.5px;font-weight:600;cursor:pointer}' +
    '.sn-ad .sn-adgo{border:0;border-radius:12px;padding:12px 18px;font-weight:800;font-size:14px;cursor:pointer;color:#1a1405;background:linear-gradient(135deg,#f6d77d,#d4a63c 55%,#b98a24);box-shadow:0 8px 22px rgba(212,166,60,.3)}' +
    '.sn-ad .sn-adav{position:absolute;right:10px;top:6px;width:84px;height:92px;font-size:0;color:transparent;filter:drop-shadow(0 8px 18px rgba(0,0,0,.45))}' +
    '@media(max-width:520px){.sn-fab{height:50px;padding:0 6px}.sn-fab .sn-lbl{display:none}}' +
    '.sn-panel{position:fixed;right:18px;bottom:18px;z-index:9500;width:410px;height:min(680px,calc(100vh - 36px));display:none;flex-direction:column;border-radius:24px;overflow:hidden;color:#f3eadb;font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:radial-gradient(130% 60% at 100% 0%,rgba(231,191,90,.16),transparent 60%),#120f0a;border:1px solid rgba(240,208,128,.22);box-shadow:0 30px 80px rgba(0,0,0,.6)}' +
    'html.sona-open .sn-panel{display:flex;animation:snIn .28s cubic-bezier(.2,.8,.3,1)}@keyframes snIn{from{opacity:0;transform:translateY(18px) scale(.98)}to{opacity:1;transform:none}}' +
    '@media(max-width:560px){.sn-panel{right:0;bottom:0;width:100%;height:100%;height:100dvh;border-radius:0;border:0}}' +
    '.sn-hd{display:flex;align-items:center;gap:11px;padding:14px 14px 12px 16px;border-bottom:1px solid rgba(240,208,128,.12)}' +
    '.sn-av{position:relative;width:48px;height:48px;flex:none;filter:drop-shadow(0 4px 10px rgba(0,0,0,.45))}' +
    '.sn-av:after{content:"";position:absolute;right:1px;bottom:3px;width:10px;height:10px;border-radius:50%;background:#2fd18b;border:2px solid #120f0a}' +
    '.sn-hd b{display:block;font-size:15.5px}.sn-hd span{font-size:11.5px;color:#a99f8b}.sn-x{margin-left:auto;width:34px;height:34px;border-radius:50%;border:0;background:rgba(255,255,255,.07);color:#f3eadb;font-size:18px;cursor:pointer}' +
    '.sn-body{flex:1;overflow-y:auto;padding:16px 14px 8px;scroll-behavior:smooth}' +
    '.sn-m{display:flex;margin:0 0 12px}.sn-m.me{justify-content:flex-end}' +
    '.sn-b[dir=rtl] .sn-v,.sn-b[dir=rtl] .sn-cmp b,.sn-b[dir=rtl] .sn-tiles span{direction:ltr;unicode-bidi:isolate}' +
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
    '.sn-hd .sn-ttl{flex:1;min-width:0}.sn-hd .sn-ttl span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sn-hd .sn-x{margin-left:0;flex:none}' +
    '.sn-lp{height:32px;flex:none;border-radius:999px;border:1px solid rgba(240,208,128,.35);background:rgba(231,191,90,.1);color:#f0d080;font:700 12.5px/1 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:0 11px;cursor:pointer;white-space:nowrap}' +
    '.sn-hb{width:34px;height:34px;flex:none;border-radius:50%;border:0;background:rgba(255,255,255,.07);color:#cfc4ad;cursor:pointer;display:flex;align-items:center;justify-content:center}.sn-hb svg{width:17px;height:17px}.sn-hb.on{background:rgba(231,191,90,.22);color:#f6d77d}' +
    '.sn-lm{display:none;position:absolute;left:12px;right:12px;top:72px;z-index:3;grid-template-columns:repeat(2,1fr);gap:6px;padding:10px;border-radius:16px;background:#1b160e;border:1px solid rgba(240,208,128,.25);box-shadow:0 18px 40px rgba(0,0,0,.55)}.sn-lm.on{display:grid}' +
    '.sn-lm button{border:1px solid rgba(240,208,128,.16);background:rgba(255,255,255,.04);color:#f3eadb;border-radius:10px;padding:10px 12px;text-align:left;font-size:14.5px;cursor:pointer}.sn-lm button.on{border-color:#e7bf5a;background:rgba(231,191,90,.15);color:#f6d77d}.sn-lm .sn-auto{grid-column:1/-1;font-weight:700}' +
    '.sn-lchips{display:flex;flex-wrap:wrap;gap:6px;margin:2px 0 4px}.sn-lchips button{border:1px solid rgba(240,208,128,.25);background:none;color:#f0d080;border-radius:999px;padding:4px 10px;font-size:12.5px;cursor:pointer}.sn-lchips button:hover{background:rgba(231,191,90,.12)}' +
    '.sn-mic{position:relative;width:46px;height:46px;flex:none;border-radius:50%;border:1px solid rgba(240,208,128,.4);background:rgba(231,191,90,.1);color:#f0d080;cursor:pointer;display:flex;align-items:center;justify-content:center}.sn-mic svg{width:21px;height:21px}' +
    '.sn-ml{position:absolute;right:-5px;bottom:-5px;min-width:17px;height:17px;padding:0 4px;border-radius:9px;background:#e7bf5a;color:#1a1405;font:700 10px/17px system-ui,sans-serif;text-align:center;pointer-events:none}' +
    '.sn-g{display:inline-block;padding:7px 14px;border-radius:999px;border:1px solid rgba(240,208,128,.45);color:#f0d080;text-decoration:none;font-weight:600}' +
    '.sn-mic.on{background:#e5484d;border-color:#e5484d;color:#fff;animation:snMic 1.2s infinite}@keyframes snMic{0%{box-shadow:0 0 0 0 rgba(229,72,77,.6)}70%{box-shadow:0 0 0 12px rgba(229,72,77,0)}100%{box-shadow:0 0 0 0 rgba(229,72,77,0)}}' +
    '.sn-orow .sn-nm b{display:block;font-size:13.5px}.sn-orow small{display:block;color:#cfc4ad;font-size:12px;line-height:1.45;margin-top:2px}' +
    '.sn-fb .sn-say{margin-left:auto}.sn-fab .sn-fmic{width:26px;height:26px;margin:0 -6px 0 -2px;border-radius:50%;background:rgba(26,20,5,.12);display:flex;align-items:center;justify-content:center}.sn-fab .sn-fmic svg{width:15px;height:15px}' +
    '@media(max-width:520px){.sn-fab .sn-fmic{display:none}}' +
    '.sn-ban .bx{position:absolute;right:8px;top:50%;transform:translateY(-50%);width:26px;height:26px;border:0;border-radius:50%;background:rgba(26,20,5,.12);color:#1a1405;cursor:pointer;font-size:14px}';

  var panel, body, chipBox, input, mic, spk, lmenu, voiceQ = false;
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition, rec = null, listening = false;
  var TTS = window.speechSynthesis, ttsOn = false;      // read every reply aloud; a spoken question is always answered aloud
  try { ttsOn = localStorage.getItem('sona_tts') === '1'; } catch (_) {}
  var ICON = {
    mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
    on: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg>',
    off: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>'
  };
  function short(c) { var l = (LG ? LG.LANGS : []).filter(function (x) { return x.c === c; })[0]; return l ? l.s : 'EN'; }
  function ui() {
    if (panel) return;
    panel = document.createElement('div'); panel.className = 'sn-panel'; panel.id = 'sonaPanel';
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Sona, the jewellery assistant');
    panel.innerHTML = '<div class="sn-hd"><div class="sn-av" id="sonaHeadAv">' + avatar() + '</div><div class="sn-ttl"><b>Sona</b><span id="sonaSub"></span></div>' +
      (LG ? '<button class="sn-lp" id="sonaLang" type="button" aria-haspopup="true"></button>' : '') +
      (TTS ? '<button class="sn-hb" id="sonaSpk" type="button"></button>' : '') +
      '<button class="sn-x" id="sonaClose" aria-label="Close">×</button></div>' +
      (LG ? '<div class="sn-lm" id="sonaLm" role="menu"><button type="button" role="menuitem" data-lang="auto" class="sn-auto"></button>' + LG.LANGS.map(function (l) { return '<button type="button" role="menuitem" data-lang="' + l.c + '">' + l.n + '</button>'; }).join('') + '</div>' : '') +
      '<div class="sn-body" aria-live="polite"></div><div class="sn-chips"></div>' +
      '<form class="sn-in"><input id="sonaInput" type="text" autocomplete="off" maxlength="200" aria-label="Your question">' +
      (SR ? '<button class="sn-mic" id="sonaMic" type="button">' + ICON.mic + '<span class="sn-ml" id="sonaMl"></span></button>' : '') +
      '<button class="sn-send" id="sonaSend" aria-label="Send">➤</button></form>' +
      '<div class="sn-foot" id="sonaFoot"></div>';
    document.body.appendChild(panel);
    body = $('.sn-body', panel); chipBox = $('.sn-chips', panel); input = $('#sonaInput', panel);
    mic = $('#sonaMic', panel); spk = $('#sonaSpk', panel); lmenu = $('#sonaLm', panel);
    $('#sonaClose', panel).onclick = close;
    $('form', panel).onsubmit = function (e) { e.preventDefault(); ask(input.value); };
    if (mic) mic.onclick = listen;
    if (spk) spk.onclick = function () {
      ttsOn = !ttsOn; try { localStorage.setItem('sona_tts', ttsOn ? '1' : '0'); } catch (_) {}
      if (!ttsOn) hush();
      labels(); track(ttsOn ? 'tts_on' : 'tts_off');
    };
    if (LG) $('#sonaLang', panel).onclick = function (e) { e.stopPropagation(); lmenu.classList.toggle('on'); };
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && opened) close(); });
    panel.addEventListener('click', function (e) {
      var lb = e.target.closest('[data-lang]');
      if (lb) { setLang(lb.getAttribute('data-lang')); return; }
      if (lmenu && !e.target.closest('#sonaLang')) lmenu.classList.remove('on');
      var c = e.target.closest('.sn-chip');
      if (c) {
        var cq = c.getAttribute('data-q') || c.textContent;
        if (cq === '#loc') locate();
        else if (cq === '#city') { home = null; try { localStorage.removeItem('sona_home'); } catch (_) {} ask(en('ch_mycity'), c.textContent); }
        else ask(cq, c.textContent);
        return;
      }
      var s = e.target.closest('[data-sn="subscribe"]');
      if (s) { close(); if (window.GR_OPEN_SUBPOP) window.GR_OPEN_SUBPOP(); else location.href = '/inquiry'; track('subscribe'); return; }
      var sy = e.target.closest('.sn-say');
      if (sy) { var m = sy.closest('.sn-m'); speak(m._say, m._sl, m); track('replay'); return; }
      var f = e.target.closest('.sn-fb button');
      if (f && !f.parentNode.getAttribute('data-done')) {
        f.classList.add('on'); f.parentNode.setAttribute('data-done', '1');
        var id = f.parentNode.getAttribute('data-id');
        if (id) rpc('bot_feedback', { p_id: +id, p_sid: window.GR_SID || '', p_helpful: f.getAttribute('data-v') === '1' });
      }
    });
    labels();
  }
  // Every fixed label in the chosen language.
  function labels() {
    RL = LANG;
    $('#sonaSub', panel).textContent = t('ui_sub');
    $('#sonaFoot', panel).textContent = t('ui_foot');
    if (!listening) input.placeholder = t('ui_ph');
    input.dir = rtl(LANG) ? 'rtl' : 'auto';
    // the language the mic listens in, on the mic (change it with the language menu)
    if (mic) { mic.setAttribute('aria-label', t('ui_mic') + ' (' + langName(micLang()) + ')'); mic.title = t('ui_mic') + ' - ' + langName(micLang());
      var ml = $('#sonaMl', panel); if (ml) ml.textContent = short(micLang()); }
    if (spk) { spk.innerHTML = ttsOn ? ICON.on : ICON.off; spk.classList.toggle('on', ttsOn); spk.setAttribute('aria-pressed', ttsOn ? 'true' : 'false'); spk.setAttribute('aria-label', t('ui_speak')); spk.title = ttsOn ? t('ui_mute') : t('ui_speak'); }
    if (LG) {
      var lp = $('#sonaLang', panel); lp.textContent = (PICK ? short(PICK) : 'Auto') + ' ▾';
      lp.setAttribute('aria-label', t('ui_lang') + ': ' + (PICK ? langName(PICK) : t('ui_auto')));
      $('.sn-auto', lmenu).textContent = t('ui_auto');
      [].forEach.call(lmenu.querySelectorAll('button'), function (b) { b.classList.toggle('on', b.getAttribute('data-lang') === (PICK || 'auto')); });
    }
  }
  function setLang(c) {
    if (c === 'auto') {
      PICK = ''; HEARD = '';
      try { localStorage.removeItem('sona_pick'); localStorage.removeItem('sona_heard'); } catch (_) {}
    } else if (STR[c]) {
      PICK = c; try { localStorage.setItem('sona_pick', c); } catch (_) {}
    } else return;
    LANG = uiLang();
    if (lmenu) lmenu.classList.remove('on');
    hush(); labels(); track('lang_' + c);
    // Only the welcome so far: say it again in the new language.
    var ms = body.querySelectorAll('.sn-m');
    if (ms.length === 1 && ms[0].getAttribute('data-greet')) { ms[0].remove(); greet(); }
    else setChips(suggest());
  }
  function greet() {
    RL = LANG;
    var m = bubble('<p>' + t('greet1') + '</p><p>' + t('greet2') + '</p>' + (LG ? '<p class="sn-dim">' + t('lang_hint') + '</p><div class="sn-lchips">' +
      LG.LANGS.map(function (l) { return '<button type="button" data-lang="' + l.c + '">' + l.n + '</button>'; }).join('') + '</div>' : ''));
    m.setAttribute('data-greet', '1');
    setChips(suggest());
  }
  function setChips(list) {
    chipBox.innerHTML = (list || []).map(function (c) {
      c = typeof c === 'string' ? { l: c, q: c } : c;
      return '<button class="sn-chip" type="button" dir="auto" data-q="' + esc(c.q) + '">' + esc(c.l) + '</button>';
    }).join('');
  }
  function bubble(html, me, talking) {
    var m = document.createElement('div'); m.className = 'sn-m' + (me ? ' me' : ' bot') + (talking ? ' sona-talk' : '');
    m.innerHTML = (me ? '' : '<div class="sn-mav">' + avatar() + '</div>') + '<div class="sn-b" dir="' + (me ? 'auto' : rtl(RL) ? 'rtl' : 'ltr') + '">' + html + '</div>';
    body.appendChild(m);
    body.scrollTop = body.scrollHeight; return m;
  }
  function note(text) { bubble('<p class="sn-dim">' + esc(text) + '</p>'); }
  // While Sona writes or reads out a reply she talks: in her message and in the header.
  function talking(on) { var h = panel && $('#sonaHeadAv', panel); if (h) h.classList.toggle('sona-talk', on); }

  // ------------------------------------------------- voice (the browser's own)
  function bcp(c) { var l = (LG ? LG.LANGS : []).filter(function (x) { return x.c === c; })[0]; return l ? l.bcp : 'en-IN'; }
  function voiceFor(c) {
    var vs = (TTS && TTS.getVoices()) || [], want = bcp(c).toLowerCase();
    var lg = function (v) { return String(v.lang || '').replace('_', '-').toLowerCase(); };
    return vs.filter(function (v) { return lg(v) === want; })[0] ||
      vs.filter(function (v) { return lg(v) === c || lg(v).indexOf(c + '-') === 0; })[0] || null;
  }
  var toldNoVoice = {};
  function speak(text, lang, m) {
    if (!TTS || !text) return;
    lang = lang || 'en';
    var go = function () {
      var v = voiceFor(lang);
      if (!v && lang !== 'en') {
        if (!toldNoVoice[lang]) { toldNoVoice[lang] = 1; RL = lang; note(t('no_voice', { l: langName(lang) })); }
        return;
      }
      try { TTS.cancel(); } catch (_) {}
      var u = new SpeechSynthesisUtterance(String(text).replace(/₹/g, ''));
      if (v) u.voice = v;
      u.lang = v ? v.lang : bcp(lang); u.rate = 1; u.pitch = 1.05;
      u.onstart = function () { talking(true); if (m) m.classList.add('sona-talk'); };
      u.onend = u.onerror = function () { talking(false); if (m) m.classList.remove('sona-talk'); };
      TTS.speak(u);
    };
    if ((TTS.getVoices() || []).length) go();
    else {                                     // voices load late on some browsers
      var done = false, once = function () { if (!done) { done = true; go(); } };
      try { TTS.addEventListener('voiceschanged', once); } catch (_) {}
      setTimeout(once, 1200);
    }
  }
  function hush() { if (TTS) try { TTS.cancel(); } catch (_) {} talking(false); }
  function setListening(on) {
    listening = on;
    if (mic) mic.classList.toggle('on', on);
    RL = LANG; input.placeholder = on ? t('ui_listen') : t('ui_ph');
  }
  // The language the mic is listening for (for the fallback below).
  var micUsed = '';
  function listen(fallback) {
    if (!SR) return;
    if (listening && !fallback) { try { rec.stop(); } catch (_) {} var r0 = rec; setTimeout(function () { if (rec === r0 && listening) { try { r0.abort(); } catch (_) {} if (r0.onend) r0.onend(); } }, 1200); return; }
    hush();
    micUsed = micLang();
    rec = new SR(); rec.lang = fallback || bcp(micUsed); rec.interimResults = true; rec.maxAlternatives = 1; rec.continuous = false;
    var heard = '', done = false, quiet = null, cap = null, me = rec;
    // iPhone Safari does not stop by itself when the visitor stops talking
    // (Android does): stop after a short silence, or if nothing is said, or
    // after a hard limit - and finish even if Safari never sends "end".
    function finish() {
      if (done) return; done = true;
      clearTimeout(quiet); clearTimeout(cap);
      if (rec === me) setListening(false);
      if (heard.trim()) { voiceQ = true; ask(heard); }
    }
    function stop(ms) {
      clearTimeout(quiet);
      quiet = setTimeout(function () {
        try { me.stop(); } catch (_) {}
        setTimeout(function () { try { me.abort(); } catch (_) {} finish(); }, 1200);
      }, ms);
    }
    rec.onresult = function (e) {
      var now = '', fin = false;
      for (var i = 0; i < e.results.length; i++) { now += e.results[i][0].transcript; fin = e.results[i].isFinal; }
      heard = now; input.value = now;
      stop(fin ? 400 : 1500);                     // 1.5 s of silence ends the question
    };
    rec.onerror = function (e) {
      RL = LANG;
      // no recogniser for this language on the phone: listen with Hindi's
      // (it knows Marathi and other Indian words best), reply in the chosen one
      if (e.error === 'language-not-supported' && !fallback && micUsed !== 'hi') {
        done = true; clearTimeout(quiet); clearTimeout(cap);
        var want = micUsed;
        setTimeout(function () { listen('hi-IN'); micUsed = want; }, 50);
        return;
      }
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') note(t('mic_denied'));
      else if (e.error === 'no-speech') note(t('mic_none'));
    };
    rec.onend = finish;
    try {
      rec.start(); setListening(true); track('voice');
      stop(8000);                                 // nothing said at all
      cap = setTimeout(function () { stop(0); }, 20000);
    } catch (_) { setListening(false); }
  }
  // FAQ answers are written in English; where the browser can translate on
  // the device (free, nothing sent anywhere), Sona answers in the reply
  // language, otherwise in English with a note.
  function translateTo(text, lang) {
    try {
      if (!('Translator' in window)) return Promise.resolve(null);
      var o = { sourceLanguage: 'en', targetLanguage: lang };
      var go = window.Translator.availability(o).then(function (a) {
        return a === 'unavailable' ? null : window.Translator.create(o).then(function (tr) { return tr.translate(text); });
      }).catch(function () { return null; });
      return Promise.race([go, new Promise(function (r) { setTimeout(function () { r(null); }, 4000); })]);
    } catch (_) { return Promise.resolve(null); }
  }

  function ask(q, label) {
    q = String(q || '').trim(); if (!q) return;
    var spoken = voiceQ; voiceQ = false;
    hush();
    input.value = ''; bubble(esc(label || q), true); setChips([]);
    var typing = bubble('<span class="sn-typing"><span></span><span></span><span></span></span>', false, true);
    talking(true);
    loadKB().then(function () {
      var a = null;
      try { a = reply(q, !!label, spoken).a; } catch (e) { a = null; }
      var ok = !!a, rl = RL;
      if (!a) a = { intent: 'unknown', html: '<p>' + t('unknown') + '</p>' + gLink(q), say: t('unknown'), chips: suggest() };
      var tr = a.en && rl !== 'en' ? translateTo(a.en, rl) : Promise.resolve(null);
      tr.then(function (txt) {
        RL = rl;
        if (a.en && rl !== 'en') {
          if (txt) { a.html = '<p>' + esc(txt) + '</p>' + a.html.replace(/^<p>[\s\S]*?<\/p>/, '') + '<div class="sn-src">' + t('translated') + '</div>'; a.say = txt; }
          else { a.html = '<p class="sn-dim">' + t('en_only') + '</p>' + a.html; a.sayLang = 'en'; }
        }
        setTimeout(function () {
          typing.remove(); talking(false);
          var m = bubble(a.html + '<div class="sn-fb"><button type="button" data-v="1" aria-label="Helpful">👍</button><button type="button" data-v="0" aria-label="Not helpful">👎</button>' +
            (TTS && a.say ? '<button type="button" class="sn-say" aria-label="' + esc(t('ui_speak')) + '">🔊</button>' : '') + '</div>');
          m._say = a.say; m._sl = a.sayLang || rl;
          setChips(a.chips || suggest());
          var tag = (rl !== 'en' ? rl : '') + (spoken ? (rl !== 'en' ? ' ' : '') + 'voice' : '');
          rpc('log_bot_question', { p_q: (tag ? '[' + tag + '] ' : '') + redact(q), p_intent: a.intent, p_answered: ok, p_page: location.pathname, p_sid: window.GR_SID || '' })
            .then(function (id) { if (id) $('.sn-fb', m).setAttribute('data-id', id); });
          track(ok ? 'answered' : 'unanswered');
          if (spoken || ttsOn) speak(a.say, m._sl, m);
        }, 350 + Math.min(600, a.html.length / 6));
      });
    }).catch(function () { typing.remove(); talking(false); RL = LANG; bubble('<p>' + t('nodata') + '</p>'); });
  }
  // "Use my location": the browser asks the visitor first; the position is
  // only compared with the city centres here and is never sent anywhere.
  function locate() {
    RL = LANG; setChips([]);
    var wait = bubble('<p class="sn-dim">' + t('loc_wait') + '</p>');
    var fail = function () {
      wait.remove(); RL = LANG;
      loadKB().then(function () { var a = askCity('loc_fail'); bubble(a.html); setChips(a.chips); });
    };
    try {
      navigator.geolocation.getCurrentPosition(function (p) {
        loadKB().then(function () {
          var c = nearest(p.coords.latitude, p.coords.longitude);
          if (!c) return fail();
          wait.remove(); setHome(c); ask(c.n, '📍 ' + c.n);
        }).catch(fail);
      }, fail, { timeout: 10000, maximumAge: 600000 });
    } catch (_) { fail(); }
  }
  function open(q) {
    ui();
    if (!opened) {
      opened = true; document.documentElement.classList.add('sona-open');
      if (!body.childNodes.length) greet();
      track('open'); loadKB();
      if (window.innerWidth > 560) setTimeout(function () { try { input.focus(); } catch (_) {} }, 200);
    }
    if (q) ask(q);
  }
  function close() {
    opened = false; document.documentElement.classList.remove('sona-open');
    hush(); if (listening && rec) try { rec.stop(); } catch (_) {}
  }
  window.GR_ASK = open;

  if (TEST) {                                   // tests drive the engine without a page
    window.__SONA_TEST = {
      setKB: function (d) { KB = d; prep(d); },
      setLang: function (c) { PICK = c === 'auto' ? '' : c; HEARD = ''; LANG = uiLang(); RL = LANG; },
      micLang: function () { return micLang(); },
      nearest: function (la, lo) { return nearest(la, lo); },
      ask: function (q, chip, spoken) { if (spoken) micUsed = micLang(); var r = reply(q, chip, spoken); return { text: r.tx, lang: RL, a: r.a }; }
    };
    return;
  }

  // ---------------------------------------------------- launcher & banner
  function mount() {
    if (document.querySelector('.bnav')) document.documentElement.classList.add('sona-bnav');
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    var fab = document.createElement('button');
    fab.className = 'sn-fab'; fab.id = 'sonaFab'; fab.type = 'button'; fab.setAttribute('aria-label', 'Ask Sona, the jewellery assistant');
    fab.innerHTML = '<span class="sn-orb">' + avatar() + '</span><span class="sn-lbl">Ask Sona</span>' + (SR ? '<span class="sn-fmic">' + ICON.mic + '</span>' : '') + '<span class="sn-ping"></span>';
    fab.onclick = function () { open(); };
    document.body.appendChild(fab);
    var seen = null; try { seen = localStorage.getItem('sona_ban2'); } catch (_) {}
    if (!seen) {
      var b = document.createElement('div'); b.className = 'sn-ban'; b.id = 'sonaBanner';
      b.innerHTML = '<span class="sn-banav">' + avatar() + '</span><span class="nw">NEW</span><span>Now <b>talk to Sona</b> about gold rates — in English, हिन्दी, اردو, मराठी, ગુજરાતી, தமிழ், తెలుగు, ಕನ್ನಡ, മലയാളം, বাংলা, ਪੰਜਾਬੀ, ଓଡ଼ିଆ or অসমীয়া. <u>Try it</u></span><button class="bx" type="button" aria-label="Dismiss">×</button>';
      b.onclick = function (e) {
        if (e.target.closest('.bx')) { b.remove(); try { localStorage.setItem('sona_ban2', '1'); } catch (_) {} return; }
        open(); track('banner');
      };
      document.body.insertBefore(b, document.body.firstChild);
    }
    if (/[?&]ask=1\b/.test(location.search) || location.hash === '#ask') setTimeout(function () { open(); }, 400);
    // Feature cards carry an empty .sn-adav: Sona herself goes there.
    [].forEach.call(document.querySelectorAll('.sn-adav'), function (el) { el.innerHTML = avatar(true); });
    // Feature cards on the pages: <button data-ask="question"> opens Sona with it.
    document.addEventListener('click', function (e) {
      var el = e.target.closest && e.target.closest('[data-ask]');
      if (!el) return;
      e.preventDefault(); track('card'); open(el.getAttribute('data-ask') || '');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
