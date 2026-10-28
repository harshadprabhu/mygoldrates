#!/usr/bin/env python3
"""Making charges sent by the jewellers themselves, merged into the comparison.

    python jeweller_making.py

Reads what listed jewellers sent through /list-your-jewellery (the private
jeweller_making table, service key), writes it to data/jeweller_making.json
(brand, category, %, date - figures the jeweller chose to publish) and merges
it into docs/making-charges.json, which every page and Sona read:
  - a category we measure from real products keeps the measured figure;
  - otherwise the jeweller's figure is added, marked source "jeweller" and
    confidence "jeweller", so the pages say "supplied by the jeweller";
  - a figure the jeweller no longer sends is dropped.
Runs every morning (offers job) and after each making-charge collection,
which rewrites docs/making-charges.json from scratch. If the table is not
there yet, it changes nothing.
"""
import json
import os
from datetime import datetime, timedelta, timezone

OUT = "data/jeweller_making.json"
MC = "docs/making-charges.json"
IST = timezone(timedelta(hours=5, minutes=30))
NOTE = ("Making charges sent by the jewellers themselves through /list-your-jewellery "
        "(% of gold value on plain gold, before offers). Shown as supplied by the jeweller.")


def merge(mc, items):
    """mc with the jewellers' figures merged in (see the module docstring)."""
    brands = {b["brand"].lower(): b for b in mc.get("brands", [])}
    for b in brands.values():                      # drop last time's jeweller figures
        b["categories"] = [c for c in b["categories"] if c.get("source") != "jeweller"]
    for it in items:
        b = brands.get(it["brand"].lower())
        if b is None:
            b = {"brand": it["brand"], "categories": []}
            brands[it["brand"].lower()] = b
        if any(c["category"] == it["category"] for c in b["categories"]):
            continue                               # measured from real products: that wins
        p = float(it["pct"])
        b["categories"].append({"category": it["category"], "items": 0, "making_pct_median": p,
                                "making_pct_min": p, "making_pct_max": p, "confidence": "jeweller",
                                "source": "jeweller", "updated": it.get("date", "")})
    out = []
    for b in sorted(brands.values(), key=lambda b: b["brand"].lower()):
        if b["categories"]:
            b["categories"].sort(key=lambda c: c["category"])
            out.append(b)
    return dict(mc, brands=out)


def main():
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    try:
        rows = sb.table("jeweller_making").select("slug, category, pct, updated_at").execute().data
    except Exception as e:
        print(f"::notice title=jeweller making::table not available yet ({type(e).__name__}) - nothing changed")
        return
    names = {r["slug"]: r["name"] for r in sb.table("brands").select("slug, name").execute().data}
    items = [{"brand": names[r["slug"]], "category": r["category"], "pct": float(r["pct"]),
              "date": str(r["updated_at"])[:10]}
             for r in sorted(rows, key=lambda r: (r["slug"], r["category"])) if r["slug"] in names]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"note": NOTE, "items": items}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    try:
        mc = json.load(open(MC, encoding="utf-8"))
    except (OSError, ValueError):
        mc = {"updated": datetime.now(IST).isoformat(), "brands": []}
    with open(MC, "w", encoding="utf-8") as f:
        json.dump(merge(mc, items), f, ensure_ascii=False, indent=2)
    print(f"::notice title=jeweller making::{len(items)} figures from {len({i['brand'] for i in items})} jewellers merged")


if __name__ == "__main__":
    main()
