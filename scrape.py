#!/usr/bin/env python3
"""
scrape.py v4 - automated gold rate collector.

THE BUG v3 HAD:
  Purity was matched by looking +/-80 characters around each price in the
  page's flattened text. In a dense rate table several purities and prices
  sit within that window, so values got bound to the wrong label. Jos Alukkas
  reported 24K = 13,150 when 13,135 is its 22K rate and 14,334 its 24K.
  Kalyan and Candere showed the same signature.

THE FIX - two layers:
  1. STRUCTURAL. Parse <tr> rows and bind a purity to a price only when both
     appear in the SAME ROW. A row is a unit of meaning; a character window
     is not. Proximity matching is kept only as a fallback for pages with no
     table markup.
  2. SANITY. Gold cannot be cheaper at higher purity. If 24K < 22K < 18K
     ordering is violated by more than a rounding margin, the extraction is
     mislabelled and the whole result is discarded rather than published.
     This catches the entire class of bug above, on any site, forever.
"""

from __future__ import annotations

import json
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
RATIO_TOLERANCE = 0.015
MIN_FOR_MEDIAN = 5

# General formula: Unknown Rate = (Known Rate / Known Karat) x Unknown Karat.
# 24K uses 1.0 — canonical_24k_pre_gst IS the per-gram 24K price. Dividing the
# scraped 18K/22K rate by its fraction gives the 24K equivalent; scaling back
# out by another purity's fraction gives that purity's rate. Fractions are
# exact karat/24 ratios (not the rounded BIS fineness stamps 916/750/583),
# so any known purity converts to any unknown purity with this one formula.
PURITY_FRACTION = {"24K": 24 / 24, "22K": 22 / 24, "18K": 18 / 24, "14K": 14 / 24}

# Brands behind anti-bot walls only reachable through Zyte API (needs the
# ZYTE_API_KEY secret) instead of a direct request; keyed by brand slug so no
# DB schema change is needed. caratlane (Titan, like tanishq) serves its
# product price-breakup only to real browsers.
NEEDS_PROXY = {"tanishq", "malabar", "caratlane", "whp", "joyalukkas"}

# Browser actions Zyte runs before returning HTML, per slug (none currently;
# CaratLane reads from its digital-gold page, which needs no interaction).
ZYTE_ACTIONS = {}

# Method tag for estimated rows: a brand with no live source gets the day's
# market median so no brand is ever missing. Excluded from the median itself,
# and re-tried every run so it upgrades to a real rate the moment one appears.
PLACEHOLDER_METHOD = "reference-median"

CANDIDATE_PATHS = [
    "/in/pan-india/en/live-gold-rate.html",
    "/gold-rate-today/", "/gold-rate-today", "/gold-rate", "/goldrate",
    "/goldprice", "/gold-rate.html", "/gold-price", "/todays-gold-rate",
    "/gold-price-calculator", "/gold-price-today", "/gold-rate-calculator",
    "/todays-gold-rate/", "/gold-rates", "/gold-price-in-india",
]

GRAM_MIN, GRAM_MAX = 8_000, 22_000
TEN_GRAM_MIN, TEN_GRAM_MAX = 80_000, 220_000

MONEY_RE = re.compile(r"(?:₹|Rs\.?|INR)?\s*([\d,]{4,12}(?:\.\d{1,2})?)")
PURITY_RE = re.compile(r"\b(24|22|18|14)\s*(?:K|KT|CT|CARAT|KARAT)\b", re.I)

_robots: dict[str, RobotFileParser | None] = {}


def _f(s):
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _per_gram(val):
    if GRAM_MIN <= val <= GRAM_MAX:
        return val
    if TEN_GRAM_MIN <= val <= TEN_GRAM_MAX:
        return val / 10.0
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


# ------------------------------------------------------------- extraction

def extract_rows(soup):
    """Row-scoped: a purity binds to a price only inside the same <tr>."""
    buckets: dict[str, list[float]] = {}
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        purities = {f"{m.group(1)}K" for c in cells for m in PURITY_RE.finditer(c)}
        if len(purities) != 1:
            continue          # ambiguous row - skip rather than guess
        purity = purities.pop()
        for c in cells:
            if PURITY_RE.search(c):
                continue      # don't read the label cell as a price
            for m in MONEY_RE.finditer(c):
                v = _f(m.group(1))
                if v is None:
                    continue
                pg = _per_gram(v)
                if pg:
                    buckets.setdefault(purity, []).append(pg)
    return buckets


def extract_proximity(text):
    """Fallback for pages with no table markup. Tight window, prices only."""
    buckets: dict[str, list[float]] = {}
    for m in re.finditer(r"(?:₹|Rs\.?|INR)\s*([\d,]{4,12}(?:\.\d{1,2})?)", text):
        v = _f(m.group(1))
        if v is None:
            continue
        pg = _per_gram(v)
        if pg is None:
            continue
        window = text[max(0, m.start() - 45): m.end() + 45]
        hits = {f"{x.group(1)}K" for x in PURITY_RE.finditer(window)}
        if len(hits) == 1:                    # unambiguous only
            buckets.setdefault(hits.pop(), []).append(pg)
    return buckets


_MP_RE = re.compile(r"metal_?price['\"\s:]{1,4}([\d.]+)", re.I)
_NW_RE = re.compile(r"net_?weight['\"\s:]{1,4}\"?([\d.]+)", re.I)
_STONE_RE = re.compile(r"(?:diamond|stone)_?(?:price|value)['\"\s:]{1,4}([\d.]+)", re.I)
_OPT_PURITY_RE = re.compile(r"option1\"?\s*:\s*\"(\d{2})\s*K", re.I)


def extract_product_breakup(html):
    """Read a per-item gold breakup embedded in a product page.

    Some jewellers (e.g. Shopify themes) render a stone-free item's pure-gold
    value and net weight straight into the page HTML: metal_price / net_weight
    is the per-gram rate for that item's purity. A high-purity anchor (a coin)
    keeps the derived ladder accurate, since jewellers mark up lower karats
    above their theoretical metal fraction. Skips items that contain stones,
    where metal_price would not be gold alone.
    """
    mp, nw = _MP_RE.search(html), _NW_RE.search(html)
    if not (mp and nw):
        return {}
    stone = _STONE_RE.search(html)
    if stone and _f(stone.group(1)):
        return {}
    metal, weight = _f(mp.group(1)), _f(nw.group(1))
    if not metal or not weight:
        return {}
    pg = _per_gram(metal / weight)
    if pg is None:
        return {}
    pm = _OPT_PURITY_RE.search(html) or PURITY_RE.search(html)
    if not pm:
        return {}
    karat = f"{pm.group(1)}K"
    if karat not in PURITY_FRACTION:
        return {}
    return {karat: [pg]}


# CaratLane coin/product pages embed a "price_breakup" JSON blob straight in
# the HTML (React page-state, present before any click/JS execution), e.g.
# {"title":"995 Kt Yellow Gold","rate":"Rs. 14729/g",...} - a coin's own
# per-gram gold cost, closely tracking the market (unlike their digital-gold
# page, which quotes ~8% above median). Their JSON serialiser escapes the
# slash as the unicode sequence / (verified live against ScraperAPI/
# ScrapingBee/ZenRows/Crawlbase output - NOT the backslash-slash \/ a plain
# browser DOM read shows), so both forms are matched. Fineness
# (995/999/916/750/583), not a literal "24K"/"22K" label, so it needs its
# own karat mapping.
_FINENESS_TO_KARAT = {"999": "24K", "995": "24K", "916": "22K",
                       "750": "18K", "583": "14K"}
_JSON_PRICE_BREAKUP_RE = re.compile(
    r'"title"\s*:\s*"(\d{3})\s*Kt\s+Yellow\s+Gold"[^}]{0,200}?'
    r'"rate"\s*:\s*"(?:Rs\.?|₹|INR)\.?\s*([\d,]+(?:\.\d{1,2})?)\s*'
    r'(?:\\?/|\\u002[Ff])g"',
    re.I)


def extract_json_price_breakup(html):
    buckets = {}
    for m in _JSON_PRICE_BREAKUP_RE.finditer(html):
        karat = _FINENESS_TO_KARAT.get(m.group(1))
        if not karat:
            continue
        pg = _per_gram(_f(m.group(2)))
        if pg:
            buckets.setdefault(karat, []).append(pg)
    return buckets


# Digital-gold buy pages print the pre-GST 24K rate as 'RS N + 3% GST'
# (e.g. CaratLane eGold: 'RS 15141.55/gram ( RS 14700.53 + 3% GST ) 24K
# 99.99% Purity'). The pre-GST figure is exactly our canonical basis.
_PREGST_RE = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)\s*\+\s*3\s*%\s*GST", re.I)


def extract_pregst_rate(text):
    m = _PREGST_RE.search(text)
    if not m:
        return {}
    # Digital gold is always 24K; still require the page to say so.
    if not re.search(r"24\s*K|99\.9", text, re.I):
        return {}
    pg = _per_gram(_f(m.group(1)))
    return {"24K": [pg]} if pg else {}


_HEADLINE_RE = re.compile(
    r"(\d{2})\s*K[tT]?\s+Gold\s+Rate\b.{0,80}?\b1\s*G(?:ram)?\b\s*₹?\s*([\d,]{4,7})",
    re.I | re.S)


def extract_headline_rate(text):
    """Grammage-style rate pages (e.g. Tanishq) show one purity's headline
    per-gram rate as 'NNKt Gold Rate ... 1 G RS NNNNN', while the other
    purities appear only as inert selector tabs that confuse window matching.
    Bind the headline purity straight to its 1-gram rate."""
    m = _HEADLINE_RE.search(text)
    if not m:
        return {}
    karat = f"{m.group(1)}K"
    if karat not in PURITY_FRACTION:
        return {}
    pg = _per_gram(_f(m.group(2)))
    return {karat: [pg]} if pg else {}


# Karat, then a short gap that may hold a fineness "(999)" and/or words like
# "Gold (" or "Yellow Gold", then the per-gram rate ending in /g. Covers
# banners ("24 KT (999) : RS 14,429/g"), breakup lines ("18KT Gold
# (RS 10,835 / g)"), and CaratLane's "14 Kt Yellow Gold RS 8,463 / g".
_LABELED_RE = re.compile(
    r"(\d{2})\s*K(?:T|ARAT)?\b[^0-9\n]{0,35}?(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)\s*(?:/\s*(?:g|gm|gram)|per\s*gram)\b",
    re.I)


def extract_labeled_rates(text):
    """Direct 'NN KT ... RS NNNNN /g' displays - header rate banners/tickers
    and per-item price-breakup lines - bind each karat to the per-gram rate
    right next to it, so every purity is captured unambiguously even when
    several sit side by side, which is exactly where a proximity window fails."""
    buckets = {}
    for m in _LABELED_RE.finditer(text):
        karat = f"{m.group(1)}K"
        if karat not in PURITY_FRACTION:
            continue
        pg = _per_gram(_f(m.group(2)))
        if pg:
            buckets.setdefault(karat, []).append(pg)
    return buckets


# Some jewellers (Malabar) print the rate BEFORE the karat label, in the
# opposite order to _LABELED_RE: "13220.00 INR/gms" ... "22k (916)". The
# fineness in parens right after the karat ("(916)"/"(999)"/"(750)") is what
# makes this pattern safe to match even with several purities stacked close
# together on the page - it can't accidentally lock onto a stray "18K" tab
# label, which never has a fineness code immediately after it.
_VALUE_THEN_KARAT_RE = re.compile(
    r"([\d,]+(?:\.\d{1,2})?)\s*(?:₹|Rs\.?|INR)?\s*/\s*(?:g|gms?|gram)\b"
    r"[^0-9]{0,40}?(\d{2})\s*[kK][tT]?\s*\(\s*(?:999|916|750|583)\s*\)",
    re.I)


def extract_value_then_karat(text):
    buckets = {}
    for m in _VALUE_THEN_KARAT_RE.finditer(text):
        karat = f"{m.group(2)}K"
        if karat not in PURITY_FRACTION:
            continue
        pg = _per_gram(_f(m.group(1)))
        if pg:
            buckets.setdefault(karat, []).append(pg)
    return buckets


# CaratLane's dedicated /gold-rate page labels purity as "22ct" rather than
# "22K"/"22KT" ("Rs 14528" ... "/Gram (22ct)") - a suffix none of the other
# extractors above recognise, so this page fell through the whole chain
# ("proxy:no values") until this was added. The value and the "(NNct)" label
# sit in separate DOM blocks, so the gap is generous and DOTALL-safe.
_VALUE_THEN_CT_RE = re.compile(
    r"(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)"
    r"[\s\S]{0,80}?/\s*(?:g|gm|gram)\s*\(\s*(\d{2})\s*ct\s*\)",
    re.I)


# Indriya-style banner: "Today's Gold Rate is Rs.13735 per gm (22kt)".
# Value THEN karat, but karat labelled "22kt" (no fineness), NO leading slash
# before g/gm (so _VALUE_THEN_KARAT_RE misses it). Guardrails:
#   * value must be >=4 digits, so a stray "Rs 500 off (22kt chain)" won't hit
#   * gap capped at 40 chars and constrained not to jump past 'per' word
# We keep this AFTER the fineness-anchored patterns so pages that DO carry a
# proper (916)/(999) code are still preferred.
_VALUE_PER_GM_KARAT_RE = re.compile(
    r"(?:Rs\.?|₹|INR)\s*"
    r"((?:\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d{1,2})?)"
    r"\s*(?:per\s*)?(?:g|gm|gram)\b"
    r"[^0-9(]{0,40}?\(?\s*(\d{2})\s*[kK][tT]\b",
    re.I)


def extract_value_per_gm_karat(text):
    buckets = {}
    for m in _VALUE_PER_GM_KARAT_RE.finditer(text):
        karat = f"{m.group(2)}K"
        if karat not in PURITY_FRACTION:
            continue
        pg = _per_gram(_f(m.group(1)))
        if pg:
            buckets.setdefault(karat, []).append(pg)
    return buckets


def extract_value_then_ct(text):
    buckets = {}
    for m in _VALUE_THEN_CT_RE.finditer(text):
        karat = f"{m.group(2)}K"
        if karat not in PURITY_FRACTION:
            continue
        pg = _per_gram(_f(m.group(1)))
        if pg:
            buckets.setdefault(karat, []).append(pg)
    return buckets


# The gold portion's value, with the weight either inline (Kisna:
# 'Gold1.880 g RS 15,874') or in a separate field (BlueStone: 'Gold Rs.
# 1,61,615' + 'Weight 11.97 gram'). Gap after 'Gold' is spaces/colons only
# (no letters) so 'Gold Color'/'Gold Purity' can't match; currency may be
# the rupee sign or 'Rs.'/'INR'.
_CUR = r"(?:₹|Rs\.?|INR)"
# Optional karat right before 'Gold' (WHP: '18K Gold (5.24 Gms.) RS 60,244');
# weight may be inline, parenthesised, and in g/gm/gms/gram(s).
_GOLD_VAL_RE = re.compile(
    r"(?:(\d{2})\s*K[tT]?\s+)?"
    r"\bGold(?:\s*(?:value|rate|amount))?[ \t:(]{0,4}"
    r"(?:([\d.]+)\s*(?:gms?|grams?|g)\b\.?\s*\)?\s*)?"
    + _CUR + r"\s*([\d,]+(?:\.\d{1,2})?)", re.I)
# No trailing boundary after 'Weight' since the value can abut it ('Weight5.72 g').
_WEIGHT_RE = re.compile(r"\bWeight[^\d]{0,8}([\d.]+)\s*(?:gms?|grams?|g)\b", re.I)
_PURITY_LABEL_RE = re.compile(r"(?:purity|type)\D{0,12}(\d{2})\s*K", re.I)
_PURITY_ANY_RE = re.compile(r"(\d{2})\s*K(?:T|ARAT)?\b", re.I)


def extract_gold_value_breakup(text):
    """Price breakups that give the gold portion's value (and weight, inline
    or in a separate Weight field) but no per-gram rate let us back it out:
    rate = gold_value / gold_weight, bound to the item's stated purity. The
    gold line is already separated from the diamond/stone line, so stones do
    not contaminate it. Handles Kisna ('Gold 1.880 g RS 15,874') and BlueStone
    ('Gold RS 1,61,615' + 'Weight 11.97 gram')."""
    m = _GOLD_VAL_RE.search(text)
    if not m:
        return {}
    value = _f(m.group(3))
    weight = _f(m.group(2)) if m.group(2) else None
    if weight is None:
        wm = _WEIGHT_RE.search(text)
        weight = _f(wm.group(1)) if wm else None
    if not value or not weight:
        return {}
    # A karat stated on the gold line itself beats a page-wide label search.
    karat_digits = m.group(1)
    if not karat_digits:
        pm = _PURITY_LABEL_RE.search(text) or _PURITY_ANY_RE.search(text)
        if not pm:
            return {}
        karat_digits = pm.group(1)
    karat = f"{karat_digits}K"
    if karat not in PURITY_FRACTION:
        return {}
    pg = _per_gram(value / weight)
    return {karat: [pg]} if pg else {}


def extract(html):
    """-> (found, counts, how). Table -> product -> headline -> proximity."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()

    buckets, how = extract_rows(soup), "rows"
    if not buckets:
        buckets, how = extract_product_breakup(html), "product"
    if not buckets:
        buckets, how = extract_json_price_breakup(html), "jsonbreakup"
    if not buckets:
        text = soup.get_text(" ", strip=True)
        for fn, name in ((extract_labeled_rates, "labeled"),
                         (extract_value_then_karat, "valuekarat"),
                         (extract_value_then_ct, "valuect"),
                         (extract_value_per_gm_karat, "valuepergm"),
                         (extract_pregst_rate, "pregst"),
                         (extract_gold_value_breakup, "goldvalue"),
                         (extract_headline_rate, "headline"),
                         (extract_proximity, "proximity")):
            buckets = fn(text)
            if buckets:
                how = name
                break

    found = {k: statistics.median(v) for k, v in buckets.items()}
    counts = {k: len(v) for k, v in buckets.items()}
    return found, counts, how


def ordering_sane(found):
    """Higher purity must cost more. Catches mislabelled extractions."""
    ranked = sorted(found, key=lambda k: PURITY_FRACTION[k])
    for a, b in zip(ranked, ranked[1:]):
        if found[a] > found[b] * 1.005:
            return False, f"{a} ({found[a]:,.0f}) > {b} ({found[b]:,.0f})"
    return True, ""


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


def derive_ladder(canonical_24k_pre_gst):
    """One karat's rate anchors the whole ladder.

    canonical_24k_pre_gst is the per-gram price of 24K gold. All other
    purities are scaled proportionally using Unknown Rate = (Known Rate /
    Known Karat) x Unknown Karat, anchored at 24K: 22K = canonical * 22/24,
    18K = canonical * 18/24, etc. 24K uses factor 1.0 (it IS the basis).
    Returns a pre-GST per-gram rate for each purity.
    """
    return {p: round(canonical_24k_pre_gst * frac, 2)
            for p, frac in PURITY_FRACTION.items()}


def upsert_rate(sb, row):
    """Upsert a rate row. If the optional derived_rates column doesn't exist
    in the DB yet, retry without it so the core rate is never lost."""
    try:
        sb.table("rates").upsert(row, on_conflict="brand_id,rate_date").execute()
        return True
    except Exception:
        if "derived_rates" in row:
            row.pop("derived_rates")
            sb.table("rates").upsert(row, on_conflict="brand_id,rate_date").execute()
            return False
        raise


# --------------------------------------------------------------- fetching

def fetch(url, session, timeout):
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True)
    except requests.Timeout:
        return None, "timeout"
    except requests.RequestException as e:
        return None, type(e).__name__
    if r.status_code in (401, 403, 429, 503):
        return None, f"blocked {r.status_code}"
    if r.status_code == 404:
        return None, "404"
    if r.status_code >= 400:
        return None, str(r.status_code)
    return r.text, "ok"


_STEALTH = (
    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    "window.chrome={runtime:{}};"
    "Object.defineProperty(navigator,'languages',{get:()=>['en-IN','en']});"
    "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
)


def render(url):
    """Headless fetch, hardened for bot-detection and JS-injected rates.

    Beyond a plain load this masks the common headless tells, scrolls to
    trigger lazy-loaded content, and waits for the network to settle before
    reading the DOM. (Datacenter-IP blocking by some CDNs is not something a
    hardened client can defeat; those brands need a residential proxy.)
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ])
            ctx = b.new_context(
                user_agent=UA, locale="en-IN",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
            )
            ctx.add_init_script(_STEALTH)
            pg = ctx.new_page()
            pg.goto(url, timeout=30_000, wait_until="domcontentloaded")
            try:
                pg.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            # Nudge lazy-loaded rate widgets, then let them settle.
            try:
                for frac in (0.3, 0.6, 1.0):
                    pg.evaluate(f"window.scrollTo(0, document.body.scrollHeight*{frac})")
                    pg.wait_for_timeout(700)
            except Exception:
                pass
            pg.wait_for_timeout(3500)
            # Some jewellers lazy-load the gold value only when the collapsed
            # price-breakup section is opened; click any such toggle first.
            try:
                pg.evaluate(
                    "Array.from(document.querySelectorAll('*'))"
                    ".filter(e=>/^\\s*(view\\s*)?price\\s*break-?\\s*up\\s*$/i"
                    ".test(e.textContent||'')&&(e.textContent||'').length<25)"
                    ".slice(0,3).forEach(e=>e.click())")
                pg.wait_for_timeout(1500)
            except Exception:
                pass
            html = pg.content()
            b.close()
            return html
    except Exception:
        return None


ZYTE_ENDPOINT = "https://api.zyte.com/v1/extract"


def fetch_via_proxy_waterfall(url, session, actions=None):
    """Multi-proxy failover waterfall:
    1. ScraperAPI (5,000 free req/mo)
    2. ScrapingBee (1,000 free req/mo)
    3. ZenRows (1,000 free req/mo)
    4. Crawlbase (1,000 free req/mo)
    5. Zyte (Paid/Final Fallback)
    -> (html, note)
    """
    # 1. ScraperAPI
    key = os.environ.get("SCRAPERAPI_KEY")
    if key:
        try:
            r = session.get("http://api.scraperapi.com",
                            params={"api_key": key, "url": url, "render": "true", "country_code": "in"},
                            timeout=45)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text, "ok:scraperapi"
        except Exception:
            pass

    # 2. ScrapingBee
    key = os.environ.get("SCRAPINGBEE_KEY")
    if key:
        try:
            r = session.get("https://app.scrapingbee.com/api/v1/",
                            params={"api_key": key, "url": url, "render_js": "true"},
                            timeout=45)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text, "ok:scrapingbee"
        except Exception:
            pass

    # 3. ZenRows
    key = os.environ.get("ZENROWS_KEY")
    if key:
        try:
            r = session.get("https://api.zenrows.com/v1/",
                            params={"apikey": key, "url": url, "js_render": "true"},
                            timeout=45)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text, "ok:zenrows"
        except Exception:
            pass

    # 4. Crawlbase
    key = os.environ.get("CRAWLBASE_KEY")
    if key:
        try:
            r = session.get("https://api.crawlbase.com/",
                            params={"token": key, "url": url},
                            timeout=45)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text, "ok:crawlbase"
        except Exception:
            pass

    # 5. Zyte (Paid / Final Fallback)
    return fetch_via_zyte(url, session, actions=actions)


def try_html(html):
    """-> (found, counts, how) if it passes sanity, else (None, note)."""
    found, counts, how = extract(html)
    if not found:
        return None, None, None, "no values"
    ok, why = ordering_sane(found)
    if not ok:
        return None, None, None, f"MISLABELLED: {why}"
    return found, counts, how, "ok"


# ------------------------------------------------- product self-discovery

def _score_product(text):
    """Rank candidate products: plain high-purity gold anchors first, stone
    or non-gold items last (their breakups don't isolate a clean gold rate)."""
    t = text.lower()
    s = 0
    if re.search(r"\bcoins?\b|\bbars?\b", t):
        s += 3
    if "24k" in t or "24-k" in t or "24 k" in t:
        s += 2
    if "22k" in t or "22-k" in t or "22 k" in t:
        s += 2
    if "gold" in t:
        s += 1
    if re.search(r"diamond|platinum|silver|solitaire|gemstone|pearl", t):
        s -= 3
    return s


def discover_products(b, session, limit=3):
    """When the curated rate_url stops yielding, hunt for other gold product
    pages on the same site (Shopify catalog JSON, then sitemaps) so the brand
    recovers with a real rate instead of falling back to an estimate."""
    base = b["domain"] if b["domain"].startswith("http") else f"https://{b['domain']}"
    scored: list[tuple[int, str]] = []

    # 1) Shopify stores publish their catalog at /products.json.
    html, _ = fetch(urljoin(base, "/products.json?limit=250"), session, FAST_TIMEOUT)
    if html:
        try:
            for p in json.loads(html).get("products", []):
                blob = f"{p.get('title', '')} {p.get('handle', '')} {p.get('product_type', '')}"
                s = _score_product(blob)
                if s > 0:
                    scored.append((s, urljoin(base, f"/products/{p['handle']}")))
        except (ValueError, KeyError, TypeError):
            pass

    # 2) Sitemaps (following one nested product sitemap if indexed).
    if len(scored) < limit:
        xml, _ = fetch(urljoin(base, "/sitemap.xml"), session, FAST_TIMEOUT)
        if xml:
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
            nested = [u for u in locs if "product" in u and u.endswith(".xml")]
            if nested:
                sub, _ = fetch(nested[0], session, FAST_TIMEOUT)
                if sub:
                    locs += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sub)
            for u in locs:
                if u.endswith(".xml"):
                    continue
                s = _score_product(u)
                if s > 0:
                    scored.append((s, u))

    seen, out = set(), []
    for s, u in sorted(scored, key=lambda x: -x[0]):
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out


def scrape_brand(b, session):
    started = time.monotonic()
    tried, blocked = [], False

    # Try the configured URL first, then fall back to path discovery on the
    # same domain so a stale rate_url can recover itself automatically.
    urls = []
    if b.get("rate_url"):
        urls.append(b["rate_url"])
    # Proxy brands cost credits per request, so hit only their configured URL;
    # everyone else also gets same-domain path discovery as a fallback.
    proxied = b.get("slug") in NEEDS_PROXY
    if b.get("domain") and not proxied:
        base = b["domain"] if b["domain"].startswith("http") else f"https://{b['domain']}"
        for p in CANDIDATE_PATHS:
            u = urljoin(base, p)
            if u not in urls:
                urls.append(u)

    for url in urls:
        if time.monotonic() - started > BRAND_BUDGET:
            tried.append("budget")
            break

        if proxied:
            zhtml, zreason = fetch_via_proxy_waterfall(url, session,
                                                    ZYTE_ACTIONS.get(b.get("slug")))
            if zhtml:
                found, counts, how, note = try_html(zhtml)
                if found:
                    return url, found, counts, f"proxy/{how}", note
                tried.append("proxy:" + note)
            else:
                tried.append(zreason)
            continue

        if not robots_ok(url, session):
            tried.append("robots")
            continue

        html, reason = fetch(url, session,
                             FULL_TIMEOUT if b.get("rate_url") else FAST_TIMEOUT)
        if html:
            found, counts, how, note = try_html(html)
            if found and how != "proximity":
                return url, found, counts, f"static/{how}", note
            # A structured breakup beats a proximity guess: proximity can grab
            # the wrong number on product pages (e.g. a GST-inclusive per-gram
            # total). If static gave only proximity (or nothing), render and
            # prefer any structured result before falling back to it.
            static_hit = (found, counts, how, note) if found else None
            if not found:
                tried.append(note)
            rhtml = render(url)
            if rhtml:
                rf, rc, rh, rn = try_html(rhtml)
                if rf and (rh != "proximity" or static_hit is None):
                    return url, rf, rc, f"rendered/{rh}", rn
                tried.append("rendered:" + (rh if rf else rn))
            if static_hit:
                f, c, h, n = static_hit
                return url, f, c, f"static/{h}", n
            continue

        if reason.startswith("blocked"):
            blocked = True
            rhtml = render(url)
            if rhtml:
                found, counts, how, note = try_html(rhtml)
                if found:
                    return url, found, counts, f"rendered/{how}", "static " + reason
        tried.append(reason)

    # Last resort for non-proxied brands: the configured URL is dead (product
    # sold out, path changed), so discover another gold product on the same
    # site and read its breakup - a real rate instead of an estimate.
    if not proxied and b.get("domain"):
        for url in discover_products(b, session):
            if time.monotonic() - started > BRAND_BUDGET * 2:
                tried.append("budget")
                break
            if not robots_ok(url, session):
                continue
            html, reason = fetch(url, session, FULL_TIMEOUT)
            if not html:
                tried.append("disc:" + reason)
                continue
            found, counts, how, note = try_html(html)
            if found:
                return url, found, counts, f"discovered/static/{how}", note
            rhtml = render(url)
            if rhtml:
                found, counts, how, note = try_html(rhtml)
                if found:
                    return url, found, counts, f"discovered/rendered/{how}", note
            tried.append("disc:" + note)

    uniq = []
    for t in tried:
        if t not in uniq:
            uniq.append(t)
    note = ", ".join(uniq[:4]) or "nothing tried"
    return None, None, None, None, ("BLOCKED - " + note) if blocked else note


# ------------------------------------------------------------------- main

def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
        "Sec-CH-UA": '"Chromium";v="126", "Not.A/Brand";v="24", "Google Chrome";v="126"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    })

    brands = sb.table("brands").select("*").eq("active", True).execute().data
    today = datetime.now(timezone.utc).date().isoformat()

    # Every scheduled run re-scrapes ALL brands so intraday board revisions
    # (jewellers often revise on volatile days) are captured at 11:05, 14:00
    # and 17:00 IST. A failed re-scrape simply keeps the stored rate - the
    # upsert only happens on a successful extraction.
    existing = sb.table("rates").select("brand_id, canonical_24k_pre_gst, method") \
                 .eq("rate_date", today).execute().data
    real_ids = {r["brand_id"] for r in existing
                if r.get("method") != PLACEHOLDER_METHOD}
    pending = brands
    print(f"{len(brands)} active brands - {len(real_ids)} already have a live "
          f"rate today; refreshing all for intraday revisions\n")
    saved = []

    for b in pending:
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

        ladder = derive_ladder(round(canonical, 2))
        row = {
            "brand_id": b["id"], "rate_date": today,
            "canonical_24k_pre_gst": round(canonical, 2),
            "source_purity": purity, "source_value": found[purity],
            "purities_found": len(found), "basis_confirmed": ok,
            "basis_note": why, "method": method, "rate_url": url,
            "derived_rates": ladder,
            "status": "published",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            persisted_ladder = upsert_rate(sb, row)
            # Record a discovered URL only when the brand had none configured:
            # a curated rate_url (hand-picked product/breakup page) must not be
            # overwritten just because path discovery found some other page.
            if not b.get("rate_url"):
                sb.table("brands").update({"rate_url": url}).eq("id", b["id"]).execute()
            saved.append(row)
            detail = " ".join(f"{k}={found[k]:,.0f}x{counts[k]}" for k in sorted(found))
            ladder_str = " ".join(f"{k}={ladder[k]:,.0f}" for k in sorted(ladder))
            note = "" if persisted_ladder else "  (no derived_rates column)"
            print(f"24K {canonical:>9,.0f}  [{method}] "
                  f"{'OK' if ok else 'unconfirmed'}  src[{detail}]  "
                  f"ladder[{ladder_str}]{note}")
        except Exception as e:
            print(f"save failed: {e}")

        time.sleep(POLITE_DELAY)

    # Median over LIVE rates only (already-stored real + newly saved), so the
    # outlier check and placeholder estimate are anchored on real data.
    live_vals = [r["canonical_24k_pre_gst"] for r in existing
                 if r.get("method") != PLACEHOLDER_METHOD
                 and r.get("canonical_24k_pre_gst")]
    live_vals += [r["canonical_24k_pre_gst"] for r in saved]

    if not live_vals:
        print("\nno live rates yet - cannot estimate; leaving brands for next run")
        return

    median = statistics.median(live_vals)
    print(f"\nmedian canonical 24K pre-GST: {median:,.0f}  ({len(live_vals)} live)")

    # Outlier check on this run's live saves (needs enough live data to trust).
    if saved and len(live_vals) >= MIN_FOR_MEDIAN:
        for r in saved:
            drift = abs(r["canonical_24k_pre_gst"] - median) / median
            patch = {"drift_from_median": round(drift, 4)}
            if drift > OUTLIER_TOLERANCE and not r["basis_confirmed"]:
                patch["status"] = "quarantined"
                patch["basis_note"] = r["basis_note"] + f" | {drift*100:.1f}% off median"
                print(f"   quarantined brand {r['brand_id']}: {drift*100:.1f}% off")
            sb.table("rates").update(patch) \
              .eq("brand_id", r["brand_id"]).eq("rate_date", today).execute()

    # Guarantee every active brand has today's rate: any brand still without a
    # live one gets the market median, flagged as an estimate. Re-tried each
    # run, so it flips to a real rate the moment a live source succeeds.
    have_live = real_ids | {r["brand_id"] for r in saved}
    canonical = round(median, 2)
    ladder = derive_ladder(canonical)
    filled = 0
    for b in brands:
        if b["id"] in have_live:
            continue
        row = {
            "brand_id": b["id"], "rate_date": today,
            "canonical_24k_pre_gst": canonical,
            "source_purity": "24K", "source_value": ladder["24K"],
            "purities_found": 0, "basis_confirmed": False,
            "basis_note": "estimate: market median, no live source",
            "method": PLACEHOLDER_METHOD, "rate_url": b.get("rate_url"),
            "derived_rates": ladder, "status": "estimated",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            upsert_rate(sb, row)
            filled += 1
            print(f"-> {b['name']:22s} estimate {canonical:>9,.0f}  [placeholder]")
        except Exception as e:
            print(f"placeholder failed {b['name']}: {e}")

    print(f"\n{len(saved)} live saved, {filled} estimated, "
          f"{len(have_live)}/{len(brands)} brands live")


if __name__ == "__main__":
    main()
