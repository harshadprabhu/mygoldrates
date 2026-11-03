#!/usr/bin/env python3
"""Making-charge comparison collector (runs ~once every 15 days).

For brands that publish a product price breakup, sample MULTIPLE products per
category and record the making charge as % of gold value, then aggregate to a
median per (brand, category). Discovery brands are enumerated from their
product sitemap; others use a curated URL. Best-effort - items without a clean
% are skipped. Writes private/making-charges.json and saves the run to
Supabase (private_store.py) - not to git, which is public.
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
# Coin to v2. Order matters (earring must come before ring). 24K gold coins
# (owner, 3 Nov 2026) are recognised in categorize() itself, not here.
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

_MAL = "https://www.malabargoldanddiamonds.com/in/pan-india/en/product-list.html?malabar_product_type="

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
     "coin_re": r'(https://www\.caratlane\.com/gold-coins/[a-z0-9-]+\.html)',
     "listings": {"Coin": "https://www.caratlane.com/gold-coins.html",
                  "Bangle": _CL + "bangles.html",
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
     "coin_re": r'((?:https://www\.bluestone\.com)?/gold\+coins/[a-z0-9-]+~\d+\.html)',
     "listings": {
        "Coin": ["https://www.bluestone.com/jewellery/coins.html",
                 "https://www.bluestone.com/search?search_query=gold+coin"],
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
     "listings": {"Coin": "https://www.candere.com/catalogsearch/result/?q=gold+coin",
                  "Bangle": "https://www.candere.com/catalogsearch/result/?q=bangle",
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
     "coin_re": r'href="(/gold-silver-coins-bars/[a-z0-9-]+\.html)"',
     "listings": {"Coin": "https://www.grtjewels.com/catalogsearch/result/?q=gold+coin",
                  "Ring": ["https://www.grtjewels.com/jewellery/gold-jewellery/gold-rings.html",
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

    # Khazana Jewellery: the product page carries a real price-breakup table
    # (gold value, making charges, subtotal; read by mc_engine's
    # div_row_breakup). Product pages are ~1 MB each, so a few workers only.
    # Reliance Jewels: the breakup comes from the site's own per-item service
    # (see FOLLOW / _reliance_breakup), read by mc_engine's sku_breakup_json.
    # Showroom-only designs ("Approx. Price") have no breakup and are skipped.
    # Most bangles and mangalsutras are showroom-only, so every one is opened
    # to find the few sold online.
    {"brand": "Reliance Jewels", "fetch_workers": 3, "sample_all": ["Bangle", "Mangalsutra"],
     "total_cap": 1100, "sitemaps": ["https://www.reliancejewels.com/sitemap.xml"]},

    # Jos Alukkas: the product page's own data carries a ProductPrice object
    # (GoldValue, MakingCharges, stone values) - mc_engine's
    # product_price_keys. The making charge is read before any offer.
    {"brand": "Jos Alukkas", "fetch_workers": 3, "require_path": "/gold-jewellery/",
     "sitemaps": ["https://www.josalukkasonline.com/sitemap.xml"]},

    # NAC Jewellers: page data has metalCost and makingChargeAmount (also
    # called wastage). A small online catalogue, so samples are small.
    {"brand": "NAC Jewellers", "fetch_workers": 2, "require_path": "/product/",
     "sitemaps": ["https://www.nacjewellers.com/sitemap.xml"]},

    # Malabar Gold: the price breakup is worked out in the visitor's browser
    # (gold value, making charge before and after any offer), so it is read
    # by opening each product in a browser - collect_rendered and mc_engine's
    # rendered_breakup_text. Category ids from the site's own filters.
    # Mangalsutra is listed as "tanmaniya" (type 81, product codes TM-) - the
    # Maharashtrian name; the site has no separate mangalsutra type. About
    # half the rings carry stones and are excluded, so open 45 a category.
    {"brand": "Malabar Gold", "render_per_cat": 45,
     "product_re": r"/product\.html\?sku=",
     "render": {"Ring": _MAL + "102", "Earrings": _MAL + "99", "Bangle": _MAL + "87",
                "Mangalsutra": _MAL + "81"}},

    {"brand": "Khazana Jewellery", "fetch_workers": 3,
     "sitemaps": ["https://www.khazanajewellery.com/sitemap_index.xml"]},
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


# The free-tier proxies (ScraperAPI, ScrapingBee, ZenRows, Crawlbase) are
# spent only on sites that answer nothing else; a slow page anywhere else
# must not use up the month's credits.
PROXY_HOSTS = {"www.tanishq.co.in", "www.thangamayil.com"}   # both refuse GitHub's servers


def fetch(sess, url, allow_proxy=True, timeout=25, min_len=500, proxy_timeout=60):
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

    for name, u, p in (_proxy_attempts(url) if urlsplit(url).netloc in PROXY_HOSTS else ()):
        try:
            r = sess.get(u, params=p, timeout=proxy_timeout)
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
# A coin's address must name 24K: "24kt", "24-karat", "24 k", "999", "995".
_COIN_24K_RE = re.compile(r"(?<!\d)24[\s_-]*(?:k|kt|ct|carat|karat)\b|(?<!\d)99[59](?!\d)", re.I)
# A coin's making charge is a few percent; far above that the page was not a
# plain 24K coin (a pendant, a gift set, a misread) and is left out.
COIN_MAX_PCT = 20.0
_SUB_GRAM_RE = re.compile(r"milligram|\d\s*mg\b|(?<![\d.])0[-.]\d+[-\s]*(?:g|gm|gms|gram|grams)\b", re.I)
# COIN_ONLY=1: read just the coins and keep everything else as it was (the
# workflow's probe=coins), so coins can be refreshed without a full run.
COIN_ONLY = os.environ.get("COIN_ONLY") == "1"

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
    # 24K gold coins only, never 22K or silver; a coin ring/pendant/chain is
    # jewellery and falls through to the rules below
    if "coin" in s and not re.search(r"ring|pendant|chain|necklace|bangle|bracelet|mangalsutra|anklet", s):
        if _SUB_GRAM_RE.search(s):      # 50 mg-0.5 g coins: making % not comparable
            return None
        return "Coin" if _COIN_24K_RE.search(s) else None
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
        c = categorize(u)
        # require_path picks a brand's jewellery pages; its coins can live
        # elsewhere (Jos Alukkas: /gold-coin/...), so coins are not held to it
        if require_path and require_path not in u and c != "Coin":
            continue
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
                pat = d.get("coin_re", prod_re) if cat == "Coin" else prod_re
                if cat == "Coin":                       # links inside page JSON
                    html = html.replace("\\u002F", "/")
                for m in re.finditer(pat, html) if pat else []:
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


def _reliance_breakup(sess, url, html):
    """Reliance Jewels shows a product's price breakup only once a size is
    picked: the page then asks its own /product/ajax/skuBreakupDetails for
    it. Ask the same, for the page's first item (showroom-only designs have
    none, and return nothing to read)."""
    pid = re.search(r"-(\d+)/?(?:[?#]|$)", url)
    item = re.search(r'data-item-id\s*=\s*"(\d+)"', html or "")
    if not (pid and item):
        return ""
    api = (f"https://www.reliancejewels.com/product/ajax/skuBreakupDetails"
           f"?productId={pid.group(1)}&itemId={item.group(1)}")
    try:
        r = sess.get(api, timeout=20, headers={"Accept": "application/json", "Referer": url})
        return r.text if r.ok else ""
    except requests.RequestException:
        return ""


# Brands whose product page loads its breakup separately: fetch that too and
# hand both to the engine.
FOLLOW = {"Reliance Jewels": _reliance_breakup}


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
    follow = FOLLOW.get(brand)
    for i, (cat, u) in enumerate(items):
        html, src = fetched[i]
        if html and follow:
            extra = follow(sess, u, html)
            html = html + "\n<!--breakup-->" + extra if extra else html
        res = engine.extract(html, brand=brand) if html else None
        if cat == "Coin" and html and not (res and res.ok):
            res = coin_from_price(html, u, OWN24.get(brand)) or res   # no breakup: from the price
        if cat == "Coin" and res is not None and html:
            pu = page_purity(html, u)               # the coin's own stated fineness
            if pu:
                res.fields["purity"] = pu
        out.append((cat, u, res, src))
    return out


# A coin page's stated fineness: "24KT (995)", "995 Kt Yellow Gold" (CaratLane's
# breakup), "24kt-999", "99.99%". Owner, 3 Nov 2026: checked on the pages -
# PN Gadgil and CaratLane 995; WHP, Candere, Khazana, NAC 999; Senco mixed.
_PUR_RE = re.compile(r"(?<![\d.])(999\.9|9999|99\.99|999|99\.9|995|99\.5)(?![\d])\s*(?:%|k\b|kt\b|\)|\s*purity|\s*fine)?", re.I)
_PUR_CTX = re.compile(r"(?:24\s*k[t]?|carat|karat|purity|fineness|pure|gold)[^<>{}]{0,40}$", re.I)


def page_purity(html, url=""):
    """'995', '999' or '999.9' from the coin page (title, specs, breakup), else
    from its address; None when the page states none."""
    import collections
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S)
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    # the breakup data inside scripts too (CaratLane: "title":"995 Kt Yellow Gold")
    t += " " + " ".join(re.findall(r'"title"\s*:\s*"(9{2}[59](?:\.9)? ?k[t]?[^"]{0,30})"', html or "", re.I))
    c = collections.Counter()
    for m in _PUR_RE.finditer(t):
        tail = (m.group(0) or "").lower()
        ctx = t[max(0, m.start() - 45):m.start()]
        if not (_PUR_CTX.search(ctx) or re.search(r"%|k|\)|purity|fine", tail[len(m.group(1)):])):
            continue                              # a bare number elsewhere on the page
        v = m.group(1)
        c["999.9" if v in ("999.9", "9999", "99.99") else "995" if v in ("995", "99.5") else "999"] += 1
    if not c:
        m = re.search(r"(?<!\d)(99[59])(?!\d)", url)
        return m.group(1) if m else None
    return c.most_common(1)[0][0]


OWN24 = {}          # jeweller name -> its own 24K rate today (filled in main())


def coin_from_price(html, url, rate24):
    """A coin page with no readable breakup but a price (Reliance: 'Price :
    14877.0', 1 gram, 24 k(99.5)): the making % worked out from the price,
    which Indian shops quote with GST, and the jeweller's own 24K rate.
    None when the price, weight or rate is missing or the result is not a
    plausible 24K coin (coin_price_making.making_pct)."""
    from mc_engine import ExtractionResult
    from coin_price_making import making_pct, weight_g
    if not rate24:
        return None
    m = (re.search(r'property="og:price:amount"\s+content="([\d.,]+)"', html)
         or re.search(r'itemprop="price"\s+content="([\d.,]+)"', html)
         or re.search(r'"@type"\s*:\s*"Offer"[^}]{0,300}?"price"\s*:\s*"?([\d.,]+)', html))
    price = float(m.group(1).replace(",", "")) if m else None
    t = re.search(r'property="og:title"\s+content="([^"]+)"', html)
    g = weight_g(url.rsplit("/", 2)[-2] if url.endswith("/") else url.rsplit("/", 1)[-1]) \
        or weight_g(t.group(1) if t else "")
    excl = bool(re.search(r"exclusive of (?:all )?tax|\+\s*gst extra|plus gst", html, re.I))
    pct = making_pct(price, g, rate24, incl_gst=not excl)
    if pct is None:
        return None
    return ExtractionResult(strategy="coin_price", making_pct=pct, confidence=0.6,
                            fields={"price": price, "grams": g, "from_price": 1.0})


def coin_gold_factor(items, rate24):
    """How much gold a jeweller bills on its coins per gram of nominal weight,
    against its own 24K rate: gold value / (weight in the coin's name x rate),
    median over its coins. 1.0 = exactly the 24K rate on the nominal weight;
    PN Gadgil's 995 coins at its 24K rate read 1.0; Khazana's '1 gram' coin
    bills 1.028 g (1.028). Readings outside 0.97-1.06 are misreads and left
    out; None without a rate or a usable reading."""
    if not rate24:
        return None
    from coin_price_making import weight_g
    fs = []
    for it in items:
        f0 = it.get("fields") or {}
        if f0.get("from_price"):
            continue                         # worked out from the price: no gold value of its own
        gv = f0.get("gold_value")
        g = weight_g(it.get("url", "").rsplit("/", 1)[-1].replace("+", " "))
        if gv and g:
            f = gv / (g * rate24)
            if 0.97 <= f <= 1.06:
                fs.append(f)
    if not fs:
        return None
    fs.sort()
    m = len(fs) // 2
    return round(fs[m] if len(fs) % 2 else (fs[m - 1] + fs[m]) / 2, 4)


def coin_purity(items):
    """The fineness a jeweller's 24K coins state on their own pages: '995',
    '999', '999.9', or two joined when its coins differ ('995/999.9' - Senco);
    None when none says."""
    import collections
    c = collections.Counter(p for it in items
                            for p in [(it.get("fields") or {}).get("purity")
                                      or (lambda m: m.group(1) if m else None)(re.search(r"(?<!\d)(99[59])(?!\d)", it.get("url", "")))]
                            if p)
    if not c:
        return None
    top = [p for p, n in c.most_common() if n >= max(2, sum(c.values()) * 0.2)] or [c.most_common(1)[0][0]]
    return "/".join(sorted(top)[:2])


def own_rate24():
    """{jeweller name: its own 24K pre-GST rate today} (collect.py keeps the
    published one; else the base rate). Empty without Supabase."""
    try:
        import private_store
        from coin_price_making import todays_rate24
        sb = private_store.client()
        return todays_rate24(sb) if sb else {}
    except Exception as e:
        print(f"coin gold factor: no rates ({type(e).__name__})")
        return {}


def record_results(agg, detail, brand, results):
    """Fold a fetch_batch() result list into agg/detail. Returns (hits, proxy_hits)."""
    hits = proxy_hits = 0
    for cat, u, res, src in results:
        if src and src not in ("direct", "all-proxies-failed"):
            proxy_hits += 1
        if res and res.ok and cat == "Coin" and not (0 <= res.making_pct <= COIN_MAX_PCT):
            continue                     # not a plain 24K coin
        if res and res.ok:
            hits += 1
            agg.setdefault((brand, cat), []).append(res.making_pct)
            detail.setdefault((brand, cat), []).append({
                "url": u, "pct": res.making_pct,
                "confidence": res.confidence,
                "strategy": res.strategy, "fields": res.fields})
    return hits, proxy_hits


def collect_rendered(d, engine):
    """Brands that work out the price breakup in the visitor's browser
    (Malabar): open each category listing like a visitor, collect product
    links (scrolling to load more), then open each product, open its "Price
    Breakup" and read the text it shows. One page at a time, with pauses.
    Returns (cat, url, ExtractionResult|None, "browser") like fetch_batch."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"  {d['brand']}: playwright not installed, skipped")
        return []
    per_cat, out = d.get("render_per_cat", 30), []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1300, "height": 1000})
        for cat, listing in d["render"].items():
            links = []
            try:
                page.goto(listing, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000)
                for _ in range(8):
                    hrefs = page.eval_on_selector_all("a[href]", "as => as.map(a => a.href)")
                    links = list(dict.fromkeys(h for h in hrefs if re.search(d["product_re"], h)))
                    if len(links) >= per_cat:
                        break
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(2500)
            except Exception as e:
                print(f"  {d['brand']} {cat}: listing failed ({type(e).__name__})")
                continue
            links = [u for u in links if not _NON_GOLD_RE.search(u.lower())][:per_cat]
            print(f"  {d['brand']} {cat}: {len(links)} products to open")
            for u in links:
                text = ""
                try:
                    page.goto(u, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(4500)
                    btn = page.get_by_text(re.compile(r"price\s*break", re.I)).first
                    if btn.count():
                        btn.click(timeout=3000)
                        page.wait_for_timeout(1500)
                    text = page.evaluate("() => document.body.innerText")
                except Exception:
                    pass
                res = engine.extract(text, brand=d["brand"]) if text else None
                out.append((cat, u, res, "browser"))
                time.sleep(1.0)
        browser.close()
    return out


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
    OWN24.update(own_rate24())        # for coins whose page shows only a price
    agg = {}          # (brand, cat) -> [pct,...]
    detail = {}       # (brand, cat) -> [{url, pct, conf, fields}, ...]

    for d in DISCOVER:
        brand = d["brand"]
        if d.get("render"):                  # breakup only in the visitor's browser
            results = collect_rendered(d, engine)
            hits, _ = record_results(agg, detail, brand, results)
            print(f"{brand}: opened {len(results)} in a browser, {hits} read, "
                  f"cats {[(c, len(v)) for (b, c), v in agg.items() if b == brand]}")
            continue
        if COIN_ONLY:                   # read only the coin listings, not the jewellery ones
            if d.get("listings") and "Coin" not in d["listings"] and not d.get("sitemaps"):
                print(f"{brand}: no coin listing"); continue
            d = dict(d, listings={k: v for k, v in (d.get("listings") or {}).items() if k == "Coin"})
        buckets = collect_urls(sess, d)
        if COIN_ONLY:
            buckets = {c: u for c, u in buckets.items() if c == "Coin"}
            if not buckets:
                print(f"{brand}: no 24K coin pages found")
                continue
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
            # sample_all: categories where only a few pieces carry a breakup
            # (Reliance: most bangles are showroom-only), so open every one
            target = len(us) if cat in d.get("sample_all", ()) else sample_size(len(us))
            per_cat.append([(cat, u) for u in us[:target]])
        candidates = [item for row in zip_longest(*per_cat) for item in row
                      if item is not None]
        candidates = candidates[:d.get("total_cap", TOTAL_CAP)]

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

    # Tanishq: blocked to plain requests, read through the proxies from its
    # own product data (tanishq_charges.py), with its making-charge offer
    brand_offer = {}
    if os.environ.get("TANISHQ", "1") != "0":
        import tanishq_charges as tq
        try:
            res, off = tq.collect(sess, only=("Coin",) if COIN_ONLY else None)
        except Exception as e:
            res, off = [], {}
            print(f"{tq.BRAND}: failed ({type(e).__name__}: {e})")
        for cat, u, pct in res:
            agg.setdefault((tq.BRAND, cat), []).append(pct)
            detail.setdefault((tq.BRAND, cat), []).append(
                {"url": u, "pct": pct, "confidence": 1.0, "strategy": "tanishq_price_info", "fields": {}})
        if tq.offer_summary(off):
            brand_offer[tq.BRAND] = tq.offer_summary(off)
        print(f"{tq.BRAND}: {len(res)} read, offer {brand_offer.get(tq.BRAND)}")

    # Jewellers with prices and gold weights but no breakup: the making
    # charge worked out from the price (price_making.py), source "price"
    from_price = set()
    if os.environ.get("FROM_PRICE", "1") != "0" and not COIN_ONLY:
        import price_making as pm
        try:
            res = pm.collect(sess)
        except Exception as e:
            res = []
            print(f"from price: failed ({type(e).__name__}: {e})")
        for b, cat, u, pct, src in res:
            agg.setdefault((b, cat), []).append(pct)
            detail.setdefault((b, cat), []).append(
                {"url": u, "pct": pct, "confidence": 1.0, "strategy": src or "breakup", "fields": {}})
            if src == "price":
                from_price.add((b, cat))

    for p in CURATED:
        html, _ = fetch(sess, p["url"], allow_proxy=True, timeout=25)
        res = engine.extract(html, brand=p["brand"]) if html else None
        if res and res.ok:
            agg.setdefault((p["brand"], p["cat"]), []).append(res.making_pct)
            print(f"{p['brand']} {p['cat']}: {res.making_pct}%")

    rate24 = own_rate24()             # each jeweller's own 24K today, for the coin gold factor
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
        if (brand, cat) in from_price:
            row["source"] = "price"
        if cat == "Coin":
            gf = coin_gold_factor(detail.get((brand, cat), []), rate24.get(brand))
            if gf:
                row["gold_factor"] = gf
            pu = coin_purity(detail.get((brand, cat), []))
            if pu:
                row["purity"] = pu
        # a couple of real examples power the dashboard's "based on ..." text
        ex = sorted(detail.get((brand, cat), []),
                    key=lambda x: -x["confidence"])[:3]
        if ex:
            row["examples"] = [{"url": e["url"], "pct": e["pct"]} for e in ex]
        brands.setdefault(brand, []).append(row)

    out = [dict({"brand": b, "categories": sorted(c, key=lambda x: x["category"])},
                **({"offer": brand_offer[b]} if b in brand_offer else {}))
           for b, c in sorted(brands.items())]

    payload = {
        "updated": datetime.now(IST).isoformat(),
        "note": "Making charge as % of gold value, median across multiple real "
                "products per category from each jeweller's public price "
                "breakup. Indicative - varies by specific design.",
        "brands": out,
    }
    import private_store
    if COIN_ONLY:
        # keep every jeweller's jewellery figures; replace only the coin rows
        old = private_store.pull_making() or {}
        coins = {b["brand"]: [c for c in b["categories"] if c["category"] == "Coin"] for b in out}
        merged = []
        for b in old.get("brands") or []:
            new = coins.pop(b["brand"], [])
            # a jeweller not re-read this time keeps its last coin figure
            cats = [c for c in b.get("categories") or [] if c.get("category") != "Coin" or not new]
            cats += new
            merged.append(dict(b, categories=sorted(cats, key=lambda x: x["category"])))
        merged += [{"brand": n, "categories": c} for n, c in coins.items() if c]
        payload = dict(old, brands=sorted(merged, key=lambda x: x["brand"]),
                       coins_updated=datetime.now(IST).isoformat())
        payload.setdefault("note", "Making charge as % of gold value.")
    os.makedirs(private_store.DIR, exist_ok=True)
    with open(private_store.MC, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    private_store.push_making(payload)
    engine.save(PROFILE_PATH)
    tot = sum(len(v) for v in agg.values())
    print(f"charges: {len(out)} brands, {tot} products with a making %")
    print("\n" + engine.report())


if __name__ == "__main__":
    main()
