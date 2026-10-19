"""Check the private analytics dashboard against the raw tables. Read-only.

Calls analytics_report() exactly as the dashboard does, then recomputes the
same figures straight from page_views / click_events with the service key,
and prints both side by side, plus how often each optional column is
filled. Forwarded as job annotations by its workflow, never committed.
"""
import json
import os
from collections import Counter
from datetime import date, timedelta

import requests

URL = os.environ["SUPABASE_URL"].rstrip("/")
SVC = os.environ["SUPABASE_SERVICE_KEY"]
ANON = os.environ.get("SUPABASE_ANON_KEY", "")
TOKEN = os.environ.get("ANALYTICS_TOKEN", "")
H = {"apikey": SVC, "Authorization": f"Bearer {SVC}"}


def fetch(table, cols, since, until):
    rows, off = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{table}",
                         params={"select": cols, "day": f"gte.{since}",
                                 "and": f"(day.lte.{until})", "order": "id.asc"},
                         headers={**H, "Range": f"{off}-{off + 999}"}, timeout=60)
        r.raise_for_status()
        b = r.json(); rows += b
        if len(b) < 1000:
            return rows
        off += 1000


def main():
    # Which database functions the service key can call (names only), and
    # whether any of them can run arbitrary SQL. Read-only.
    r = requests.get(f"{URL}/rest/v1/", headers=H, timeout=60)
    try:
        paths = sorted(p for p in r.json().get("paths", {}) if p.startswith("/rpc/"))
    except Exception:
        paths = [f"(no list: HTTP {r.status_code})"]
    print("RPC functions:", ", ".join(x[5:] for x in paths))
    today = date.today()
    for days in (1, 7, 30):
        lo = (today - timedelta(days=days - 1)).isoformat(); hi = today.isoformat()
        print(f"\n===== RANGE {lo} .. {hi} =====")
        r = requests.post(f"{URL}/rest/v1/rpc/analytics_report",
                          headers={"apikey": ANON, "Authorization": f"Bearer {ANON}",
                                   "Content-Type": "application/json"},
                          json={"p_secret": TOKEN, "p_from": lo, "p_to": hi, "p_page": None},
                          timeout=60)
        d = r.json() if r.ok else {"http": r.status_code, "body": r.text[:200]}
        if days == 1:
            print("RPC keys:", sorted(d.keys()) if isinstance(d, dict) else d)
        if isinstance(d, dict) and "error" in d:
            print("RPC error:", d); continue
        t = d.get("totals", {})
        print("RPC version:", d.get("version", "OLD (pre 2026-10-19)"),
              "| lifetime:", d.get("lifetime", "MISSING"))
        print("RPC totals:", t, "| top_hosts:", d.get("top_hosts", "MISSING"))
        print("RPC daily rows:", len(d.get("daily") or []),
              "| sum of daily views:", sum(x["views"] for x in d.get("daily") or []))

        pv = fetch("page_views", "id,day,page,session_id,host,referrer", lo, hi)
        ce = fetch("click_events", "id,day,page,target,session_id", lo, hi)
        real_pv = [x for x in pv if not (x.get("page") or "").startswith("/__")]
        print(f"RAW page_views={len(pv)} (excl. /__ probes {len(real_pv)}) "
              f"sessions={len({x['session_id'] for x in pv})} "
              f"click_events={len(ce)} (excl. probes "
              f"{sum(1 for x in ce if not (x.get('page') or '').startswith('/__'))})")
        print("RAW host fill:", Counter((x.get("host") or "(null)") for x in pv).most_common(5))
        print("RAW session_id empty:", sum(1 for x in pv if not x.get("session_id")),
              "| clicks with empty session:", sum(1 for x in ce if not x.get("session_id")))
        if days == 30:
            byday = Counter(x["day"] for x in pv); cday = Counter(x["day"] for x in ce)
            hostday = Counter(x["day"] for x in pv if x.get("host"))
            print("day         views clicks with_host")
            for k in sorted(byday)[-30:]:
                print(f"{k}  {byday[k]:5} {cday[k]:6} {hostday[k]:9}")


if __name__ == "__main__":
    main()
