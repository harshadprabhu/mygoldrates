#!/usr/bin/env python3
"""Search Console: remove and re-submit the sitemaps, then inspect the key
pages (owner, 6 Nov 2026).

Google had not read the sitemaps since early October and listed most key
pages as "unknown to Google". Re-adding a sitemap makes Google fetch it
afresh. The URL Inspection API then shows, page by page, whether Google
has crawled and indexed it, and why not.

"Request indexing" (the button in Search Console) has no API: Google's
Indexing API is only for job postings and livestreams, and using it for
other pages breaks its terms. That step stays in the Search Console UI.

    python gsc_fix.py            # inspect only
    python gsc_fix.py resubmit   # remove + re-submit sitemaps, then inspect

Needs GSC_SERVICE_ACCOUNT_JSON (the account is a full user on the
property, which may manage sitemaps).
"""
import json
import os
import sys

SITE_URL = "https://mygoldrates.com"
SITEMAPS = ["sitemap.xml", "sitemap_main.xml", "sitemap_cities.xml",
            "sitemap_daily.xml", "sitemap_news.xml"]
KEY_PAGES = ["/", "/gold-rate-today-in-mumbai", "/gold-rate-today-in-chennai",
             "/gold-rate-today-in-bengaluru", "/gold-rate-today-in-delhi",
             "/gold-rate-today-in-hyderabad", "/gold-rate-today-in-thrissur",
             "/tanishq-gold-rate-today", "/kalyan-jewellers-gold-rate-today",
             "/making-charges-comparison", "/gold-coin-price-today",
             "/gold-price-gap-report", "/gold-rate-widget", "/hi/gold-rate-today",
             "/ta/gold-rate-today", "/gold-rate-history", "/gold-rate-by-jeweller"]


def service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    info = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/webmasters"])
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def list_sitemaps(svc, site):
    for e in svc.sitemaps().list(siteUrl=site).execute().get("sitemap", []):
        print(f"  {e.get('path')}  submitted={str(e.get('lastSubmitted'))[:10]} "
              f"downloaded={str(e.get('lastDownloaded'))[:10]} pending={e.get('isPending')} "
              f"errors={e.get('errors')} warnings={e.get('warnings')} "
              + " ".join(f"{c.get('type')}:{c.get('submitted')}/{c.get('indexed')}"
                         for c in e.get("contents") or []))


def main():
    if not os.environ.get("GSC_SERVICE_ACCOUNT_JSON"):
        print("GSC_SERVICE_ACCOUNT_JSON is not set"); return 1
    svc = service()
    sites = svc.sites().list().execute().get("siteEntry", [])
    site = next((s["siteUrl"] for s in sites if "mygoldrates" in s["siteUrl"]), None)
    print("PROPERTY:", site, next((s["permissionLevel"] for s in sites if s["siteUrl"] == site), ""))
    if not site:
        return 1
    print("== SITEMAPS BEFORE ==")
    list_sitemaps(svc, site)
    if sys.argv[1:2] == ["resubmit"]:
        print("== REMOVE AND RE-SUBMIT ==")
        old = [e["path"] for e in svc.sitemaps().list(siteUrl=site).execute().get("sitemap", [])]
        for path in old:
            try:
                svc.sitemaps().delete(siteUrl=site, feedpath=path).execute()
                print(f"  removed {path}")
            except Exception as e:
                print(f"  remove {path}: {type(e).__name__}: {str(e)[:160]}")
        for sm in SITEMAPS:
            path = f"{SITE_URL}/{sm}"
            try:
                svc.sitemaps().submit(siteUrl=site, feedpath=path).execute()
                print(f"  submitted {path}")
            except Exception as e:
                print(f"  submit {path}: {type(e).__name__}: {str(e)[:160]}")
        print("== SITEMAPS AFTER ==")
        list_sitemaps(svc, site)
    print("== KEY PAGES (URL Inspection) ==")
    for p in KEY_PAGES:
        u = SITE_URL + p
        try:
            r = svc.urlInspection().index().inspect(
                body={"inspectionUrl": u, "siteUrl": site}).execute()
            ix = r.get("inspectionResult", {}).get("indexStatusResult", {})
            print(f"  {p}  {ix.get('verdict')} | {ix.get('coverageState')} | "
                  f"crawled={str(ix.get('lastCrawlTime'))[:10]} fetch={ix.get('pageFetchState')} "
                  f"robots={ix.get('robotsTxtState')} indexing={ix.get('indexingState')}"
                  + (f" | google canonical={ix.get('googleCanonical')}"
                     if ix.get("googleCanonical") and ix.get("googleCanonical") != u else ""))
        except Exception as e:
            print(f"  {p}  {type(e).__name__}: {str(e)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
