#!/usr/bin/env python3
"""Diamond jewellery data - the foundation for comparing jewellers on
diamonds, not just gold (owner, 21 Nov 2026).

Diamonds are NOT a commodity like 24K gold: two "1 carat" rings can honestly
cost 3-4x apart because the stones differ (the 4Cs, natural vs lab-grown,
certification). So we never compare raw diamond prices. Instead we extract
each product's specs and its price breakup, then compare jewellers on a
LIKE-FOR-LIKE basis: price per carat within a quality band, natural vs
lab-grown, certifier, and the diamond-value / gold-value / making split.

Indian jeweller product pages publish this in structured form. Candere
(Kalyan's online brand) carries the cleanest breakup - stone_price,
metal_price, making_charge, total_stone_weight (carat), clarity, colour and
whether the stone is lab-grown or natural - so it is the first reader here;
BlueStone and CaratLane follow with their own extractors.

    python diamonds.py probe        # scrape a small live sample, print the
                                    # price-per-carat spread (changes nothing)
    python diamonds.py collect      # full run -> Supabase table `diamonds`

Read-only probe needs no secrets; collect needs SUPABASE_URL + _SERVICE_KEY.
"""
import json
import os
import re
import sys
import html as _html
from statistics import median

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# Quality bands - how we group stones so a comparison is like-for-like.
def carat_band(ct):
    if ct is None:
        return "?"
    for lo, hi, name in ((0, 0.3, "<0.3ct"), (0.3, 0.5, "0.3-0.5ct"),
                         (0.5, 1.0, "0.5-1ct"), (1.0, 2.0, "1-2ct")):
        if lo <= ct < hi:
            return name
    return "2ct+"


CLARITY_ORDER = ["FL", "IF", "VVS1", "VVS2", "VVS", "VS1", "VS2", "VS",
                 "SI1", "SI2", "SI", "I1", "I2", "I3", "I"]
COLOR_ORDER = ["D", "E", "F", "G", "H", "I", "J", "K"]


def _num(s):
    try:
        return float(str(s).replace(",", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return None


def fetch(url):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
        return r.text if r.status_code < 400 else ""
    except requests.RequestException:
        return ""


def _field(h, key):
    m = re.search(rf'"{key}"\s*:\s*"?([0-9][0-9,]*\.?[0-9]*)"?', h)
    return _num(m.group(1)) if m else None


def _str(h, key):
    m = re.search(rf'"{key}"\s*:\s*"([^"]{{1,24}})"', h)
    return m.group(1).strip() if m else None


def extract_candere(url, html_raw):
    """Candere exposes a full price breakup + specs in page JSON."""
    h = _html.unescape(html_raw)
    stone = _field(h, "stone_price") or _field(h, "gemstone_price")
    metal = _field(h, "metal_price")
    making = _field(h, "making_charge")
    total = _field(h, "final_price") or _field(h, "special_price") or _field(h, "price")
    carat = _field(h, "total_stone_weight")        # total diamond weight, carats
    n_dia = _field(h, "no_of_diamonds") or _field(h, "total_stone_numbers")
    # Candere packs stone clarity + colour into one field, e.g. "SI IJ"
    # (clarity SI, colour range I-J). Split it; the separate "color" field is
    # usually the METAL colour (Yellow/White/Rose), not the stone.
    clarity = _str(h, "clarity")
    color = None
    if clarity:
        toks = clarity.upper().replace(",", " ").split()
        cl = [t for t in toks if t.rstrip("123") in {"FL", "IF", "VVS", "VS", "SI", "I"}]
        co = [t for t in toks if re.fullmatch(r"[D-K]{1,2}", t)]
        clarity = cl[0] if cl else (toks[0] if toks else None)
        color = co[0] if co else None
    if not color:
        mc = _str(h, "color")
        if mc and mc.upper() and re.fullmatch(r"[D-K]{1,2}", mc.upper()):
            color = mc.upper()
    lab = bool(re.search(r"lab[\s-]?grown", h, re.I))
    cert = next((c for c in ("IGI", "GIA", "SGL", "BIS") if re.search(rf"\b{c}\b", h)), None)
    if not (carat and (stone or total)):
        return None
    return {
        "brand": "Candere", "url": url,
        "carat": carat, "n_diamonds": int(n_dia) if n_dia else None,
        "clarity": clarity or None,
        "color": color or None,
        "type": "lab-grown" if lab else "natural",
        "cert": cert,
        "diamond_price": stone, "metal_value": metal, "making": making, "total": total,
        "band": carat_band(carat),
        "per_carat": round(stone / carat) if (stone and carat) else None,
    }


def extract_caratlane(url, html_raw):
    """CaratLane geo-redirects non-India IPs to its US site, so these pages
    are fetched through the India proxy (render=true, country=in) - the
    rendered India PDP then shows INR and the 4Cs. Extraction is defensive
    (JSON-LD price + labelled specs in the rendered text) because the markup
    varies by template."""
    h = _html.unescape(html_raw)
    # India only. The proxy sometimes still serves the US site (USD); mixing
    # currencies would corrupt the comparison, so keep a row ONLY when the
    # page is unambiguously the India experience (INR) and never the US one.
    cur = (re.search(r'"priceCurrency"\s*:\s*"([A-Z]{3})"', h) or ["", ""])[1]
    is_in = ("₹" in h or cur == "INR" or "en_IN" in h or "caratlane.com/jewellery" in h and "USD" not in h)
    is_us = ("caratlane us" in h.lower() or "/en_us" in h.lower() or cur == "USD" or "$" in h[:20000])
    if is_us or not is_in:
        return None
    def g(pat):
        m = re.search(pat, h, re.I)
        return m.group(1).strip() if m else None
    carat = _num(g(r'([\d.]+)\s*(?:ct|carat)\b'))
    total = _num(g(r'"price"\s*:\s*"?([0-9][0-9,]*\.?\d*)') or g(r'₹\s?([\d,]{4,})'))
    clarity = g(r'Clarity[\s:<>/"]{1,8}([A-Z]{1,3}\d?(?:[-/][A-Z]{1,3}\d?)?)')
    color = g(r'Colou?r[\s:<>/"]{1,8}([D-K]{1,2}(?:[-/][D-K]{1,2})?)')
    lab = bool(re.search(r"lab[\s-]?grown", h, re.I))
    cert = next((c for c in ("IGI", "GIA", "SGL") if re.search(rf"\b{c}\b", h)), None)
    stone = _num(g(r'"(?:diamondPrice|stonePrice|diamondValue)"\s*:\s*"?([0-9][0-9,]*\.?\d*)'))
    metal = _num(g(r'"(?:metalValue|goldValue|metalPrice)"\s*:\s*"?([0-9][0-9,]*\.?\d*)'))
    if not (carat and (stone or total)):
        return None
    pc = round(stone / carat) if (stone and carat) else None
    return {
        "brand": "CaratLane", "url": url, "carat": carat, "n_diamonds": None,
        "clarity": (clarity or "").upper() or None, "color": (color or "").upper() or None,
        "type": "lab-grown" if lab else "natural", "cert": cert,
        "diamond_price": stone, "metal_value": metal, "making": None, "total": total,
        "band": carat_band(carat), "per_carat": pc,
    }


def extract_senco(url, html_raw):
    """Senco publishes a full price breakup in page JSON - diamond_value_inr,
    diamond_weight (carat), gold_value, making_charge_value - and the total in
    JSON-LD (INR). Direct fetch, no proxy. Clarity/colour are not exposed
    per-stone, so they stay null; carat + diamond value still give a clean
    price-per-carat."""
    h = _html.unescape(html_raw)

    def g(pat):
        m = re.search(pat, h, re.I)
        return _num(m.group(1)) if m else None
    carat = g(r'"diamond_weight"\s*:\s*"?([0-9][0-9.,]*)')
    stone = g(r'"diamond_value_inr"\s*:\s*"?([0-9][0-9.,]*)') or g(r'"diamond_value"\s*:\s*"?([0-9][0-9.,]*)')
    metal = g(r'"gold_value"\s*:\s*"?([0-9][0-9.,]*)')
    making = g(r'"making_charge_value"\s*:\s*"?([0-9][0-9.,]*)')
    total = g(r'"price"\s*:\s*"?([0-9][0-9.,]*)')
    if not (carat and carat > 0 and stone and stone > 0):   # a real diamond piece, not plain gold
        return None
    lab = bool(re.search(r"lab[\s-]?grown", h, re.I))
    return {
        "brand": "Senco Gold", "url": url, "carat": carat, "n_diamonds": None,
        "clarity": None, "color": None,
        "type": "lab-grown" if lab else "natural", "cert": None,
        "diamond_price": stone, "metal_value": metal, "making": making, "total": total,
        "band": carat_band(carat), "per_carat": round(stone / carat),
    }


def _parse_4c(*opts):
    """From a jeweller's variant option like 'GH-SI' or 'EF VVS' pull the
    diamond colour (D-K range) and clarity (FL/IF/VVS/VS/SI/I). Returns
    (color, clarity), either may be None."""
    color = clarity = None
    for opt in opts:
        if not opt:
            continue
        for tok in re.split(r"[-/ ]+", str(opt).upper()):
            if not color and re.fullmatch(r"[D-K]{1,2}", tok):
                color = tok
            elif not clarity and re.fullmatch(r"(FL|IF|VVS[12]?|VS[12]?|SI[12]?|I[123]?)", tok):
                clarity = tok
    return color, clarity


def extract_png(url, html_raw):
    """PN Gadgil (pngjewellers.com, Shopify) publishes a full breakup DIRECT -
    no proxy. A per-variant object carries metal_price, diamond_stone (the
    diamond value) and making_charges; a `data` map carries dia_weight_N (the
    diamond carat per stone group) so the total diamond weight is their sum;
    and the variant option (e.g. 'GH-SI') carries colour + clarity. That makes
    PNG the most complete direct source - carat, the 4Cs AND the value split."""
    h = _html.unescape(html_raw)
    # First variant's value breakup (the object is keyed by variant id).
    # PNG's keys are UNQUOTED JS (metal_price: 12871.0), so match either form.
    def jf(key):
        m = re.search(rf'"?{key}"?\s*:\s*"?([0-9][0-9,]*\.?[0-9]*)', h)
        return _num(m.group(1)) if m else None
    metal = jf("metal_price")
    stone = jf("diamond_stone")
    making = jf("making_charges")
    # Total: the breakup `price` is in paise (e.g. 2723800 -> 27238.00).
    pm = re.search(r'"?price"?\s*:\s*([0-9]{4,})', h)
    total = round(int(pm.group(1)) / 100) if pm else None
    # Total diamond carat = sum of the diamond-group weights. The page repeats
    # the same dia_weight_N block once per variant, so take each group index
    # (_1, _2, _3...) ONCE - its FIRST occurrence - then sum the distinct ones.
    groups = {}
    for m in re.finditer(r'dia_weight_([0-9]+)["\':\s]+([0-9]*\.?[0-9]+)', h):
        idx = m.group(1)
        if idx not in groups:
            groups[idx] = _num(m.group(2)) or 0.0
    carat = round(sum(groups.values()), 3) or None
    # Colour + clarity from any variant option value.
    color = clarity = None
    for m in re.finditer(r'"option[123]"\s*:\s*"([^"]{1,16})"', h):
        c, cl = _parse_4c(m.group(1))
        color = color or c
        clarity = clarity or cl
        if color and clarity:
            break
    lab = bool(re.search(r"lab[\s-]?grown", h, re.I))
    cert = next((c for c in ("IGI", "GIA", "SGL") if re.search(rf"\b{c}\b", h)), None)
    if not (carat and stone and stone > 0):     # a real diamond piece
        return None
    return {
        "brand": "PN Gadgil", "url": url, "carat": carat, "n_diamonds": None,
        "clarity": clarity, "color": color,
        "type": "lab-grown" if lab else "natural", "cert": cert,
        "diamond_price": stone, "metal_value": metal, "making": making, "total": total,
        "band": carat_band(carat), "per_carat": round(stone / carat),
    }


BRANDS = {
    # Candere (static, India data, full breakup) - the reference source.
    "Candere": {
        "extract": extract_candere, "mode": "direct",
        "prod_re": r'href="(https://www\.candere\.com/[a-z0-9][a-z0-9-]*(?:ring|pendant|earring|bracelet|necklace|mangalsutra)[a-z0-9-]*\.html)"',
        "listings": {
            "diamond ring": ["https://www.candere.com/catalogsearch/result/?q=diamond+ring",
                             "https://www.candere.com/catalogsearch/result/?q=solitaire+ring"],
            "pendant": ["https://www.candere.com/catalogsearch/result/?q=diamond+pendant"],
            "earring": ["https://www.candere.com/catalogsearch/result/?q=diamond+earring"],
            "bracelet": ["https://www.candere.com/catalogsearch/result/?q=diamond+bracelet"],
        },
    },
    # Senco Gold (static, India, full breakup) - a second DIRECT source, no
    # proxy. Discover diamond products from its product sitemap.
    "Senco Gold": {
        "extract": extract_senco, "mode": "direct",
        "sitemap": "https://sencogoldanddiamonds.com/sitemap-product.xml",
        "slug_re": r"(diamond|solitaire)",
    },
    # PN Gadgil (pngjewellers.com, Shopify) - a third DIRECT source and the
    # most complete: carat, colour + clarity AND the value split, no proxy.
    # Its top sitemap is an INDEX pointing to sitemap_products_N.xml children.
    "PN Gadgil": {
        "extract": extract_png, "mode": "direct",
        "sitemap": "https://www.pngjewellers.com/sitemap.xml",
        "sitemap_index": True, "child_re": r"product",
        "slug_re": r"diamond|solitaire",
    },
    # CaratLane: discover from the product sitemap (works from any IP), fetch
    # each PDP through the India proxy, extract. Market leader - but needs a
    # working India-geo proxy (see proxy_fetch), so it yields only when one is
    # funded; the direct sources above never depend on that.
    "CaratLane": {
        "extract": extract_caratlane, "mode": "proxy", "geo": "IN",
        "sitemap": "https://www.caratlane.com/caratlane-sitemap/product-sitemap.xml",
        "slug_re": r"(diamond-ring|solitaire|diamond-pendant|diamond-earring|diamond-bracelet)",
    },
}


ZYTE_ENDPOINT = "https://api.zyte.com/v1/extract"


def zyte_fetch(url, geo="IN"):
    """Zyte browser render pinned to a country (geolocation), so a
    geo-redirecting site serves that country's page - CaratLane in INR with
    geo='IN'. Self-contained (ZYTE_API_KEY), returns '' without a key."""
    global _ZYTE_DIAG
    key = os.environ.get("ZYTE_API_KEY")
    if not key:
        if not _ZYTE_DIAG:
            print("  zyte: no ZYTE_API_KEY in env"); _ZYTE_DIAG = True
        return ""
    try:
        r = requests.post(ZYTE_ENDPOINT, json={"url": url, "browserHtml": True, "geolocation": geo},
                          auth=(key, ""), timeout=90)
        if r.status_code == 200:
            return r.json().get("browserHtml") or ""
        if not _ZYTE_DIAG:
            print(f"  zyte: HTTP {r.status_code} {str(r.text)[:140]}"); _ZYTE_DIAG = True
    except requests.RequestException as e:
        if not _ZYTE_DIAG:
            print(f"  zyte: {type(e).__name__}: {str(e)[:80]}"); _ZYTE_DIAG = True
    return ""


_ZYTE_DIAG = False


def _looks_india(h):
    """A fetched page is the India experience (INR), not the US one. CaratLane
    geo-redirects, and we must keep only the India page or prices would be in
    USD. Cheap signals, no parsing."""
    if not h or len(h) < 1000:
        return False
    low = h.lower()
    if "caratlane us" in low or "/en_us" in low or '"pricecurrency":"usd"' in low:
        return False
    return ("₹" in h or "en_IN" in h or '"priceCurrency":"INR"' in h
            or ("INR" in h and "USD" not in h[:20000]))


def india_fetch(url):
    """Fetch a geo-redirecting page as INDIA, trying EVERY proxy we have with
    its own India-geotargeting parameter and keeping the first response that
    is actually the India (INR) page. The gold waterfall returns the first
    200 of any geo (so CaratLane came back as the US site); this validates
    the country and falls through to the next provider otherwise. Does not
    depend on any single provider (e.g. Zyte being up)."""
    env = os.environ.get
    # (name, endpoint, params, success_status) - each with India geotargeting.
    attempts = [
        ("scraperapi", "http://api.scraperapi.com",
         {"api_key": env("SCRAPERAPI_KEY"), "url": url, "render": "true",
          "country_code": "in", "premium": "true"}),               # premium = residential India IPs
        ("scrapingbee", "https://app.scrapingbee.com/api/v1/",
         {"api_key": env("SCRAPINGBEE_KEY"), "url": url, "render_js": "true", "country_code": "in"}),
        ("zenrows", "https://api.zenrows.com/v1/",
         {"apikey": env("ZENROWS_KEY"), "url": url, "js_render": "true", "proxy_country": "in"}),
        ("crawlbase", "https://api.crawlbase.com/",
         {"token": env("CRAWLBASE_KEY"), "url": url, "country": "IN"}),
    ]
    global _PROXY_DIAG
    diag = not _PROXY_DIAG
    for name, ep, params in attempts:
        if not (params.get("api_key") or params.get("apikey") or params.get("token")):
            if diag:
                print(f"  india proxy: {name} - no key")
            continue
        try:
            r = requests.get(ep, params=params, timeout=70)
            india = _looks_india(r.text)
            if diag:
                low = r.text.lower()
                tag = ("US" if ("caratlane us" in low or "/en_us" in low) else
                       "INR" if india else "?")
                print(f"  india proxy: {name} HTTP {r.status_code} {len(r.text)}b looks={tag}")
            if r.status_code == 200 and india:
                _PROXY_DIAG = True
                return r.text
        except requests.RequestException as e:
            if diag:
                print(f"  india proxy: {name} {type(e).__name__}")
    # Zyte with India geolocation, last (paid; may be suspended).
    h = zyte_fetch(url, "IN")
    if _looks_india(h):
        if not _PROXY_DIAG:
            print("  india proxy: zyte served the India page"); _PROXY_DIAG = True
        return h
    return ""


_PROXY_DIAG = False


def proxy_fetch(url, geo=None):
    """India-geo fetch for a geo-redirecting site (CaratLane): the full
    multi-proxy India waterfall, not one provider."""
    return india_fetch(url)


def discover(b, limit=60):
    cfg = BRANDS[b]
    urls = []
    if cfg.get("sitemap"):
        # A sitemap index points to child sitemaps (PNG); a plain sitemap
        # lists product URLs directly (Senco, CaratLane). For an index, walk
        # the product-bearing children and collect product URLs from each.
        sitemaps = [cfg["sitemap"]]
        if cfg.get("sitemap_index"):
            idx = _html.unescape(fetch(cfg["sitemap"]))
            child_re = cfg.get("child_re", r"product")
            sitemaps = [m.group(1) for m in re.finditer(r"<loc>([^<]+)</loc>", idx)
                        if re.search(child_re, m.group(1), re.I)] or sitemaps
        for sm in sitemaps:
            xml = _html.unescape(fetch(sm))
            for m in re.finditer(r"<loc>([^<]+)</loc>", xml):
                u = m.group(1)
                if re.search(cfg["slug_re"], u, re.I) and u not in urls:
                    urls.append(u)
                if len(urls) >= limit:
                    return urls
        return urls
    for group in cfg["listings"].values():
        for lu in group:
            for m in re.finditer(cfg["prod_re"], fetch(lu)):
                u = m.group(1)
                if u not in urls:
                    urls.append(u)
    return urls


def grab(b, url):
    html_ = proxy_fetch(url, BRANDS[b].get("geo")) if BRANDS[b].get("mode") == "proxy" else fetch(url)
    return BRANDS[b]["extract"](url, html_) if html_ else None


def probe(limit=24):
    rows = []
    for b in BRANDS:
        urls = discover(b)[:limit]
        print(f"{b}: {len(urls)} diamond products discovered")
        for u in urls:
            r = grab(b, u)
            if r:
                rows.append(r)
    print(f"\nextracted {len(rows)} products with specs + price breakup\n")
    # Price per carat of the DIAMOND only, by type and band - the honest,
    # like-for-like comparison.
    by = {}
    for r in rows:
        if r["per_carat"]:
            by.setdefault((r["type"], r["band"]), []).append(r["per_carat"])
    print(f"{'type':<10} {'band':<12} {'n':>3}  price/carat (diamond only): low - median - high")
    for (t, band), v in sorted(by.items()):
        v.sort()
        print(f"{t:<10} {band:<12} {len(v):>3}  ₹{v[0]:,} - ₹{round(median(v)):,} - ₹{v[-1]:,}")
    # A few example rows so the specs are visible
    print("\nsample products:")
    for r in rows[:8]:
        dp = f"{round(r['diamond_price']):,}" if r['diamond_price'] else "?"
        tp = f"{round(r['total']):,}" if r['total'] else "?"
        pc = f"{r['per_carat']:,}" if r['per_carat'] else "?"
        print(f"  {r['brand']}  {r['carat']}ct {r['color'] or '?'}/{r['clarity'] or '?'} {r['type']} "
              f"{r['cert'] or '?'}  diamond ₹{dp}  total ₹{tp}  per-carat ₹{pc}")
    return rows


def aggregate(rows):
    """Quality-normalised, like-for-like summary for the customer page.

    Price per carat of the DIAMOND alone, grouped by natural/lab and carat
    band (and, where we have enough, clarity). Also a per-jeweller profile.
    Never a raw "cheapest diamond" number - that would compare different
    stones and mislead.
    """
    from collections import defaultdict
    band = defaultdict(list)       # (type, band) -> [per_carat]
    byclar = defaultdict(list)     # (type, clarity) -> [per_carat]
    jeweller = defaultdict(lambda: {"n": 0, "types": set(), "certs": set(), "per_carat": []})
    for r in rows:
        if not r.get("per_carat"):
            continue
        band[(r["type"], r["band"])].append(r["per_carat"])
        if r.get("clarity"):
            byclar[(r["type"], r["clarity"])].append(r["per_carat"])
        j = jeweller[r["brand"]]
        j["n"] += 1
        j["types"].add(r["type"])
        if r.get("cert"):
            j["certs"].add(r["cert"])
        j["per_carat"].append(r["per_carat"])

    def band_stat(d):
        return {f"{t}|{b}": {"n": len(v), "low": min(v), "median": round(median(v)), "high": max(v)}
                for (t, b), v in d.items() if len(v) >= 2}
    return {
        "by_band": band_stat(band),
        "by_clarity": band_stat(byclar),
        "jewellers": {b: {"n": j["n"], "types": sorted(j["types"]), "certs": sorted(j["certs"]),
                          "median_per_carat": round(median(j["per_carat"])) if j["per_carat"] else None}
                      for b, j in jeweller.items()},
        "updated": __import__("datetime").datetime.now(
            __import__("datetime").timezone(__import__("datetime").timedelta(hours=5, minutes=30))
        ).strftime("%d %b %Y"),
    }


def collect(limit=120):
    import private_store
    rows = []
    for b in BRANDS:
        # Proxy brands (Zyte renders) cost money per fetch, so cap them;
        # direct brands (Candere) are free, so sample widely.
        cap = BRANDS[b].get("sample", 25) if BRANDS[b].get("mode") == "proxy" else limit
        urls = discover(b)[:cap]
        got = 0
        for i, u in enumerate(urls):
            html_ = proxy_fetch(u, BRANDS[b].get("geo")) if BRANDS[b].get("mode") == "proxy" else fetch(u)
            if BRANDS[b].get("mode") == "proxy" and i == 0:
                tag = ("US-page" if "caratlane us" in html_.lower() or "/en_us" in html_.lower()
                       else ("india" if "₹" in html_ or "en_IN" in html_ else "unknown"))
                print(f"  {b}: proxy sample {len(html_)} bytes, looks={tag}, "
                      f"carat?={'ct' in html_.lower()} clarity?={'clarity' in html_.lower()}")
            r = BRANDS[b]["extract"](u, html_) if html_ else None
            if r:
                rows.append(r); got += 1
        print(f"  {b}: {len(urls)} discovered, {got} extracted")
    print(f"collected {len(rows)} diamond products across {len(BRANDS)} jeweller(s)")
    # Raw rows to the `diamonds` table (run sql/diamonds.sql once first), and
    # the summary the page reads to collector_cache.
    try:
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
        day = __import__("datetime").date.today().isoformat()
        sb.table("diamonds").delete().eq("captured_on", day).execute()
        for i in range(0, len(rows), 200):
            sb.table("diamonds").insert([
                {"captured_on": day, "brand": r["brand"], "url": r["url"], "carat": r["carat"],
                 "band": r["band"], "clarity": r.get("clarity"), "color": r.get("color"),
                 "type": r["type"], "cert": r.get("cert"), "diamond_price": r.get("diamond_price"),
                 "metal_value": r.get("metal_value"), "making": r.get("making"), "total": r.get("total"),
                 "per_carat": r.get("per_carat")}
                for r in rows[i:i + 200]], returning="minimal").execute()
        print(f"  stored {len(rows)} rows in `diamonds`")
    except Exception as e:
        print(f"  DB store skipped/failed: {type(e).__name__}: {str(e)[:120]}")
    summary = aggregate(rows)
    try:
        private_store.cache_put("diamonds_summary", summary)
        print("  summary cached for the site (diamonds_summary)")
    except Exception as e:
        print(f"  summary cache failed: {type(e).__name__}")
    print(json.dumps(summary, indent=1, default=list)[:1200])
    return rows


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "collect":
        collect()
    else:
        probe()
    return 0


if __name__ == "__main__":
    sys.exit(main())
