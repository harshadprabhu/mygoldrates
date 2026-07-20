#!/usr/bin/env python3
"""
scrape.py v3 - automated gold rate collector with failure diagnostics.

CHANGES over v2:
  * extract() now takes the MEDIAN of every value found for a purity, not the
    first one. History tables and city lists cluster around today's real rate,
    so the median lands on it; a stray nav item or product price no longer
    wins. This is what produced CaratLane's wrong 12,450.
  * Every failure now reports WHY - "403 blocked", "timeout", "fetched but no
    rate found", "404 everywhere". Previously all of these printed the same
    useless "no rate", so we couldn't tell a blocked site from a parse bug.
  * Playwright is tried when a static fetch is BLOCKED (403/503), not only
    when parsing fails. A real browser often gets through where requests
    doesn't.
  * Quarantine needs at least MIN_FOR_MEDIAN brands. With 3 brands a median
    is meaningless and could quarantine the only correct one.
"""

from __future__ import annotations

import os
import re
import statistics
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from supabase import create_client

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

FAST_TIMEOUT, FULL_TIMEOUT = 8, 20
BRAND_BUDGET = 60
POLITE_DELAY = 1.5
OUTLIER_TOLERANCE = 0.04
RATIO_TOLERANCE = 0.01
MIN_FOR_MEDIAN = 5        # don't quarantine on a median of 3

PURITY_FRACTION = {"24K": 0.999, "22K": 0.916, "18K": 0.750, "14K": 0.583}

CANDIDATE_PATHS = [
    "/gold-rate-today/", "/gold-rate-today", "/gold-rate", "/goldrate",
    "/goldprice", "/gold-rate.html", "/gold-price", "/todays-gold-rate",
]

GRAM_MIN, GRAM_MAX = 8_000, 22_000
TEN_GRAM_MIN, TEN_GRAM_MAX = 80_000, 220_000

MONEY_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]{4,12}(?:\.\d{1,2})?)")
PURITY_RE = re.compile(r"\b(24|22|18|14)\s*(?:K|KT|CT|CARAT|KARAT)\b", re.I)

_robots: dict[str, RobotFileParser | None] = {}


def _f(s):
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def robots_ok(url, session):
    host = urlparse(url).netloc
    if host not in _robots:
        rp = RobotFileParser()
        try:
            r = session.get(f"https://{host}/robots.txt", timeout=FAST_TIMEOUT)
            if r.status_code >= 400:
                _robots[host] = None
            else:
                rp.parse(r.text.splitlines())
                _robots[host] = rp
        except requests.RequestException:
            _robots[host] = None
    rp = _robots[host]
    return True if rp is None else (rp.can_fetch(UA, url) and rp.can_fetch("*", url))


def visible_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return soup.get_text(" ", strip=True)


def extract(text):
    """{purity: median_per_gram}. Median beats first-match: history tables and
    city lists cluster on today's rate, outlier junk gets voted out."""
    buckets: dict[str, list[float]] = {}
    for m in MONEY_RE.finditer(text):
        val = _f(m.group(1))
        if val is None:
            continue
        if GRAM_MIN <= val <= GRAM_MAX:
            per_gram = val
        elif TEN_GRAM_MIN <= val <= TEN_GRAM_MAX:
            per_gram = val / 10.0
        else:
            continue
        pm = PURITY_RE.search(text[max(0, m.start() - 80): m.end() + 80])
        if pm:
            buckets.setdefault(f"{pm.group(1)}K", []).append(per_gram)
    return {k: statistics.median(v) for k, v in buckets.items()}, \
           {k: len(v) for k, v in buckets.items()}


def basis_confirmed(found):
    keys = list(found)
    for a in keys:
        for b in keys:
            if a == b:
                continue
            exp = PURITY_FRACTION[a] / PURITY_FRACTION[b]
            if abs(found[a] / found[b] - exp) / exp > RATIO_TOLERANCE:
                return False, f"{a}/{b} ratio off"
    return (True, f"consistent across {len(keys)} purities") if len(keys) >= 2 \
        else (False, "single purity")


def fetch(url, session, timeout):
    """-> (html, reason). html is None on failure; reason explains why."""
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True)
    except requests.Timeout:
        return None, "timeout"
    except requests.RequestException as e:
        return None, type(e).__name__
    if r.status_code in (403, 401, 503, 429):
        return None, f"blocked {r.status_code}"
    if r.status_code == 404:
        return None, "404"
    if r.status_code >= 400:
        return None, str(r.status_code)
    return r.text, "ok"


def render(url):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page(user_agent=UA, locale="en-IN")
            pg.goto(url, timeout=30_000, wait_until="domcontentloaded")
            pg.wait_for_timeout(3000)
            html = pg.content()
            b.close()
            return html
    except Exception as e:
        return None


def scrape_brand(b, session):
    """-> (url, found, counts, method, note) | (None, None, None, None, reason)"""
    started = time.monotonic()
    tried = []

    urls = [b["rate_url"]] if b.get("rate_url") else None
    if urls is None:
        base = b["domain"] if b["domain"].startswith("http") else f"https://{b['domain']}"
        urls = [urljoin(base, p) for p in CANDIDATE_PATHS]

    blocked_seen = False
    for url in urls:
        if time.monotonic() - started > BRAND_BUDGET:
            tried.append("budget")
            break
        if not robots_ok(url, session):
            tried.append("robots")
            continue

        html, reason = fetch(url, session, FULL_TIMEOUT if b.get("rate_url") else FAST_TIMEOUT)
        if html:
            found, counts = extract(visible_text(html))
            if found:
                return url, found, counts, "static", "ok"
            tried.append("fetched-but-no-rate")
            # page loaded, values probably injected by JS
            rhtml = render(url)
            if rhtml:
                found, counts = extract(visible_text(rhtml))
                if found:
                    return url, found, counts, "rendered", "ok"
            continue

        if reason.startswith("blocked"):
            blocked_seen = True
            rhtml = render(url)            # browser may get past a soft block
            if rhtml:
                found, counts = extract(visible_text(rhtml))
                if found:
                    return url, found, counts, "rendered", "static was " + reason
        tried.append(reason)

    uniq = []
    for t in tried:
        if t not in uniq:
            uniq.append(t)
    summary = ", ".join(uniq[:4]) or "nothing tried"
    if blocked_seen:
        summary = "BLOCKED (datacenter IP?) - " + summary
    return None, None, None, None, summary


def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    })

    brands = sb.table("brands").select("*").eq("active", True).execute().data
    print(f"{len(brands)} active brands\n")
    today = datetime.now(timezone.utc).date().isoformat()
    saved = []

    for b in brands:
        print(f"-> {b['name']:22s} ", end="", flush=True)
        try:
            url, found, counts, method, note = scrape_brand(b, session)
        except Exception as e:
            print(f"ERROR {type(e).__name__}: {e}")
            time.sleep(POLITE_DELAY)
            continue

        if not found:
            print(f"no rate  ({note})")
            time.sleep(POLITE_DELAY)
            continue

        ok, why = basis_confirmed(found)
        purity = max(found, key=lambda k: PURITY_FRACTION[k])
        canonical = found[purity] / PURITY_FRACTION[purity]
        if b.get("includes_gst"):
            canonical /= 1.03

        row = {
            "brand_id": b["id"], "rate_date": today,
            "canonical_24k_pre_gst": round(canonical, 2),
            "source_purity": purity, "source_value": found[purity],
            "purities_found": len(found), "basis_confirmed": ok,
            "basis_note": why, "method": method, "rate_url": url,
            "status": "published",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            sb.table("rates").upsert(row, on_conflict="brand_id,rate_date").execute()
            if url != b.get("rate_url"):
                sb.table("brands").update({"rate_url": url}).eq("id", b["id"]).execute()
            saved.append(row)
            hits = " ".join(f"{k}x{counts[k]}" for k in sorted(counts))
            print(f"{purity} {found[purity]:>9,.0f} -> 24K {canonical:>9,.0f} "
                  f"[{method}] {'OK' if ok else 'unconfirmed'}  ({hits})")
        except Exception as e:
            print(f"save failed: {e}")

        time.sleep(POLITE_DELAY)

    if not saved:
        print("\nnothing collected")
        return

    if len(saved) < MIN_FOR_MEDIAN:
        print(f"\nonly {len(saved)} brands - skipping outlier check "
              f"(need {MIN_FOR_MEDIAN} for a meaningful median)")
        return

    median = statistics.median(r["canonical_24k_pre_gst"] for r in saved)
    print(f"\nmedian canonical 24K pre-GST: {median:,.0f}")
    q = 0
    for r in saved:
        drift = abs(r["canonical_24k_pre_gst"] - median) / median
        patch = {"drift_from_median": round(drift, 4)}
        if drift > OUTLIER_TOLERANCE and not r["basis_confirmed"]:
            patch["status"] = "quarantined"
            patch["basis_note"] = r["basis_note"] + f" | {drift*100:.1f}% off median"
            q += 1
            print(f"   quarantined brand {r['brand_id']}: {drift*100:.1f}% off")
        sb.table("rates").update(patch) \
          .eq("brand_id", r["brand_id"]).eq("rate_date", today).execute()

    print(f"\n{len(saved)-q} published, {q} quarantined")


if __name__ == "__main__":
    main()
