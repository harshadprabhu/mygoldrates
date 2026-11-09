#!/usr/bin/env python3
"""Manubhai Jewellers' making charges by category (owner, 9 Nov 2026).

Manubhai's product pages show each piece's price (taxes included), net and
gross weight, purity and the shop's own gold rate, but no making charge. The
JD Worker reads them on its schedule (its site refuses requests from GitHub)
and keeps, per piece, the making charge worked out as

    making % = price / 1.03 / (net weight x that purity's rate) - 1

in collector_cache "manubhai_making" (cf-worker-jd/worker.js, mbMaking).
This turns the last 30 days of readings into one row per category - the
median, like every other jeweller's - and puts them in the making-charges
data. A category needs MIN_ITEMS pieces; readings outside 0-60% (a price
not refreshed, a piece with an offer) are left out. A category measured
from a breakup is never replaced.

    python manubhai_making.py          # read, update (needs Supabase)
    python manubhai_making.py --dry    # read and print only
"""
import json
import os
import statistics
import sys

BRAND = "Manubhai Jewellers"
KEY = "manubhai_making"
MIN_ITEMS, LO, HI = 5, 0.0, 60.0


def rows_from_readings(readings):
    """{category: making-charges row} from the Worker's per-piece readings."""
    by = {}
    for url, r in (readings or {}).items():
        p = r.get("pct")
        if r.get("cat") and p is not None and LO <= p <= HI:
            by.setdefault(r["cat"], []).append((p, url))
    out = {}
    for cat, xs in by.items():
        if len(xs) < MIN_ITEMS:
            continue
        ps = [p for p, _ in xs]
        med = statistics.median(ps)
        ex = sorted(xs, key=lambda x: abs(x[0] - med))[:3]
        out[cat] = {"category": cat, "items": len(ps), "making_pct_median": round(med, 1),
                    "making_pct_min": round(min(ps), 1), "making_pct_max": round(max(ps), 1),
                    "confidence": "price", "source": "price",
                    "examples": [{"url": u, "pct": round(p, 1)} for p, u in ex]}
    return out


def merge(mc, rows, brand=BRAND):
    """Manubhai's categories worked out from prices into the making-charges
    data; a category measured from a breakup is kept."""
    mc = dict(mc or {"brands": []})
    brands = {b["brand"]: dict(b, categories=list(b.get("categories") or [])) for b in mc.get("brands") or []}
    b = brands.setdefault(brand, {"brand": brand, "categories": []})
    have = {c["category"]: c for c in b["categories"]}
    for cat, row in rows.items():
        old = have.get(cat)
        if old and old.get("source") != "price":
            continue
        have[cat] = row
    b["categories"] = sorted(have.values(), key=lambda c: c["category"])
    mc["brands"] = sorted(brands.values(), key=lambda x: x["brand"])
    return mc


def main(dry=False):
    import private_store
    st = private_store.cache_get(KEY) or {}
    rd = st.get("readings") or {}
    rows = rows_from_readings(rd)
    print(f"manubhai making: {len(rd)} readings, queue {len(st.get('queue') or [])}, listed {st.get('listed')}")
    for cat, r in sorted(rows.items()):
        print(f"  {cat:12s} {r['making_pct_median']:5.1f}%  ({r['items']} pieces, "
              f"{r['making_pct_min']}-{r['making_pct_max']}%)")
    if dry or not rows:
        return
    mc = merge(private_store.pull_making(), rows)
    os.makedirs(private_store.DIR, exist_ok=True)
    with open(private_store.MC, "w", encoding="utf-8") as f:
        json.dump(mc, f, indent=2)
    private_store.push_making(mc)


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
