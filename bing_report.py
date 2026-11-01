#!/usr/bin/env python3
"""Bing Webmaster Tools: what Bing (and so ChatGPT search and Copilot, which
draw on it) knows about the site - crawl stats, crawl issues, the searches the
site shows for, and how key pages stand. Read-only, except `submit`, which
sends the key pages to Bing (within its daily allowance).

    python bing_report.py            # report
    python bing_report.py submit     # report, then submit KEY_PAGES

Needs BING_WEBMASTER_KEY. The key goes in the query string, so no request URL
is ever printed: errors are reported by method name only.
"""
import json
import os
import sys

import requests

API = "https://ssl.bing.com/webmaster/api.svc/json/"
SITE = "https://mygoldrates.com/"
KEY_PAGES = [SITE] + [SITE + p for p in (
    "compare-jewellers-gold-rate", "gold-rate-by-jeweller", "making-charges-comparison", "gold-rate-around-the-world",
    "gold-rate-today-in-dubai", "gold-offers-today", "gold-rate-near-me", "calculators", "news",
    "jewellers-digest", "gold-rate-today-in-mumbai", "gold-rate-today-in-delhi", "gold-rate-today-in-chennai",
    "gold-rate-today-in-bengaluru", "gold-rate-today-in-pune", "gold-rate-today-in-hyderabad",
    "gold-rate-today-in-kolkata", "gold-rate-today-in-ahmedabad", "tanishq-gold-rate-today",
    "kalyan-jewellers-gold-rate-today", "malabar-gold-rate-today")]


def call(method, key, params=None, body=None):
    q = {"apikey": key, **(params or {})}
    try:
        r = (requests.post(API + method, params=q, json=body, timeout=40) if body is not None
             else requests.get(API + method, params=q, timeout=40))
    except requests.RequestException as e:
        return None, f"{method}: {type(e).__name__}"
    if not r.ok:
        return None, f"{method}: HTTP {r.status_code} {r.text[:200].replace(key, '***')}"
    try:
        return r.json().get("d"), ""
    except ValueError:
        return None, f"{method}: not JSON"


def date(v):
    """Bing's "/Date(1730000000000)/" -> YYYY-MM-DD."""
    import re
    from datetime import datetime, timezone
    m = re.search(r"\d{10,13}", str(v or ""))
    return datetime.fromtimestamp(int(m.group()) / 1000, timezone.utc).strftime("%Y-%m-%d") if m else str(v)


def main():
    key = os.environ.get("BING_WEBMASTER_KEY", "").strip()
    if not key:
        print("BING_WEBMASTER_KEY is not set"); return 1
    sites, e = call("GetUserSites", key)
    print("== BING SITES ==")
    for s in sites or []:
        print(f"  {s.get('Url')}  verified={s.get('IsVerified')}")
    if e:
        print("  " + e)
    site = next((s["Url"] for s in sites or [] if "mygoldrates.com" in s.get("Url", "")), SITE)
    p = {"siteUrl": site}

    cs, e = call("GetCrawlStats", key, p)
    print("\n== CRAWL STATS (most recent days) ==" + (" " + e if e else ""))
    for d in (cs or [])[-14:]:
        print(f"  {date(d.get('Date'))}  crawled={d.get('CrawledPages')} errors={d.get('CrawlErrors')} "
              f"inIndex={d.get('InIndex')} inLinks={d.get('InLinks')} blockedByRobots={d.get('BlockedByRobotsTxt')} "
              f"5xx={d.get('Code5xx')} 4xx={d.get('Code4xx')}")

    ci, e = call("GetCrawlIssues", key, p)
    print("\n== CRAWL ISSUES ==" + (" " + e if e else ""))
    for i in (ci or [])[:30]:
        print(f"  {i.get('Url')}  issue={i.get('Issues')} http={i.get('HttpCode')}")

    rt, e = call("GetRankAndTrafficStats", key, p)
    print("\n== SEARCH TRAFFIC (recent days) ==" + (" " + e if e else ""))
    for d in (rt or [])[-21:]:
        print(f"  {date(d.get('Date'))}  impressions={d.get('Impressions')} clicks={d.get('Clicks')}")

    qs, e = call("GetQueryStats", key, p)
    print("\n== SEARCHES THE SITE SHOWS FOR ==" + (" " + e if e else ""))
    for q in sorted(qs or [], key=lambda q: -(q.get("Impressions") or 0))[:40]:
        print(f"  impr={q.get('Impressions'):>5} clicks={q.get('Clicks'):>3} pos={q.get('AvgImpressionPosition')} | {q.get('Query')}")

    print("\n== KEY PAGES IN BING ==")
    for u in KEY_PAGES[:12]:
        info, e = call("GetUrlInfo", key, {"siteUrl": site, "url": u})
        if e:
            print(f"  {u}  {e}"); continue
        info = info or {}
        print(f"  {u}  http={info.get('HttpStatus')} lastCrawled={date(info.get('LastCrawledDate'))} "
              f"discovered={date(info.get('DiscoveryDate'))}")

    if sys.argv[1:2] == ["submit"]:
        quota, e = call("GetUrlSubmissionQuota", key, p)
        left = (quota or {}).get("DailyQuota", 0)
        print(f"\n== SUBMIT == daily quota left: {left}" + (" " + e if e else ""))
        urls = KEY_PAGES[:max(0, left)]
        if urls:
            _, e = call("SubmitUrlBatch", key, body={"siteUrl": site, "urlList": urls})
            print(f"  submitted {len(urls)} pages" if not e else "  " + e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
