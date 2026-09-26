#!/usr/bin/env python3
"""Probe candidate local jewellers and report which publish a usable rate.

Reuses scrape.py wholesale - the same fetch(), the same CANDIDATE_PATHS
walk, the same eight extractors, the same ordering_sane() check. A rate that
verifies here is one the real scraper can read tomorrow; nothing is
reimplemented, so the two cannot drift apart.

For each candidate it walks the domain's likely rate paths, and for every
one that responds it tries to extract a purity-labelled per-gram rate. The
first path that yields a sane ladder wins, and the verdict records which
path and which extractor - so a promotion carries a pinned rate_url rather
than a guess.

VERDICTS
  verified   a per-gram rate was extracted and passed the sanity check
  no-rate    the site answered but no purity-labelled rate could be read
  blocked    401/403/429/503 on every path - bot-walled to a plain request
  dead       nothing resolved (DNS, timeout, 404 everywhere)

A "blocked" or "no-rate" verdict is NOT proof a jeweller is unscrapeable.
This prober does static fetches only. The real scraper additionally has a
browser-render path and a paid proxy waterfall, and several brands on the
live board need them - Vaibhav Jewellers comes back "blocked" here while
scrape.py reads it every day, and Tanishq 403s every plain request yet
publishes through the render path. That omission is deliberate: rendering
and proxying cost time and credits per request, and a sweep whose job is to
say "is there anything here at all" should not burn either. Read these two
verdicts as "not readable cheaply", and hand a promising one to the real
scraper to settle.

Calibrated against brands already on the board: of five known-good
controls, three verify from a plain fetch (CKC from a homepage banner, GRT
from script JSON, Chandukaka from a table), one needs its specific pinned
product URL and one is bot-walled. So treat roughly 60% as this prober's
ceiling, not 100%.

WHY VERIFIED CANDIDATES ARE PROMOTED AS INACTIVE

A verdict of "verified" means a number was extracted, NOT that the number
is right. This repo has already published a fabricated rate from a 404
page (WHP, read off an error page that happened to contain product prices)
and a stale fallback baked into served HTML (PN Gadgil & Sons, 5.7% out of
date). Both looked exactly like a successful extraction.

So promotion writes the brand with active=False and the discovered
rate_url. Flipping one flag after a glance at the number is cheap;
un-publishing a wrong rate that reached the board is not. Promoted brands
are regional, and generate_site.py already excludes REGION_MAP slugs from
median24, so they cannot move the national median or the "cheapest today"
badge even once activated.

Writes docs/local-discovery.json (the full report, so a bad promotion can
be audited later) and prints a summary. Exits 0 unless the report itself
could not be written - a candidate failing to verify is the expected case,
not an error.
"""
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import requests

import scrape
from local_candidates import CANDIDATES, DENY_HOSTS

TIMEOUT = 20
OUT = "docs/local-discovery.json"


def slugify(name):
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]


def probe(cand, session):
    """-> verdict dict for one candidate."""
    host = cand["domain"].lower().lstrip("/")
    if host.startswith("www."):
        bare = host[4:]
    else:
        bare = host
    if bare in DENY_HOSTS:
        return {**cand, "verdict": "skipped",
                "note": "aggregator/marketplace on the deny list"}

    base = host if host.startswith("http") else f"https://{host}"
    # The bare domain first: several jewellers put the rate in a homepage
    # banner (CKC and Indriya on the live board both do), so the rate pages
    # are a fallback rather than the only place worth looking.
    paths = [""] + list(scrape.CANDIDATE_PATHS)
    seen, tried = set(), []
    blocked = dead = 0

    for p in paths:
        url = urljoin(base, p) if p else base
        if url in seen:
            continue
        seen.add(url)
        if not scrape.robots_ok(url, session):
            tried.append(f"{p or '/'}: robots")
            continue
        html, reason = scrape.fetch(url, session, TIMEOUT)
        if not html:
            tried.append(f"{p or '/'}: {reason}")
            if str(reason).startswith("blocked"):
                blocked += 1
            else:
                dead += 1
            continue
        found, counts, how, note = scrape.try_html(html)
        if found:
            k24 = scrape.derive_ladder(
                max((v / scrape.PURITY_FRACTION[k] for k, v in found.items()),
                    default=0))
            best = max(found.items(),
                       key=lambda kv: scrape.PURITY_FRACTION[kv[0]])
            c24 = round(best[1] / scrape.PURITY_FRACTION[best[0]], 2)
            return {**cand, "verdict": "verified", "rate_url": url,
                    "method": how, "purities": sorted(found),
                    "canonical_24k": c24,
                    "slug": slugify(cand["name"]),
                    "note": f"read {len(found)} purity/purities via {how}"}
        tried.append(f"{p or '/'}: {note}")

    if blocked and not dead:
        v, n = "blocked", "bot-walled on every path tried"
    elif blocked:
        v, n = "blocked", "blocked or unreachable on every path tried"
    else:
        v, n = ("no-rate", "responded but no purity-labelled rate found") \
            if any(": no values" in t or "MISLABELLED" in t for t in tried) \
            else ("dead", "nothing resolved on any path")
    # Flag the cases the heavier machinery might still crack, so a human
    # reading the report knows which ones are worth a second look.
    may_render = v in ("blocked", "no-rate")
    return {**cand, "verdict": v, "note": n, "tried": tried[:8],
            "may_work_with_render": may_render}


def promote(sb, rows):
    """Insert verified candidates as INACTIVE brands with a pinned rate_url.

    Never touches a slug that already exists - an existing brand's
    configuration is the scraper's business, not this job's.
    """
    if not sb or not rows:
        return 0
    n = 0
    for r in rows:
        try:
            ex = sb.table("brands").select("id") \
                   .eq("slug", r["slug"]).execute().data
            if ex:
                print(f"  promote: {r['slug']} already a brand, left alone")
                continue
            sb.table("brands").insert({
                "slug": r["slug"], "name": r["name"],
                "domain": r["domain"], "rate_url": r["rate_url"],
                "active": False, "includes_gst": False,
            }).execute()
            print(f"  promote: {r['slug']} added as INACTIVE "
                  f"(24K ~ {r['canonical_24k']}, {r['method']}) "
                  f"-> review, then set active")
            n += 1
        except Exception as e:
            print(f"  promote: {r['slug']} FAILED {type(e).__name__}: "
                  f"{str(e)[:120]}")
    return n


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": scrape.UA})

    results = []
    for c in CANDIDATES:
        r = probe(c, session)
        results.append(r)
        extra = ""
        if r["verdict"] == "verified":
            extra = f" 24K~{r['canonical_24k']} via {r['method']}"
        print(f"{r['verdict']:<9} {r['state'][:18]:<18} "
              f"{r['name'][:26]:<26}{extra}")

    verified = [r for r in results if r["verdict"] == "verified"]
    by_verdict = {}
    for r in results:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1

    print()
    print(f"discover-local: {len(results)} candidates -> "
          + ", ".join(f"{v} {k}" for k, v in sorted(by_verdict.items())))

    states = sorted({r["state"] for r in verified})
    if states:
        print(f"  states with a verified local source: {', '.join(states)}")
    retry = [r for r in results if r.get("may_work_with_render")]
    if retry:
        print(f"  {len(retry)} answered but not readable cheaply - these may "
              f"still work via the render/proxy path:")
        for r in retry[:12]:
            print(f"    {r['name'][:28]:<28} {r['domain']}")

    sb = None
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"):
        try:
            from supabase import create_client
            sb = create_client(os.environ["SUPABASE_URL"],
                               os.environ["SUPABASE_SERVICE_KEY"])
        except Exception as e:
            print(f"  supabase unavailable ({type(e).__name__}), report only")
    added = promote(sb, verified)
    if verified and not sb:
        print("  (no Supabase credentials - nothing promoted, report only)")

    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "candidates": len(results), "verified": len(verified),
                   "promoted_inactive": added,
                   "states_covered": states,
                   "results": results}, f, indent=1)
    print(f"  wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
