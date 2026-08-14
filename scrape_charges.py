#!/usr/bin/env python3
"""Making-charge comparison scraper (runs ~once every 15 days).

For brands that publish a product price breakup, sample MULTIPLE products per
category and record the making charge as % of gold value, then aggregate to a
median per (brand, category). Discovery brands are enumerated from their
product sitemap; others use a curated URL. Best-effort - items without a clean
% are skipped. Writes docs/making-charges.json.
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlsplit

import base64

import requests

from mc_engine import Engine

# Learned per-brand extraction profiles (auto-maintained by mc_engine).
PROFILE_PATH = "mc_profiles.json"

IST = timezone(timedelta(hours=5, minutes=30))
ZYTE_KEY = os.environ.get("ZYTE_API_KEY", "").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PER_CAT = 20           # sample size for a small discovery pool (curated
                       # seeds, a thin listing page) - sampling more than
                       # what's realistically available is meaningless
PER_CAT_MED = 60       # pool of 100-500 candidates (a partial category page)
PER_CAT_LARGE = 150    # pool of 500+ candidates (sitemap-scale) - once a
                       # brand's real catalogue is in the thousands, a
                       # 20-item sample is one unusual design away from
                       # skewing the whole category median; sample hundreds
                       # instead so the median reflects the actual catalogue
TOTAL_CAP = 600        # hard cap on product fetches per brand (4 categories
                       # at PER_CAT_LARGE, with headroom)
FETCH_WORKERS = 6      # concurrent product-page fetches per brand. Product
                       # pages were fetched one at a time - fine at
                       # PER_CAT=20, but a serial killer once samples run into
                       # the hundreds (BlueStone/Kisna). A brand's fetches
                       # only ever hit that one brand's domain, so bounding
                       # concurrency here is also what keeps this polite -
                       # a fixed pool of parallel connections, not an
                       # unbounded burst. Dialed back from 10: a production
                       # run showed some brands' smaller sites (e.g. Waman
                       # Hari Pethe) slow to a crawl and start timing out
                       # under 10 concurrent connections, which silently
                       # looked like "no data for this category" rather than
                       # what it actually was - the site couldn't keep up.
FETCH_RETRIES = 1      # retries for a failed fetch (no html / timeout) before
                       # giving up on that URL - a fetch failure under
                       # concurrent load is often transient (the origin
                       # momentarily overloaded), not permanent.


def sample_size(pool_size):
    """How many candidate URLs to actually fetch for a category, given how
    many were discovered. Scales up only when the pool genuinely supports
    it - small pools already get everything they have."""
    if pool_size >= 500:
        return PER_CAT_LARGE
    if pool_size >= 100:
        return PER_CAT_MED
    return PER_CAT

# slug keyword -> category. v1 categories only (Bangles, Rings, Earrings,
# Mangalsutra) - user explicitly deferred Chain, Necklace, Bracelet, Pendant,
# Coin to v2. Order matters (earring must come before ring).
CAT_RULES = [
    ("mangalsutra", "Mangalsutra"),
    ("earring", "Earrings"), ("jhumk", "Earrings"), ("stud", "Earrings"),
    ("bangle", "Bangle"), ("kada", "Bangle"),
    ("ring", "Ring"),
]

# All 7 brands verified feasible via diag-making workflow. Direct fetch is
# tried first for every brand; the proxy waterfall is only invoked when direct
# fails - so brands that DO respond direct (Senco/Kisna/ORRA/PN Gadgil) never
# spend a proxy request. proxy_hint=True on the remaining 3 (BlueStone/
# CaratLane/WHP) is cosmetic - it just documents that we've seen those need
# proxy in practice; fetch() ignores it.
_CL = "https://www.caratlane.com/jewellery/"
# Capture the FULL path including .html - capturing only the slug produced
# extension-less URLs after urljoin(), which 404'd and zeroed out this brand.
_CL_PROD = r'(/jewellery/[a-z0-9][a-z0-9-]{4,}?-[a-z]{1,3}\d{4,}-[0-9a-z]{4,}\.html)'
_BS_PROD = r'href="(https://www\.bluestone\.com/[^"]+?~\d+\.html)"'
# Candere's own category listings are thin server-side; its Magento search
# results page is not (30+ product links per query from page 1 alone) and
# needs no discovery route beyond a plain category-keyword search - product
# pages already extract cleanly with the existing json_flat_keys strategy.
_CD_PROD = r'href="(https://www\.candere\.com/[a-z0-9][a-z0-9-]+\.html)"'
_GRT_PROD = r'href="(/all-jewellery/[a-z-]+/[a-z0-9-]+\.html)"'

DISCOVER = [
    # Sitemap route works well here (80 items in the last full run).
    {"brand": "Senco Gold",
     "sitemaps": ["https://sencogoldanddiamonds.com/sitemap-product.xml"]},

    # Sitemaps 404; category listings + ?baseOffset pagination verified good
    # (25 bangles / 16 rings / 8 earrings). Mangalsutra grid is client-side,
    # so it stays thin until seeds are added.
    {"brand": "CaratLane", "product_re": _CL_PROD,
     "listings": {"Bangle": _CL + "bangles.html",
                  "Ring": _CL + "rings.html",
                  "Earrings": _CL + "earrings.html",
                  "Mangalsutra": _CL + "mangalsutra.html"}},

    # Search/listing pages are client-rendered (0 links in server HTML), so
    # this brand runs on hand-verified seeds until a server-rendered listing
    # is found. Extraction itself is solid: 8/8 on these URLs.
    # robots.txt (not the plain /sitemap.xml, which is a short manual index
    # that doesn't mention it) links products-sitemap.xml - 10,700+ real
    # product URLs, versus the ~10 hand-picked seeds this brand relied on
    # before because its listing/search pages are client-rendered. The
    # seeds are kept as a fallback if the sitemap route ever breaks.
    {"brand": "BlueStone", "product_re": _BS_PROD,
     "sitemaps": ["https://www.bluestone.com/products-sitemap.xml"],
     "seeds": {
        "Bangle": ["https://www.bluestone.com/bangles/the-orrale-round-bangle~79884.html",
                   "https://www.bluestone.com/bangles/the-estrella-oval-bangle~34771.html"],
        "Ring": ["https://www.bluestone.com/preset+solitaire+rings/the-aphaea-ring-for-him~83508.html",
                 "https://www.bluestone.com/rings/the-petillante-ring~86191.html",
                 "https://www.bluestone.com/rings/the-dimas-textured-band-for-her~81692.html"],
        "Earrings": ["https://www.bluestone.com/earrings/the-mathilda-drop-earrings~8976.html",
                     "https://www.bluestone.com/earrings/the-marianna-stud-earrings~67286.html",
                     "https://www.bluestone.com/earrings/the-rua-stud-earrings~60693.html"],
        "Mangalsutra": ["https://www.bluestone.com/mangalsutra+chains/the-yosni-mangalsutra~81520.html",
                        "https://www.bluestone.com/mangalsutra/the-karnika-mangalsutra-pendant~69986.html"],
     }},

    {"brand": "Waman Hari Pethe",
     "sitemaps": ["https://whpjewellers.com/sitemap.xml"]},

    # Shopify. Listings + pagination verified good; seeds cover the gap.
    # products-sitemap.xml (found via the plain /sitemap.xml index - not
    # listed among the site's category/collection sitemaps, easy to miss)
    # carries 5700+ real product URLs, dwarfing the old listings+seeds route
    # which only ever found the hand-picked seeds (listing pages are
    # client-rendered, same as the pricing data - see rsc_price_breakup in
    # mc_engine.py). Kept listings+seeds as a fallback.
    {"brand": "Kisna", "pagination": "page",
     "sitemaps": ["https://www.kisna.com/products-sitemap.xml"],
     "product_re": r'href="(/products/[a-z0-9][a-z0-9-]*)(?:\?[^"]*)?"',
     "listings": {"Ring": "https://www.kisna.com/jewellery/rings+18kt",
                  "Earrings": "https://www.kisna.com/jewellery/earrings+24kt+18kt",
                  "Mangalsutra": "https://www.kisna.com/jewellery/mangalsutra",
                  "Bangle": "https://www.kisna.com/jewellery/bangles"},
     "seeds": {
        "Ring": ["https://www.kisna.com/products/embrace-love-gold-ring",
                 "https://www.kisna.com/products/taisna-ring",
                 "https://www.kisna.com/products/andelise-ring",
                 "https://www.kisna.com/products/twinora-ring"],
        "Earrings": ["https://www.kisna.com/products/sunshine-blossom-gold--earring",
                     "https://www.kisna.com/products/florafanatic-gold-earring",
                     "https://www.kisna.com/products/delicate-blossom-gold-earring"],
        "Mangalsutra": ["https://www.kisna.com/products/narcia-diamond-mangalsutra-with-chain",
                        "https://www.kisna.com/products/linked-squarelet-diamond-mangalsutra-with-chain"],
        "Bangle": ["https://www.kisna.com/products/floriance-heart-filigree-gold-bangle",
                   "https://www.kisna.com/products/starbloom-emerald-diamond-bangle",
                   "https://www.kisna.com/products/pink-amour-diamond-bangle",
                   "https://www.kisna.com/products/bloomira-gold-bangle"],
     }},
    # robots.txt advertises /sitemap.xml, which 404s (Magento's real default
    # location is /media/sitemap/sitemap.xml) - that wrong path is why this
    # brand previously discovered zero URLs at all.
    {"brand": "ORRA",
     "sitemaps": ["https://www.orra.co.in/media/sitemap/sitemap.xml"]},
    {"brand": "PN Gadgil",
     "sitemaps": ["https://www.pngjewellers.com/sitemap.xml"]},
    {"brand": "Candere", "product_re": _CD_PROD,
     "listings": {"Bangle": "https://www.candere.com/catalogsearch/result/?q=bangle",
                  "Ring": "https://www.candere.com/catalogsearch/result/?q=ring",
                  "Earrings": "https://www.candere.com/catalogsearch/result/?q=earrings",
                  "Mangalsutra": "https://www.candere.com/catalogsearch/result/?q=mangalsutra"}},
    # Product pages carry the full price breakup as a JSON object
    # re-serialized as an escaped string (see escaped_json_block in
    # mc_engine.py) - verified across ring/earring products, 15.7-21.1%,
    # 0.99 confidence (every component reconciles against the stated total).
    # Each listing page shows ~12 items via an internal REST query
    # (page_size:12, seen in the page's own embedded state) with no
    # fetchable pagination - ?p=2 just serves a client-only shell with no
    # product grid at all, so a single listing page plateaus well under
    # PER_CAT regardless of retries. The site exposes several distinct
    # listing pages per category (a "gold jewellery" view + a broader
    # "all jewellery" view) that turned out to show different products
    # (spot-checked: /all-jewellery/ring.html's 11 products share zero SKUs
    # with /jewellery/gold-jewellery/gold-rings.html's) - unioning them is
    # the only way to get past ~12 items/category from this brand.
    {"brand": "GRT Jewellers", "product_re": _GRT_PROD,
     "listings": {"Ring": ["https://www.grtjewels.com/jewellery/gold-jewellery/gold-rings.html",
                           "https://www.grtjewels.com/all-jewellery/ring.html"],
                  "Earrings": ["https://www.grtjewels.com/jewellery/gold-jewellery/gold-earrings.html",
                              "https://www.grtjewels.com/all-jewellery/earrings.html"],
                  "Bangle": ["https://www.grtjewels.com/jewellery/gold-jewellery/bangles-and-bracelets.html",
                            "https://www.grtjewels.com/all-jewellery/bangles-bracelets.html"],
                  "Mangalsutra": ["https://www.grtjewels.com/jewellery/gold-jewellery/mangalsutras.html",
                                 "https://www.grtjewels.com/all-jewellery/mangalsutra.html"]}},
]
CURATED = []


# Ordered proxy waterfall (free tiers first, Zyte last if paid key exists).
# fetch() tries each in turn until one returns >=500 bytes at HTTP 200.
def _proxy_attempts(url):
    for key_env, name, url_tpl, params in [
        ("SCRAPERAPI_KEY", "scraperapi", "http://api.scraperapi.com",
         {"url": url, "render": "true", "country_code": "in"}),
        ("SCRAPINGBEE_KEY", "scrapingbee", "https://app.scrapingbee.com/api/v1/",
         {"url": url, "render_js": "true", "wait": "3000"}),
        ("ZENROWS_KEY", "zenrows", "https://api.zenrows.com/v1/",
         {"url": url, "js_render": "true", "wait": "3000"}),
        ("CRAWLBASE_KEY", "crawlbase", "https://api.crawlbase.com/",
         {"url": url}),
    ]:
        key = os.environ.get(key_env)
        if not key:
            continue
        p = dict(params)
        p["api_key" if name != "crawlbase" else "token"] = key
        if name == "zenrows":
            p["apikey"] = p.pop("api_key")
        yield name, url_tpl, p


def fetch(sess, url, allow_proxy=True, timeout=25, min_len=500):
    """Direct first (free), proxy waterfall only if direct fails.

    Honors the 'avoid proxy where possible' rule. Sitemap fetches pass
    allow_proxy=False - they're always static XML that direct handles.

    min_len guards against bot-wall stub pages, but sitemap INDEX files are
    legitimately tiny (a handful of <loc> entries), so callers fetching those
    pass a smaller floor - otherwise valid indexes are discarded as failures.
    Returns (html, source) or (None, err).
    """
    try:
        r = sess.get(url, timeout=timeout)
        if r.status_code == 200 and len(r.text) > min_len:
            return r.text, "direct"
        direct_err = f"direct/{r.status_code}"
    except Exception as e:
        direct_err = f"direct/{type(e).__name__}"

    if not allow_proxy:
        return None, direct_err

    for name, u, p in _proxy_attempts(url):
        try:
            r = sess.get(u, params=p, timeout=60)
            if r.status_code == 200 and len(r.text) > min_len:
                return r.text, name
        except Exception:
            continue

    # Zyte as absolute last resort (paid).
    if ZYTE_KEY:
        try:
            r = sess.post("https://api.zyte.com/v3/extract",
                          auth=(ZYTE_KEY, ""),
                          json={"url": url, "httpResponseBody": True},
                          timeout=60)
            r.raise_for_status()
            return base64.b64decode(r.json()["httpResponseBody"]).decode(
                "utf-8", "replace"), "zyte"
        except Exception:
            pass

    return None, "all-proxies-failed"


# Materials whose "metal value" is not gold - a making % against them would
# not be comparable, so drop them at the URL stage.
_NON_GOLD_RE = re.compile(r"\b(silver|platinum|titanium|steel)\b", re.I)

# Studded/diamond pieces discount the making charge against the stone's own
# markup, so their making-% is not representative of a plain gold item (see
# the stone_value gate in mc_engine._finish, which catches whatever slips
# past this). Filtering by slug here is the cheaper, earlier cut: most
# brands name the stone right in the product URL ("...-diamond-bangle",
# "...-solitaire-ring"), so skipping those candidates before ever fetching
# them means the sample we DO fetch is overwhelmingly plain gold, instead of
# spending a large chunk of a big sample on pages that just get excluded
# after the fact. Deliberately excludes "stud"/"studs" - that word means the
# earring style (stud earrings), not gem-studded, and is one of the
# CAT_RULES category keywords.
_STUDDED_RE = re.compile(
    r"\b(diamond|diamonds|solitaire|studded|gemstone|gemstones|kundan|polki|"
    r"pearl|pearls|ruby|rubies|emerald|emeralds|sapphire|sapphires|"
    r"american[- ]?diamond|americandiamond|cz|zircon|zirconia|topaz|"
    r"garnet|onyx|opal|turquoise|moissanite|navratna|navratra|stone|stones|"
    r"gem|gems)\b", re.I)


def categorize(url):
    """Map a product URL to a v1 category, or None to skip it.

    NOTE: this deliberately does NOT require the word "gold" in the URL. Doing
    so silently discarded every BlueStone product (their URLs look like
    /bangles/the-orrale-round-bangle~79884.html), which is why that brand
    yielded zero items. Non-gold items are excluded explicitly instead, and
    anything that slips through is caught later: the engine only returns a
    making % when it finds a gold/metal value in the breakup.

    Studded/diamond items are excluded the same way - see _STUDDED_RE.
    """
    s = url.lower()
    if _NON_GOLD_RE.search(s) or _STUDDED_RE.search(s):
        return None
    for kw, cat in CAT_RULES:
        if kw in s:
            return cat
    return None


def discover_urls(sess, sitemaps):
    """Walk sitemap(s). Sitemaps are static XML - direct fetch only, no proxy."""
    urls, seen = [], set()
    queue = list(sitemaps)
    while queue and len(seen) < 18:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        # min_len=120: sitemap indexes are often only a few hundred bytes
        t, src = fetch(sess, sm, allow_proxy=False, min_len=120)
        if not t:
            print("  sitemap fail:", sm, src)
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", t)
        for loc in locs:
            # Shopify's own nested product sitemaps carry a cursor query
            # string (…/sitemap_products_1.xml?from=X&to=Y), so the raw URL
            # never ends in ".xml" - only its path does. Checking the full
            # URL here silently treated every nested sitemap as a dead-end
            # "product" URL instead of recursing into it, which is why WHP
            # and PN Gadgil (both Shopify) previously yielded zero products:
            # every real product URL lives one level down, inside those
            # cursor-paginated sub-sitemaps.
            path = urlsplit(loc).path.lower()
            if path.endswith(".xml") and ("product" in path or "sitemap" in path):
                queue.append(loc)          # nested sitemap
            else:
                urls.append(loc)
    return urls


def collect_urls(sess, d):
    """Gather candidate product URLs for a brand from every route it declares.

    Three routes, unioned (a brand may use any combination):
      sitemaps - walk XML sitemap(s)
      listings - {category: listing_url or [listing_url, ...]}, each
                 paginated per the brand's declared "pagination" style
                 (?baseOffset= or ?page=) until PER_CAT items are found or
                 pages run out - a list unions several distinct listing
                 pages for the same category (useful when no single one
                 both shows enough items and actually paginates)
      seeds    - {category: [product_url, ...]} hand-verified fallbacks for
                 brands whose listings are client-rendered (e.g. BlueStone)
    Returns {category: [url, ...]}.
    """
    buckets = {}

    def add(cat, url):
        lst = buckets.setdefault(cat, [])
        if url not in lst:
            lst.append(url)

    for cat, urls in (d.get("seeds") or {}).items():
        for u in urls:
            # Seeds are hand-picked per category already, so they skip
            # categorize() - but still route through the same non-gold /
            # studded filters, in case a hand-picked seed turns out to be a
            # diamond piece.
            if _NON_GOLD_RE.search(u.lower()) or _STUDDED_RE.search(u.lower()):
                continue
            add(cat, u)

    for u in discover_urls(sess, d.get("sitemaps") or []):
        c = categorize(u)
        if c:
            add(c, u)

    prod_re = d.get("product_re")
    # Pagination style varies by platform - guessing wrong silently caps
    # discovery at page 1 + hand-supplied seeds, which is nowhere near
    # PER_CAT and would make the category median unfair (few items = one
    # unusual design skews the whole number). Each brand declares its style:
    #   "baseOffset" (CaratLane): ?baseOffset=20,40,60,...
    #   "page"       (Shopify, e.g. Kisna): ?page=2,3,4,...
    pag_style = d.get("pagination", "baseOffset")
    for cat, listing in (d.get("listings") or {}).items():
        # A category value may be one URL (str) or several (list) - some
        # storefronts show only ~12 items per listing with no working
        # pagination (GRT: a client-side "load more" the static fetch can't
        # trigger), so distinct listing URLs for the same category (a
        # brand-wide catalogue view alongside a gold-only one, say) are the
        # only way to reach more than one page's worth of real products.
        listing_urls = listing if isinstance(listing, list) else [listing]
        for base_listing in listing_urls:
            page_num = 1
            # Cap raised from 6 to 25 pages / PER_CAT to PER_CAT_LARGE so a
            # listing-only brand with a genuinely deep catalogue (no sitemap
            # route) isn't stopped short of a large sample - the "page
            # yielded nothing new" break below already ends the loop early
            # for brands whose real catalogue is much smaller than that.
            while page_num <= 25 and len(buckets.get(cat, [])) < PER_CAT_LARGE:
                if page_num == 1:
                    url = base_listing
                elif pag_style == "page":
                    url = f"{base_listing}?page={page_num}"
                else:
                    url = f"{base_listing}?baseOffset={(page_num - 1) * 20}"
                html, _ = fetch(sess, url, allow_proxy=True, timeout=25)
                if not html:
                    break
                before = len(buckets.get(cat, []))
                for m in re.finditer(prod_re, html) if prod_re else []:
                    cand = m.group(0) if not m.groups() else m.group(1)
                    if not cand.startswith("http"):
                        cand = urljoin(base_listing, cand)
                    if categorize(cand) == cat:
                        add(cat, cand)
                if len(buckets.get(cat, [])) == before and page_num > 1:
                    break              # page yielded nothing new
                page_num += 1
                time.sleep(0.3)
    return buckets


def fetch_batch(sess, engine, brand, items):
    """Fetch + extract a batch of (cat, url) candidates concurrently.

    Replaces the old one-at-a-time loop (with a 0.3s sleep after every direct
    fetch) - fine when a brand only needed 20 fetches, but a serial killer
    once samples run into the hundreds. Network I/O dominates a fetch, so a
    bounded thread pool (FETCH_WORKERS) turns wall-clock time into roughly
    fetches/FETCH_WORKERS instead of fetches - and IS the politeness control
    now, in place of the per-request sleep (a fixed number of concurrent
    connections to one brand's domain, not an unbounded burst).

    A first pass at FETCH_WORKERS, then up to FETCH_RETRIES more passes (at
    half the concurrency) retrying only the fetches that came back empty.
    A smaller origin can start timing out once several hundred fetches for
    one brand are in flight - without a retry, that silently reads as "no
    making % on these pages" instead of what it is, a transient failure
    under load - so a URL only counts as a real miss once a retry at gentler
    concurrency has also failed on it.

    Returns a list of (cat, url, ExtractionResult|None, src).
    """
    fetched = [None] * len(items)   # (html, src) per item, filled in below

    def run_pass(indices, workers):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fetch, sess, items[i][1], True, 25): i for i in indices}
            for fut in as_completed(futs):
                fetched[futs[fut]] = fut.result()

    run_pass(range(len(items)), FETCH_WORKERS)
    for _ in range(FETCH_RETRIES):
        failed = [i for i, r in enumerate(fetched) if not r[0]]
        if not failed:
            break
        run_pass(failed, max(2, FETCH_WORKERS // 2))

    out = []
    for i, (cat, u) in enumerate(items):
        html, src = fetched[i]
        res = engine.extract(html, brand=brand) if html else None
        out.append((cat, u, res, src))
    return out


def record_results(agg, detail, brand, results):
    """Fold a fetch_batch() result list into agg/detail. Returns (hits, proxy_hits)."""
    hits = proxy_hits = 0
    for cat, u, res, src in results:
        if src and src not in ("direct", "all-proxies-failed"):
            proxy_hits += 1
        if res and res.ok:
            hits += 1
            agg.setdefault((brand, cat), []).append(res.making_pct)
            detail.setdefault((brand, cat), []).append({
                "url": u, "pct": res.making_pct,
                "confidence": res.confidence,
                "strategy": res.strategy, "fields": res.fields})
    return hits, proxy_hits


def main():
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    # Default pool_maxsize (10) undersells FETCH_WORKERS concurrent fetches -
    # bump it so the pool doesn't start dropping/reopening connections once
    # requests are actually running in parallel.
    adapter = requests.adapters.HTTPAdapter(pool_connections=FETCH_WORKERS,
                                            pool_maxsize=FETCH_WORKERS * 2)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    engine = Engine.load(PROFILE_PATH)
    agg = {}          # (brand, cat) -> [pct,...]
    detail = {}       # (brand, cat) -> [{url, pct, conf, fields}, ...]

    for d in DISCOVER:
        brand = d["brand"]
        buckets = collect_urls(sess, d)
        candidates = []
        for cat, us in buckets.items():
            target = sample_size(len(us))
            candidates.extend((cat, u) for u in us[:target])
        candidates = candidates[:TOTAL_CAP]

        # Probe phase first, fetched concurrently: bail on the whole brand
        # only if that first batch lands zero hits - the engine has already
        # tried every strategy on those pages. Threshold is 25, not 10: with
        # the plain-gold-only stone gate, a brand whose catalogue leans
        # studded can legitimately go several fetches between hits (a real,
        # working brand), not just a broken one.
        probe, rest = candidates[:25], candidates[25:]
        results = fetch_batch(sess, engine, brand, probe)
        hits, proxy_hits = record_results(agg, detail, brand, results)
        fetched = len(results)

        if fetched >= 25 and hits == 0:
            print(f"  {brand}: no making % in first 25 items, skipping")
        elif rest:
            results = fetch_batch(sess, engine, brand, rest)
            h2, p2 = record_results(agg, detail, brand, results)
            hits += h2
            proxy_hits += p2
            fetched += len(results)

        cat_summary = [(c, len(v)) for (b, c), v in agg.items() if b == brand]
        print(f"{brand}: fetched {fetched} ({proxy_hits} via proxy), "
              f"cats {cat_summary}")

    for p in CURATED:
        html, _ = fetch(sess, p["url"], allow_proxy=True, timeout=25)
        res = engine.extract(html, brand=p["brand"]) if html else None
        if res and res.ok:
            agg.setdefault((p["brand"], p["cat"]), []).append(res.making_pct)
            print(f"{p['brand']} {p['cat']}: {res.making_pct}%")

    brands = {}
    for (brand, cat), pcts in agg.items():
        if not pcts:
            continue
        # summarize() applies MAD outlier rejection and grades confidence by
        # sample size, so one bad page cannot move a category median.
        s = engine.record(brand, cat, pcts)
        if not s.get("median"):
            continue
        row = {
            "category": cat,
            "items": s["items"],
            "making_pct_median": s["median"],
            "making_pct_min": s["min"],
            "making_pct_max": s["max"],
            "confidence": s["confidence"],
            "rejected_outliers": s["rejected"],
        }
        if s.get("drift_flag"):
            row["drift_vs_last"] = s.get("drift_vs_last")
        # a couple of real examples power the dashboard's "based on ..." text
        ex = sorted(detail.get((brand, cat), []),
                    key=lambda x: -x["confidence"])[:3]
        if ex:
            row["examples"] = [{"url": e["url"], "pct": e["pct"]} for e in ex]
        brands.setdefault(brand, []).append(row)

    out = [{"brand": b, "categories": sorted(c, key=lambda x: x["category"])}
           for b, c in sorted(brands.items())]

    payload = {
        "updated": datetime.now(IST).isoformat(),
        "note": "Making charge as % of gold value, median across multiple real "
                "products per category from each jeweller's public price "
                "breakup. Indicative - varies by specific design.",
        "brands": out,
    }
    os.makedirs("docs", exist_ok=True)
    with open("docs/making-charges.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    engine.save(PROFILE_PATH)
    tot = sum(len(v) for v in agg.values())
    print(f"charges: {len(out)} brands, {tot} products with a making %")
    print("\n" + engine.report())


if __name__ == "__main__":
    main()
