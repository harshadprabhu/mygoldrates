"""Search Console diagnosis: when did search traffic fall, for which queries
and pages, and what does Google say about the pages that matter.

Read-only. Prints a plain-text report. The workflow forwards it as job
annotations rather than committing it, because this repository is public
and search queries are business data.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

SITE_BASE = "https://mygoldrates.com/"
INSPECT = [
    "", "gold-rate-today-in-surat", "gold-rate-today-in-mumbai",
    "gold-rate-today-in-chennai", "gold-rate-today-in-pune",
    "gold-rate-today-in-delhi", "making-charges-comparison",
    "dhanteras-gold-report-2026", "calculators", "gold-loan-calculator",
    "news", "jewellers-digest",
]


def q(svc, site, start, end, dims, limit=25000, filters=None):
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
            "dimensions": dims, "rowLimit": limit}
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]
    return svc.searchanalytics().query(siteUrl=site, body=body).execute().get("rows", [])


def main():
    info = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    sites = svc.sites().list().execute().get("siteEntry", [])
    print("PROPERTIES:", ", ".join(f"{s['siteUrl']} ({s['permissionLevel']})" for s in sites))
    site = next((s["siteUrl"] for s in sites if "mygoldrates" in s["siteUrl"]), None)
    if not site:
        print("NO mygoldrates PROPERTY VISIBLE"); return
    print("USING:", site)

    today = date.today()

    # 1. Weekly trend over ~6 months - when did it change?
    rows = q(svc, site, today - timedelta(days=182), today, ["date"])
    wk = defaultdict(lambda: [0, 0, 0.0, 0])
    for r in rows:
        d = date.fromisoformat(r["keys"][0])
        monday = d - timedelta(days=d.weekday())
        w = wk[monday]
        w[0] += r["clicks"]; w[1] += r["impressions"]
        w[2] += r["position"] * r["impressions"]; w[3] += 1
    print("\n== WEEKLY SEARCH TRAFFIC (week starting, clicks, impressions, avg pos) ==")
    for m in sorted(wk):
        c, i, pw, n = wk[m]
        print(f"{m}  clicks={c:5}  impr={i:7}  pos={pw/i if i else 0:5.1f}  days={n}")
    # Discover, Google News and image results are reported separately from
    # web search, and Discover and the Google app usually arrive with no
    # referrer - in the site's own analytics they look like direct visits.
    for st in ("discover", "googleNews", "news", "image"):
        try:
            body = {"startDate": (today - timedelta(days=120)).isoformat(),
                    "endDate": today.isoformat(), "dimensions": ["date"],
                    "type": st, "rowLimit": 25000}
            rs = svc.searchanalytics().query(siteUrl=site, body=body).execute().get("rows", [])
        except Exception as e:
            print(f"\n== {st.upper()}: ERROR {str(e)[:120]}"); continue
        w2 = defaultdict(lambda: [0, 0])
        for r in rs:
            d = date.fromisoformat(r["keys"][0]); m = d - timedelta(days=d.weekday())
            w2[m][0] += r["clicks"]; w2[m][1] += r["impressions"]
        print(f"\n== {st.upper()} WEEKLY (clicks, impressions) - {len(rs)} days with data ==")
        for m in sorted(w2):
            print(f"{m}  clicks={w2[m][0]:5}  impr={w2[m][1]:7}")
        if st == "discover" and rs:
            pg = svc.searchanalytics().query(siteUrl=site, body={
                **body, "dimensions": ["page"], "rowLimit": 15}).execute().get("rows", [])
            for r in pg:
                print(f"   {r['clicks']:5} clicks  {r['impressions']:7} impr  {r['keys'][0].replace(SITE_BASE, '/')}")

    print("\n== LAST 21 DAYS, DAILY ==")
    for r in rows[-21:]:
        print(f"{r['keys'][0]}  clicks={r['clicks']:4}  impr={r['impressions']:6}  pos={r['position']:5.1f}")

    # 2. Queries: last 28d vs the 28d before
    a_end = today - timedelta(days=2); a_start = a_end - timedelta(days=27)
    b_end = a_start - timedelta(days=1); b_start = b_end - timedelta(days=27)
    now = {r["keys"][0]: r for r in q(svc, site, a_start, a_end, ["query"])}
    before = {r["keys"][0]: r for r in q(svc, site, b_start, b_end, ["query"])}
    print(f"\n== QUERIES: {b_start}..{b_end}  vs  {a_start}..{a_end} ==")
    print(f"distinct queries with impressions: before={len(before)}  now={len(now)}")
    keys = sorted(set(now) | set(before),
                  key=lambda k: -(before.get(k, {}).get("impressions", 0) + now.get(k, {}).get("impressions", 0)))
    for k in keys[:30]:
        b = before.get(k, {}); n = now.get(k, {})
        print(f"impr {b.get('impressions',0):6} -> {n.get('impressions',0):6} | clicks {b.get('clicks',0):4} -> {n.get('clicks',0):4} | "
              f"pos {b.get('position',0):5.1f} -> {n.get('position',0):5.1f} | {k[:60]}")

    # 3. Pages: same comparison
    nowp = {r["keys"][0]: r for r in q(svc, site, a_start, a_end, ["page"])}
    befp = {r["keys"][0]: r for r in q(svc, site, b_start, b_end, ["page"])}
    print(f"\n== PAGES with impressions: before={len(befp)}  now={len(nowp)} ==")
    pk = sorted(set(nowp) | set(befp),
                key=lambda k: -(befp.get(k, {}).get("impressions", 0) + nowp.get(k, {}).get("impressions", 0)))
    for k in pk[:30]:
        b = befp.get(k, {}); n = nowp.get(k, {})
        print(f"impr {b.get('impressions',0):6} -> {n.get('impressions',0):6} | clicks {b.get('clicks',0):4} -> {n.get('clicks',0):4} | "
              f"pos {b.get('position',0):5.1f} -> {n.get('position',0):5.1f} | {k.replace(SITE_BASE,'/')}")

    # 3b. Every page with impressions over 90 days, for deciding which pages
    # earn their place in the index.
    allp = q(svc, site, today - timedelta(days=90), today, ["page"])
    print(f"\n== ALL PAGES WITH IMPRESSIONS, LAST 90 DAYS ({len(allp)}) ==")
    for r in sorted(allp, key=lambda r: -r["impressions"]):
        print(f"impr {r['impressions']:6} clicks {r['clicks']:4} pos {r['position']:5.1f} | "
              f"{r['keys'][0].replace(SITE_BASE, '/')}")

    # 4. Device and country split, last 28d
    for dim in ("device", "country"):
        rs = q(svc, site, a_start, a_end, [dim], limit=8)
        print(f"\n== BY {dim.upper()} (last 28d) ==")
        for r in rs:
            print(f"{r['keys'][0]:10} clicks={r['clicks']:5} impr={r['impressions']:7} pos={r['position']:5.1f}")

    # 5. Google's verdict on the pages that matter
    print("\n== URL INSPECTION ==")
    for path in INSPECT:
        u = SITE_BASE + path
        try:
            r = svc.urlInspection().index().inspect(
                body={"inspectionUrl": u, "siteUrl": site}).execute()
            res = r["inspectionResult"].get("indexStatusResult", {})
            mob = r["inspectionResult"].get("mobileUsabilityResult", {})
            print(f"/{path}")
            print(f"   verdict={res.get('verdict')} | coverage={res.get('coverageState')}")
            print(f"   indexing={res.get('indexingState')} robots={res.get('robotsTxtState')} "
                  f"fetch={res.get('pageFetchState')} lastCrawl={res.get('lastCrawlTime','never')}")
            print(f"   googleCanonical={res.get('googleCanonical')} | userCanonical={res.get('userCanonical')}")
            if res.get("referringUrls"):
                print(f"   referring={res['referringUrls'][:2]}")
            if mob.get("verdict"):
                print(f"   mobile={mob.get('verdict')} {[i.get('issueType') for i in mob.get('issues',[])]}")
        except Exception as e:
            print(f"/{path}\n   ERROR {str(e)[:200]}")

    # 6. Sitemaps
    print("\n== SITEMAPS ==")
    try:
        for e in svc.sitemaps().list(siteUrl=site).execute().get("sitemap", []):
            cs = "; ".join(f"{c.get('type')} submitted={c.get('submitted')} indexed={c.get('indexed')}"
                           for c in e.get("contents", []))
            print(f"{e.get('path')}  lastDownloaded={e.get('lastDownloaded','never')} "
                  f"errors={e.get('errors')} warnings={e.get('warnings')} pending={e.get('isPending')} | {cs}")
    except Exception as ex:
        print("ERROR", ex)


if __name__ == "__main__":
    main()
