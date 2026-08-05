#!/usr/bin/env python3
"""Making-charge comparison scraper (runs ~once every 15 days).

For brands that publish a product price breakup, sample MULTIPLE products per
category and record the making charge as % of gold value, then aggregate to a
median per (brand, category). Discovery brands are enumerated from their
product sitemap; others use a curated URL. Best-effort - items without a clean
% are skipped. Writes docs/making-charges.json.
"""
import json
import os
import re
import statistics
import time
from datetime import datetime, timezone, timedelta

import base64

import requests

IST = timezone(timedelta(hours=5, minutes=30))
ZYTE_KEY = os.environ.get("ZYTE_API_KEY", "").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PER_CAT = 20           # products sampled per category per brand
TOTAL_CAP = 280        # hard cap on product fetches per brand

# slug keyword -> category. v1 categories only (Bangles, Rings, Earrings,
# Mangalsutra) - user explicitly deferred Chain, Necklace, Bracelet, Pendant,
# Coin to v2. Order matters (earring must come before ring).
CAT_RULES = [
    ("mangalsutra", "Mangalsutra"),
    ("earring", "Earrings"), ("jhumk", "Earrings"), ("stud", "Earrings"),
    ("bangle", "Bangle"), ("kada", "Bangle"),
    ("ring", "Ring"),
]

# All 7 brands verified feasible via diag-making workflow. Direct fetch is
# tried first for every brand; the proxy waterfall is only invoked when direct
# fails - so brands that DO respond direct (Senco/Kisna/ORRA/PN Gadgil) never
# spend a proxy request. proxy_hint=True on the remaining 3 (BlueStone/
# CaratLane/WHP) is cosmetic - it just documents that we've seen those need
# proxy in practice; fetch() ignores it.
DISCOVER = [
    {"brand": "Senco Gold",
     "sitemaps": ["https://sencogoldanddiamonds.com/sitemap-product.xml"]},
    {"brand": "CaratLane", "proxy_hint": True,
     "sitemaps": ["https://www.caratlane.com/sitemap-products.xml",
                  "https://www.caratlane.com/sitemap.xml"]},
    {"brand": "BlueStone", "proxy_hint": True,
     "sitemaps": ["https://www.bluestone.com/sitemap.xml"]},
    {"brand": "Waman Hari Pethe", "proxy_hint": True,
     "sitemaps": ["https://whpjewellers.com/sitemap.xml"]},
    {"brand": "Kisna",
     "sitemaps": ["https://www.kisna.com/sitemap.xml"]},
    {"brand": "ORRA",
     "sitemaps": ["https://www.orra.co.in/sitemap.xml"]},
    {"brand": "PN Gadgil",
     "sitemaps": ["https://www.pngjewellers.com/sitemap.xml"]},
]
CURATED = []


# Ordered proxy waterfall (free tiers first, Zyte last if paid key exists).
# fetch() tries each in turn until one returns >=500 bytes at HTTP 200.
def _proxy_attempts(url):
    for key_env, name, url_tpl, params in [
        ("SCRAPERAPI_KEY", "scraperapi", "http://api.scraperapi.com",
         {"url": url, "render": "true", "country_code": "in"}),
        ("SCRAPINGBEE_KEY", "scrapingbee", "https://app.scrapingbee.com/api/v1/",
         {"url": url, "render_js": "true", "wait": "3000"}),
        ("ZENROWS_KEY", "zenrows", "https://api.zenrows.com/v1/",
         {"url": url, "js_render": "true", "wait": "3000"}),
        ("CRAWLBASE_KEY", "crawlbase", "https://api.crawlbase.com/",
         {"url": url}),
    ]:
        key = os.environ.get(key_env)
        if not key:
            continue
        p = dict(params)
        p["api_key" if name != "crawlbase" else "token"] = key
        if name == "zenrows":
            p["apikey"] = p.pop("api_key")
        yield name, url_tpl, p


def fetch(sess, url, allow_proxy=True, timeout=25):
    """Direct first (free), proxy waterfall only if direct fails.

    Honors the 'avoid proxy where possible' rule. Sitemap fetches pass
    allow_proxy=False - they're always static XML that direct handles.
    Returns (html, source) or (None, err).
    """
    try:
        r = sess.get(url, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 500:
            return r.text, "direct"
        direct_err = f"direct/{r.status_code}"
    except Exception as e:
        direct_err = f"direct/{type(e).__name__}"

    if not allow_proxy:
        return None, direct_err

    for name, u, p in _proxy_attempts(url):
        try:
            r = sess.get(u, params=p, timeout=60)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text, name
        except Exception:
            continue

    # Zyte as absolute last resort (paid).
    if ZYTE_KEY:
        try:
            r = sess.post("https://api.zyte.com/v3/extract",
                          auth=(ZYTE_KEY, ""),
                          json={"url": url, "httpResponseBody": True},
                          timeout=60)
            r.raise_for_status()
            return base64.b64decode(r.json()["httpResponseBody"]).decode(
                "utf-8", "replace"), "zyte"
        except Exception:
            pass

    return None, "all-proxies-failed"


def categorize(url):
    s = url.lower()
    if "gold" not in s and "coin" not in s:
        return None                      # skip diamond/silver-only items
    for kw, cat in CAT_RULES:
        if kw in s:
            return cat
    return None


def making_pct(html):
    mt = re.search(r'"making_charge_type"\s*:\s*"([a-z]+)"', html)
    mv = re.search(r'"making_charge"\s*:\s*"?([0-9.]+)', html)
    if mt and mv and "percent" in mt.group(1).lower():
        p = float(mv.group(1))
        if 0 < p <= 60:
            return round(p, 1)
    mval = re.search(r'"(?:making_charge_value|making_charges?|makingCharge|labour|wastage)"\s*:\s*"?([0-9,.]+)', html, re.I)
    gval = re.search(r'"(?:gold_value|metal_value|metal_price|gold_amount|goldValue|metalValue)"\s*:\s*"?([0-9,.]+)', html, re.I)
    if mval and gval:
        mvn = float(mval.group(1).replace(",", ""))
        gvn = float(gval.group(1).replace(",", ""))
        if gvn > 0 and 0 < mvn / gvn <= 0.6:
            return round(mvn / gvn * 100, 1)
    m = re.search(r'(?:making\s*charges?|value\s*addition|wastage)'
                  r'[^%<0-9]{0,40}([0-9]{1,2}(?:\.[0-9])?)\s*%', html, re.I)
    if m and 0 < float(m.group(1)) <= 60:
        return round(float(m.group(1)), 1)
    return None


def discover_urls(sess, sitemaps):
    """Walk sitemap(s). Sitemaps are static XML - direct fetch only, no proxy."""
    urls, seen = [], set()
    queue = list(sitemaps)
    while queue and len(seen) < 12:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        t, src = fetch(sess, sm, allow_proxy=False)
        if not t:
            print("  sitemap fail:", sm, src)
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", t)
        for loc in locs:
            if loc.endswith(".xml") and ("product" in loc.lower()
                                          or "sitemap" in loc.lower()):
                queue.append(loc)          # nested sitemap
            else:
                urls.append(loc)
    return urls


def main():
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    agg = {}          # (brand, cat) -> [pct,...]

    for d in DISCOVER:
        urls = discover_urls(sess, d["sitemaps"])
        buckets = {}
        for u in urls:
            c = categorize(u)
            if c:
                buckets.setdefault(c, []).append(u)
        fetched = hits = proxy_hits = 0
        dead = False
        for cat, us in buckets.items():
            if dead:
                break
            for u in us[:PER_CAT]:
                if fetched >= TOTAL_CAP:
                    break
                fetched += 1
                html, src = fetch(sess, u, allow_proxy=True, timeout=25)
                if src and src != "direct" and src != "all-proxies-failed":
                    proxy_hits += 1
                p = making_pct(html) if html else None
                if p is not None:
                    hits += 1
                    agg.setdefault((d["brand"], cat), []).append(p)
                # Bail early if the first 10 fetches yielded no marker at all:
                # the breakup shape probably isn't in this brand's HTML today,
                # so keep hammering only wastes fetches.
                if fetched >= 10 and hits == 0:
                    print(f"  {d['brand']}: no making % in first 10 items,"
                          " skipping remaining categories")
                    dead = True
                    break
                if src == "direct":
                    time.sleep(0.3)     # be polite to origins we hit direct
        cat_summary = [(c, len(v)) for (b, c), v in agg.items()
                       if b == d["brand"]]
        print(f"{d['brand']}: fetched {fetched} ({proxy_hits} via proxy), "
              f"cats {cat_summary}")

    for p in CURATED:
        html, _ = fetch(sess, p["url"], allow_proxy=True, timeout=25)
        pct = making_pct(html) if html else None
        if pct is not None:
            agg.setdefault((p["brand"], p["cat"]), []).append(pct)
            print(f"{p['brand']} {p['cat']}: {pct}%")

    brands = {}
    for (brand, cat), pcts in agg.items():
        if not pcts:
            continue
        brands.setdefault(brand, []).append({
            "category": cat, "items": len(pcts),
            "making_pct_median": round(statistics.median(pcts), 1),
            "making_pct_min": round(min(pcts), 1),
            "making_pct_max": round(max(pcts), 1)})
    out = [{"brand": b, "categories": sorted(c, key=lambda x: x["category"])}
           for b, c in sorted(brands.items())]

    payload = {
        "updated": datetime.now(IST).isoformat(),
        "note": "Making charge as % of gold value, median across multiple real "
                "products per category from each jeweller's public price "
                "breakup. Indicative - varies by specific design.",
        "brands": out,
    }
    os.makedirs("docs", exist_ok=True)
    with open("docs/making-charges.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tot = sum(len(v) for v in agg.values())
    print(f"charges: {len(out)} brands, {tot} products with a making %")


if __name__ == "__main__":
    main()
