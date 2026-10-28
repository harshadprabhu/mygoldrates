#!/usr/bin/env python3
"""Which jewellers' product pages publish a making charge we can read?

Read-only survey, run from the making-charges workflow (probe mode). For each
jeweller that has no making-charge data yet it asks, politely and honestly:
  - does robots.txt allow a visit to its product pages (we obey it);
  - does the site answer ordinary visits (a block page or a captcha means the
    jeweller does not want automated visits - we leave it alone);
  - does a product page show the making charge in the page itself (a "price
    breakup" with making / value addition / wastage), or only a total price.
One request at a time, a pause between requests, a few product pages per
jeweller, an honest User-Agent. Prints one line per jeweller; changes nothing.
"""
import json
import os
import re
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests

UA = "MyGoldRatesBot/1.0 (+https://mygoldrates.com; price comparison)"
PAUSE = 1.5
BLOCK = re.compile(r"access denied|request blocked|just a moment|attention required|captcha|verify you are human|"
                   r"are you a robot|unusual traffic|akamai|incapsula|pardon our interruption", re.I)
BREAKUP = re.compile(r"(making|labou?r|value addition|wastage)[^<]{0,60}", re.I)
PERCENT = re.compile(r"(making|labou?r|value addition|wastage|VA)[^<]{0,80}?(\d{1,2}(?:\.\d+)?)\s?%", re.I)
AMOUNT = re.compile(r"(making|labou?r|value addition|wastage)[^<]{0,80}?(?:rs\.?|₹)\s?([\d,]+)", re.I)


def get(url, timeout=25):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml"}, timeout=timeout)
        return r.status_code, r.text
    except requests.RequestException as e:
        return 0, type(e).__name__


def blocked(code, body):
    return code in (401, 403, 406, 429, 503) or (code == 200 and bool(BLOCK.search(body[:4000])) and len(body) < 20000)


def probe(name, domain):
    base = f"https://{domain.strip('/')}"
    out = {"brand": name, "domain": domain}
    code, body = get(base + "/robots.txt")
    rp = RobotFileParser()
    rp.parse(body.splitlines() if code == 200 else [])
    sitemaps = re.findall(r"(?im)^sitemap:\s*(\S+)", body) if code == 200 else []
    time.sleep(PAUSE)
    code, home = get(base + "/")
    out["home"] = code
    if blocked(code, home):
        out["verdict"] = "blocks automated visits - left alone"
        return out
    if code != 200:
        out["verdict"] = f"home page answered {code or home}"
        return out
    if not rp.can_fetch(UA, base + "/"):
        out["verdict"] = "robots.txt disallows automated visits"
        return out
    # product pages: from sitemaps if any, else links on the home page
    urls = []
    for sm in sitemaps[:4]:
        time.sleep(PAUSE)
        c, x = get(sm)
        if c != 200:
            continue
        locs = re.findall(r"<loc>\s*(\S+?)\s*</loc>", x)
        subs = [u for u in locs if u.endswith(".xml") and re.search(r"product|item|jewel", u, re.I)]
        if subs and not any(re.search(r"/(product|p)/|\.html$", u) for u in locs[:5]):
            time.sleep(PAUSE)
            c, x = get(subs[0])
            locs = re.findall(r"<loc>\s*(\S+?)\s*</loc>", x) if c == 200 else []
        urls += [u for u in locs if not u.endswith(".xml")]
        if len(urls) > 30:
            break
    if not urls:
        urls = [urljoin(base, h) for h in re.findall(r'href="([^"#?]+)"', home)
                if re.search(r"(product|/p/|gold-(ring|bangle|chain|earring)|jewel.*\.html)", h, re.I)]
    urls = [u for u in dict.fromkeys(urls) if urlsplit(u).netloc.endswith(urlsplit(base).netloc.replace("www.", ""))]
    out["product_urls_found"] = len(urls)
    seen = pct = amt = tried = 0
    for u in urls[:40:8][:5]:
        if not rp.can_fetch(UA, u):
            continue
        time.sleep(PAUSE)
        c, page = get(u)
        tried += 1
        if blocked(c, page):
            out["verdict"] = "product pages block automated visits - left alone"
            return out
        if c != 200:
            continue
        if BREAKUP.search(page):
            seen += 1
        pct += bool(PERCENT.search(page))
        amt += bool(AMOUNT.search(page))
    out.update(pages_tried=tried, mention_making=seen, with_percent=pct, with_amount=amt)
    if not tried:
        out["verdict"] = "no product pages found to check"
    elif pct or amt:
        out["verdict"] = "READABLE: the making charge is in the page"
    elif seen:
        out["verdict"] = "mentions making charges but no figure in the page (loaded by script?)"
    else:
        out["verdict"] = "no making charge in the page (total price only)"
    return out


def main():
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    have = {b["brand"].lower() for b in json.load(open(__import__("private_store").MC))["brands"]}
    rows = sb.table("brands").select("name,domain,active").eq("active", True).order("name").execute().data
    todo = [r for r in rows if r.get("domain") and r["name"].lower() not in have]
    print(f"probe: {len(todo)} jewellers without making charges, {len(have)} with")
    lines = []
    for r in todo:
        try:
            res = probe(r["name"], r["domain"])
        except Exception as e:                           # one site must not stop the survey
            res = {"brand": r["name"], "verdict": f"error {type(e).__name__}"}
        line = f"{res['brand']} ({res.get('domain', '')}): {res['verdict']}" + (
            f" [pages {res.get('pages_tried')}, making {res.get('mention_making')}, %: {res.get('with_percent')}, Rs: {res.get('with_amount')}]"
            if "pages_tried" in res else "")
        print(line)
        lines.append(line)
    for i in range(0, len(lines), 8):
        msg = "%0A".join(l.replace("%", "%25") for l in lines[i:i + 8])
        print(f"::notice title=making-charge probe {i // 8 + 1}::{msg}")


if __name__ == "__main__":
    main()
