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

import requests

IST = timezone(timedelta(hours=5, minutes=30))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PER_CAT = 6            # max products sampled per category per brand
TOTAL_CAP = 70         # hard cap on product fetches per brand

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
]
CURATED = [
    {"brand": "ORRA", "cat": "Pendant",
     "url": "https://www.orra.co.in/product/round-diamond-crown-star-pendant-set-in-rose-gold-osp20029-m300x0b"},
]


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
    mval = re.search(r'"making_charge_value"\s*:\s*"?([0-9.]+)', html)
    gval = re.search(r'"(?:gold_value|metal_value|gold_amount)"\s*:\s*"?([0-9.]+)', html)
    if mval and gval:
        mvn, gvn = float(mval.group(1)), float(gval.group(1))
        if gvn > 0 and 0 < mvn / gvn <= 0.6:
            return round(mvn / gvn * 100, 1)
    m = re.search(r'making\s*charges?[^%<0-9]{0,40}([0-9]{1,2}(?:\.[0-9])?)\s*%',
                  html, re.I)
    if m and 0 < float(m.group(1)) <= 60:
        return round(float(m.group(1)), 1)
    return None


def discover_urls(sess, sitemaps):
    urls = []
    for sm in sitemaps:
        try:
            t = sess.get(sm, timeout=25).text
            urls += re.findall(r"<loc>([^<]+)</loc>", t)
        except Exception as e:
            print("  sitemap error:", type(e).__name__)
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
        fetched = 0
        for cat, us in buckets.items():
            for u in us[:PER_CAT]:
                if fetched >= TOTAL_CAP:
                    break
                fetched += 1
                try:
                    p = making_pct(sess.get(u, timeout=20).text)
                except Exception:
                    p = None
                if p is not None:
                    agg.setdefault((d["brand"], cat), []).append(p)
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
