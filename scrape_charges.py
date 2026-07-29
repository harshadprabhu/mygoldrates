#!/usr/bin/env python3
"""Making-charge comparison scraper.

Reads a curated list of real products (per brand, per category) that expose a
price breakup, extracts the making charge as a % of gold value, and writes
docs/making-charges.json. Runs weekly (charges change slowly). Best-effort:
brands/products that don't yield a clean % are skipped, not guessed.
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta

import requests

IST = timezone(timedelta(hours=5, minutes=30))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# curated representative products (public price-breakup pages)
CURATED = [
    {"brand": "Senco Gold", "cat": "Chain",
     "url": "https://sencogoldanddiamonds.com/jewellery/sleek-n-stylish-gold-mens-chain"},
    {"brand": "BlueStone", "cat": "Chain",
     "url": "https://www.bluestone.com/chains/the-shravya-gold-chain~59380.html"},
    {"brand": "Waman Hari Pethe", "cat": "Coin",
     "url": "https://whpjewellers.com/products/whp-24kt-999-10-gm-gold-coin"},
    {"brand": "PN Gadgil", "cat": "Coin",
     "url": "https://www.pngjewellers.com/products/10-gram-24-kt-995-laxmi-shree-gold-coin"},
    {"brand": "Kisna", "cat": "Ring",
     "url": "https://www.kisna.com/products/elysian-diamond-ring"},
    {"brand": "ORRA", "cat": "Pendant",
     "url": "https://www.orra.co.in/product/round-diamond-crown-star-pendant-set-in-rose-gold-osp20029-m300x0b"},
]


def making_pct(html):
    """Return making charge as % of gold value, or None."""
    # 1) explicit percentage field (Senco / Shopify metafields)
    mt = re.search(r'"making_charge_type"\s*:\s*"([a-z]+)"', html)
    mv = re.search(r'"making_charge"\s*:\s*"?([0-9.]+)', html)
    if mt and mv and "percent" in mt.group(1).lower():
        p = float(mv.group(1))
        if 0 <= p <= 60:
            return round(p, 1)
    # 2) making charge value (Rs) + gold value nearby -> derive %
    mval = re.search(r'"making_charge_value"\s*:\s*"?([0-9.]+)', html)
    gval = re.search(r'"(?:gold_value|metal_value|gold_amount)"\s*:\s*"?([0-9.]+)', html)
    if mval and gval:
        mvn, gvn = float(mval.group(1)), float(gval.group(1))
        if gvn > 0 and 0 <= mvn / gvn <= 0.6:
            return round(mvn / gvn * 100, 1)
    # 3) visible "Making Charges ... NN%"
    m = re.search(r'making\s*charges?[^%<0-9]{0,40}([0-9]{1,2}(?:\.[0-9])?)\s*%',
                  html, re.I)
    if m:
        p = float(m.group(1))
        if 0 <= p <= 60:
            return round(p, 1)
    # 4) visible "Making Charges Rs X" + "Gold Value Rs Y"
    mk = re.search(r'making\s*charges?[^0-9]{0,25}(?:rs\.?|₹|inr)?\s*([0-9,]{2,7})',
                   html, re.I)
    gv = re.search(r'(?:gold\s*value|metal\s*value)[^0-9]{0,25}(?:rs\.?|₹|inr)?\s*([0-9,]{3,7})',
                   html, re.I)
    if mk and gv:
        try:
            mn = float(mk.group(1).replace(",", ""))
            gn = float(gv.group(1).replace(",", ""))
            if gn > 0 and 0 <= mn / gn <= 0.6:
                return round(mn / gn * 100, 1)
        except ValueError:
            pass
    return None


def main():
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    out = []
    for p in CURATED:
        try:
            r = sess.get(p["url"], timeout=25)
            pct = making_pct(r.text)
        except Exception as e:
            print(f"  {p['brand']:18} {p['cat']:8} ERROR {type(e).__name__}")
            continue
        if pct is None:
            print(f"  {p['brand']:18} {p['cat']:8} no making% found")
            continue
        print(f"  {p['brand']:18} {p['cat']:8} {pct}%")
        out.append({"brand": p["brand"], "category": p["cat"],
                    "making_pct": pct, "url": p["url"]})

    payload = {
        "updated": datetime.now(IST).isoformat(),
        "note": "Making charge as % of gold value, from each jeweller's public "
                "product price breakup. Indicative - varies by specific design.",
        "items": out,
    }
    os.makedirs("docs", exist_ok=True)
    with open("docs/making-charges.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"charges: wrote {len(out)} items")


if __name__ == "__main__":
    main()
