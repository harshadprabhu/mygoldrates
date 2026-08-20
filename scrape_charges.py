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
from itertools import zip_longest
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
FETCH_RETRIES = 2      # retries for a failed fetch (no html / timeout) before
                       # giving up on that URL - a fetch failure under
                       # concurrent load is often transient (the origin
                       # momentarily overloaded), not permanent. Raised from
                       # 1: BlueStone and CaratLane both had at least one
                       # production run collapse to near-zero across every
                       # category (BlueStone: 1/2/2 items) despite fine
                       # results on other runs with identical code - a
                       # single retry wasn't enough to ride out whichever
                       # brand's origin was struggling that day.
RETRY_BACKOFF = 3      # seconds to wait before each retry pass - gives an
                       # origin that was struggling under the first pass'
                       # concurrency a moment to recover, instead of
                       # re-hitting it at the same rate immediately.


def sample_size(pool_size):
    """How many candidate URLs to actually fetch for a category, given how
    many were discovered. Scales up only when the pool genuinely supports
    it - small pools already get everything they have."""
    if pool_size >= 500:
        return PER_CAT_LARGE
    if pool_size >= 100:
        return PER_CAT_MED
    # A truly tiny pool (a handful of curated seeds) already gets everything
    # it has at PER_CAT=20. But a pool of, say, 40 - a brand's category-page
    # snapshot with no real pagination - used to be silently truncated to
    # the same flat 20 regardless, discarding real already-discovered
    # candidates for free (no extra discovery requests, just fetching more
    # of what collect_urls() already found) and capping the category well
    # under the 20-30+ target even on brands with a heavy studded-item
    # rejection rate that needs the larger pool to net enough plain-gold
    # hits (BlueStone: 37-44 candidates/category, ~50-80% excluded as
    # studded, so PER_CAT=20 could never clear ~20 real hits no matter how
    # good discovery got).
    return max(PER_CAT, min(pool_size, PER_CAT_MED))

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
# Relative on category-listing pages (href="/rings/the-...~76539.html"),
# absolute on the old sitemap route - accept either.
_BS_PROD = r'href="((?:https://www\.bluestone\.com)?/[a-z0-9+]+/[a-z0-9][a-z0-9-]*~\d+\.html)"'
# Candere's own category listings are thin server-side; its Magento search
# results page is not (30+ product links per query from page 1 alone) and
# needs no discovery route beyond a plain category-keyword search - product
# pages already extract cleanly with the existing json_flat_keys strategy.
_CD_PROD = r'href="(https://www\.candere\.com/[a-z0-9][a-z0-9-]+\.html)"'
_GRT_PROD = r'href="(/all-jewellery/[a-z-]+/[a-z0-9-]+\.html)"'
# C Krishniah Chetty (Salesforce Commerce Cloud): category/browse pages and
# the sitemap both render an empty product grid server-side (AJAX-loaded) -
# only the site's own /search endpoint server-renders real product tiles.
# No homepage/session pre-fetch needed - verified the search endpoint
# returns real results on a fresh, cookie-less request.
_CKC_PROD = r'href="(/en_IN/[a-z0-9][a-z0-9-]+-CKCJ_\d+\.html)"'

DISCOVER = [
    # Sitemap route works well here (80 items in the last full run).
    {"brand": "Senco Gold",
     "sitemaps": ["https://sencogoldanddiamonds.com/sitemap-product.xml"]},

    # Sitemaps 404; category listings + ?baseOffset pagination verified good
    # (25 bangles / 16 rings / 8 earrings). Mangalsutra grid is client-side,
    # so it stays thin until seeds are added.
    # fetch_workers=3: this brand's origin has repeatedly collapsed to
    # near-zero hits on a production run (0/0/0/0, then recovered to
    # 19/20/12 on the next run with identical code) while other brands ran
    # fine at the default concurrency the same day - it can't reliably
    # sustain that many simultaneous connections.
    {"brand": "CaratLane", "product_re": _CL_PROD, "fetch_workers": 3,
     "listings": {"Bangle": _CL + "bangles.html",
                  "Ring": _CL + "rings.html",
                  "Earrings": _CL + "earrings.html",
                  "Mangalsutra": _CL + "mangalsutra.html"}},

    # products-sitemap.xml (the old discovery route) is specifically
    # blocked/throttled - the domain root loads in ~1s but that one path
    # times out completely (confirmed both directly and via curl, no proxy
    # involved), matching the 503 seen on a real run. robots.txt lists 4
    # OTHER sitemaps on this domain; productscats-sitemap.xml (not blocked)
    # is a small index of category pages, not products, but those category
    # pages themselves ARE server-rendered with real product links - just
    # not paginated (?p=2 silently returns byte-different but
    # product-identical HTML - a cached/SSR'd first page, not a real next
    # page), so multiple distinct listing URLs per category (the plain-gold
    # and metal-only filtered views from productsfilter-sitemap.xml, which
    # rank a different top-N into their own snapshot) are the only way to
    # get more than one page's worth. Verified live: this brand's catalogue
    # is heavily diamond/gemstone-accented even on rings/earrings/
    # mangalsutra pages whose URLs don't say so, so the studded filter (see
    # _STUDDED_RE) rejects the majority of candidates after fetch - the
    # extra listing URLs per category exist to compensate for that, not
    # because any one listing is thin. max_pages=1: pagination is a no-op
    # here (confirmed above), so trying pages 2-25 would just be 96 wasted
    # requests per run against a domain that already blocks one of its own
    # sitemap paths.
    # fetch_workers=3: this brand's origin has repeatedly collapsed to
    # near-zero hits on a production run (0/0/0/0, then recovered to
    # 19/20/12 on the next run with identical code) while other brands ran
    # fine at the default concurrency the same day - it can't reliably
    # sustain that many simultaneous connections.
    {"brand": "BlueStone", "product_re": _BS_PROD, "fetch_workers": 3,
     "max_pages": 1,
     "listings": {
        "Ring": ["https://www.bluestone.com/jewellery/rings.html",
                 "https://www.bluestone.com/jewellery/plain+gold-rings.html",
                 "https://www.bluestone.com/jewellery/only+metal-rings.html"],
        "Bangle": ["https://www.bluestone.com/jewellery/bangles.html",
                   "https://www.bluestone.com/jewellery/plain+gold-bangles.html"],
        "Earrings": ["https://www.bluestone.com/jewellery/earrings.html",
                     "https://www.bluestone.com/jewellery/plain+gold-earrings.html"],
        "Mangalsutra": ["https://www.bluestone.com/jewellery/mangalsutra.html",
                        "https://www.bluestone.com/jewellery/plain+gold-mangalsutra.html"],
     },
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
    # require_path: this sitemap is one flat file with every URL type mixed
    # together - real products live under /product/<slug>-<sku>, but
    # /rings, /offers/.../rings etc. all match the "Ring" category keyword
    # too and vastly outnumber real products (~93% of raw "Ring" hits were
    # non-product pages), starving the probe phase and getting the whole
    # brand skipped as "no making % found" despite real products being
    # present the whole time. Verified live: /product/ narrows it to real
    # product detail pages only.
    {"brand": "ORRA", "require_path": "/product/",
     "sitemaps": ["https://www.orra.co.in/media/sitemap/sitemap.xml"]},
    {"brand": "PN Gadgil",
     "sitemaps": ["https://www.pngjewellers.com/sitemap.xml"]},
    {"brand": "Candere", "product_re": _CD_PROD, "pagination": "p",
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

    # Ranka Jewellers investigated and NOT added: extraction works fine on
    # a single product (verified 18.9% via dom_breakup_section), but there
    # is no reliable discovery route for our 4 tracked categories. The
    # site's own sitemap_products chunk is almost entirely silver
    # coins/bars/rakhis with a handful of gold "nath" (nose-ring) items -
    # not one of our tracked categories; its Shopify collection pages
    # (e.g. /collections/gold-rings) are inconsistently curated (that
    # collection's own first listed item is a silver rakhi, not a ring).
    # No amount of URL-pattern-matching fixes a catalogue whose own
    # front-end mixes categories - this would need a different, noisier
    # discovery approach with no confidence in what it would actually turn
    # up, so it's left out rather than guessed at.

    # Salesforce Commerce Cloud. Category/browse pages AND the sitemap both
    # render an empty product grid server-side (AJAX-loaded) - only the
    # site's own /search endpoint server-renders real product tiles, no
    # session/cookie needed first (verified on a fresh, cookie-less
    # request). Pagination is &start=N&sz=21 (verified live: 21 genuinely
    # new products per page). Extraction needed a new strategy
    # (table_row_columns in mc_engine.py): its price-breakup table has an
    # "Approx. Weight" column between the label and the value column
    # ("18Kt Gold | 3.078 Grams | Rs.36,390.18 | Rs.36,390.18"), which the
    # existing label-immediately-followed-by-amount scan can't parse -
    # verified live, 19.7-21.3% across 4 real plain-gold rings.
    {"brand": "C Krishniah Chetty", "product_re": _CKC_PROD, "pagination": "start_sz",
     "listings": {"Bangle": "https://www.ckcjewellers.com/en_IN/search?q=gold+bangle",
                  "Ring": "https://www.ckcjewellers.com/en_IN/search?q=gold+ring",
                  "Earrings": "https://www.ckcjewellers.com/en_IN/search?q=gold+earrings",
                  "Mangalsutra": "https://www.ckcjewellers.com/en_IN/search?q=gold+mangalsutra"}},
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
            # Shopify's own sitemap index lists sitemap_pages_N.xml,
            # sitemap_collections_N.xml and sitemap_blogs_N.xml alongside
            # sitemap_products_N.xml, all matching "sitemap" in path -
            # recursing into those too used to add category/collection/blog
            # URLs straight into the flat product-URL list. Harmless on a
            # large catalogue (a handful of stray URLs get lost in
            # thousands), but on Ranka Jewellers' much smaller catalogue it
            # let collection pages like /collections/bangles-bracelets
            # (categorize()'s keyword match doesn't know the difference)
            # swamp the real product URLs almost entirely - verified live:
            # every "Bangle"/"Ring"/etc. candidate discovered was a
            # collection or guide page, zero were real products.
            non_product = any(x in path for x in
                               ("page", "collection", "blog", "author", "news"))
            if path.endswith(".xml") and not non_product and (
                    "product" in path or "sitemap" in path):
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

    # A sitemap can be one flat file mixing every URL type (ORRA: category
    # pages like /rings and /offers/... sit right alongside real products
    # like /product/<slug>-<sku>, and categorize()'s keyword match can't
    # tell them apart - "rings" matches the CAT_RULES keyword same as a
    # real product slug does). require_path lets a brand declare the one
    # substring its real product URLs actually have, so junk listing/offer
    # pages that happen to match a category keyword don't get treated as
    # products - on ORRA this was severe enough (~93% of "Ring" candidates
    # were non-product pages) that the probe phase's first 25 fetches could
    # land on nothing but junk and the whole brand got skipped as "no
    # making % found", even though real products were sitting in the same
    # sitemap the whole time.
    require_path = d.get("require_path")
    for u in discover_urls(sess, d.get("sitemaps") or []):
        if require_path and require_path not in u:
            continue
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
    #   "p"          (Magento search results, e.g. Candere): &p=2,3,4,...
    #                (verified live: Candere's ?q=ring&p=2 surfaces a
    #                different ~40 products than page 1, not a repeat of it -
    #                the old default ("baseOffset", a no-op param on this
    #                platform) silently capped this brand at page 1 forever)
    #   "start_sz"   (Salesforce Commerce Cloud search, e.g. C Krishniah
    #                Chetty): &start=0,21,42,...&sz=21 - verified live,
    #                21 genuinely new products per page, no repeats.
    pag_style = d.get("pagination", "baseOffset")
    # A brand whose pagination param is a confirmed no-op (BlueStone: ?p=2
    # returns byte-different but product-identical HTML - a cached first-page
    # snapshot, not a real next page) declares max_pages=1 so the loop below
    # doesn't burn 24 more requests per listing URL proving that every time.
    max_pages = d.get("max_pages", 25)
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
            # Some listing URLs already carry a query string (Candere's
            # ?q=ring) - a page param has to join with "&", not a second
            # "?", or the whole query string after the first "?" is invalid.
            sep = "&" if "?" in base_listing else "?"
            # Cap raised from 6 to 25 pages / PER_CAT to PER_CAT_LARGE so a
            # listing-only brand with a genuinely deep catalogue (no sitemap
            # route) isn't stopped short of a large sample - the "page
            # yielded nothing new" break below already ends the loop early
            # for brands whose real catalogue is much smaller than that.
            while page_num <= max_pages and len(buckets.get(cat, [])) < PER_CAT_LARGE:
                if page_num == 1:
                    url = base_listing
                elif pag_style == "page":
                    url = f"{base_listing}{sep}page={page_num}"
                elif pag_style == "p":
                    url = f"{base_listing}{sep}p={page_num}"
                elif pag_style == "start_sz":
                    url = f"{base_listing}{sep}start={(page_num - 1) * 21}&sz=21"
                else:
                    url = f"{base_listing}{sep}baseOffset={(page_num - 1) * 20}"
                html, _ = fetch(sess, url, allow_proxy=True, timeout=25)
                if not html:
                    break
                raw_matches = 0
                for m in re.finditer(prod_re, html) if prod_re else []:
                    raw_matches += 1
                    cand = m.group(0) if not m.groups() else m.group(1)
                    if not cand.startswith("http"):
                        cand = urljoin(base_listing, cand)
                    if categorize(cand) == cat:
                        add(cat, cand)
                # Stop only when the page truly has no product links left -
                # NOT when none of this page's links happened to survive
                # categorize()/the studded filter for THIS category. A page
                # that's mostly diamond pieces for this query can legitimately
                # add zero new items while a later page still has plenty;
                # stopping on that used to cut pagination short right when
                # the studded filter (added for plain-gold-only sampling)
                # had a bad page, silently capping brands like Candere well
                # under their real catalogue size.
                if raw_matches == 0 and page_num > 1:
                    break
                page_num += 1
                time.sleep(0.3)
    return buckets


def fetch_batch(sess, engine, brand, items, workers=None):
    """Fetch + extract a batch of (cat, url) candidates concurrently.

    Replaces the old one-at-a-time loop (with a 0.3s sleep after every direct
    fetch) - fine when a brand only needed 20 fetches, but a serial killer
    once samples run into the hundreds. Network I/O dominates a fetch, so a
    bounded thread pool (workers, default FETCH_WORKERS) turns wall-clock
    time into roughly fetches/workers instead of fetches - and IS the
    politeness control now, in place of the per-request sleep (a fixed
    number of concurrent connections to one brand's domain, not an
    unbounded burst). A brand whose origin can't sustain the default (see
    DISCOVER's per-brand "fetch_workers" override) passes a lower value here.

    A first pass at `workers`, then up to FETCH_RETRIES more passes (at half
    the concurrency, after a short backoff) retrying only the fetches that
    came back empty. A smaller origin can start timing out once several
    hundred fetches for one brand are in flight - without a retry, that
    silently reads as "no making % on these pages" instead of what it is, a
    transient failure under load - so a URL only counts as a real miss once
    retries at gentler concurrency have also failed on it.

    Returns a list of (cat, url, ExtractionResult|None, src).
    """
    workers = workers or FETCH_WORKERS
    fetched = [None] * len(items)   # (html, src) per item, filled in below

    def run_pass(indices, n_workers):
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            futs = {ex.submit(fetch, sess, items[i][1], True, 25): i for i in indices}
            for fut in as_completed(futs):
                fetched[futs[fut]] = fut.result()

    run_pass(range(len(items)), workers)
    for _ in range(FETCH_RETRIES):
        failed = [i for i, r in enumerate(fetched) if not r[0]]
        if not failed:
            break
        time.sleep(RETRY_BACKOFF)
        run_pass(failed, max(2, workers // 2))

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
        # Interleave categories round-robin instead of one full category
        # block at a time, so a brand's largest category doesn't consume
        # the whole probe (and a disproportionate share of the run) before
        # the others get a look-in. If a brand's origin ever degrades
        # partway through a run (rate limiting, a slow spell), every
        # category has already gotten a proportional slice by then, instead
        # of whichever categories happen to be enumerated last getting
        # nothing at all.
        per_cat = []
        for cat, us in buckets.items():
            target = sample_size(len(us))
            per_cat.append([(cat, u) for u in us[:target]])
        candidates = [item for row in zip_longest(*per_cat) for item in row
                      if item is not None]
        candidates = candidates[:TOTAL_CAP]

        # Probe phase first, fetched concurrently: bail on the whole brand
        # only if that first batch lands zero hits - the engine has already
        # tried every strategy on those pages. Threshold is 25, not 10: with
        # the plain-gold-only stone gate, a brand whose catalogue leans
        # studded can legitimately go several fetches between hits (a real,
        # working brand), not just a broken one.
        probe, rest = candidates[:25], candidates[25:]
        brand_workers = d.get("fetch_workers")
        results = fetch_batch(sess, engine, brand, probe, workers=brand_workers)
        hits, proxy_hits = record_results(agg, detail, brand, results)
        fetched = len(results)

        if fetched >= 25 and hits == 0:
            print(f"  {brand}: no making % in first 25 items, skipping")
        elif rest:
            results = fetch_batch(sess, engine, brand, rest, workers=brand_workers)
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
