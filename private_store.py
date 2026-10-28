#!/usr/bin/env python3
"""Collected jeweller data lives in Supabase (private), not in git.

The repository is public, so the data the collectors gather - making charges
(with every run kept as history), the day's offers, working lists - is kept in
three Supabase tables that only the service key can read (RLS on, no grants
to the public key):

  making_charges   one row per collection run, jeweller and category
  offers_daily     one row per day and jeweller: status, pages, its offers
  collector_cache  working data a collector keeps between runs (key -> JSON)

Jobs work on local copies under private/ (git-ignored, never deployed):
    pull()  Supabase -> private/*.json   before a build or a collection
    push_making() / push_offers()        after a collection
Only the conclusions reach the public site and Sona (aggregated per jeweller
and category), as before.

If the tables are not there yet, pull() leaves the local files alone and the
push functions do nothing, so every job keeps working.

    python private_store.py pull | push-making | push-offers | migrate
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

DIR = "private"
MC = DIR + "/making-charges.json"
OFFERS = DIR + "/offers.json"
JM = DIR + "/jeweller_making.json"
IST = timezone(timedelta(hours=5, minutes=30))
_sb = None

# making-charges.json fields kept in their own columns; the rest go to detail
_COLS = ("making_pct_median", "making_pct_min", "making_pct_max", "items", "confidence", "source")


def client():
    global _sb
    if _sb is None:
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
        if not (url and key):
            return None
        from supabase import create_client
        _sb = create_client(url, key)
    return _sb


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


# ------------------------------------------------------------ making charges

def making_rows(mc):
    """docs-style making-charges dict -> table rows (one per jeweller and category)."""
    run = mc.get("updated") or datetime.now(IST).isoformat()
    rows = []
    for b in mc.get("brands", []):
        for c in b.get("categories", []):
            r = {"run_at": run, "brand": b["brand"], "category": c["category"],
                 "brand_offer": b.get("offer"),
                 "detail": {k: v for k, v in c.items() if k not in _COLS + ("category",)}}
            r.update({k: c.get(k) for k in _COLS})
            rows.append(r)
    return rows


def making_from_rows(rows, note=""):
    """Table rows of one run -> the making-charges dict every page reads."""
    brands = {}
    for r in sorted(rows, key=lambda r: (r["brand"].lower(), r["category"])):
        b = brands.setdefault(r["brand"], {"brand": r["brand"], "categories": []})
        if r.get("brand_offer"):
            b["offer"] = r["brand_offer"]
        c = {"category": r["category"]}
        c.update({k: r[k] for k in _COLS if r.get(k) is not None})
        for k in ("making_pct_median", "making_pct_min", "making_pct_max"):
            if k in c:
                c[k] = float(c[k])
        c.update(r.get("detail") or {})
        b["categories"].append(c)
    return {"updated": rows[0]["run_at"] if rows else "", "note": note, "brands": list(brands.values())}


NOTE = ("Making charge as % of gold value, median across multiple real products per category "
        "from each jeweller's public price breakup. Indicative - varies by specific design.")


def push_making(mc=None):
    sb = client()
    mc = mc if mc is not None else load(MC)
    if not sb or not mc or not mc.get("brands"):
        return 0
    rows = making_rows(mc)
    try:   # the run replaces itself (a jeweller's figure merged in later, or dropped)
        sb.table("making_charges").delete().eq("run_at", rows[0]["run_at"]).execute()
        sb.table("making_charges").insert(rows).execute()
    except Exception as e:
        print(f"::warning title=private store::making charges not saved ({type(e).__name__}: {str(e)[:120]})")
        return 0
    print(f"private store: {len(rows)} making-charge rows saved (run {rows[0]['run_at']})")
    return len(rows)


def pull_making():
    sb = client()
    if not sb:
        return None
    try:
        last = sb.table("making_charges").select("run_at").order("run_at", desc=True).limit(1).execute().data
        if not last:
            return None
        rows = sb.table("making_charges").select("*").eq("run_at", last[0]["run_at"]).execute().data
    except Exception as e:
        print(f"private store: making charges not read ({type(e).__name__})")
        return None
    return making_from_rows(rows, NOTE)


# ------------------------------------------------------------------- offers

def push_offers(data=None):
    sb = client()
    data = data if data is not None else load(OFFERS)
    if not sb or not data or not data.get("brands"):
        return 0
    day = (data.get("updated") or datetime.now(IST).isoformat())[:10]
    rows = [{"day": day, "slug": b["slug"], "name": b.get("name"), "domain": b.get("domain"),
             "status": b.get("status"), "offers": b.get("offers") or [],
             "meta": {k: v for k, v in b.items() if k not in ("slug", "name", "domain", "status", "offers")},
             "updated": data.get("updated")} for b in data["brands"]]
    try:
        sb.table("offers_daily").upsert(rows, on_conflict="day,slug").execute()
    except Exception as e:
        print(f"::warning title=private store::offers not saved ({type(e).__name__}: {str(e)[:120]})")
        return 0
    print(f"private store: offers of {len(rows)} jewellers saved for {day}")
    return len(rows)


def pull_offers():
    sb = client()
    if not sb:
        return None
    try:
        last = sb.table("offers_daily").select("day").order("day", desc=True).limit(1).execute().data
        if not last:
            return None
        rows = sb.table("offers_daily").select("*").eq("day", last[0]["day"]).execute().data
    except Exception as e:
        print(f"private store: offers not read ({type(e).__name__})")
        return None
    brands = []
    for r in sorted(rows, key=lambda r: (r.get("name") or r["slug"]).lower()):
        b = {"slug": r["slug"], "name": r.get("name"), "domain": r.get("domain"), "status": r.get("status")}
        b.update(r.get("meta") or {})
        b["offers"] = r.get("offers") or []
        brands.append(b)
    upd = max((r.get("updated") or "" for r in rows), default="") or last[0]["day"]
    return {"updated": upd,
            "note": "Offers as published on each jeweller's own website on the date shown. "
                    "Read automatically; confirm terms with the jeweller before buying.",
            "brands": brands}


# -------------------------------------------------------------------- cache

def cache_get(key, default=None):
    sb = client()
    if sb:
        try:
            d = sb.table("collector_cache").select("value").eq("key", key).execute().data
            if d:
                return d[0]["value"]
        except Exception:
            pass
    return default


def cache_put(key, value):
    sb = client()
    if not sb:
        return False
    try:
        sb.table("collector_cache").upsert({"key": key, "value": value,
                                            "updated_at": datetime.now(IST).isoformat()}).execute()
        return True
    except Exception as e:
        print(f"private store: cache {key} not saved ({type(e).__name__})")
        return False


# -------------------------------------------------------------------- jobs

def pull():
    """Latest making charges and offers from Supabase into private/ (for this job only)."""
    got = []
    mc = pull_making()
    if mc and mc["brands"]:
        _write(MC, mc)
        got.append(f"making charges ({len(mc['brands'])} jewellers, run {mc['updated'][:10]})")
    of = pull_offers()
    if of and of["brands"]:
        _write(OFFERS, of)
        got.append(f"offers ({of['updated'][:10]})")
    for old, new in (("docs/making-charges.json", MC), ("docs/offers.json", OFFERS)):
        if not os.path.exists(new) and os.path.exists(old):      # before the move to Supabase
            _write(new, load(old))
    print("private store: " + ("; ".join(got) if got else "nothing in Supabase yet - local files used"))
    return bool(got)


def migrate():
    """One-off: the files that used to be in git -> Supabase."""
    for old, new in (("docs/making-charges.json", MC), ("docs/offers.json", OFFERS)):
        if not os.path.exists(new) and os.path.exists(old):
            _write(new, load(old))
    push_making()
    push_offers()
    tq = load("data/tanishq_products.json")
    if tq:
        cache_put("tanishq_sitemaps", tq)


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["pull"])[0]
    done = {"pull": pull, "push-making": push_making, "push-offers": push_offers, "migrate": migrate}[cmd]()
    # a push that saved nothing fails the job, so lost data is never silent
    sys.exit(0 if done or cmd in ("pull", "migrate") else 1)
