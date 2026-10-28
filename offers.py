#!/usr/bin/env python3
"""Today's jeweller offers, read from each jeweller's own public pages.

Daily (offers.yml). For every active jeweller:

  1. Read the homepage and up to four of its own pages that look like offer
     pages (links mentioning offer / promotion / festive / scheme ...).
     robots.txt is respected; a site that refuses automated visits (403,
     a challenge page) is recorded as "not readable" and left alone.
  2. Pull out offer statements with fixed rules - no AI, nothing paid:
     making-charge discounts, discounts on diamond value or on everything,
     old-gold exchange terms, free coins, rate-protection / advance booking,
     monthly schemes, bank cashback. Each keeps the jeweller's own sentence,
     the page it came from, "up to" wording, minimum purchase and dates.
  3. Write docs/offers.json. The site (generate_site.py) turns it into the
     /gold-offers-today page, working out what a making-charge discount is
     worth in rupees from today's rate and docs/making-charges.json.

A site that blocks plain requests but is in collect_charges.PROXY_HOSTS
(Tanishq) is read through the same proxy waterfall as its daily rate: the
homepage and up to two offer pages, about three proxy requests a day.

What is NOT done: no images or text copied beyond the short offer sentence,
and no judgement of which designs are "better" - that is taste, not a fact
we can check.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import sys
import urllib.robotparser
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse

IST = timezone(timedelta(hours=5, minutes=30))
OUT = "docs/offers.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0 Safari/537.36 MyGoldRatesOffers/1.0")
MAX_PAGES = 5            # homepage + up to 4 offer pages per jeweller
# Where a jeweller's Indian site starts, for sites that send visitors from
# abroad (our reader) to another country's store. Found by hand; the reader
# also looks for an India link itself (india_url).
INDIA_HOME = {
    "malabar": "https://www.malabargoldanddiamonds.com/in/pan-india/en/jewellery.html",
}
COUNTRY_PATH = re.compile(r"^/(?:us|uk|ae|uae|sg|au|ca|qa|om|kw|bh|sa|my|nz|gcc|intl|international)(?:/|$)", re.I)
LINK_WORDS = re.compile(
    r"offer|promotion|promo|deal|festive|festival|scheme|celebrat|dhanteras|"
    r"diwali|akshaya|wedding-season|sale", re.I)

# ------------------------------------------------------------------ rules
PCT = r"(100|\d{1,2}(?:\.\d)?)\s*%"
UPTO = r"(up\s*to|upto|flat|min(?:imum)?)?\s*"
MONEY = r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|lakhs|l)?"

RULES = [
    # 20% off on making charges / flat 15% off making / upto 25% discount on MC
    ("making_off", re.compile(
        UPTO + PCT + r"\s*(?:off|discount|savings?)\s*(?:on|in)?\s*(?:the\s*)?"
        r"(?:gold\s*|diamond\s*|jewell?ery\s*)*(?:making|mc\b|labou?r|wastage|va\b|value\s*addition)", re.I)),
    # making charges flat 20% off / making charges upto 30% off
    # 50% Off on making charges / 25% on making charges (banner wording)
    ("making_off", re.compile(
        UPTO + PCT + r"\s*(?:off\s*)?on\s*(?:the\s*)?(?:making|mc\b|wastage|va\b|value\s*addition)", re.I)),
    ("making_off", re.compile(
        r"(?:making|wastage|value\s*addition)\s*charges?\s*[:\-]?\s*" + UPTO + PCT +
        r"\s*(?:off|discount)", re.I)),
    # zero / no / 0% making charges
    ("making_zero", re.compile(
        r"(?:zero|no|nil|0\s*%)\s*(?:making|wastage|va\b)(?:\s*charges?)?", re.I)),
    # 15% off on diamond value / diamond prices
    ("diamond_off", re.compile(
        UPTO + PCT + r"\s*(?:off|discount)\s*(?:on|in)\s*(?:the\s*)?(?:all\s*)?"
        r"(?:diamond|solitaire|gem\s*stones?|stones?)", re.I)),
    # 0% deduction on old gold exchange / 100% exchange value
    ("exchange", re.compile(
        r"(?:0\s*%|zero|no)\s*deduction|100\s*%\s*(?:exchange|buy\s*back)|"
        r"100\s*%\s*value\s*(?:on|for)\s*(?:your\s*)?(?:old\s*)?gold|"
        r"full\s*value\s*(?:on|for)\s*(?:your\s*)?old\s*gold", re.I)),
    # free gold / silver coin
    ("free_coin", re.compile(r"free\s*(?:\d+\s*(?:g|gm|gram)s?\s*)?(?:gold\s*|silver\s*)?coins?\b", re.I)),
    # gold rate protection / price lock / advance booking
    ("rate_protect", re.compile(
        r"(?:gold\s*)?(?:rate|price)\s*(?:protection|lock|guarantee|assurance)|"
        r"advance\s*booking|book\s*(?:your\s*)?gold\s*(?:at|now)|"
        r"lock\s*(?:your\s*)?gold\s*rate|(?:at\s*the\s*)?booked\s*rate|"
        r"price\s*(?:hiked|dropped)\?", re.I)),
    # monthly purchase schemes
    ("scheme", re.compile(
        r"(?:gold|jewell?ery)\s*(?:savings?|purchase|harvest|plus|tree|mine|"
        r"advantage|investment)\s*(?:scheme|plan)|(?:last|one)\s*(?:month'?s?\s*)?"
        r"instal(?:l)?ment\s*(?:free|waived|on\s*us)", re.I)),
    # bank / card cashback
    ("cashback", re.compile(
        PCT + r"\s*(?:instant\s*)?(?:cash\s*back|discount)\s*(?:with|on|using)\s*"
        r"(?:[A-Z][\w&]+\s*){1,3}(?:bank|card|credit|debit)|"
        r"(?:cash\s*back|instant\s*discount)\s*(?:of\s*)?(?:up\s*to\s*)?" + MONEY, re.I)),
    # buy one, get the second at a discount
    ("combo", re.compile(
        r"buy\s*(?:1|one|2|two)\b[^.]{0,80}?(?:get|2nd|second|3rd|third)\b[^.]{0,40}", re.I)),
    # flat 10% off on gold jewellery / on everything (not on making - above)
    ("all_off", re.compile(
        UPTO + PCT + r"\s*(?:off|discount)\s*(?:on|in)\s*(?:all\s*|the\s*|our\s*)?"
        r"(?:gold\s*)?(?:jewell?ery|collection|purchases?|products?|everything|"
        r"gold\s*value|metal\s*value)(?!\s*making)", re.I)),
]
RULES_BY_KIND = {k: rx for k, rx in RULES}
MIN_PURCHASE = re.compile(
    r"(?:on\s*(?:a\s*)?|with\s*(?:a\s*)?|minimum\s*)?(?:purchase|shopping|buy)\w*\s*"
    r"(?:of|above|worth|over)\s*" + MONEY, re.I)
VALID = re.compile(
    r"(?:valid|offer\s*(?:valid|ends?|available|period)|till|until|up\s*to|ends?\s*on|"
    r"from|starts?)\s*(?:till|until|on|from|:)?\s*"
    r"(\d{1,2}(?:st|nd|rd|th)?\s*(?:of\s*)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"[a-z]*\.?,?\s*(?:20\d\d)?)", re.I)
FOREIGN_CURRENCY = re.compile(r"\$\s*\d|\bUSD\b|€|£")
# Customer reviews quoted on the page are not offers.
REVIEW = re.compile(
    r"\b(?:they|he|she)\s+gave\b|\bhighly\s+recommend|\bthank(?:s|\s+you)\b|"
    r"\b(?:we|i)\s+(?:really\s+)?(?:are\s+|am\s+|was\s+|were\s+)?(?:happy|loved|bought|visited|purchased)|"
    r"\bour\s+(?:purchase|experience|family)\b|\bexperience\s+was\b|"
    r"for\s+the\s+customer.?s\s+money|\b(?:their|the)\s+\w+(?:\s+\w+){0,4}\s+is\s+very\b|"
    # "Beautiful necklace, got 100% discount on making charges making it worth
    # it" - a customer review on CaratLane's homepage, read as an offer and
    # published as CaratLane's on 24 Oct 2026. Past tense and praise mark a
    # review; missing an offer is better than inventing one.
    r"\b(?:i|we|she|he)?\s*got\b|\breceived\b|\bbeautiful\b|\blovely\b|\bamazing\b|"
    r"\bworth\s+it\b|\bloved\b|\bsatisfied\b|\bexcellent\b|\bhappy\s+with\b|\bmy\s+(?:wife|mother|"
    r"daughter|sister|husband|order|purchase)\b|\breview|\brated\b|\bstars?\b", re.I)
# Leading clutter: ratings "4.7 (6)", prices "₹ 91,817", repeated menu text.
LEAD_JUNK = re.compile(r"^(?:\d(?:\.\d)?\s*\(\d+\)\s*|(?:₹|rs\.?)\s*[\d,]+(?:\.\d+)?\s*)+", re.I)
# Fine print: the conditions that decide what an offer is really worth.
COND = re.compile(
    r"valid\s*only|not\s*valid|will\s*not|not\s*applicable|cannot\s*be|t\s*&\s*c|"
    r"terms|conditions?\s*apply|subject\s*to|only\s*(?:if|on|for|when|in)|excluding|"
    r"except|to\s*avail|applicable\s*(?:on|only)|not\s*(?:be\s*)?clubbed", re.I)
DANGLING = re.compile(r"\b(?:on|for|of|with|at|to|in|upto|up\s*to)$", re.I)


def page_text(html: str) -> str:
    """Visible text, with block boundaries kept as line breaks."""
    h = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|section|a|span|td|button)>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    t = _html.unescape(h)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def _sentence(text: str, start: int, end: int) -> str:
    """The jeweller's own words around a match, trimmed to one statement."""
    a = max(text.rfind("\n", 0, start), text.rfind(". ", 0, start - 1) + 1, start - 160)
    b_candidates = [i for i in (text.find("\n", end), text.find(". ", end)) if i != -1]
    b = min(b_candidates + [end + 160])
    # A statement split across two lines ("100% Value On" / "Old Gold
    # Exchange") gets its second line back.
    if DANGLING.search(text[max(a, 0):b].strip()) and b < len(text):
        nxt = text.find("\n", b + 1)
        b = nxt if nxt != -1 and nxt - b < 80 else min(len(text), b + 80)
    # Far from the start of its line, the offer begins at the match itself;
    # what comes before is usually navigation or a product name.
    if start - max(a, 0) > 45:
        a = start
    s = text[max(a, 0):b].strip(" .|-:\n")
    s = LEAD_JUNK.sub("", re.sub(r"\s+", " ", s)).strip()
    s = re.sub(r"^(.{4,40}?)\s+\1\s+", "", s, flags=re.I)   # "Search Search 15% OFF"
    return s[:220]


def _ocr_prepare(text: str) -> str:
    """Banner text from OCR as one run, and the stylised "%" OCR drops put
    back where a number is followed by "off" ("FLAT 20 Off" -> "20% Off")."""
    # Banner phrases run across lines ("FLAT / 20% Off / On All Diamond
    # Jewellery"); the offer rules match across line breaks, which are kept
    # so a lead-in word stays with its own line.
    t = "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())
    t = _fix_figures(t)
    # A dropped "%" before off / on making / on diamond.
    return re.sub(r"\b(\d{1,3})\s+(?=(?:off|on\s+making|on\s+diamond|on\s+m/?c)\b)", r"\1% ", t, flags=re.I)


def _fix_figures(t: str) -> str:
    # Common misreads in stylised figures: "lOO" for 100, "O" for 0, "l" for 1.
    t = re.sub(r"\b[lI1]\s?[oO0][oO0]\b", "100", t)
    return re.sub(r"\b([1-9])[oO]\b", r"\g<1>0", t)


def _ocr_sentence(text: str, start: int, end: int) -> str:
    """One offer out of a banner that may carry several: a lead-in word or
    two ("FLAT", "Up to"), the match, and its words up to the next figure."""
    # A lead-in word counts only from the figure's own banner line: "FLAT"
    # above "20%" must not be read into the "5%" offer printed next to it.
    lead = re.search(r"(?:\b(?:flat|up\s*to|upto|get|enjoy|extra|special)\b[ \t]*)+$",
                     text[max(0, start - 25):start].split("\n")[-1], re.I)
    a = start - (len(lead.group(0)) if lead else 0)
    nl = text.find("\n", end)                 # a panel is one line: stop at its end
    tail = text[end:min(end + 60, nl if nl != -1 else len(text))]
    nxt = re.search(r"\d{1,3}\s*%|\bvalid\b|\bt\s*&\s*c\b|\bmin\b|\bmax\b", tail, re.I)
    b = end + (nxt.start() if nxt else len(tail))
    return re.sub(r"\s+", " ", text[a:b]).strip(" \u00b7.,")[:160]


def extract_offers(text: str, url: str, image: str | None = None) -> list[dict]:
    """Every offer statement on one page, de-duplicated by wording. With
    image=..., the text came from a banner picture (banner_ocr.py)."""
    out, seen = [], set()
    if image:
        text = _ocr_prepare(text)
        # A buy-two banner: its figures belong to the deal ("get your 2nd at
        # 100% off on diamond value / 15% off on VA", Jewel One), not shop-wide.
        if RULES_BY_KIND["combo"].search(text):
            hit = RULES_BY_KIND["combo"].search(text)
            return [{"kind": "combo", "pct": None, "upto": False, "selected": False,
                     "min_purchase": None, "dates": [d.strip() for d in VALID.findall(text)][:2],
                     "text": re.sub(r"\s+", " ", text[hit.start():hit.end() + 80]).strip()[:200],
                     "url": url, "image": image, "banner": text[:300]}]
    for kind, rx in RULES:
        for m in rx.finditer(text):
            sent = (_ocr_sentence if image else _sentence)(text, m.start(), m.end())
            if image:                        # the date and T&C go in their own fields
                sent = re.sub(r"[\s:;,.|*-]*(?:\boffer\b[\s:]*)?(?:\bvalid\b.*|\bt\s*&\s*c\b.*|\d{1,2}\s*(?:jan|feb|mar|apr|may|"
                              r"jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*20\d\d.*)$", "", sent, flags=re.I)
                sent = re.sub(r"\s+offer$", "", sent, flags=re.I).strip()
            if len(sent) < 8 or FOREIGN_CURRENCY.search(sent) or REVIEW.search(sent):
                continue                     # template junk, other markets, reviews
            # A benefit of a monthly plan is the plan's, not a shop-wide offer.
            if kind in ("making_off", "diamond_off", "all_off") and re.search(
                    r"\bmonths?\s*plan|instal(?:l)?ment|\bscheme\b", sent, re.I):
                kind = "scheme"
            key = (kind, sent.lower())
            if key in seen:
                continue
            # A making-charge discount also matches the generic pattern; keep
            # the specific reading only.
            if kind == "all_off" and re.search(r"making|wastage|diamond|stone", sent, re.I):
                continue
            if kind == "diamond_off" and re.search(r"making|wastage|value\s*addition", sent, re.I):
                continue                     # making on diamond jewellery: making_off
            seen.add(key)
            pct = None
            for g in m.groups():
                if g and re.fullmatch(r"100|\d{1,2}(?:\.\d)?", g.strip()):
                    pct = float(g)
                    break
            if kind == "making_zero":
                pct = 100.0
            if pct is not None and not (0 < pct <= 100):
                continue
            # A banner loses the context around a big figure ("100% OFF ON
            # DIAMOND" on Jewel One's was part of a buy-two deal): from a
            # picture, 50% or more is left out rather than published.
            # Exception: a making-charge offer that names diamond jewellery
            # outright ("100% on making charges of certified natural diamond
            # jewellery", PN Gadgil & Sons) is clear on its own.
            # With the banner read panel by panel, a big figure that says
            # outright it is "on making charges" has its context and stays.
            if image and pct is not None and pct >= 50 and not (
                    kind == "making_off" and re.search(r"making\s*charges?", sent, re.I)):
                continue
            # A banner's dates and minimum spend usually cover all of it.
            mp = MIN_PURCHASE.search(text if image else sent)
            vd = VALID.findall(text if image else sent)
            if image and not vd:            # the small "Valid till" may not be read, the date is
                vd = re.findall(r"\b(\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
                                r"[a-z]*\.?,?\s*20\d\d)\b", text, re.I)
            out.append({
                "kind": kind,
                "pct": pct,
                # From a picture, a figure without an explicit "flat" is
                # shown as "up to": banners often print "UPTO" too small to
                # read (PN Gadgil & Sons'), and "up to" is the safer claim.
                "upto": bool(re.search(r"up\s*to|upto", m.group(0) + " " + sent[:60], re.I))
                        or bool(image and not re.search(r"\bflat\b", sent, re.I)),
                "selected": bool(re.search(r"select(ed)?\s*(designs|range|collection|products|items)|"
                                           r"on\s*select", sent, re.I)),
                "min_purchase": _money(mp.group(1), mp.group(2)) if mp else None,
                "dates": list(dict.fromkeys(d.strip() for d in vd))[:2],
                "text": sent,
                "url": url,
                **({"image": image, "banner": text[:300]} if image else {}),
            })
    return out


def _applies(words: str) -> list[str]:
    """What an offer covers, as far as its own wording says."""
    tags = []
    for rx, tag in ((r"diamond\s*jewell?ery", "diamond jewellery only"),
                    (r"\bonline\b", "online purchases only"),
                    (r"select(?:ed)?\s*(?:designs?|range|collection|products|items)|on\s*select",
                     "selected designs only"),
                    (r"solitaire", "solitaires"),
                    (r"\bstud(?:ded)?\b|precious\s*stones?|gem\s*stones?", "stones and gems"),
                    (r"silver", "silver"),
                    (r"(?:22|18)\s*k|gold\s*jewell?ery|plain\s*gold", "gold jewellery")):
        if re.search(rx, words, re.I) and tag not in tags:
            tags.append(tag)
    # "...exchange & buyback facility for Senco jewellery": their own only.
    if re.search(r"for (?:our |[A-Z][A-Za-z]+ )[Jj]ewell?ery|bought from (?:us|them)|"
                 r"purchased from (?:us|them|our)", words):
        tags.append("only jewellery bought from them")
    return tags


def _money(num: str, unit: str | None) -> int | None:
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    u = (unit or "").lower()
    if u == "k":
        v *= 1000
    elif u in ("lakh", "lakhs", "l"):
        v *= 100000
    return int(v)


def _group(o):
    if o["kind"] == "making_off" and re.search(r"diamond\s*jewell?ery", o["text"], re.I):
        return "making_off_diamond"
    return o["kind"]


def summarise(offers: list[dict]) -> list[dict]:
    """Fold per-product repeats ("15% off on making charges" printed under 40
    products) into one line per kind, keeping the range and a count."""
    # One line per kind - but a making-charge offer on diamond jewellery is
    # its own line, never folded into the plain-gold one (PN Gadgil & Sons:
    # up to 50% on gold, up to 100% on diamond jewellery).
    by_kind: dict[str, list[dict]] = {}
    for o in offers:
        by_kind.setdefault(_group(o), []).append(o)
    out = []
    for key, items in by_kind.items():
        kind = items[0]["kind"]
        pcts = sorted({o["pct"] for o in items if o["pct"] is not None})
        # Headline: the biggest figure in an offer statement (not fine
        # print), and of those the fullest wording, to a point.
        heads = [o for o in items if not COND.search(o["text"])] or items
        best = max(heads, key=lambda o: ((o["pct"] or 0), min(len(o["text"]), 140)))
        fine = list(dict.fromkeys(o["text"] for o in items if COND.search(o["text"])))[:3]
        words = " ".join([best["text"]] + fine)
        out.append({
            "kind": kind,
            "pct_min": pcts[0] if pcts else None,
            "pct_max": pcts[-1] if pcts else None,
            "upto": any(o["upto"] for o in items),
            "selected": any(o["selected"] for o in items) or len(pcts) > 1,
            "mentions": len(items),
            "min_purchase": next((o["min_purchase"] for o in items if o["min_purchase"]), None),
            "dates": next((o["dates"] for o in items if o["dates"]), []),
            "applies_to": _applies(words),
            "conditions": fine,
            "text": best["text"],
            "url": best["url"],
            **({"image": best["image"], "banner": best.get("banner", "")} if best.get("image") else {}),
        })
    order = ["making_off", "making_zero", "all_off", "diamond_off", "combo", "exchange",
             "free_coin", "cashback", "rate_protect", "scheme"]
    return sorted(out, key=lambda o: order.index(o["kind"]) if o["kind"] in order else 99)


# ---------------------------------------------------------------- fetching
def _robots(sess, base):
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = sess.get(urljoin(base, "/robots.txt"), timeout=15)
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    except Exception:
        rp.parse([])
    return rp


FOREIGN_HOST = re.compile(r"\.(?:us|ae|uk|co\.uk|sg|com\.au|ca|qa|om|kw|bh|sa|my|nz)(?:/|$|:)", re.I)


def international(html: str) -> bool:
    """True when a site shows our reader (abroad) its international version:
    more dollar prices than rupee prices. Its offers are not India's."""
    text = page_text(html)                    # visible text: scripts are full of "$1"
    rupees = len(re.findall(r"₹|\bRs\.?\s?\d|\bINR\b", text))
    dollars = len(re.findall(r"(?<![A-Za-z])\$\s?\d|\bUSD\b|\bAED\b", text))
    # Server-side geo pages name their assets: Malabar's homepage abroad is
    # all "-intl" / "US-Gold-Scheme" banners.
    # Only image addresses count: "intl" in a script name is a phone-number
    # widget (Prince), "/international-shipping" a link (Candere).
    intl_assets = len(re.findall(
        r"[\w./-]*[-_/](?:intl|international|usa|uae|gcc|dubai)(?=[-_/.])[\w./-]*\.(?:jpe?g|png|webp)",
        html, re.I))
    return dollars > max(3, rupees) or intl_assets >= 3


def india_url(sess, base, final_url, html):
    """The Indian store, when the site sent our reader to another country's:
    a same-site link to /in/ or /india/. None if there is no such link."""
    host = urlparse(final_url or base).netloc
    if not (COUNTRY_PATH.search(urlparse(final_url or "").path) or international(html)):
        return None
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        u = urljoin(final_url or base, m.group(1))
        p = urlparse(u)
        if p.netloc == host and re.match(r"^/(?:in|india|en-in|in-en)(?:/|$)", p.path, re.I):
            try:
                r = sess.get(u, timeout=25)
                if r.status_code == 200 and not international(r.text):
                    return r.url
            except Exception:
                return None
    return None


def _blocked(status, html):
    return status in (401, 403, 429, 503) or bool(re.search(
        r"cf-chl|challenge-platform|Just a moment|Attention Required|captcha", html[:4000], re.I))


def _render(url):
    """Headless Chromium for pages that build their text in the browser.
    Free (runs in the job); used only when the plain page had no offers."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox"],
                                 executable_path=os.environ.get("OFFERS_CHROMIUM") or None)
            pg = b.new_page(user_agent=UA)
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(4000)
            h = pg.content()
            b.close()
            return h
    except Exception:
        return None


def _render_with_banners(url):
    """The rendered page and its banner images (for OCR). Free: Chromium in
    the job. (None, []) if a browser is not available."""
    try:
        from playwright.sync_api import sync_playwright
        import banner_ocr
    except Exception:
        return None, []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--no-sandbox"],
                                 executable_path=os.environ.get("OFFERS_CHROMIUM") or None)
            pg = b.new_page(user_agent=UA, viewport={"width": 1366, "height": 900})
            if os.environ.get("OFFERS_LOCAL_RELAY"):      # local testing only
                def _relay(r):
                    try:
                        r.fulfill(response=r.fetch(timeout=30000))
                    except Exception:
                        try:
                            r.abort()
                        except Exception:
                            pass
                pg.route("**/*", _relay)
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(5000)
            pg.mouse.wheel(0, 1200)                       # lazy-loaded banners
            pg.wait_for_timeout(1500)
            h, imgs = pg.content(), banner_ocr.banner_urls(pg)
            b.close()
            return h, imgs
    except Exception:
        return None, []


def read_banners(sess, imgs, page_url):
    """Offers in banner pictures, read with Tesseract (free)."""
    try:
        import banner_ocr
    except Exception:
        return []
    out = []
    for u in imgs:
        if FOREIGN_HOST.search(urlparse(u).netloc + "/") or re.search(
                r"[-_/](?:intl|international|usa|uae|gcc|dubai)[-_/.]", u, re.I):
            continue                     # e.g. cdn.caratlane.us: the US site's banner
        try:
            r = sess.get(u, timeout=25)
            if r.status_code != 200 or len(r.content) > 6_000_000:
                continue
            txt = banner_ocr.read_image(r.content)
        except Exception:
            continue
        if txt:
            out += extract_offers(txt, page_url, image=u)
    return out


def banner_extras(text_offers, banner_offers):
    """The banner offers that add something to the page text: a kind of
    offer the text does not have (PN Gadgil & Sons' "up to 50% on gold
    making" banner next to an older page about diamond making), or the
    dates the text leaves out."""
    groups = {}
    for o in text_offers:
        groups.setdefault(_group(o), []).append(o)
    out = []
    for o in banner_offers:
        g = groups.get(_group(o))
        if not g or (o["dates"] and not any(t["dates"] for t in g)):
            out.append(o)
    return out


def offer_links(html: str, base: str) -> list[str]:
    host = urlparse(base).netloc.replace("www.", "")
    found = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href, label = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        u = urljoin(base, href)
        if urlparse(u).netloc.replace("www.", "") != host:
            continue
        if LINK_WORDS.search(href) or LINK_WORDS.search(label):
            if u not in found and u.rstrip("/") != base.rstrip("/"):
                found.append(u)
    # Offer-ish URLs first, shortest first: /offers beats a product page.
    found.sort(key=lambda u: (not re.search(r"offer|promotion|scheme", u, re.I), len(u)))
    return found[:MAX_PAGES - 1]


PROXY_PAGES = 3          # homepage + up to 2 offer pages, each one proxy credit


def read_via_proxy(sess, rec, base):
    """A blocked site the daily rate already reads through the proxies
    (collect_charges.PROXY_HOSTS): its homepage and offer pages, rendered."""
    try:
        from collect_charges import PROXY_HOSTS, fetch
    except Exception:
        PROXY_HOSTS = ()
    if urlparse(base).netloc not in PROXY_HOSTS:
        rec["status"] = "not readable (the site blocks automated visits)"
        return rec
    home, how = fetch(sess, base)
    if not home or _blocked(200, home):
        rec["status"] = f"not readable today (proxies: {how})"
        return rec
    rec["read_from"], rec["via"] = base, "proxy"
    pages, raw = [(base, home)], []
    for u in offer_links(home, base)[:PROXY_PAGES - 1]:
        h, _ = fetch(sess, u)
        if h and not _blocked(200, h):
            pages.append((u, h))
    for u, h in pages:
        rec["pages"].append(u)
        raw += extract_offers(page_text(h), u)
    try:
        import banner_ocr
        imgs = banner_ocr.banner_urls_from_html(home, base)
    except Exception:
        imgs = []
    rec["banners"] = len(imgs)
    raw += banner_extras(raw, read_banners(sess, imgs[:10], base))
    rec["offers"] = summarise(raw)
    if not rec["offers"]:
        rec["status"] = "no offers published as text or in banners today"
    return rec


def read_brand(sess, brand, render=True):
    domain = (brand.get("domain") or "").strip()
    rec = {"slug": brand["slug"], "name": brand["name"], "domain": brand.get("domain") or "",
           "status": "ok",
           "pages": [], "offers": []}
    if not domain:
        rec["status"] = "no website"
        return rec
    base = INDIA_HOME.get(brand["slug"]) or "https://" + domain.rstrip("/") + "/"
    rp = _robots(sess, base)
    raw = []
    try:
        r = sess.get(base, timeout=25)
        home, status = r.text, r.status_code
    except Exception as e:
        rec["status"] = f"unreachable ({type(e).__name__})"
        return rec
    if _blocked(status, home):
        return read_via_proxy(sess, rec, base)
    ind = india_url(sess, base, r.url, home)
    if ind:                                  # sent abroad: read the Indian store
        base = ind
        try:
            r = sess.get(base, timeout=25)
            home = r.text
        except Exception:
            pass
    elif international(home) or COUNTRY_PATH.search(urlparse(r.url).path):
        rec["status"] = "shows its international site to our reader, so no Indian offers"
        return rec
    rec["read_from"] = base
    pages = [(base, home)]
    for u in offer_links(home, base):
        if not rp.can_fetch(UA, u):
            continue
        try:
            r = sess.get(u, timeout=25)
            if r.status_code == 200 and not _blocked(r.status_code, r.text):
                pages.append((u, r.text))
        except Exception:
            pass
    for u, h in pages:
        rec["pages"].append(u)
        raw += extract_offers(page_text(h), u)
    imgs = []
    if render:
        # The homepage in a real browser: its text when the plain page had
        # none (built by the site's scripts), and its banner pictures, which
        # is where many jewellers put their offers.
        h, imgs = _render_with_banners(base)
        rec["rendered"] = bool(h)
        if h and international(h):
            rec["rendered"] = "international"
            h, imgs = None, []
        if h and not raw:
            raw += extract_offers(page_text(h), base)
        if not raw and len(pages) > 1:
            h2 = _render(pages[1][0])
            if h2:
                raw += extract_offers(page_text(h2), pages[1][0])
    # Banner pictures: those named in the plain (Indian) page first, then
    # the rendered page's own. A banner adds what the page text does not
    # already say.
    try:
        import banner_ocr
        imgs = banner_ocr.banner_urls_from_html(home, base) + [
            u for u in (imgs if render else []) if u not in home]
    except Exception:
        imgs = []
    rec["banners"] = len(imgs)
    raw += banner_extras(raw, read_banners(sess, imgs[:10], base))
    rec["offers"] = summarise(raw)
    if not rec["offers"]:
        rec["status"] = "no offers published as text or in banners today"
    return rec


def main(argv=None):
    import requests
    argv = argv if argv is not None else sys.argv[1:]
    only = set(a for a in argv if not a.startswith("-"))
    render = "--no-render" not in argv
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"):
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
        brands = sb.table("brands").select("slug, name, domain, rate_url, active").eq("active", True).execute().data
    else:
        brands = json.load(open(os.environ.get("OFFERS_BRANDS", "brands.json")))
    brands = [b for b in brands if not only or b["slug"] in only]
    brands = [b for b in brands if not str(b.get("rate_url", "")).startswith("submitted:")]
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})

    prev = {}
    try:
        for b in json.load(open(OUT)).get("brands", []):
            for o in b.get("offers", []):
                prev[(b["slug"], o["kind"], o["text"])] = o.get("first_seen")
    except Exception:
        pass
    today = datetime.now(IST).date().isoformat()
    result = []
    for b in sorted(brands, key=lambda x: x["name"].lower()):
        rec = read_brand(sess, b, render=render)
        for o in rec["offers"]:
            o["first_seen"] = prev.get((rec["slug"], o["kind"], o["text"])) or today
        print(f"{rec['name']:28s} {len(rec['offers'])} offers  {rec['status']}")
        result.append(rec)
    data = {"updated": datetime.now(IST).isoformat(timespec="minutes"),
            "note": "Offers as published on each jeweller's own website on the date shown. "
                    "Read automatically; confirm terms with the jeweller before buying.",
            "brands": result}
    if only:
        print(json.dumps(data, ensure_ascii=False, indent=1)[:6000])
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"offers: {sum(len(b['offers']) for b in result)} from "
          f"{sum(1 for b in result if b['offers'])} of {len(result)} jewellers")


if __name__ == "__main__":
    main()
