#!/usr/bin/env python3
"""24K coin making charges worked out from the coin's price (owner, 3 Nov 2026).

Some jewellers show a coin's price and weight but no breakup. With the
jeweller's own 24K rate today (our rates table):

    making % = price / 1.03 (GST, when the price includes it) / (weight x 24K rate) - 1

Indian shops must quote prices inclusive of GST, so that is assumed unless the
page says otherwise. A coin is taken as 24K only when that works out between
0 and 20%: a lower figure means the coin is not 24K (Joyalukkas's coins come
out below the gold value at the 24K rate - they are 22K). Coins under 1 g are
skipped (their making % is not comparable).

Each run's readings are kept by day in Supabase (collector_cache key
coin_price_history, 60 days) so the figures can be watched before they are
relied on. The coin rows in the making-charges data are refreshed from the
last 7 days' readings for jewellers whose coins carry no breakup (source
"price"); a coin making charge measured from a breakup is never replaced.

    python coin_price_making.py          # read, record, update (needs Supabase)
    python coin_price_making.py --dry    # read and print only
"""
import json
import os
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone

import requests

IST = timezone(timedelta(hours=5, minutes=30))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
GST = 0.03
MIN_G, MAX_PCT = 1.0, 20.0
HISTORY_KEY, KEEP_DAYS, USE_DAYS = "coin_price_history", 60, 7
_WT = re.compile(r"(\d+(?:\.\d+)?)\s*-?\s*(?:gm|gms|g|gram|grams)\b", re.I)


def weight_g(text):
    """'5 gm', '10 Gram', '2-gram' -> grams, or None."""
    m = _WT.search((text or "").replace("-", " "))
    return float(m.group(1)) if m else None


def making_pct(price, grams, rate24, incl_gst=True):
    """Making % on a 24K coin from its price, or None when it is not a
    plausible 24K coin (under 1 g, or outside 0-20%)."""
    if not (price and grams and rate24) or grams < MIN_G:
        return None
    gold = grams * rate24
    pct = (price / (1 + GST) if incl_gst else price) / gold * 100 - 100
    return round(pct, 2) if 0 <= pct <= MAX_PCT else None


# ---------------------------------------------------------------- readers
def read_joyalukkas(sess):
    """Joyalukkas's open GraphQL search: name (carries the weight) + price."""
    q = ('{products(search:"gold coin",pageSize:60){items{name url_key '
         'price_range{minimum_price{final_price{value}}}}}}')
    r = sess.get("https://www.joyalukkas.in/graphql", params={"query": q}, timeout=25)
    out = []
    for it in ((r.json().get("data") or {}).get("products") or {}).get("items") or []:
        name = it.get("name") or ""
        if "coin" not in name.lower() or re.search(r"silver|pendant|chain", name, re.I):
            continue
        price = (((it.get("price_range") or {}).get("minimum_price") or {}).get("final_price") or {}).get("value")
        out.append({"url": f"https://www.joyalukkas.in/{it.get('url_key')}.html", "name": name,
                    "g": weight_g(name), "price": price, "incl_gst": True})
    return out


def read_ckc(sess, limit=12):
    """C Krishniah Chetty: coin pages from its search, price from the page's
    product data, 'Inclusive Of All Taxes' printed beside it."""
    base = "https://www.ckcjewellers.com"
    h = sess.get(base + "/en_IN/search?q=gold+coin", timeout=25).text
    links = list(dict.fromkeys(re.findall(r'href="(/en_IN/gold-coin[^"]+-CKCJ_\d+\.html)"', h)))
    out = []
    for u in links[:limit]:
        name = requests.utils.unquote(u)
        if not re.search(r"24\s*kt|999|995", name, re.I):
            continue
        try:
            p = sess.get(base + u, timeout=25).text
        except requests.RequestException:
            continue
        m = re.search(r'"price"\s*:\s*"?([\d.]+)', p)
        # inclusive unless the page says the tax is extra
        excl = bool(re.search(r"exclusive of (?:all )?tax|\+\s*gst extra|plus gst", p, re.I))
        out.append({"url": base + u, "name": name.rsplit("/", 1)[-1][:120], "g": weight_g(name),
                    "price": float(m.group(1)) if m else None, "incl_gst": not excl})
    return out


READERS = {"Joyalukkas": read_joyalukkas, "C Krishniah Chetty": read_ckc}


# ---------------------------------------------------------------- run
def todays_rate24(sb):
    """{jeweller name: 24K pre-GST rate} from the latest published rates."""
    rows = (sb.table("rates").select("rate_date, canonical_24k_pre_gst, brands(name, slug)")
            .eq("status", "published").order("rate_date", desc=True).limit(400).execute().data)
    import private_store
    own = private_store.cache_get("rate24_actual") or {}    # the jeweller's own 24K (collect.py)
    out = {}
    for r in rows:
        b = r.get("brands") or {}
        n = b.get("name")
        if n and n not in out:
            mine = (own.get("rates") or {}).get(b.get("slug")) if own.get("date") == r.get("rate_date") else None
            out[n] = float(mine or r["canonical_24k_pre_gst"])
    return out


def read_all(sess, rate24):
    """{brand: [reading with pct]} for every reader, plausible 24K coins only."""
    got = {}
    for brand, fn in READERS.items():
        r24 = rate24.get(brand)
        try:
            items = fn(sess)
        except Exception as e:                      # one jeweller never stops the rest
            print(f"  {brand}: failed ({type(e).__name__}: {e})")
            continue
        ok = []
        for it in items:
            pct = making_pct(it.get("price"), it.get("g"), r24, it.get("incl_gst", True))
            if pct is not None:
                ok.append(dict(it, pct=pct, rate24=r24))
        print(f"  {brand}: {len(items)} coins listed, {len(ok)} plausible 24K"
              + (f", median {statistics.median([x['pct'] for x in ok]):.2f}%" if ok else "")
              + ("" if r24 else " (no 24K rate today)"))
        if ok:
            got[brand] = ok
    return got


def update_history(hist, today, got):
    hist = dict(hist or {})
    hist[today] = {b: {"median": round(statistics.median([x["pct"] for x in v]), 2), "n": len(v),
                       "readings": [{k: x[k] for k in ("url", "g", "price", "pct")} for x in v[:10]]}
                   for b, v in got.items()}
    cut = (datetime.fromisoformat(today) - timedelta(days=KEEP_DAYS)).date().isoformat()
    return {d: v for d, v in hist.items() if d >= cut}


def coin_rows_from_history(hist, today):
    """{brand: making-charges row} from the last USE_DAYS days of readings."""
    cut = (datetime.fromisoformat(today) - timedelta(days=USE_DAYS)).date().isoformat()
    pcts, ex = {}, {}
    for d, day in sorted(hist.items()):
        if d < cut:
            continue
        for b, v in day.items():
            pcts.setdefault(b, []).extend(x["pct"] for x in v["readings"])
            ex[b] = v["readings"][:3]
    return {b: {"category": "Coin", "items": len(p), "making_pct_median": round(statistics.median(p), 2),
                "making_pct_min": min(p), "making_pct_max": max(p), "confidence": "price",
                "source": "price", "examples": [{"url": e["url"], "pct": e["pct"]} for e in ex[b]]}
            for b, p in pcts.items() if p}


def merge_into_making(mc, rows):
    """Put worked-out coin rows into the making-charges data, never over a
    coin charge measured from a breakup."""
    mc = dict(mc or {"brands": []})
    brands = {b["brand"]: dict(b, categories=list(b.get("categories") or [])) for b in mc.get("brands") or []}
    for name, row in rows.items():
        b = brands.setdefault(name, {"brand": name, "categories": []})
        old = next((c for c in b["categories"] if c.get("category") == "Coin"), None)
        if old and old.get("source") != "price":
            continue                                   # measured from a breakup: keep it
        b["categories"] = [c for c in b["categories"] if c.get("category") != "Coin"] + [row]
        b["categories"].sort(key=lambda c: c["category"])
    mc["brands"] = sorted(brands.values(), key=lambda b: b["brand"])
    return mc


def main(dry=False):
    import private_store
    sb = private_store.client()
    if not sb:
        print("coin prices: no Supabase credentials"); return
    sess = requests.Session(); sess.headers["User-Agent"] = UA
    today = datetime.now(IST).date().isoformat()
    got = read_all(sess, todays_rate24(sb))
    if dry:
        print(json.dumps({b: [(x["g"], x["price"], x["pct"]) for x in v] for b, v in got.items()}, indent=1)[:3000])
        return
    hist = update_history(private_store.cache_get(HISTORY_KEY) or {}, today, got)
    private_store.cache_put(HISTORY_KEY, hist)
    rows = coin_rows_from_history(hist, today)
    if rows:
        mc = merge_into_making(private_store.pull_making(), rows)
        os.makedirs(private_store.DIR, exist_ok=True)
        with open(private_store.MC, "w", encoding="utf-8") as f:
            json.dump(mc, f, indent=2)
        private_store.push_making(mc)
    # the watch list: each jeweller's daily median, oldest first
    print("coin making % worked out from price, by day:")
    for b in sorted({b for d in hist.values() for b in d}):
        print(f"  {b:20s} " + "  ".join(f"{d[5:]}:{hist[d][b]['median']:.1f}%" for d in sorted(hist) if b in hist[d]))


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
