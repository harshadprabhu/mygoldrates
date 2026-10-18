"""Where visitors come from, day by day: Google, Bing, other search,
social, other sites, or direct. Read-only.

Reads page_views with the service key and prints a plain-text table. The
workflow forwards it as job annotations rather than committing it,
because this repository is public and traffic data is business data.
"""
import os
from collections import Counter, defaultdict
from datetime import date, timedelta
from urllib.parse import urlparse

import requests

DAYS = int(os.environ.get("DAYS", "75"))
COLS = ["google", "bing", "other_search", "social", "ai", "other_site", "direct"]
SEARCH = ("duckduckgo.", "yahoo.", "yandex.", "ecosia.", "baidu.", "brave.", "startpage.")
SOCIAL = ("facebook.", "instagram.", "twitter.", "linkedin.",
          "whatsapp.", "reddit.", "youtube.", "pinterest.", "quora.", "telegram.")
AI = ("chatgpt.", "openai.", "perplexity.", "claude.ai", "gemini.", "copilot.")


def source(ref):
    if not ref:
        return "direct"
    h = (urlparse(ref).hostname or "").lower()
    if not h or "mygoldrates" in h:
        return None                       # internal navigation
    if "google." in h:
        return "google"
    if "bing." in h:
        return "bing"
    if any(s in h for s in SEARCH):
        return "other_search"
    if any(s in h for s in AI):
        return "ai"
    # t.co and x.com match as whole hosts: as substrings they would claim
    # chatgpt.com and any domain ending in "x.com".
    if h in ("t.co", "x.com") or any(s in h for s in SOCIAL):
        return "social"
    return "other_site"


def main():
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    since = (date.today() - timedelta(days=DAYS)).isoformat()
    rows, off = [], 0
    while True:
        r = requests.get(
            f"{url}/rest/v1/page_views",
            params={"select": "day,referrer,session_id,page",
                    "day": f"gte.{since}", "order": "day.asc"},
            headers={**h, "Range": f"{off}-{off + 999}"}, timeout=60)
        r.raise_for_status()
        b = r.json()
        rows += b
        if len(b) < 1000:
            break
        off += 1000
    rows = [x for x in rows if not (x.get("page") or "").startswith("/__")]
    print(f"page_views rows since {since}: {len(rows)}")

    # A visit is attributed by its session's first external referrer, so
    # one Google arrival that browses five pages counts once, as Google.
    first = {}
    for x in rows:
        sid = x.get("session_id") or id(x)
        if sid in first:
            continue
        s = source(x.get("referrer"))
        if s is not None:
            first[sid] = (x["day"], s)
    per = defaultdict(Counter)
    for d, s in first.values():
        per[d][s] += 1
    views = Counter(x["day"] for x in rows)

    print("\n== VISITS BY SOURCE, WEEKLY (week starting) ==")
    wk = defaultdict(Counter); wv = Counter()
    for d, c in per.items():
        m = date.fromisoformat(d); m = (m - timedelta(days=m.weekday())).isoformat()
        wk[m].update(c)
    for d, n in views.items():
        m = date.fromisoformat(d); m = (m - timedelta(days=m.weekday())).isoformat()
        wv[m] += n
    print("week        views  " + " ".join(f"{c:>12}" for c in COLS))
    for m in sorted(set(wk) | set(wv)):
        print(f"{m}  {wv[m]:5}  " + " ".join(f"{wk[m][c]:12}" for c in COLS))

    print("\n== LAST 21 DAYS, DAILY ==")
    print("day         views  " + " ".join(f"{c:>12}" for c in COLS))
    for d in sorted(set(per) | set(views))[-21:]:
        print(f"{d}  {views[d]:5}  " + " ".join(f"{per[d][c]:12}" for c in COLS))

    # Where do "direct" visits land, before and after the 7 Oct link fix?
    # Bots that run JavaScript and follow broken relative links show up as
    # direct sessions landing on odd paths.
    land = {}
    for x in rows:
        sid = x.get("session_id") or id(x)
        if sid not in land:
            land[sid] = (x["day"], x.get("page") or "", source(x.get("referrer")))
    for lo, hi in (("2026-09-28", "2026-10-06"), ("2026-10-08", "2026-10-31")):
        lp = Counter(); city_chain = 0; deep = 0; tot = 0
        pages_per = Counter()
        for x in rows:
            if lo <= x["day"] <= hi:
                pages_per[x.get("session_id")] += 1
        for sid, (d, pg, s) in land.items():
            if lo <= d <= hi and s == "direct":
                tot += 1; lp[pg] += 1
                if pg.startswith("/city/"):
                    city_chain += 1
                if pg.count("/city/") > 1:
                    deep += 1
        big = sum(1 for v in pages_per.values() if v >= 20)
        print(f"\n== DIRECT LANDINGS {lo}..{hi}: {tot} sessions, "
              f"{city_chain} on /city/ paths, {deep} on chained /city/.../city/ paths, "
              f"{big} sessions with 20+ page views ==")
        for pg, n in lp.most_common(12):
            print(f"{n:5}  {pg[:90]}")

    print("\n== TOP OTHER SITES (last 30 days) ==")
    cut = (date.today() - timedelta(days=30)).isoformat()
    hosts = Counter()
    for x in rows:
        if x["day"] >= cut and source(x.get("referrer")) in ("other_site", "social",
                                                              "other_search", "ai"):
            hosts[urlparse(x["referrer"]).hostname] += 1
    for hst, n in hosts.most_common(15):
        print(f"{n:5}  {hst}")


if __name__ == "__main__":
    main()
