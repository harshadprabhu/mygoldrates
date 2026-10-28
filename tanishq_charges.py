#!/usr/bin/env python3
"""Tanishq's making charges and making-charge offers (part of collect_charges).

Tanishq answers a plain request with "Access Blocked", so every page goes
through the proxy waterfall the daily rate collector already uses
(collect_charges.fetch). Its product list comes from its own sitemaps; for
each product its own product data (the same response its page asks for when
a visitor opens "Price Breakup") carries a priceInfo block:
  GDV  gold value      F2   making charge (before any offer)
  AF1  stones          UTP  the total with 3% GST   (MGR is the gold rate per gram)
plus the karat, stone and diamond weight, and the offer the page shows
("15% off on making charges", "Rs 301 off per gram"). Only plain 22K gold
counts: making % = MGR / GDV x 100, as for every other jeweller.

    python tanishq_charges.py      # a small sample, printed (changes nothing)
"""
import html as htmllib
import random
import re
from concurrent.futures import ThreadPoolExecutor

from collect_charges import _STUDDED_RE, categorize, fetch

BRAND = "Tanishq"
BASE = "https://www.tanishq.co.in"
SITEMAPS = [BASE + "/sitemap_%d.xml" % i for i in range(3)]
VARIATION = BASE + "/on/demandware.store/Sites-Tanishq-Site/en_IN/Product-Variation?pid={pid}&quantity=1"
PROD_RE = re.compile(r"/product/[^?#<]*-([0-9a-z]{10,})\.html", re.I)
# karats other than 22 and coloured gold, named in the product's own address
_OTHER_KT = re.compile(r"\b(9|14|18|24) ?(kt|k|karat|carat)\b|\brose gold\b|\bwhite gold\b|\bplatinum\b", re.I)
PER_CAT = 15          # plain 22K pieces read per category
TRIES_PER_CAT = 30    # product data requests per category at most (each one costs a proxy credit)
WORKERS = 3


def _num(txt, key):
    m = re.search(r'"%s"\s*:\s*"?(-?[\d.]+)' % key, txt)
    return float(m.group(1)) if m else None


def _str(txt, key):
    m = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, txt)
    return m.group(1) if m else ""


def why_not(txt):
    """What a product's data says, for the log when parse() says no."""
    t = htmllib.unescape(txt or "")
    return {k: (_str(t, k) or _num(t, k)) for k in ("productType", "karatage", "metal", "pricingGroupType",
                                                   "stoneWeight", "diamondWeight", "GDV", "F2", "AF1", "UTP")} | {"bytes": len(t)}


def variant_url(txt):
    """A master product's first variant (a size/weight), which carries the price."""
    m = re.search(r'(?:https://www\.tanishq\.co\.in)?/on/demandware\.store/Sites-Tanishq-Site/en_IN/Product-Variation\?dwvar_[^"\'\s\\]+',
                  htmllib.unescape(txt or ""))
    if not m:
        return None
    u = m.group(0).replace("&amp;", "&")
    return u if u.startswith("http") else BASE + u


def parse(txt):
    """One product's data -> {pct, karat, gold, making, offer} or None when
    it is not plain 22K gold or the breakup is missing."""
    t = htmllib.unescape(txt or "")
    gold, making, total = _num(t, "GDV"), _num(t, "F2"), _num(t, "UTP")
    karat, metal = _str(t, "karatage"), _str(t, "metal")
    stone, diamond = _num(t, "stoneWeight") or 0, _num(t, "diamondWeight") or 0
    group = _str(t, "pricingGroupType").upper()
    if not gold or making is None or karat != "22" or metal.lower() != "gold":
        return None
    if stone or diamond or "STUDDED" in group:
        return None
    # the parts must add up to Tanishq's own total (gold + making + stones + GST)
    parts = gold + making + (_num(t, "AF1") or 0) + (_num(t, "WTV") or 0)
    if not total or abs(parts * 1.03 - total) > total * 0.02:
        return None
    pct = round(making / gold * 100, 2)
    if not 2 <= pct <= 60:
        return None
    # the offer the page shows: dtt names it, dtp is its % ("15% off on
    # making charges"), vpg a rupee amount off per gram
    text = _str(t, "dttText")
    dtp, vpg = _num(t, "dtp"), _num(t, "vpg")
    offer = None
    if dtp and "making" in text.lower():
        offer = {"pct": dtp}
    elif vpg:
        offer = {"per_gram": vpg}
    return {"pct": pct, "gold": gold, "making": making, "offer": offer}


def product_urls(sess):
    """{category: [product url, ...]} from the sitemaps, plain-gold-looking only."""
    urls = set()
    for sm in SITEMAPS:
        for _ in range(3):                     # big files: a proxy sometimes gives up
            x, how = fetch(sess, sm, min_len=100, proxy_timeout=150)
            if x:
                break
        found = {u.split("?")[0] for u in re.findall(r"<loc>([^<]+)</loc>", x or "")}
        print(f"  {BRAND}: {sm.rsplit('/', 1)[1]} {how}, {len(found)} products")
        urls |= found
    cats = {}
    for u in sorted(urls):
        name = u.replace("-", " ")
        if "/product/" not in u or _STUDDED_RE.search(name) or _OTHER_KT.search(name):
            continue
        pid = PROD_RE.search(u)
        if not pid or pid.group(1).startswith("55"):    # 55...: Mia, Tanishq's 14K line
            continue
        c = categorize(u)
        if c:
            cats.setdefault(c, []).append(u)
    return cats


def _says_22(u):
    return bool(re.search(r"\b22 ?(kt|k|karat|carat)\b", u.replace("-", " "), re.I))


def _read(sess, url):
    m = PROD_RE.search(url)
    if not m:
        return url, None, "no pid"
    txt, how = fetch(sess, VARIATION.format(pid=m.group(1)), min_len=200)
    r = parse(txt) if txt else None
    if txt and not r and '"productType": "master"' in txt and '"karatage": "22"' in txt:
        v = variant_url(txt)                   # sizes carry the price, the master does not
        if v:
            txt, how = fetch(sess, v, min_len=200)
            r = parse(txt) if txt else None
    return url, r, how


def collect(sess, per_cat=PER_CAT, tries=TRIES_PER_CAT, seed=None):
    """-> (results, offers): results [(category, url, pct)], offers
    {category: {"seen": n, "pct": [..], "per_gram": [..]}} over the plain
    22K pieces read."""
    rnd = random.Random(seed)
    results, offers = [], {}
    for cat, urls in product_urls(sess).items():
        rnd.shuffle(urls)
        urls.sort(key=lambda u: not _says_22(u))        # "22kt" in the name first
        got, i = [], 0
        with ThreadPoolExecutor(WORKERS) as ex:
            while len(got) < per_cat and i < min(tries, len(urls)):
                batch = urls[i:min(i + WORKERS * 2, tries, len(urls))]
                i += len(batch)
                for u, r, how in ex.map(lambda u: _read(sess, u), batch):
                    if r:
                        got.append((u, r))
        o = offers.setdefault(cat, {"seen": 0, "pct": [], "per_gram": []})
        for u, r in got[:per_cat]:
            results.append((cat, u, r["pct"]))
            o["seen"] += 1
            if r["offer"] and "pct" in r["offer"]:
                o["pct"].append(r["offer"]["pct"])
            elif r["offer"]:
                o["per_gram"].append(r["offer"]["per_gram"])
        print(f"  {BRAND} {cat}: {len(urls)} candidates, {i} read, {len(got[:per_cat])} plain 22K")
    return results, offers


def offer_summary(offers):
    """The making-charge offer across what was read: the most common % off,
    and on what share of pieces (1.0 = every piece read had it)."""
    pcts = [p for o in offers.values() for p in o["pct"]]
    seen = sum(o["seen"] for o in offers.values())
    if not pcts or not seen:
        return None
    common = max(set(pcts), key=pcts.count)
    return {"making_pct_off": common, "max_pct_off": max(pcts),
            "share": round(len(pcts) / seen, 2)}


if __name__ == "__main__":
    import requests
    from collect_charges import UA
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    res, off = collect(s, per_cat=3, tries=6, seed=1)
    for r in res:
        print(r)
    print(offer_summary(off), off)
