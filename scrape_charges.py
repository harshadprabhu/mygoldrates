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

# slug keyword -> category (order matters; earring before ring)
CAT_RULES = [
    ("mangalsutra", "Mangalsutra"), ("earring", "Earrings"),
    ("jhumk", "Earrings"), ("stud", "Earrings"), ("chain", "Chain"),
    ("necklace", "Necklace"), ("haar", "Necklace"), ("bangle", "Bangle"),
    ("kada", "Bangle"), ("bracelet", "Bracelet"), ("pendant", "Pendant"),
    ("coin", "Coin"), ("ring", "Ring"),
]

DISCOVER = [
    {"brand": "Senco Gold",
     "sitemaps": ["https://sencogoldanddiamonds.com/sitemap-product.xml"]},
    # Bot-walled brands -> fetched through Zyte (proxy=True). Best-effort:
    # only rows where a clean making % is found are kept.
    {"brand": "CaratLane", "proxy": True,
     "sitemaps": ["https://www.caratlane.com/sitemap-products.xml",
                  "https://www.caratlane.com/sitemap.xml"]},
    {"brand": "BlueStone", "proxy": True,
     "sitemaps": ["https://www.bluestone.com/sitemap.xml"]},
    {"brand": "Candere", "proxy": True,
     "sitemaps": ["https://www.candere.com/sitemap.xml"]},
    {"brand": "Vaibhav Jewellers", "proxy": True,
     "sitemaps": ["https://www.vaibhavjewellers.com/sitemap.xml"]},
]
CURATED = [
    {"brand": "ORRA", "cat": "Pendant",
     "url": "https://www.orra.co.in/product/round-diamond-crown-star-pendant-set-in-rose-gold-osp20029-m300x0b"},
]


def get(sess, url, proxy=False, timeout=25):
    """Fetch a URL, optionally via Zyte to bypass bot walls."""
    if proxy and ZYTE_KEY:
        r = sess.post("https://api.zyte.com/v3/extract",
                      auth=(ZYTE_KEY, ""),
                      json={"url": url, "httpResponseBody": True},
                      timeout=60)
        r.raise_for_status()
        return base64.b64decode(r.json()["httpResponseBody"]).decode(
            "utf-8", "replace")
    return sess.get(url, timeout=timeout).text


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


def discover_urls(sess, sitemaps, proxy=False):
    urls, seen = [], set()
    queue = list(sitemaps)
    while queue and len(seen) < 12:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            t = get(sess, sm, proxy=proxy)
        except Exception as e:
            print("  sitemap error:", sm, type(e).__name__)
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
        proxy = d.get("proxy", False)
        urls = discover_urls(sess, d["sitemaps"], proxy)
        buckets = {}
        for u in urls:
            c = categorize(u)
            if c:
                buckets.setdefault(c, []).append(u)
        fetched = hits = 0
        dead = False
        for cat, us in buckets.items():
            if dead:
                break
            for u in us[:PER_CAT]:
                if fetched >= TOTAL_CAP:
                    break
                fetched += 1
                try:
                    p = making_pct(get(sess, u, proxy=proxy, timeout=20))
                except Exception:
                    p = None
                if p is not None:
                    hits += 1
                    agg.setdefault((d["brand"], cat), []).append(p)
                # Bail early on bot-walled / JS-rendered brands: no % in the
                # first 10 fetched products means the breakup isn't in the HTML.
                if proxy and fetched >= 10 and hits == 0:
                    print(f"  {d['brand']}: no making % in HTML, skipping")
                    dead = True
                    break
                if not proxy:
                    time.sleep(0.3)
        print(f"{d['brand']}: fetched {fetched}, "
              f"cats {[(c, len(v)) for (b, c), v in agg.items() if b == d['brand']]}")

    for p in CURATED:
        try:
            pct = making_pct(sess.get(p["url"], timeout=25).text)
        except Exception:
            pct = None
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
