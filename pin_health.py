#!/usr/bin/env python3
"""Health check: report brands whose configured rate_url has gone dead.

Runs as a step in the rates workflow, after scrape.py. Reads today's rows
with the ANON key only (both tables are public-readable) and prints a
report. Exit code is intentionally always 0 - a stale pin must never break
the scrape or the deploy, only become visible.

Why this exists
---------------
scrape_brand() has a deliberate recovery chain: configured rate_url ->
CANDIDATE_PATHS on the same domain -> discover_products(). That chain is
good; a brand whose product handle is retired keeps publishing a real rate
instead of collapsing to `estimated`. The problem is that it is *silent*.

On 2026-09-13 two brands were found running on fallbacks with nothing
anywhere saying so:

  * Senco - the pinned 999.9 coin handle was renamed (9999 -> 999.9) and
    started 404-ing. discover_products() picked some other gold product and
    published `discovered/static/goldvalue`: one purity, basis_confirmed
    False. That is the exact fragile jewellery-ladder shape the coin pin was
    added to replace, quietly reinstated. It read 15,460.36 against the
    coin's true 15,460.00 - so no drift or outlier gate could have caught
    it. The number was right; the source was unpinned and free to drift.

  * Ranka - /gold-rate-today returns a hard 404, but their metal-rates strip
    is site-wide and renders on the 404 page too, so extract_rows kept
    returning a correct ladder off a page the server calls "not found".

Neither failure was detectable from the rate value. Both are obvious from
the `method` column, which nobody was reading. So read it here.

What it flags
-------------
  STALE PIN   method starts with `discovered/` - the configured rate_url is
              dead and the brand is publishing off whatever path discovery
              found today. The rate may well be right; the source is not
              pinned, so it can move without warning. Repair the rate_url
              in seed_brands.py and run seed-brands.
  NOT LIVE    an active brand with no published row today (quarantined,
              estimated, or missing entirely) - it is absent from the board
              right now. The line also reports how many of the last 7 days
              the brand DID publish, so a failed run mid-day is not mistaken
              for a dead source.

A brand recovering via CANDIDATE_PATHS rather than discover_products keeps
a plain `static/`|`rendered/` method and so is not flagged here; that case
is caught by the rate_url in the row differing from the configured one,
reported as a NOTE.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta


def get(url, key, path):
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get(
        "SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("pin-health: SUPABASE_URL / key not set, skipping")
        return 0

    today = date.today().isoformat()
    try:
        brands = get(url, key, "brands?select=id,slug,name,rate_url,active"
                               "&active=eq.true")
        # Also the previous week, so a brand that is missing RIGHT NOW can be
        # told apart from one that is actually broken. rates.yml re-scrapes
        # every 30 minutes and upserts the day's row, so a brand can sit at
        # `estimated` mid-morning and be `published` by noon. Reporting that
        # snapshot as "absent from the board" with no history reads as a
        # standing outage - it misled the author of this script into saying
        # exactly that about Tanishq, which had in fact published on 40
        # consecutive days.
        since = (date.today() - timedelta(days=7)).isoformat()
        hist = get(url, key, f"rates?rate_date=gte.{since}&rate_date=lt.{today}"
                             "&status=eq.published"
                             "&select=brand_id,rate_date")
        rates = get(url, key, f"rates?rate_date=eq.{today}"
                              "&select=brand_id,canonical_24k_pre_gst,status,"
                              "method,purities_found,rate_url")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"pin-health: could not read Supabase ({e}), skipping")
        return 0

    by_id = {r["brand_id"]: r for r in rates}
    stale, notlive, moved = [], [], []

    for b in sorted(brands, key=lambda x: x["slug"]):
        r = by_id.get(b["id"])
        if not r or r["status"] != "published":
            notlive.append((b, r))
            continue
        method = r.get("method") or ""
        if method.startswith("discovered/"):
            stale.append((b, r))
        elif b.get("rate_url") and r.get("rate_url") \
                and r["rate_url"] != b["rate_url"]:
            moved.append((b, r))

    print(f"pin-health {today}: {len(brands)} active brands, "
          f"{sum(1 for r in rates if r['status'] == 'published')} published")

    if stale:
        print("")
        print("!" * 68)
        print(f"!! STALE PIN: {len(stale)} brand(s) publishing from path "
              f"discovery.")
        print("!! Their configured rate_url is dead. The rate may be correct")
        print("!! today, but the source is unpinned and can move silently.")
        print("!! Fix: repair rate_url in seed_brands.py, run seed-brands.")
        for b, r in stale:
            print(f"!!   {b['slug']:<14} {float(r['canonical_24k_pre_gst']):>9.2f}"
                  f"  {r['method']}")
            print(f"!!     configured: {b['rate_url']}")
            print(f"!!     actually used: {r.get('rate_url')}")
        print("!" * 68)

    if moved:
        print("")
        for b, r in moved:
            print(f"NOTE {b['slug']:<14} recovered via a different path than "
                  f"its configured rate_url")
            print(f"       configured: {b['rate_url']}")
            print(f"       used:       {r.get('rate_url')}")

    if notlive:
        print("")
        recent = {}
        for h in hist:
            recent.setdefault(h["brand_id"], set()).add(h["rate_date"])
        for b, r in notlive:
            st = r["status"] if r else "no row"
            days = len(recent.get(b["id"], ()))
            if days >= 5:
                # Published nearly every day this week, so this is almost
                # certainly a failed run that a later one will fix, not an
                # outage. Say so, rather than implying the brand is gone.
                note = (f"published {days}/7 of the last 7 days - most likely a "
                        f"transient run failure; re-check after the next scrape")
            elif days:
                note = f"published only {days}/7 of the last 7 days - flaky source"
            else:
                note = "NOT published at all in the last 7 days - genuinely broken"
            print(f"NOT LIVE {b['slug']:<14} {st} - {note}")

    if not stale and not moved and not notlive:
        print("pin-health: OK - every active brand published from its "
              "configured source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
