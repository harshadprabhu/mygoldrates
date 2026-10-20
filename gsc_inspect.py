"""Google's index status for every page in the live sitemap.xml (read-only).

    python gsc_inspect.py

Search Console's API cannot request indexing - that button exists only in
the Search Console website - but it can say, for each URL, whether Google
knows it, has crawled it, and indexed it. This lists every sitemap URL with
that status, grouped, so the owner knows exactly which pages still need
"Request indexing" pressed. Uses the URL Inspection API (2,000 a day per
property; the sitemap has about a hundred).
"""
import json
import os
import re
from collections import defaultdict

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

SITEMAP = "https://mygoldrates.com/sitemap.xml"


def main():
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    site = next(s["siteUrl"] for s in svc.sites().list().execute().get("siteEntry", [])
                if "mygoldrates" in s["siteUrl"])
    urls = re.findall(r"<loc>([^<]+)</loc>",
                      requests.get(SITEMAP, timeout=30).text)
    groups = defaultdict(list)
    for u in urls:
        try:
            r = svc.urlInspection().index().inspect(
                body={"inspectionUrl": u, "siteUrl": site}).execute()
            s = r["inspectionResult"].get("indexStatusResult", {})
            cov = s.get("coverageState", "?")
            crawl = (s.get("lastCrawlTime") or "never")[:10]
        except Exception as e:
            cov, crawl = f"error {type(e).__name__}", "-"
        groups[cov].append((u.replace("https://mygoldrates.com", "") or "/", crawl))
    print(f"{len(urls)} sitemap URLs")
    for cov, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"\n== {cov}: {len(rows)} ==")
        for path, crawl in sorted(rows):
            print(f"  {path}  last crawled {crawl}")


if __name__ == "__main__":
    main()
