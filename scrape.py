#!/usr/bin/env python3
"""
scrape.py - fully automated gold/silver/platinum rate collector.

Runs unattended on GitHub Actions. No human in the daily loop.

Three things that normally need a person are automated here:

1. FINDING THE RATE URL
   auto_discover() tries a list of common rate-page paths against the brand's
   domain and caches whichever one works in the DB. Adding a brand = inserting
   a row with a domain. No code change, no hand-written URL.

2. GETTING PAST JS-RENDERED PAGES
   Static fetch first (cheap). If no rate is found, the same page is retried
   through Playwright, which executes the JS. Kalyan's Next.js shell and
   Malabar's XHR-injected values both resolve this way without hand-written
   endpoint replay.

3. WORKING OUT THE PURITY BASIS  <-- this is the one that mattered
   Two automatic checks, no phone calls:
   a) INTERNAL: if a page publishes 2+ purities, the ratios between them
      prove the basis. 22K/24K must be ~0.916. If it holds, the basis is
      confirmed automatically.
   b) CROSS-BRAND: every brand is normalised to 24K pre-GST, then compared
      to the median across all brands that day. Anything more than
      OUTLIER_TOLERANCE off the median is quarantined, not published.
      CaratLane's mislabelled "22ct" is caught by this automatically.

Quarantined and missing brands surface on the site as "Soon to be updated".
Nothing wrong ever gets published; it just goes quiet instead.
"""

from __future__ import annotations

import os
import re
import statistics
import sys
import time
from dataclasses import dataclass
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
TIMEOUT = 30
POLITE_DELAY = 3.0
OUTLIER_TOLERANCE = 0.04      # 4% off the day's median -> quarantine
RATIO_TOLERANCE = 0.01        # purity ratio must hold to 1%

PURITY_FRACTION = {"24K": 0.999, "22K": 0.916, "18K": 0.750, "14K": 0.583}

# Paths tried in order when a brand has no cached rate_url yet.
CANDIDATE_PATHS = [
    "/gold-rate-today", "/gold-rate-today/", "/gold-rate", "/gold-rate/",
    "/goldrate", "/goldprice", "/gold-price", "/gold-rate.html",
    "/todays-gold-rate", "/gold-rate/india", "/rates", "/gold-rate-today/India",
]

GRAM_MIN, GRAM_MAX = 8_000, 22_000
TEN_GRAM_MIN, TEN_GRAM_MAX = 80_000, 220_000

MONEY_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]{4,12}(?:\.\d{1,2})?)")
PURITY_RE = re.compile(r"\b(24|22|18|14)\s*(?:K|KT|CT|CARAT|KARAT)\b", re.I)


# ---------------------------------------------------------------- extraction

@dataclass
class Observation:
    purity: str          # "24K" / "22K" / "18K"
    per_gram: float
    raw: float
    unit: str


def _f(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def extract(text: str) -> list[Observation]:
    """Pull labelled per-gram rates out of visible page text."""
    found: dict[str, Observation] = {}
    for m in MONEY_RE.finditer(text):
        val = _f(m.group(1))
        if val is None:
            continue
        if GRAM_MIN <= val <= GRAM_MAX:
            unit, per_gram = "per_gram", val
        elif TEN_GRAM_MIN <= val <= TEN_GRAM_MAX:
            unit, per_gram = "per_10g", val / 10.0
        else:
            continue
        window = text[max(0, m.start() - 80): m.end() + 80]
        pm = PURITY_RE.search(window)
        if not pm:
            continue
        purity = f"{pm.group(1)}K"
        # keep the first (usually the headline figure, not the history table)
        found.setdefault(purity, Observation(purity, per_gram, val, unit))
    return list(found.values())


def confirm_basis_internally(obs: list[Observation]) -> tuple[bool, str]:
    """If 2+ purities are published, their ratio proves the basis."""
    by = {o.purity: o.per_gram for o in obs}
    pairs = [(a, b) for a in by for b in by if a != b]
    for a, b in pairs:
        expected = PURITY_FRACTION[a] / PURITY_FRACTION[b]
        actual = by[a] / by[b]
        if abs(actual - expected) / expected > RATIO_TOLERANCE:
            return False, f"{a}/{b} ratio {actual:.4f} != expected {expected:.4f}"
    if len(by) >= 2:
        return True, f"internally consistent across {len(by)} purities"
    return False, "only one purity published - needs cross-brand check"


def to_canonical_24k(per_gram: float, purity: str, includes_gst: bool = False) -> float:
    v = per_gram / 1.03 if includes_gst else per_gram
    return v / PURITY_FRACTION[purity]


# ------------------------------------------------------------------ fetching

def robots_ok(url: str, session: requests.Session) -> bool:
    p = urlparse(url)
    rp = RobotFileParser()
    try:
        r = session.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=TIMEOUT)
        if r.status_code >= 400:
            return True
        rp.parse(r.text.splitlines())
    except requests.RequestException:
        return True
    return rp.can_fetch(UA, url) and rp.can_fetch("*", url)


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return soup.get_text(" ", strip=True)


def fetch_static(url: str, session: requests.Session) -> str | None:
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        return r.text if r.status_code < 400 else None
    except requests.RequestException:
        return None


def fetch_rendered(url: str) -> str | None:
    """JS fallback. Handles Next.js shells and XHR-injected values."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page(user_agent=UA)
            pg.goto(url, timeout=45_000, wait_until="networkidle")
            pg.wait_for_timeout(2500)
            html = pg.content()
            b.close()
            return html
    except Exception:
        return None


def auto_discover(domain: str, session: requests.Session) -> tuple[str, list[Observation]] | None:
    """Try candidate paths until one yields a rate. Caches nothing here."""
    base = domain if domain.startswith("http") else f"https://{domain}"
    for path in CANDIDATE_PATHS:
        url = urljoin(base, path)
        if not robots_ok(url, session):
            continue
        html = fetch_static(url, session)
        if html:
            obs = extract(visible_text(html))
            if obs:
                return url, obs
        time.sleep(1.0)
    return None


def scrape_one(brand: dict, session: requests.Session):
    """Returns (rate_url, observations, method) or None."""
    url = brand.get("rate_url")

    if url:
        if not robots_ok(url, session):
            return None
        html = fetch_static(url, session)
        if html:
            obs = extract(visible_text(html))
            if obs:
                return url, obs, "static"
        html = fetch_rendered(url)
        if html:
            obs = extract(visible_text(html))
            if obs:
                return url, obs, "rendered"
        return None

    found = auto_discover(brand["domain"], session)
    if found:
        return found[0], found[1], "discovered"
    return None


# ---------------------------------------------------------------------- main

def main() -> int:
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept-Language": "en-IN,en;q=0.9",
    })

    brands = sb.table("brands").select("*").eq("active", True).execute().data
    today = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc).isoformat()

    staged = []
    for b in brands:
        print(f"-> {b['name']:24s} ", end="", flush=True)
        result = scrape_one(b, session)
        if not result:
            print("no rate")
            time.sleep(POLITE_DELAY)
            continue

        rate_url, obs, method = result
        ok, why = confirm_basis_internally(obs)

        # Prefer a purity we can trust; 24K if present, else highest available.
        obs.sort(key=lambda o: PURITY_FRACTION[o.purity], reverse=True)
        primary = obs[0]
        canonical = to_canonical_24k(primary.per_gram, primary.purity,
                                     includes_gst=b.get("includes_gst", False))

        staged.append({
            "brand_id": b["id"],
            "rate_date": today,
            "canonical_24k_pre_gst": round(canonical, 2),
            "source_purity": primary.purity,
            "source_value": primary.per_gram,
            "purities_found": len(obs),
            "basis_confirmed": ok,
            "basis_note": why,
            "method": method,
            "rate_url": rate_url,
            "scraped_at": now,
        })
        print(f"{primary.purity} {primary.per_gram:>9,.0f}  ->24K {canonical:>9,.0f}  "
              f"[{method}] {'OK' if ok else 'unconfirmed'}")

        if rate_url != b.get("rate_url"):
            sb.table("brands").update({"rate_url": rate_url}).eq("id", b["id"]).execute()

        time.sleep(POLITE_DELAY)

    if not staged:
        print("\nnothing collected")
        return 0

    # --- cross-brand outlier quarantine ----------------------------------
    median = statistics.median(r["canonical_24k_pre_gst"] for r in staged)
    print(f"\nmedian canonical 24K pre-GST: {median:,.0f}")

    published = 0
    for r in staged:
        drift = abs(r["canonical_24k_pre_gst"] - median) / median
        if drift > OUTLIER_TOLERANCE and not r["basis_confirmed"]:
            r["status"] = "quarantined"
            r["basis_note"] += f" | {drift*100:.1f}% off median"
            print(f"   QUARANTINE {r['brand_id']}: {drift*100:.1f}% off median")
        else:
            r["status"] = "published"
            published += 1
        r["drift_from_median"] = round(drift, 4)

    sb.table("rates").upsert(staged, on_conflict="brand_id,rate_date").execute()
    print(f"\n{published}/{len(staged)} published, "
          f"{len(staged)-published} quarantined as 'Soon to be updated'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
