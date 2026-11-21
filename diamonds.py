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
    if "caratlane us" in h.lower() or "$" in (re.search(r'("priceCurrency"\s*:\s*"[^"]+")', h) or [""])[0].lower():
        return None                                     # still the US page - skip
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
    # CaratLane: discover from the product sitemap (works from any IP), fetch
    # each PDP through the India proxy, extract. Market leader.
    "CaratLane": {
        "extract": extract_caratlane, "mode": "proxy",
        "sitemap": "https://www.caratlane.com/caratlane-sitemap/product-sitemap.xml",
        "slug_re": r"(diamond-ring|solitaire|diamond-pendant|diamond-earring|diamond-bracelet)",
    },
}


def proxy_fetch(url):
    """Fetch through the gold scraper's India proxy waterfall (render=true,
    country=in). Needs a proxy key in the environment; returns '' without one."""
    try:
        import collect
        s = requests.Session()
        s.headers.update({"User-Agent": UA})
        html_, _ = collect.fetch_via_proxy_waterfall(url, s)
        return html_ or ""
    except Exception:
        return ""


def discover(b, limit=60):
    cfg = BRANDS[b]
    urls = []
    if cfg.get("sitemap"):
        xml = fetch(cfg["sitemap"])
        for m in re.finditer(r"<loc>([^<]+)</loc>", xml):
            u = m.group(1)
            if re.search(cfg["slug_re"], u) and u not in urls:
                urls.append(u)
            if len(urls) >= limit:
                break
        return urls
    for group in cfg["listings"].values():
        for lu in group:
            for m in re.finditer(cfg["prod_re"], fetch(lu)):
                u = m.group(1)
                if u not in urls:
                    urls.append(u)
    return urls


def grab(b, url):
    html_ = proxy_fetch(url) if BRANDS[b].get("mode") == "proxy" else fetch(url)
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
        for u in discover(b)[:limit]:
            r = grab(b, u)
            if r:
                rows.append(r)
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
