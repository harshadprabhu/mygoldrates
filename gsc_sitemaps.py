"""List, and optionally clean up, the sitemaps registered in Search Console.

    python gsc_sitemaps.py list
    python gsc_sitemaps.py cleanup

cleanup removes every registered sitemap that is not one of the site's own
real sitemaps (SITE_SITEMAPS below), then submits sitemap.xml so Google
re-reads it. It never touches the real ones. Built for the entry
"sitemap.xmlSitemap1 Aug 2026..." - text pasted into the Add-a-sitemap box,
which the Search Console UI would not let the owner remove.
"""
import json
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

SITE_SITEMAPS = {
    "https://mygoldrates.com/sitemap.xml",
    "https://mygoldrates.com/sitemap_main.xml",
    "https://mygoldrates.com/sitemap_cities.xml",
    "https://mygoldrates.com/sitemap_daily.xml",
    "https://mygoldrates.com/sitemap_news.xml",
}


def main(mode):
    scope = ("https://www.googleapis.com/auth/webmasters" if mode == "cleanup"
             else "https://www.googleapis.com/auth/webmasters.readonly")
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"]), scopes=[scope])
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    site = next(s for s in svc.sites().list().execute().get("siteEntry", [])
                if "mygoldrates" in s["siteUrl"])
    print(f"property {site['siteUrl']}  permission {site['permissionLevel']}")
    entries = svc.sitemaps().list(siteUrl=site["siteUrl"]).execute().get("sitemap", [])
    print(f"{len(entries)} registered sitemap(s):")
    for e in entries:
        tag = "ours" if e["path"] in SITE_SITEMAPS else "NOT OURS"
        print(f"  [{tag}] {e['path']!r}  errors={e.get('errors')} "
              f"lastDownloaded={e.get('lastDownloaded', 'never')}")
    if mode != "cleanup":
        return
    for e in entries:
        if e["path"] in SITE_SITEMAPS:
            continue
        try:
            svc.sitemaps().delete(siteUrl=site["siteUrl"], feedpath=e["path"]).execute()
            print(f"REMOVED {e['path']!r}")
        except Exception as ex:
            print(f"COULD NOT REMOVE {e['path']!r}: {str(ex)[:300]}")
    try:
        svc.sitemaps().submit(siteUrl=site["siteUrl"],
                              feedpath="https://mygoldrates.com/sitemap.xml").execute()
        print("SUBMITTED https://mygoldrates.com/sitemap.xml")
    except Exception as ex:
        print(f"COULD NOT SUBMIT sitemap.xml: {str(ex)[:300]}")
    left = svc.sitemaps().list(siteUrl=site["siteUrl"]).execute().get("sitemap", [])
    print("now registered:", [e["path"] for e in left])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "list")
