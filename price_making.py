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

Jewellers read this way (READERS):
  Indriya  sitemaps -> each product's own data (product.pdp.json): price
           before tax, gold weight, karat, stones; the 22K rate is printed
           on every product page ("Rs.13195 per gm (22kt)").

    python price_making.py      # a small sample, printed (changes nothing)
"""
import random
import re
from concurrent.futures import ThreadPoolExecutor

from collect_charges import categorize

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


READERS = [Indriya()]


def collect(sess, per_cat=PER_CAT, tries=TRIES_PER_CAT, seed=None):
    """-> [(brand, category, url, pct)] for every reader."""
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
                rnd.shuffle(us)
                pcts = [(u, p) for u, p in zip(us[:tries], ex.map(lambda u: r.read(sess, u, rate), us[:tries])) if p]
                out += [(r.brand, cat, u, p) for u, p in pcts[:per_cat]]
                print(f"  {r.brand} {cat}: {len(pcts[:per_cat])} plain 22K from {min(tries, len(us))} read")
    return out


if __name__ == "__main__":
    import statistics
    import requests
    from collect_charges import UA
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    res = collect(s, per_cat=8, tries=20, seed=1)
    for b, c in sorted({(b, c) for b, c, _, _ in res}):
        v = [p for bb, cc, _, p in res if (bb, cc) == (b, c)]
        print(b, c, "median", statistics.median(v), v)
