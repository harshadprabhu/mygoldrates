#!/usr/bin/env python3
"""Where does Tanishq's price breakup live? (charges job, probe=tanishq)

Tanishq answers a plain request with "Access Blocked", so every page here
goes through the same proxy waterfall the daily rate collector uses
(collect_charges.fetch). Prints, for the sitemap, a few listing pages and the
first products found, the size of what came back, the product links and the
text around "making" - enough to write the reader. Changes nothing.
"""
import re
import sys

import requests

from collect_charges import UA, fetch, _STUDDED_RE, categorize

BASE = "https://www.tanishq.co.in"
LISTINGS = [BASE + "/shop/gold-rings", BASE + "/shop/rings", BASE + "/shop/gold-earrings",
            BASE + "/shop/gold-bangles", BASE + "/shop/mangalsutra"]
PROD_RE = re.compile(r'href="((?:https://www\.tanishq\.co\.in)?/[^"?#]*?\d[A-Z0-9]{6,}[^"?#]*\.html)"')


def around(html, word, n=4, w=220):
    out = []
    for m in re.finditer(word, html, re.I):
        out.append(re.sub(r"\s+", " ", html[max(0, m.start() - w):m.end() + w]))
        if len(out) >= n:
            break
    return out


def main():
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    prods = []
    html, how = fetch(s, BASE + "/sitemap_index.xml", min_len=100)
    print(f"== sitemap_index: {how} {len(html or '')} bytes")
    if html:
        print("\n".join(re.findall(r"<loc>([^<]+)</loc>", html)[:15]))
    for sm in ("sitemap_0.xml", "sitemap_1.xml", "sitemap_2.xml"):
        for _ in range(3):
            x, how = fetch(s, BASE + "/" + sm, min_len=100)
            if x:
                break
        locs = sorted({l.split("?")[0] for l in re.findall(r"<loc>([^<]+)</loc>", x or "")})
        print(f"== {sm}: {how} {len(x or '')} bytes, {len(locs)} urls")
        plain = [l for l in locs if "/product/" in l and not _STUDDED_RE.search(l.replace("-", " "))]
        cats = {}
        for l in plain:
            cats.setdefault(categorize(l), []).append(l)
        print("   plain gold by category:", {c: len(v) for c, v in cats.items()})
        for c in ("Ring", "Bangle", "Earrings", "Mangalsutra"):
            if not any(categorize(p) == c for p in prods):
                prods += cats.get(c, [])[:1]
    for u in []:
        html, how = fetch(s, u)
        found = sorted({p if p.startswith("http") else BASE + p for p in PROD_RE.findall(html or "")})
        print(f"== {u}: {how} {len(html or '')} bytes, {len(found)} products")
        print("\n".join(found[:5]))
        prods += found[:2]
        if html and not found:
            hrefs = re.findall(r'href="([^"]+\.html)"', html)
            print("   .html links:", len(hrefs), hrefs[:8])
            for snip in around(html, r"product-tile|data-pid|pdp-link", n=2, w=300):
                print("   tile:", snip)
    for u in prods[:4]:
        html, how = fetch(s, u)
        print(f"\n== PRODUCT {u}: {how} {len(html or '')} bytes")
        if not html:
            continue
        print("   title:", (re.findall(r"<title>([^<]*)", html) or ["?"])[0][:120])
        for word in ("making", "breakup", "break-up", "gold value", "grand total", "discount", "13[0-9]{3}"):
            for snip in around(html, word, n=3):
                print(f"[{word}] …{snip}…")
        for m in re.findall(r"https://[^\"' ]*(?:price|breakup|Product-)[^\"' ]{0,120}", html)[:10]:
            print("[url]", m)
    sys.exit(0)


if __name__ == "__main__":
    main()
