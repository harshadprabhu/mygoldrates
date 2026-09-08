#!/usr/bin/env python3
"""Persist Market Pulse data into Supabase.

Pulls the Cloudflare worker's endpoints (the same ones the live homepage
reads) and writes them into the tables created by
sql/market_pulse_tables.sql:

    /market   -> market_ticks       (one row per run)
    /vendors  -> vendor_rates       (one row per dealer x metal)
    /ohlc     -> ohlc_history       (upsert on (symbol, d))
    /news     -> market_news        (upsert on url)
    /calendar -> economic_calendar  (upsert on (event_at, title, country))

WHY this exists: until now every Market Pulse number was fetched live on
each page load and then thrown away. Nothing was stored, so there was no
history, no way to audit a bad print, and no source of truth to reconcile
the page against. The live page still reads the worker directly for
sub-second freshness - this is the durable record behind it, not a slower
path in front of it.

Uses SUPABASE_SERVICE_KEY (bypasses RLS; anon has read-only on these
tables). Every endpoint is independently soft-failed: one dead upstream
must not stop the others from being recorded.

Exit code is 0 unless EVERY endpoint failed, so a single flaky upstream
does not turn the schedule red.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

WORKER = os.environ.get(
    "MARKET_API_BASE",
    "https://mygoldrates-market-api.harshads-priority.workers.dev",
).rstrip("/")

OZ_TO_G = 31.1034768
OZ_PER_KG = 32.1507466
INDIA_PREMIUM_GOLD = 0.14
INDIA_PREMIUM_SILVER = 0.12


def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def sb_write(table, rows, on_conflict=None):
    """POST rows to PostgREST. on_conflict makes it an upsert."""
    url = os.environ["SUPABASE_URL"].rstrip("/") + f"/rest/v1/{table}"
    if on_conflict:
        url += f"?on_conflict={on_conflict}"
    key = os.environ["SUPABASE_SERVICE_KEY"]
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": ("resolution=merge-duplicates,return=minimal"
                   if on_conflict else "return=minimal"),
    }
    req = urllib.request.Request(
        url, data=json.dumps(rows).encode("utf-8"),
        headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.status


def snap_market():
    m = get_json(f"{WORKER}/market")
    gold_usd = m.get("gold_usd")
    silver_usd = m.get("silver_usd")
    usd_inr = m.get("usd_inr")
    row = {
        "gold_usd_oz": gold_usd,
        "silver_usd_oz": silver_usd,
        "usd_inr": usd_inr,
        # Same derivation the page uses, stored so the record is
        # self-contained and doesn't need the constants to reproduce.
        "gold_inr_g": (round((gold_usd / OZ_TO_G) * usd_inr
                             * (1 + INDIA_PREMIUM_GOLD), 4)
                       if gold_usd and usd_inr else None),
        "silver_inr_kg": (round(silver_usd * OZ_PER_KG * usd_inr
                                * (1 + INDIA_PREMIUM_SILVER), 4)
                          if silver_usd and usd_inr else None),
        "source": "cf-worker",
    }
    for side in ("gold", "silver"):
        blk = m.get(f"mcx_{side}") or {}
        row[f"mcx_{side}_ltp"] = blk.get("ltp")
        row[f"mcx_{side}_expiry"] = blk.get("expiry")
        row[f"mcx_{side}_pchg"] = blk.get("pchg")
    sb_write("market_ticks", [row])
    return 1


def snap_vendors():
    v = get_json(f"{WORKER}/vendors")
    rows = []
    # Worker shape: {"dealers":[{"dealer":"x","rates":{"GOLD_995":{...}}}]}
    for d in (v.get("dealers") or []):
        dealer = d.get("dealer") or d.get("name")
        for metal, vals in (d.get("rates") or {}).items():
            if not isinstance(vals, dict):
                continue
            rows.append({
                "dealer": dealer, "metal": metal,
                "buy": vals.get("buy"), "sell": vals.get("sell"),
                "high": vals.get("high"), "low": vals.get("low"),
            })
    if rows:
        sb_write("vendor_rates", rows)
    return len(rows)


def snap_ohlc():
    total = 0
    for sym in ("GC=F", "SI=F"):
        try:
            o = get_json(f"{WORKER}/ohlc?symbol={urllib.parse.quote(sym)}")
        except Exception as e:
            print(f"  ohlc {sym}: {type(e).__name__}: {e}")
            continue
        rows = [{
            "symbol": sym, "d": c.get("date") or c.get("d"),
            "open": c.get("open"), "high": c.get("high"),
            "low": c.get("low"), "close": c.get("close"),
        } for c in (o.get("candles") or o.get("data") or [])
            if (c.get("date") or c.get("d"))]
        if rows:
            sb_write("ohlc_history", rows, on_conflict="symbol,d")
            total += len(rows)
    return total


def snap_news():
    n = get_json(f"{WORKER}/news")
    rows = [{
        "title": it.get("title"), "url": it.get("url") or it.get("link"),
        "published_at": it.get("published_at") or it.get("pubDate"),
        "source": it.get("source"),
    } for it in (n.get("items") or n.get("news") or [])
        if it.get("title") and (it.get("url") or it.get("link"))]
    if rows:
        sb_write("market_news", rows, on_conflict="url")
    return len(rows)


def snap_calendar():
    c = get_json(f"{WORKER}/calendar")
    rows = [{
        "event_at": it.get("event_at") or it.get("date"),
        "title": it.get("title") or it.get("event"),
        "country": it.get("country"), "impact": it.get("impact"),
        "actual": it.get("actual"), "forecast": it.get("forecast"),
        "previous": it.get("previous"),
    } for it in (c.get("events") or c.get("items") or [])
        if (it.get("title") or it.get("event"))]
    if rows:
        sb_write("economic_calendar", rows,
                 on_conflict="event_at,title,country")
    return len(rows)


def main():
    if not os.environ.get("SUPABASE_URL") or \
            not os.environ.get("SUPABASE_SERVICE_KEY"):
        print("market_snapshot: SUPABASE_URL/SUPABASE_SERVICE_KEY not set")
        return 1
    jobs = [("market", snap_market), ("vendors", snap_vendors),
            ("ohlc", snap_ohlc), ("news", snap_news),
            ("calendar", snap_calendar)]
    ok = 0
    for name, fn in jobs:
        try:
            n = fn()
            print(f"market_snapshot: {name} ok ({n} rows)")
            ok += 1
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            print(f"market_snapshot: {name} FAILED HTTP {e.code}: {body}")
        except Exception as e:
            print(f"market_snapshot: {name} FAILED {type(e).__name__}: "
                  f"{str(e)[:200]}")
    if ok == 0:
        print("market_snapshot: every endpoint failed")
        return 1
    print(f"market_snapshot: {ok}/{len(jobs)} endpoints recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
