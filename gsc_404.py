"""Which addresses Google knows return 404 now (read-only).

Search Console's "Not found (404)" report is not exposed by its API, so
this rebuilds it: every page that appeared in Google search in the last
16 months (Search Analytics, by page), plus every sitemap URL, each
fetched now without following redirects. Prints the ones that answer 404
(or anything other than 200 / 301 / 308), grouped by pattern, so they can
be redirected to the right page.
"""
import json
import os
import re
from collections import defaultdict
from datetime import date, timedelta

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build


def main():
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    site = next(s["siteUrl"] for s in svc.sites().list().execute().get("siteEntry", [])
                if "mygoldrates" in s["siteUrl"])
    urls, start = set(), 0
    while True:
        r = svc.searchanalytics().query(siteUrl=site, body={
            "startDate": (date.today() - timedelta(days=480)).isoformat(),
            "endDate": date.today().isoformat(), "dimensions": ["page"],
            "rowLimit": 25000, "startRow": start}).execute()
        rows = r.get("rows", [])
        urls |= {x["keys"][0] for x in rows}
        if len(rows) < 25000:
            break
        start += 25000
    n_search = len(urls)
    for sm in ("sitemap.xml",):
        urls |= set(re.findall(r"<loc>([^<]+)</loc>",
                               requests.get(f"https://mygoldrates.com/{sm}", timeout=30).text))
    bad = defaultdict(list)
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    for u in sorted(urls):
        try:
            code = s.get(u, allow_redirects=False, timeout=20).status_code
        except Exception as e:
            code = type(e).__name__
        if code not in (200, 301, 308):
            path = re.sub(r"^https?://[^/]+", "", u) or "/"
            pat = re.sub(r"\d{1,2}-[a-z]{3}-\d{4}", "<date>", path)
            pat = re.sub(r"/gold-rate-[a-z-]+-<date>", "/gold-rate-<place>-<date>", pat)
            bad[(code, pat)].append(u)
    print(f"{len(urls)} addresses checked ({n_search} from Google search, rest from sitemap)")
    print(f"{sum(len(v) for v in bad.values())} do not answer 200/301/308")
    for (code, pat), us in sorted(bad.items(), key=lambda kv: -len(kv[1])):
        print(f"\n[{code}] {pat}  x{len(us)}")
        for u in us[:8]:
            print("   ", u)


if __name__ == "__main__":
    main()
