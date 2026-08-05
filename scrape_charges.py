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
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import base64

import requests

from mc_engine import Engine

# Learned per-brand extraction profiles (auto-maintained by mc_engine).
PROFILE_PATH = "mc_profiles.json"

IST = timezone(timedelta(hours=5, minutes=30))
ZYTE_KEY = os.environ.get("ZYTE_API_KEY", "").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PER_CAT = 20           # products sampled per category per brand
TOTAL_CAP = 280        # hard cap on product fetches per brand

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
_CL_PROD = r'/jewellery/([a-z0-9][a-z0-9-]{4,}?-[a-z]{1,3}\d{4,}-[0-9a-z]{4,})\.html'
_BS_PROD = r'href="(https://www\.bluestone\.com/[^"]+?~\d+\.html)"'

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
    {"brand": "BlueStone", "product_re": _BS_PROD,
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
    {"brand": "Kisna",
     "sitemaps": ["https://www.kisna.com/sitemap.xml"]},
    {"brand": "ORRA",
     "sitemaps": ["https://www.orra.co.in/sitemap.xml"]},
    {"brand": "PN Gadgil",
     "sitemaps": ["https://www.pngjewellers.com/sitemap.xml"]},
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


def fetch(sess, url, allow_proxy=True, timeout=25):
    """Direct first (free), proxy waterfall only if direct fails.

    Honors the 'avoid proxy where possible' rule. Sitemap fetches pass
    allow_proxy=False - they're always static XML that direct handles.
    Returns (html, source) or (None, err).
    """
    try:
        r = sess.get(url, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 500:
            return r.text, "direct"
        direct_err = f"direct/{r.status_code}"
    except Exception as e:
        direct_err = f"direct/{type(e).__name__}"

    if not allow_proxy:
        return None, direct_err

    for name, u, p in _proxy_attempts(url):
        try:
            r = sess.get(u, params=p, timeout=60)
            if r.status_code == 200 and len(r.text) > 500:
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


def categorize(url):
    """Map a product URL to a v1 category, or None to skip it.

    NOTE: this deliberately does NOT require the word "gold" in the URL. Doing
    so silently discarded every BlueStone product (their URLs look like
    /bangles/the-orrale-round-bangle~79884.html), which is why that brand
    yielded zero items. Non-gold items are excluded explicitly instead, and
    anything that slips through is caught later: the engine only returns a
    making % when it finds a gold/metal value in the breakup.
    """
    s = url.lower()
    if _NON_GOLD_RE.search(s):
        return None
    for kw, cat in CAT_RULES:
        if kw in s:
            return cat
    return None


def discover_urls(sess, sitemaps):
    """Walk sitemap(s). Sitemaps are static XML - direct fetch only, no proxy."""
    urls, seen = [], set()
    queue = list(sitemaps)
    while queue and len(seen) < 12:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        t, src = fetch(sess, sm, allow_proxy=False)
        if not t:
            print("  sitemap fail:", sm, src)
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", t)
        for loc in locs:
            if loc.endswith(".xml") and ("product" in loc.lower()
                                          or "sitemap" in loc.lower()):
                queue.append(loc)          # nested sitemap
            else:
                urls.append(loc)
    return urls


def collect_urls(sess, d):
    """Gather candidate product URLs for a brand from every route it declares.

    Three routes, unioned (a brand may use any combination):
      sitemaps - walk XML sitemap(s)
      listings - {category: listing_url}, with ?baseOffset pagination when a
                 category comes up short (verified on CaratLane)
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
            add(cat, u)

    for u in discover_urls(sess, d.get("sitemaps") or []):
        c = categorize(u)
        if c:
            add(c, u)

    prod_re = d.get("product_re")
    for cat, listing in (d.get("listings") or {}).items():
        offset, page = 0, 0
        while page < 5 and len(buckets.get(cat, [])) < PER_CAT:
            url = listing if offset == 0 else f"{listing}?baseOffset={offset}"
            html, _ = fetch(sess, url, allow_proxy=True, timeout=25)
            if not html:
                break
            before = len(buckets.get(cat, []))
            for m in re.finditer(prod_re, html) if prod_re else []:
                cand = m.group(0) if not m.groups() else m.group(1)
                if not cand.startswith("http"):
                    cand = urljoin(listing, cand)
                if categorize(cand) == cat:
                    add(cat, cand)
            if len(buckets.get(cat, [])) == before:
                break                  # page yielded nothing new
            offset += 20
            page += 1
            time.sleep(0.3)
    return buckets


def main():
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    engine = Engine.load(PROFILE_PATH)
    agg = {}          # (brand, cat) -> [pct,...]
    detail = {}       # (brand, cat) -> [{url, pct, conf, fields}, ...]

    for d in DISCOVER:
        brand = d["brand"]
        buckets = collect_urls(sess, d)
        fetched = hits = proxy_hits = 0
        for cat, us in buckets.items():
            for u in us[:PER_CAT]:
                if fetched >= TOTAL_CAP:
                    break
                fetched += 1
                html, src = fetch(sess, u, allow_proxy=True, timeout=25)
                if src and src not in ("direct", "all-proxies-failed"):
                    proxy_hits += 1
                res = engine.extract(html, brand=brand) if html else None
                if res and res.ok:
                    hits += 1
                    agg.setdefault((brand, cat), []).append(res.making_pct)
                    detail.setdefault((brand, cat), []).append({
                        "url": u, "pct": res.making_pct,
                        "confidence": res.confidence,
                        "strategy": res.strategy, "fields": res.fields})
                # Bail early only when nothing at all is landing - the engine
                # has already tried every strategy on those 10 pages.
                if fetched >= 10 and hits == 0:
                    print(f"  {brand}: no making % in first 10 items, skipping")
                    break
                if src == "direct":
                    time.sleep(0.3)     # be polite to origins we hit direct
            if fetched >= 10 and hits == 0:
                break
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
