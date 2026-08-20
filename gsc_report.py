"""One-off Search Console diagnostic - NOT part of the regular scrape/build
pipeline. Run manually via the gsc-report.yml workflow when investigating
search performance.

What this can and can't see, since it matters for how to read the output:
- The Search Console UI's "Page indexing" report (Crawled-not-indexed,
  Duplicate-without-canonical, etc.) has NO bulk API equivalent - Google
  doesn't expose it. The closest substitute here is urlInspection().index()
  per URL (one at a time, real-time verdict) on a handful of representative
  pages, not a full-site breakdown.
- Search Analytics (clicks/impressions/position) IS fully queryable and is
  what actually tells us whether performance moved and when.
"""
import json
import os
import sys
from datetime import date, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def main():
    raw = os.environ.get("GSC_SERVICE_ACCOUNT_JSON")
    if not raw:
        print("GSC_SERVICE_ACCOUNT_JSON not set", file=sys.stderr)
        sys.exit(1)
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES)
    svc = build("searchconsole", "v1", credentials=creds)

    sites = svc.sites().list().execute().get("siteEntry", [])
    print("=== Accessible properties ===")
    for s in sites:
        print(f"  {s['siteUrl']}  ({s['permissionLevel']})")
    site = next((s["siteUrl"] for s in sites if "mygoldrates" in s["siteUrl"]),
                None)
    if not site:
        print("No mygoldrates property visible to this service account - "
              "check step 6 (Add user) was done on the right property.")
        sys.exit(1)
    print(f"\nUsing property: {site}\n")

    # ---- 1. Performance trend, last 90 days, by date ----
    end = date.today()
    start = end - timedelta(days=90)
    resp = svc.searchanalytics().query(siteUrl=site, body={
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "dimensions": ["date"],
    }).execute()
    rows = resp.get("rows", [])
    print(f"=== Daily performance, last 90 days ({len(rows)} days with data) ===")
    for row in rows:
        d = row["keys"][0]
        print(f"  {d}  clicks={row['clicks']:>5}  impressions={row['impressions']:>6}  "
              f"ctr={row['ctr']:.2%}  avg_pos={row['position']:.1f}")
    if not rows:
        print("  (no rows - either no traffic in this window, or the "
              "property is too new for data yet)")
    print()

    # ---- 2. Per-page breakdown, last 28 days ----
    end2 = date.today()
    start2 = end2 - timedelta(days=28)
    resp2 = svc.searchanalytics().query(siteUrl=site, body={
        "startDate": start2.isoformat(), "endDate": end2.isoformat(),
        "dimensions": ["page"], "rowLimit": 25000,
    }).execute()
    prows = resp2.get("rows", [])
    daily_pages = [r for r in prows if "/news/daily/" in r["keys"][0]]
    recap_pages = [r for r in prows if "/news/recap/" in r["keys"][0]]
    other_pages = [r for r in prows
                   if r not in daily_pages and r not in recap_pages]
    print(f"=== Pages with >=1 impression, last 28 days: {len(prows)} total ===")
    print(f"  /news/daily/*  : {len(daily_pages)} pages "
          f"({sum(r['clicks'] for r in daily_pages)} clicks total)")
    print(f"  /news/recap/*  : {len(recap_pages)} pages "
          f"({sum(r['clicks'] for r in recap_pages)} clicks total)")
    print(f"  everything else: {len(other_pages)} pages "
          f"({sum(r['clicks'] for r in other_pages)} clicks total)")
    print()

    print("=== Top 20 pages by clicks (last 28 days) ===")
    for row in sorted(prows, key=lambda r: -r["clicks"])[:20]:
        print(f"  clicks={row['clicks']:>4}  impr={row['impressions']:>5}  "
              f"pos={row['position']:>5.1f}  {row['keys'][0]}")
    print()

    clicked_stale = sorted(
        [r for r in daily_pages + recap_pages if r["clicks"] > 0],
        key=lambda r: -r["clicks"])
    print(f"=== Daily/recap pages that earned ANY clicks (last 28 days): "
          f"{len(clicked_stale)} ===")
    print("(this is the check that matters most: if any of these are old "
          "pages the index-bloat fix noindexed, that's a real cost, not "
          "just a theoretical one)")
    for row in clicked_stale[:30]:
        print(f"  clicks={row['clicks']:>4}  impr={row['impressions']:>5}  "
              f"{row['keys'][0]}")
    print()

    # ---- 3. URL Inspection spot-check ----
    base = "https://mygoldrates.com/"
    inspect_urls = [
        base,
        base + "gold-rate-today-in-mumbai",
        base + "news/daily/gold-rate-mumbai-27-jul-2026",   # noindexed by the fix
        base + "news/daily/gold-rate-mumbai-20-aug-2026",   # still fresh
        base + "news/recap/daily-recap-1-aug-2026",
    ]
    print("=== URL Inspection (live Google index status per URL) ===")
    for u in inspect_urls:
        try:
            r = svc.urlInspection().index().inspect(body={
                "inspectionUrl": u, "siteUrl": site}).execute()
            res = r["inspectionResult"]["indexStatusResult"]
            print(f"  {u}")
            print(f"    verdict={res.get('verdict')}  "
                  f"coverageState={res.get('coverageState')}  "
                  f"robotsTxtState={res.get('robotsTxtState')}  "
                  f"indexingState={res.get('indexingState')}  "
                  f"lastCrawl={res.get('lastCrawlTime', 'never')}")
        except Exception as e:
            print(f"  {u}\n    ERROR: {e}")
    print()

    # ---- 4. Sitemap processing status ----
    # Read-only (sitemaps.list/get) - the service account's Search Console
    # role is "Restricted" (read-only), so sitemaps.submit() would fail
    # regardless of OAuth scope. Google discovers sitemaps via robots.txt
    # automatically either way; explicit submission mostly just gives GSC UI
    # visibility and a mild nudge to reprocess sooner - not required for
    # indexing to happen, so not worth another permission round-trip unless
    # this check shows something actually wrong.
    print("=== Sitemap processing status ===")
    try:
        sm = svc.sitemaps().list(siteUrl=site).execute()
        entries = sm.get("sitemap", [])
        if not entries:
            print("  No sitemaps registered with Search Console at all.")
        for e in entries:
            print(f"  {e.get('path')}")
            print(f"    lastSubmitted={e.get('lastSubmitted', 'never')}  "
                  f"lastDownloaded={e.get('lastDownloaded', 'never')}  "
                  f"isPending={e.get('isPending')}  isSitemapsIndex={e.get('isSitemapsIndex')}")
            warnings = e.get("warnings", "0")
            errors = e.get("errors", "0")
            print(f"    warnings={warnings}  errors={errors}")
            for content in e.get("contents", []):
                print(f"    type={content.get('type')}  "
                      f"submitted={content.get('submitted')}  "
                      f"indexed={content.get('indexed')}")
    except Exception as ex:
        print(f"  ERROR fetching sitemap status: {ex}")
    print()

    # ---- 5. Manual actions ----
    print("=== Note: Manual Actions has no API - check this yourself at ===")
    print("    https://search.google.com/search-console/manual-actions")
    print("    (a manual action is a different, more severe class of "
          "problem than anything above, and I have no way to check it)")


if __name__ == "__main__":
    main()
