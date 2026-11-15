#!/usr/bin/env python3
"""Search Console history (owner, 15 Nov 2026): "we used to see queries like
'gold rate today' and 'gold rate today in mumbai', now none". Prints, for
every property the account can read: weekly clicks/impressions over the
16 months Google keeps, the best 4 weeks vs the last 4 weeks (top queries
and top pages), and which page used to rank for the key searches.

Read-only. Output goes to job annotations (public repo: no commits)."""
import collections
import datetime as dt
import json
import os
import sys

KEY_Q = ["gold rate today", "gold rate today in mumbai", "today gold rate",
         "gold rate in mumbai", "gold price today", "22k gold rate today"]


def service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    info = json.loads(os.environ["GSC_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/webmasters"])
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def q(svc, site, start, end, dims, limit=25000, filters=None):
    body = {"startDate": str(start), "endDate": str(end), "dimensions": dims,
            "rowLimit": limit, "dataState": "all"}
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]
    return svc.searchanalytics().query(siteUrl=site, body=body).execute().get("rows", [])


def short(u):
    for p in ("https://mygoldrates.com", "https://www.mygoldrates.com", "http://mygoldrates.com"):
        if u.startswith(p):
            return u[len(p):] or "/"
    return u


def main():
    svc = service()
    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=485)
    sites = svc.sites().list().execute().get("siteEntry", [])
    print("PROPERTIES:", [(s["siteUrl"], s["permissionLevel"]) for s in sites])
    for s in sites:
        site = s["siteUrl"]
        print(f"\n######## {site} ########")
        try:
            days = q(svc, site, start, end, ["date"])
        except Exception as e:
            print("  ", type(e).__name__, str(e)[:200]); continue
        if not days:
            print("  no data"); continue
        wk = collections.OrderedDict()
        for r in days:
            d = dt.date.fromisoformat(r["keys"][0]); k = d - dt.timedelta(days=d.weekday())
            a = wk.setdefault(k, [0, 0, 0.0])
            a[0] += r["clicks"]; a[1] += r["impressions"]; a[2] += r["position"] * r["impressions"]
        # which form of the address carried the impressions, by month
        import re as _re
        pr = q(svc, site, start, end, ["date", "page"], 25000)
        form = collections.defaultdict(collections.Counter)
        for r in pr:
            u = r["keys"][1]
            host = _re.match(r"https?://[^/]+", u).group(0)
            kind = host + (" .html" if u.endswith(".html") else "") + (" ?query" if "?" in u else "")
            form[r["keys"][0][:7]][kind] += r["impressions"]
        print("== IMPRESSIONS BY ADDRESS FORM, BY MONTH ==")
        for m in sorted(form):
            print(f"  {m}: " + ", ".join(f"{k}={v}" for k, v in form[m].most_common()))
        print("== WEEKLY (week of, clicks, impressions, avg pos) ==")
        for k, (c, i, pw) in wk.items():
            print(f"  {k} c={c:>4} i={i:>6} pos={pw / i if i else 0:5.1f}")
        # best 28 days by impressions
        series = [(dt.date.fromisoformat(r["keys"][0]), r["impressions"]) for r in days]
        series.sort()
        best, bs = 0, None
        for j in range(len(series)):
            w = sum(i for d, i in series if series[j][0] <= d < series[j][0] + dt.timedelta(days=28))
            if w > best:
                best, bs = w, series[j][0]
        windows = [("BEST 28 DAYS", bs, bs + dt.timedelta(days=27)),
                   ("LAST 28 DAYS", end - dt.timedelta(days=27), end)]
        for name, a, b in windows:
            print(f"\n== {name} {a}..{b} ==")
            for dim, n in (("query", 30), ("page", 20), ("country", 5), ("device", 3)):
                rows = sorted(q(svc, site, a, b, [dim], 1000), key=lambda r: -r["impressions"])
                tot = len(rows)
                print(f" -- top {dim} ({tot} distinct) --")
                for r in rows[:n]:
                    print(f"  i={r['impressions']:>5} c={r['clicks']:>3} pos={r['position']:5.1f} | {short(r['keys'][0])}")
        # are the pages that carried the traffic still in Google's index?
        a, b = windows[0][1], windows[0][2]
        top = sorted(q(svc, site, a, b, ["page"], 1000), key=lambda r: -r["impressions"])[:25]
        print("\n== BEST-WINDOW PAGES: INDEX STATUS NOW ==")
        for r in top[:18]:
            u = r["keys"][0]
            try:
                ix = svc.urlInspection().index().inspect(body={"inspectionUrl": u, "siteUrl": site}).execute()
                ix = ix.get("inspectionResult", {}).get("indexStatusResult", {})
                gc = ix.get("googleCanonical")
                print(f"  {u} | {ix.get('coverageState')} | crawled={str(ix.get('lastCrawlTime'))[:10]}"
                      + (f" | google canonical={short(gc)}" if gc and gc != u else ""))
            except Exception as e:
                print(f"  {short(u)} | {type(e).__name__}: {str(e)[:100]}")
        print("\n== KEY SEARCHES BY MONTH (impressions, pos, top page) ==")
        for kq in KEY_Q:
            rows = q(svc, site, start, end, ["date", "page"], 25000,
                     [{"dimension": "query", "operator": "equals", "expression": kq}])
            mon = collections.defaultdict(lambda: [0, 0.0, collections.Counter()])
            for r in rows:
                m = r["keys"][0][:7]; a = mon[m]
                a[0] += r["impressions"]; a[1] += r["position"] * r["impressions"]; a[2][short(r["keys"][1])] += r["impressions"]
            print(f" [{kq}] " + ("; ".join(f"{m}: i={a[0]} pos={a[1]/a[0]:.0f} {a[2].most_common(1)[0][0]}"
                                          for m, a in sorted(mon.items())) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
