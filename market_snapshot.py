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
from datetime import datetime, timezone

WORKER = os.environ.get(
    "MARKET_API_BASE",
    "https://mygoldrates-market-api.harshads-priority.workers.dev",
).rstrip("/")

OZ_TO_G = 31.1034768
OZ_PER_KG = 32.1507466
INDIA_PREMIUM_GOLD = 0.14
INDIA_PREMIUM_SILVER = 0.12


# Cloudflare fronts the worker and its browser-integrity check answers
# "Error 1010: Access denied" to urllib's default Python-urllib/3.x
# User-Agent. Every scheduled run was getting 403 on 4 of 5 endpoints
# because of this one missing header - reproduced exactly: same URL,
# default UA -> 403, browser UA -> 200.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def get_json(url, timeout=30):
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def sb_write(table, rows, on_conflict=None):
    """POST rows to PostgREST. on_conflict makes it an upsert.

    An upsert batch may not contain the same key twice (Postgres refuses
    the whole batch), so repeats are dropped first, keeping the last."""
    if on_conflict:
        keys = on_conflict.split(",")
        rows = list({tuple(r.get(k) for k in keys): r for r in rows}.values())
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


def vendor_rows(v):
    """Rows for vendor_rates from the worker's /vendors payload.

    Current shape (since September 2026):
      {"vendors": [{"dealer_id": "arihant", "dealer": "Arihant Spot",
                    "all_rows": [{"name": "GOLD 995 (1kg) ...", "buy": ..,
                                  "sell": .., "high": .., "low": ..}, ...]}]}
    The original shape, still accepted:
      {"dealers": [{"dealer": "x", "rates": {"GOLD_995": {"buy": ..}}}]}
    Reading only the original shape is why vendor_rates stayed empty.
    """
    rows = []
    for d in (v.get("vendors") or v.get("dealers") or []):
        dealer = d.get("dealer_id") or d.get("dealer") or d.get("name")
        for r in (d.get("all_rows") or []):
            if isinstance(r, dict) and r.get("name"):
                rows.append({"dealer": dealer, "metal": r["name"],
                             "buy": r.get("buy"), "sell": r.get("sell"),
                             "high": r.get("high"), "low": r.get("low")})
        for metal, vals in (d.get("rates") or {}).items():
            if isinstance(vals, dict):
                rows.append({"dealer": dealer, "metal": metal,
                             "buy": vals.get("buy"), "sell": vals.get("sell"),
                             "high": vals.get("high"), "low": vals.get("low")})
    return [r for r in rows if r["dealer"]]


def snap_vendors():
    rows = vendor_rows(get_json(f"{WORKER}/vendors"))
    if rows:
        sb_write("vendor_rates", rows)
    return len(rows)


def ohlc_rows(sym, o):
    """Rows for ohlc_history. Candles now come as {"t": epoch seconds,
    "o","h","l","c"}; the original {"date","open","high","low","close"}
    is still accepted. Reading only the original is why ohlc_history
    stayed empty. One row per day: a repeated day keeps the last candle."""
    by_day = {}
    for c in (o.get("candles") or o.get("data") or []):
        d = c.get("date") or c.get("d")
        if not d and c.get("t") is not None:
            d = datetime.fromtimestamp(int(c["t"]), tz=timezone.utc).date().isoformat()
        if not d:
            continue
        by_day[str(d)[:10]] = {
            "symbol": sym, "d": str(d)[:10],
            "open": c.get("open", c.get("o")), "high": c.get("high", c.get("h")),
            "low": c.get("low", c.get("l")), "close": c.get("close", c.get("c"))}
    return list(by_day.values())


def snap_ohlc():
    total = 0
    # The worker takes ?sym=XAU|XAG. This used to send ?symbol=GC=F, which
    # the worker ignores, so both requests returned gold and silver would
    # have been stored with gold's prices.
    for sym, wsym in (("GC=F", "XAU"), ("SI=F", "XAG")):
        try:
            o = get_json(f"{WORKER}/ohlc?sym={wsym}")
        except Exception as e:
            print(f"  ohlc {sym}: {type(e).__name__}: {e}")
            continue
        rows = ohlc_rows(sym, o)
        if rows:
            sb_write("ohlc_history", rows, on_conflict="symbol,d")
            total += len(rows)
    return total


NEWS_FEED = ("https://news.google.com/rss/search?q="
             "gold%20rate%20OR%20gold%20price%20India%20when:1d"
             "&hl=en-IN&gl=IN&ceid=IN:en")


def news_rows_from_rss(xml):
    """Headlines (title, link, source, time) from a Google News RSS page -
    the same source the site build's news strip uses."""
    import html as _h
    import re
    from email.utils import parsedate_to_datetime
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        def f(tag):
            m = re.search(r"<" + tag + r"[^>]*>(.*?)</" + tag + ">", it, re.S)
            return _h.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
        title, link, src = f("title"), f("link"), f("source")
        if src and title.endswith(" - " + src):
            title = title[:-(len(src) + 3)].strip()
        try:
            when = parsedate_to_datetime(f("pubDate")).isoformat()
        except (TypeError, ValueError):
            when = None
        if title and link:
            out.append({"title": title, "url": link, "published_at": when,
                        "source": src or None})
    return out


def snap_news():
    n = get_json(f"{WORKER}/news")
    rows = [{
        "title": it.get("title"), "url": it.get("url") or it.get("link"),
        "published_at": it.get("published_at") or it.get("pubDate"),
        "source": it.get("source"),
    } for it in (n.get("items") or n.get("news") or [])
        if it.get("title") and (it.get("url") or it.get("link"))]
    if not rows:
        # the worker's news upstream has returned an empty list since
        # October 2026; read the headlines directly instead
        req = urllib.request.Request(NEWS_FEED, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = news_rows_from_rss(r.read().decode("utf-8", errors="replace"))
    if rows:
        sb_write("market_news", rows, on_conflict="url")
    return len(rows)


CALENDAR_FEED = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def calendar_rows(events):
    """US events from the FairEconomy weekly feed: they are what moves gold,
    and the same filter the site's calendar strip uses."""
    return [{
        "event_at": it.get("date"), "title": it.get("title"),
        "country": it.get("country"), "impact": it.get("impact"),
        "actual": it.get("actual") or None, "forecast": it.get("forecast") or None,
        "previous": it.get("previous") or None,
    } for it in (events or [])
        if it.get("title") and (it.get("country") or "").upper() in ("USD", "US")]


def snap_calendar():
    # Straight from the feed, not through the worker: the feed sits behind
    # Cloudflare, which refuses the worker's subrequests, so /calendar
    # answered 502 on every call (generate_site.fetch_calendar documents
    # the same). From a GitHub runner the feed answers normally.
    rows = calendar_rows(get_json(CALENDAR_FEED))
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
    # Count ROWS WRITTEN, not jobs that failed to raise. snap_ohlc swallows
    # its per-symbol errors and returns 0, which used to be counted as a
    # success - so a run where every single endpoint was 403ing still had
    # ok == 1 and exited 0. Twenty consecutive green runs had persisted
    # exactly nothing. A job that writes no rows is not a success.
    ok = 0
    rows_total = 0
    for name, fn in jobs:
        try:
            n = fn()
            if n:
                ok += 1
                rows_total += n
                print(f"market_snapshot: {name} ok ({n} rows)")
            else:
                print(f"market_snapshot: {name} WROTE NOTHING (0 rows)")
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
    if rows_total == 0:
        print("market_snapshot: NOTHING WAS RECORDED - every endpoint "
              "either failed or wrote zero rows")
        return 1
    print(f"market_snapshot: {ok}/{len(jobs)} endpoints recorded, "
          f"{rows_total} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
