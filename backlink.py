#!/usr/bin/env python3
"""Backlink automation (owner, 20 Nov 2026).

Real backlinks come from other sites choosing to link to us; they cannot be
mass-manufactured without breaking Google/Bing guidelines and getting the
site penalised. What this DOES automate is the whole white-hat pipeline:

    python backlink.py monitor    # find backlinks we have already earned
    python backlink.py outreach   # generate a personalised pitch + ready
                                  # embed code for every jeweller not yet
                                  # linking back

- monitor: fetches each tracked jeweller's own website and checks whether it
  links to mygoldrates.com (a plain link, our /badge.svg, or our widget.js).
  Newly found backlinks are flagged. State is kept in collector_cache
  (key "backlinks_seen") so each run reports what changed.
- outreach: for every active jeweller with a website that does NOT yet link
  back, prints a short personalised email and the exact badge snippet they
  paste - the badge links to their own gold-rate page here, so when they add
  it we gain a backlink and they gain a free "today's rate" widget. The owner
  sends these from their own mailbox (we hold no jeweller email addresses,
  and auto-sending cold mail would be spam).

Output goes to the job log / annotations, never committed (public repo).
Needs SUPABASE_URL + SUPABASE_SERVICE_KEY for the brand list and the cache.
"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

import requests

import private_store
from outreach_pages import badge_code, embed_code

SITE = "https://mygoldrates.com"
IST = timezone(timedelta(hours=5, minutes=30))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
SEEN_KEY = "backlinks_seen"

# Other places worth a link besides the jewellers we list. Public, relevant
# sites only; extend as real opportunities come up.
EXTRA_TARGETS = [
    # (name, homepage) - directories / blogs where a listing is legitimate
]


def brands():
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    rows = sb.table("brands").select("name,slug,domain,active").eq("active", True).execute().data or []
    out = []
    for r in rows:
        dom = (r.get("domain") or "").replace("https://", "").replace("http://", "").split("/")[0]
        if dom:
            out.append((r["name"], r["slug"], dom.lower().lstrip("www.")))
    return sorted(set(out))


def fetch(url):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": UA, "Cache-Control": "no-cache"},
                         allow_redirects=True)
        return r.text if r.status_code < 400 else ""
    except requests.RequestException:
        return ""


LINK = re.compile(r'https?://(?:www\.)?mygoldrates\.com', re.I)
BADGE = re.compile(r'mygoldrates\.com/(?:badge\.svg|widget\.js)', re.I)


def links_back(html):
    """Does this page link to us? Returns the kind, or ''."""
    if not html:
        return ""
    if BADGE.search(html):
        return "badge/widget"
    if LINK.search(html):
        return "link"
    return ""


def monitor():
    seen = private_store.cache_get(SEEN_KEY) or {}
    found, new = {}, []
    targets = [(n, d) for n, _, d in brands()] + EXTRA_TARGETS
    for name, dom in targets:
        kind = ""
        for scheme in ("https://", "https://www."):
            kind = links_back(fetch(scheme + dom))
            if kind:
                break
        if kind:
            found[dom] = {"name": name, "kind": kind}
            if dom not in seen:
                new.append((name, dom, kind))
                seen[dom] = {"name": name, "kind": kind,
                             "first_seen": datetime.now(IST).date().isoformat()}
    private_store.cache_put(SEEN_KEY, seen)
    print(f"== BACKLINK MONITOR ({datetime.now(IST).date()}) ==")
    print(f"checked {len(targets)} sites; {len(found)} link back; {len(new)} new since last run")
    for name, dom, kind in new:
        print(f"  NEW  {name}  {dom}  ({kind})")
    print("-- all backlinks we have earned --")
    for dom, d in sorted(seen.items()):
        live = " (still live)" if dom in found else " (not found this run)"
        print(f"  {d['name']:<22} {dom:<28} {d['kind']}  since {d.get('first_seen','?')}{live}")
    if not seen:
        print("  none yet - run `outreach` to generate the pitches that earn them")


def outreach():
    seen = private_store.cache_get(SEEN_KEY) or {}
    todo = [(n, s, d) for n, s, d in brands() if d not in seen]
    print(f"== OUTREACH PACKETS ==  {len(todo)} jewellers not yet linking back\n")
    for name, slug, dom in todo:
        page = f"{slug}-gold-rate-today"
        badge = badge_code(SITE, page, name)
        subject = f"{name}'s live gold rate on MyGoldRates - free badge for your site"
        body = (
            f"Hi {name} team,\n\n"
            f"We run MyGoldRates.com, a free site that compares today's gold rates across Indian "
            f"jewellers. {name}'s daily rate is already listed, with your name and a link to your site:\n"
            f"  {SITE}/{page}\n\n"
            f"We've made a free badge you can add to your website - it shows today's gold rate and "
            f"links to your page on MyGoldRates. Just paste this where you'd like it to appear:\n\n"
            f"{badge}\n\n"
            f"It updates on its own every day, costs nothing, and gives your visitors a live rate. "
            f"If you'd prefer the full comparison widget instead, reply and we'll send that snippet.\n\n"
            f"Thank you,\nMyGoldRates.com\n"
        )
        print(f"--- {name}  ({dom}) ---")
        print(f"To: (the jeweller's contact / webmaster)")
        print(f"Subject: {subject}\n{body}")
    print("Send these from your own mailbox. When a jeweller adds the badge, "
          "`backlink.py monitor` will detect the new backlink automatically.")


def main():
    if not os.environ.get("SUPABASE_URL"):
        print("SUPABASE_URL not set"); return 1
    mode = sys.argv[1] if len(sys.argv) > 1 else "monitor"
    if mode == "outreach":
        outreach()
    else:
        monitor()
    return 0


if __name__ == "__main__":
    sys.exit(main())
