#!/usr/bin/env python3
"""Making charges worked out from the price (part of collect_charges).

Some jewellers publish each product's price, gold weight and karat but no
price breakup. Then, for plain gold (no stones):

    making % = (price before GST - net gold weight x the jeweller's own 22K rate)
               / (net gold weight x that rate) x 100

using the 22K rate the jeweller itself states that day. Pieces with any stone,
diamond or other karat are skipped, as are results outside 2-60%. Categories
recorded this way carry source "price", and the site labels them "worked out
from the price".

Jewellers read here (READERS; source "price" marks the worked-out ones):
  Indriya  sitemaps -> each product's own data (product.pdp.json): price
           before tax, gold weight, karat, stones; the 22K rate is printed
           on every product page ("Rs.13195 per gm (22kt)").
  Thangamayil  not worked out: its product pages print the breakup itself
           ("22KT GOLD Rs x + MC Rs y + HMC + GST"), so MC / gold is measured
           like any other breakup (source unset).

    python price_making.py      # a small sample, printed (changes nothing)
"""
import random
import re
from concurrent.futures import ThreadPoolExecutor

from collect_charges import categorize, fetch

PER_CAT = 25          # plain 22K pieces per category
TRIES_PER_CAT = 70    # product reads per category at most
WORKERS = 3


def making_pct(price_ex_gst, gold_g, rate22):
    """The making charge as % of the gold value, or None if implausible."""
    if not (price_ex_gst and gold_g and rate22):
        return None
    gold = gold_g * rate22
    pct = round((price_ex_gst - gold) / gold * 100, 2)
    return pct if 2 <= pct <= 60 else None


def _num(s):
    s = re.sub(r"[^\d.]", "", str(s or ""))
    try:
        return float(s)
    except ValueError:
        return None


class Indriya:
    brand = "Indriya"
    source = "price"
    base = "https://www.indriya.com"
    sitemaps = ["https://www.indriya.com/skusitemap-%d.xml" % i for i in (1, 2, 3)]
    data = "https://www.indriya.com" + ("/content/noveljewels/in/en/jewellery-products/jcr:content/root/container/"
                   "container/container_1787415936/product.pdp.json/")

    def products(self, sess):
        urls = []
        for sm in self.sitemaps:
            try:
                urls += re.findall(r"<loc>([^<]+/jewellery-products/[^<]+)</loc>", sess.get(sm, timeout=60).text)
            except Exception:
                pass
        return urls

    def rate22(self, sess, urls):
        for u in urls[:3]:
            try:
                m = re.search(r"Rs\.?\s*([\d,]+(?:\.\d+)?)\s*per\s*gm\s*\(22\s*kt\)", sess.get(u, timeout=40).text, re.I)
                if m:
                    return _num(m.group(1))
            except Exception:
                pass
        return None

    def read(self, sess, url, rate):
        """-> making % for a plain 22K piece, else None."""
        try:
            d = sess.get(self.data + url.rstrip("/").rsplit("/", 1)[1], timeout=30).json()
        except Exception:
            return None
        return self.parse(d, rate)

    @staticmethod
    def parse(d, rate):
        spec = {e.get("key", "").strip(): e.get("value") for a in d.get("productAccordions", [])
                for e in a.get("tableValue", [])}
        if spec.get("Purity (Karatage)") != "22K":
            return None
        if any(k for k in spec if re.search(r"gemstone|diamond|stone|pearl", k, re.I)):
            return None
        if (d.get("masterAttrMap") or {}).get("master_group", "Gold") != "Gold":
            return None
        return making_pct(_num(d.get("formattedPrice")), _num(spec.get("Gold Weight")), rate)


class Thangamayil:
    brand = "Thangamayil"
    source = None                       # its own breakup, not worked out
    sitemaps = ["https://www.thangamayil.com/sitemap.xml"]

    # refuses GitHub's servers: direct first, then the proxies
    # (collect_charges.PROXY_HOSTS), so fewer pieces per run to spare credits
    per_cat, tries = 12, 25

    def products(self, sess):
        for _ in range(3):
            x, _how = fetch(sess, self.sitemaps[0], min_len=100, proxy_timeout=120)
            if x:
                return re.findall(r"<loc>([^<]+\.html)</loc>", x)
        return []

    def rate22(self, sess, urls):
        return 1.0                      # not needed: the page has the gold value

    def read(self, sess, url, rate):
        html, _how = fetch(sess, url)
        return self.parse(html) if html else None

    @staticmethod
    def parse(page):
        import html as htmllib
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", htmllib.unescape(page or "")))
        i = t.find("Price Breakup")
        if i < 0 or not re.search(r"Metal Purity \|?\s*\|?\s*22K", t):
            return None
        bd = t[i:i + 600]
        bd = bd[:bd.find("GST")] if "GST" in bd else bd
        if re.search(r"stone|diamond|pearl|polki|kundan|platinum|silver", bd, re.I):
            return None
        g = re.search(r"22KT GOLD[ |]*₹\s*([\d,]+(?:\.\d+)?)", bd)
        mc = re.search(r"\bMC[ |]*₹\s*([\d,]+(?:\.\d+)?)", bd)
        if not (g and mc):
            return None
        gold, making = _num(g.group(1)), _num(mc.group(1))
        pct = round(making / gold * 100, 2) if gold else None
        return pct if pct and 2 <= pct <= 60 else None


READERS = [Indriya(), Thangamayil()]


def collect(sess, per_cat=PER_CAT, tries=TRIES_PER_CAT, seed=None):
    """-> [(brand, category, url, pct, source)] for every reader."""
    out, rnd = [], random.Random(seed)
    for r in READERS:
        urls = r.products(sess)
        rate = r.rate22(sess, urls)
        if not urls or not rate:
            print(f"  {r.brand}: {len(urls)} products, 22K rate {rate} - skipped")
            continue
        cats = {}
        for u in urls:
            c = categorize(u)
            if c:
                cats.setdefault(c, []).append(u)
        print(f"  {r.brand}: {len(urls)} products, 22K rate {rate}, {({c: len(v) for c, v in cats.items()})}")
        with ThreadPoolExecutor(WORKERS) as ex:
            for cat, us in cats.items():
                pc, tr = min(per_cat, getattr(r, "per_cat", per_cat)), min(tries, getattr(r, "tries", tries))
                rnd.shuffle(us)
                pcts = [(u, p) for u, p in zip(us[:tr], ex.map(lambda u: r.read(sess, u, rate), us[:tr])) if p]
                out += [(r.brand, cat, u, p, r.source) for u, p in pcts[:pc]]
                print(f"  {r.brand} {cat}: {len(pcts[:pc])} plain 22K from {min(tr, len(us))} read")
    return out


if __name__ == "__main__":
    import statistics
    import requests
    from collect_charges import UA
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    res = collect(s, per_cat=3, tries=6, seed=1)
    for b, c in sorted({(b, c) for b, c, _, _, _ in res}):
        v = [p for bb, cc, _, p, _ in res if (bb, cc) == (b, c)]
        print(b, c, "median", statistics.median(v), v)
