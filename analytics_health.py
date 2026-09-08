#!/usr/bin/env python3
"""Health check: verify anon can INSERT into page_views + click_events.

Runs as a build step. Uses the same anon key the browser tracker uses,
tries a single throwaway INSERT into each analytics table, and:

  * prints a small OK line on success
  * on failure, prints a LOUD multi-line warning naming the exact table,
    the HTTP status, and the fix (sql/fix_page_views_rls_2026_09_07.sql)

Rationale: on 2026-09-07 we discovered that page_views INSERTs had been
silently failing for weeks - the browser tracker's .catch() swallowed
every 401 and no one saw it. This script surfaces that class of break
into every rebuild-deploy run, so the next time RLS drifts the fix hits
the ops window instead of accumulating for weeks.

Uses only the anon key (public). No service-role secrets required, no
side effects beyond one probe row per table (they carry
session_id='__health_probe__' so the dashboard can filter them out).

Exit code is intentionally 0 either way - a broken policy MUST NOT
break the deploy, only surface loudly.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error


def probe(url, key, table, row):
    """Insert one row via PostgREST. Return (ok: bool, status: int, body: str)."""
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}",
        data=json.dumps(row).encode("utf-8"),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return (resp.status < 300, resp.status, "")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        return (False, e.code, body)
    except Exception as e:
        return (False, 0, f"{type(e).__name__}: {e}")


def main():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        print("analytics_health: SUPABASE_URL/SUPABASE_ANON_KEY not set - skipping")
        return
    marker = f"__health_probe__/{int(time.time())}"
    probes = [
        ("page_views",
         {"page": "/__health__", "referrer": None,
          "session_id": marker, "host": "health.mygoldrates.com"}),
        ("click_events",
         {"page": "/__health__", "target": "__health__",
          "session_id": marker}),
    ]
    broken = []
    for table, row in probes:
        ok, status, body = probe(url, key, table, row)
        if ok:
            print(f"analytics_health: {table} INSERT ok ({status})")
        else:
            broken.append((table, status, body))
            print(f"analytics_health: {table} INSERT FAILED "
                  f"({status}): {body[:200]}")
    if broken:
        rule = "!" * 78
        print("\n" + rule)
        print("ANALYTICS RLS BREAK - anon key cannot INSERT the tables named "
              "above. Every")
        print("browser pageview/click is being dropped SILENTLY (the client "
              "swallows the")
        print("401). The dashboard will read as if the site has no traffic "
              "until fixed.")
        print("")
        print("Fix: open Supabase SQL Editor, paste and run:")
        print("    sql/fix_page_views_rls_2026_09_07.sql")
        print("(idempotent - safe to re-run any time).")
        print(rule + "\n")
        # Exit 0 anyway - do not break the deploy.


if __name__ == "__main__":
    main()
    sys.exit(0)
