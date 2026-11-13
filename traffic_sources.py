"""Where visitors come from, day by day: Google, Bing, other search,
social, other sites, or direct - and the weekly funnel from visitor to
subscriber with buying intent. Read-only.

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
            params={"select": "day,referrer,session_id,page,created_at",
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

    # Hour of day (IST) of direct landings, by landing page group. People
    # in India browse in the daytime; an automated visitor is flat or
    # clockwork. Pages per session says the same thing another way.
    from datetime import datetime, timezone, timedelta as _td
    ist = timezone(_td(hours=5, minutes=30))
    n_pages = Counter(x.get("session_id") for x in rows)
    for lo, hi in (("2026-09-28", "2026-10-06"), ("2026-10-08", "2026-10-31")):
        groups = defaultdict(Counter); single = Counter(); tot = Counter()
        for sid, (d, pg, s) in land.items():
            if not (lo <= d <= hi and s == "direct"):
                continue
            g = ("/compare" if pg.startswith("/compare") else "/" if pg == "/"
                 else "city" if pg.startswith("/gold-rate-today-in-") else "other")
            ts = next((x.get("created_at") for x in rows
                       if x.get("session_id") == sid), None)
            if ts:
                hr = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ist).hour
                groups[g][hr // 3 * 3] += 1
            tot[g] += 1
            single[g] += n_pages[sid] == 1
        print(f"\n== DIRECT LANDINGS {lo}..{hi}: share by IST hour block, "
              "and share of one-page sessions ==")
        print("group      n    " + " ".join(f"{h:02d}h" for h in range(0, 24, 3)) + "  1-page")
        for g in ("/compare", "/", "city", "other"):
            if tot[g]:
                print(f"{g:9} {tot[g]:4}  " + " ".join(
                    f"{100 * groups[g][h] / tot[g]:3.0f}" for h in range(0, 24, 3))
                    + f"  {100 * single[g] / tot[g]:4.0f}%")

    # Every page's views and visitors over the window, for deciding which
    # pages earn their place.
    pv = Counter(); vis = defaultdict(set); ext = Counter()
    for x in rows:
        pg = x.get("page") or ""
        pv[pg] += 1; vis[pg].add(x.get("session_id"))
        if source(x.get("referrer")) not in (None, "direct"):
            ext[pg] += 1
    print("\n== PER PAGE (views, visitors, arrivals from other sites) ==")
    for pg, n in sorted(pv.items(), key=lambda kv: -kv[1]):
        if pg.startswith(("/gold-rate-today-in-", "/news/", "/learn/")) or n >= 20:
            print(f"{n:6} {len(vis[pg]):6} {ext[pg]:4}  {pg[:80]}")

    print("\n== TOP OTHER SITES (last 30 days) ==")
    cut = (date.today() - timedelta(days=30)).isoformat()
    hosts = Counter()
    for x in rows:
        if x["day"] >= cut and source(x.get("referrer")) in ("other_site", "social",
                                                              "other_search", "ai"):
            hosts[urlparse(x["referrer"]).hostname] += 1
    for hst, n in hosts.most_common(15):
        print(f"{n:5}  {hst}")

    funnel(url, h, rows)
    popup_audit(url, h)
    client_errors(url, h, days=10)


def popup_audit(url, h, days=14):
    """Why is "popup shown" so much higher than closes and signups? For each
    session the popup was shown in: seconds from its first page view to the
    popup (a person needs 5-10 s - a search engine's renderer fast-forwards
    timers and gets it at once), whether anything was clicked after it, pages
    viewed, and the host. Counts only."""
    from datetime import datetime
    since = (date.today() - timedelta(days=days)).isoformat()
    ce = _all(url, h, "click_events", "created_at,target,session_id,page", {"day": f"gte.{since}"}) or []
    pv = _all(url, h, "page_views", "created_at,session_id,host,page,referrer", {"day": f"gte.{since}"}) or []
    ts = lambda x: datetime.fromisoformat(x["created_at"].replace("Z", "+00:00"))
    first_pv, n_pv, host, ref = {}, Counter(), {}, {}
    for x in pv:
        sid = x.get("session_id")
        n_pv[sid] += 1
        if sid not in first_pv or ts(x) < first_pv[sid]:
            first_pv[sid] = ts(x); host[sid] = x.get("host") or "?"; ref[sid] = source(x.get("referrer")) or "direct"
    shown, after, ok, closes = {}, Counter(), set(), set()
    for x in sorted(ce, key=ts):
        sid, tg = x.get("session_id"), x.get("target") or ""
        if tg.endswith("popup_shown"):
            shown.setdefault(sid, ts(x))
        elif sid in shown and ts(x) >= shown[sid]:
            after[sid] += 1
            if tg.endswith(("popup_email_ok", "popup_google_ok")):
                ok.add(sid)
            if any(k in tg.lower() for k in ("close", "spno", "spsureno", "dismiss", "x")):
                closes.add(sid)
    print(f"\n== POPUP AUDIT (last {days} days): {len(shown)} sessions saw it ==")
    if not shown:
        return
    buckets = Counter()
    groups = defaultdict(list)
    for sid, t in shown.items():
        d = (t - first_pv[sid]).total_seconds() if sid in first_pv else None
        b = ("no page view" if d is None else "<3 s" if d < 3 else "3-9 s" if d < 9.5 else "10-30 s" if d < 30 else "30 s+")
        buckets[b] += 1
        groups[b].append(sid)
    print("seconds from landing to popup   sessions  clicked after  signed up  1-page visits  hosts / arrived from")
    for b in ("no page view", "<3 s", "3-9 s", "10-30 s", "30 s+"):
        g = groups.get(b, [])
        if not g:
            continue
        hosts = Counter(host.get(s, "?") for s in g).most_common(3)
        refs = Counter(ref.get(s, "?") for s in g).most_common(3)
        print(f"{b:31} {len(g):9} {sum(1 for s in g if after[s]):14} {sum(1 for s in g if s in ok):10} "
              f"{sum(1 for s in g if n_pv[s] <= 1):14}  {hosts} {refs}")
    print(f"signed up: {len(ok)}  clicked anything after the popup: {sum(1 for s in shown if after[s])}  "
          f"close-like clicks: {len(closes)}")
    by_day = Counter(t.date().isoformat() for t in shown.values())
    print("popup sessions by day: " + ", ".join(f"{d[5:]} {n}" for d, n in sorted(by_day.items())))
    tg_after = Counter(x["target"] for x in ce if x.get("session_id") in shown and x.get("target") and
                       ts(x) >= shown[x["session_id"]])
    print("what was clicked after the popup: " + ", ".join(f"{k} {v}" for k, v in tg_after.most_common(15)))


def client_errors(url, h, days=3):
    """Errors pages report about themselves (click_events target "mc_err:..."
    from the Making Charges loader), newest first. Counts and messages only."""
    since = (date.today() - timedelta(days=days)).isoformat()
    ce = _all(url, h, "click_events", "created_at,target,page", {"day": f"gte.{since}", "target": "like.mc_err*"}) or []
    print(f"\n== CLIENT ERRORS, last {days} days ({len(ce)}) ==")
    for t, n in Counter(x["target"] for x in ce).most_common(20):
        print(f"  {n:4d}  {t}")
    for x in sorted(ce, key=lambda x: x["created_at"], reverse=True)[:10]:
        print(f"  {x['created_at'][:19]}  {x.get('page')}  {x['target']}")
    # the app and its notifications (pwa.js): installs, bell taps and why
    # a subscription did not happen (refused, failed)
    pw = _all(url, h, "click_events", "created_at,target,page", {"day": f"gte.{since}", "target": "like.pwa:*"}) or []
    print(f"\n== APP / NOTIFICATION EVENTS, last {days} days ({len(pw)}) ==")
    for t, n in Counter(x["target"] for x in pw).most_common(20):
        print(f"  {n:4d}  {t}")
    for x in sorted(pw, key=lambda x: x["created_at"], reverse=True)[:15]:
        print(f"  {x['created_at'][:19]}  {x.get('page')}  {x['target']}")


def _all(url, h, table, select, flt):
    """Every row of a table (paged), or None if a column is not there yet."""
    out, off = [], 0
    while True:
        r = requests.get(f"{url}/rest/v1/{table}", params={"select": select, **flt},
                         headers={**h, "Range": f"{off}-{off + 999}"}, timeout=60)
        if r.status_code >= 400:
            return None
        b = r.json(); out += b
        if len(b) < 1000:
            return out
        off += 1000


def funnel(url, h, rows):
    """Weekly: visitors -> asked Sona -> new subscribers (and where) ->
    price alerts -> buying intent given. Counts only - no addresses, no
    names: this report is forwarded as public job annotations."""
    since = (date.today() - timedelta(days=56)).isoformat()
    wk = lambda d: (date.fromisoformat(str(d)[:10]) - timedelta(days=date.fromisoformat(str(d)[:10]).weekday())).isoformat()
    vis, sona = defaultdict(set), defaultdict(set)
    for x in rows:
        if x["day"] >= since:
            vis[wk(x["day"])].add(x.get("session_id"))
    q = _all(url, h, "bot_questions", "day,session_id", {"day": f"gte.{since}"}) or []
    for x in q:
        sona[wk(x["day"])].add(x.get("session_id"))
    subs = _all(url, h, "inquiries", "created_at,signup_method,buy_for,buy_when,intent_at",
                {"created_at": f"gte.{since}"})
    intent_cols = subs is not None
    if subs is None:                                   # before subscriber_intent.sql
        subs = _all(url, h, "inquiries", "created_at,signup_method", {"created_at": f"gte.{since}"}) or []
    new, how, intent = Counter(), defaultdict(Counter), Counter()
    for x in subs:
        w = wk(x["created_at"]); new[w] += 1; how[w][x.get("signup_method") or "?"] += 1
        if x.get("buy_for") or x.get("buy_when"):
            intent[w] += 1
    al = _all(url, h, "price_alerts", "created_at,source", {"created_at": f"gte.{since}"}) or []
    alerts, from_sona = Counter(), Counter()
    for x in al:
        alerts[wk(x["created_at"])] += 1
        if (x.get("source") or "") == "sona":
            from_sona[wk(x["created_at"])] += 1
    print("\n== WEEKLY FUNNEL (week starting): visitors -> asked Sona -> new subscribers -> alerts -> intent ==")
    print(f"{'week':10} {'visitors':>8} {'sona':>6} {'new subs':>8} {'alerts':>7} {'via sona':>8} {'intent':>7}  how they signed up")
    for w in sorted(set(vis) | set(new) | set(alerts)):
        print(f"{w:10} {len(vis[w]):8} {len(sona[w]):6} {new[w]:8} {alerts[w]:7} {from_sona[w]:8} "
              f"{(intent[w] if intent_cols else '-'):>7}  " + ", ".join(f"{k} {v}" for k, v in how[w].most_common()))
    if intent_cols:
        tot_for = Counter(x.get("buy_for") for x in subs if x.get("buy_for"))
        tot_when = Counter(x.get("buy_when") for x in subs if x.get("buy_when"))
        print("buying for (8 weeks): " + (", ".join(f"{k} {v}" for k, v in tot_for.most_common()) or "-"))
        print("buying when (8 weeks): " + (", ".join(f"{k} {v}" for k, v in tot_when.most_common()) or "-"))
    else:
        print("intent columns not there yet - run sql/subscriber_intent.sql")


if __name__ == "__main__":
    main()
