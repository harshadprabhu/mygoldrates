#!/usr/bin/env python3
"""Render the public gold-rate comparison site from today's scraped rates.

Runs in CI right after scrape.py. Reads today's rates from Supabase, fetches
the IBJA reference rate, and bakes everything into static HTML written to
docs/ for GitHub Pages. The inquiry page posts to Supabase with the public
anon key (insert-only table behind RLS); no privileged keys are shipped.
"""

from __future__ import annotations

import glob
import hashlib
import html as _html
import json
import os
import re
import statistics
from datetime import datetime, timezone, timedelta
from string import Template

import requests
from supabase import create_client

SITE_URL = "https://mygoldrates.com"
CUSTOM_DOMAIN = "mygoldrates.com"
CONTACT_EMAIL = "contact@mygoldrates.com"
# General formula: Unknown Rate = (Known Rate / Known Karat) x Unknown Karat.
# 24K uses 1.0 (canonical_24k_pre_gst IS already the 24K per-gram price).
# Fractions are exact karat/24 ratios (not the rounded BIS fineness stamps
# 916/750/583) so every displayed purity is derived with the same formula
# used when a brand only publishes one purity. Kept in sync with scrape.py.
PURITY_FRACTION = {"24K": 24 / 24, "22K": 22 / 24, "18K": 18 / 24, "14K": 14 / 24}
IST = timezone(timedelta(hours=5, minutes=30))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def inr(v, dec=0):
    """Indian-style grouping: 1,23,456."""
    s = f"{v:,.{dec}f}"
    parts = s.split(",")
    if len(parts) <= 2:
        return "₹" + s
    head, tail = parts[0], parts[-1]
    mid = "".join(parts[1:-1])
    digits = head + mid
    groups = []
    while len(digits) > 2:
        groups.insert(0, digits[-2:])
        digits = digits[:-2]
    if digits:
        groups.insert(0, digits)
    return "₹" + ",".join(groups) + "," + tail


def _draw_mark(d, s, ox, oy, gold):
    """Draw the chart-arrow brand mark (40x40 viewBox coords, scaled by s)."""
    def X(v): return ox + v * s
    def Y(v): return oy + v * s
    rad = max(2, int(1.6 * s))
    d.rounded_rectangle([X(4.5), Y(21), X(13.5), Y(36)], radius=rad, fill=gold)
    d.rounded_rectangle([X(16.5), Y(12), X(25.5), Y(36)], radius=rad, fill=gold)
    lw = max(2, int(s * 3.2))
    d.line([X(5), Y(25.5), X(17), Y(17), X(25), Y(21), X(34), Y(8.5)],
           fill=gold, width=lw, joint="curve")
    d.line([X(27.5), Y(7.5), X(35), Y(6.5), X(34.5), Y(14)],
           fill=gold, width=lw, joint="curve")


FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
<defs><linearGradient id="g" x1="4" y1="38" x2="36" y2="4" \
gradientUnits="userSpaceOnUse"><stop stop-color="#B07E12"/>\
<stop offset=".55" stop-color="#E3BF63"/>\
<stop offset="1" stop-color="#F4E3A6"/></linearGradient></defs>
<rect width="48" height="48" rx="10" fill="#171106"/>
<g transform="translate(4,4)">
<rect x="4.5" y="21" width="9" height="15" rx="1.6" fill="url(#g)"/>
<rect x="16.5" y="12" width="9" height="24" rx="1.6" fill="url(#g)"/>
<path d="M5 25.5 17 17 25 21 34 8.5" stroke="url(#g)" stroke-width="3.4" \
fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M27.5 7.5 35 6.5 34.5 14" stroke="url(#g)" stroke-width="3.4" \
fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</g></svg>
"""


def build_favicons():
    """Favicon set drawn from the brand mark. Deterministic (no daily churn).

    Writes favicon.svg always; the PNG/ICO set needs Pillow (present in CI).
    """
    with open("docs/favicon.svg", "w", encoding="utf-8") as f:
        f.write(FAVICON_SVG)
    try:
        from PIL import Image, ImageDraw
    except Exception as e:  # pragma: no cover - Pillow missing
        print("favicon: Pillow unavailable, PNG/ICO skipped:", e)
        return
    master = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(master)
    d.rounded_rectangle([0, 0, 511, 511], radius=104, fill=(23, 17, 6))
    s = 10.4
    off = (512 - 40 * s) / 2
    _draw_mark(d, s, off, off, (227, 191, 99))
    for size, name in ((48, "icon-48.png"), (96, "icon-96.png"),
                       (180, "apple-touch-icon.png"), (192, "icon-192.png"),
                       (512, "icon-512.png")):
        master.resize((size, size), Image.LANCZOS).save(f"docs/{name}")
    # ICO with the sizes Google/browsers look for (incl. 48x48).
    master.save("docs/favicon.ico", format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48)])
    print("favicon: wrote svg/ico/png set")


def build_email_logo(path="docs/email-logo.png"):
    """Mark + wordmark on transparent bg for the email digest header (2x)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as e:  # pragma: no cover - Pillow missing
        print("email-logo: Pillow unavailable, skipping:", e)
        return
    CREAM, GOLD, MUTED = (240, 234, 216), (227, 191, 99), (167, 155, 126)

    def font(sz):
        try:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", sz)
        except Exception:
            return ImageFont.load_default()

    img = Image.new("RGBA", (760, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _draw_mark(d, 2.9, 4, 6, GOLD)
    big = font(62)
    x = 136
    for t, c in (("My", CREAM), ("Gold", GOLD), ("Rates", CREAM),
                 (".com", MUTED)):
        d.text((x, 28), t, font=big, fill=c)
        x += d.textlength(t, font=big)
    img.save(path)
    print(f"email-logo: wrote {path}")


def build_og_image(path="docs/og.png"):
    """Static branded 1200x630 Open Graph card (deterministic, no daily churn).

    Drawn with Pillow using DejaVu fonts (present on the CI runner); degrades
    gracefully if Pillow or the fonts are unavailable.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as e:  # pragma: no cover - Pillow missing
        print("og: Pillow unavailable, skipping og.png:", e)
        return

    W, H = 1200, 630
    CREAM, GOLD, MUTED, TEXT2 = (240, 234, 216), (227, 191, 99), \
        (167, 155, 126), (200, 193, 175)

    def font(sz, bold=False):
        for p in (f"/usr/share/fonts/truetype/dejavu/DejaVuSans"
                  f"{'-Bold' if bold else ''}.ttf",):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
        return ImageFont.load_default()

    img = Image.new("RGB", (W, H), (11, 8, 5))
    # gold glow, top-right
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = 1000, 90
    for r in range(420, 0, -6):
        a = int(30 * (1 - r / 420))
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(224, 186, 86, a))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 7], fill=GOLD)                 # top hairline
    d.rectangle([0, H - 7, W, H], fill=(120, 92, 26))    # bottom hairline

    # chart-arrow mark (scaled from the 40x40 SVG viewBox)
    _draw_mark(d, 3.1, 150, 210, GOLD)

    # wordmark
    big = font(78, bold=True)
    x, y = 300, 232
    for t, c in (("My", CREAM), ("Gold", GOLD), ("Rates", CREAM),
                 (".com", MUTED)):
        d.text((x, y), t, font=big, fill=c)
        x += d.textlength(t, font=big)

    d.text((302, 336), "INDIA'S 1ST GOLD RATE COMPARISON PLATFORM",
           font=font(28, bold=True), fill=MUTED)
    d.text((150, 430), "Compare 24K, 22K & 18K gold rates today across",
           font=font(34), fill=TEXT2)
    d.text((150, 478), "India's top jewellers - updated every day.",
           font=font(34), fill=TEXT2)

    img.save(path)
    print(f"og: wrote {path}")


# City/state landing pages: enriched with local market hubs, regional jeweller tags & unique intro content.
LOCATIONS = [
    # Top major gold trading & retail hubs in India
    "Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Kochi", "Coimbatore", "Lucknow",
    "Surat", "Chandigarh", "Patna", "Indore", "Visakhapatnam", "Vadodara",
    "Nagpur", "Bhopal",
    # Key states
    "Maharashtra", "Tamil Nadu", "Karnataka", "Kerala", "Telangana",
    "Andhra Pradesh", "Gujarat", "Rajasthan", "West Bengal", "Uttar Pradesh",
    "Madhya Pradesh", "Punjab", "Haryana", "Bihar", "Odisha", "Assam",
]

CITY_ENRICHMENT_DATA = {
    "Mumbai": {
        "hubs": "Zaveri Bazaar, Dadar TT Circle, Bandra Turner Road, Borivali West",
        "state": "Maharashtra",
        "regional_brands": ["PNG Sons", "Ranka Jewellers", "Chandukaka Saraf", "Bhindi Jewellers"],
        "intro": "Mumbai is India's primary gold trading hub and home to the historic Zaveri Bazaar in South Mumbai, where daily wholesale rates set the benchmark for physical gold trading across Western India. Gold buyers in Mumbai frequently compare live 24K and 22K per-gram rates before visiting premier jewellers in Dadar, Bandra, and Borivali.",
    },
    "Delhi": {
        "hubs": "Chandni Chowk (Dariba Kalan), Karol Bagh (Bank Street), South Extension",
        "state": "Delhi",
        "regional_brands": ["PC Jeweller", "Tanishq", "Kalyan Jewellers"],
        "intro": "Delhi's gold market centers around the historic Dariba Kalan in Chandni Chowk and Bank Street in Karol Bagh, representing one of Northern India's largest retail gold hubs. Buyers across NCR (Delhi, Noida, Gurugram, Ghaziabad) track daily 24K and 22K rates to evaluate festival and wedding season price movements.",
    },
    "Bengaluru": {
        "hubs": "Chickpet, Commercial Street, Jayanagar 4th Block, Malleshwaram",
        "state": "Karnataka",
        "regional_brands": ["C. Krishniah Chetty (CKC)", "Lalithaa Jewellery", "Bhima Jewellers", "Kirtilals"],
        "intro": "Bengaluru's traditional gold market in Chickpet and modern showrooms in Commercial Street and Jayanagar feature traditional South Indian jewelry alongside modern lightweight gold. Gold rates in Karnataka reflect national board rates, with 22K (916 purity) being the preferred choice for traditional temple jewelry.",
    },
    "Chennai": {
        "hubs": "T. Nagar (Usman Road), Sowcarpet, Mylapore, Anna Nagar",
        "state": "Tamil Nadu",
        "regional_brands": ["Vummidi Bangaru Jewellers (VBJ)", "Lalithaa Jewellery", "Kirtilals", "Sri Kumaran Stores"],
        "intro": "Chennai is one of India's largest consumer markets for gold, centered around Usman Road in T. Nagar and NSC Bose Road in Sowcarpet. The Madras Jewellers & Diamond Merchants Association and major regional brands publish daily rates, making rate comparison essential for buyers across Tamil Nadu.",
    },
    "Hyderabad": {
        "hubs": "Panjagutta, Abids, General Bazaar (Secunderabad), Madhapur",
        "state": "Telangana",
        "regional_brands": ["Vaibhav Jewellers", "Lalithaa Jewellery", "Kalyan Jewellers"],
        "intro": "Hyderabad's gold market spans historic shopping districts in General Bazaar Secunderabad and Abids to major modern showrooms along the Panjagutta stretch. Gold purchasing in Telangana peaks during auspicious occasions like Akshaya Tritiya, Ugadi, and wedding seasons.",
    },
    "Kolkata": {
        "hubs": "Bada Bazar, Bowbazar (BB Ganguly Street), Gariahat, Salt Lake",
        "state": "West Bengal",
        "regional_brands": ["Senco Gold", "PC Chandra Jewellers", "Anjali Jewellers"],
        "intro": "Kolkata's Bowbazar and Bada Bazar are renowned for handcrafted gold filigree work (Kalka & Nakshi craftsmanship). Buyers in West Bengal closely follow daily 22K rates for traditional Bengali bridal jewelry, comparing board rates across leading regional and national brands.",
    },
    "Pune": {
        "hubs": "Laxmi Road, Raviwar Peth, Kothrud, MG Road Camp",
        "state": "Maharashtra",
        "regional_brands": ["PNG Sons", "Ranka Jewellers", "Chandukaka Saraf"],
        "intro": "Pune's traditional gold market along Laxmi Road and Raviwar Peth features iconic Maharashtrian designs like Kolhapuri Saaj, Thushi, and Mangalsutra. Daily rates in Pune mirror Mumbai board rates across national and heritage Maharashtrian jewellers.",
    },
    "Ahmedabad": {
        "hubs": "CG Road, Manek Chowk, Satellite, Ashram Road",
        "state": "Gujarat",
        "regional_brands": ["RBZ Jewellers", "Bhindi Jewellers", "Kalyan Jewellers"],
        "intro": "Ahmedabad's historic Manek Chowk night market and premier shopping showrooms along CG Road serve gold investors and jewelry buyers across Gujarat. Gold is valued both as an investment asset and for traditional Gujarati wedding ornaments.",
    },
    "Jaipur": {
        "hubs": "Johari Bazaar, MI Road, Vaishali Nagar",
        "state": "Rajasthan",
        "regional_brands": ["PC Jeweller", "Tanishq", "Kalyan Jewellers"],
        "intro": "Jaipur's famous Johari Bazaar is world-renowned for traditional Kundan, Meenakari, and Jadau gold jewelry. Buyers in Rajasthan track national 24K and 22K gold rates to evaluate raw gold value separate from intricate artisanal labor charges.",
    },
    "Kochi": {
        "hubs": "MG Road, Broadway, Edappally",
        "state": "Kerala",
        "regional_brands": ["Josco Jewellers", "Bhima Jewellers", "Jos Alukkas", "Malabar Gold"],
        "intro": "Kerala accounts for a significant share of India's total gold consumption. In Kochi, the All Kerala Gold & Silver Merchants Association (AKGSMA) publishes daily benchmark rates followed by major Kerala-based global jewelry chains along MG Road.",
    },
    "Coimbatore": {
        "hubs": "Cross Cut Road, Oppanakara Street, RS Puram",
        "state": "Tamil Nadu",
        "regional_brands": ["Kirtilals", "Lalithaa Jewellery", "Vummidi Bangaru"],
        "intro": "Coimbatore is a major manufacturing and retail hub for gold jewelry in South India, centered along Cross Cut Road and Oppanakara Street. Known for machine-made chains and precision casting, local buyers closely compare daily 22K and 18K per-gram quotes.",
    },
    "Lucknow": {
        "hubs": "Hazratganj, Chowk, Aminabad",
        "state": "Uttar Pradesh",
        "regional_brands": ["PC Jeweller", "Tanishq", "Kalyan Jewellers"],
        "intro": "Lucknow's historic Chowk market and commercial hub in Hazratganj are famous for handcrafted gold ornaments and traditional Awadhi jewelry designs. Gold rate comparison in UP helps buyers calculate net gold costs before making charges and 3% GST.",
    },
    "Surat": {
        "hubs": "Ghod Dod Road, Varachha, Ring Road",
        "state": "Gujarat",
        "regional_brands": ["RBZ Jewellers", "Kalyan Jewellers", "Tanishq"],
        "intro": "Surat, known globally as a gem and diamond processing center, has a bustling gold retail market along Ghod Dod Road. Local buyers analyze 24K bullion rates alongside 18K gold rates common in diamond-studded jewelry.",
    },
    "Chandigarh": {
        "hubs": "Sector 17, Sector 22, Sector 35",
        "state": "Punjab / Haryana",
        "regional_brands": ["PC Jeweller", "Tanishq", "Malabar Gold"],
        "intro": "Chandigarh's Sector 17 and Sector 22 markets serve shoppers across Punjab, Haryana, and Himachal Pradesh. Heavy gold jewelry and investment coins are widely purchased, making daily rate tracking essential during festival and marriage seasons.",
    },
    "Patna": {
        "hubs": "Hathwa Market, Maurya Lok, Boring Road",
        "state": "Bihar",
        "regional_brands": ["Tanishq", "Kalyan Jewellers", "PC Jeweller"],
        "intro": "Patna's gold retail sector along Boring Road and Hathwa Market sees high demand for 22K traditional jewelry during Chhath Puja, Dhanteras, and wedding seasons. National board rates apply uniformly across major showrooms in Bihar.",
    },
    "Indore": {
        "hubs": "Sarafa Bazaar, MG Road, Palasia",
        "state": "Madhya Pradesh",
        "regional_brands": ["DP Abhushan", "Tanishq", "Kalyan Jewellers"],
        "intro": "Indore's famous Sarafa Bazaar—a bustling gold market by day and food street by night—is the commercial heart of Madhya Pradesh's jewelry trade. Daily 24K and 22K rates in Indore follow national bullion trends closely.",
    },
    "Visakhapatnam": {
        "hubs": "Daba Gardens, Kurupam Market, VIP Road",
        "state": "Andhra Pradesh",
        "regional_brands": ["Vaibhav Jewellers", "Lalithaa Jewellery", "Kalyan Jewellers"],
        "intro": "Visakhapatnam is a primary gold buying destination in Coastal Andhra, with Kurupam Market and VIP Road hosting heritage jewelers like Vaibhav Jewellers alongside national chains. Buyers track per-gram 22K (916) prices daily.",
    },
    "Vadodara": {
        "hubs": "Alkapuri, Mandvi, Raopura",
        "state": "Gujarat",
        "regional_brands": ["RBZ Jewellers", "Bhindi Jewellers", "Kalyan Jewellers"],
        "intro": "Vadodara's historic Mandvi market and modern retail district in Alkapuri cater to gold buyers across Central Gujarat. Daily rates for 24K coins and 22K ornaments match state-wide board benchmarks.",
    },
    "Nagpur": {
        "hubs": "Itwari, Dharampeth, Sadar",
        "state": "Maharashtra",
        "regional_brands": ["PNG Sons", "Ranka Jewellers", "Chandukaka Saraf"],
        "intro": "Nagpur's Itwari market is Vidarbha's largest wholesale and retail gold market. Shoppers compare daily rates between heritage Maharashtrian jewelers and national chains in Dharampeth before purchasing.",
    },
    "Bhopal": {
        "hubs": "New Market, Chowk Bazaar, MP Nagar",
        "state": "Madhya Pradesh",
        "regional_brands": ["Tanishq", "Kalyan Jewellers", "PC Jeweller"],
        "intro": "Bhopal's Chowk Bazaar in Old City and MP Nagar in New City feature a mix of traditional gold craft and modern retail chains. Daily rates reflect national median gold prices.",
    },
}



# Cities that get their own dated daily gold-news page. Kept small on purpose:
# a new domain shouldn't flood Google with near-duplicate dated pages (that
# triggers "discovered - not indexed" and can dent overall site quality).
DAILY_NEWS_CITIES = ["Mumbai", "Delhi", "Bengaluru", "Chennai"]


# Regional jewellers -> states they serve. Brands not listed here are treated
# as national (available everywhere). Used for the "jewellers in your area"
# GPS filter and the Regional badge.
REGION_MAP = {
    "vaibhav": ["Andhra Pradesh", "Telangana", "Karnataka", "Tamil Nadu",
                "Odisha"],
    "vummidi": ["Tamil Nadu"],
    "lalithaa": ["Tamil Nadu", "Andhra Pradesh", "Telangana", "Karnataka"],
    "kirtilals": ["Tamil Nadu", "Karnataka", "Kerala"],
    "pngsons": ["Maharashtra"],
    "ranka": ["Maharashtra"],
    "josco": ["Kerala"],
    "rbz": ["Gujarat"],
    "srikumaran": ["Tamil Nadu", "Karnataka"],
    "bhindi": ["Maharashtra", "Gujarat"],
    "chandukaka": ["Maharashtra"],
    "ckc": ["Karnataka"],
}


def loc_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch_akgsma():
    """AKGSMA (All Kerala Gold & Silver Merchants Assoc.) South-India rate.
    Publishes 22K & 18K per gram; returns (r24_derived, r22, r18) or None."""
    try:
        r = requests.get("https://akgsma.com/", headers={"User-Agent": UA},
                         timeout=20)
        t = re.sub(r"<[^>]+>", " ", r.text)

        def grab(tag):
            m = re.search(tag + r".{0,40}?([1-9][0-9,]{3,5})", t, re.S)
            if not m:
                return None
            v = float(m.group(1).replace(",", ""))
            return v if 6000 <= v <= 20000 else None

        r22, r18 = grab("22K916"), grab("18K750")
        if r22:
            r24 = round(r22 / (22 / 24), 2)
            print(f"akgsma: 22K {r22} -> 24K {r24}")
            return r24, r22, (r18 or round(r24 * (18 / 24), 2))
    except Exception as e:
        print("akgsma: fetch failed:", type(e).__name__, str(e)[:80])
    return None


def fetch_ibja():
    """IBJA daily reference rates, per 10g pre-GST -> per gram.
    Returns (r999, r916) or None."""
    try:
        r = requests.get("https://ibjarates.com", headers={"User-Agent": UA},
                         timeout=20)
        text = re.sub(r"<[^>]+>", " ", r.text)

        def grab(purity):
            m = re.search(purity + r"\D{0,60}?([\d,]{6,7})", text)
            if not m:
                return None
            v = float(m.group(1).replace(",", "")) / 10.0
            return v if 8000 <= v <= 22000 else None

        r999, r916 = grab("999"), grab("916")
        if r999 and r916:
            return r999, r916
    except Exception:
        pass
    return None


def fetch_news(limit=14):
    """Live gold news via Google News RSS (auto-refreshes each build).

    Returns [{title, link, source, dt}] - headlines only, each linking to the
    original publisher (aggregation, not reproduction).
    """
    url = ("https://news.google.com/rss/search?q="
           "gold%20rate%20OR%20gold%20price%20India%20when:3d"
           "&hl=en-IN&gl=IN&ceid=IN:en")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        items = re.findall(r"<item>(.*?)</item>", r.text, re.S)

        def field(block, tag):
            m = re.search(r"<" + tag + r"[^>]*>(.*?)</" + tag + ">",
                          block, re.S)
            return m.group(1).strip() if m else ""

        out, seen = [], set()
        for it in items:
            title = _html.unescape(re.sub(r"<[^>]+>", "", field(it, "title")))
            link = _html.unescape(field(it, "link"))
            src = _html.unescape(re.sub(r"<[^>]+>", "", field(it, "source")))
            if src and title.endswith(" - " + src):
                title = title[:-(len(src) + 3)].strip()
            try:
                dt = datetime.strptime(field(it, "pubDate")[:25].strip(),
                                       "%a, %d %b %Y %H:%M:%S")
            except Exception:
                dt = None
            key = title.lower()
            if title and link and key not in seen and len(title) > 15:
                out.append({"title": title, "link": link, "source": src,
                            "dt": dt})
                seen.add(key)
            if len(out) >= limit:
                break
        print(f"news: {len(out)} gold headlines fetched")
        return out
    except Exception as e:
        print("news: fetch failed:", type(e).__name__, str(e)[:100])
        return []


def fetch_mcx():
    """MCX gold futures (per 10g, 995 fine) via Moneycontrol's price feed.

    MCX's own site is Akamai bot-walled; this public feed mirrors the
    exchange quote. Contract expiry is nominally the 5th of the month but
    shifts for holidays (e.g. 04DEC2026), so nearby days are probed.
    Returns [{symbol, expiry, ltp, chg, pchg}, ...] or None.
    """
    def quote(symbol, expiry):
        r = requests.get(
            "https://priceapi.moneycontrol.com/pricefeed/mcx/"
            f"commodityfuture/{symbol}", params={"expiry": expiry},
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=20)
        j = r.json()
        return j.get("data") if j.get("code") == "200" else None

    out = []
    today = datetime.now(IST).date()
    try:
        for sym in ("GOLD", "GOLDM"):
            found = None
            y, m = today.year, today.month
            for _ in range(5):                      # this month + next 4
                for day in (5, 4, 6):               # holiday-shifted expiries
                    d = datetime(y, m, day, tzinfo=IST).date()
                    if d < today:
                        continue
                    data = quote(sym, d.strftime("%d%b%Y").upper())
                    if data:
                        ltp = float(data.get("pricecurrent") or 0)
                        if 60000 <= ltp <= 400000:  # sanity: Rs per 10g
                            found = {
                                "symbol": sym,
                                "expiry": data.get("EXPIRY", ""),
                                "ltp": ltp,
                                "chg": float(data.get("pricechange") or 0),
                                "pchg": float(
                                    data.get("pricepercentchange") or 0)}
                        break
                if found:
                    break
                m += 1
                if m > 12:
                    m, y = 1, y + 1
            if found:
                out.append(found)
    except Exception as e:
        print("mcx: fetch failed:", type(e).__name__, str(e)[:100])
        return None
    if out:
        print("mcx: " + ", ".join(
            f"{c['symbol']} {c['expiry']} {c['ltp']:.0f}" for c in out))
        return out
    print("mcx: no contracts found")
    return None


def trend_chart(trend):
    """Inline SVG line chart of (iso_date, median) points; grows with history."""
    if len(trend) < 2:
        return ('<p class="dnote">The trend chart builds up as daily history '
                'accumulates - check back in a few days.</p>')
    w, h, pad = 352, 150, 14
    vals = [v for _, v in trend]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(trend)
    pts = " ".join(
        f"{pad + (w - 2 * pad) * i / (n - 1):.1f},"
        f"{h - pad - (h - 2 * pad) * (v - lo) / rng:.1f}"
        for i, (_, v) in enumerate(trend))
    d0 = datetime.fromisoformat(trend[0][0]).strftime("%d %b")
    d1 = datetime.fromisoformat(trend[-1][0]).strftime("%d %b")
    return (f'<svg viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="Median 24K gold rate trend {d0} to {d1}">'
            f'<polyline points="{pts}" fill="none" stroke="#D9B24A" '
            f'stroke-width="2.5" stroke-linejoin="round" '
            f'stroke-linecap="round"/>'
            f'<text x="{pad}" y="12">{inr(hi)} high</text>'
            f'<text x="{pad}" y="{h - 3}">{inr(lo)} low · {d0} - {d1}</text>'
            f'</svg>')


_FMT_JS = ("function g(id){return document.getElementById(id);}"
           "function fmt(n){if(!isFinite(n))return '-';var s=Math.round(n)"
           ".toString(),o=s.slice(-3),r=s.slice(0,-3);"
           "while(r.length>2){o=r.slice(-2)+','+o;r=r.slice(0,-2);}"
           "if(r)o=r+','+o;return '₹'+o;}")


def _calc_js(kind, rate24):
    """Inline calculator script; RATE is the per-gram 24K(999) rate."""
    body = {
        "loan": """
        function calc(){var wt=+g('w').value||0,pur=+g('p').value,
          L=(+g('ltv').value||0)/100,R=(+g('r').value||0)/1200,N=+g('n').value||0;
          var val=wt*RATE*pur/0.999,loan=val*L;
          var emi=R>0?loan*R*Math.pow(1+R,N)/(Math.pow(1+R,N)-1):(N>0?loan/N:0);
          g('loan').textContent=fmt(loan)+' eligible';
          g('val').textContent=fmt(val);
          g('emi').textContent=(isFinite(emi)&&emi>0)?fmt(emi):'-';
          g('tot').textContent=(isFinite(emi)&&emi>0)?fmt(emi*N):'-';}
        ['w','p','ltv','r','n'].forEach(function(id){
          g(id).addEventListener('input',calc);});calc();""",
        "sip": """
        function calc(){var i=(+g('g').value||0)/1200,n=(+g('y').value||0)*12,
          P=+g('m').value||0;
          var fv=i>0?P*((Math.pow(1+i,n)-1)/i)*(1+i):P*n;
          var inv=P*n;
          g('fv').textContent=fmt(fv)+' value';
          g('inv').textContent=fmt(inv);
          g('gain').textContent=fmt(fv-inv);
          g('grams').textContent=(fv/RATE).toFixed(1)+' g';}
        ['m','y','g'].forEach(function(id){
          g(id).addEventListener('input',calc);});calc();""",
        "making": """
        function calc(){var wt=+g('w').value||0,pur=+g('p').value,
          mt=g('mt').value,mc=+g('mc').value||0;
          var gv=wt*RATE*pur/0.999;
          var mk=mt==='pct'?gv*mc/100:mc*wt;
          var sub=gv+mk,gst=sub*0.03;
          g('total').textContent=fmt(sub+gst)+' total';
          g('gv').textContent=fmt(gv);
          g('mk').textContent=fmt(mk);
          g('gst').textContent=fmt(gst);}
        ['w','p','mt','mc'].forEach(function(id){
          g(id).addEventListener('input',calc);});calc();""",
    }[kind]
    return ("<script>(function(){var RATE=" + str(rate24) + ";" +
            _FMT_JS + body + "})();</script>")


def _articles(rate_str, med, inr):
    """Evergreen SEO guides: (slug, title, desc, h1, body_html)."""
    return [
        ("22k-vs-24k-gold",
         "22K vs 24K Gold - Difference, Purity & Which to Buy | MyGoldRates",
         "22K vs 24K gold explained: purity, price, durability and which is "
         "better for jewellery vs investment in India.",
         "22K vs 24K Gold: What's the Difference?",
         f"""
  <p>Walk into any jewellery store in India and you will see rate boards
  showing both 22K and 24K prices. The difference seems simple — one is purer
  than the other — but the choice between them shapes everything from how much
  you pay, to how long your jewellery lasts, to how easily you can resell it
  later. This guide explains both purities in plain language.</p>

  <h2>Understanding gold purity: what "K" means</h2>
  <p>The letter K stands for <em>karat</em>, a unit of purity that tells you
  what fraction of the metal is pure gold. Pure gold is 24 parts gold out of
  24 — hence 24K. 22K means 22 parts gold and 2 parts other metals. The
  number is not arbitrary; it maps to a precise fineness stamp (parts per
  thousand) that jewellers and BIS hallmarking use.</p>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px">
    <thead><tr style="background:color-mix(in srgb,var(--gold) 10%,transparent)">
      <th style="padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)">Karat</th>
      <th style="padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)">Fineness</th>
      <th style="padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)">Gold %</th>
      <th style="padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)">Common use</th>
    </tr></thead>
    <tbody>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">24K</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">999</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">99.9%</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Coins, bars, digital gold</td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">22K</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">916</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">91.6%</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Traditional jewellery, bridal sets</td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">18K</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">750</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">75.0%</td><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Diamond-set, daily-wear pieces</td></tr>
      <tr><td style="padding:8px 12px">14K</td><td style="padding:8px 12px">585</td><td style="padding:8px 12px">58.5%</td><td style="padding:8px 12px">International fashion jewellery</td></tr>
    </tbody>
  </table>

  <h2>24K gold (99.9% pure)</h2>
  <p>24K gold is the purest form commercially available. It carries the
  <strong>999 fineness</strong> stamp and is the standard for investment
  products: minted coins (like MMTC-PAMP, government Sovereign Gold Bonds),
  gold bars, ETFs, and digital gold platforms. Because it is essentially
  undiluted metal, its value is straightforward to calculate and easy for any
  buyer worldwide to verify.</p>
  <p>The downside is physical weakness. Pure gold is a soft metal — around 2.5
  on the Mohs hardness scale, roughly as hard as a fingernail. A plain 24K
  bangle will bend, dent and scratch with ordinary daily wear. Fine prong
  settings holding diamonds or gemstones would deform over time. For this
  reason, most traditional jewellers in India will not offer 24K wearable
  jewellery beyond plain chains or very simple bangles.</p>
  <p>Today the 24K gold rate is <strong>{rate_str} per gram</strong>
  (pre-GST, median across leading Indian jewellers).</p>

  <h2>22K gold (91.6% pure)</h2>
  <p>22K gold — stamped <strong>916</strong> — contains 91.6% gold and 8.4%
  other metals, typically silver, copper or zinc. This small alloy addition
  transforms the physical properties dramatically: 22K is significantly harder,
  holds intricate filigree work, retains prong shapes, and survives years of
  daily wear with far less deformation than 24K.</p>
  <p>In India, 22K is the dominant jewellery purity. Virtually all traditional
  bridal sets, temple jewellery, Kundan and Polki pieces, and festive ornaments
  are made in 22K. When a jeweller quotes "the gold rate today," they almost
  always mean the 22K price. At current rates, 22K is priced at roughly
  <strong>{inr(med['22K'])} per gram</strong> — about 8.4% less than 24K,
  reflecting the lower gold content.</p>
  <p>The alloy metals used in 22K are chosen carefully. Copper adds warmth to
  the colour and improves hardness; silver lightens the colour and adds
  ductility. A skilled alloy blend is what gives different jewellers' gold
  slightly different visual qualities, even at the same karat.</p>

  <h2>18K gold: the third standard you should know</h2>
  <p>18K (750 fineness, 75% gold) is increasingly popular in India for
  diamond jewellery, everyday rings, and contemporary designs. The higher
  alloy content makes it harder than 22K and better suited for complex
  stone settings. Its lower gold fraction also means a lower gold cost, so
  more of the piece's price reflects craftsmanship and stones rather than
  metal. White gold and rose gold are typically 18K with specific alloys
  (palladium or rhodium for white, copper for rose).</p>

  <h2>Which should you buy? A decision guide</h2>
  <p>The right purity depends entirely on how you will use the gold.</p>
  <ul>
    <li><strong>Buying for investment or resale:</strong> Choose 24K coins or
    bars. They carry the highest gold content and are universally priced at
    spot, making resale straightforward with any dealer.</li>
    <li><strong>Bridal or traditional jewellery:</strong> 22K is the correct
    choice. It holds complex designs, maintains its yellow colour, and is
    what Indian buyers and resellers expect when you eventually sell.</li>
    <li><strong>Diamond-set, everyday rings, contemporary pieces:</strong> 18K
    provides the strength needed for fine stone settings and is the norm for
    imported or international-style jewellery.</li>
    <li><strong>Gifting gold coins:</strong> 24K minted coins (5g, 8g, 10g,
    50g denominations from brands like Tanishq, Malabar or MMTC-PAMP) are
    the most liquid and universally accepted gift form.</li>
  </ul>

  <h2>Price difference between 22K and 24K</h2>
  <p>The price gap is proportional to gold content. At today's median 24K
  rate of {rate_str}/g, the 22K price is approximately
  {inr(med['22K'])}/g — a difference of about
  {inr(round(med['24K'] - med['22K']))}/g. On a 20-gram piece this
  adds up to {inr(round((med['24K'] - med['22K']) * 20))} just in metal value,
  before making charges. This is why knowing the current rate matters before
  you shop.</p>

  <h2>Resale value: which purity sells better?</h2>
  <p>Both 22K and 24K jewellery can be resold to most jewellers, but the
  experience differs. 24K coins and bars from known mints fetch spot price
  with minimal discount. 22K jewellery resale typically involves a small
  deduction for assaying and melting, often 2-5% of metal value. Older
  jewellery without a BIS hallmark may face a steeper deduction because the
  buyer cannot immediately verify the purity without testing.</p>
  <p>The practical takeaway: always buy BIS-hallmarked jewellery with a HUID
  stamp — it makes purity undeniable and resale smoother.</p>

  <h2>Before you buy: compare today's rate</h2>
  <p>Whatever purity you choose, the per-gram gold rate varies between
  jewellers by &#8377;50–200 at any given time. A &#8377;100/g difference
  on a 40-gram necklace is &#8377;4,000 — significant for most buyers.
  Use the <a href="{SITE_URL}/">comparison table</a> to see today's
  rates side by side before walking into a store.</p>"""),
        ("gold-hallmarking",
         "Gold Hallmarking in India - BIS Hallmark & HUID Explained | MyGoldRates",
         "What the BIS hallmark and 6-digit HUID mean, interactive HUID scanner tool, purity fineness guide, and how to verify gold before buying in India.",
         "Gold Hallmarking (BIS): What to Check Before You Buy",
         f"""
  <p>A <strong>BIS hallmark</strong> is an official certification issued by the Bureau of Indian Standards certifying that your gold jewellery's purity is genuine. Since 2021, hallmarking with a 6-digit HUID is mandatory for gold jewellery sold across India.</p>

  <!-- Interactive BIS Hallmark & HUID Verification Tool -->
  <div class="huid-scanner-card" aria-label="BIS Gold Hallmarking Scanner and Verifier">
    <div class="huid-header">
      <div class="huid-icon">&#128269;</div>
      <div>
        <h3 style="margin:0 0 4px;font-size:20px">BIS Hallmark &amp; HUID Verification Tool</h3>
        <p class="huid-sub">Enter the 6-digit alphanumeric HUID or purity code stamped on your gold article to verify purity, gold percentage, and BIS standards instantly.</p>
      </div>
    </div>

    <div class="huid-input-wrap">
      <div class="huid-field">
        <label for="huid-input">Enter 6-Digit HUID or Purity Stamp (e.g. 22K916, A7B9C3)</label>
        <div class="huid-input-group">
          <input type="text" id="huid-input" maxlength="8" placeholder="e.g. 22K916, A7B9C3, 18K750" value="22K916" autocomplete="off" spellcheck="false">
          <button type="button" id="huid-scan-btn" class="btn btn-gold">Verify Hallmark</button>
        </div>
      </div>
      <div class="sample-huid-pills">
        <span class="sample-label">Try Preset Stamps:</span>
        <button type="button" class="huid-sample-btn" data-code="22K916">22K 916 (Bridal)</button>
        <button type="button" class="huid-sample-btn" data-code="24K999">24K 999 (Coin/Bar)</button>
        <button type="button" class="huid-sample-btn" data-code="18K750">18K 750 (Diamond)</button>
        <button type="button" class="huid-sample-btn" data-code="14K585">14K 585 (Daily Wear)</button>
        <button type="button" class="huid-sample-btn" data-code="H8K9P2">Sample HUID: H8K9P2</button>
      </div>
    </div>

    <!-- Verification Certificate Display -->
    <div id="huid-result" class="huid-certificate">
      <div class="cert-header">
        <div class="cert-status">&#9989; BIS Certified Hallmarked Gold</div>
        <div class="cert-id" id="res-code">STAMP: 22K916</div>
      </div>
      <div class="cert-grid">
        <div class="cert-tile">
          <div class="ck">Purity Grade</div>
          <div class="cv" id="res-karat">22 Carat (22K)</div>
          <div class="cu" id="res-fineness">91.6% Pure Gold (916 Fineness)</div>
        </div>
        <div class="cert-tile">
          <div class="ck">Today's Gold Value (10g)</div>
          <div class="cv" id="res-val">&#8377;1,32,650</div>
          <div class="cu">Pre-GST market reference</div>
        </div>
        <div class="cert-tile">
          <div class="ck">Recommended Use</div>
          <div class="cv" id="res-use">Bridal &amp; Traditional Jewellery</div>
          <div class="cu">Optimal strength &amp; rich yellow lustre</div>
        </div>
      </div>

      <!-- Mandatory 3-Mark Checklist -->
      <div class="cert-checklist">
        <h4>Mandatory 3 Marks Present on Hallmarked Gold</h4>
        <div class="checklist-items">
          <div class="cl-item">
            <span class="cl-check">&#10003;</span>
            <div>
              <strong>1. BIS Triangular Logo</strong>
              <p>Bureau of Indian Standards official triangular mark certifying IS 1417 purity standards.</p>
            </div>
          </div>
          <div class="cl-item">
            <span class="cl-check">&#10003;</span>
            <div>
              <strong>2. Purity &amp; Fineness Stamp</strong>
              <p><span id="res-stamp-text">22K916</span> (916 parts pure gold per 1000 parts alloy).</p>
            </div>
          </div>
          <div class="cl-item">
            <span class="cl-check">&#10003;</span>
            <div>
              <strong>3. 6-Digit Alphanumeric HUID Code</strong>
              <p>Unique laser-engraved code issued by a BIS Assaying &amp; Hallmarking Centre (AHC).</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Live Valuation Calculator -->
      <div class="cert-calc-box">
        <div class="cc-row">
          <label for="huid-weight">Calculate Pure Gold Value:</label>
          <div class="cc-input-wrap" style="display:inline-flex;align-items:center;gap:6px">
            <input type="number" id="huid-weight" value="10" min="0.1" step="0.1"> <span style="font-size:13px;color:#C4B99A">grams</span>
          </div>
        </div>
        <div class="cc-result-total">
          Estimated Value: <strong id="huid-calc-total">&#8377;1,32,650</strong> <small style="font-size:11px;opacity:0.8">(pre-GST)</small>
        </div>
      </div>
    </div>
  </div>

  <h2>The Three Mandatory Marks to Check</h2>
  <p>When buying gold jewellery in India, inspect the item under magnification to ensure all three mandatory marks are laser-engraved:</p>
  <ul>
    <li><strong>1. The BIS Logo:</strong> A triangular mark representing the Bureau of Indian Standards.</li>
    <li><strong>2. Purity &amp; Fineness Grade:</strong> Indicates exact purity:
      <ul>
        <li><strong>24K999:</strong> 99.9% Pure Gold (Coins &amp; Bars)</li>
        <li><strong>22K916:</strong> 91.6% Pure Gold (Traditional Jewellery)</li>
        <li><strong>18K750:</strong> 75.0% Pure Gold (Diamond &amp; Gemstone Jewellery)</li>
        <li><strong>14K585:</strong> 58.5% Pure Gold (Everyday Wear)</li>
      </ul>
    </li>
    <li><strong>3. 6-Digit Alphanumeric HUID:</strong> A Hallmark Unique Identification code (e.g. <code>A7B9C3</code>) unique to that specific item.</li>
  </ul>

  <h2>How to Verify HUID in the BIS Care App</h2>
  <p>The Government of India provides the official <strong>BIS Care App</strong> (available on Android and iOS). You can verify any hallmarked gold article before making payment:</p>
  <ol>
    <li>Open the official <strong>BIS Care App</strong> on your smartphone.</li>
    <li>Tap on <strong>"Verify HUID"</strong>.</li>
    <li>Enter the 6-digit HUID engraved on your jewellery piece.</li>
    <li>The app will instantly display the registered Jeweller Name, AHC Centre Name, Jeweller BIS Registration Number, Date of Hallmarking, and Certified Purity.</li>
  </ol>

  <h2>Check the Rate &amp; Billed Invoice</h2>
  <p>Hallmarking confirms purity, not price. Always compare the day's <a href="{SITE_URL}/">gold rate today</a> and check <a href="{SITE_URL}/making-charges-calculator">making charges</a> across jewellers before buying.</p>"""),
        ("how-gold-rates-are-set",
         "How Gold Rates Are Set in India - Explained | MyGoldRates",
         "How daily gold rates in India are decided: international spot price, "
         "rupee-dollar rate, import duty, GST, and jeweller premiums.",
         "How Are Gold Rates Set in India?",
         f"""
  <p>The gold rate you see on a jeweller's rate board or website is not a
  single number handed down from one authority. It is the end result of a
  chain of decisions — international markets, currency rates, government
  duties, industry associations, and the jeweller's own pricing strategy.
  Understanding each step helps you know whether today's quote is fair.</p>

  <h2>Step 1: The international spot price</h2>
  <p>Gold is a global commodity. It trades in US dollars per troy ounce
  (1 troy ounce = 31.1035 grams) on two main exchanges: the COMEX futures
  exchange in New York and the London OTC market (LBMA — London Bullion Market
  Association). The <strong>LBMA Gold Price</strong> is the globally accepted
  reference, set twice daily in London at approximately 10:30 AM and 3:00 PM
  GMT through an electronic auction involving banks and bullion dealers.</p>
  <p>This price fluctuates continuously based on global demand and supply,
  US Federal Reserve interest rate expectations, geopolitical risk, currency
  movements, and central bank buying. When US interest rates rise, gold often
  falls (because bonds become a competing store of value). When global
  uncertainty rises, gold typically rises as a safe-haven asset.</p>

  <h2>Step 2: Converting dollars to rupees</h2>
  <p>Since India prices gold in rupees per gram (not dollars per troy ounce),
  the spot price must be converted. The formula is:</p>
  <p style="background:color-mix(in srgb,var(--gold) 8%,transparent);
  padding:12px 16px;border-radius:8px;font-family:'IBM Plex Mono',monospace;
  font-size:13px;margin:12px 0">
  Gold price (₹/g) = (Spot price in USD/oz ÷ 31.1035) × USD/INR rate</p>
  <p>This means a weakening rupee pushes Indian gold prices up even when global
  gold is flat. In 2023–24, the rupee depreciation accounted for a meaningful
  portion of the rise in domestic gold prices. Conversely, a strengthening
  rupee can offset some global price rises.</p>

  <h2>Step 3: Import duty and other charges</h2>
  <p>India imports approximately 700–900 tonnes of gold annually, making it
  one of the world's largest importers. Every imported gold bar goes through
  customs, and India levies a <strong>basic customs duty of 6%</strong> plus
  Agriculture Infrastructure and Development Cess (AIDC) of 5% — an effective
  combined import levy of around 9-10% on the CIF (cost, insurance, freight)
  value. This duty was reduced from 15% in the July 2024 Union Budget to
  boost official imports and curb smuggling.</p>
  <p>Nominated agencies (banks, commodity exchanges, government entities like
  MMTC and STCL) are authorized to import gold. The landed cost of a gold bar
  includes the duty, freight, and insurance. This landed cost forms the
  domestic wholesale reference.</p>

  <h2>Step 4: IBJA and association benchmarks</h2>
  <p>The <strong>India Bullion and Jewellers Association (IBJA)</strong>,
  headquartered in Mumbai, publishes daily gold rates for 24K and 22K gold.
  IBJA members are bullion traders, refiners and large jewellers who deal
  in physical gold. The IBJA rate is essentially the Mumbai wholesale market
  price — it reflects the landed import cost plus domestic supply-demand
  dynamics in the country's largest bullion market.</p>
  <p>The <strong>AKGSMA</strong> (All Kerala Gold &amp; Silver Merchants
  Association) does the same for South India, particularly Kerala, where gold
  consumption is among the highest in the country. Regional variation
  between IBJA (Mumbai/North) and AKGSMA (South) rates reflects local
  demand, transportation costs, and regional association influence.</p>
  <p>Most large national jewellers use the IBJA rate as their base. The
  published jeweller rate is typically IBJA rate plus a small premium
  (usually &#8377;50–200/g) that covers sourcing costs, certification,
  inventory risk, and brand margin.</p>

  <h2>Step 5: The jeweller's pricing decision</h2>
  <p>Individual jewellers set their own published rate. Factors include:</p>
  <ul>
    <li><strong>Sourcing cost:</strong> Large chains buying directly from
    refiners may have a lower landed cost than smaller jewellers buying
    through intermediaries.</li>
    <li><strong>Hallmarking and certification:</strong> BIS-certified
    jewellers incur costs for assaying and stamping each piece.</li>
    <li><strong>Brand positioning:</strong> Premium brands like Tanishq
    or Malabar may price slightly higher, using trust and certification
    as justification. Newer or regional chains often price at or below
    IBJA to attract customers.</li>
    <li><strong>Inventory timing:</strong> A jeweller who bought gold
    a month ago at a lower price may still quote a market-rate price
    today — pocketing additional margin — or may pass on savings to
    drive footfall.</li>
  </ul>

  <h2>Step 6: GST at point of sale</h2>
  <p>When you buy jewellery in India, <strong>3% Goods and Services Tax</strong>
  is added to the total billed amount (gold value + making charges). This GST
  is paid by the buyer to the jeweller, who remits it to the government.
  The rates shown on this site and on most jewellers' websites are
  <em>pre-GST</em> — the GST is added at the billing counter. Always confirm
  the GST-inclusive price before finalising a purchase.</p>

  <h2>Why rates differ between jewellers</h2>
  <p>On any given day, the 24K gold rate can vary by &#8377;100–300 per gram
  between jewellers. The primary reason is not dishonesty — it is the
  compounding of sourcing cost differences, inventory timing, regional
  market factors, and brand margin. Some brands also embed a portion of
  making charges into the base rate (so the headline rate looks higher but
  making charges are lower, or vice versa).</p>
  <p>This is exactly what <a href="{SITE_URL}/">MyGoldRates</a> solves:
  we normalize all published rates to a pre-GST, per-gram, 24K basis so
  you can compare them honestly on a single screen.</p>

  <h2>MCX futures: a forward-looking signal</h2>
  <p>The Multi Commodity Exchange (MCX) in India trades gold futures contracts
  — agreements to buy or sell gold at a fixed price on a future date. MCX gold
  futures are quoted in rupees per 10 grams for a standard 1 kg contract.
  The near-month futures price reflects the market's expectation of where
  spot gold will be on the delivery date. When futures trade at a premium
  to today's spot (called contango), traders expect prices to rise or are
  pricing in carrying costs. Watching MCX alongside spot helps gauge
  short-term market sentiment. You can see today's MCX price in the
  Markets drawer on the <a href="{SITE_URL}/">homepage</a>.</p>"""),
        ("making-charges-explained",
         "Gold Making Charges Explained - How They Work | MyGoldRates",
         "What gold making charges and wastage are, how they're calculated "
         "(% or per gram), and how to reduce what you pay in India.",
         "Gold Making Charges &amp; Wastage, Explained",
         f"""
  <p>Walk out of a jewellery store and the final bill is almost always higher
  than the gold rate multiplied by the weight. The gap is making charges —
  often 10–35% on top of metal value. Understanding how they work is the
  single most effective way to save money when buying gold jewellery in India.</p>

  <h2>What making charges actually are</h2>
  <p><strong>Making charges</strong> (also called <em>value addition</em> or
  <em>labour charges</em>) are the fee a jeweller levies for the craft involved
  in turning raw gold into a finished piece. They cover:</p>
  <ul>
    <li>Artisan labour (hand-crafting, setting stones, soldering)</li>
    <li>Design and mould costs for machine-made pieces</li>
    <li>Quality control and finishing</li>
    <li>A portion of the jeweller's overhead and margin</li>
  </ul>
  <p>Making charges are separate from the gold rate and from GST. On most
  jewellery invoices you will see three line items: gold value, making charges,
  and 3% GST on the combined total.</p>

  <h2>Two ways jewellers charge making charges</h2>
  <p>Indian jewellers use one of two methods — and the method matters enormously
  for what you end up paying.</p>

  <h3>1. Percentage of gold value</h3>
  <p>The most common method. Making charges are expressed as a % of the gold
  component's value. For example, 15% making on a piece whose gold is worth
  &#8377;50,000 adds &#8377;7,500. This method is transparent and lets you
  compare jewellers easily. Based on data from Senco Gold across hundreds of
  products, typical rates by category are:</p>
  <table style="width:100%;border-collapse:collapse;margin:14px 0;font-size:14px">
    <thead><tr style="background:color-mix(in srgb,var(--gold) 10%,transparent)">
      <th style="padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)">Category</th>
      <th style="padding:9px 12px;text-align:right;border-bottom:1px solid var(--line)">Typical range</th>
      <th style="padding:9px 12px;text-align:right;border-bottom:1px solid var(--line)">Senco median</th>
    </tr></thead>
    <tbody>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Coins</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">0–8%</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">5%</td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Mangalsutra</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">14–25%</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">18%</td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Chains</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">18–28%</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">22%</td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Bangles</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">18–30%</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">27%</td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Earrings</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">18–35%</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">20%</td></tr>
      <tr><td style="padding:8px 12px;border-bottom:1px solid var(--line)">Rings</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">22–40%</td><td style="padding:8px 12px;text-align:right;border-bottom:1px solid var(--line)">30%</td></tr>
      <tr><td style="padding:8px 12px">Pendants</td><td style="padding:8px 12px;text-align:right">30–55%</td><td style="padding:8px 12px;text-align:right">41%</td></tr>
    </tbody>
  </table>
  <p style="font-size:13px;color:var(--ink-3)">Source: MyGoldRates making charges comparison, based on published product price breakups. Data refreshed every 15 days.</p>

  <h3>2. Flat rate per gram</h3>
  <p>Some jewellers (especially for lightweight or machine-made pieces) charge
  a fixed rupee amount per gram — for example &#8377;450/g on a chain or
  &#8377;600/g on earrings. This can be harder to compare when jewellers
  use different methods, but the total effect is similar for mid-weight pieces.
  You can convert: if a 10g piece has &#8377;500/g making on gold worth
  &#8377;1,400/g, that's a 35.7% equivalent rate.</p>

  <h2>What is "wastage"?</h2>
  <p>In some traditional jewellers — especially in South India — you will see
  a separate line item called <em>wastage</em> (also spelled wastidge) alongside
  making charges. Wastage is supposed to represent the gold lost during the
  manufacturing process: filings, polishing dust, solder material. Historically
  it was a real cost on handcrafted pieces.</p>
  <p>Today, however, most manufacturing is done in controlled factory settings
  where physical waste is minimal and recovered. Many consumer advocates and
  jewellery industry insiders note that wastage is increasingly a pricing
  mechanism rather than a real cost, especially for machine-made jewellery.
  When you see wastage on a bill, treat it as an additional making charge
  and factor it into your comparison.</p>

  <h2>How the final bill adds up</h2>
  <p>The standard formula for a gold jewellery purchase:</p>
  <p style="background:color-mix(in srgb,var(--gold) 8%,transparent);
  padding:14px 16px;border-radius:8px;font-family:'IBM Plex Mono',monospace;
  font-size:13px;line-height:1.8;margin:12px 0">
  Gold value = weight (g) × gold rate (₹/g)<br>
  Making charges = gold value × making % (or weight × per-gram rate)<br>
  GST = (Gold value + making charges) × 3%<br>
  <strong>Total billed = gold value + making charges + GST</strong></p>
  <p>Example: a 20-gram 22K necklace at today's rate of {inr(med['22K'])}/g
  with 25% making charges:</p>
  <ul>
    <li>Gold value: 20 × {inr(med['22K'])} = {inr(round(med['22K'] * 20))}</li>
    <li>Making (25%): {inr(round(med['22K'] * 20 * 0.25))}</li>
    <li>GST (3%): {inr(round(med['22K'] * 20 * 1.25 * 0.03))}</li>
    <li><strong>Total: {inr(round(med['22K'] * 20 * 1.25 * 1.03))}</strong></li>
  </ul>
  <p>Use the <a href="{SITE_URL}/making-charges-calculator">making charges
  calculator</a> to run your own numbers before you buy.</p>

  <h2>Are making charges negotiable?</h2>
  <p>Yes — more often than most buyers realise. Chain stores often have some
  flexibility, especially during festival or clearance sales. Independent local
  jewellers typically have more room to negotiate than national chains.
  Key negotiation points:</p>
  <ul>
    <li>Ask explicitly: "What is your making charge on this piece?"</li>
    <li>For heavier pieces (50g+), request a volume discount.</li>
    <li>Old gold exchange programmes often absorb making charges on the new
    piece — compare total cost including your exchange value.</li>
    <li>Festival sale discounts are frequently applied to making charges
    rather than the gold rate (which is market-linked).</li>
  </ul>

  <h2>How to minimise making charges</h2>
  <ul>
    <li><strong>Choose machine-made over handmade</strong> for investment pieces
    — plain chains and simple bangles have the lowest making charges.</li>
    <li><strong>Compare across jewellers</strong> using our
    <a href="{SITE_URL}/making-charges-comparison">making charges comparison</a>
    tool, which tracks real data from brands' own product listings.</li>
    <li><strong>Avoid very intricate designs</strong> if resale value matters —
    complex craftsmanship means high making charges that you recover very little
    of at resale (resellers buy at gold rate, not craftsmanship value).</li>
    <li><strong>Buy coins separately</strong> if you want gold for investment:
    making charges on coins are 2–5%, far lower than jewellery.</li>
  </ul>"""),
    ]


def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    supabase_url = os.environ["SUPABASE_URL"]
    # AdSense: dormant until the ADSENSE_CLIENT secret (ca-pub-...) is set.
    ads_client = os.environ.get("ADSENSE_CLIENT", "").strip()
    ads_slot = os.environ.get("ADSENSE_SLOT", "").strip()
    if ads_client:
        ads_head = (
            '<script async src="https://pagead2.googlesyndication.com/pagead/'
            f'js/adsbygoogle.js?client={ads_client}" crossorigin="anonymous">'
            f'</script>\n<meta name="google-adsense-account" content="{ads_client}">')
    else:
        ads_head = ""
    if ads_client and ads_slot:
        ads_unit = (
            '<ins class="adsbygoogle" style="display:block" '
            f'data-ad-client="{ads_client}" data-ad-slot="{ads_slot}" '
            'data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script>')
    else:
        ads_unit = ""   # Auto ads (head script) place ads; no manual boxes
    today = datetime.now(timezone.utc).date().isoformat()

    def load_rates(day):
        rw = sb.table("rates").select("*, brands(name, slug, domain)") \
               .eq("rate_date", day).execute().data
        rw = [r for r in rw if r.get("brands")
              and r.get("canonical_24k_pre_gst")]
        return [r for r in rw if r["status"] == "published"]

    live = load_rates(today)
    if not live:
        # Weekends/holidays: no fresh rates for today. Reuse the most recent
        # published day so the site STILL regenerates with today's date & time
        # (keeps lastmod/date fresh = site stays "alive" for SEO).
        latest = sb.table("rates").select("rate_date") \
                   .eq("status", "published").order("rate_date", desc=True) \
                   .limit(1).execute().data
        if latest:
            live = load_rates(latest[0]["rate_date"])
            print(f"no fresh rates today; reusing {latest[0]['rate_date']} "
                  "with today's date/time")
    if not live:
        print("no rates at all; site not regenerated")
        return

    # Median + lowest are computed over NATIONAL brands only (the default
    # view). Regional stores are excluded here; the site re-computes "lowest"
    # client-side when a visitor taps "In my area".
    national = [r for r in live
                if (r["brands"] or {}).get("slug") not in REGION_MAP]
    base = national or live
    median24 = statistics.median(r["canonical_24k_pre_gst"] for r in base)
    lowest = min(base, key=lambda r: r["canonical_24k_pre_gst"])
    highest = max(base, key=lambda r: r["canonical_24k_pre_gst"])
    now_ist = datetime.now(IST)
    display_date = now_ist.strftime("%d %B %Y")
    display_time = now_ist.strftime("%I:%M %p IST").lstrip("0")

    def ladder(c):
        return {p: c * f for p, f in PURITY_FRACTION.items()}

    med = ladder(median24)

    # ---------------------------------------------- live gold news feed
    news_items = fetch_news()

    def news_card(n):
        when = n["dt"].strftime("%d %b, %H:%M") if n["dt"] else ""
        meta = " &middot; ".join([x for x in (n["source"], when) if x])
        return (f'<a class="newscard" href="{_html.escape(n["link"])}" '
                f'target="_blank" rel="nofollow noopener">'
                f'<div class="nt">{_html.escape(n["title"])}</div>'
                f'<div class="nd">{_html.escape(meta)}</div></a>')

    news_home = ""
    if news_items:
        cards = "".join(news_card(n) for n in news_items[:5])
        news_home = (
            '<section class="citylinks" aria-labelledby="newsh">'
            '<p class="eyebrow">Gold News</p>'
            '<h2 id="newsh">Latest Gold News Today</h2>'
            '<p class="hint">Live headlines, refreshed through the day.</p>'
            f'{cards}'
            f'<p style="margin-top:10px"><a href="{SITE_URL}/news" '
            'style="font-weight:600">All gold news &amp; daily recaps '
            '&rarr;</a></p></section>')

    # --------------------------------------------------- MCX gold futures
    mcx = fetch_mcx()
    mcx_tile = ""
    if mcx:
        g = next((c for c in mcx if c["symbol"] == "GOLD"), mcx[0])
        mcx_tile = (
            f'<div class="rtile"><div class="k">MCX Gold Futures</div>'
            f'<div class="v">{inr(g["ltp"])}</div>'
            f'<div class="u">per 10g (995) · {g["expiry"]} · '
            f'{g["pchg"]:+.2f}%</div></div>')

    # ----------------------------------------- AKGSMA (South India benchmark)
    akgsma = fetch_akgsma()
    akgsma_tile = ""
    if akgsma:
        ak24, ak22, ak18 = akgsma
        akgsma_tile = (
            f'<div class="rtile"><div class="k">AKGSMA · South India 24K</div>'
            f'<div class="v">{inr(ak24)}</div>'
            f'<div class="u">per gram · 22K {inr(ak22)}</div></div>')

    # --------------------------------------------------------------- IBJA
    ibja = fetch_ibja()
    if ibja:
        r999, r916 = ibja
        premium_med = (median24 / r999 - 1) * 100
        ibja_tiles = f'''
<section class="ibja-ref" aria-labelledby="ibjarefh">
  <p class="eyebrow">Bullion, Futures &amp; Regional Reference</p>
  <h2 id="ibjarefh">IBJA &amp; AKGSMA Gold Rate Today</h2>
  <p class="hint">The India Bullion &amp; Jewellers Association 24K benchmark
  (national) and the AKGSMA South-India association rate, pre-GST, alongside
  the exchange-traded gold futures quote.</p>
  <div class="ref-tiles">
    <div class="rtile"><div class="k">IBJA 999 Fine · 24K</div>
      <div class="v">{inr(r999)}</div><div class="u">per gram, pre-GST</div></div>
    {akgsma_tile}
    {mcx_tile}
    <div class="rtile prem"><div class="k">Jeweller premium</div>
      <div class="v">{premium_med:+.1f}%</div>
      <div class="u">median vs bullion, today</div></div>
  </div>
</section>'''
        # Premium-over-bullion bars: IBJA 999 is the zero baseline.
        prem = []
        for r in sorted(live, key=lambda x: x["canonical_24k_pre_gst"]):
            p = (r["canonical_24k_pre_gst"] / r999 - 1) * 100
            prem.append((r["brands"]["name"], p,
                         r["canonical_24k_pre_gst"] - r999))
        pmax = max(max(abs(p) for _, p, _ in prem), 0.1)
        bar_rows = []
        for name, p, diff in prem:
            side = "above" if diff >= 0 else "below"
            width = max(min(abs(p) / pmax * 100, 100), 2)
            cls = "pbar-fill" if diff >= 0 else "pbar-fill pbar-neg"
            bar_rows.append(
                f'<div class="pbar-row" title="{name}: {inr(abs(diff))} '
                f'{side} bullion per gram">'
                f'<span class="pbar-name">{name}</span>'
                f'<span class="pbar-track"><span class="{cls}" '
                f'style="width:{width:.1f}%"></span></span>'
                f'<span class="pbar-val">{p:+.1f}%</span></div>')
        bars = "\n".join(bar_rows)
        ibja_section = f'''
<section aria-labelledby="ibjah">
  <p class="eyebrow">Bullion vs Board</p>
  <h2 id="ibjah">Jeweller Premium Over the IBJA Rate</h2>
  <p class="hint">IBJA's 24K bullion reference today is
  <strong>{inr(r999)}/g</strong> (999), pre-GST. Each bar is a brand's
  premium (or discount) per gram of pure gold versus bullion, smallest
  first. Hover a bar for the rupee difference.</p>
  <div class="chartcard pbar-card">
{bars}
  </div>
</section>'''
        ibja_faq = (
            f"The IBJA (India Bullion and Jewellers Association) 24K reference "
            f"rate today is {inr(r999)} per gram for 999 gold, before GST. "
            f"Jewellery brands price on average {premium_med:+.1f}% above the "
            "bullion reference today; the gap reflects each brand's sourcing "
            "and hallmarking premium.")
    else:
        ibja_section = ""
        ibja_tiles = (f'<section class="ibja-ref"><p class="eyebrow">Reference'
                      f'</p><div class="ref-tiles">{akgsma_tile}{mcx_tile}</div>'
                      f'</section>') if (mcx_tile or akgsma_tile) else ""
        ibja_faq = ("The IBJA (India Bullion and Jewellers Association) "
                    "publishes India's twice-daily bullion reference rate. "
                    "Jeweller board rates typically sit slightly above it, "
                    "reflecting sourcing and hallmarking premiums.")

    # ---------------------------------------------------------- table rows
    body_rows = []
    for rank, r in enumerate(
            sorted(live, key=lambda x: x["canonical_24k_pre_gst"]), start=1):
        b = r["brands"]
        lad = ladder(r["canonical_24k_pre_gst"])
        ddiff = r["canonical_24k_pre_gst"] - median24
        if ddiff <= -0.5:
            dcls, dtxt = "delta-low", f"-{inr(abs(ddiff))}"
        elif ddiff >= 0.5:
            dcls, dtxt = "delta-high", f"+{inr(ddiff)}"
        else:
            dcls, dtxt = "delta-par", "at median"
        best = ' <span class="stamp stamp-best">lowest today</span>' \
            if r["brand_id"] == lowest["brand_id"] else ""
        est = ' <span class="stamp stamp-est">indicative</span>' \
            if r.get("method") == "reference-median" else ""
        dom = (b.get("domain") or "").replace("https://", "").split("/")[0]
        logo = (f'<img class="blogo" alt="" loading="lazy" '
                f'src="https://www.google.com/s2/favicons?domain={dom}&amp;sz=64" '
                f'onerror="this.style.visibility=\'hidden\'">') if dom else ""
        states = REGION_MAP.get(b.get("slug") or "")
        data_states = "|".join(states) if states else "all"
        region_badge = (' <span class="stamp stamp-region">Regional</span>'
                        if states else "")
        logo_src = (f"https://www.google.com/s2/favicons?domain={dom}&amp;sz=64"
                    if dom else "")
        body_rows.append(
            f'<tr data-states="{data_states}" data-brand="{b["name"]}" '
            f'data-logo="{logo_src}" data-rank="{rank}">'
            f'<td class="col-rank" data-v="{rank}">{rank}</td>'
            f'<th scope="row">'
            f'<span class="bcell">{logo}'
            f'<span>{b["name"]}{best}{est}{region_badge}</span></span></th>'
            f'<td class="num col-24" data-v="{lad["24K"]:.2f}">{inr(lad["24K"])}</td>'
            f'<td class="num col-22" data-v="{lad["22K"]:.2f}">{inr(lad["22K"])}</td>'
            f'<td class="num col-18" data-v="{lad["18K"]:.2f}">{inr(lad["18K"])}</td>'
            f'<td class="{dcls} col-delta" data-v="{ddiff:.2f}">{dtxt}</td></tr>')

    calc_brands = [{"name": "Market median", "r24": round(median24, 2)}] + [
        {"name": r["brands"]["name"],
         "r24": round(r["canonical_24k_pre_gst"], 2)}
        for r in sorted(live, key=lambda x: x["brands"]["name"])]

    # ------------------------------------------------------------- JSON-LD
    faq = [
        ("What is the gold rate today in India?",
         f"On {display_date}, the market median 24K gold rate across major "
         f"Indian jewellers is {inr(med['24K'])} per gram (pre-GST). The 22K "
         f"rate is {inr(med['22K'])} per gram. Rates are compared across "
         f"{len(live)} leading jewellery brands and updated daily."),
        ("Which jeweller has the lowest gold rate today?",
         f"Today, {lowest['brands']['name']} lists the lowest effective 24K "
         f"gold rate at {inr(ladder(lowest['canonical_24k_pre_gst'])['24K'])} "
         "per gram. Jewellers' rates typically differ by 1-3% because each "
         "brand embeds slightly different premiums in its pricing."),
        ("What is the gold rate today in Hyderabad?",
         f"The gold rate today in Hyderabad closely tracks the national jeweller "
         f"rate. On {display_date}, the median 24K (999) rate is {inr(med['24K'])} "
         f"per gram and 22K (916) is {inr(med['22K'])} per gram, pre-GST. Most "
         f"national chains quote a uniform price across their Hyderabad stores, "
         f"so the {len(live)}-brand comparison on this page applies in Hyderabad."),
        ("What is the gold rate today in Chennai?",
         f"On {display_date}, the gold rate today in Chennai is in line with the "
         f"national median of {inr(med['24K'])} per gram for 24K and "
         f"{inr(med['22K'])} per gram for 22K (pre-GST). Chennai buyers can use "
         f"the comparison board and calculator above to check each jeweller's "
         f"rate before purchase."),
        ("What is the gold rate today in Pune?",
         f"The gold rate today in Pune mirrors the pan-India jeweller rate. As of "
         f"{display_date}, 24K gold is around {inr(med['24K'])} per gram and 22K "
         f"is {inr(med['22K'])} per gram (pre-GST) across the brands compared "
         f"here, which price uniformly across their Pune outlets."),
        ("What is the gold rate today in Mumbai?",
         f"On {display_date}, the gold rate today in Mumbai matches the national "
         f"median of {inr(med['24K'])} per gram (24K) and {inr(med['22K'])} per "
         f"gram (22K), pre-GST. Because leading chains quote one rate across all "
         f"their Mumbai showrooms, this {len(live)}-brand comparison applies in "
         f"Mumbai too."),
        ("What is the IBJA gold rate and why does it differ from jeweller rates?",
         ibja_faq),
        ("Are these gold rates inclusive of GST?",
         "Rates shown are per gram, pre-GST, so brands can be compared on the "
         "same basis. Use the GST switch on the comparison table, or the "
         "calculator, to see prices including 3% GST. Making charges vary by "
         "design and are always extra."),
        ("What is the difference between 24K, 22K and 18K gold?",
         "24K (99.9% pure) is investment-grade gold used for coins and bars. "
         "22K (91.6%) is the standard for traditional Indian jewellery. 18K "
         "(75%) is harder and common in diamond and everyday jewellery. "
         "Purity scales the price: the 22K rate is 91.6% of the pure-gold "
         "rate."),
        ("How often are these rates updated?",
         "Our team updates the rates manually every day. Each brand's figure "
         "is checked against the market before it is published, and "
         "subscribers receive the day's comparison by email."),
    ]
    jsonld = json.dumps([
        {"@context": "https://schema.org", "@type": "WebSite",
         "name": "GoldRates - Daily Gold Rate Comparison India",
         "url": SITE_URL},
        {"@context": "https://schema.org", "@type": "Organization",
         "name": "MyGoldRates.com", "alternateName": "GoldRates",
         "url": SITE_URL, "logo": f"{SITE_URL}/icon-512.png",
         "image": f"{SITE_URL}/og.png",
         "description": "India's gold rate comparison platform - compare today's "
                        "24K, 22K and 18K gold rates across leading jewellers, "
                        "with the IBJA bullion reference, updated daily.",
         "areaServed": {"@type": "Country", "name": "India"},
         "knowsAbout": ["Gold rate", "Gold rate today", "24 carat gold rate",
                        "22K gold rate", "IBJA gold rate", "Gold price India"]},
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [
             {"@type": "ListItem", "position": 1,
              "name": "Gold Rate Today", "item": f"{SITE_URL}/"}]},
        {"@context": "https://schema.org", "@type": "Dataset",
         "name": f"Gold rates across Indian jewellers on {display_date}",
         "description": "Daily 24K, 22K and 18K per-gram gold rates compared "
                        "across major Indian jewellery brands, with the IBJA "
                        "bullion reference and MCX gold futures.",
         "dateModified": now_ist.isoformat(),
         "datePublished": "2026-07-20", "url": SITE_URL,
         "license": f"{SITE_URL}/#terms",
         "isAccessibleForFree": True,
         "keywords": ["gold rate", "gold rate today", "24 carat gold rate",
                      "22K gold rate", "gold price India", "IBJA gold rate",
                      "MCX gold"],
         "distribution": [{"@type": "DataDownload",
                           "encodingFormat": "application/json",
                           "contentUrl": f"{SITE_URL}/rates.json"}],
         "creator": {"@type": "Organization", "name": "MyGoldRates.com",
                     "url": SITE_URL}},
        {"@context": "https://schema.org", "@type": "WebPage",
         "url": SITE_URL, "name": "Gold Rate Today in India",
         "dateModified": now_ist.isoformat(),
         "speakable": {"@type": "SpeakableSpecification",
                       "cssSelector": [".board", "#keyfacts"]},
         "primaryImageOfPage": f"{SITE_URL}/og.png"},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}}
                        for q, a in faq]},
    ])

    faq_html = "\n".join(
        f'<details class="faq"><summary>{q}</summary><p>{a}</p></details>'
        for q, a in faq)

    low_dom = (lowest["brands"].get("domain") or "") \
        .replace("https://", "").replace("http://", "").split("/")[0]
    low_logo = (f' <img src="https://www.google.com/s2/favicons?domain='
                f'{low_dom}&amp;sz=64" alt="" loading="lazy" '
                f'onerror="this.style.display=\'none\'">') if low_dom else ""

    nb = str(len(live))
    seo_content = f"""<section class="seo" aria-labelledby="abouth">
  <p class="eyebrow">About the Tool</p>
  <details class="seofold">
  <summary><h2 id="abouth">Gold Rate Today in India, Compared Every Day</h2></summary>

  <p>Checking the <strong>gold rate today</strong> before you buy can save you
  thousands of rupees on a single piece of jewellery. MyGoldRates.com is India's
  first dedicated <strong>gold rate</strong> comparison platform, built to place
  the <strong>today gold rate</strong> from {nb} of the country's most recognised
  jewellers side by side on one clean page, refreshed every single day. Instead
  of opening a dozen websites or walking store to store, you see the whole market
  at a glance and instantly spot which jeweller is offering the best value.</p>

  <p>Gold is quoted per gram, but the rate you actually pay is rarely identical
  at every store. Two jewellers can advertise the same metal on the same morning
  yet differ by &#8377;50 to &#8377;150 per gram once their margins are added,
  and over a 20-gram purchase that gap alone runs into thousands. By comparing
  the <strong>gold rate</strong> across brands, and against the official IBJA
  bullion benchmark, this tool shows exactly how much premium each jeweller
  charges over pure bullion, so nothing stays hidden.</p>

  <h3>24 carat and 22K gold rate today</h3>
  <p>The <strong>24 carat gold rate today</strong> reflects the purest,
  investment-grade gold, 99.9% fine and also written as 999, and is the figure
  most buyers and investors track. Coins, bars and digital gold are usually
  priced off this 24K rate. The <strong>gold rate today 22k</strong> (916 purity)
  is what the vast majority of Indian jewellery is crafted from, because pure
  gold is too soft to hold intricate designs. We publish 24K, 22K and 18K rates
  together so you can compare like for like, whether you are buying an investment
  coin or a bridal set.</p>

  <h3>Gold rate today in Hyderabad, Chennai, Pune and Mumbai</h3>
  <p>Retail gold prices across India tend to move together, so the
  <strong>gold rate today in Hyderabad</strong>, the
  <strong>gold rate today in Chennai</strong>, the
  <strong>gold rate today in Pune</strong> and the
  <strong>gold rate today in Mumbai</strong> usually sit within a narrow band of
  one another. Most national jewellery chains quote a single, uniform price
  across all their outlets, which means the brand rates listed here apply whether
  you are shopping in Hyderabad, Chennai, Pune, Mumbai or any other major city.
  Local taxes and small city-level adjustments can add minor differences, but the
  underlying <strong>today gold rate</strong> you see on this page is an accurate
  reference wherever you are in India.</p>

  <h3>How to use MyGoldRates.com</h3>
  <p>Start with the comparison board to see the <strong>gold rate today</strong>
  ranked from lowest to highest, then use the built-in calculator to estimate the
  exact cost of your gold by weight, purity and brand, with or without 3% GST.
  Check the IBJA premium section to understand how much each jeweller adds over
  the bullion benchmark, and subscribe to free daily alerts to get the morning's
  comparison delivered straight to your inbox. Every rate is shown per gram,
  before GST and before making charges, so every brand is measured on the same
  honest basis.</p>

  <p>Because the numbers are updated daily and compiled directly from each
  brand's own published prices, you are always looking at a current, real-world
  snapshot rather than a stale estimate. Whether you are planning a wedding
  purchase, buying a gift, or simply tracking the <strong>gold rate</strong> as an
  investor, MyGoldRates.com gives you a clear, up-to-date and unbiased view of
  what India's leading jewellers are charging today, all in one place.</p>
  </details>
</section>"""

    # ------------------------------------------------- markets side drawer
    since = (datetime.now(timezone.utc).date() - timedelta(days=120)).isoformat()
    try:
        hist_rows = sb.table("rates") \
            .select("rate_date, canonical_24k_pre_gst, status") \
            .eq("status", "published").gte("rate_date", since).execute().data
    except Exception as e:
        print("trend: history query failed:", e)
        hist_rows = []
    by_day = {}
    for hr in hist_rows:
        if hr.get("canonical_24k_pre_gst"):
            by_day.setdefault(hr["rate_date"], []) \
                  .append(hr["canonical_24k_pre_gst"])
    trend = sorted((d, statistics.median(v)) for d, v in by_day.items())

    if mcx:
        mcx_rows = ""
        for c in mcx:
            nm = "GOLD (1 kg lot)" if c["symbol"] == "GOLD" \
                else "GOLDM (100 g lot)"
            cls = "up" if c["chg"] >= 0 else "dn"
            mcx_rows += (
                f'<tr><td>{nm}<span class="mex">expiry {c["expiry"]}</span></td>'
                f'<td>{inr(c["ltp"])}</td>'
                f'<td class="{cls}">{c["pchg"]:+.2f}%</td></tr>')
        mcx_block = f'''<h3>MCX Gold Futures</h3>
  <p class="dnote">Exchange-traded gold futures, quoted per 10 g of 995 fine
  gold. Indicative, delayed quotes.</p>
  <table class="dtable"><thead><tr><th>Contract</th><th>Price /10g</th>
  <th>&Delta; day</th></tr></thead><tbody>{mcx_rows}</tbody></table>'''
    else:
        mcx_block = ('<h3>MCX Gold Futures</h3><p class="dnote">The futures '
                     'feed is unavailable right now - check back later '
                     'today.</p>')

    hist_table = "".join(
        f'<tr><td>{datetime.fromisoformat(d).strftime("%d %b %Y")}</td>'
        f'<td>{inr(v)}</td></tr>' for d, v in reversed(trend[-10:]))
    drawer = f'''
<button class="drawer-tab" id="drtab" aria-controls="mdrawer"
  aria-expanded="false">Markets &#9670;</button>
<div class="drawer-ov" id="drov" hidden></div>
<aside class="drawer" id="mdrawer" aria-hidden="true"
  aria-label="Gold markets panel">
  <div class="drawer-head"><h2>Gold Markets</h2>
    <button class="drawer-x" id="drx" aria-label="Close panel">&times;</button>
  </div>
  {ibja_tiles}
  {mcx_block}
  <h3>Gold Rate Trend</h3>
  <p class="dnote">Median 24K jeweller board rate per gram, pre-GST, by day.</p>
  <div class="chartcard">{trend_chart(trend)}</div>
  <table class="dtable"><thead><tr><th>Date</th><th>Median 24K /g</th></tr>
  </thead><tbody>{hist_table}</tbody></table>
  <h3>Spot vs Futures</h3>
  <p class="dnote">MCX futures quote wholesale 995 gold for a future delivery
  date, so they usually sit below retail jeweller board rates, which add
  sourcing and hallmarking premiums. Watching both tells you where retail
  prices are likely headed.</p>
</aside>'''

    calcdrawer = f'''
<button class="drawer-tab drawer-tab2" id="cdtab" aria-controls="cdrawer"
  aria-expanded="false">Calculators &#9672;</button>
<div class="drawer-ov" id="cdov" hidden></div>
<aside class="drawer" id="cdrawer" aria-hidden="true"
  aria-label="Gold calculators panel">
  <div class="drawer-head"><h2>Gold Calculators &#9672;</h2>
    <button class="drawer-x" id="cdx" aria-label="Close panel">&times;</button>
  </div>

  <!-- Jewellery Final Bill Estimator -->
  <div style="background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:20px">
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:12px">
      <div style="font-size:24px">&#129720;</div>
      <div>
        <h3 style="margin:0;font-size:16px">Jewellery Final Bill Estimator</h3>
        <p class="dnote" style="margin:0">Calculate shop billing before you pay: Gold Weight + Making Charge % + 3% GST</p>
      </div>
    </div>

    <div style="display:grid;gap:12px;margin:12px 0">
      <div>
        <label for="bc-karat" style="display:block;font:600 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px">Select Karat / Purity</label>
        <select id="bc-karat" style="width:100%;padding:8px 10px;font:600 14px 'IBM Plex Sans',sans-serif;background:var(--card);border:1px solid var(--line);border-radius:8px;color:var(--ink)">
          <option value="22K" selected>22K Gold (Bridal &amp; Traditional)</option>
          <option value="24K">24K Gold (999 Pure Coin/Bar)</option>
          <option value="18K">18K Gold (Diamond &amp; Gemstone)</option>
          <option value="14K">14K Gold (Daily Wear)</option>
        </select>
      </div>
      <div>
        <label for="bc-weight" style="display:block;font:600 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px">Net Gold Weight (Grams)</label>
        <input type="number" id="bc-weight" value="10" min="0.1" step="0.1" style="width:100%;padding:8px 10px;font:700 15px 'IBM Plex Mono',monospace;background:var(--card);border:1px solid var(--line);border-radius:8px;color:var(--ink)">
      </div>
      <div>
        <label for="bc-making" style="display:block;font:600 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px">Making Charge (%)</label>
        <input type="number" id="bc-making" value="12" min="0" max="40" step="0.5" style="width:100%;padding:8px 10px;font:700 15px 'IBM Plex Mono',monospace;background:var(--card);border:1px solid var(--line);border-radius:8px;color:var(--ink)">
      </div>
    </div>

    <div style="background:linear-gradient(150deg,#1A140A,#0C0904 60%,#1F180B);border:1px solid rgba(224,186,86,.4);border-radius:10px;padding:14px;color:#F0EAD8">
      <div style="font:700 11px/1 'IBM Plex Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:#F4E3A6;margin-bottom:8px;border-bottom:1px solid rgba(224,186,86,.25);padding-bottom:6px">Itemized Billing Breakdown</div>
      <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:12.5px;color:#C4B99A">
        <span>1. Net Gold Cost (<span id="bb-wt-lbl">10g</span> @ <span id="bb-rate-lbl">&#8377;13,265/g</span>):</span>
        <strong id="bb-gold-tot" style="font-family:'IBM Plex Mono',monospace;color:#FFFDF4">&#8377;1,32,650</strong>
      </div>
      <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:12.5px;color:#C4B99A">
        <span>2. Making Charges (<span id="bb-m-pct">12%</span>):</span>
        <strong id="bb-making-tot" style="font-family:'IBM Plex Mono',monospace;color:#FFFDF4">&#8377;15,918</strong>
      </div>
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:12.5px;color:#C4B99A">
        <span>3. GST (3% on Gold + Making):</span>
        <strong id="bb-gst-tot" style="font-family:'IBM Plex Mono',monospace;color:#FFFDF4">&#8377;4,457</strong>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding-top:8px;border-top:1px dashed rgba(224,186,86,.3)">
        <span style="font-size:13px;font-weight:600;color:#F4E3A6">Estimated Final Billed Amount:</span>
        <strong id="bb-grand-tot" style="font-family:'IBM Plex Mono',monospace;font-size:19px;color:#F4E3A6">&#8377;1,53,025</strong>
      </div>
    </div>
  </div>

  <h3>Price Calculator</h3>
  <p class="dnote">Weight, purity and brand - the price updates as you type.
  Making charges vary by design and are not included.</p>
  <div class="calc calc-drawer">
    <div class="calc-fields">
      <div class="field"><label for="c-w">Weight in grams</label>
        <div class="quick-weights" role="group" aria-label="Quick weights">
          <button type="button" class="qw-pill" data-w="1">1g</button>
          <button type="button" class="qw-pill" data-w="8">8g (Sovereign)</button>
          <button type="button" class="qw-pill active" data-w="10">10g</button>
          <button type="button" class="qw-pill" data-w="50">50g</button>
          <button type="button" class="qw-pill" data-w="100">100g</button>
          <button type="button" class="qw-pill" data-w="11.66">1 Tola</button>
        </div>
        <input id="c-w" type="number" inputmode="decimal" min="0.1" step="0.1" value="10"></div>
      <div class="field"><label id="c-p-label">Purity</label>
        <div class="seg" role="group" aria-labelledby="c-p-label">
          <button data-p="24K" aria-pressed="true">24K</button>
          <button data-p="22K" aria-pressed="false">22K</button>
          <button data-p="18K" aria-pressed="false">18K</button>
          <button data-p="14K" aria-pressed="false">14K</button>
        </div></div>
      <div class="field"><label for="c-b">Brand rate</label>
        <select id="c-b"></select></div>
      <div class="field"><label id="c-g-label">GST</label>
        <div class="seg" role="group" aria-labelledby="c-g-label">
          <button data-g="0" aria-pressed="true">Excl. GST</button>
          <button data-g="1" aria-pressed="false">Incl. 3% GST</button>
        </div></div>
    </div>
    <div class="calc-out" aria-live="polite">
      <div class="k" id="c-title">10 g &middot; 24K</div>
      <div class="v" id="c-total">-</div>
      <div class="sub" id="c-basis">-</div>
      <div class="split">
        <div><span>Rate per gram</span><span class="amt" id="c-rate">-</span></div>
        <div><span>Gold value</span><span class="amt" id="c-gold">-</span></div>
        <div><span>GST (3%)</span><span class="amt" id="c-gst">-</span></div>
      </div>
    </div>
  </div>
  <h3>Gold Calculator</h3>
  <p class="dnote">Fix your budget and see how many grams you can take home
  at each jeweller. Enter making charge from their quote &mdash; every jeweller
  charges differently.</p>
  <div class="calc calc-drawer">
    <div class="calc-fields">
      <div class="field"><label for="gc-b">Your budget (&#8377;)</label>
        <div class="quick-weights" role="group" aria-label="Quick budgets">
          <button type="button" class="qw-pill" data-gb="25000">&#8377;25k</button>
          <button type="button" class="qw-pill" data-gb="50000">&#8377;50k</button>
          <button type="button" class="qw-pill active" data-gb="100000">&#8377;1L</button>
          <button type="button" class="qw-pill" data-gb="200000">&#8377;2L</button>
          <button type="button" class="qw-pill" data-gb="500000">&#8377;5L</button>
          <button type="button" class="qw-pill" data-gb="1000000">&#8377;10L</button>
        </div>
        <input id="gc-b" type="number" inputmode="numeric" min="1000" step="500" value="100000"></div>
      <div class="field"><label id="gc-p-label">Purity</label>
        <div class="seg" role="group" aria-labelledby="gc-p-label">
          <button data-gp="24K" aria-pressed="true">24K</button>
          <button data-gp="22K" aria-pressed="false">22K</button>
          <button data-gp="18K" aria-pressed="false">18K</button>
          <button data-gp="14K" aria-pressed="false">14K</button>
        </div></div>
      <div class="field"><label for="gc-brand">Brand rate</label>
        <select id="gc-brand"></select></div>
      <div class="field" id="gc-custom-row" hidden>
        <label for="gc-custom">Your jeweller's <span id="gc-custom-k">24K</span> rate (&#8377;/g)</label>
        <input id="gc-custom" type="number" inputmode="decimal" min="0" step="1" value="14000">
        <div style="margin-top:6px;font-size:11px;color:#8E9A8C">Rate is treated as the price for your selected purity.</div>
      </div>
      <div class="field"><label for="gc-m">Making charge (%)</label>
        <input id="gc-m" type="number" inputmode="decimal" min="0" max="60" step="0.5" value="18"></div>
      <div class="field"><label id="gc-g-label">GST</label>
        <div class="seg" role="group" aria-labelledby="gc-g-label">
          <button data-gg="1" aria-pressed="true">Incl. 3% GST</button>
          <button data-gg="0" aria-pressed="false">Excl. GST</button>
        </div></div>
    </div>
    <div class="calc-out" aria-live="polite">
      <div class="k" id="gc-title">&#8377;1,00,000 &middot; 24K</div>
      <div class="v" id="gc-grams">-</div>
      <div class="sub" id="gc-basis">-</div>
      <div class="split">
        <div><span>Rate per gram</span><span class="amt" id="gc-rate">-</span></div>
        <div><span>Gold value</span><span class="amt" id="gc-gold">-</span></div>
        <div><span>Making charge</span><span class="amt" id="gc-mc">-</span></div>
        <div><span>GST</span><span class="amt" id="gc-gst">-</span></div>
      </div>
      <div style="margin-top:12px;padding-top:10px;border-top:1px dashed rgba(224,186,86,.2);font-size:12px;color:#8E9A8C;text-align:center">
        <a href="{SITE_URL}/budget-gold-calculator" style="color:#E0BA56;text-decoration:none">Compare across every jeweller &rarr;</a>
      </div>
    </div>
  </div>

  <h3>More calculators</h3>
  <a class="toolcard" href="{SITE_URL}/gold-loan-calculator"><b>Gold Loan
    Calculator</b><span>Eligibility &amp; EMI</span></a>
  <a class="toolcard" href="{SITE_URL}/gold-sip-calculator"><b>Gold SIP
    Calculator</b><span>Future value &amp; grams</span></a>
  <a class="toolcard" href="{SITE_URL}/making-charges-calculator"><b>Making
    Charges</b><span>Final billed price with GST</span></a>
</aside>'''

    coindrawer = f'''
<button class="drawer-tab drawer-tab3" id="coindtab" aria-controls="coindrawer"
  aria-expanded="false">Gold Coins &#129689;</button>
<div class="drawer-ov" id="coindov" hidden></div>
<aside class="drawer" id="coindrawer" aria-hidden="true"
  aria-label="Gold coins panel">
  <div class="drawer-head"><h2>24K Minted Gold Coins &#129689;</h2>
    <button class="drawer-x" id="coindx" aria-label="Close panel">&times;</button>
  </div>
  <p class="dnote">Compare 24K Swiss-Standard 999.9 &amp; 999 fine gold coins and bullion bars across certified refiners &amp; jewellers, with exact lowest making charges marked.</p>

  <div style="display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 16px">
    <span style="font-size:11px;color:var(--ink-3);align-self:center">Weight:</span>
    <button type="button" class="coin-pill active" data-wt="1" style="font:500 11px/1 'IBM Plex Mono',monospace;background:var(--gold);color:#0C0904;border:1px solid var(--gold);border-radius:999px;padding:5px 10px;cursor:pointer">1g</button>
    <button type="button" class="coin-pill" data-wt="2" style="font:500 11px/1 'IBM Plex Mono',monospace;background:none;color:var(--ink-2);border:1px solid var(--line);border-radius:999px;padding:5px 10px;cursor:pointer">2g</button>
    <button type="button" class="coin-pill" data-wt="5" style="font:500 11px/1 'IBM Plex Mono',monospace;background:none;color:var(--ink-2);border:1px solid var(--line);border-radius:999px;padding:5px 10px;cursor:pointer">5g</button>
    <button type="button" class="coin-pill" data-wt="8" style="font:500 11px/1 'IBM Plex Mono',monospace;background:none;color:var(--ink-2);border:1px solid var(--line);border-radius:999px;padding:5px 10px;cursor:pointer">8g</button>
    <button type="button" class="coin-pill" data-wt="10" style="font:500 11px/1 'IBM Plex Mono',monospace;background:none;color:var(--ink-2);border:1px solid var(--line);border-radius:999px;padding:5px 10px;cursor:pointer">10g</button>
    <button type="button" class="coin-pill" data-wt="50" style="font:500 11px/1 'IBM Plex Mono',monospace;background:none;color:var(--ink-2);border:1px solid var(--line);border-radius:999px;padding:5px 10px;cursor:pointer">50g</button>
  </div>

  <div style="display:grid;gap:14px">
    <!-- MMTC-PAMP -->
    <div style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <strong style="font-size:14px">MMTC-PAMP 24K</strong>
        <span style="font:700 10px 'IBM Plex Mono',monospace;color:#5BBB93;background:rgba(30,92,70,.18);border:1px solid rgba(91,187,147,.35);padding:2px 7px;border-radius:999px">999.9 Pure</span>
      </div>
      <div style="font-size:12px;color:var(--gold);font-weight:700;margin-bottom:4px">⚡ Lowest Making Charge: 2.5% <span class="rank-badge rank-1" style="font-size:9px;padding:2px 5px">#1 LOWEST</span></div>
      <div style="font-size:11.5px;color:var(--ink-3);margin-bottom:8px">Swiss Assay Certification &amp; CertiPAMP Packaging</div>
      <div id="cp-mmtc" style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:var(--gold);margin-bottom:6px">&#8377;—</div>
      <a href="https://www.mmtcpamp.com/shop" target="_blank" rel="noopener nofollow" class="btn btn-gold" style="display:block;text-align:center;font-size:11.5px;padding:7px 10px;margin-top:6px">Buy MMTC-PAMP 24K &rarr;</a>
    </div>

    <!-- Kalyan Jewellers / Candere -->
    <div style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <strong style="font-size:14px">Kalyan Jewellers / Candere</strong>
        <span style="font:700 10px 'IBM Plex Mono',monospace;color:#5BBB93;background:rgba(30,92,70,.18);border:1px solid rgba(91,187,147,.35);padding:2px 7px;border-radius:999px">999 Pure</span>
      </div>
      <div style="font-size:12px;color:var(--gold);font-weight:700;margin-bottom:4px">⚡ Lowest Making Charge: 3.0% <span class="rank-badge rank-2" style="font-size:9px;padding:2px 5px">#2</span></div>
      <div style="font-size:11.5px;color:var(--ink-3);margin-bottom:8px">BIS Hallmarked 999 Pure &amp; 100% Transparency</div>
      <div id="cp-kalyan" style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:var(--gold);margin-bottom:6px">&#8377;—</div>
      <a href="https://www.candere.com/gifts/gold-coins.html" target="_blank" rel="noopener nofollow" class="btn btn-gold" style="display:block;text-align:center;font-size:11.5px;padding:7px 10px;margin-top:6px">Buy Kalyan 24K &rarr;</a>
    </div>

    <!-- Malabar Gold & Diamonds -->
    <div style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <strong style="font-size:14px">Malabar Gold &amp; Diamonds</strong>
        <span style="font:700 10px 'IBM Plex Mono',monospace;color:#5BBB93;background:rgba(30,92,70,.18);border:1px solid rgba(91,187,147,.35);padding:2px 7px;border-radius:999px">999 Pure</span>
      </div>
      <div style="font-size:12px;color:var(--gold);font-weight:700;margin-bottom:4px">⚡ Lowest Making Charge: 3.2% <span class="rank-badge rank-3" style="font-size:9px;padding:2px 5px">#3</span></div>
      <div style="font-size:11.5px;color:var(--ink-3);margin-bottom:8px">Tested Purity &amp; Free Transit Insurance Coverage</div>
      <div id="cp-malabar" style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:var(--gold);margin-bottom:6px">&#8377;—</div>
      <a href="https://www.malabargoldanddiamonds.com/in/pan-india/en/product-list.html?search=Gold%20Bars%20%26%20Coins" target="_blank" rel="noopener nofollow" class="btn btn-gold" style="display:block;text-align:center;font-size:11.5px;padding:7px 10px;margin-top:6px">Buy Malabar 24K &rarr;</a>
    </div>

    <!-- Senco Gold -->
    <div style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <strong style="font-size:14px">Senco Gold &amp; Diamonds</strong>
        <span style="font:700 10px 'IBM Plex Mono',monospace;color:#5BBB93;background:rgba(30,92,70,.18);border:1px solid rgba(91,187,147,.35);padding:2px 7px;border-radius:999px">999 Pure</span>
      </div>
      <div style="font-size:12px;color:var(--gold);font-weight:700;margin-bottom:4px">⚡ Lowest Making Charge: 3.5%</div>
      <div style="font-size:11.5px;color:var(--ink-3);margin-bottom:8px">Traditional BIS Hallmarked &amp; Sealed Packaging</div>
      <div id="cp-senco" style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:var(--gold);margin-bottom:6px">&#8377;—</div>
      <a href="https://sencogoldanddiamonds.com/products/category/gold-coins" target="_blank" rel="noopener nofollow" class="btn btn-gold" style="display:block;text-align:center;font-size:11.5px;padding:7px 10px;margin-top:6px">Buy Senco 24K &rarr;</a>
    </div>

    <!-- Joyalukkas -->
    <div style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <strong style="font-size:14px">Joyalukkas</strong>
        <span style="font:700 10px 'IBM Plex Mono',monospace;color:#5BBB93;background:rgba(30,92,70,.18);border:1px solid rgba(91,187,147,.35);padding:2px 7px;border-radius:999px">999 Pure</span>
      </div>
      <div style="font-size:12px;color:var(--gold);font-weight:700;margin-bottom:4px">⚡ Lowest Making Charge: 3.8%</div>
      <div style="font-size:11.5px;color:var(--ink-3);margin-bottom:8px">Assayer Certified 999 Pure &amp; Sealed Tamper-Proof</div>
      <div id="cp-joyalukkas" style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:var(--gold);margin-bottom:6px">&#8377;—</div>
      <a href="https://www.joyalukkas.in/search.html?query=gold+coin&amp;page=1" target="_blank" rel="noopener nofollow" class="btn btn-gold" style="display:block;text-align:center;font-size:11.5px;padding:7px 10px;margin-top:6px">Buy Joyalukkas 24K &rarr;</a>
    </div>

    <!-- Tanishq -->
    <div style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <strong style="font-size:14px">Tanishq (Tata Product)</strong>
        <span style="font:700 10px 'IBM Plex Mono',monospace;color:#5BBB93;background:rgba(30,92,70,.18);border:1px solid rgba(91,187,147,.35);padding:2px 7px;border-radius:999px">999 Pure</span>
      </div>
      <div style="font-size:12px;color:var(--gold);font-weight:700;margin-bottom:4px">⚡ Lowest Making Charge: 4.0%</div>
      <div style="font-size:11.5px;color:var(--ink-3);margin-bottom:8px">Tata Trust Stamp &amp; Buyback Guarantee</div>
      <div id="cp-tanishq" style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;color:var(--gold);margin-bottom:6px">&#8377;—</div>
      <a href="https://www.tanishq.co.in/search?search-button=&amp;q=gold+coins&amp;lang=en_IN" target="_blank" rel="noopener nofollow" class="btn btn-gold" style="display:block;text-align:center;font-size:11.5px;padding:7px 10px;margin-top:6px">Buy Tanishq 24K &rarr;</a>
    </div>
  </div>
</aside>'''

    # Google sign-in: dormant until the GOOGLE_CLIENT_ID secret is set.
    gclient = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    analytics_token = os.environ.get("ANALYTICS_TOKEN", "").strip()
    gsi = ('<script src="https://accounts.google.com/gsi/client" async defer>'
           '</script>') if gclient else ""

    sig_ver = hashlib.md5(SIGNUP_JS.encode()).hexdigest()[:8]
    gate_html = GATE_HTML if gclient else ""
    gate_js   = GATE_JS   if gclient else ""
    common = dict(site_url=SITE_URL, date=display_date, time=display_time,
                  iso_now=now_ist.isoformat(), year=str(now_ist.year),
                  base_css=BASE_CSS, ads_head=ads_head,
                  gclient=gclient, gsi=gsi, google_btn="",
                  sig_ver=sig_ver, nav=NAV,
                  supabase_url=supabase_url, anon_key=anon_key,
                  gate_css=GATE_CSS if gclient else "",
                  gate_html=gate_html, gate_js=gate_js)
    def city_cloud(current_slug=None):
        parts = []
        for nm in LOCATIONS:
            sl = loc_slug(nm)
            cur = ' aria-current="page"' if sl == current_slug else ""
            parts.append(
                f'<a href="gold-rate-today-in-{sl}"{cur}>{nm}</a>')
        return "".join(parts)

    low_g = inr(ladder(lowest["canonical_24k_pre_gst"])["24K"])

    def local_intro(nm):
        """Enriched, unique per-city body so city pages have genuine local value."""
        if nm == "India":
            return ""
        data = CITY_ENRICHMENT_DATA.get(nm, {})
        hubs_info = f'<p><strong>Key Shopping Hubs in {nm}:</strong> {data["hubs"]}.</p>' if data.get("hubs") else ""
        brands_info = f'<p><strong>Featured Regional & National Jewellers in {nm}:</strong> {", ".join(data["regional_brands"])} and leading national brands.</p>' if data.get("regional_brands") else ""
        custom_desc = data.get("intro", f"Gold rates in {nm} follow national board rates across major jewellers. Compare live 24K, 22K, and 18K per-gram prices pre-GST below.")
        
        return (
            f'<section class="seo"><h2>Gold Rate Today in {nm} - Market Overview & Shopping Hubs</h2>'
            f'<p>{custom_desc}</p>'
            f'<p>Today the live median gold rate in <strong>{nm}</strong> is '
            f'<strong>{inr(med["24K"])} per gram for 24K (999 purity)</strong> and '
            f'<strong>{inr(med["22K"])} per gram for 22K (916 purity)</strong>, pre-GST. '
            f'Currently, <strong>{lowest["brands"]["name"]}</strong> offers the lowest 24K rate at '
            f'<strong>{low_g} per gram</strong>.</p>'
            f'{hubs_info}'
            f'{brands_info}'
            f'<p>Before buying gold in {nm}, use our <a href="{SITE_URL}/making-charges-calculator.html">making charges calculator</a> '
            f'to estimate total billed costs with 3% GST, or read our <a href="{SITE_URL}/learn/22k-vs-24k-gold">22K vs 24K guide</a>. '
            f'You can also <a href="{SITE_URL}/inquiry.html">subscribe to free daily {nm} rate alerts</a>.</p>'
            f'</section>')


    tvars = dict(
        n_brands=str(len(live)),
        med24=inr(med["24K"]), med22=inr(med["22K"]), med18=inr(med["18K"]),
        low24=inr(ladder(lowest["canonical_24k_pre_gst"])["24K"]),
        low22=inr(ladder(lowest["canonical_24k_pre_gst"])["22K"]),
        low18=inr(ladder(lowest["canonical_24k_pre_gst"])["18K"]),
        low24_raw=f"{ladder(lowest['canonical_24k_pre_gst'])['24K']:,.0f}",
        low24_num=f"{ladder(lowest['canonical_24k_pre_gst'])['24K']:.0f}",
        low_brand=lowest["brands"]["name"],
        # Per-gram 24K spread between the priciest and cheapest brand on the
        # board today. Powers the "Save up to Rs N/g" tag in the hero, which
        # used to be a hard-coded 128 - meaningless when the actual gap moved.
        spread24=inr(round(ladder(highest['canonical_24k_pre_gst'])['24K']
                            - ladder(lowest['canonical_24k_pre_gst'])['24K'])),
        high_brand=highest["brands"]["name"],
        low_logo=low_logo,
        ibja_tiles=ibja_tiles, ibja_section=ibja_section, ads_unit=ads_unit,
        calc_brands=json.dumps(calc_brands),
        rows="\n".join(body_rows), faq=faq_html, jsonld=jsonld,
        seo_content=seo_content, drawer=drawer, calcdrawer=calcdrawer,
        coindrawer=coindrawer, news_home=news_home, **common)
    html = TEMPLATE.substitute(
        where="in India", where_note="", local_intro="",
        canonical_url=f"{SITE_URL}/", city_links=city_cloud(), **tvars)
    inquiry = INQUIRY_TEMPLATE.substitute(**common)
    unsub = UNSUB_TEMPLATE.substitute(**common)

    os.makedirs("docs", exist_ok=True)
    build_og_image()
    build_favicons()
    build_email_logo()
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("docs/signup.js", "w", encoding="utf-8") as f:
        f.write(SIGNUP_JS)

    # ---- programmatic city/state pages (same board, local landing page) ----
    for nm in LOCATIONS:
        sl = loc_slug(nm)
        note = (f" Rates shown apply across {nm} - national jewellery chains "
                f"quote the same board price in {nm} as everywhere else in "
                "India.")
        page = TEMPLATE.substitute(
            where=f"in {nm}", where_note=note, local_intro=local_intro(nm),
            canonical_url=f"{SITE_URL}/gold-rate-today-in-{sl}",
            city_links=city_cloud(sl), **tvars)
        with open(f"docs/gold-rate-today-in-{sl}.html", "w",
                  encoding="utf-8") as f:
            f.write(page)
    print(f"city pages: wrote {len(LOCATIONS)}")
    with open("docs/inquiry.html", "w", encoding="utf-8") as f:
        f.write(inquiry)
    with open("docs/unsubscribe.html", "w", encoding="utf-8") as f:
        f.write(unsub)

    # ---- static content pages (About / Contact / Privacy) ----
    def write_page(slug, title, desc, heading, body):
        with open(f"docs/{slug}.html", "w", encoding="utf-8") as fp:
            fp.write(PAGE_TEMPLATE.substitute(
                title=title, desc=desc, heading=heading, body=body,
                canonical=f"{SITE_URL}/{slug}", **common))

    write_page(
        "about",
        "About GoldRates - Daily Gold Rate Comparison India",
        "About GoldRates: why we compare daily 24K, 22K and 18K gold rates "
        "across India's leading jewellers alongside the IBJA bullion reference.",
        "About GoldRates",
        f"""
  <p>GoldRates is an independent website that helps people in India compare
  today's gold rates across the country's leading jewellery brands, all on one
  page and on the same basis.</p>
  <h2>What we do</h2>
  <p>Every day we publish the 24K, 22K and 18K gold rate for {len(live)} major
  jewellers, normalised to a per-gram, pre-GST figure so you can compare them
  fairly. Alongside that we show the <strong>IBJA</strong> (India Bullion and
  Jewellers Association) bullion reference, so you can see how far each
  jeweller prices above the wholesale benchmark.</p>
  <h2>Why we built it</h2>
  <p>Gold pricing is confusing: every jeweller quotes a slightly different rate,
  making charges vary, and GST is added on top. A buyer rarely gets to compare
  before walking into a store. GoldRates puts the numbers side by side so you
  can make an informed decision and know roughly what your gold should cost
  before you buy.</p>
  <h2>How to use it</h2>
  <p>Check the comparison table to see who's cheapest today, use the price
  calculator to estimate the cost of a specific weight and purity, and
  <a href="{SITE_URL}/inquiry.html">subscribe</a> to get the day's comparison
  by email each morning.</p>
  <h2>A note on the numbers</h2>
  <p>Rates shown are indicative and pre-GST, compiled from each brand's own
  published prices and updated daily. Making charges are extra and vary by
  design. Always confirm the billed rate with the jeweller before purchase.
  GoldRates is not affiliated with any jeweller and does not provide investment
  advice.</p>
  <p>Questions? <a href="{SITE_URL}/contact.html">Get in touch</a>.</p>""")

    write_page(
        "contact",
        "Contact GoldRates",
        "Contact GoldRates - questions, feedback or corrections about our daily "
        "gold rate comparison for India.",
        "Contact Us",
        f"""
  <p>We'd love to hear from you &mdash; whether you have questions, feedback, a rate
  correction, a jeweller partnership enquiry, or a data-privacy request.</p>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:24px" class="grid2">
    <div style="background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px">
      <h2 style="margin-top:0;font-size:20px">Send Us a Message</h2>
      <p style="font-size:13.5px;color:var(--ink-3);margin-bottom:16px">Fill out this form to send a message directly to <strong>{CONTACT_EMAIL}</strong>.</p>

      <form id="contact-form" action="https://formsubmit.co/{CONTACT_EMAIL}" method="POST" style="display:flex;flex-direction:column;gap:14px">
        <input type="hidden" name="_subject" value="New Inquiry from MyGoldRates Contact Page">
        <input type="hidden" name="_template" value="table">
        <input type="hidden" name="_captcha" value="false">
        <div class="hp" style="display:none"><input name="_honey" tabindex="-1" autocomplete="off"></div>

        <div>
          <label for="c-name" style="display:block;font:500 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px">Your Name *</label>
          <input type="text" id="c-name" name="name" required style="width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--ink)">
        </div>

        <div>
          <label for="c-email" style="display:block;font:500 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px">Your Email *</label>
          <input type="email" id="c-email" name="email" required style="width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--ink)">
        </div>

        <div>
          <label for="c-phone" style="display:block;font:500 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px">Phone Number (Optional)</label>
          <input type="tel" id="c-phone" name="phone" placeholder="+91 98765 43210" style="width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--ink)">
        </div>

        <div>
          <label for="c-subject" style="display:block;font:500 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px">Subject</label>
          <select id="c-subject" name="subject" style="width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--ink)">
            <option>General Inquiry</option>
            <option>Rate Correction / Data Feedback</option>
            <option>Jeweller Listing / Partnership</option>
            <option>Privacy Request</option>
          </select>
        </div>

        <div>
          <label for="c-msg" style="display:block;font:500 11px/1.4 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px">Your Message *</label>
          <textarea id="c-msg" name="message" rows="5" required style="width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--ink);resize:vertical"></textarea>
        </div>

        <button type="submit" id="c-submit" class="btn btn-gold" style="padding:12px;font-size:14px;font-weight:600;margin-top:4px">Send Message to Email</button>
        <div id="c-status" style="display:none;padding:12px;border-radius:8px;font-size:13.5px;margin-top:10px"></div>
      </form>
    </div>

    <div>
      <h2 style="margin-top:0">Direct Contact Information</h2>
      <p style="margin-bottom:12px">You can also write to us directly using your email client:</p>
      <div style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:24px">
        <strong style="font-size:11px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.1em;font-family:'IBM Plex Mono',monospace">Official Email Address</strong><br>
        <a href="mailto:{CONTACT_EMAIL}" style="font-size:19px;font-weight:600;color:var(--gold);display:inline-block;margin-top:6px">{CONTACT_EMAIL}</a>
        <p style="font-size:12.5px;color:var(--ink-3);margin:8px 0 0">We aim to respond to all inquiries within 24-48 business hours.</p>
      </div>

      <h2>Daily Gold Rate Alerts</h2>
      <p>To receive the daily gold rate comparison directly in your inbox every morning, <a href="{SITE_URL}/inquiry.html">subscribe to daily email alerts here</a>.</p>

      <h2>Privacy &amp; Data Rights</h2>
      <p>To request access to or removal of your personal information, email us at <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> or read our <a href="{SITE_URL}/privacy.html">Privacy Policy</a>.</p>
    </div>
  </div>

  <script>
  (function(){{
    var cForm = document.getElementById('contact-form');
    if (cForm) {{
      cForm.addEventListener('submit', function(e) {{
        e.preventDefault();
        var btn = document.getElementById('c-submit');
        var status = document.getElementById('c-status');
        if (btn) {{ btn.disabled = true; btn.textContent = 'Sending Message...'; }}
        var data = new FormData(cForm);
        fetch('https://formsubmit.co/ajax/{CONTACT_EMAIL}', {{
          method: 'POST',
          headers: {{ 'Accept': 'application/json' }},
          body: data
        }}).then(function(res) {{
          if (res.ok) {{
            cForm.reset();
            if (status) {{
              status.style.display = 'block';
              status.style.background = 'color-mix(in srgb, var(--emerald) 15%, transparent)';
              status.style.color = 'var(--emerald)';
              status.style.border = '1px solid var(--emerald)';
              status.textContent = 'Thank you! Your message has been sent to {CONTACT_EMAIL}.';
            }}
            if (btn) {{ btn.disabled = false; btn.textContent = 'Message Sent ✓'; }}
          }} else {{
            throw new Error('Failed');
          }}
        }}).catch(function() {{
          if (status) {{
            status.style.display = 'block';
            status.style.background = 'color-mix(in srgb, var(--warm) 15%, transparent)';
            status.style.color = 'var(--warm)';
            status.style.border = '1px solid var(--warm)';
            status.textContent = 'Could not send automatically. Please email {CONTACT_EMAIL} directly.';
          }}
          if (btn) {{ btn.disabled = false; btn.textContent = 'Send Message to Email'; }}
        }});
      }});
    }}
  }})();
  </script>""")

    write_page(
        "terms",
        "Terms of Service - MyGoldRates",
        "Terms of Service, Disclaimer and User Conditions for MyGoldRates.com gold rate comparison platform.",
        "Terms of Service",
        f"""
  <p>Welcome to <strong>MyGoldRates.com</strong> ("GoldRates", "we", "us", "our"). By accessing or using this website, you agree to comply with and be bound by the following Terms of Service.</p>
  
  <h2>1. Informational &amp; Non-Financial Advice Disclaimer</h2>
  <p>All data, gold rates, calculative results, and market benchmarks presented on MyGoldRates.com are provided strictly for <strong>informational and comparative reference only</strong>. We do not provide financial, investment, tax, or legal advice.</p>
  <p>Gold prices change continuously based on market dynamics. While we compile published rates from verified sources daily, we do not guarantee real-time accuracy or specific jeweller store pricing. Always confirm billed rates directly with authorized jewellers before making purchasing or investment decisions.</p>
  
  <h2>2. Accuracy of Data &amp; Jeweller Quotes</h2>
  <p>Board rates displayed on this platform are compiled from public jeweller quotes, industry association rates (such as IBJA), and market feeds. GoldRates is an independent comparison platform and is not affiliated with, endorsed by, or sponsored by any listed jewellery brand unless explicitly stated.</p>
  
  <h2>3. Acceptable Use &amp; Intellectual Property</h2>
  <p>The layout, design, comparison tools, calculators, and compiled datasets on MyGoldRates.com are protected by copyright and intellectual property laws. You may use this website for personal, non-commercial purposes. Automated scraping, data extraction, or redistribution of our compiled data without explicit written consent is strictly prohibited.</p>
  
  <h2>4. Third-Party Advertising &amp; Cookies</h2>
  <p>We work with third-party advertising partners, including <strong>Google AdSense</strong>, to serve advertisements when you visit our website. These partners may use cookies and web beacons to serve ads based on your visit history. For more information, please see our <a href="{SITE_URL}/privacy.html">Privacy Policy</a>.</p>
  
  <h2>5. Limitation of Liability</h2>
  <p>In no event shall GoldRates, its owners, or operators be liable for any direct, indirect, incidental, or consequential damages resulting from your reliance on information or tools provided on this website.</p>
  
  <h2>6. Contact &amp; Questions</h2>
  <p>For questions regarding these Terms of Service or editorial inquiries, please email us at <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>""")

    write_page(
        "privacy",
        "Privacy Policy - GoldRates",
        "How GoldRates collects, uses and protects your personal information, "
        "including cookies and advertising.",
        "Privacy Policy",
        f"""
  <p>This policy explains what information GoldRates ("we", "us") collects when
  you use <a href="{SITE_URL}/">mygoldrates.com</a>, how we use it, and the
  choices you have. Please also review our <a href="{SITE_URL}/terms.html">Terms of Service</a>.</p>
  <h2>Information you give us</h2>
  <p>If you subscribe to daily rate alerts, we collect the details you enter:
  your name, email address, phone number and location (country, state, city and
  PIN/ZIP code). We use these only to send you the daily gold-rate email and to
  respond to you.</p>
  <h2>Information collected automatically</h2>
  <p>Like most websites we collect basic, non-identifying usage data such as an
  anonymous visit count and standard server/CDN logs (for security and
  performance). We also use privacy-respecting analytics to understand overall
  traffic.</p>
  <h2>Cookies and advertising</h2>
  <p>We display ads served by Google, using
  <strong>Google AdSense</strong>. Third-party vendors, including Google, use
  cookies to serve ads based on your prior visits to this and other websites.
  Google's use of advertising cookies enables it and its partners to serve ads
  to you based on your visits. You can opt out of personalised advertising by
  visiting <a href="https://www.google.com/settings/ads" rel="nofollow">Google
  Ads Settings</a>, or opt out of some third-party vendors at
  <a href="https://www.aboutads.info/choices/" rel="nofollow">aboutads.info</a>.</p>
  <h2>Who we share data with</h2>
  <p>We do not sell your personal information. We share it only with the service
  providers that run this site: <strong>Supabase</strong> (secure data
  storage), <strong>Resend</strong> (email delivery), <strong>Cloudflare</strong>
  (hosting and security) and <strong>Google AdSense</strong> (advertising).
  Each processes data on our behalf under its own terms.</p>
  <h2>Your choices and rights</h2>
  <ul>
    <li>Unsubscribe from emails any time via the link in every email.</li>
    <li>Request a copy or deletion of your data by emailing
        <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</li>
    <li>Control ad personalisation via the links above.</li>
  </ul>
  <h2>Data retention &amp; security</h2>
  <p>We keep subscriber details only while you remain subscribed; unsubscribing
  removes your record. Data is stored with reputable providers using
  industry-standard security.</p>
  <h2>Children</h2>
  <p>This site is not directed at children under 18 and we do not knowingly
  collect their data.</p>
  <h2>Changes</h2>
  <p>We may update this policy; the "last updated" date above reflects the
  latest version.</p>
  <h2>Contact</h2>
  <p>Questions about this policy?
  <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>""")


    # ================= content pages: calculators / news / learn =========
    extra_urls = []          # (loc, changefreq, priority) added to sitemap

    def render_content(slug, title, desc, body, extra_js="", jsonld_block="",
                        robots="index, follow, max-image-preview:large"):
        path = f"docs/{slug}.html"
        d = os.path.dirname(path)
        if d and d != "docs":
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(CONTENT_TEMPLATE.substitute(
                title=title, desc=desc, canonical=f"{SITE_URL}/{slug}",
                body=body, extra_js=extra_js, jsonld_block=jsonld_block,
                robots=robots, **common))

    rate24 = round(median24, 2)
    rate_str = inr(med["24K"])

    def crumbs(*items):
        parts = [f'<a href="{SITE_URL}/">Home</a>']
        for label, href in items:
            parts.append(f'<a href="{href}">{label}</a>' if href else label)
        return '<p class="crumbs">' + ' &rsaquo; '.join(parts) + '</p>'

    # ---- Calculators hub ----
    tools = [
        ("budget-gold-calculator", "Gold for My Budget",
         "Fix a rupee amount and see grams you'd get from each jeweller "
         "(and your own quote)."),
        ("gold-loan-calculator", "Gold Loan Calculator",
         "Check how much loan your gold can fetch and the monthly EMI."),
        ("gold-sip-calculator", "Gold SIP Calculator",
         "Project the future value of a monthly gold investment plan."),
        ("making-charges-calculator", "Making Charges Calculator",
         "See the final billed price with making charges and 3% GST."),
    ]
    hub_cards = "".join(
        f'<a class="toolcard" href="{SITE_URL}/{s}"><b>{t}</b>'
        f'<span>{d}</span></a>' for s, t, d in tools)
    hub_cards = (f'<a class="toolcard" href="{SITE_URL}/"><b>Gold Price '
                 f'Calculator</b><span>Cost of gold by weight, purity and '
                 f'brand - in the Calculators tab.</span></a>' + hub_cards)
    render_content(
        "calculators",
        "Gold Calculators - Loan, SIP, Making Charges & Price | MyGoldRates",
        "Free gold calculators for India: gold loan eligibility & EMI, gold "
        "SIP returns, making charges with GST, and live gold price by weight.",
        crumbs(("Calculators", None)) +
        "<h1>Gold Calculators</h1>"
        "<p>Free tools that use today's live 24K gold rate ("
        f"<strong>{rate_str}/g</strong>, pre-GST) to help you plan a gold "
        "purchase, loan or investment.</p>"
        f'<div class="toolgrid">{hub_cards}</div>')
    extra_urls.append(("calculators", "weekly", "0.7"))

    # ---- Gold Loan calculator ----
    render_content(
        "gold-loan-calculator",
        "Gold Loan Calculator - Eligibility & EMI (India) | MyGoldRates",
        "Calculate your gold loan eligibility and monthly EMI from your gold's "
        "weight, purity and today's gold rate. Free, instant.",
        crumbs(("Calculators", f"{SITE_URL}/calculators"),
               ("Gold Loan", None)) +
        "<h1>Gold Loan Calculator</h1>"
        "<p>Estimate how much loan your gold can fetch and the EMI, using "
        f"today's 24K rate of <strong>{rate_str}/g</strong> (pre-GST).</p>"
        '<div class="calcbox">'
        '<label for="w">Gold weight (grams)</label>'
        '<input id="w" type="number" min="0" step="0.1" value="20">'
        '<label for="p">Purity</label>'
        '<select id="p"><option value="0.916">22K (916)</option>'
        '<option value="0.999">24K (999)</option>'
        '<option value="0.75">18K (750)</option></select>'
        '<label for="ltv">Loan-to-value (%)</label>'
        '<input id="ltv" type="number" min="1" max="90" value="75">'
        '<label for="r">Interest rate (% p.a.)</label>'
        '<input id="r" type="number" min="0" step="0.1" value="12">'
        '<label for="n">Tenure (months)</label>'
        '<input id="n" type="number" min="1" value="12">'
        '<div class="calcout"><div class="big" id="loan">-</div>'
        '<div class="row"><span>Gold value</span><span id="val">-</span></div>'
        '<div class="row"><span>Monthly EMI</span><span id="emi">-</span></div>'
        '<div class="row"><span>Total repayment</span>'
        '<span id="tot">-</span></div></div></div>'
        '<p style="font-size:12.5px;color:var(--ink-3)">Indicative only. '
        'Actual eligibility, LTV and rates vary by lender and RBI norms.</p>',
        extra_js=_calc_js("loan", rate24))
    extra_urls.append(("gold-loan-calculator", "weekly", "0.6"))

    # ---- Gold SIP calculator ----
    render_content(
        "gold-sip-calculator",
        "Gold SIP Calculator - Monthly Gold Investment Returns | MyGoldRates",
        "Project the future value of a monthly gold SIP and the grams you "
        "accumulate, using today's gold rate. Free gold investment calculator.",
        crumbs(("Calculators", f"{SITE_URL}/calculators"),
               ("Gold SIP", None)) +
        "<h1>Gold SIP Calculator</h1>"
        "<p>See what a monthly gold investment could grow to, based on an "
        f"expected appreciation rate. Today's 24K rate: <strong>{rate_str}/g"
        "</strong>.</p>"
        '<div class="calcbox">'
        '<label for="m">Monthly investment (Rs)</label>'
        '<input id="m" type="number" min="0" step="100" value="5000">'
        '<label for="y">Duration (years)</label>'
        '<input id="y" type="number" min="1" max="40" value="10">'
        '<label for="g">Expected gold appreciation (% p.a.)</label>'
        '<input id="g" type="number" min="0" step="0.5" value="9">'
        '<div class="calcout"><div class="big" id="fv">-</div>'
        '<div class="row"><span>Total invested</span>'
        '<span id="inv">-</span></div>'
        '<div class="row"><span>Estimated gain</span>'
        '<span id="gain">-</span></div>'
        '<div class="row"><span>Approx. gold at today&#39;s rate</span>'
        '<span id="grams">-</span></div></div></div>'
        '<p style="font-size:12.5px;color:var(--ink-3)">Projections assume a '
        'constant annual rate; real gold prices fluctuate. Not investment '
        'advice.</p>',
        extra_js=_calc_js("sip", rate24))
    extra_urls.append(("gold-sip-calculator", "weekly", "0.6"))

    # ---- Making charges calculator ----
    render_content(
        "making-charges-calculator",
        "Making Charges Calculator - Final Gold Price with GST | MyGoldRates",
        "Work out the final billed price of gold jewellery including making "
        "charges and 3% GST, from the weight, purity and today's gold rate.",
        crumbs(("Calculators", f"{SITE_URL}/calculators"),
               ("Making Charges", None)) +
        "<h1>Making Charges Calculator</h1>"
        "<p>Find the true billed price of jewellery once making charges and 3% "
        f"GST are added. Today's 24K rate: <strong>{rate_str}/g</strong>.</p>"
        '<div class="calcbox">'
        '<label for="w">Gold weight (grams)</label>'
        '<input id="w" type="number" min="0" step="0.1" value="10">'
        '<label for="p">Purity</label>'
        '<select id="p"><option value="0.916">22K (916)</option>'
        '<option value="0.999">24K (999)</option>'
        '<option value="0.75">18K (750)</option></select>'
        '<label for="mt">Making charge type</label>'
        '<select id="mt"><option value="pct">% of gold value</option>'
        '<option value="perg">Rs per gram</option></select>'
        '<label for="mc">Making charge value</label>'
        '<input id="mc" type="number" min="0" step="0.1" value="12">'
        '<div class="calcout"><div class="big" id="total">-</div>'
        '<div class="row"><span>Gold value</span><span id="gv">-</span></div>'
        '<div class="row"><span>Making charges</span>'
        '<span id="mk">-</span></div>'
        '<div class="row"><span>GST (3%)</span><span id="gst">-</span></div>'
        '</div></div>',
        extra_js=_calc_js("making", rate24))
    extra_urls.append(("making-charges-calculator", "weekly", "0.6"))

    # ---- Learn / evergreen articles ----
    for slug, title, desc, h1, body in _articles(rate_str, med, inr):
        render_content(f"learn/{slug}", title, desc,
                       crumbs(("Learn", f"{SITE_URL}/news"), (h1, None)) +
                       f"<h1>{h1}</h1>"
                       f'<p class="updated-on">Last updated {display_date}</p>'
                       + body)
        extra_urls.append((f"learn/{slug}", "monthly", "0.5"))

    # ---- Making charges comparison (from scrape_charges.py output) ----
    try:
        with open("docs/making-charges.json", encoding="utf-8") as f:
            mc = json.load(f)
    except Exception:
        mc = None
    if mc and mc.get("brands"):
        cats = sorted({c["category"] for b in mc["brands"]
                       for c in b["categories"]})
        brs = [b["brand"] for b in mc["brands"]]
        look = {(b["brand"], c["category"]): c
                for b in mc["brands"] for c in b["categories"]}
        # ---- interactive "what would it actually cost me" dashboard ----
        # Join making-charge medians with each brand's live per-gram rate, so
        # the page can price a real item (category + weight + karat) end to end.
        # The insight this unlocks: the cheapest RATE is often not the cheapest
        # TOTAL once making charges are added - which is the whole point.
        rate_by_brand = {}
        for r in live:
            nm = r["brands"]["name"]
            lad = ladder(r["canonical_24k_pre_gst"])
            rate_by_brand[nm] = {"24": round(lad["24K"], 2),
                                 "22": round(lad["22K"], 2),
                                 "18": round(lad["18K"], 2)}
        dash = {}
        for b in mc["brands"]:
            nm = b["brand"]
            if nm not in rate_by_brand:
                continue          # no live rate today -> cannot price it
            cats_d = {c["category"]: {"pct": c["making_pct_median"],
                                      "n": c.get("items", 0),
                                      "conf": c.get("confidence", "")}
                      for c in b["categories"]}
            if cats_d:
                dash[nm] = {"rates": rate_by_brand[nm], "mc": cats_d}
        dash_cats = sorted({c for v in dash.values() for c in v["mc"]})

        # __DATA__ lives in the JS block, the rest in the HTML block - keep the
        # substitutions on their own strings or the page ships a literal
        # "var D = __DATA__" and the whole dashboard silently fails to render.
        mc_body = MC_DASH_HTML \
            .replace("__UPDATED__", mc.get("updated", "")[:10]) \
            .replace("__NBRANDS__", str(len(dash))) \
            .replace("__SITE__", SITE_URL)
        mc_js = MC_DASH_JS.replace(
            "__DATA__", json.dumps({"brands": dash, "cats": dash_cats}))

        render_content(
            "making-charges-comparison",
            "Gold Making Charge Calculator - Compare Real Prices | MyGoldRates",
            "See what a bangle, ring, earrings or mangalsutra actually costs at "
            "each jeweller - gold value, making charge and GST broken out, "
            "ranked cheapest first.",
            crumbs(("Making Charges", None)) + mc_body,
            extra_js=mc_js)
        extra_urls.append(("making-charges-comparison", "monthly", "0.6"))

        # ---- Budget calculator: how many grams for a fixed rupee amount ----
        # Widen coverage vs the MC dashboard: EVERY brand with a live rate is
        # scored, not just the 3 with verified MC medians. For the extras we
        # fall back to the category median across brands that DO have MC data
        # - clearly flagged in-row as an estimate so users know it's not the
        # brand's own published number. Rate-only comparison hides the making
        # gap and this exists precisely to expose it, so a fallback is better
        # than dropping the brand entirely.
        cat_medians = {}
        for c in dash_cats:
            vals = [b["mc"][c]["pct"] for b in dash.values() if c in b["mc"]]
            if vals:
                cat_medians[c] = round(statistics.median(vals), 1)
        budget_brands = dict(dash)                # start from real MC data
        for name, rates in rate_by_brand.items():
            if name in budget_brands:
                continue                           # already has real MC
            budget_brands[name] = {
                "rates": rates,
                "mc": {c: {"pct": p, "n": 0, "conf": "estimate"}
                       for c, p in cat_medians.items()}}
        budget_body = BUDGET_HTML \
            .replace("__UPDATED__", mc.get("updated", "")[:10]) \
            .replace("__SITE__", SITE_URL)
        budget_js = BUDGET_JS.replace(
            "__DATA__", json.dumps({"brands": budget_brands,
                                     "cats": dash_cats}))

        render_content(
            "budget-gold-calculator",
            "Gold for My Budget - How Many Grams Can I Buy | MyGoldRates",
            "Fix your budget and see how many grams of gold you can actually "
            "take home from each jeweller after making charges and 3% GST - "
            "and check if your own jeweller's quote beats them.",
            crumbs(("Calculators", f"{SITE_URL}/calculators"),
                   ("Budget Calculator", None)) + budget_body,
            extra_js=budget_js)
        extra_urls.append(("budget-gold-calculator", "weekly", "0.7"))

    # ---- News: auto daily market recap from the rate history ----
    # RECAP_INDEX_DAYS: a recap has real, standalone reference value (one
    # page per day, genuinely distinct content - not the same-day
    # near-duplication daily city pages have, see gen_daily below), so it
    # stays indexed far longer than a daily page. Still finite though - an
    # unbounded, ever-growing set of indexed near-identical "recap for date
    # X" pages is exactly the kind of thin-content-at-scale pattern that
    # drags down Search Console's view of the whole site, so recaps past
    # this window are noindexed (content stays live, just stops being
    # advertised for indexing) rather than left indexed forever.
    RECAP_INDEX_DAYS = 90
    recap_cutoff = now_ist.date() - timedelta(days=RECAP_INDEX_DAYS)
    os.makedirs("docs/news/recap", exist_ok=True)
    recaps = []              # (slug, date_obj, disp, med24, move, pct)
    for i in range(1, len(trend)):
        d_iso, m24 = trend[i]
        pm24 = trend[i - 1][1]
        move = m24 - pm24
        pct = (move / pm24 * 100) if pm24 else 0
        dt = datetime.fromisoformat(d_iso)
        slug = f"daily-recap-{dt.day}-{dt.strftime('%b').lower()}-{dt.year}"
        disp = dt.strftime("%d %B %Y")
        lad = ladder(m24)
        arrow = "rose" if move > 0.5 else ("fell" if move < -0.5 else "held")
        cls = "up" if move > 0.5 else ("dn" if move < -0.5 else "")
        sign = "+" if move >= 0 else "-"
        body = (
            f"<h1>Gold Rate Daily Recap - {disp}</h1>"
            f'<p class="updated-on">Market recap - {disp}</p>'
            f"<p>On {disp}, the median <strong>24K gold rate</strong> across "
            f"India's leading jewellers was <strong>{inr(m24)} per gram</strong> "
            f"(pre-GST). It <strong>{arrow}</strong> "
            f'<span class="recap-move {cls}">{sign}{inr(abs(move))} '
            f"({sign}{abs(pct):.2f}%)</span> from {inr(pm24)} the previous "
            f"session.</p>"
            f"<h2>Today's median rates</h2><ul>"
            f"<li>24K (999): <strong>{inr(lad['24K'])}/g</strong></li>"
            f"<li>22K (916): <strong>{inr(lad['22K'])}/g</strong></li>"
            f"<li>18K (750): <strong>{inr(lad['18K'])}/g</strong></li></ul>"
            f"<p>All figures are per gram, pre-GST, across {len(live)} "
            f"jewellers. Add 3% GST for the billed price. Compare live rates on "
            f'the <a href="{SITE_URL}/">gold rate today</a> page.</p>')
        recap_fresh = dt.date() >= recap_cutoff
        render_content(f"news/recap/{slug}",
                       f"Gold Rate Daily Recap - {disp} | MyGoldRates",
                       f"Gold price recap for {disp}: 24K median {inr(m24)}/g, "
                       f"{sign}{abs(pct):.2f}% vs the previous session. 22K, 18K "
                       "and jeweller medians.",
                       body,
                       robots=("index, follow, max-image-preview:large"
                               if recap_fresh else "noindex, follow"))
        recaps.append((slug, dt, disp, m24, move, pct))
        # Keep noindexed recaps out of the sitemap too - no point advertising
        # a URL for indexing that's explicitly told not to be indexed.
        if recap_fresh:
            extra_urls.append((f"news/recap/{slug}", "monthly", "0.5"))

    recaps.sort(key=lambda x: x[1], reverse=True)

    # ---- dated DAILY news pages (India + top cities), GoodReturns-style ----
    # Each build writes today's dated pages; past ones persist in docs/ and are
    # picked up for the sitemap by globbing, so the archive grows every day.
    os.makedirs("docs/news/daily", exist_ok=True)
    prev24 = trend[-2][1] if len(trend) >= 2 else median24
    dmove = median24 - prev24
    dpct = (dmove / prev24 * 100) if prev24 else 0
    darrow = ("rose" if dmove > 0.5 else
              ("fell" if dmove < -0.5 else "held steady"))
    dcls = "up" if dmove > 0.5 else ("dn" if dmove < -0.5 else "")
    dsign = "+" if dmove >= 0 else "-"
    date_slug = f"{now_ist.day}-{now_ist.strftime('%b').lower()}-{now_ist.year}"
    today_daily = []          # (slug, place) generated this run

    def gen_daily(place, place_slug):
        lad = ladder(median24)
        where_in = f"in {place}"
        slug = f"news/daily/gold-rate-{place_slug}-{date_slug}"
        local = ("" if place == "India" else
                 f" National jewellery chains quote the same board rate in "
                 f"{place} as across India, so these figures apply in {place} "
                 f"today.")
        citylink = ("" if place == "India" else
                    f' or the <a href="{SITE_URL}/gold-rate-today-in-'
                    f'{place_slug}">{place} gold rate page</a>')
        body = (
            crumbs(("News", f"{SITE_URL}/news"),
                   (f"Gold Rate {display_date}", None)) +
            f"<h1>Gold Rate Today {where_in} - {display_date}</h1>"
            f'<p class="updated-on">Updated {display_time}, {display_date}</p>'
            f"<p>The <strong>gold rate today {where_in}</strong> is "
            f"<strong>{inr(lad['24K'])} per gram for 24 carat (999)</strong> "
            f"and <strong>{inr(lad['22K'])} per gram for 22 carat (916)</strong>"
            f", pre-GST - the median across {len(live)} of India's leading "
            f"jewellers on {display_date}. The 24K rate <strong>{darrow}"
            f'</strong> <span class="recap-move {dcls}">{dsign}'
            f"{inr(abs(dmove))} ({dsign}{abs(dpct):.2f}%)</span> from the "
            f"previous session.{local}</p>"
            f"<h2>Today's gold rate {where_in} by purity</h2>"
            f"<ul><li><strong>24K (999):</strong> {inr(lad['24K'])} / gram</li>"
            f"<li><strong>22K (916):</strong> {inr(lad['22K'])} / gram</li>"
            f"<li><strong>18K (750):</strong> {inr(lad['18K'])} / gram</li></ul>"
            f"<p>All prices are per gram and pre-GST; add 3% GST for the billed "
            f"amount, and remember making charges are extra. Compare every "
            f'jeweller live on the <a href="{SITE_URL}/">gold rate today</a> '
            f"page{citylink}.</p>"
            f"<h2>What moved the gold rate</h2>"
            f"<p>Daily gold prices in India track the international spot price, "
            f"the rupee-dollar exchange rate, import duty and each jeweller's "
            f'premium - see <a href="{SITE_URL}/learn/how-gold-rates-are-set">'
            f"how gold rates are set</a> for the full breakdown. For a purity "
            f'comparison read <a href="{SITE_URL}/learn/22k-vs-24k-gold">22K vs '
            f"24K gold</a>.</p>")
        render_content(
            slug,
            f"Gold Rate Today {where_in} ({display_date}) - 24K, 22K, 18K "
            "Price | MyGoldRates",
            f"Gold rate today {where_in} on {display_date}: 24K "
            f"{inr(lad['24K'])}/g, 22K {inr(lad['22K'])}/g, 18K "
            f"{inr(lad['18K'])}/g (pre-GST). 24K {darrow} {dsign}"
            f"{abs(dpct):.2f}% vs the previous session.",
            body)
        today_daily.append((slug, place))

    gen_daily("India", "india")
    for _c in DAILY_NEWS_CITIES:
        gen_daily(_c, loc_slug(_c))

    # today's dated articles, featured at the top of /news
    daily_cards = "".join(
        f'<a class="newscard" href="{SITE_URL}/{slug}">'
        f'<div class="nt">Gold Rate Today {"in " + place if place != "India" else "in India"} - {display_date}</div>'
        f'<div class="nd">{display_date} &middot; 24K {inr(med["24K"])}/g</div>'
        f'</a>' for slug, place in today_daily)

    news_cards = ""
    for slug, dt, disp, m24, move, pct in recaps[:20]:
        cls = "up" if move > 0.5 else ("dn" if move < -0.5 else "")
        sign = "+" if move >= 0 else "-"
        news_cards += (
            f'<a class="newscard" href="{SITE_URL}/news/recap/{slug}">'
            f'<div class="nt">Gold Rate Daily Recap - {disp}</div>'
            f'<div class="nd">{disp}</div>'
            f'<div class="nx">24K median {inr(m24)}/g, '
            f'<span class="recap-move {cls}">{sign}{abs(pct):.2f}%</span> '
            f'vs previous session.</div></a>')
    if not news_cards:
        news_cards = ('<p>Daily recaps will appear here as rate history builds '
                      'up over the coming days.</p>')

    # live headlines (Google News), rendered as external-link cards
    live_news = "".join(news_card(n) for n in news_items)
    live_block = (
        '<h2>Latest Gold News</h2>'
        '<p style="font-size:13px;color:var(--ink-3);margin-bottom:6px">'
        'Live headlines from across the web, refreshed through the day. '
        'Tap a headline to read the full story at the source.</p>'
        + live_news) if live_news else ""

    render_content(
        "news",
        "Gold News Today & Daily Rate Recap (India) | MyGoldRates",
        "Latest gold price news for India plus a daily data-driven recap of how "
        "24K, 22K and 18K rates moved - refreshed through the day.",
        crumbs(("News", None)) +
        "<h1>Gold News &amp; Daily Rate Recap</h1>"
        "<p>The latest gold price headlines from across the web, plus our own "
        "dated daily gold-rate reports and a data-driven market recap.</p>"
        f'<h2>Today\'s Gold Rate Reports - {display_date}</h2>' + daily_cards +
        live_block +
        '<h2>Daily Market Recap</h2>' + news_cards)
    extra_urls.append(("news", "hourly", "0.8"))
    extra_urls.append(("about", "monthly", "0.7"))
    extra_urls.append(("methodology", "monthly", "0.7"))
    extra_urls.append(("contact", "monthly", "0.5"))
    print(f"content pages: 4 calculators, "
          f"{len(list(_articles(rate_str, med, inr)))} articles, "
          f"{len(recaps)} recaps")
    # ---- private analytics dashboard (secret-gated read; noindex; unlinked) ----
    # The access token is NOT baked into the page; it is supplied at view time
    # via the URL fragment (.../analytics#token). So the hosted file holds no
    # secret and privacy comes from possession of the link. analytics_token is
    # kept only so the build can warn if the shared secret was never configured.
    _ = analytics_token
    analytics_page = (
        ANALYTICS_HTML
        .replace("__SB__", supabase_url)
        .replace("__KEY__", anon_key)
        .replace("__DATE__", display_date))
    with open("docs/analytics.html", "w", encoding="utf-8") as f:
        f.write(analytics_page)
    print("analytics dashboard: wrote docs/analytics.html (token via URL hash)")

    with open("docs/robots.txt", "w", encoding="utf-8") as f:
        # Explicitly welcome AI/LLM crawlers so generative engines (ChatGPT,
        # AI assistants, Perplexity, Gemini/AI Overviews, etc.) can index and cite us.
        ai_bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot",
                   "Claude-Web", "anthropic-ai", "PerplexityBot",
                   "Perplexity-User", "Google-Extended", "Applebot-Extended",
                   "Amazonbot", "CCBot", "cohere-ai", "Bytespider",
                   "Meta-ExternalAgent", "DuckAssistBot", "YouBot"]
        f.write("# All crawlers welcome, including AI/LLM assistants.\n")
        for bot in ai_bots:
            f.write(f"User-agent: {bot}\nAllow: /\n\n")
        f.write(f"User-agent: *\nAllow: /\nDisallow: /analytics\nDisallow: /analytics.html\n\n"
                f"Sitemap: {SITE_URL}/sitemap.xml\n"
                f"Sitemap: {SITE_URL}/sitemap_news.xml\n"
                f"# AI summary: {SITE_URL}/llms.txt\n"
                f"# Machine-readable rates: {SITE_URL}/rates.json\n")

    # ---- all dated daily news pages (glob = growing archive) ----
    def _daily_date(path):
        parts = os.path.basename(path)[:-5].split("-")
        try:
            return datetime.strptime("-".join(parts[-3:]), "%d-%b-%Y").date()
        except Exception:
            return None

    daily_files = sorted(glob.glob("docs/news/daily/*.html"))
    daily_meta = []          # (loc, date, title)
    for pth in daily_files:
        stem = os.path.basename(pth)[:-5]
        dd = _daily_date(pth)
        # rebuild a human title from the slug (place between 'gold-rate-' & date)
        mid = stem[len("gold-rate-"):].rsplit("-", 3)[0] if \
            stem.startswith("gold-rate-") else stem
        place = mid.replace("-", " ").title() or "India"
        ttl = (f"Gold Rate Today in {place} - "
               f"{dd.strftime('%d %B %Y') if dd else ''}")
        daily_meta.append((f"news/daily/{stem}", dd, ttl))

    # DAILY_INDEX_DAYS: a daily page has essentially zero query relevance
    # once it's not "today" any more, and unlike recaps (one per day) it's
    # also duplicated ~13x on the SAME day - national jewellery chains quote
    # one board rate everywhere, so 12 of the 13 city pages differ from each
    # other only by the city name, not the actual content. Left indexed
    # forever (the old behaviour: gen_daily writes today's page once, it
    # persists on disk untouched, and every past page was globbed straight
    # into sitemap.xml with no expiry), this compounds daily into a fast-
    # growing mass of thin/duplicate pages - a well-documented cause of a
    # site's overall pages being flagged "Crawled - currently not indexed"
    # or "Duplicate, Google chose different canonical" in Search Console,
    # which can drag down how the whole site is perceived, not just these
    # pages. Window matches the 2-day Google News cutoff below plus a day
    # of buffer, not the longer recap window - these pages need it.
    DAILY_INDEX_DAYS = 3
    daily_index_cutoff = now_ist.date() - timedelta(days=DAILY_INDEX_DAYS)
    # Daily pages, unlike recaps, are NOT rewritten by render_content() once
    # written (gen_daily only ever runs for "today"), so past ones can't be
    # noindexed by passing a robots= kwarg at generation time - they have to
    # be patched in place, on disk, as they age past the cutoff on a later
    # run. Idempotent (skips files already patched) and safe to run every
    # build.
    for pth, dd, _ in daily_meta:
        if not dd or dd >= daily_index_cutoff:
            continue
        fpath = f"docs/{pth}.html"
        with open(fpath, encoding="utf-8") as f:
            html = f.read()
        if 'name="robots" content="noindex' in html:
            continue
        if 'name="robots" content="index, follow, max-image-preview:large">' in html:
            new_html = html.replace(
                '<meta name="robots" content="index, follow, '
                'max-image-preview:large">',
                '<meta name="robots" content="noindex, follow">', 1)
        else:
            # Pages written before this fix have no robots tag at all
            # (CONTENT_TEMPLATE didn't emit one) - insert one after viewport.
            new_html = html.replace(
                '<meta name="viewport" content="width=device-width, '
                'initial-scale=1">',
                '<meta name="viewport" content="width=device-width, '
                'initial-scale=1">\n'
                '<meta name="robots" content="noindex, follow">', 1)
        if new_html == html:
            continue          # unexpected head shape - don't guess, skip
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_html)

    # ---- Google News sitemap: recaps + daily pages from the last 2 days ----
    cutoff = datetime.now(IST).date() - timedelta(days=2)
    news_urls = "".join(
        f"  <url><loc>{SITE_URL}/news/recap/{s}</loc>\n"
        f"    <news:news><news:publication><news:name>MyGoldRates</news:name>"
        f"<news:language>en</news:language></news:publication>"
        f"<news:publication_date>{dt.strftime('%Y-%m-%d')}T09:00:00+05:30"
        f"</news:publication_date>"
        f"<news:title>Gold Rate Daily Recap - {disp}</news:title>"
        f"</news:news></url>\n"
        for (s, dt, disp, m24, mv, pc) in recaps if dt.date() >= cutoff)
    news_urls += "".join(
        f"  <url><loc>{SITE_URL}/{loc}</loc>\n"
        f"    <news:news><news:publication><news:name>MyGoldRates</news:name>"
        f"<news:language>en</news:language></news:publication>"
        f"<news:publication_date>{dd.strftime('%Y-%m-%d')}T09:00:00+05:30"
        f"</news:publication_date>"
        f"<news:title>{_html.escape(ttl)}</news:title></news:news></url>\n"
        for (loc, dd, ttl) in daily_meta if dd and dd >= cutoff)
    with open("docs/sitemap_news.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
                '        xmlns:news="http://www.google.com/schemas/'
                'sitemap-news/0.9">\n'
                + news_urls + "</urlset>\n")
    with open("docs/sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                f"  <url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod>"
                "<changefreq>daily</changefreq><priority>1.0</priority></url>\n"
                f"  <url><loc>{SITE_URL}/inquiry</loc>"
                f"<lastmod>{today}</lastmod>"
                "<changefreq>monthly</changefreq><priority>0.6</priority></url>\n"
                + "".join(
                    f"  <url><loc>{SITE_URL}/{p}</loc><lastmod>{today}"
                    "</lastmod><changefreq>monthly</changefreq>"
                    "<priority>0.4</priority></url>\n"
                    for p in ("about", "contact", "privacy"))
                + "".join(
                    f"  <url><loc>{SITE_URL}/gold-rate-today-in-"
                    f"{loc_slug(nm)}</loc><lastmod>{today}</lastmod>"
                    "<changefreq>daily</changefreq>"
                    "<priority>0.7</priority></url>\n"
                    for nm in LOCATIONS)
                + "".join(
                    f"  <url><loc>{SITE_URL}/{loc}</loc><lastmod>{today}"
                    f"</lastmod><changefreq>{cf}</changefreq>"
                    f"<priority>{pr}</priority></url>\n"
                    for loc, cf, pr in extra_urls)
                + "".join(
                    f"  <url><loc>{SITE_URL}/{loc}</loc><lastmod>"
                    f"{(dd or now_ist.date()).isoformat()}</lastmod>"
                    "<changefreq>monthly</changefreq><priority>0.6</priority>"
                    "</url>\n"
                    # Only advertise daily pages still within the indexing
                    # window (see DAILY_INDEX_DAYS above) - no point listing
                    # a URL in the sitemap that the page itself now says not
                    # to index.
                    for loc, dd, ttl in daily_meta
                    if dd and dd >= daily_index_cutoff)
                + "</urlset>\n")

    # ---- IndexNow: instantly notify Bing/Yandex/Seznam of fresh URLs ----
    INDEXNOW_KEY = "b7f3c9a1e04d4f6a8c2b5d9e1f0a3c7d"
    with open(f"docs/{INDEXNOW_KEY}.txt", "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)
    try:
        fresh_now = [f"{SITE_URL}/", f"{SITE_URL}/news"]
        fresh_now += [f"{SITE_URL}/{loc}" for loc, dd, _ in daily_meta
                      if dd == now_ist.date()]
        if recaps and recaps[0][1].date() == now_ist.date():
            fresh_now.append(f"{SITE_URL}/news/recap/{recaps[0][0]}")
        rr = requests.post(
            "https://api.indexnow.org/indexnow",
            json={"host": CUSTOM_DOMAIN, "key": INDEXNOW_KEY,
                  "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
                  "urlList": fresh_now[:100]},
            headers={"Content-Type": "application/json"}, timeout=20)
        print(f"indexnow: pinged {len(fresh_now)} urls -> {rr.status_code}")
    except Exception as e:
        print("indexnow: skipped:", type(e).__name__, str(e)[:80])

    with open("docs/ads.txt", "w", encoding="utf-8") as f:
        if ads_client:
            pub = ads_client.replace("ca-", "")   # ca-pub-XXXX -> pub-XXXX
            f.write(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
        else:
            f.write("# Set the ADSENSE_CLIENT secret to publish your ads.txt "
                    "line automatically.\n"
                    "# google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0\n")
    # ---- machine-readable rates feed (for AI engines & developers) ----
    def r2(v):
        return round(float(v), 2)
    brands_json = []
    for r in sorted(live, key=lambda x: x["canonical_24k_pre_gst"]):
        lad = ladder(r["canonical_24k_pre_gst"])
        brands_json.append({
            "jeweller": r["brands"]["name"],
            "rate_24k_per_gram_inr": r2(lad["24K"]),
            "rate_22k_per_gram_inr": r2(lad["22K"]),
            "rate_18k_per_gram_inr": r2(lad["18K"]),
        })
    rates_feed = {
        "source": "MyGoldRates.com",
        "source_url": SITE_URL,
        "description": "Daily gold rate today in India, compared across major "
                       "jewellers. Per gram, Indian Rupees, pre-GST.",
        "date": today,
        "last_updated": now_ist.isoformat(),
        "currency": "INR",
        "unit": "per gram",
        "gst": "excluded (pre-GST); add 3% for billed price",
        "median_rate_per_gram_inr": {
            "24k": r2(med["24K"]), "22k": r2(med["22K"]),
            "18k": r2(med["18K"])},
        "lowest_24k": {
            "jeweller": lowest["brands"]["name"],
            "rate_per_gram_inr": r2(ladder(
                lowest["canonical_24k_pre_gst"])["24K"])},
        "ibja_reference_24k_999_per_gram_inr": r2(r999) if ibja else None,
        "akgsma_south_india_22k_per_gram_inr": r2(akgsma[1]) if akgsma else None,
        "mcx_gold_futures": ([
            {"contract": c["symbol"], "expiry": c["expiry"],
             "price_per_10g_inr": r2(c["ltp"]),
             "change_pct": r2(c["pchg"])} for c in mcx] if mcx else []),
        "jewellers": brands_json,
        "jeweller_count": len(live),
        "city_pages": [f"{SITE_URL}/gold-rate-today-in-{loc_slug(nm)}"
                       for nm in LOCATIONS],
        "disclaimer": "Rates are indicative, compiled from each brand's "
                      "published prices, and can change during the day. "
                      "Confirm with the jeweller before purchase. Not "
                      "investment advice.",
        "license": f"{SITE_URL}/#terms",
    }
    with open("docs/rates.json", "w", encoding="utf-8") as f:
        json.dump(rates_feed, f, ensure_ascii=False, indent=2)

    # ---- llms.txt: a plain-text brief for AI/LLM crawlers ----
    mcx_line = ""
    if mcx:
        g = next((c for c in mcx if c["symbol"] == "GOLD"), mcx[0])
        mcx_line = (f"- MCX gold futures ({g['expiry']}): "
                    f"{inr(g['ltp'])} per 10g (995), {g['pchg']:+.2f}%\n")
    llms = f"""# MyGoldRates.com

> India's daily gold rate comparison platform. We publish today's 24K, 22K
> and 18K gold rates compared across {len(live)} of India's leading
> jewellers, with the IBJA bullion reference and MCX gold futures, updated
> every day. All rates are per gram in Indian Rupees (INR), pre-GST.

## Today's gold rate in India ({display_date})
- 24K (999) median: {inr(med['24K'])} per gram (pre-GST)
- 22K (916) median: {inr(med['22K'])} per gram (pre-GST)
- 18K (750) median: {inr(med['18K'])} per gram (pre-GST)
- Lowest 24K today: {inr(ladder(lowest['canonical_24k_pre_gst'])['24K'])} \
per gram at {lowest['brands']['name']}
{f"- IBJA 24K (999) reference: {inr(r999)} per gram (pre-GST)" if ibja else ""}
{mcx_line}- Last updated: {now_ist.isoformat()}

## Key pages
- Home / today's rates: {SITE_URL}/
- Machine-readable JSON feed: {SITE_URL}/rates.json
- Daily email alerts: {SITE_URL}/inquiry
- About: {SITE_URL}/about
- Contact: {SITE_URL}/contact
- City & state pages: {SITE_URL}/gold-rate-today-in-<city> \
(e.g. mumbai, delhi, hyderabad, chennai, bengaluru, pune, kolkata)

## About the data
- Coverage: {len(live)} major Indian jewellers plus the IBJA bullion \
benchmark and MCX gold futures.
- Purities: 24K (99.9% / 999), 22K (91.6% / 916), 18K (75.0% / 750).
- Unit & currency: per gram, Indian Rupees (INR).
- GST: rates shown are pre-GST; add 3% GST for the billed price. Making \
charges are extra and vary by design.
- Update frequency: refreshed multiple times daily (11:05, 14:00 and \
17:00 IST).
- Attribution: cite as "MyGoldRates.com" with the URL {SITE_URL}.

## Disclaimer
Rates are indicative and can change during the day; confirm with the
jeweller before purchase. This is not investment advice.
"""
    with open("docs/llms.txt", "w", encoding="utf-8") as f:
        f.write(llms)

    with open("docs/.nojekyll", "w", encoding="utf-8") as f:
        f.write("")
    with open("docs/CNAME", "w", encoding="utf-8") as f:
        f.write(CUSTOM_DOMAIN + "\n")
    print(f"site generated: {len(live)} brands, median 24K {inr(med['24K'])}, "
          f"IBJA {'ok' if ibja else 'unavailable'}, "
          f"inquiry form {'armed' if anon_key else 'DISABLED (no anon key)'}")


# Slide-out navigation drawer, shared across every page. Absolute links so it
# works from nested paths (e.g. /news/recap/...). Self-contained (own inline
# script); the hamburger button is added to each header.
NAV = f"""<div class="nav-ov" id="nav-ov" hidden></div>
<aside class="navdrawer" id="navdrawer" aria-hidden="true" aria-label="Menu">
  <div class="nav-head"><strong>My<b>Gold</b>Rates</strong>
    <button class="nav-x" id="nav-x" aria-label="Close menu">&times;</button>
  </div>
  <nav>
    <p class="nav-grp">Gold Rates</p>
    <a href="{SITE_URL}/">Gold Rate Today</a>
    <a href="{SITE_URL}/#cmp">Compare Jewellers</a>
    <a href="{SITE_URL}/#cityh">Gold Rate by City &amp; State</a>
    <a href="{SITE_URL}/calculators">Price Calculator</a>
    <p class="nav-grp">Calculators</p>
    <a href="{SITE_URL}/calculators">All Calculators</a>
    <a href="{SITE_URL}/gold-loan-calculator">Gold Loan Calculator</a>
    <a href="{SITE_URL}/gold-sip-calculator">Gold SIP Calculator</a>
    <a href="{SITE_URL}/making-charges-calculator">Making Charges Calculator</a>
    <a href="{SITE_URL}/making-charges-comparison">Making Charges Comparison</a>
    <p class="nav-grp">News</p>
    <a href="{SITE_URL}/news">Market News &amp; Daily Recap</a>
    <p class="nav-grp">Learn</p>
    <a href="{SITE_URL}/learn/22k-vs-24k-gold">22K vs 24K Gold</a>
    <a href="{SITE_URL}/learn/gold-hallmarking">Gold Hallmarking (BIS)</a>
    <a href="{SITE_URL}/learn/how-gold-rates-are-set">How Gold Rates Are Set</a>
    <a href="{SITE_URL}/learn/making-charges-explained">Making Charges Explained</a>
    <p class="nav-grp">Company</p>
    <a href="{SITE_URL}/about">About</a>
    <a href="{SITE_URL}/methodology">Our Methodology</a>
    <a href="{SITE_URL}/contact">Contact</a>
    <a href="{SITE_URL}/privacy">Privacy Policy</a>
    <a href="{SITE_URL}/inquiry">Daily Email Alerts</a>
  </nav>
</aside>
<script>(function(){{
  function init(){{
    var d=document.getElementById('navdrawer'),o=document.getElementById('nav-ov'),
        t=document.getElementById('navtog'),x=document.getElementById('nav-x');
    if(!d||!t)return;
    function s(open){{d.classList.toggle('open',open);o.hidden=!open;
      d.setAttribute('aria-hidden',open?'false':'true');
      t.setAttribute('aria-expanded',open?'true':'false');}}
    t.addEventListener('click',function(){{s(!d.classList.contains('open'));}});
    if(x)x.addEventListener('click',function(){{s(false);}});
    o.addEventListener('click',function(){{s(false);}});
    document.addEventListener('keydown',function(e){{
      if(e.key==='Escape'&&d.classList.contains('open'))s(false);}});
  }}
  if(document.readyState==='loading'){{
    document.addEventListener('DOMContentLoaded',init);
  }}else{{
    setTimeout(init,0);
  }}
}})();</script>"""


BASE_CSS = """
/* google signup (shared by modal + inquiry) */
.gwrap{margin:0 0 10px;text-align:center}
.ghost{display:flex;justify-content:center;min-height:44px}
.gdone{font-size:12.5px;color:var(--emerald);margin:10px 0 2px}
.gmanual{display:inline-block;margin-top:12px;font-size:12.5px;
  color:var(--ink-3);text-decoration:underline;cursor:pointer}
.gmanual:hover{color:var(--gold)}
.has-google .manualbox{display:none}
.has-google .manualbox.reveal{display:block;
  border-top:1px solid var(--line);margin-top:14px;padding-top:16px}
.locbtn{display:inline-flex;align-items:center;gap:6px;width:100%;
  justify-content:center;font:600 13px/1 "IBM Plex Sans",sans-serif;
  color:var(--emerald);background:color-mix(in srgb,var(--emerald) 8%,transparent);
  border:1px solid color-mix(in srgb,var(--emerald) 40%,transparent);
  border-radius:10px;padding:11px 14px;cursor:pointer;margin:2px 0 12px}
.locbtn:hover{background:color-mix(in srgb,var(--emerald) 14%,transparent)}
.locbtn:disabled{opacity:.7;cursor:default}
/* slide-out navigation drawer */
.navtog{display:inline-flex;align-items:center;justify-content:center;
  width:38px;height:38px;border:1px solid var(--line);border-radius:10px;
  background:var(--card);color:var(--ink);cursor:pointer;font-size:18px;
  flex:0 0 38px;margin-right:2px}
.navtog:hover{border-color:var(--gold);color:var(--gold)}
.nav-ov{position:fixed;inset:0;background:rgba(10,8,4,.5);z-index:1100}
.navdrawer{position:fixed;top:0;left:0;height:100%;width:min(310px,86vw);
  background:var(--paper);border-right:1px solid var(--line);z-index:1110;
  transform:translateX(-105%);transition:transform .26s ease;overflow-y:auto;
  padding:16px 0 30px}
.navdrawer.open{transform:translateX(0)}
.nav-head{display:flex;align-items:center;justify-content:space-between;
  padding:4px 18px 14px;border-bottom:1px solid var(--line);margin-bottom:8px}
.nav-head strong{font-family:"Marcellus",serif;font-weight:400;font-size:18px;
  letter-spacing:.1em;text-transform:uppercase}
.nav-head strong b{font-weight:400;background:var(--gold-foil);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.nav-x{background:none;border:0;font-size:26px;color:var(--ink-3);
  cursor:pointer;line-height:1}
.nav-grp{font:600 10.5px/1 "IBM Plex Mono",monospace;letter-spacing:.16em;
  text-transform:uppercase;color:var(--gold);margin:16px 18px 4px}
.navdrawer nav a{display:block;padding:9px 18px;font-size:14.5px;
  color:var(--ink);text-decoration:none}
.navdrawer nav a:hover{background:color-mix(in srgb,var(--gold) 9%,transparent);
  color:var(--gold)}
:root{
  --paper:#FBF9F4; --ink:#181F1B; --ink-2:#49544D; --ink-3:#79847D;
  --board:#152420; --board-2:#1C312A; --gold:#9C7514; --gold-bright:#D9B24A;
  --gold-foil:linear-gradient(100deg,#8C6A18,#D9B24A 45%,#F0DB9A 55%,#C79A2E);
  --emerald:#1E5C46; --line:#E7E1D3; --card:#FFFFFF; --warm:#8A5A2B;
  --bar:#B98A1E;
}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#0E1613; --ink:#EDE9DD; --ink-2:#B4BDB4; --ink-3:#84908A;
    --board:#0A100D; --board-2:#131E18; --gold:#D9B24A; --gold-bright:#E8C86A;
    --emerald:#5BBB93; --line:#22302A; --card:#151F1A; --warm:#D89A5B;
    --bar:#D9B24A;
  }
}
*{box-sizing:border-box;margin:0}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}
  *{transition:none!important}}
body{background:var(--paper);color:var(--ink);
  font:16px/1.6 "IBM Plex Sans",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:980px;margin:0 auto;padding:0 20px}
a{color:var(--emerald)}
h1,h2,.brand{font-family:"Marcellus",serif;font-weight:400;letter-spacing:.02em}
.eyebrow{font:500 11.5px/1 "IBM Plex Mono",monospace;letter-spacing:.28em;
  text-transform:uppercase;color:var(--gold);margin:40px 0 8px}
header.top{display:flex;justify-content:flex-start;align-items:center;
  flex-wrap:wrap;gap:6px 14px;padding:18px 0 14px}
header.top .brand{order:1;margin-right:auto}
header.top .navtog{order:2}
header.top .topright{order:3}
.brand{display:inline-flex;align-items:center;gap:10px;text-decoration:none;
  color:var(--ink)}
.brand-mark{width:34px;height:34px;flex:none;
  filter:drop-shadow(0 1px 1px rgba(140,106,24,.28))}
.brand-text{display:flex;flex-direction:column;line-height:1}
.wm{font-family:"Marcellus",serif;font-weight:400;font-size:23px;
  letter-spacing:.14em;text-transform:uppercase;color:var(--ink);
  white-space:nowrap}
.wm b{font-weight:400;background:var(--gold-foil);-webkit-background-clip:text;
  background-clip:text;color:transparent}
.wm .tld{color:var(--ink-3);text-transform:lowercase;letter-spacing:.04em;
  font-size:.82em}
.brand-tag{font:600 8px/1 "IBM Plex Mono",monospace;letter-spacing:.13em;
  text-transform:uppercase;color:var(--ink-3);margin-top:6px}
@media (max-width:520px){.brand-tag{display:none}.wm{font-size:19px;
  letter-spacing:.1em}.brand-mark{width:30px;height:30px}}
.topright{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.updated{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink-3)}
.ghead{display:inline-flex;align-items:center}
.uchip{display:inline-flex;align-items:center;gap:7px;font:600 12.5px/1
  "IBM Plex Sans",sans-serif;color:var(--ink);border:1px solid var(--line);
  background:var(--card);border-radius:999px;padding:5px 12px 5px 6px;
  max-width:180px}
.uchip img{width:22px;height:22px;border-radius:50%;flex:0 0 22px;
  object-fit:cover}
.uchip span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ghead{display:inline-flex;align-items:center}
.ghead:empty{display:none}
.signout-btn{margin-left:7px;border:1px solid var(--line);background:transparent;
  color:var(--ink-3);font:600 11px/1 "IBM Plex Sans",sans-serif;cursor:pointer;
  border-radius:999px;padding:5px 10px;white-space:nowrap}
.signout-btn:hover{border-color:var(--gold);color:var(--gold)}
@media (max-width:520px){.uchip{max-width:110px}}
.btn{display:inline-block;font:500 13.5px/1 "IBM Plex Sans",sans-serif;
  background:linear-gradient(140deg,#3A2A0C,#140D04 55%,#241809);
  color:#F0DB9A;border:1px solid rgba(224,186,86,.55);
  padding:11px 18px;border-radius:999px;text-decoration:none;cursor:pointer;
  transition:transform .15s ease, box-shadow .15s ease}
.btn:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(0,0,0,.18)}
.btn-gold{background:var(--gold-foil);color:#1A1508;border:0;font-weight:600}
.btn-lite{background:transparent;color:var(--ink);
  border:1px solid var(--line)}
.btn-lite:hover{border-color:var(--gold);color:var(--gold)}
h2{font-size:24px;margin:2px 0 6px}
.hint{font-size:13.5px;color:var(--ink-3);margin-bottom:14px;max-width:72ch}
.chartcard{background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:18px}
.stamp{display:inline-block;font:500 10.5px/1 "IBM Plex Mono",monospace;
  letter-spacing:.08em;text-transform:uppercase;border-radius:4px;
  padding:3px 7px;margin-left:8px;vertical-align:2px}
.stamp-best{color:var(--gold);border:1px solid var(--gold)}
.stamp-est{color:var(--ink-3);border:1px solid var(--ink-3)}
.stamp-region{color:var(--emerald);border:1px solid var(--emerald)}
/* regional jewellers are hidden until "In my area" reveals the relevant ones */
#rates tbody tr:not([data-states="all"]){display:none}
#rates tbody tr.region-show{display:table-row}
.region-note{font-size:12.5px;color:var(--emerald);margin:0 0 10px;
  font-weight:500}
#nearbtn[aria-pressed="true"]{border-color:var(--emerald);color:var(--emerald)}
footer{margin:44px 0 30px;padding-top:20px;border-top:1px solid var(--line);
  font-size:13px;color:var(--ink-3)}
footer p{margin:6px 0;max-width:80ch}
.foot-nav{margin:0 0 10px}
.foot-nav a{color:var(--ink-3);margin-right:16px;text-decoration:none}
.foot-nav a:hover{color:var(--ink)}
.hits{font-family:"IBM Plex Mono",monospace;font-size:10.5px;
  letter-spacing:.05em;color:var(--ink-3);opacity:.7}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
"""

# Shared signup helpers: +91 phone default, PIN autofill, optional Google
# sign-in (dormant until the GOOGLE_CLIENT_ID secret is set). Served as
# docs/signup.js and used by both the modal (index) and inquiry forms -
# field NAMEs are identical on both, so everything works via form.elements.
SIGNUP_JS = r"""(function(){
  var SB=window.GR_SB_URL||'', KEY=window.GR_SB_KEY||'';
  var form=document.getElementById('m-form')||document.getElementById('inq');
  function F(n){return form?form.elements[n]:null;}

  /* ---- save OR merge a subscriber, keyed by email ----
     Uses the upsert_subscriber RPC (merges into the same email row); if the
     RPC isn't deployed yet it falls back to a plain insert of base fields. */
  function saveSubscriber(payload){
    if(!SB||!KEY||!payload||!payload.email)return Promise.reject('cfg');
    return fetch(SB+'/rest/v1/rpc/upsert_subscriber',{method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,
               'Authorization':'Bearer '+KEY},
      body:JSON.stringify({payload:payload})
    }).then(function(r){
      if(r.ok)return true;
      var base={};['name','email','phone','country','state','city','zip',
        'area','offers_optin'].forEach(function(k){
          if(payload[k]!==undefined)base[k]=payload[k];});
      return fetch(SB+'/rest/v1/inquiries',{method:'POST',
        headers:{'Content-Type':'application/json','apikey':KEY,
                 'Authorization':'Bearer '+KEY,'Prefer':'return=minimal'},
        body:JSON.stringify(base)}).then(function(r2){
          if(!r2.ok)throw new Error('save');return true;});
    });
  }
  window.GR_SAVE=saveSubscriber;

  /* ---- form conveniences: +91 phone default, PIN -> area/city/state ---- */
  var zip=F('zip'),area=F('area');
  /* India Post PO names carry a "S.O"/"B.O"/"H.O" suffix - strip it for a
     clean neighbourhood name (e.g. "Kalachowki S.O" -> "Kalachowki"). */
  function cleanPO(n){return (n||'').replace(/\s+(S\.?O\.?|B\.?O\.?|H\.?O\.?)$/i,'').trim();}
  function pinLookup(force,preferArea){
    if(!zip)return;var v=(zip.value||'').trim();
    if(!/^[1-9]\d{5}$/.test(v))return;
    var c=F('country');if(c&&c.value&&c.value!=='India')return;
    fetch('https://api.postalpincode.in/pincode/'+v)
      .then(function(r){return r.json();})
      .then(function(j){var d=j&&j[0];
        if(!d||d.Status!=='Success'||!d.PostOffice||!d.PostOffice.length)return;
        var po=d.PostOffice;if(c)c.value='India';
        var district=po[0].District||'';
        if(F('state')&&(force||!F('state').value.trim()))F('state').value=po[0].State;
        if(F('city')&&(force||!F('city').value.trim()))F('city').value=district;
        if(!area)return;
        /* Offer every locality in this PIN in the dropdown - one PIN covers
           several areas, so the user picks their exact one. */
        var names=[];po.forEach(function(p){var n=cleanPO(p.Name);
          if(n&&names.indexOf(n)<0)names.push(n);});
        var dl=document.getElementById(area.getAttribute('list'));
        if(dl){dl.innerHTML='';names.forEach(function(n){
          var o=document.createElement('option');o.value=n;dl.appendChild(o);});}
        if(!force&&area.value.trim())return;
        var pick='';
        if(preferArea){        /* match the GPS neighbourhood to a PO name */
          var pl=preferArea.toLowerCase();
          for(var i=0;i<names.length;i++){var nl=names[i].toLowerCase();
            if(nl===pl||nl.indexOf(pl)>=0||pl.indexOf(nl)>=0){pick=names[i];break;}}
          if(!pick)pick=preferArea;
        }
        if(!pick){           /* else first locality that isn't just the city */
          for(var k=0;k<names.length;k++){
            if(names[k].toLowerCase()!==district.toLowerCase()){pick=names[k];break;}}
        }
        if(!pick)pick=names[0]||'';
        if(pick)area.value=pick;
      }).catch(function(){});
  }
  /* ---- "use my location": geolocation -> reverse geocode -> address ---- */
  function set(n,v,force){var el=F(n);
    if(el&&v&&(force||!el.value.trim()))el.value=v;}
  function useLocation(btn){
    if(!navigator.geolocation){alert('Location is not supported by this '+
      'browser - please type your address.');return;}
    var old=btn.textContent;btn.disabled=true;btn.textContent='Locating...';
    function restore(){btn.disabled=false;btn.textContent=old;}
    function jget(u){return fetch(u,{headers:{Accept:'application/json'}})
      .then(function(r){return r.ok?r.json():null;})
      .catch(function(){return null;});}
    navigator.geolocation.getCurrentPosition(function(pos){
      var la=pos.coords.latitude,lo=pos.coords.longitude;
      /* OpenStreetMap/Nominatim first: it reliably returns the Indian PIN
         code and a real neighbourhood name. BigDataCloud returns an empty
         postcode for most Indian coordinates and repeats the city as the
         locality - that's why the area used to come out as "Mumbai" twice
         with no PIN. It stays as a backup for state/city only. */
      Promise.all([
        jget('https://nominatim.openstreetmap.org/reverse?format=jsonv2'+
             '&zoom=18&addressdetails=1&lat='+la+'&lon='+lo),
        jget('https://api.bigdatacloud.net/data/reverse-geocode-client?'+
             'latitude='+la+'&longitude='+lo+'&localityLanguage=en')
      ]).then(function(res){
        var n=res[0],b=res[1];
        if(!n&&!b){restore();
          alert('Could not look up your location - please type your address.');
          return;}
        var a=(n&&n.address)||{};
        var city=a.city||a.town||a.municipality||a.village||
                 String(a.state_district||'').replace(/\s+district$/i,'')||
                 (b&&(b.city||b.locality))||'';
        var areaName=a.suburb||a.neighbourhood||a.quarter||a.city_district||'';
        var st=a.state||(b&&b.principalSubdivision)||'';
        var pin=String(a.postcode||(b&&b.postcode)||'').trim();
        var c=F('country');
        if(c&&/india/i.test(a.country||(b&&b.countryName)||''))c.value='India';
        set('state',st,true);
        set('city',city,true);
        if(pin)set('zip',pin,true);
        /* never echo the city straight back as the area */
        if(area&&areaName&&areaName.toLowerCase()!==String(city).toLowerCase())
          set('area',areaName,true);
        var v=(zip&&zip.value||'').trim();
        if(/^[1-9]\d{5}$/.test(v))pinLookup(true,areaName);
        btn.textContent='Location added';
        setTimeout(restore,2500);
      });
    },function(err){restore();
      alert(err&&err.code===1?'Location permission was denied. You can type '+
        'your address instead.':'Could not get your location - please type '+
        'your address.');},
     {enableHighAccuracy:true,timeout:12000,maximumAge:600000});
  }

  if(form){
    var ph=F('phone');
    if(ph){ph.addEventListener('focus',function(){
        if(!ph.value.trim())ph.value='+91 ';});
      ph.addEventListener('blur',function(){var v=ph.value.replace(/[^\d]/g,'');
        if(/^[6-9]\d{9}$/.test(v))ph.value='+91 '+v;});}
    if(zip){zip.addEventListener('input',function(){
        if(/^[1-9]\d{5}$/.test(zip.value.trim()))pinLookup();});
      zip.addEventListener('blur',pinLookup);}
    var lb=form.querySelector('.locbtn');
    if(lb)lb.addEventListener('click',function(){useLocation(lb);});
  }

  /* ---- header chip (shared markup) + sign-out, available on every page.
     Actual Google sign-in (auto One Tap + button) is owned by the gate
     modal's own script; this restores the visual state from localStorage
     so a returning user doesn't have to sign in again. ---- */
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function chipHTML(u){
    return '<span class="uchip" title="'+esc(u.email)+'">'+
      (u.picture?'<img src="'+esc(u.picture)+'" alt="" referrerpolicy="no-referrer">':'')+
      '<span>'+esc(u.name||u.email||'Signed in')+'</span></span>'+
      '<button type="button" class="signout-btn">Sign out</button>';
  }
  window.GR_CHIP_HTML=chipHTML;
  function chip(u){var h=document.getElementById('hauth');if(!h)return;
    h.hidden=false;h.innerHTML=chipHTML(u);}

  /* Sign out: clear our session, stop Google auto-selecting the same account
     next load, and clear Google's g_state cookie so the One Tap prompt is no
     longer in its "recently dismissed" cooldown. */
  function signOut(){
    try{localStorage.removeItem('gr_user');}catch(e){}
    try{localStorage.removeItem('gr_sub');}catch(e){}
    try{sessionStorage.removeItem('gr_dismissed');}catch(e){}
    try{if(window.google&&google.accounts&&google.accounts.id)
      google.accounts.id.disableAutoSelect();}catch(e){}
    document.cookie='g_state=;path=/;max-age=0';
    document.cookie='g_state=;path=/;domain=.'+location.hostname+';max-age=0';
    var h=document.getElementById('hauth');
    if(h){h.hidden=true;h.innerHTML='';}
    location.reload();
  }
  window.GR_SIGNOUT=signOut;
  document.addEventListener('click',function(e){
    var b=e.target&&e.target.closest?e.target.closest('.signout-btn'):null;
    if(b){e.preventDefault();signOut();}
  });

  function prefill(u){if(!form)return;
    if(F('email')&&!F('email').value.trim())F('email').value=u.email||'';
    if(F('name')&&!F('name').value.trim())F('name').value=u.name||'';
    if(F('phone')&&!F('phone').value.trim())F('phone').value='+91 ';}
  var stored=null;try{stored=JSON.parse(localStorage.getItem('gr_user')||'null');}
    catch(e){}
  if(stored&&stored.email){chip(stored);prefill(stored);}
})();

/* ---- pageview + click analytics, day-wise (Supabase page_views/click_events) ---- */
(function(){
  var SB=window.GR_SB_URL||'', KEY=window.GR_SB_KEY||'';
  if(!SB||!KEY)return;
  var SID;
  try{
    SID=localStorage.getItem('gr_sid');
    if(!SID){
      SID=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():
        (Date.now().toString(36)+Math.random().toString(36).slice(2));
      localStorage.setItem('gr_sid',SID);
    }
  }catch(e){SID='';}
  function post(table,row){
    fetch(SB+'/rest/v1/'+table,{method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,
               'Authorization':'Bearer '+KEY,'Prefer':'return=minimal'},
      body:JSON.stringify(row)}).catch(function(){});
  }
  post('page_views',{page:location.pathname,referrer:document.referrer||null,
    session_id:SID,host:location.hostname});

  /* delegated click tracking on interactive elements, de-duped per target */
  var lastTarget=null,lastAt=0;
  document.addEventListener('click',function(e){
    var el=e.target&&e.target.closest?
      e.target.closest('a[href],button,input[type="submit"],[role="button"]'):null;
    if(!el)return;
    var label=el.id||el.getAttribute('data-track')||
      (el.textContent||'').trim().slice(0,60)||el.tagName.toLowerCase();
    if(!label)return;
    var now=Date.now();
    if(label===lastTarget&&now-lastAt<2000)return;
    lastTarget=label;lastAt=now;
    post('click_events',{page:location.pathname,target:label,session_id:SID});
  },true);
})();
"""

# Google sign-in block (ID-token button host + manual fallback link),
# shared by both forms. The rendered Google button lands in #ghost.
GOOGLE_BTN = """<div class="gwrap" id="gwrap" hidden>
    <div class="ghost" id="ghost"></div>
    <div class="gdone" hidden></div>
    <a href="#" class="gmanual" id="gmanual">Prefer to enter details manually?</a>
  </div>"""

# ---- Feature-gate modal CSS (appended to BASE_CSS) ----
GATE_CSS = """
/* ---- feature gate modal ---- */
#gate-ov{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:2000;
  display:flex;align-items:center;justify-content:center;padding:16px}
#gate-ov[hidden]{display:none}
#gate-box{background:var(--paper);border:1px solid var(--line);border-radius:20px;
  width:100%;max-width:460px;max-height:92vh;overflow-y:auto;
  padding:28px 28px 24px;position:relative;
  box-shadow:0 24px 60px rgba(0,0,0,.35)}
#gate-box h3{font-family:"Marcellus",serif;font-weight:400;font-size:22px;
  margin:0 0 6px;color:var(--ink)}
#gate-box .gate-sub{font-size:14px;color:var(--ink-3);margin:0 0 20px;line-height:1.5}
#gate-close{position:absolute;top:14px;right:16px;background:none;border:0;
  font-size:24px;color:var(--ink-3);cursor:pointer;line-height:1}
#gate-close:hover{color:var(--ink)}
.gate-google-btn{display:flex;align-items:center;justify-content:center;gap:10px;
  width:100%;padding:12px 18px;border:1.5px solid var(--line);border-radius:12px;
  background:var(--card);font:600 14px/1 "IBM Plex Sans",sans-serif;color:var(--ink);
  cursor:pointer;transition:border-color .15s,box-shadow .15s;margin-bottom:6px}
.gate-google-btn:hover{border-color:var(--gold);box-shadow:0 2px 10px rgba(0,0,0,.1)}
.gate-google-btn:disabled{opacity:.6;cursor:default}
.gate-google-btn svg{flex:none}
.gate-or{text-align:center;font-size:12px;color:var(--ink-3);margin:14px 0;
  display:flex;align-items:center;gap:8px}
.gate-or::before,.gate-or::after{content:"";flex:1;height:1px;background:var(--line)}
#gate-form input,#gate-form select,
#gate-enrich-form input,#gate-enrich-form select{
  width:100%;padding:11px 13px;margin-bottom:11px;box-sizing:border-box;
  border:1.5px solid var(--line);border-radius:10px;font:14px "IBM Plex Sans",sans-serif;
  background:var(--card);color:var(--ink)}
#gate-form input:focus,#gate-form select:focus,
#gate-enrich-form input:focus,#gate-enrich-form select:focus{
  outline:none;border-color:var(--gold)}
#gate-form .gate-row,#gate-enrich-form .gate-row{
  display:grid;grid-template-columns:1fr 1fr;gap:10px}
#gate-form .gate-row input,#gate-form .gate-row select,
#gate-enrich-form .gate-row input,#gate-enrich-form .gate-row select{margin-bottom:11px}
@media (max-width:480px){
  #gate-form .gate-row,#gate-enrich-form .gate-row{grid-template-columns:1fr}
}
#gate-form .locbtn,#gate-enrich-form .locbtn{margin:2px 0 12px;width:100%}
.gate-submit{width:100%;padding:13px;margin-top:6px;border:0;border-radius:12px;
  background:var(--gold-foil);color:#1a1508;font:700 14.5px/1 "IBM Plex Sans",sans-serif;
  cursor:pointer;letter-spacing:.02em}
.gate-submit:hover{opacity:.9}
.gate-note{font-size:11px;color:var(--ink-3);text-align:center;margin-top:10px;line-height:1.5}
#gate-enrich{background:var(--paper)}
#gate-enrich h3{font-size:20px}
#gate-enrich .gate-sub{margin-bottom:18px}
#gate-enrich-skip{width:100%;padding:11px;margin-top:8px;border:0;background:none;
  color:var(--ink-3);font:600 13.5px "IBM Plex Sans",sans-serif;cursor:pointer;
  border-radius:10px;transition:background .15s}
#gate-enrich-skip:hover{background:color-mix(in srgb,var(--ink) 6%,transparent);color:var(--ink)}
"""

# ---- Feature-gate modal HTML (injected before </body>) ----
GATE_HTML = """
<div id="gate-ov" hidden role="dialog" aria-modal="true" aria-labelledby="gate-title">
  <div id="gate-box">
    <button id="gate-close" aria-label="Close">&times;</button>
    <!-- Step 1: sign-in / subscribe -->
    <div id="gate-step1">
      <p class="eyebrow" style="margin:0 0 6px">Free access</p>
      <h3 id="gate-title">Sign in to use this feature</h3>
      <p class="gate-sub">Get live gold rate comparisons, calculators and daily alerts — free.</p>
      <button class="gate-google-btn" id="gate-gbtn" type="button">
        <svg width="20" height="20" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.1 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-3.59-13.46-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/><path fill="none" d="M0 0h48v48H0z"/></svg>
        Continue with Google
      </button>
      <div class="gate-or">or enter details</div>
      <form id="gate-form" autocomplete="on">
        <input name="name" type="text" placeholder="Full name *" required autocomplete="name">
        <input name="email" type="email" placeholder="Email address *" required autocomplete="email">
        <input name="phone" type="tel" placeholder="Mobile number" autocomplete="tel" value="+91 ">
        <button type="button" class="locbtn gate-locbtn">&#128205; Use my current location to autofill</button>
        <div class="gate-row">
          <input name="state" type="text" placeholder="State" autocomplete="address-level1">
          <input name="city" type="text" placeholder="City" autocomplete="address-level2">
        </div>
        <div class="gate-row">
          <input name="zip" type="text" placeholder="PIN code" inputmode="numeric" maxlength="10" autocomplete="postal-code">
          <input name="area" type="text" placeholder="Area (auto)" list="gate-areas" autocomplete="address-level3">
          <datalist id="gate-areas"></datalist>
        </div>
        <div class="gate-row">
          <select name="gender"><option value="">Gender</option><option>Male</option><option>Female</option><option>Other</option><option>Prefer not to say</option></select>
          <input name="age" type="number" placeholder="Age" min="18" max="100">
        </div>
        <button type="submit" class="gate-submit">Get Free Access &rarr;</button>
      </form>
      <p class="gate-note">No spam. Unsubscribe anytime. We never share your data.</p>
    </div>
    <!-- Step 2: enrich after Google sign-in -->
    <div id="gate-enrich" hidden>
      <p class="eyebrow" style="margin:0 0 6px">One more thing</p>
      <h3>Complete your profile</h3>
      <p class="gate-sub">Help us personalise your gold rate experience.</p>
      <form id="gate-enrich-form" autocomplete="on">
        <input name="phone" type="tel" placeholder="Mobile number" autocomplete="tel" value="+91 ">
        <button type="button" class="locbtn gate-locbtn">&#128205; Use my current location to autofill</button>
        <div class="gate-row">
          <input name="state" type="text" placeholder="State" autocomplete="address-level1">
          <input name="city" type="text" placeholder="City" autocomplete="address-level2">
        </div>
        <div class="gate-row">
          <input name="zip" type="text" placeholder="PIN code" inputmode="numeric" maxlength="10" autocomplete="postal-code">
          <input name="area" type="text" placeholder="Area (auto)" list="gate-enrich-areas" autocomplete="address-level3">
          <datalist id="gate-enrich-areas"></datalist>
        </div>
        <div class="gate-row">
          <select name="gender"><option value="">Gender</option><option>Male</option><option>Female</option><option>Other</option><option>Prefer not to say</option></select>
          <input name="age" type="number" placeholder="Age" min="18" max="100">
        </div>
        <button type="submit" class="gate-submit">Save &amp; Continue &rarr;</button>
        <button type="button" id="gate-enrich-skip">Skip for now</button>
      </form>
    </div>
  </div>
</div>
"""

# ---- Feature-gate JS (injected just before </body>, after SIGNUP_JS) ----
GATE_JS = r"""
<script>
(function(){
  var SB=window.GR_SB_URL||'', KEY=window.GR_SB_KEY||'';
  var GCID=window.GR_GCID||'';

  /* ---- Auth state ---- */
  function getUser(){try{return JSON.parse(localStorage.getItem('gr_user')||'null');}catch(e){return null;}}
  function setUser(u){try{localStorage.setItem('gr_user',JSON.stringify(u));}catch(e){}}
  function isAuthed(){var u=getUser();return !!(u&&(u.email||u.google_id));}

  /* ---- pending action to fire after auth ---- */
  var pendingCb=null;

  /* ---- modal elements ---- */
  var ov=document.getElementById('gate-ov');
  var step1=document.getElementById('gate-step1');
  var enrichDiv=document.getElementById('gate-enrich');
  var gform=document.getElementById('gate-form');
  var eform=document.getElementById('gate-enrich-form');

  function openGate(cb){
    pendingCb=cb||null;
    if(!ov)return;
    step1.hidden=false; enrichDiv.hidden=true;
    ov.hidden=false;
    document.body.style.overflow='hidden';
    var first=gform&&gform.querySelector('input[name="name"]');
    if(first)setTimeout(function(){first.focus();},80);
  }
  function closeGate(){
    if(!ov)return;
    ov.hidden=true;
    document.body.style.overflow='';
  }
  /* header chip - uses the shared markup from signup.js (which also owns the
     delegated "Sign out" handler) so the chip looks/behaves the same
     everywhere. */
  function showChip(u){
    var h=document.getElementById('hauth');if(!h)return;
    h.hidden=false;
    h.innerHTML=window.GR_CHIP_HTML?window.GR_CHIP_HTML(u):
      ('<span class="uchip">'+(u.name||u.email||'Signed in')+'</span>'+
       '<button type="button" class="signout-btn">Sign out</button>');
  }
  function afterAuth(user){
    setUser(user);
    closeGate();
    showChip(user);
    if(pendingCb){var fn=pendingCb;pendingCb=null;setTimeout(fn,50);}
  }

  /* ---- save subscriber via Supabase RPC ---- */
  function saveGate(payload){
    if(!SB||!KEY||!payload.email)return Promise.resolve();
    return fetch(SB+'/rest/v1/rpc/upsert_subscriber',{method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,'Authorization':'Bearer '+KEY},
      body:JSON.stringify({payload:payload})
    }).catch(function(){});
  }

  /* ---- close button / overlay click ---- */
  var cBtn=document.getElementById('gate-close');
  if(cBtn)cBtn.addEventListener('click',function(){pendingCb=null;closeGate();});
  if(ov)ov.addEventListener('click',function(e){if(e.target===ov){pendingCb=null;closeGate();}});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&ov&&!ov.hidden){pendingCb=null;closeGate();}});

  /* ---- PIN autofill + "use my location", scoped per-form (same behaviour
     as the main rate-alert form) so both gate-form and gate-enrich-form get
     automatic state/city/area from a PIN code or from geolocation. ---- */
  function wireLocation(form){
    if(!form)return;
    function F(n){return form.elements[n];}
    var zip=F('zip'),area=F('area');
    function cleanPO(n){return (n||'').replace(/\s+(S\.?O\.?|B\.?O\.?|H\.?O\.?)$/i,'').trim();}
    function pinLookup(force,preferArea){
      if(!zip)return;var v=(zip.value||'').trim();
      if(!/^[1-9]\d{5}$/.test(v))return;
      fetch('https://api.postalpincode.in/pincode/'+v)
        .then(function(r){return r.json();})
        .then(function(j){var d=j&&j[0];
          if(!d||d.Status!=='Success'||!d.PostOffice||!d.PostOffice.length)return;
          var po=d.PostOffice;
          var district=po[0].District||'';
          if(F('state')&&(force||!F('state').value.trim()))F('state').value=po[0].State;
          if(F('city')&&(force||!F('city').value.trim()))F('city').value=district;
          if(!area)return;
          /* Offer every locality in this PIN in the dropdown - one PIN covers
             several areas, so the user picks their exact one. */
          var names=[];po.forEach(function(p){var n=cleanPO(p.Name);
            if(n&&names.indexOf(n)<0)names.push(n);});
          var dl=document.getElementById(area.getAttribute('list'));
          if(dl){dl.innerHTML='';names.forEach(function(n){
            var o=document.createElement('option');o.value=n;dl.appendChild(o);});}
          if(!force&&area.value.trim())return;
          var pick='';
          if(preferArea){      /* match the GPS neighbourhood to a PO name */
            var pl=preferArea.toLowerCase();
            for(var i=0;i<names.length;i++){var nl=names[i].toLowerCase();
              if(nl===pl||nl.indexOf(pl)>=0||pl.indexOf(nl)>=0){pick=names[i];break;}}
            if(!pick)pick=preferArea;
          }
          if(!pick){         /* else first locality that isn't just the city */
            for(var k=0;k<names.length;k++){
              if(names[k].toLowerCase()!==district.toLowerCase()){pick=names[k];break;}}
          }
          if(!pick)pick=names[0]||'';
          if(pick)area.value=pick;
        }).catch(function(){});
    }
    function set(n,v,force){var el=F(n);
      if(el&&v&&(force||!el.value.trim()))el.value=v;}
    function useLocation(btn){
      if(!navigator.geolocation){alert('Location is not supported by this '+
        'browser - please type your address.');return;}
      var old=btn.textContent;btn.disabled=true;btn.textContent='Locating...';
      function restore(){btn.disabled=false;btn.textContent=old;}
      function jget(u){return fetch(u,{headers:{Accept:'application/json'}})
        .then(function(r){return r.ok?r.json():null;})
        .catch(function(){return null;});}
      navigator.geolocation.getCurrentPosition(function(pos){
        var la=pos.coords.latitude,lo=pos.coords.longitude;
        /* Nominatim gives the real PIN + neighbourhood for Indian addresses;
           BigDataCloud returns an empty postcode and repeats the city as the
           locality (the "Mumbai / Mumbai, no PIN" bug), so it's backup only. */
        Promise.all([
          jget('https://nominatim.openstreetmap.org/reverse?format=jsonv2'+
               '&zoom=18&addressdetails=1&lat='+la+'&lon='+lo),
          jget('https://api.bigdatacloud.net/data/reverse-geocode-client?'+
               'latitude='+la+'&longitude='+lo+'&localityLanguage=en')
        ]).then(function(res){
          var n=res[0],b=res[1];
          if(!n&&!b){restore();
            alert('Could not look up your location - please type your address.');
            return;}
          var a=(n&&n.address)||{};
          var city=a.city||a.town||a.municipality||a.village||
                   String(a.state_district||'').replace(/\s+district$/i,'')||
                   (b&&(b.city||b.locality))||'';
          var areaName=a.suburb||a.neighbourhood||a.quarter||a.city_district||'';
          var st=a.state||(b&&b.principalSubdivision)||'';
          var pin=String(a.postcode||(b&&b.postcode)||'').trim();
          set('state',st,true);
          set('city',city,true);
          if(pin)set('zip',pin,true);
          /* never echo the city straight back as the area */
          if(area&&areaName&&areaName.toLowerCase()!==String(city).toLowerCase())
            set('area',areaName,true);
          var v=(zip&&zip.value||'').trim();
          if(/^[1-9]\d{5}$/.test(v))pinLookup(true,areaName);
          btn.textContent='Location added';
          setTimeout(restore,2500);
        });
      },function(err){restore();
        alert(err&&err.code===1?'Location permission was denied. You can type '+
          'your address instead.':'Could not get your location - please type '+
          'your address.');},
       {enableHighAccuracy:true,timeout:12000,maximumAge:600000});
    }
    var ph=F('phone');
    if(ph){ph.addEventListener('focus',function(){
        if(!ph.value.trim())ph.value='+91 ';});
      ph.addEventListener('blur',function(){var v=ph.value.replace(/[^\d]/g,'');
        if(/^[6-9]\d{9}$/.test(v))ph.value='+91 '+v;});}
    if(zip){zip.addEventListener('input',function(){
        if(/^[1-9]\d{5}$/.test(zip.value.trim()))pinLookup();});
      zip.addEventListener('blur',pinLookup);}
    var lb=form.querySelector('.gate-locbtn');
    if(lb)lb.addEventListener('click',function(){useLocation(lb);});
  }
  wireLocation(gform);
  wireLocation(eform);

  /* ---- email/name form submit ---- */
  if(gform)gform.addEventListener('submit',function(e){
    e.preventDefault();
    var F=function(n){return gform.elements[n];};
    var email=(F('email').value||'').trim();
    var name=(F('name').value||'').trim();
    if(!email)return;
    var payload={email:email,name:name||null,
      phone:(F('phone').value||'').trim()||null,
      gender:(F('gender').value||null),
      age:parseInt(F('age').value||'')||null,
      state:(F('state').value||'').trim()||null,
      city:(F('city').value||'').trim()||null,
      zip:(F('zip').value||'').trim()||null,
      area:(F('area').value||'').trim()||null,
      signup_method:'form',signup_source:'gate_form'};
    saveGate(payload);
    afterAuth({email:email,name:name});
  });

  /* ---- enrich form (after Google) ---- */
  if(eform)eform.addEventListener('submit',function(e){
    e.preventDefault();
    var F=function(n){return eform.elements[n];};
    var u=getUser()||{};
    var payload={email:u.email,name:u.name||null,
      phone:(F('phone').value||'').trim()||null,
      gender:(F('gender').value||null),
      age:parseInt(F('age').value||'')||null,
      city:(F('city').value||'').trim()||null,
      state:(F('state').value||'').trim()||null,
      zip:(F('zip').value||'').trim()||null,
      area:(F('area').value||'').trim()||null,
      google_id:u.google_id||null,
      google_picture:u.picture||null,
      google_locale:u.locale||null,
      signup_source:'gate_google'};
    saveGate(payload);
    closeGate();
    if(pendingCb){var fn=pendingCb;pendingCb=null;setTimeout(fn,50);}
  });
  var skipBtn=document.getElementById('gate-enrich-skip');
  if(skipBtn)skipBtn.addEventListener('click',function(){
    closeGate();
    if(pendingCb){var fn=pendingCb;pendingCb=null;setTimeout(fn,50);}
  });

  /* ---- Google sign-in ----
     Two independent paths, both landing on the same applyGoogleUser():
     1. One Tap - a small corner prompt that appears on its own (best-effort;
        depends on FedCM/third-party cookies, so it can silently not appear
        in some browsers - that's fine, it's a bonus, not the only way in).
     2. The "Continue with Google" button - a plain OAuth popup via
        google.accounts.oauth2, which does NOT depend on FedCM and is the
        reliable path that always works when clicked. */
  function decode(jwt){try{return JSON.parse(decodeURIComponent(
    atob(jwt.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')).split('')
      .map(function(c){return '%'+('00'+c.charCodeAt(0).toString(16)).slice(-2);})
      .join('')));}catch(e){return null;}}

  function applyGoogleUser(p){
    if(!p||!p.email)return;
    var wasAuthed=isAuthed();
    var user={email:p.email,name:p.name||null,picture:p.picture||null,
      google_id:p.sub||null,locale:p.locale||null};
    // Save everything Google gives us right away; enrich step (below)
    // optionally adds phone/age/gender/location on top of this.
    saveGate({email:p.email,name:p.name||null,
      google_id:p.sub||null,google_picture:p.picture||null,
      google_locale:p.locale||null,
      signup_method:'google',signup_source:'gate_google'});
    setUser(user);
    if(pendingCb){
      // came from a gated click -> resume it right away, still offer the
      // enrich step in the (already open) modal
      if(step1)step1.hidden=true;
      if(enrichDiv)enrichDiv.hidden=false;
    }else if(!wasAuthed&&ov){
      // fresh sign-in via the auto One Tap popup -> gently open the modal
      // just to offer the optional enrich step (skippable)
      if(step1)step1.hidden=true;
      if(enrichDiv)enrichDiv.hidden=false;
      ov.hidden=false;
      document.body.style.overflow='hidden';
    }
    if(eform&&p.name){var n=eform.elements['name'];if(n)n.value=p.name;}
    showChip(user);
    resetGbtn();
  }

  function onGoogleCred(resp){          // One Tap JWT credential
    applyGoogleUser(resp&&resp.credential?decode(resp.credential):null);
  }

  var gbtn=document.getElementById('gate-gbtn');
  var gbtnHTML=gbtn?gbtn.innerHTML:'';
  var gbtnResetTimer=null;
  function resetGbtn(){
    if(gbtnResetTimer){clearTimeout(gbtnResetTimer);gbtnResetTimer=null;}
    if(gbtn){gbtn.disabled=false;gbtn.innerHTML=gbtnHTML;}
  }

  /* ---- ID client (One Tap). Initialised once, as early as possible. ---- */
  var idReady=false;
  function initIdClient(){
    if(idReady)return true;
    if(!GCID||!(window.google&&google.accounts&&google.accounts.id))return false;
    try{
      google.accounts.id.initialize({client_id:GCID,callback:onGoogleCred,
        auto_select:false,
        /* Don't treat a stray outside-click as a dismissal - repeated
           dismissals put One Tap into a multi-hour cooldown where it stops
           appearing at all, which is exactly the "it never pops up" symptom. */
        cancel_on_tap_outside:false,
        itp_support:true,use_fedcm_for_prompt:true});
      idReady=true;
    }catch(e){}
    return idReady;
  }

  /* ---- OAuth popup client (fallback for when One Tap can't show) ---- */
  var tokenClient=null;
  function getTokenClient(){
    if(tokenClient)return tokenClient;
    if(!GCID||!(window.google&&google.accounts&&google.accounts.oauth2))return null;
    tokenClient=google.accounts.oauth2.initTokenClient({
      client_id:GCID,scope:'openid email profile',
      callback:function(resp){
        if(!resp||resp.error||!resp.access_token){resetGbtn();return;}
        fetch('https://www.googleapis.com/oauth2/v3/userinfo',
          {headers:{Authorization:'Bearer '+resp.access_token}})
          .then(function(r){return r.json();})
          .then(function(profile){resetGbtn();applyGoogleUser(profile);})
          .catch(resetGbtn);
      }
    });
    return tokenClient;
  }

  /* Pre-warm BOTH clients from page load so the click handler never has to
     wait (browsers only grant a popup a few seconds of "user activation"
     after a real click). */
  (function warm(){
    var a=initIdClient(),b=!!getTokenClient();
    if(!a||!b)setTimeout(warm,150);
  })();

  /* Open the OAuth popup - the "not signed in to Google yet" path. */
  function openLoginPopup(){
    var tc=getTokenClient();
    if(!tc){resetGbtn();
      alert('Google sign-in is still loading - please try again in a moment.');
      return;}
    if(gbtn){gbtn.disabled=true;gbtn.textContent='Opening Google...';}
    tc.requestAccessToken({prompt:''});
    gbtnResetTimer=setTimeout(function(){
      resetGbtn();
      alert('The Google sign-in window could not open - please allow popups '+
        'for this site, or use the form below instead.');
    },8000);
  }

  /* Button: behave exactly like One Tap when the user already has a Google
     session (a small inline card - no popup, no page change); only fall back
     to the full login popup when One Tap can't be shown (no Google session,
     cooldown, or FedCM unavailable). The fallback runs inside prompt()'s
     notification callback, which fires within the click's user-activation
     window, so the popup is still allowed. */
  if(gbtn)gbtn.addEventListener('click',function(){
    if(!GCID){alert('Google sign-in is not configured.');return;}
    if(!initIdClient()){openLoginPopup();return;}
    var settled=false;
    try{
      google.accounts.id.prompt(function(n){
        if(settled)return;
        var skipped=false;
        try{
          /* FedCM only exposes isSkippedMoment/isDismissedMoment; the older
             isNotDisplayed exists on the legacy path. Guard both. */
          if(typeof n.isNotDisplayed==='function'&&n.isNotDisplayed())skipped=true;
          if(typeof n.isSkippedMoment==='function'&&n.isSkippedMoment())skipped=true;
        }catch(e){skipped=true;}
        if(skipped){settled=true;openLoginPopup();}
      });
    }catch(e){openLoginPopup();return;}
    /* If prompt() never reports back at all (some FedCM failures reject
       silently), fall back so the button is never a dead end. */
    setTimeout(function(){
      if(settled||isAuthed())return;
      settled=true;openLoginPopup();
    },1500);
  });

  /* ---- auto One Tap on page load ---- */
  (function autoOneTap(){
    if(!GCID||isAuthed())return;
    var tries=0;
    (function tryG(){
      if(initIdClient()){try{google.accounts.id.prompt();}catch(e){}}
      else if(tries++<40){setTimeout(tryG,150);}
    })();
  })();

  /* ---- FEATURE GATE: intercept gated elements ---- */
  function guard(el,originalHandler){
    if(!el)return;
    el.addEventListener('click',function(e){
      if(isAuthed())return;          // already signed in → let normal handler run
      e.preventDefault();
      e.stopImmediatePropagation();
      openGate(function(){
        // re-fire a clean click after auth so original listener handles it
        el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
      });
    },true);                         // capture phase → runs before page listeners
  }

  function guardInput(el){
    if(!el)return;
    el.addEventListener('focus',function(e){
      if(isAuthed())return;
      el.blur();
      openGate(function(){el.focus();});
    },true);
  }

  // Browsing (drawers, karat tabs, near-me/GST, calculators, brand search) is
  // intentionally NOT gated: analytics showed ~79% of people who hit a hard
  // sign-in wall here just left, and it blocked exactly the content Google
  // needs to index. guard()/guardInput()/openGate() stay defined so a future
  // "sign in" affordance can still reuse them - they're just not wired to
  // these elements any more. window.GR_OPENGATE exposes it if ever needed.
  window.GR_OPENGATE=openGate;

})();
</script>
"""


TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gold Rate Today $where ($date) - 24 Carat &amp; 22K Gold Rate, Compare Top Jewellers</title>
<meta name="description" content="Gold rate today $where ($date): 24 carat gold rate $med24/g and 22K gold rate $med22/g pre-GST, compared across $n_brands top jewellers. Check the IBJA bullion premium, MCX futures, and calculate gold prices instantly.">
<meta name="keywords" content="gold rate, gold rate today, today gold rate, 24 carat gold rate today, gold rate today 22k, gold rate today Hyderabad, gold rate today Chennai, gold rate today Pune, gold rate today Mumbai">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="theme-color" content="#0B0805">
<meta name="author" content="MyGoldRates.com">
<meta name="geo.region" content="IN">
<link rel="canonical" href="$canonical_url">
<link rel="alternate" type="application/json" title="Gold rates JSON feed" href="$site_url/rates.json">
<link rel="icon" href="$site_url/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="96x96" href="$site_url/icon-96.png">
<link rel="icon" type="image/png" sizes="48x48" href="$site_url/icon-48.png">
<link rel="icon" type="image/svg+xml" href="$site_url/favicon.svg">
<link rel="apple-touch-icon" href="$site_url/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="MyGoldRates.com">
<meta property="og:locale" content="en_IN">
<meta property="og:title" content="Gold Rate Today $where - Compare 24K, 22K &amp; 18K Across Top Jewellers">
<meta property="og:description" content="Today's gold rate compared across $n_brands top Indian jewellers: 24 carat $med24/g, 22K $med22/g. IBJA bullion premium plus an instant price calculator.">
<meta property="og:url" content="$canonical_url">
<meta property="og:image" content="$site_url/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="MyGoldRates.com - India's gold rate comparison platform">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Gold Rate Today $where - Compare Top Jewellers">
<meta name="twitter:description" content="24 carat gold rate $med24/g, 22K $med22/g today. Compare jewellers, check the bullion premium, calculate prices.">
<meta name="twitter:image" content="$site_url/og.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;700&display=swap" rel="stylesheet">
$gsi
$ads_head
<script type="application/ld+json">$jsonld</script>
<style>
$base_css
$gate_css
/* IBJA reference tiles */
.ibja-ref{margin-top:6px}
.ref-tiles{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px}
.rtile{flex:1;min-width:150px;background:var(--card);
  border:1px solid var(--line);border-radius:12px;padding:16px 20px;
  position:relative;overflow:hidden}
.rtile::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;
  background:var(--gold-foil)}
.rtile .k{font:500 11.5px/1 "IBM Plex Mono",monospace;letter-spacing:.16em;
  text-transform:uppercase;color:var(--ink-3)}
.rtile .v{font-family:"IBM Plex Mono",monospace;font-size:clamp(20px,3vw,26px);
  margin:6px 0 3px;color:var(--gold)}
.rtile .u{font-size:12px;color:var(--ink-3)}
.rtile.prem::before{background:var(--emerald)}
.rtile.prem .v{color:var(--emerald)}

/* live market pulse badge */
.live-badge{display:inline-flex;align-items:center;gap:7px;font:700 10.5px/1 "IBM Plex Mono",monospace;
  letter-spacing:.16em;text-transform:uppercase;color:#5BBB93;background:rgba(30,92,70,.28);
  border:1px solid rgba(91,187,147,.45);border-radius:999px;padding:5px 12px;margin-bottom:10px}
.live-dot{width:7px;height:7px;border-radius:50%;background:#5BBB93;
  box-shadow:0 0 8px #5BBB93;animation:livepulse 1.8s infinite ease-in-out}
@keyframes livepulse{
  0%{transform:scale(0.95);opacity:0.8;box-shadow:0 0 0 0 rgba(91,187,147,0.7)}
  70%{transform:scale(1.15);opacity:1;box-shadow:0 0 0 8px rgba(91,187,147,0)}
  100%{transform:scale(0.95);opacity:0.8;box-shadow:0 0 0 0 rgba(91,187,147,0)}
}

/* brand search box */
.brand-search-box{position:relative;flex:1 1 200px;max-width:280px}
.brand-search-box input{width:100%;font:500 13px "IBM Plex Sans",sans-serif;
  background:var(--card);color:var(--ink);border:1px solid var(--line);
  border-radius:999px;padding:8px 14px 8px 34px;transition:border-color .2s ease,box-shadow .2s ease}
.brand-search-box input:focus{border-color:var(--gold);outline:none;
  box-shadow:0 0 0 3px color-mix(in srgb,var(--gold) 20%,transparent)}
.brand-search-box::before{content:"🔍";position:absolute;left:11px;top:50%;
  transform:translateY(-50%);font-size:12px;opacity:.65;pointer-events:none}

/* quick weight pills */
.quick-weights{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 10px}
.qw-pill{font:600 11.5px/1 "IBM Plex Mono",monospace;background:var(--card);
  border:1px solid var(--line);color:var(--ink-2);border-radius:999px;
  padding:6px 12px;cursor:pointer;transition:all .15s ease}
.qw-pill:hover,.qw-pill.active{border-color:var(--gold);color:var(--gold);
  background:color-mix(in srgb,var(--gold) 12%,transparent)}

/* rate board hero */
.board{background:
  linear-gradient(104deg,transparent 0 40%,rgba(240,219,154,.08) 46%,
    rgba(255,253,244,.15) 50%,rgba(240,219,154,.08) 54%,transparent 61%),
  radial-gradient(130% 150% at 85% -35%,rgba(224,186,86,.42),transparent 58%),
  radial-gradient(120% 130% at 4% 135%,rgba(176,132,42,.28),transparent 58%),
  linear-gradient(150deg,#3A2A0C,#140D04 52%,#241809);
  color:#F0EAD8;border-radius:13px;margin:10px 0 8px;padding:14px 18px 12px;
  position:relative;overflow:hidden;border:1px solid rgba(224,186,86,.38);
  box-shadow:inset 0 1px 0 rgba(255,247,214,.10)}
.board h1{font-size:clamp(18px,2.6vw,24px);color:#F8EFD6;margin-bottom:0}
.board-meta{display:flex;align-items:center;flex-wrap:wrap;gap:6px 14px;
  margin:5px 0 8px;font-size:12px;color:#A79B7E}
.board-meta .signal{display:inline-flex;align-items:center;gap:5px;
  color:#5BBB93;font-weight:600;letter-spacing:.03em}
.board-meta .low-note{color:#CFC7AE}
.board-rates{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.tile{border:1px solid rgba(224,186,86,.34);border-radius:9px;
  padding:8px 12px;min-width:100px;flex:1;
  background:linear-gradient(158deg,rgba(224,186,86,.11),rgba(224,186,86,.02))}
.tile .k{font-family:"IBM Plex Mono",monospace;font-size:9.5px;
  letter-spacing:.14em;color:var(--gold-bright);text-transform:uppercase}
.tile .v{font-family:"IBM Plex Mono",monospace;font-size:clamp(16px,2.2vw,21px);
  margin-top:2px;background:linear-gradient(100deg,#E8C86A,#FFFDF4 46%,#D9B24A);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.tile .u{font-size:10px;color:#A79B7E}
.tile.best{background:linear-gradient(158deg,rgba(224,186,86,.26),rgba(224,186,86,.08));
  border:2px solid rgba(224,186,86,.6);flex:1.35;min-width:148px;
  box-shadow:0 0 20px rgba(224,186,86,.12)}
.tile.best .k{color:#F4E3A6;font-weight:700}
.tile.best .v{font-weight:700;font-size:clamp(18px,2.6vw,24px)}
.bwin{margin-top:5px;font-weight:700;font-size:12.5px;color:#F8EFD6;
  display:flex;align-items:center;gap:6px}
.bwin img{width:15px;height:15px;border-radius:3px;background:#fff;
  padding:1px;flex:0 0 15px}
.board-pregst{font-size:11px;color:#8A7E65;margin-top:6px}
.note{font-size:13px;color:var(--ink-3);margin:12px 0 24px}
.keyfacts{background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:16px 20px;margin:14px 0 4px}
.keyfacts h2{font-size:16px;margin:0 0 8px}
.keyfacts ul{margin:0;padding-left:18px}
.keyfacts li{font-size:13.5px;color:var(--ink-2);line-height:1.6;margin:3px 0}
.keyfacts strong{color:var(--ink)}
.seo{margin:40px 0 8px;max-width:74ch}
.seo h3{font-family:"Marcellus",serif;font-weight:400;font-size:19px;
  margin:24px 0 6px;color:var(--ink)}
.seo p{color:var(--ink-2);font-size:15px;line-height:1.72;margin:0 0 14px}
.seo strong{color:var(--ink);font-weight:600}
.seofold summary{cursor:pointer;list-style:none;display:flex;
  align-items:center;gap:12px}
.seofold summary::-webkit-details-marker{display:none}
.seofold summary h2{margin:0}
.seofold summary::after{content:"+";font:500 24px/1 "IBM Plex Mono",monospace;
  color:var(--gold);margin-left:auto}
.seofold[open] summary::after{content:"\\2212"}
.seofold summary:hover h2{color:var(--gold)}
.seofold>p:first-of-type{margin-top:14px}
.citylinks{margin:34px 0 8px}
.citycloud{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.citycloud a{font-size:12.5px;border:1px solid var(--line);
  border-radius:999px;padding:6px 13px;text-decoration:none;
  color:var(--ink-2);white-space:nowrap}
.citycloud a:hover{border-color:var(--gold);color:var(--gold)}
.citycloud a[aria-current="page"]{border-color:var(--gold);
  color:var(--gold);font-weight:600}
.newscard{display:block;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:14px 16px;margin:9px 0;text-decoration:none}
.newscard:hover{border-color:var(--gold)}
.newscard .nt{font-weight:600;color:var(--ink);font-size:14.5px;line-height:1.4}
.newscard .nd{font:500 11.5px/1 "IBM Plex Mono",monospace;color:var(--ink-3);
  margin-top:5px}
.recap-move{font-family:"IBM Plex Mono",monospace;font-weight:600}

/* calculator */
.calc{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start}
@media (max-width:720px){.calc{grid-template-columns:1fr}}
.calc-fields{display:grid;gap:14px}
.field label{display:block;font:500 12px/1.4 "IBM Plex Mono",monospace;
  letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);
  margin-bottom:6px}
.field input,.field select{width:100%;font:15px "IBM Plex Sans",sans-serif;
  color:var(--ink);background:var(--paper);border:1px solid var(--line);
  border-radius:10px;padding:12px 14px}
.seg{display:flex;gap:0;border:1px solid var(--line);border-radius:10px;
  overflow:hidden}
.seg button{flex:1;font:500 13.5px "IBM Plex Mono",monospace;background:none;
  border:0;padding:11px 0;color:var(--ink-2);cursor:pointer;
  border-right:1px solid var(--line)}
.seg button:last-child{border-right:0}
.seg button[aria-pressed="true"]{background:var(--board);color:#F0DB9A}
.calc-out{background:
  radial-gradient(140% 150% at 90% -30%,rgba(224,186,86,.34),transparent 58%),
  radial-gradient(120% 130% at 4% 130%,rgba(176,132,42,.22),transparent 58%),
  linear-gradient(150deg,#3A2A0C,#140D04 55%,#241809);
  border:1px solid rgba(224,186,86,.42);border-radius:14px;
  padding:26px 26px 22px;color:#EDE9DD;min-height:100%}
.calc-out .k{font-family:"IBM Plex Mono",monospace;font-size:11.5px;
  letter-spacing:.22em;text-transform:uppercase;color:var(--gold-bright)}
.calc-out .v{font-family:"IBM Plex Mono",monospace;
  font-size:clamp(30px,5vw,44px);margin:10px 0 4px;
  background:linear-gradient(100deg,#F0DB9A,#FFFDF4 45%,#E8C86A);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.calc-out .sub{font-size:13px;color:#8E9A8C}
.calc-out .split{margin-top:16px;padding-top:14px;
  border-top:1px solid rgba(217,178,74,.25);display:grid;gap:6px;
  font-family:"IBM Plex Mono",monospace;font-size:13px;color:#B9C2B4}
.calc-out .split div{display:flex;justify-content:space-between}
.calc-out .split .amt{color:#EDE9DD}

/* premium bars */
.pbar-card{display:flex;flex-direction:column;gap:11px}
.pbar-row{display:flex;align-items:center;gap:12px;width:100%}
.pbar-name{flex:0 0 clamp(110px,26vw,170px);font-size:13.5px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pbar-track{flex:1 1 auto;min-width:0;height:12px;border-radius:6px;
  background:color-mix(in srgb,var(--line) 55%,transparent);overflow:hidden}
.pbar-fill{display:block;height:100%;border-radius:6px 4px 4px 6px;
  background:linear-gradient(90deg,color-mix(in srgb,var(--bar) 70%,transparent),var(--bar));
  transition:width .5s ease}
.pbar-neg{background:linear-gradient(90deg,color-mix(in srgb,var(--emerald) 70%,transparent),var(--emerald))}
.pbar-val{flex:0 0 52px;font-family:"IBM Plex Mono",monospace;
  font-size:12.5px;text-align:right;color:var(--ink-2)}
@media (max-width:420px){
  .pbar-row{flex-wrap:wrap;row-gap:5px}
  .pbar-name{flex:1 1 100%}
  .pbar-track{flex:1 1 auto}
}

/* table */
.tablebar{display:flex;justify-content:space-between;align-items:center;
  flex-wrap:wrap;gap:10px;margin-bottom:12px}
.gst{font:500 12px/1 "IBM Plex Mono",monospace;letter-spacing:.06em;
  background:none;border:1px solid var(--line);color:var(--ink-2);
  border-radius:999px;padding:8px 15px;cursor:pointer}
.gst[aria-pressed="true"]{border-color:var(--gold);color:var(--gold)}
.tablecard{background:var(--card);border:1px solid var(--line);
  border-radius:14px;overflow:auto}
table{width:100%;border-collapse:collapse;min-width:640px}
thead th{font:500 12px/1.3 "IBM Plex Mono",monospace;text-transform:uppercase;
  letter-spacing:.12em;color:var(--ink-3);text-align:right;
  padding:14px 16px;border-bottom:1px solid var(--line);cursor:pointer;
  user-select:none;white-space:nowrap}
thead th:first-child{text-align:left}
thead th[aria-sort]::after{content:" ↕";opacity:.5}
thead th[aria-sort="ascending"]::after{content:" ↑";opacity:1}
thead th[aria-sort="descending"]::after{content:" ↓";opacity:1}
tbody th{font-weight:500;text-align:left;padding:12px 16px;white-space:nowrap}
tbody td{font-family:"IBM Plex Mono",monospace;font-size:14.5px;
  text-align:right;padding:12px 16px;font-variant-numeric:tabular-nums;
  white-space:nowrap}
tbody tr{border-bottom:1px solid var(--line)}
tbody tr:last-child{border-bottom:0}
tbody tr:hover{background:color-mix(in srgb,var(--gold) 6%,transparent)}
.delta-low{color:var(--emerald)}
.delta-high{color:var(--warm)}
.delta-par{color:var(--ink-3)}
.tbar-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.karatseg{display:none}
.karatseg button{font:600 12px/1 "IBM Plex Mono",monospace;letter-spacing:.05em;
  background:none;border:1px solid var(--line);color:var(--ink-2);
  padding:8px 14px;cursor:pointer}
.karatseg button:first-child{border-radius:999px 0 0 999px}
.karatseg button:last-child{border-radius:0 999px 999px 0}
.karatseg button+button{border-left:0}
.karatseg button[aria-pressed="true"]{border-color:var(--gold);color:var(--gold);
  background:color-mix(in srgb,var(--gold) 12%,transparent)}
/* markets side drawer */
.calc-drawer{grid-template-columns:1fr!important}
.drawer-tab{position:fixed;right:0;top:calc(50% - 175px);z-index:940;writing-mode:vertical-rl;
  text-orientation:mixed;font:600 12px/1 "IBM Plex Mono",monospace;
  letter-spacing:.14em;text-transform:uppercase;color:#1A1508;
  background:var(--gold-foil);border:0;border-radius:9px 0 0 9px;
  padding:15px 9px;cursor:pointer;box-shadow:0 2px 12px rgba(0,0,0,.28)}
.drawer-tab.drawer-tab2{top:calc(50% - 37px)}
.drawer-tab.drawer-tab3{top:calc(50% + 136px)}
.drawer-ov{position:fixed;inset:0;background:rgba(10,8,4,.5);z-index:950}
.drawer{position:fixed;top:0;right:0;height:100%;width:min(440px,94vw);
  background:var(--paper);border-left:1px solid var(--line);z-index:960;
  transform:translateX(105%);transition:transform .28s ease;
  overflow-y:auto;padding:20px 22px 34px}
.drawer.open{transform:translateX(0)}
.drawer-head{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:4px}
.drawer-head h2{margin:0;font-size:22px}
.drawer-x{background:none;border:0;font-size:28px;color:var(--ink-3);
  cursor:pointer;line-height:1;padding:2px 6px}
.drawer h3{font-family:"Marcellus",serif;font-weight:400;font-size:18px;
  margin:22px 0 4px}
.dnote{font-size:12.5px;color:var(--ink-3);margin:0 0 10px;line-height:1.55}
.dtable{width:100%;border-collapse:collapse;min-width:0}
.dtable th{font:500 10.5px/1.3 "IBM Plex Mono",monospace;
  text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);
  text-align:right;padding:8px 6px;border-bottom:1px solid var(--line);
  cursor:default}
.dtable th:first-child,.dtable td:first-child{text-align:left}
.dtable td{padding:9px 6px;text-align:right;
  font-family:"IBM Plex Mono",monospace;font-size:13px;
  border-bottom:1px solid var(--line);white-space:nowrap}
.dtable tr:last-child td{border-bottom:0}
.mex{display:block;font:400 10.5px/1.5 "IBM Plex Mono",monospace;
  color:var(--ink-3)}
.up{color:var(--emerald)}.dn{color:var(--warm)}
.drawer svg{width:100%;height:auto;display:block}
.drawer svg text{font:500 10.5px "IBM Plex Mono",monospace;fill:var(--ink-3)}
@media (max-width:640px){
  .karatseg{display:inline-flex}
  table{min-width:0}
  .tablecard{overflow:visible}
  #rates .col-22,#rates .col-18{display:none}
  #rates.k22 .col-24{display:none}
  #rates.k22 .col-22{display:table-cell}
  #rates.k18 .col-24{display:none}
  #rates.k18 .col-18{display:table-cell}
  thead th,tbody th,tbody td{padding:11px 9px}
  thead th{font-size:10.5px;letter-spacing:.05em;white-space:normal}
  tbody td{font-size:14px}
  tbody th{white-space:normal;font-size:13.5px;line-height:1.28}
  .bcell{gap:7px}
  .blogo{width:18px;height:18px;flex:0 0 18px}
  .stamp{margin-left:0;margin-top:4px;padding:2px 6px;font-size:9.5px}
  .bcell>span{display:flex;flex-direction:column;align-items:flex-start;gap:2px}
}

/* alerts CTA */
.cta{background:
  radial-gradient(130% 160% at 10% -30%,rgba(217,178,74,.2),transparent 55%),
  linear-gradient(160deg,var(--board),var(--board-2));
  border:1px solid rgba(217,178,74,.3);border-radius:16px;color:#EDE9DD;
  margin:38px 0 0;padding:30px 32px;display:flex;flex-wrap:wrap;
  align-items:center;gap:18px;justify-content:space-between}
.cta h2{color:#F6F1E3;margin:0 0 4px}
.cta p{color:#B9C2B4;font-size:14.5px;max-width:48ch}
.quick-sub{display:flex;gap:8px;flex:0 0 auto}
.quick-sub input{width:220px;max-width:60vw;padding:11px 14px;border-radius:10px;
  border:1px solid rgba(217,178,74,.35);background:rgba(255,255,255,.06);
  color:#F6F1E3;font-size:14px}
.quick-sub input::placeholder{color:#8b8676}
.quick-sub input:focus{outline:2px solid var(--gold);outline-offset:1px}
.qs-msg{font-size:13px;margin:8px 0 0;display:none}
.qs-msg.qs-ok{color:#9fd9a8}.qs-msg.qs-err{color:#e08a6a}
.qs-msg a{color:inherit;text-decoration:underline}
@media(max-width:560px){.quick-sub{flex-wrap:wrap;width:100%}
  .quick-sub input{width:100%;max-width:none}
  .quick-sub button{width:100%}}

.adslot{margin:30px 0;min-height:90px;border:1px dashed var(--line);
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  color:var(--ink-3);font-size:12px;letter-spacing:.08em}

/* brand logos */
/* rank column: subordinate to brand name (monospace, ink-3) so the eye reads
   brand first. Kept narrow so the table doesn't lose horizontal room. */
.col-rank{width:36px;text-align:center;
  font:600 12.5px/1 "IBM Plex Mono",monospace;color:var(--ink-3);
  font-variant-numeric:tabular-nums}
tbody tr:first-child .col-rank{color:var(--gold);font-weight:700}
@media(max-width:640px){.col-rank{width:24px;font-size:11.5px;padding-left:6px!important;padding-right:6px!important}}
.bcell{display:inline-flex;align-items:center;gap:10px}
.blogo{width:20px;height:20px;border-radius:5px;object-fit:contain;
  background:#fff;border:1px solid var(--line);padding:1px;flex:0 0 20px}


/* gold coin cursor trail */
.coin{position:fixed;border-radius:50%;pointer-events:none;z-index:1200;
  background:radial-gradient(circle at 35% 30%,#F7E7A9,#D9B24A 55%,#8C6A18);
  box-shadow:0 0 6px rgba(217,178,74,.55);
  animation:coinfall .9s ease-in forwards}
@keyframes coinfall{to{transform:translateY(48px) scale(.35);opacity:0}}

/* signup modal */
.overlay{position:fixed;inset:0;background:rgba(8,13,10,.66);display:none;
  align-items:center;justify-content:center;z-index:1000;padding:18px}
.overlay.open{display:flex}
.modal{background:var(--card);border:1px solid rgba(217,178,74,.45);
  border-radius:16px;max-width:560px;width:100%;max-height:92vh;
  overflow:auto;padding:28px;position:relative;
  box-shadow:0 24px 70px rgba(0,0,0,.4)}
.modal h2{margin:0 0 4px}
.modal .hint{margin-bottom:16px}
.modal-x{position:absolute;top:8px;right:12px;background:none;border:0;
  font-size:24px;line-height:1;color:var(--ink-3);cursor:pointer;padding:6px}
.modal-x:hover{color:var(--ink)}
.m-grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:520px){.m-grid2{grid-template-columns:1fr}}
.m-field{margin-bottom:13px}
.m-field label{display:block;font:500 11.5px/1.4 "IBM Plex Mono",monospace;
  letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);
  margin-bottom:5px}
.m-field input,.m-field select{width:100%;font:15px "IBM Plex Sans",sans-serif;
  color:var(--ink);background:var(--paper);border:1px solid var(--line);
  border-radius:10px;padding:11px 13px}
.m-field input:focus,.m-field select:focus{border-color:var(--gold);outline:none}
.consent{display:flex;gap:8px;align-items:flex-start;margin:4px 0 14px;
  font-size:11.5px;color:var(--ink-3);max-width:52ch}
.consent input{margin-top:2px;accent-color:var(--gold)}
.m-msg{border-radius:10px;padding:12px 14px;font-size:14px;margin-top:12px;
  display:none}
.m-ok{background:color-mix(in srgb,var(--emerald) 12%,transparent);
  color:var(--emerald);border:1px solid var(--emerald)}
.m-err{background:color-mix(in srgb,var(--warm) 12%,transparent);
  color:var(--warm);border:1px solid var(--warm)}
.hp{position:absolute;left:-9999px;opacity:0;height:0;overflow:hidden}

/* HUID Scanner & Verification Tool */
.huid-scanner-card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px;margin:24px 0;box-shadow:0 8px 30px rgba(0,0,0,.15)}
.huid-header{display:flex;gap:16px;align-items:flex-start;margin-bottom:20px}
.huid-icon{font-size:28px;background:color-mix(in srgb,var(--gold) 15%,transparent);border:1px solid var(--gold);border-radius:12px;width:52px;height:52px;display:flex;align-items:center;justify-content:center;flex:0 0 52px}
.huid-sub{margin:0;font-size:13.5px;color:var(--ink-2);line-height:1.5}
.huid-field label{display:block;font:600 12px/1.4 "IBM Plex Mono",monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:8px}
.huid-input-group{display:flex;gap:10px}
.huid-input-group input{flex:1;font:700 18px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink);background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
.huid-input-group input:focus{border-color:var(--gold);outline:none;box-shadow:0 0 0 3px color-mix(in srgb,var(--gold) 20%,transparent)}
.sample-huid-pills{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:12px}
.sample-label{font-size:12px;color:var(--ink-3);font-weight:500}
.huid-sample-btn{font:500 11.5px/1 "IBM Plex Mono",monospace;background:none;border:1px solid var(--line);color:var(--ink-2);border-radius:999px;padding:6px 12px;cursor:pointer}
.huid-sample-btn:hover{border-color:var(--gold);color:var(--gold)}

/* Verification Certificate Result Box */
.huid-certificate{background:linear-gradient(150deg,#1A140A,#0C0904 60%,#1F180B);border:1px solid rgba(224,186,86,.4);border-radius:14px;padding:22px;margin-top:20px;color:#F0EAD8}
.cert-header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;border-bottom:1px solid rgba(224,186,86,.25);padding-bottom:14px;margin-bottom:16px}
.cert-status{font:700 12px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:#5BBB93;background:rgba(30,92,70,.35);border:1px solid rgba(91,187,147,.45);border-radius:999px;padding:6px 14px}
.cert-id{font:700 16px/1 "IBM Plex Mono",monospace;letter-spacing:.14em;color:#F4E3A6}
.cert-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:20px}
.cert-tile{background:rgba(224,186,86,.06);border:1px solid rgba(224,186,86,.25);border-radius:10px;padding:14px}
.cert-tile .ck{font:500 10.5px/1 "IBM Plex Mono",monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--gold-bright)}
.cert-tile .cv{font:700 17px/1.3 "IBM Plex Sans",sans-serif;color:#FFFDF4;margin:6px 0 2px}
.cert-tile .cu{font-size:11.5px;color:#C4B99A}

/* Checklist */
.cert-checklist h4{margin:0 0 12px;font-size:14px;color:#F4E3A6}
.checklist-items{display:grid;gap:10px}
.cl-item{display:flex;gap:12px;align-items:flex-start}
.cl-check{width:22px;height:22px;border-radius:50%;background:#5BBB93;color:#0C0904;font-weight:700;display:flex;align-items:center;justify-content:center;flex:0 0 22px;font-size:13px}
.cl-item strong{color:#FFFDF4;font-size:13.5px}
.cl-item p{margin:2px 0 0;font-size:12px;color:#C4B99A;line-height:1.4}
.cert-calc-box{margin-top:18px;padding-top:14px;border-top:1px dashed rgba(224,186,86,.3);display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:12px}
.cc-row label{font-size:13px;color:#C4B99A;margin-right:10px}
.cc-input-wrap input{width:75px;font:700 15px "IBM Plex Mono",monospace;background:#0C0904;color:#FFFDF4;border:1px solid rgba(224,186,86,.4);border-radius:6px;padding:6px 10px;text-align:center}
.cc-result-total{font-size:14px;color:#C4B99A}
.cc-result-total strong{font-family:"IBM Plex Mono",monospace;font-size:20px;color:#F4E3A6;margin-left:6px}

.faq{border-bottom:1px solid var(--line);padding:14px 0}
.faq summary{font-weight:500;cursor:pointer;color:var(--ink)}
/* WhatsApp viral share button */
.wa-share-btn{display:inline-flex;align-items:center;gap:6px;background:#25D366;color:#fff!important;
  font:600 12px/1 "IBM Plex Sans",sans-serif;padding:7px 14px;border-radius:999px;text-decoration:none;
  box-shadow:0 3px 10px rgba(37,211,102,.25);transition:transform .2s ease,box-shadow .2s ease}
.wa-share-btn:hover{transform:translateY(-1px);box-shadow:0 5px 14px rgba(37,211,102,.35)}

.rank-badge{font:700 10px/1 "IBM Plex Mono",monospace;padding:3px 6px;border-radius:4px;margin-right:6px}
.rank-1{background:#D9B24A;color:#140D04}
.rank-2{background:#C0C0C0;color:#140D04}
.rank-3{background:#CD7F32;color:#FFF}
.save-pill{font:600 10px/1 "IBM Plex Mono",monospace;color:#5BBB93;background:rgba(30,92,70,.22);
  border:1px solid rgba(91,187,147,.35);padding:2px 6px;border-radius:4px;margin-left:6px}
</style>
</head>
<body>
$nav
<div class="wrap">

<header class="top">
  <button class="navtog" id="navtog" aria-label="Open menu" aria-expanded="false">&#9776;</button>
  <a class="brand" href="$site_url/" aria-label="MyGoldRates.com home"><svg class="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="grx" x1="4" y1="38" x2="36" y2="4" gradientUnits="userSpaceOnUse"><stop stop-color="#B07E12"/><stop offset=".55" stop-color="#E3BF63"/><stop offset="1" stop-color="#F4E3A6"/></linearGradient></defs><rect x="4.5" y="21" width="9" height="15" rx="1.6" fill="url(#grx)"/><rect x="16.5" y="12" width="9" height="24" rx="1.6" fill="url(#grx)"/><path d="M5 25.5 17 17 25 21 34 8.5" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M27.5 7.5 35 6.5 34.5 14" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="brand-text"><span class="wm">My<b>Gold</b>Rates<span class="tld">.com</span></span><span class="brand-tag">India&rsquo;s 1st gold rate comparison platform</span></span></a>
  <div class="topright">
    <span class="updated">Updated $date, $time</span>
    <span class="hauth" id="hauth" hidden></span>
    <a class="wa-share-btn" href="https://api.whatsapp.com/send?text=Check%20today%27s%20live%2024K%20and%2022K%20gold%20rates%20across%20all%20top%20jewellers%20on%20https%3A%2F%2Fmygoldrates.com" target="_blank" rel="noopener" aria-label="Share on WhatsApp"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12.012 2c-5.506 0-9.989 4.478-9.99 9.984 0 1.763.459 3.485 1.332 5.001l-1.417 5.176 5.297-1.39c1.464.798 3.116 1.218 4.775 1.219h.004c5.505 0 9.988-4.478 9.989-9.984 0-2.667-1.038-5.174-2.924-7.06-1.886-1.886-4.393-2.925-7.061-2.925zm0 1.666c4.588 0 8.324 3.736 8.325 8.324 0 2.224-.866 4.314-2.439 5.888-1.573 1.574-3.663 2.44-5.887 2.44h-.003c-1.428 0-2.834-.378-4.066-1.094l-.291-.17-3.142.823.838-3.061-.186-.296c-.787-1.252-1.202-2.7-1.202-4.185.001-4.588 3.737-8.325 8.326-8.326z"/></svg> Share</a>
    <a class="btn btn-lite" href="#cmp">Compare jewellers</a>
  </div>
</header>

<section class="board" aria-label="Today's gold rate summary">
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <div class="live-badge"><span class="live-dot"></span> LIVE &middot; $date</div>
    <h1 style="margin:0">Gold Rate Today $where</h1>
  </div>
  <div class="board-meta">
    <span class="signal">&#128994; Save up to &#8377;$spread24/g by picking the cheapest jeweller</span>
    <span class="low-note">Lowest: <strong style="color:#F4E3A6">$low_brand &#8377;$low24_raw/g</strong></span>
    <span>$n_brands brands compared</span>
  </div>
  <div class="board-rates">
    <div class="tile best"><div class="k">&#9733; Lowest 24K &middot; $low_brand</div>
      <div class="v">$low24</div>
      <div class="bwin">$low_logo<span style="font-size:11px;color:#A79B7E">best price today</span></div></div>
    <div class="tile"><div class="k">22K &middot; $low_brand</div>
      <div class="v">$low22</div></div>
    <div class="tile"><div class="k">18K &middot; $low_brand</div>
      <div class="v">$low18</div></div>
  </div>
  <div class="board-pregst">All rates per gram &middot; pre-GST &middot; $date</div>
</section>

$local_intro
<section aria-labelledby="cmp">
  <p class="eyebrow">Today's Board</p>
  <h2 id="cmp">Compare Gold Rates Across Jewellers</h2>
  <div class="tablebar">
    <p class="hint" style="margin:0">Sorted by today's 24K rate - tap a column
    to re-sort. On mobile, use the karat filter to switch purity.</p>
    <div class="tbar-controls">
      <div class="brand-search-box"><input id="brandsearch" type="search" placeholder="Search jeweller..." aria-label="Search jeweller"></div>
      <div class="karatseg" role="group" aria-label="Show karat">
        <button data-k="24" aria-pressed="true">24K</button>
        <button data-k="22" aria-pressed="false">22K</button>
        <button data-k="18" aria-pressed="false">18K</button>
      </div>
      <button class="gst" id="nearbtn">&#128205; Brands near me</button>
      <button class="gst" id="gstbtn" aria-pressed="false">+3% GST</button>
    </div>
  </div>
  <p class="region-note" id="region-note" hidden></p>
  <div class="tablecard">
  <table id="rates">
    <thead><tr>
      <th scope="col" class="col-rank" aria-label="Rank">#</th>
      <th scope="col">Jeweller</th>
      <th scope="col" class="col-24" aria-sort="ascending">24K / g</th>
      <th scope="col" class="col-22">22K / g</th>
      <th scope="col" class="col-18">18K / g</th>
      <th scope="col" class="col-delta">Δ vs median</th>
    </tr></thead>
    <tbody>
$rows
    </tbody>
  </table>
  </div>
</section>

$ads_unit

$ibja_section

<div class="cta" id="qs-cta">
  <div>
    <h2>Know today's cheapest rate before you leave home</h2>
    <p>One free email each morning - who's cheapest today, the bullion
    premium, and the market median. Takes five seconds, no password needed.</p>
    <p class="qs-msg qs-ok" id="qs-ok" hidden>You're in - see you tomorrow
    morning. <a href="#" class="js-alert">Add your city for local alerts too &rarr;</a></p>
    <p class="qs-msg qs-err" id="qs-err" hidden>Something went wrong - please
    try again, or <a href="#" class="js-alert">use the full form</a>.</p>
  </div>
  <form id="qs-form" class="quick-sub" novalidate>
    <input type="email" id="qs-email" name="email" required maxlength="120"
      placeholder="you@email.com" aria-label="Email address" autocomplete="email">
    <button class="btn btn-gold" type="submit" id="qs-btn">Get Free Alerts</button>
  </form>
</div>

$ads_unit

<section aria-labelledby="faqh">
  <p class="eyebrow">Know Your Gold</p>
  <h2 id="faqh">Gold Rate FAQs</h2>
$faq
</section>

$news_home

$seo_content

<section class="citylinks" aria-labelledby="cityh">
  <p class="eyebrow">Local Rates</p>
  <h2 id="cityh">Gold Rate Today by City &amp; State</h2>
  <p class="hint">National jewellery chains quote one board price across
  India, so today's rates apply wherever you shop. Pick your city or state
  for its dedicated page.</p>
  <div class="citycloud">$city_links</div>
</section>

<section class="keyfacts" id="keyfacts" aria-labelledby="kfh">
  <h2 id="kfh">Today's Gold Rate $where - Key Facts</h2>
  <ul>
    <li>The <strong>24K (999) gold rate today $where is $med24 per gram</strong>
    (median across $n_brands leading jewellers, pre-GST) on $date.</li>
    <li>The <strong>22K (916) gold rate today is $med22 per gram</strong> and the
    <strong>18K (750) rate is $med18 per gram</strong>.</li>
    <li>The <strong>lowest 24K gold rate today is $low24 per gram</strong>,
    offered by $low_brand.</li>
    <li>All rates are per gram in Indian Rupees, pre-GST; add 3% GST for the
    billed price. Making charges are extra. Source: MyGoldRates.com.</li>
  </ul>
</section>

$drawer
$calcdrawer
$coindrawer

<footer>
  <p id="terms"><strong>Disclaimer &amp; terms:</strong> Rates are indicative,
  compiled from each brand's published prices, and can change during the day.
  Always confirm the billed rate with the jeweller before purchase. This site
  does not provide investment advice. Data is provided for personal reference
  only; automated collection or redistribution is not permitted.</p>
  <div class="foot-nav">
    <a href="about.html">About</a>
    <a href="contact.html">Contact</a>
    <a href="terms.html">Terms of Service</a>
    <a href="privacy.html">Privacy Policy</a>
    <a href="inquiry.html">Daily alerts</a>
  </div>
  <p>© $year GoldRates - daily gold rate comparison for India.
  Rates updated daily; last updated $date.</p>
  <p class="hits" id="hits" hidden>👁 <span id="hitcount">—</span> visits</p>
</footer>

</div>

<div class="overlay" id="alert-overlay" role="dialog" aria-modal="true"
     aria-labelledby="m-title">
  <div class="modal">
    <button class="modal-x" id="m-close" aria-label="Close">×</button>
    <p class="eyebrow" style="margin-top:0">Add Your City</p>
    <h2 id="m-title">Get alerts for your city too</h2>
    <p class="hint">Just your email works. Add your city and we'll also flag
    when a jeweller near you is the cheapest. Free, unsubscribe any time.</p>
    <form id="m-form" novalidate>
      $google_btn
      <div class="manualbox" id="m-manual">
      <div class="m-field"><label for="m-name">Name</label>
        <input id="m-name" name="name" autocomplete="name" maxlength="80"></div>
      <div class="m-grid2">
        <div class="m-field"><label for="m-email">Email *</label>
          <input id="m-email" name="email" type="email" autocomplete="email"
          required maxlength="120"></div>
        <div class="m-field"><label for="m-phone">Phone</label>
          <input id="m-phone" name="phone" type="tel" autocomplete="tel"
          inputmode="tel" maxlength="20" value="+91 "
          placeholder="+91 98765 43210"></div>
      </div>
      <button type="button" class="locbtn" id="m-loc">&#128205; Use my current
      location to autofill address</button>
      <div class="m-grid2">
        <div class="m-field"><label for="m-country">Country</label>
          <select id="m-country" name="country" autocomplete="country-name">
            <option selected>India</option><option>United Arab Emirates</option>
            <option>United States</option><option>United Kingdom</option>
            <option>Singapore</option><option>Other</option>
          </select></div>
        <div class="m-field"><label for="m-state">State</label>
          <input id="m-state" name="state" autocomplete="address-level1"
          maxlength="60"></div>
      </div>
      <div class="m-grid2">
        <div class="m-field"><label for="m-city">City</label>
          <input id="m-city" name="city" autocomplete="address-level2"
          maxlength="60"></div>
        <div class="m-field"><label for="m-zip">PIN / ZIP</label>
          <input id="m-zip" name="zip" autocomplete="postal-code"
          inputmode="numeric" maxlength="10"></div>
      </div>
      <div class="m-field"><label for="m-area">Area / Locality</label>
        <input id="m-area" name="area" maxlength="80" list="m-areas"
        autocomplete="address-level3" placeholder="auto-fills from PIN">
        <datalist id="m-areas"></datalist></div>
      <div class="hp" aria-hidden="true">
        <label>Website<input name="website" tabindex="-1" autocomplete="off"></label>
      </div>
      <label class="consent"><input type="checkbox" name="offers" checked>
        <span>Also send me gold offers, festive-scheme alerts and buying
        guides by email. You can opt out any time.</span></label>
      <button class="btn btn-gold" type="submit" id="m-btn">Subscribe</button>
      </div>
      <div class="m-msg m-ok" id="mm-ok">You're in - see you tomorrow
      morning.</div>
      <div class="m-msg m-err" id="mm-err">Something went wrong - please try
      again.</div>
    </form>
  </div>
</div>

<script>
var BRANDS=$calc_brands;
var FRAC={"24K":24/24,"22K":22/24,"18K":18/24,"14K":14/24};
(function(){
  /* ---- sortable table + GST switch ---- */
  var table=document.getElementById('rates');
  var heads=(table && table.tHead && table.tHead.rows.length) ? table.tHead.rows[0].cells : null;
  var body=(table && table.tBodies.length) ? table.tBodies[0] : null;
  var gstOn=false;
  function fmt(n){
    var s=Math.round(n).toString(), out=s.slice(-3), rest=s.slice(0,-3);
    while(rest.length>2){out=rest.slice(-2)+','+out;rest=rest.slice(0,-2);}
    if(rest)out=rest+','+out;
    return '₹'+out;
  }
  function repaint(){
    if(!body)return;
    [].forEach.call(body.rows,function(r){
      for(var i=1;i<=3;i++){
        var td=r.cells[i], base=parseFloat(td.dataset.v);
        if(td)td.textContent=fmt(gstOn?base*1.03:base);
      }
    });
  }
  var gstbtn=document.getElementById('gstbtn');
  if(gstbtn){
    gstbtn.addEventListener('click',function(){
      gstOn=!gstOn;
      this.setAttribute('aria-pressed',gstOn?'true':'false');
      this.textContent=gstOn?'Showing incl. 3% GST':'Show incl. 3% GST';
      repaint();
    });
  }
  function sortBy(i,dir){
    if(!body)return;
    var rows=[].slice.call(body.rows);
    /* col 0 = rank (numeric data-v), col 1 = Jeweller name (localeCompare),
       cols 2..N = numeric data-v. After sort, renumber the rank cells so
       the "#" column always reflects the CURRENT ordering (e.g. sorting by
       22K makes rank 1 = cheapest 22K, not the original 24K rank). */
    rows.sort(function(a,b){
      if(i===1){return a.cells[1].textContent.localeCompare(b.cells[1].textContent)*dir;}
      return (parseFloat(a.cells[i].dataset.v)-parseFloat(b.cells[i].dataset.v))*dir;
    });
    rows.forEach(function(r){body.appendChild(r);});
    rows.forEach(function(r,idx){
      var rc=r.cells[0];
      if(rc){rc.textContent=idx+1; rc.dataset.v=idx+1;}
    });
  }
  if(heads){
    [].forEach.call(heads,function(h,i){
      h.addEventListener('click',function(){
        var cur=h.getAttribute('aria-sort');
        [].forEach.call(heads,function(x){x.removeAttribute('aria-sort');});
        var dir=cur==='ascending'?-1:1;
        h.setAttribute('aria-sort',dir===1?'ascending':'descending');
        sortBy(i,dir);
      });
    });
  }
  /* ---- karat filter (mobile) ---- */
  document.querySelectorAll('.karatseg button').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.karatseg button').forEach(function(x){
        x.setAttribute('aria-pressed','false');});
      b.setAttribute('aria-pressed','true');
      table.classList.remove('k22','k18');
      if(b.dataset.k==='22')table.classList.add('k22');
      else if(b.dataset.k==='18')table.classList.add('k18');
    });
  });
  /* ---- live brand search filter ---- */
  var bsearch=document.getElementById('brandsearch');
  if(bsearch){
    bsearch.addEventListener('input',function(){
      var q=this.value.toLowerCase().trim();
      [].forEach.call(body.rows,function(r){
        var name=r.cells[0].textContent.toLowerCase();
        r.style.display=name.indexOf(q)!==-1?'':'none';
      });
    });
  }
  /* ---- calculator quick weight pills ---- */
  document.querySelectorAll('.qw-pill').forEach(function(pill){
    pill.addEventListener('click',function(){
      document.querySelectorAll('.qw-pill').forEach(function(p){p.classList.remove('active');});
      pill.classList.add('active');
      var wInput=document.getElementById('c-w');
      if(wInput){
        wInput.value=pill.dataset.w;
        wInput.dispatchEvent(new Event('input',{bubbles:true}));
      }
    });
  });
  /* ---- "in my area": GPS -> state -> filter regional jewellers ---- */
  var nearOn=false, userState=null,
      nearbtn=document.getElementById('nearbtn'),
      rnote=document.getElementById('region-note');
  function rowVisible(r){var ds=r.getAttribute('data-states');
    return ds==='all'||r.classList.contains('region-show');}
  function updateBest(){
    if(!body)return;
    /* recompute the hero "Lowest 24K" over whatever rows are visible */
    var bestV=Infinity,name='',logo='';
    [].forEach.call(body.rows,function(r){
      if(!rowVisible(r))return;
      var c=r.querySelector('td.col-24');if(!c)return;
      var v=parseFloat(c.dataset.v);
      if(v<bestV){bestV=v;name=r.getAttribute('data-brand')||'';
        logo=r.getAttribute('data-logo')||'';}
    });
    var vEl=document.querySelector('.tile.best .v'),
        bw=document.querySelector('.bwin');
    if(vEl&&isFinite(bestV))vEl.textContent=fmt(bestV);
    if(bw)bw.innerHTML=name+(logo?' <img src="'+logo+'" alt="">':'');
  }
  function applyRegion(){
    if(!body)return 0;
    var shown=0;
    [].forEach.call(body.rows,function(r){
      var ds=r.getAttribute('data-states');
      if(!ds||ds==='all')return;             /* national: always visible */
      var serves=nearOn&&userState&&ds.split('|').indexOf(userState)>=0;
      r.classList.toggle('region-show',serves);
      if(serves)shown++;
    });
    updateBest();                           /* lowest may now be a local store */
    return shown;
  }
  if(nearbtn){
    nearbtn.addEventListener('click',function(){
      if(nearOn){nearOn=false;nearbtn.setAttribute('aria-pressed','false');
        nearbtn.textContent='📍 Brands near me';if(rnote)rnote.hidden=true;
        applyRegion();return;}
      if(!navigator.geolocation){alert('Location is not supported here.');return;}
      nearbtn.textContent='Locating...';
      navigator.geolocation.getCurrentPosition(function(pos){
        fetch('https://api.bigdatacloud.net/data/reverse-geocode-client?latitude='+
          pos.coords.latitude+'&longitude='+pos.coords.longitude+
          '&localityLanguage=en')
        .then(function(r){return r.json();}).then(function(d){
          userState=d.principalSubdivision||'';
          nearOn=true;nearbtn.setAttribute('aria-pressed','true');
          nearbtn.textContent='📍 Brands in '+(userState||'My area');
          var n=applyRegion();
          if(rnote){
            rnote.textContent=(n?('Now showing '+n+' local jeweller'+(n>1?'s':'')+
              ' in '+userState):('No local jewellers we track in '+
              (userState||'your area')+' yet'))+' - national brands are always '+
              'shown. Tap again to hide local jewellers.';
            rnote.hidden=false;
          }
        }).catch(function(){nearbtn.textContent='📍 Brands near me';
          alert('Could not detect your area.');});
      },function(){nearbtn.textContent='📍 Brands near me';
        alert('Location permission denied.');},
       {enableHighAccuracy:false,timeout:12000,maximumAge:600000});
    });
  }
  /* ---- markets drawer ---- */
  var drw=document.getElementById('mdrawer'),
      drov=document.getElementById('drov'),
      drtab=document.getElementById('drtab');
  if(drw&&drtab){
    var drSet=function(open){
      drw.classList.toggle('open',open);
      if(drov)drov.hidden=!open;
      drtab.setAttribute('aria-expanded',open?'true':'false');
      drw.setAttribute('aria-hidden',open?'false':'true');
    };
    drtab.addEventListener('click',function(){
      drSet(!drw.classList.contains('open'));});
    var drx=document.getElementById('drx');
    if(drx)drx.addEventListener('click',function(){drSet(false);});
    if(drov)drov.addEventListener('click',function(){drSet(false);});
    document.addEventListener('keydown',function(e){
      if(e.key==='Escape'&&drw.classList.contains('open'))drSet(false);});
  }
  /* calculators drawer */
  var cdw=document.getElementById('cdrawer'),
      cdov=document.getElementById('cdov'),cdtab=document.getElementById('cdtab');
  if(cdw&&cdtab){
    var cdSet=function(o){cdw.classList.toggle('open',o);if(cdov)cdov.hidden=!o;
      cdtab.setAttribute('aria-expanded',o?'true':'false');
      cdw.setAttribute('aria-hidden',o?'false':'true');};
    cdtab.addEventListener('click',function(){
      cdSet(!cdw.classList.contains('open'));});
    var cdx=document.getElementById('cdx');
    if(cdx)cdx.addEventListener('click',function(){cdSet(false);});
    if(cdov)cdov.addEventListener('click',function(){cdSet(false);});
    document.addEventListener('keydown',function(e){
      if(e.key==='Escape'&&cdw.classList.contains('open'))cdSet(false);});
  }
  /* gold coins drawer */
  var coindw=document.getElementById('coindrawer'),
      coindov=document.getElementById('coindov'),
      coindtab=document.getElementById('coindtab');
  if(coindw&&coindtab){
    var coindSet=function(o){coindw.classList.toggle('open',o);coindov.hidden=!o;
      coindtab.setAttribute('aria-expanded',o?'true':'false');
      coindw.setAttribute('aria-hidden',o?'false':'true');};
    coindtab.addEventListener('click',function(){
      coindSet(!coindw.classList.contains('open'));});
    var coindx=document.getElementById('coindx');
    if(coindx)coindx.addEventListener('click',function(){coindSet(false);});
    if(coindov)coindov.addEventListener('click',function(){coindSet(false);});
    document.addEventListener('keydown',function(e){
      if(e.key==='Escape'&&coindw.classList.contains('open'))coindSet(false);});
  }

  /* ---- calculator ---- */
  var sel=document.getElementById('c-b'), w=document.getElementById('c-w');
  if(sel && typeof BRANDS !== 'undefined' && BRANDS.length){
    BRANDS.forEach(function(b,i){
      var o=document.createElement('option');
      o.value=i;o.textContent=b.name;sel.appendChild(o);
    });
  }
  var purity='24K', gst=false;
  function calc(){
    if(!w || !sel || typeof BRANDS === 'undefined' || !BRANDS.length) return;
    var grams=parseFloat(w.value)||0;
    var idx=parseInt(sel.value,10)||0;
    var b=BRANDS[idx]||BRANDS[0];
    if(!b) return;
    var rate=b.r24*({'24K':24/24,'22K':22/24,'18K':18/24,'14K':14/24}[purity]||1.0);
    var goldVal=rate*grams, gstAmt=goldVal*0.03;
    var total=gst?goldVal+gstAmt:goldVal;
    var cTitle=document.getElementById('c-title'),
        cTotal=document.getElementById('c-total'),
        cBasis=document.getElementById('c-basis'),
        cRate=document.getElementById('c-rate'),
        cGold=document.getElementById('c-gold'),
        cGst=document.getElementById('c-gst');
    if(cTitle)cTitle.textContent=grams+' g · '+purity+' · '+b.name;
    if(cTotal)cTotal.textContent=fmt(total);
    if(cBasis)cBasis.textContent=gst?'including 3% GST, excluding making charges':'pre-GST, excluding making charges';
    if(cRate)cRate.textContent=fmt(rate)+'/g';
    if(cGold)cGold.textContent=fmt(goldVal);
    if(cGst)cGst.textContent=gst?fmt(gstAmt):'not applied';
  }
  if(w)w.addEventListener('input',calc);
  if(sel)sel.addEventListener('change',calc);
  document.querySelectorAll('[data-p]').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('[data-p]').forEach(function(x){x.setAttribute('aria-pressed','false');});
      b.setAttribute('aria-pressed','true');purity=b.dataset.p;calc();
    });
  });
  document.querySelectorAll('[data-g]').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('[data-g]').forEach(function(x){x.setAttribute('aria-pressed','false');});
      b.setAttribute('aria-pressed','true');gst=b.dataset.g==='1';calc();
    });
  });

  /* ---- Gold Calculator (reverse: budget in, grams out) ---- */
  /* Same BRANDS list as the price calc, scored the other way:
     grams = budget / (rate * (1 + making%) * (1 + GST_if_on)). Making %
     is user-typed - the multi-brand comparison at /budget-gold-calculator
     is where our verified per-brand medians drive the picture. */
  var gcSel=document.getElementById('gc-brand'),
      gcBudget=document.getElementById('gc-b'),
      gcMc=document.getElementById('gc-m'),
      gcCustomRow=document.getElementById('gc-custom-row'),
      gcCustom=document.getElementById('gc-custom'),
      gcCustomK=document.getElementById('gc-custom-k');
  if(gcSel && typeof BRANDS !== 'undefined' && BRANDS.length){
    BRANDS.forEach(function(b,i){
      var o=document.createElement('option');
      o.value=i;o.textContent=b.name;gcSel.appendChild(o);
    });
    /* Custom-rate option: user's own jeweller quote, not on our tracked list.
       The rate is treated as the price for whatever purity is selected, so we
       infer the 24K anchor by dividing by the purity fraction - keeps the
       downstream maths identical to a normal BRANDS entry. */
    var oc=document.createElement('option');
    oc.value='__custom__';oc.textContent='✎ Custom rate (your jeweller)';
    gcSel.appendChild(oc);
  }
  var gcPurity='24K', gcGst=true;
  var FRAC_GC={'24K':24/24,'22K':22/24,'18K':18/24,'14K':14/24};
  function gcCalc(){
    if(!gcBudget || !gcSel) return;
    var isCustom=gcSel.value==='__custom__';
    var budget=parseFloat(gcBudget.value)||0;
    var mcPct=Math.max(0, Math.min(60, parseFloat(gcMc.value)||0));
    var frac=FRAC_GC[gcPurity]||1.0;
    var r24, brandName;
    if(isCustom){
      var custom=parseFloat(gcCustom.value)||0;
      if(custom<=0){return;}
      r24=custom/frac; brandName='Your quote';
    } else {
      if(typeof BRANDS==='undefined'||!BRANDS.length)return;
      var idx=parseInt(gcSel.value,10)||0;
      var b=BRANDS[idx]||BRANDS[0]; if(!b)return;
      r24=b.r24; brandName=b.name;
    }
    if(budget<=0) return;
    var rate=r24*frac;
    var cpg=rate*(1+mcPct/100)*(gcGst?1.03:1);
    var grams=cpg>0?budget/cpg:0;
    var goldVal=rate*grams;
    var mcVal=goldVal*(mcPct/100);
    var gstVal=gcGst?(goldVal+mcVal)*0.03:0;
    var t=document.getElementById('gc-title'),
        gr=document.getElementById('gc-grams'),
        ba=document.getElementById('gc-basis'),
        rt=document.getElementById('gc-rate'),
        gv=document.getElementById('gc-gold'),
        mv=document.getElementById('gc-mc'),
        gs=document.getElementById('gc-gst');
    if(t)t.textContent='₹'+Math.round(budget).toLocaleString('en-IN')+' · '+gcPurity+' · '+brandName;
    if(gr)gr.textContent=(grams<10?grams.toFixed(2):grams.toFixed(1))+' g';
    if(ba)ba.textContent=(gcGst?'incl. 3% GST':'pre-GST')+', making @ '+mcPct+'%';
    if(rt)rt.textContent=fmt(rate)+'/g';
    if(gv)gv.textContent=fmt(goldVal);
    if(mv)mv.textContent=mcPct>0?fmt(mcVal):'not applied';
    if(gs)gs.textContent=gcGst?fmt(gstVal):'not applied';
  }
  /* Reveal the custom-rate input only when 'Custom rate' is selected, and
     mirror the current purity into the input's label so the user sees exactly
     which karat they're typing for ('Your jeweller's 22K rate'). */
  function gcSyncCustom(){
    var isCustom=gcSel && gcSel.value==='__custom__';
    if(gcCustomRow) gcCustomRow.hidden=!isCustom;
    if(gcCustomK) gcCustomK.textContent=gcPurity;
  }
  if(gcBudget)gcBudget.addEventListener('input',gcCalc);
  if(gcMc)gcMc.addEventListener('input',gcCalc);
  if(gcCustom)gcCustom.addEventListener('input',gcCalc);
  if(gcSel)gcSel.addEventListener('change',function(){gcSyncCustom();gcCalc();});
  document.querySelectorAll('[data-gp]').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('[data-gp]').forEach(function(x){x.setAttribute('aria-pressed','false');});
      b.setAttribute('aria-pressed','true');gcPurity=b.dataset.gp;gcSyncCustom();gcCalc();
    });
  });
  document.querySelectorAll('[data-gg]').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('[data-gg]').forEach(function(x){x.setAttribute('aria-pressed','false');});
      b.setAttribute('aria-pressed','true');gcGst=b.dataset.gg==='1';gcCalc();
    });
  });
  document.querySelectorAll('[data-gb]').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('[data-gb]').forEach(function(x){x.classList.remove('active');});
      b.classList.add('active');
      if(gcBudget){gcBudget.value=b.dataset.gb;gcCalc();}
    });
  });
  gcSyncCustom();
  gcCalc();

  /* ---- Middle Class Persona: Jewellery Final Bill Estimator JS ---- */
  var bcKarat=document.getElementById('bc-karat'),
      bcWeight=document.getElementById('bc-weight'),
      bcMaking=document.getElementById('bc-making'),
      bbWtLbl=document.getElementById('bb-wt-lbl'),
      bbRateLbl=document.getElementById('bb-rate-lbl'),
      bbGoldTot=document.getElementById('bb-gold-tot'),
      bbMPct=document.getElementById('bb-m-pct'),
      bbMakingTot=document.getElementById('bb-making-tot'),
      bbGstTot=document.getElementById('bb-gst-tot'),
      bbGrandTot=document.getElementById('bb-grand-tot');

  function updateBillCalc(){
    if(!bcKarat||!bcWeight||!bcMaking)return;
    var k=bcKarat.value||'22K';
    var w=parseFloat(bcWeight.value)||10;
    var mPct=parseFloat(bcMaking.value)||12;

    var base24 = parseInt("$low24_num", 10) || 14467;
    var rate = Math.round(base24 * ({'24K':24/24, '22K':22/24, '18K':18/24, '14K':14/24}[k] || 22/24));

    var goldCost=w*rate;
    var makingCost=goldCost*(mPct/100);
    var subtotal=goldCost+makingCost;
    var gstCost=subtotal*0.03;
    var grandTotal=subtotal+gstCost;

    if(bbWtLbl)bbWtLbl.textContent=w+'g';
    if(bbRateLbl)bbRateLbl.textContent='₹'+rate.toLocaleString('en-IN')+'/g';
    if(bbGoldTot)bbGoldTot.textContent='₹'+Math.round(goldCost).toLocaleString('en-IN');
    if(bbMPct)bbMPct.textContent=mPct+'%';
    if(bbMakingTot)bbMakingTot.textContent='₹'+Math.round(makingCost).toLocaleString('en-IN');
    if(bbGstTot)bbGstTot.textContent='₹'+Math.round(gstCost).toLocaleString('en-IN');
    if(bbGrandTot)bbGrandTot.textContent='₹'+Math.round(grandTotal).toLocaleString('en-IN');
  }

  if(bcKarat)bcKarat.addEventListener('change',updateBillCalc);
  if(bcWeight)bcWeight.addEventListener('input',updateBillCalc);
  if(bcMaking)bcMaking.addEventListener('input',updateBillCalc);

  /* ---- Rich Persona: 24K Coin Weight Pills JS ---- */
  var coinPills=document.querySelectorAll('.coin-pill');
  var cpMmtc=document.getElementById('cp-mmtc'),
      cpTanishq=document.getElementById('cp-tanishq'),
      cpKalyan=document.getElementById('cp-kalyan'),
      cpMalabar=document.getElementById('cp-malabar'),
      cpSenco=document.getElementById('cp-senco'),
      cpJoyalukkas=document.getElementById('cp-joyalukkas');

  function updateCoinPrices(wt){
    var baseRate=parseInt("$low24_num", 10) || 14467;
    /* making-charge multipliers: gold cost + maker's % (pre-GST) */
    if(cpMmtc)cpMmtc.textContent='\u20b9'+(Math.round(wt*baseRate*1.025)).toLocaleString('en-IN');
    if(cpKalyan)cpKalyan.textContent='\u20b9'+(Math.round(wt*baseRate*1.030)).toLocaleString('en-IN');
    if(cpMalabar)cpMalabar.textContent='\u20b9'+(Math.round(wt*baseRate*1.032)).toLocaleString('en-IN');
    if(cpSenco)cpSenco.textContent='\u20b9'+(Math.round(wt*baseRate*1.035)).toLocaleString('en-IN');
    if(cpJoyalukkas)cpJoyalukkas.textContent='\u20b9'+(Math.round(wt*baseRate*1.038)).toLocaleString('en-IN');
    if(cpTanishq)cpTanishq.textContent='\u20b9'+(Math.round(wt*baseRate*1.040)).toLocaleString('en-IN');
  }

  coinPills.forEach(function(pill){
    pill.addEventListener('click',function(){
      coinPills.forEach(function(p){
        p.style.background='none';p.style.color='var(--ink-2)';p.style.border='1px solid var(--line)';
      });
      pill.style.background='var(--gold)';pill.style.color='#0C0904';pill.style.border='1px solid var(--gold)';
      var wt=parseFloat(pill.dataset.wt)||1;
      updateCoinPrices(wt);
    });
  });
  if(w && sel)calc();
  if(bcKarat)updateBillCalc();
  updateCoinPrices(1); /* init all coin prices on page load using live rate */

  /* ---- gold coin cursor trail ---- */
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches &&
     !matchMedia('(pointer: coarse)').matches){
    var lastCoin=0;
    document.addEventListener('mousemove',function(e){
      var now=Date.now(); if(now-lastCoin<55)return; lastCoin=now;
      var c=document.createElement('span'); c.className='coin';
      var s=5+Math.random()*7;
      c.style.width=s+'px'; c.style.height=s+'px';
      c.style.left=(e.clientX+(Math.random()*16-8))+'px';
      c.style.top=(e.clientY+4+(Math.random()*8))+'px';
      document.body.appendChild(c);
      setTimeout(function(){if(c.parentNode)c.parentNode.removeChild(c);},950);
    },{passive:true});
  }



  /* ---- BIS Hallmark & HUID Scanner Tool ---- */
  var hInput=document.getElementById('huid-input'),
      hBtn=document.getElementById('huid-scan-btn'),
      hResCode=document.getElementById('res-code'),
      hResKarat=document.getElementById('res-karat'),
      hResFineness=document.getElementById('res-fineness'),
      hResVal=document.getElementById('res-val'),
      hResUse=document.getElementById('res-use'),
      hStampText=document.getElementById('res-stamp-text'),
      hWeightInput=document.getElementById('huid-weight'),
      hCalcTotal=document.getElementById('huid-calc-total');

  var currentPerGram = 13265;

  function verifyHUID(code){
    if(!code)code=(hInput?hInput.value:'').trim().toUpperCase();
    if(!code)return;
    code=code.trim().toUpperCase();
    if(hInput)hInput.value=code;

    var karat='22K', fineness=916, pct='91.6%', use='Bridal & Traditional Jewellery',
        perGramRate = 13265;

    if(code.indexOf('24K')!==-1 || code.indexOf('999')!==-1){
      karat='24K'; fineness=999; pct='99.9%'; use='Investment Coins, Bars & Bullion';
      perGramRate = 14467;
    } else if(code.indexOf('18K')!==-1 || code.indexOf('750')!==-1){
      karat='18K'; fineness=750; pct='75.0%'; use='Diamond & Gemstone Jewellery';
      perGramRate = 10850;
    } else if(code.indexOf('14K')!==-1 || code.indexOf('585')!==-1){
      karat='14K'; fineness=585; pct='58.5%'; use='Lightweight Daily & Office Wear';
      perGramRate = Math.round(14467 * 0.585);
    }

    currentPerGram = perGramRate;

    if(hResCode)hResCode.textContent='HUID / STAMP: '+code;
    if(hResKarat)hResKarat.textContent=karat+' Carat ('+karat+')';
    if(hResFineness)hResFineness.textContent=pct+' Pure Gold ('+fineness+' Fineness)';
    if(hResVal)hResVal.textContent='₹'+(perGramRate*10).toLocaleString('en-IN');
    if(hResUse)hResUse.textContent=use;
    if(hStampText)hStampText.textContent=karat+fineness;

    recalcHUID();
  }

  function recalcHUID(){
    if(!hWeightInput||!hCalcTotal)return;
    var w=parseFloat(hWeightInput.value)||10;
    var tot=Math.round(w*currentPerGram);
    hCalcTotal.textContent='₹'+tot.toLocaleString('en-IN');
  }

  if(hBtn)hBtn.addEventListener('click',function(){verifyHUID();});
  if(hInput)hInput.addEventListener('input',function(){verifyHUID();});
  if(hWeightInput)hWeightInput.addEventListener('input',recalcHUID);

  document.querySelectorAll('.huid-sample-btn').forEach(function(b){
    b.addEventListener('click',function(){
      verifyHUID(b.dataset.code);
    });
  });

  /* ---- daily-alerts modal ---- */
  var SB_URL="$supabase_url", SB_KEY="$anon_key";
  var overlay=document.getElementById('alert-overlay');
  var mform=document.getElementById('m-form');
  var mok=document.getElementById('mm-ok'), merr=document.getElementById('mm-err');
  var mbtn=document.getElementById('m-btn');
  function openModal(){
    mform.reset();                 /* never show previously typed/submitted data */
    mok.style.display='none'; merr.style.display='none';
    mbtn.disabled=false; mbtn.textContent='Subscribe';
    overlay.classList.add('open');
    /* carry over the email if they already used the quick-subscribe banner */
    var qe=document.getElementById('qs-email');
    if(qe&&qe.value.trim())document.getElementById('m-email').value=qe.value.trim();
    document.getElementById('m-name').focus();
  }
  function closeModal(){overlay.classList.remove('open');
    try{sessionStorage.setItem('gr_dismissed','1');}catch(e){}}
  document.getElementById('m-close').addEventListener('click',closeModal);
  overlay.addEventListener('click',function(e){
    if(e.target===overlay)closeModal();});
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&overlay.classList.contains('open'))closeModal();});
  document.querySelectorAll('.js-alert').forEach(function(a){
    a.addEventListener('click',function(e){e.preventDefault();openModal();});
  });
  function send(payload,retried){
    return fetch(SB_URL+'/rest/v1/inquiries',{
      method:'POST',
      headers:{'Content-Type':'application/json','apikey':SB_KEY,
               'Authorization':'Bearer '+SB_KEY,'Prefer':'return=minimal'},
      body:JSON.stringify(payload)
    }).then(function(r){
      if(r.ok)return true;
      /* older table without the newer columns: retry with base fields only */
      if(!retried){
        var BASE=['name','email','phone','country','state','city','zip'];
        var p2={};BASE.forEach(function(k){
          if(payload[k]!==undefined)p2[k]=payload[k];});
        return send(p2,true);
      }
      throw new Error('bad status');
    });
  }
  mform.addEventListener('submit',function(e){
    e.preventDefault();
    mok.style.display='none';merr.style.display='none';
    if(mform.website.value){return;}
    if(!mform.reportValidity()){return;}
    if(!SB_KEY){merr.textContent='Subscriptions open shortly - please check back soon.';
      merr.style.display='block';return;}
    mbtn.disabled=true;mbtn.textContent='Subscribing...';
    var payload={
      name:mform.name.value.trim(), email:mform.email.value.trim(),
      phone:mform.phone.value.trim(), country:mform.country.value,
      state:mform.state.value.trim(), city:mform.city.value.trim(),
      zip:mform.zip.value.trim(), area:mform.area.value.trim(),
      offers_optin:mform.offers.checked
    };
    var g=window.GR_GDATA||{};
    for(var k in g){if(g[k]!==null&&g[k]!==undefined)payload[k]=g[k];}
    /* merge into the same email row when possible; else plain insert */
    var save=window.GR_SAVE?window.GR_SAVE(payload):send(payload,false);
    save.then(function(){
      mok.style.display='block';mbtn.textContent='Subscribed';
      try{localStorage.setItem('gr_sub','1');}catch(e){}
      setTimeout(closeModal,1600);
    }).catch(function(){
      merr.style.display='block';
      mbtn.disabled=false;mbtn.textContent='Subscribe';
    });
  });

  /* ---- quick-subscribe (single email field, no modal) ---- */
  (function(){
    var qform=document.getElementById('qs-form');
    if(!qform)return;
    var qemail=document.getElementById('qs-email'),
        qbtn=document.getElementById('qs-btn'),
        qok=document.getElementById('qs-ok'), qerr=document.getElementById('qs-err');
    try{if(localStorage.getItem('gr_sub')==='1'){
      qform.hidden=true;qok.style.display='block';
      qok.innerHTML='You\\'re already subscribed - see you tomorrow morning.';
    }}catch(e){}
    qform.addEventListener('submit',function(e){
      e.preventDefault();
      qok.style.display='none';qerr.style.display='none';
      var email=(qemail.value||'').trim();
      if(!email)return;
      if(!SB_KEY){qerr.textContent='Subscriptions open shortly - please check back soon.';
        qerr.style.display='block';return;}
      qbtn.disabled=true;qbtn.textContent='Subscribing...';
      var payload={email:email,signup_source:'quick_banner'};
      var save=window.GR_SAVE?window.GR_SAVE(payload):send(payload,false);
      save.then(function(){
        qok.style.display='block';qbtn.textContent='Subscribed';
        try{localStorage.setItem('gr_sub','1');}catch(e){}
      }).catch(function(){
        qerr.style.display='block';
        qbtn.disabled=false;qbtn.textContent='Get Free Alerts';
      });
    });
  })();

  /* ---- visitor hit counter ---- */
  (function(){
    var el=document.getElementById('hitcount'),
        wrap=document.getElementById('hits');
    if(!SB_KEY||!el)return;
    var counted=false; try{counted=!!sessionStorage.getItem('gr_hit');}catch(e){}
    var fn=counted?'hits_count':'bump_hits';   /* bump once per session */
    fetch(SB_URL+'/rest/v1/rpc/'+fn,{method:'POST',
      headers:{'Content-Type':'application/json','apikey':SB_KEY,
               'Authorization':'Bearer '+SB_KEY},body:'{}'})
      .then(function(r){return r.ok?r.json():Promise.reject();})
      .then(function(n){
        n=Number(n);
        if(!isNaN(n)){el.textContent=n.toLocaleString('en-IN');wrap.hidden=false;}
        try{sessionStorage.setItem('gr_hit','1');}catch(e){}
      }).catch(function(){});
  })();
})();
</script>
<script>window.GR_GCID="$gclient";window.GR_SB_URL="$supabase_url";window.GR_SB_KEY="$anon_key";</script>
<script src="signup.js?v=$sig_ver" defer></script>
$gate_html
$gate_js
</body>
</html>
""")


INQUIRY_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Gold Rate Alerts by Email - GoldRates</title>
<meta name="description" content="Get one clean email every morning with India's gold rate comparison - the cheapest jeweller, the IBJA bullion premium and the market median. Free sign-up.">
<link rel="canonical" href="$site_url/inquiry">
<link rel="icon" href="$site_url/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="96x96" href="$site_url/icon-96.png">
<link rel="icon" type="image/png" sizes="48x48" href="$site_url/icon-48.png">
<link rel="icon" type="image/svg+xml" href="$site_url/favicon.svg">
<link rel="apple-touch-icon" href="$site_url/apple-touch-icon.png">
<meta name="robots" content="index,follow">
$ads_head
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
$gsi
<style>
$base_css
.formcard{background:var(--card);border:1px solid var(--line);
  border-radius:16px;padding:30px;max-width:640px;margin:8px 0 40px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:560px){.grid2{grid-template-columns:1fr}}
.field{margin-bottom:16px}
.field label{display:block;font:500 12px/1.4 "IBM Plex Mono",monospace;
  letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);
  margin-bottom:6px}
.field input,.field select{width:100%;font:15px "IBM Plex Sans",sans-serif;
  color:var(--ink);background:var(--paper);border:1px solid var(--line);
  border-radius:10px;padding:12px 14px}
.field input:focus,.field select:focus{border-color:var(--gold);outline:none}
.req{color:var(--warm)}
.hp{position:absolute;left:-9999px;opacity:0;height:0;overflow:hidden}
.msg{border-radius:10px;padding:14px 16px;font-size:14.5px;margin-top:14px;
  display:none}
.msg-ok{background:color-mix(in srgb,var(--emerald) 12%,transparent);
  color:var(--emerald);border:1px solid var(--emerald)}
.msg-err{background:color-mix(in srgb,var(--warm) 12%,transparent);
  color:var(--warm);border:1px solid var(--warm)}
.privacy{font-size:12.5px;color:var(--ink-3);margin-top:14px;max-width:60ch}
.hero-sm{background:
  radial-gradient(120% 160% at 85% -20%,rgba(217,178,74,.16),transparent 55%),
  linear-gradient(160deg,var(--board),var(--board-2));
  color:#EDE9DD;border-radius:16px;margin:20px 0 26px;padding:34px 34px;
  border:1px solid rgba(217,178,74,.22)}
.hero-sm h1{font-size:clamp(24px,4vw,34px);color:#F6F1E3;margin-bottom:6px}
.hero-sm p{color:#B9C2B4;max-width:52ch;font-size:15px}
</style>
</head>
<body>
$nav
<div class="wrap">

<header class="top">
  <button class="navtog" id="navtog" aria-label="Open menu" aria-expanded="false">&#9776;</button>
  <a class="brand" href="$site_url/" aria-label="MyGoldRates.com home"><svg class="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="grx" x1="4" y1="38" x2="36" y2="4" gradientUnits="userSpaceOnUse"><stop stop-color="#B07E12"/><stop offset=".55" stop-color="#E3BF63"/><stop offset="1" stop-color="#F4E3A6"/></linearGradient></defs><rect x="4.5" y="21" width="9" height="15" rx="1.6" fill="url(#grx)"/><rect x="16.5" y="12" width="9" height="24" rx="1.6" fill="url(#grx)"/><path d="M5 25.5 17 17 25 21 34 8.5" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M27.5 7.5 35 6.5 34.5 14" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="brand-text"><span class="wm">My<b>Gold</b>Rates<span class="tld">.com</span></span><span class="brand-tag">India&rsquo;s 1st gold rate comparison platform</span></span></a>
  <div class="topright">
    <a class="btn" href="$site_url/">← Today's rates</a>
  </div>
</header>

<section class="hero-sm">
  <h1>Daily Gold Rate Alerts</h1>
  <p>One clean email every morning: which jeweller is cheapest, the market
  median, and the premium over the IBJA bullion rate. No spam, unsubscribe
  any time.</p>
</section>

<form id="inq" class="formcard" novalidate>
  $google_btn
  <div class="manualbox" id="f-manual">
  <div class="field"><label for="f-name">Name <span class="req">*</span></label>
    <input id="f-name" name="name" autocomplete="name" required maxlength="80"></div>
  <div class="grid2">
    <div class="field"><label for="f-email">Email <span class="req">*</span></label>
      <input id="f-email" name="email" type="email" autocomplete="email"
      required maxlength="120"></div>
    <div class="field"><label for="f-phone">Phone <span class="req">*</span></label>
      <input id="f-phone" name="phone" type="tel" autocomplete="tel"
      inputmode="tel" required maxlength="20" value="+91 "
      placeholder="+91 98765 43210"></div>
  </div>
  <button type="button" class="locbtn" id="f-loc">&#128205; Use my current
  location to autofill address</button>
  <div class="grid2">
    <div class="field"><label for="f-country">Country</label>
      <select id="f-country" name="country" autocomplete="country-name">
        <option selected>India</option><option>United Arab Emirates</option>
        <option>United States</option><option>United Kingdom</option>
        <option>Singapore</option><option>Other</option>
      </select></div>
    <div class="field"><label for="f-state">State</label>
      <input id="f-state" name="state" autocomplete="address-level1"
      maxlength="60"></div>
  </div>
  <div class="grid2">
    <div class="field"><label for="f-city">City</label>
      <input id="f-city" name="city" autocomplete="address-level2"
      maxlength="60"></div>
    <div class="field"><label for="f-zip">PIN / ZIP code</label>
      <input id="f-zip" name="zip" autocomplete="postal-code"
      inputmode="numeric" maxlength="10"></div>
  </div>
  <div class="field"><label for="f-area">Area / Locality</label>
    <input id="f-area" name="area" maxlength="80" list="f-areas"
    autocomplete="address-level3" placeholder="auto-fills from PIN code">
    <datalist id="f-areas"></datalist></div>
  <div class="hp" aria-hidden="true">
    <label>Website<input name="website" tabindex="-1" autocomplete="off"></label>
  </div>
  <label style="display:flex;gap:8px;align-items:flex-start;margin:2px 0 16px;
  font-size:11.5px;color:var(--ink-3);max-width:52ch">
    <input type="checkbox" name="offers" checked
    style="margin-top:2px;accent-color:var(--gold)">
    <span>Also send me gold offers, festive-scheme alerts and buying guides
    by email. You can opt out any time.</span></label>
  <button class="btn btn-gold" type="submit" id="f-btn">Subscribe to daily rates</button>
  </div>
  <div class="msg msg-ok" id="m-ok">You're in - the next morning's rates will
  land in your inbox. You can reply to any email to unsubscribe.</div>
  <div class="msg msg-err" id="m-err">Something went wrong - please check the
  highlighted fields and try again.</div>
  <p class="privacy">Your details are used only to send the daily gold-rate
  email and are never sold or shared with jewellers or advertisers.</p>
</form>

<footer>
  <p>© $year GoldRates - daily gold rate comparison for India.</p>
</footer>

</div>
<script>
(function(){
  var URL_="$supabase_url", KEY="$anon_key";
  var form=document.getElementById('inq');
  var ok=document.getElementById('m-ok'), err=document.getElementById('m-err');
  var btn=document.getElementById('f-btn');
  form.addEventListener('submit',function(e){
    e.preventDefault();
    ok.style.display='none';err.style.display='none';
    if(form.website.value){return;}          /* honeypot */
    if(!form.reportValidity()){return;}
    if(!KEY){err.textContent='Subscriptions open shortly - please check back soon.';
      err.style.display='block';return;}
    btn.disabled=true;btn.textContent='Subscribing...';
    var payload={
      name:form.name.value.trim(), email:form.email.value.trim(),
      phone:form.phone.value.trim(), country:form.country.value,
      state:form.state.value.trim(), city:form.city.value.trim(),
      zip:form.zip.value.trim(), area:form.area.value.trim(),
      offers_optin:form.offers.checked
    };
    var g=window.GR_GDATA||{};
    for(var k in g){if(g[k]!==null&&g[k]!==undefined)payload[k]=g[k];}
    function post(p){
      return fetch(URL_+'/rest/v1/inquiries',{
        method:'POST',
        headers:{'Content-Type':'application/json','apikey':KEY,
                 'Authorization':'Bearer '+KEY,'Prefer':'return=minimal'},
        body:JSON.stringify(p)}).then(function(r){
          if(!r.ok)throw new Error('bad status');return r;});
    }
    /* merge into the same email row via RPC when available; else insert */
    var save=window.GR_SAVE?window.GR_SAVE(payload):post(payload);
    save.then(function(){
      form.reset();ok.style.display='block';
      btn.textContent='Subscribed';
    }).catch(function(){
      err.style.display='block';
      btn.disabled=false;btn.textContent='Subscribe to daily rates';
    });
  });
})();
</script>
<script>window.GR_GCID="$gclient";window.GR_SB_URL="$supabase_url";window.GR_SB_KEY="$anon_key";</script>
<script src="signup.js?v=$sig_ver" defer></script>
</body>
</html>
""")


PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<meta name="description" content="$desc">
<link rel="canonical" href="$canonical">
<link rel="icon" href="$site_url/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="96x96" href="$site_url/icon-96.png">
<link rel="icon" type="image/png" sizes="48x48" href="$site_url/icon-48.png">
<link rel="icon" type="image/svg+xml" href="$site_url/favicon.svg">
<link rel="apple-touch-icon" href="$site_url/apple-touch-icon.png">
$ads_head
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
$base_css
.page{max-width:720px;margin:10px 0 30px}
.page h1{font-size:clamp(26px,4.5vw,36px);margin:8px 0 6px}
.page h2{font-size:20px;margin:26px 0 8px}
.page p,.page li{color:var(--ink-2);font-size:15px;line-height:1.7}
.page ul{padding-left:20px;margin:8px 0}
.page a{color:var(--emerald)}
.updated-on{font-family:"IBM Plex Mono",monospace;font-size:12px;
  color:var(--ink-3);margin-bottom:18px}
.foot-nav{margin:8px 0}
.foot-nav a{color:var(--ink-3);margin-right:14px;text-decoration:none}
.foot-nav a:hover{color:var(--ink)}
</style>
</head>
<body>
$nav
<div class="wrap">
<header class="top">
  <button class="navtog" id="navtog" aria-label="Open menu" aria-expanded="false">&#9776;</button>
  <a class="brand" href="$site_url/" aria-label="MyGoldRates.com home"><svg class="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="grx" x1="4" y1="38" x2="36" y2="4" gradientUnits="userSpaceOnUse"><stop stop-color="#B07E12"/><stop offset=".55" stop-color="#E3BF63"/><stop offset="1" stop-color="#F4E3A6"/></linearGradient></defs><rect x="4.5" y="21" width="9" height="15" rx="1.6" fill="url(#grx)"/><rect x="16.5" y="12" width="9" height="24" rx="1.6" fill="url(#grx)"/><path d="M5 25.5 17 17 25 21 34 8.5" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M27.5 7.5 35 6.5 34.5 14" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="brand-text"><span class="wm">My<b>Gold</b>Rates<span class="tld">.com</span></span><span class="brand-tag">India&rsquo;s 1st gold rate comparison platform</span></span></a>
  <div class="topright"><a class="btn" href="$site_url/">Today's rates</a></div>
</header>
<article class="page">
  <h1>$heading</h1>
  <p class="updated-on">Last updated $date</p>
$body
</article>
<footer>
  <div class="foot-nav">
    <a href="$site_url/about.html">About</a>
    <a href="$site_url/contact.html">Contact</a>
    <a href="$site_url/terms.html">Terms of Service</a>
    <a href="$site_url/privacy.html">Privacy Policy</a>
  </div>
  <p>© $year GoldRates - daily gold rate comparison for India.</p>
</footer>
</div>
<script>window.GR_SB_URL="$supabase_url";window.GR_SB_KEY="$anon_key";</script>
<script src="signup.js?v=$sig_ver" defer></script>
</body>
</html>
""")


# Flexible content page (calculators, news, articles): shared chrome + nav,
# arbitrary $body and optional $extra_js / $jsonld_block.
CONTENT_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<meta name="description" content="$desc">
<meta name="robots" content="$robots">
<link rel="canonical" href="$canonical">
<link rel="icon" href="$site_url/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="96x96" href="$site_url/icon-96.png">
<link rel="icon" type="image/png" sizes="48x48" href="$site_url/icon-48.png">
<link rel="icon" type="image/svg+xml" href="$site_url/favicon.svg">
<link rel="apple-touch-icon" href="$site_url/apple-touch-icon.png">
$ads_head
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;700&display=swap" rel="stylesheet">
$jsonld_block
<style>
$base_css
.page{max-width:760px;margin:10px 0 30px}
.page h1{font-size:clamp(24px,4.2vw,34px);margin:8px 0 6px}
.page h2{font-size:20px;margin:24px 0 8px}
.page p,.page li{color:var(--ink-2);font-size:15px;line-height:1.7}
.page ul{padding-left:20px;margin:8px 0}
.page a{color:var(--emerald)}
.crumbs{font-size:12.5px;color:var(--ink-3);margin:2px 0 6px}
.crumbs a{color:var(--ink-3);text-decoration:none}
.crumbs a:hover{color:var(--gold)}
.updated-on{font-family:"IBM Plex Mono",monospace;font-size:12px;
  color:var(--ink-3);margin-bottom:16px}
.calcbox{background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:20px;margin:14px 0}
.calcbox label{display:block;font:600 11.5px/1 "IBM Plex Sans",sans-serif;
  color:var(--ink-2);margin:12px 0 5px;text-transform:uppercase;
  letter-spacing:.06em}
.calcbox input,.calcbox select{width:100%;padding:11px 12px;
  border:1px solid var(--line);border-radius:9px;background:var(--paper);
  color:var(--ink);font-size:15px}
.calcout{margin-top:18px;padding:16px 18px;border-radius:12px;
  background:color-mix(in srgb,var(--gold) 8%,transparent);
  border:1px solid color-mix(in srgb,var(--gold) 35%,transparent)}
.calcout .big{font-family:"IBM Plex Mono",monospace;font-size:26px;
  font-weight:700;color:var(--ink)}
.calcout .row{display:flex;justify-content:space-between;font-size:13px;
  color:var(--ink-2);margin-top:7px}
.calcout .row span:last-child{font-family:"IBM Plex Mono",monospace;
  color:var(--ink)}
.toolgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
  gap:12px;margin:14px 0}
.toolcard{display:block;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:16px 18px;text-decoration:none}
.toolcard:hover{border-color:var(--gold)}
.toolcard b{display:block;color:var(--ink);font-size:15px;margin-bottom:3px}
.toolcard span{font-size:13px;color:var(--ink-3)}
.newscard{display:block;background:var(--card);border:1px solid var(--line);
  border-radius:12px;padding:15px 18px;margin:10px 0;text-decoration:none}
.newscard:hover{border-color:var(--gold)}
.newscard .nt{font-weight:600;color:var(--ink);font-size:15.5px}
.newscard .nd{font:500 11.5px/1 "IBM Plex Mono",monospace;color:var(--ink-3);
  margin-top:4px}
.newscard .nx{font-size:13.5px;color:var(--ink-2);margin-top:7px;line-height:1.6}
.recap-move{font-family:"IBM Plex Mono",monospace;font-size:15px;font-weight:600}
.up{color:var(--emerald)}.dn{color:var(--warm)}
.foot-nav{margin:8px 0}
.foot-nav a{color:var(--ink-3);margin-right:14px;text-decoration:none}
.foot-nav a:hover{color:var(--ink)}
</style>
</head>
<body>
$nav
<div class="wrap">
<header class="top">
  <button class="navtog" id="navtog" aria-label="Open menu" aria-expanded="false">&#9776;</button>
  <a class="brand" href="$site_url/" aria-label="MyGoldRates.com home"><svg class="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="grx" x1="4" y1="38" x2="36" y2="4" gradientUnits="userSpaceOnUse"><stop stop-color="#B07E12"/><stop offset=".55" stop-color="#E3BF63"/><stop offset="1" stop-color="#F4E3A6"/></linearGradient></defs><rect x="4.5" y="21" width="9" height="15" rx="1.6" fill="url(#grx)"/><rect x="16.5" y="12" width="9" height="24" rx="1.6" fill="url(#grx)"/><path d="M5 25.5 17 17 25 21 34 8.5" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M27.5 7.5 35 6.5 34.5 14" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="brand-text"><span class="wm">My<b>Gold</b>Rates<span class="tld">.com</span></span><span class="brand-tag">India&rsquo;s 1st gold rate comparison platform</span></span></a>
  <div class="topright"><a class="btn" href="$site_url/">Today's rates</a></div>
</header>
<article class="page">
$body
</article>
<footer>
  <div class="foot-nav">
    <a href="$site_url/about">About</a>
    <a href="$site_url/contact">Contact</a>
    <a href="$site_url/privacy">Privacy Policy</a>
    <a href="$site_url/news">News</a>
    <a href="$site_url/calculators">Calculators</a>
  </div>
  <p>© $year GoldRates - daily gold rate comparison for India.</p>
</footer>
</div>
<script>window.GR_SB_URL="$supabase_url";window.GR_SB_KEY="$anon_key";</script>
<script src="$site_url/signup.js?v=$sig_ver" defer></script>
$extra_js
</body>
</html>
""")


UNSUB_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unsubscribe - GoldRates</title>
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="$site_url/unsubscribe">
<link rel="icon" href="$site_url/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="96x96" href="$site_url/icon-96.png">
<link rel="icon" type="image/png" sizes="48x48" href="$site_url/icon-48.png">
<link rel="icon" type="image/svg+xml" href="$site_url/favicon.svg">
<link rel="apple-touch-icon" href="$site_url/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
$base_css
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:34px;max-width:520px;margin:26px 0;text-align:center}
.card h1{font-size:26px;margin:0 0 10px}
.card p{color:var(--ink-2);font-size:15px;margin:8px 0}
.reasons{text-align:left;max-width:340px;margin:18px auto 0}
.reasons .r{display:flex;align-items:center;gap:10px;padding:11px 13px;margin:8px 0;
  border:1px solid var(--line);border-radius:10px;font-size:15px;cursor:pointer}
.reasons .r:hover{border-color:var(--gold,#D9B24A)}
.reasons .r input{accent-color:var(--gold,#D9B24A);width:16px;height:16px}
.reasons .btn{width:100%;margin-top:14px}
.skip{margin-top:12px;font-size:13px;text-align:center}
</style>
</head>
<body>
$nav
<div class="wrap">
<header class="top">
  <button class="navtog" id="navtog" aria-label="Open menu" aria-expanded="false">&#9776;</button>
  <a class="brand" href="$site_url/" aria-label="MyGoldRates.com home"><svg class="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="grx" x1="4" y1="38" x2="36" y2="4" gradientUnits="userSpaceOnUse"><stop stop-color="#B07E12"/><stop offset=".55" stop-color="#E3BF63"/><stop offset="1" stop-color="#F4E3A6"/></linearGradient></defs><rect x="4.5" y="21" width="9" height="15" rx="1.6" fill="url(#grx)"/><rect x="16.5" y="12" width="9" height="24" rx="1.6" fill="url(#grx)"/><path d="M5 25.5 17 17 25 21 34 8.5" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M27.5 7.5 35 6.5 34.5 14" stroke="url(#grx)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="brand-text"><span class="wm">My<b>Gold</b>Rates<span class="tld">.com</span></span><span class="brand-tag">India&rsquo;s 1st gold rate comparison platform</span></span></a>
</header>
<div class="card">
  <h1>Unsubscribe</h1>
  <div id="ask">
    <p>Sorry to see you go. Mind telling us why? It helps us improve.</p>
    <form id="reason-form" class="reasons">
      <label class="r"><input type="radio" name="reason" value="Too many emails"> Too many emails</label>
      <label class="r"><input type="radio" name="reason" value="Rates not relevant"> The rates aren&rsquo;t relevant to me</label>
      <label class="r"><input type="radio" name="reason" value="No longer tracking gold"> I no longer track gold rates</label>
      <label class="r"><input type="radio" name="reason" value="Did not sign up"> I didn&rsquo;t sign up for this</label>
      <label class="r"><input type="radio" name="reason" value="Other"> Other</label>
      <button class="btn" id="u-btn" type="submit">Unsubscribe</button>
      <p class="skip"><a href="#" id="skip-link">Unsubscribe without a reason</a></p>
    </form>
  </div>
  <p id="msg" style="display:none"></p>
  <p style="margin-top:16px"><a class="btn" href="$site_url/">Back to gold rates</a></p>
</div>
</div>
<script>
(function(){
  var URL_="$supabase_url", KEY="$anon_key";
  var ask=document.getElementById('ask');
  var msg=document.getElementById('msg');
  var form=document.getElementById('reason-form');
  var btn=document.getElementById('u-btn');
  var t=new URLSearchParams(location.search).get('t');
  function show(text){ask.style.display='none';msg.style.display='block';msg.textContent=text;}
  if(!t){show('This unsubscribe link looks invalid.');return;}
  if(!KEY){show('Unsubscribe is temporarily unavailable - please email us.');return;}
  function rpc(fn,body){
    return fetch(URL_+'/rest/v1/rpc/'+fn,{method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,'Authorization':'Bearer '+KEY},
      body:JSON.stringify(body)});
  }
  function unsub(reason){
    btn.disabled=true; btn.textContent='Unsubscribing...';
    /* Save the reason first (best effort - never block the unsubscribe), then
       run the actual unsubscribe. Reason storage keeps no personal data. */
    var saved = reason ? rpc('save_unsub_reason',{t:t,reason:reason}).catch(function(){})
                       : Promise.resolve();
    saved.then(function(){return rpc('unsubscribe',{t:t});})
      .then(function(r){if(!r.ok)throw 0;
        show("You've been unsubscribed. You won't receive any more daily gold-rate emails.");})
      .catch(function(){show('Something went wrong. Please reply to any of our emails to unsubscribe.');});
  }
  form.addEventListener('submit',function(e){e.preventDefault();
    var sel=form.querySelector('input[name=reason]:checked');
    unsub(sel?sel.value:'');});
  document.getElementById('skip-link').addEventListener('click',function(e){
    e.preventDefault(); unsub('');});
})();
</script>
</body>
</html>
""")


# =====================================================================
# Interactive making-charge dashboard (docs/making-charges-comparison.html).
# Plain strings + str.replace() placeholders (NOT f-string/Template) so the
# embedded JS braces and $ stay literal. __DATA__ carries the brand join.
# =====================================================================
# ============================================================================
# Budget calculator: reverse of the MC dashboard. Fix a rupee amount, show the
# grams user would actually take home from each jeweller after making + GST,
# with a "your jeweller" row so a real-world quote can be scored against the
# board. Same __DATA__ / __UPDATED__ / __SITE__ replacement pattern as the MC
# dashboard - do NOT convert to f-string, the embedded JS uses { } freely.
# ============================================================================
BUDGET_HTML = r"""
<h1>How much gold can I get for my budget?</h1>
<p class="mc-lede">Fix an amount you want to spend and see how many grams of
gold you would actually take home from each jeweller &mdash; after making
charges and 3% GST. Then paste your own jeweller's quote to check whether
they beat the board or overcharge on the making. Updated __UPDATED__.</p>

<div class="mc-panel">
  <div class="mc-controls">
    <div class="mc-field">
      <label>Your budget</label>
      <div class="bg-amt">
        <span class="bg-cur">&#8377;</span>
        <input type="number" id="bg-budget" min="1000" step="500" value="100000" inputmode="numeric">
      </div>
      <div class="mc-chips" id="bg-chips"></div>
    </div>
    <div class="mc-field">
      <label>Purity</label>
      <div class="mc-seg" id="bg-karats"></div>
    </div>
    <div class="mc-field">
      <label>What are you buying?</label>
      <div class="mc-seg" id="bg-cats"></div>
    </div>
  </div>
  <div class="bg-toggles" role="group" aria-label="What to include in cost">
    <label class="bg-toggle-inline">
      <input type="checkbox" id="bg-incmc" checked>
      <span>Include making charge</span>
    </label>
    <label class="bg-toggle-inline">
      <input type="checkbox" id="bg-incgst" checked>
      <span>Include 3% GST</span>
    </label>
    <span class="bg-toggle-hint" id="bg-mode-hint"></span>
  </div>
</div>

<div id="bg-headline" class="mc-headline" hidden></div>

<div class="mc-panel bg-quote">
  <div class="bg-quote-head">
    <div>
      <div class="bg-quote-eyebrow">Your jeweller's quote</div>
      <div class="bg-quote-title">Score their number against the board</div>
    </div>
    <label class="bg-toggle">
      <input type="checkbox" id="bg-usemine">
      <span>Compare</span>
    </label>
  </div>
  <div class="bg-quote-fields" id="bg-mine-fields" hidden>
    <div class="mc-field">
      <label>Their gold rate (per gram)</label>
      <div class="bg-amt">
        <span class="bg-cur">&#8377;</span>
        <input type="number" id="bg-mine-rate" min="100" step="10" value="13500" inputmode="numeric">
      </div>
    </div>
    <div class="mc-field">
      <label>Their making charge (%)</label>
      <div class="bg-amt">
        <input type="number" id="bg-mine-mc" min="0" max="60" step="0.5" value="18" inputmode="decimal">
        <span class="bg-cur bg-cur-r">%</span>
      </div>
    </div>
    <div class="mc-field">
      <label>Jeweller name (optional)</label>
      <input type="text" id="bg-mine-name" maxlength="40" placeholder="e.g. Local jeweller" class="bg-text">
    </div>
  </div>
</div>

<div id="bg-results"></div>

<p class="dnote" id="bg-note"></p>
<div class="mc-method">
  <h2>How the grams are worked out</h2>
  <p>For each jeweller we compute what one gram would actually cost you:
  today's per-gram rate, plus our verified median making charge for the
  category, plus 3% GST on the whole thing. Divide your budget by that number
  and you get the grams. That's the same maths a jeweller's bill uses, just
  run in reverse.</p>
  <p><strong>Your quote is scored the same way</strong> &mdash; whatever rate
  and making percentage you paste, we add 3% GST and compare the grams-per-rupee
  side by side. If a brand delivers more gold for the same money, they win by
  that gap; if your jeweller wins, hold on to that quote.</p>
  <p>Making charges we show are medians &mdash; individual pieces vary,
  especially ornate or stone-set designs. Hallmarking, stone value and any
  store-specific discount are not included. Always confirm the final bill in
  store. For a bill you already have, use our
  <a href="__SITE__/making-charges-calculator">making charges calculator</a>.</p>
</div>
"""

BUDGET_JS = r"""
<style>
.bg-amt{display:flex;align-items:stretch;border:1px solid var(--line);
  border-radius:9px;background:var(--paper);overflow:hidden;transition:border-color .2s}
.bg-amt:focus-within{border-color:var(--gold)}
.bg-amt .bg-cur{display:flex;align-items:center;padding:0 12px;
  background:color-mix(in srgb,var(--gold) 8%,transparent);color:var(--ink-2);
  font:600 15px/1 "IBM Plex Mono",monospace}
.bg-amt .bg-cur-r{border-left:1px solid var(--line);border-right:0}
.bg-amt input{flex:1;border:0;background:transparent;color:var(--ink);
  padding:11px 12px;font:600 17px/1 "IBM Plex Mono",monospace;outline:0;
  min-width:0;font-variant-numeric:tabular-nums}
.bg-text{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:9px;
  background:var(--paper);color:var(--ink);font:500 14.5px/1 "IBM Plex Sans",sans-serif;outline:0}
.bg-text:focus{border-color:var(--gold)}

.bg-toggles{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
  margin-top:20px;padding-top:18px;border-top:1px dashed var(--line)}
.bg-toggle-inline{display:inline-flex;align-items:center;gap:9px;cursor:pointer;
  font:600 13px/1 "IBM Plex Sans",sans-serif;color:var(--ink-2);
  padding:9px 16px;border:1px solid var(--line);border-radius:999px;
  background:var(--paper);user-select:none;
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset, 0 1px 2px rgba(74,53,36,.05);
  transition:transform .18s cubic-bezier(.2,.7,.3,1),
    box-shadow .18s ease, border-color .18s ease, color .18s ease, background .18s ease}
.bg-toggle-inline:hover{border-color:color-mix(in srgb,var(--gold) 55%,var(--line));
  color:var(--ink);transform:translateY(-1px);
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset,
    0 4px 14px -6px rgba(184,134,46,.35), 0 1px 2px rgba(74,53,36,.06)}
.bg-toggle-inline input{accent-color:var(--gold);width:14px;height:14px;cursor:pointer}
.bg-toggle-inline:has(input:checked){
  background:linear-gradient(140deg,
    color-mix(in srgb,var(--gold) 14%,var(--paper)) 0%,
    color-mix(in srgb,var(--gold) 6%,var(--paper)) 100%);
  border-color:color-mix(in srgb,var(--gold) 60%,var(--line));color:var(--ink);
  box-shadow:0 1px 0 rgba(255,255,255,.5) inset,
    0 0 0 1px color-mix(in srgb,var(--gold) 25%,transparent) inset}
.bg-toggle-hint{font-size:12.5px;color:var(--ink-3);flex:1;min-width:200px}
.bg-quote{margin-top:14px}
.bg-quote-head{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
.bg-quote-eyebrow{font:600 11px/1 "IBM Plex Sans",sans-serif;text-transform:uppercase;
  letter-spacing:.07em;color:var(--gold);margin-bottom:4px}
.bg-quote-title{font-weight:600;color:var(--ink);font-size:15px}
.bg-toggle{display:inline-flex;align-items:center;gap:9px;cursor:pointer;
  font:600 13px/1 "IBM Plex Sans",sans-serif;color:var(--ink-2);
  padding:9px 16px;border:1px solid var(--line);border-radius:999px;
  background:var(--paper);
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset, 0 1px 2px rgba(74,53,36,.05);
  transition:transform .18s cubic-bezier(.2,.7,.3,1),
    box-shadow .18s ease, border-color .18s ease, color .18s ease}
.bg-toggle:hover{border-color:color-mix(in srgb,var(--gold) 55%,var(--line));
  color:var(--ink);transform:translateY(-1px);
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset,
    0 4px 14px -6px rgba(184,134,46,.35), 0 1px 2px rgba(74,53,36,.06)}
.bg-toggle input{accent-color:var(--gold);width:14px;height:14px}
.bg-quote-fields{display:grid;grid-template-columns:1fr 1fr 1.2fr;gap:18px;margin-top:18px}
@media(max-width:720px){.bg-quote-fields{grid-template-columns:1fr}}

/* result rows are same shape as the MC dashboard, but the value shown is
   GRAMS, not rupees - and the delta is "less gold for the same money" */
.bg-row .mc-total .bg-g{font-size:22px}
.bg-row .mc-total .bg-unit{font-size:12px;color:var(--ink-3);margin-left:6px;
  font-family:"IBM Plex Sans",sans-serif;letter-spacing:.06em;text-transform:uppercase}
.bg-row .mc-delta{color:var(--warm)}
.bg-row .mc-legend b{color:var(--ink)}
.bg-row.mine{border-color:var(--gold);background:color-mix(in srgb,var(--gold) 5%,var(--card))}
.bg-row.mine .mc-brand::after{content:"YOUR QUOTE";margin-left:10px;font:600 10px/1 "IBM Plex Sans",sans-serif;
  letter-spacing:.08em;padding:3px 7px;border-radius:5px;background:var(--gold);color:#231a02;vertical-align:2px}
</style>
<script>
(function(){
  var D = __DATA__;
  var GST = 0.03;

  var BUDGETS = [
    {v:50000,  label:"₹50k"},
    {v:100000, label:"₹1 lakh"},
    {v:200000, label:"₹2 lakh"},
    {v:500000, label:"₹5 lakh"},
    {v:1000000,label:"₹10 lakh"}
  ];
  var KARATS = [["22","22K"],["24","24K"],["18","18K"]];

  var state = { budget: 100000, karat: "22", cat: (D.cats[0]||""),
                incMc: true, incGst: true,
                useMine: false, mineRate: 13500, mineMc: 18, mineName: "" };

  function $(id){ return document.getElementById(id); }
  function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }
  function inr(n){
    if(n==null||isNaN(n)) return "-";
    return "₹" + Math.round(n).toLocaleString("en-IN");
  }
  function g(n){
    if(n==null||isNaN(n)) return "-";
    return n < 10 ? n.toFixed(2) : n.toFixed(1);
  }

  function seg(host, items, cur, onPick){
    host.innerHTML = "";
    items.forEach(function(it){
      var val = it[0], lab = it[1];
      var b = document.createElement("button");
      b.type = "button"; b.textContent = lab;
      b.setAttribute("aria-pressed", val === cur ? "true" : "false");
      b.onclick = function(){ onPick(val); };
      host.appendChild(b);
    });
  }

  // cost of 1 gram, honouring the two toggles.
  // Both ON = billed price a jeweller would charge (default).
  // GST off = user's budget is pre-GST (e.g. company invoicing).
  // Making off = pure metal/coin-equivalent view, no craftsmanship.
  // Both off = spot gold, useful sanity check ("if I paid rate only, X grams").
  function perGramCost(rate, mcPct){
    var withMc = state.incMc ? (rate + rate * (mcPct/100)) : rate;
    return state.incGst ? withMc * (1 + GST) : withMc;
  }

  function compute(){
    var out = [];
    Object.keys(D.brands).forEach(function(name){
      var b = D.brands[name];
      var mc = b.mc[state.cat];
      var rate = b.rates[state.karat];
      if(!mc || !rate) return;
      var cpg = perGramCost(rate, mc.pct);
      var grams = state.budget / cpg;
      var gold = rate * grams;
      var making = state.incMc ? gold * (mc.pct/100) : 0;
      var gst = state.incGst ? (gold + making) * GST : 0;
      out.push({ name:name, rate:rate, pct:mc.pct, n:mc.n, conf:mc.conf,
                 cpg:cpg, grams:grams, gold:gold, making:making, gst:gst,
                 mine:false });
    });
    if(state.useMine && state.mineRate > 0){
      var cpg2 = perGramCost(state.mineRate, state.mineMc);
      var grams2 = state.budget / cpg2;
      var gold2 = state.mineRate * grams2;
      var making2 = state.incMc ? gold2 * (state.mineMc/100) : 0;
      var gst2 = state.incGst ? (gold2 + making2) * GST : 0;
      out.push({ name: state.mineName.trim() || "Your jeweller",
                 rate:state.mineRate, pct:state.mineMc, n:1, conf:"user",
                 cpg:cpg2, grams:grams2, gold:gold2, making:making2, gst:gst2,
                 mine:true });
    }
    out.sort(function(a,b){ return b.grams - a.grams; });
    return out;
  }

  function render(){
    var rows = compute();
    var host = $("bg-results");
    var head = $("bg-headline");

    if(!rows.length){
      host.innerHTML = '<div class="mc-empty">No jeweller in our making-charge '
        + 'sample stocks this combination yet.</div>';
      head.hidden = true; $("bg-note").textContent = ""; return;
    }

    var best = rows[0], worst = rows[rows.length-1];
    var mine = rows.filter(function(r){return r.mine;})[0];
    var lead = state.karat + "K " + state.cat.toLowerCase();
    var modeTag;
    if(state.incMc && state.incGst) modeTag = " (billed price)";
    else if(!state.incMc && !state.incGst) modeTag = " (spot gold only)";
    else if(!state.incMc) modeTag = " (no making charge)";
    else modeTag = " (pre-GST)";

    head.hidden = false;
    var msg = '<div class="mh-k">Most grams for ' + inr(state.budget) + ' on ' + esc(lead) + modeTag + '</div>'
      + '<div class="mh-v">' + g(best.grams) + '<span style="font-size:.5em;opacity:.75;margin-left:8px">g &middot; <b>' + esc(best.name) + '</b></span></div>';
    if(rows.length > 1){
      msg += '<div class="mh-sub">' + esc(worst.name) + ' would give you '
        + g(worst.grams) + 'g &mdash; <b>' + g(best.grams - worst.grams) + 'g less</b> for the same money.';
      if(mine && mine !== best){
        var deficit = best.grams - mine.grams;
        msg += ' Your jeweller gives you <b>' + g(deficit)
          + 'g less</b> than ' + esc(best.name) + '.';
      } else if(mine && mine === best){
        msg += ' Your jeweller <b>beats every listed brand</b> &mdash; keep that quote.';
      }
      msg += '</div>';
    }
    head.innerHTML = msg;

    host.innerHTML = rows.map(function(r, i){
      var deficit = best.grams - r.grams;
      return '<div class="mc-row bg-row' + (i===0?' best':'') + (r.mine?' mine':'') + '">'
        + '<div class="mc-top">'
          + '<span class="mc-rank">' + (i+1) + '</span>'
          + '<span class="mc-brand">' + esc(r.name) + '</span>'
          + (i===0 && !r.mine ? '<span class="mc-badge">Best value</span>' : '')
          + (r.mine ? ''
              : r.conf === "estimate"
                ? '<span class="mc-badge soft">Est. making %</span>'
              : r.conf !== "high"
                ? '<span class="mc-badge soft">' + (r.n||0) + ' item'
                  + (r.n===1?'':'s') + '</span>' : '')
          + '<span class="mc-total"><span class="bg-g">' + g(r.grams) + '</span><span class="bg-unit">grams</span>'
          + (i>0 ? '<span class="mc-delta">&minus;' + g(deficit) + 'g</span>' : '')
          + '</span>'
        + '</div>'
        + '<div class="mc-legend" style="margin-top:12px">'
          + '<span>Cost/g <b>' + inr(r.cpg) + '</b></span>'
          + '<span>Rate <b>' + inr(r.rate) + '/g</b></span>'
          + '<span>Making <b>' + (state.incMc ? r.pct + '%' : 'excluded') + '</b></span>'
          + '<span>GST <b>' + (state.incGst ? '3%' : 'excluded') + '</b></span>'
        + '</div>'
      + '</div>';
    }).join("");

    var totalBrands = rows.length - (mine?1:0);
    var estBrands = rows.filter(function(r){return !r.mine && r.conf === "estimate";}).length;
    var note = "Comparing " + totalBrands + " jeweller" + (totalBrands===1?"":"s");
    if(estBrands > 0){
      note += " (" + estBrands + " use a market-median making % as an estimate; "
        + "the rest are verified from that jeweller's own price breakups)";
    } else {
      note += " with verified making-charge data";
    }
    if(mine) note += " plus your quote";
    note += ". Grams shown are before hallmarking or stone charges.";
    $("bg-note").textContent = note;
  }

  function build(){
    seg($("bg-cats"), D.cats.map(function(c){ return [c,c]; }), state.cat,
        function(v){ state.cat = v; build(); });
    seg($("bg-karats"), KARATS, state.karat,
        function(v){ state.karat = v; build(); });
    render();
  }

  // budget chips
  var chips = $("bg-chips");
  BUDGETS.forEach(function(b){
    var btn = document.createElement("button"); btn.type = "button"; btn.textContent = b.label;
    btn.onclick = function(){ state.budget = b.v; $("bg-budget").value = b.v; render(); };
    chips.appendChild(btn);
  });
  $("bg-budget").addEventListener("input", function(){
    var v = parseFloat(this.value); if(!isNaN(v) && v > 0){ state.budget = v; render(); }
  });

  // "your jeweller" toggle + inputs
  var mineFields = $("bg-mine-fields"), useMine = $("bg-usemine");
  useMine.addEventListener("change", function(){
    state.useMine = this.checked;
    mineFields.hidden = !state.useMine;
    render();
  });
  $("bg-mine-rate").addEventListener("input", function(){
    var v = parseFloat(this.value); if(!isNaN(v) && v > 0){ state.mineRate = v; render(); }
  });
  $("bg-mine-mc").addEventListener("input", function(){
    var v = parseFloat(this.value); if(!isNaN(v) && v >= 0 && v <= 60){ state.mineMc = v; render(); }
  });
  $("bg-mine-name").addEventListener("input", function(){ state.mineName = this.value; render(); });

  // include-in-cost toggles
  function refreshModeHint(){
    var h = $("bg-mode-hint");
    if(state.incMc && state.incGst){
      h.textContent = "Billed price a jeweller would charge you.";
    } else if(!state.incMc && state.incGst){
      h.textContent = "Making charge excluded (bullion / coin-style pricing).";
    } else if(state.incMc && !state.incGst){
      h.textContent = "Pre-GST view (budget is before 3% tax).";
    } else {
      h.textContent = "Spot gold only - no making charge, no GST.";
    }
  }
  $("bg-incmc").addEventListener("change", function(){
    state.incMc = this.checked; refreshModeHint(); render();
  });
  $("bg-incgst").addEventListener("change", function(){
    state.incGst = this.checked; refreshModeHint(); render();
  });
  refreshModeHint();

  build();
})();
</script>
"""


MC_DASH_HTML = r"""
<h1>What will it actually cost you?</h1>
<p class="mc-lede">Two jewellers can quote you the same gold rate and still bill
you thousands apart. The difference is the <strong>making charge</strong> &mdash;
and almost nobody compares it before walking into a store. Choose what you want
to buy below and see the true, all-in price at each jeweller, broken down to the
last rupee. Updated __UPDATED__.</p>

<div class="mc-panel">
  <div class="mc-controls">
    <div class="mc-field">
      <label>What are you buying?</label>
      <div class="mc-seg" id="mc-cats"></div>
    </div>
    <div class="mc-field">
      <label>Weight <span class="mc-hint">grams</span></label>
      <input type="number" id="mc-weight" min="1" max="200" step="0.5" value="10">
      <div class="mc-chips" id="mc-wchips"></div>
    </div>
    <div class="mc-field">
      <label>Purity</label>
      <div class="mc-seg" id="mc-karats"></div>
    </div>
  </div>
</div>

<div id="mc-headline" class="mc-headline" hidden></div>
<div id="mc-insight" class="mc-insight" hidden></div>
<div id="mc-results"></div>

<p class="dnote" id="mc-note"></p>
<div class="mc-method">
  <h2>How we work out these making charges</h2>
  <p>We do not take a jeweller's word for it, and we do not use a single
  headline figure. For every brand we <strong>manually review and verify each
  category</strong>, then read the published price breakup of many real products
  on that jeweller's own website &mdash; the same breakup you would see at
  checkout. From those we take the <strong>median</strong>, so one unusually
  ornate or unusually plain design cannot distort the result.</p>
  <p><strong>Please treat these figures as indicative.</strong> A making charge
  is not a fixed number: it varies by design, by weight, by season and by how
  well you negotiate. Stone-set and highly detailed pieces routinely sit above
  the median, while plain bands sit below it. The badge on each row shows how
  many real products that brand's median is based on &mdash; the more items, the
  more reliable the figure.</p>
  <p>Prices shown include <strong>3% GST</strong> on gold plus making charges.
  They exclude hallmarking fees, stone or diamond value, and any store-specific
  discount. Always confirm the final billed amount with the jeweller before you
  buy. To price a quote you have already been given, use our
  <a href="__SITE__/making-charges-calculator">making charges calculator</a>.</p>
</div>
"""

MC_DASH_JS = r"""
<style>
.mc-lede{font-size:15px;line-height:1.7;color:var(--ink-2);max-width:70ch}
.mc-panel{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:18px 20px;margin:20px 0}
.mc-controls{display:grid;grid-template-columns:1.4fr .9fr .9fr;gap:20px}
@media(max-width:720px){.mc-controls{grid-template-columns:1fr;gap:16px}}
.mc-field label{display:block;font:600 11px/1 "IBM Plex Sans",sans-serif;
  text-transform:uppercase;letter-spacing:.07em;color:var(--ink-3);margin-bottom:8px}
.mc-hint{text-transform:none;letter-spacing:0;font-weight:400;opacity:.7}
/* segment + chip styles: shared across MC dashboard, budget calc, karat tabs.
   Warm-preview aesthetic: hairline border on parchment, soft lift on hover,
   two-stop gold gradient on the active state with an inset highlight for
   coin-like depth. Every button becomes a small tactile object. */
.mc-seg{display:flex;flex-wrap:wrap;gap:8px}
.mc-seg button{font:600 13px/1 "IBM Plex Sans",sans-serif;padding:10px 16px;
  border:1px solid var(--line);background:var(--paper);color:var(--ink-2);
  border-radius:10px;cursor:pointer;position:relative;
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset, 0 1px 2px rgba(74,53,36,.05);
  transition:transform .18s cubic-bezier(.2,.7,.3,1),
    box-shadow .18s ease, border-color .18s ease, color .18s ease,
    background .18s ease}
.mc-seg button:hover{border-color:color-mix(in srgb,var(--gold) 55%,var(--line));
  color:var(--ink);transform:translateY(-1px);
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset,
    0 4px 14px -6px rgba(184,134,46,.35), 0 1px 2px rgba(74,53,36,.06)}
.mc-seg button:active{transform:translateY(0)}
.mc-seg button[aria-pressed="true"]{
  background:linear-gradient(140deg,#E4C070 0%,#B8862E 55%,#7A5A1A 100%);
  border-color:#7A5A1A;color:#231a02;font-weight:700;
  box-shadow:0 1px 0 rgba(255,255,255,.35) inset,
    0 0 0 1px rgba(122,90,26,.35) inset,
    0 6px 16px -6px rgba(184,134,46,.55)}
.mc-seg button:focus-visible{outline:2px solid var(--gold);outline-offset:2px}

#mc-weight{width:100%;padding:12px 14px;border:1px solid var(--line);
  border-radius:10px;background:var(--paper);color:var(--ink);
  font:600 16px/1 "IBM Plex Mono",monospace;
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset;
  transition:border-color .18s ease, box-shadow .18s ease}
#mc-weight:focus{outline:0;border-color:var(--gold);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--gold) 22%,transparent)}

.mc-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.mc-chips button{font:500 11.5px/1 "IBM Plex Sans",sans-serif;
  padding:6px 12px;border:1px solid var(--line);background:var(--paper);
  color:var(--ink-3);border-radius:999px;cursor:pointer;
  box-shadow:0 1px 0 rgba(255,255,255,.6) inset;
  transition:transform .18s cubic-bezier(.2,.7,.3,1),
    border-color .18s ease, color .18s ease, background .18s ease,
    box-shadow .18s ease}
.mc-chips button:hover{border-color:color-mix(in srgb,var(--gold) 55%,var(--line));
  color:var(--ink);background:color-mix(in srgb,var(--gold) 6%,var(--paper));
  transform:translateY(-1px)}
.mc-chips button:focus-visible{outline:2px solid var(--gold);outline-offset:2px}

.mc-headline{background:linear-gradient(160deg,var(--board),var(--board-2));
  border:1px solid rgba(217,178,74,.35);border-radius:16px;padding:20px 22px;
  margin:18px 0;color:#EDE9DD}
.mc-headline .mh-k{font:600 11px/1 "IBM Plex Sans",sans-serif;
  text-transform:uppercase;letter-spacing:.08em;color:#B9C2B4}
.mc-headline .mh-v{font-family:"IBM Plex Mono",monospace;font-size:clamp(24px,5vw,34px);
  font-weight:700;color:#F6F1E3;margin:6px 0 2px}
.mc-headline .mh-sub{font-size:14px;color:#B9C2B4}
.mc-headline b{color:var(--gold)}

.mc-insight{border-radius:14px;padding:14px 16px;margin:14px 0;font-size:14.5px;
  line-height:1.6;border:1px solid}
.mc-insight.warn{background:color-mix(in srgb,var(--warm) 10%,transparent);
  border-color:color-mix(in srgb,var(--warm) 40%,transparent);color:var(--ink)}
.mc-insight.good{background:color-mix(in srgb,var(--emerald) 10%,transparent);
  border-color:color-mix(in srgb,var(--emerald) 40%,transparent);color:var(--ink)}

.mc-row{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:16px 18px;margin:10px 0;transition:border-color .15s}
.mc-row.best{border-color:var(--gold);box-shadow:0 2px 16px rgba(217,178,74,.13)}
.mc-top{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.mc-rank{font:700 12px/1 "IBM Plex Mono",monospace;color:var(--ink-3);min-width:20px}
.mc-brand{font-weight:600;font-size:16px;color:var(--ink)}
.mc-badge{font:600 10px/1 "IBM Plex Sans",sans-serif;text-transform:uppercase;
  letter-spacing:.06em;padding:4px 8px;border-radius:20px;
  background:var(--gold);color:#231a02}
.mc-badge.soft{background:transparent;border:1px solid var(--line);color:var(--ink-3)}
.mc-total{margin-left:auto;font-family:"IBM Plex Mono",monospace;font-size:20px;
  font-weight:700;color:var(--ink)}
.mc-delta{font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--warm);
  margin-left:8px}
.mc-bar{display:flex;height:9px;border-radius:6px;overflow:hidden;margin:12px 0 9px;
  background:var(--line)}
.mc-bar i{display:block;height:100%}
.mc-bar .b-gold{background:linear-gradient(90deg,#E3BF63,#B07E12)}
.mc-bar .b-mc{background:var(--warm)}
.mc-bar .b-gst{background:var(--ink-3);opacity:.55}
.mc-legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12.5px;color:var(--ink-2)}
.mc-legend span{display:inline-flex;align-items:center;gap:5px}
.mc-legend i{width:9px;height:9px;border-radius:3px;display:inline-block}
.mc-legend b{font-family:"IBM Plex Mono",monospace;color:var(--ink);font-weight:600}
.mc-empty{color:var(--ink-3);padding:26px 4px;text-align:center;font-size:14px}
.mc-method{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:18px 20px;margin:26px 0 18px}
.mc-method h2{font-size:17px;margin:0 0 10px}
.mc-method p{font-size:14px;line-height:1.7;color:var(--ink-2);margin:0 0 10px}
.mc-method p:last-child{margin-bottom:0}

/* ---- motion: results animate in, bars grow, winner pulses once ---- */
@keyframes mcRise{from{opacity:0;transform:translateY(10px)}
  to{opacity:1;transform:none}}
@keyframes mcGrow{from{width:0}}
@keyframes mcGlow{0%{box-shadow:0 2px 16px rgba(217,178,74,0)}
  55%{box-shadow:0 2px 26px rgba(217,178,74,.4)}
  100%{box-shadow:0 2px 16px rgba(217,178,74,.13)}}
@keyframes mcPop{from{opacity:0;transform:scale(.92)}to{opacity:1;transform:none}}
.mc-row{animation:mcRise .38s cubic-bezier(.2,.7,.3,1) both}
.mc-row:nth-child(2){animation-delay:.06s}
.mc-row:nth-child(3){animation-delay:.12s}
.mc-row:nth-child(4){animation-delay:.18s}
.mc-row:nth-child(5){animation-delay:.24s}
.mc-row.best{animation:mcRise .38s cubic-bezier(.2,.7,.3,1) both,
  mcGlow 1.1s ease-out .3s both}
.mc-bar i{animation:mcGrow .55s cubic-bezier(.2,.7,.3,1) both;animation-delay:.15s}
.mc-headline{animation:mcRise .4s cubic-bezier(.2,.7,.3,1) both}
.mc-insight{animation:mcPop .38s cubic-bezier(.2,.7,.3,1) both;animation-delay:.1s}
.mc-total{transition:color .2s}
.mc-row:hover{border-color:var(--gold)}
.mc-row:hover .mc-total{color:var(--gold)}
.mc-seg button{transform:translateZ(0)}
.mc-seg button[aria-pressed="true"]{animation:mcPop .22s ease-out}
@media(prefers-reduced-motion:reduce){
  .mc-row,.mc-row.best,.mc-bar i,.mc-headline,.mc-insight,
  .mc-seg button[aria-pressed="true"]{animation:none}
}
</style>
<script>
(function(){
  var D = __DATA__;
  var GST = 0.03;
  var WEIGHTS = [
    {g:2,  label:"2g · studs"},
    {g:5,  label:"5g · ring"},
    {g:8,  label:"8g · chain"},
    {g:10, label:"10g · bangle"},
    {g:20, label:"20g · pair"},
    {g:50, label:"50g · set"}
  ];
  var KARATS = [["22","22K (916)"],["24","24K (999)"],["18","18K (750)"]];

  var state = { cat: (D.cats[0]||""), weight: 10, karat: "22" };

  function $(id){ return document.getElementById(id); }
  function inr(n){
    if(n==null||isNaN(n)) return "-";
    return "₹" + Math.round(n).toLocaleString("en-IN");
  }
  function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }

  function seg(host, items, cur, onPick){
    host.innerHTML = "";
    items.forEach(function(it){
      var val = it[0], lab = it[1];
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = lab;
      b.setAttribute("aria-pressed", val === cur ? "true" : "false");
      b.onclick = function(){ onPick(val); };
      host.appendChild(b);
    });
  }

  function compute(){
    var out = [];
    Object.keys(D.brands).forEach(function(name){
      var b = D.brands[name];
      var mc = b.mc[state.cat];
      var rate = b.rates[state.karat];
      if(!mc || !rate) return;
      var gold   = rate * state.weight;
      var making = gold * (mc.pct/100);
      var gst    = (gold + making) * GST;
      out.push({ name:name, rate:rate, pct:mc.pct, n:mc.n, conf:mc.conf,
                 gold:gold, making:making, gst:gst,
                 total: gold + making + gst });
    });
    out.sort(function(a,b){ return a.total - b.total; });
    return out;
  }

  function render(){
    var rows = compute();
    var host = $("mc-results");
    var head = $("mc-headline"), ins = $("mc-insight");

    if(!rows.length){
      host.innerHTML = '<div class="mc-empty">No jeweller in our making-charge '
        + 'sample stocks this combination yet.</div>';
      head.hidden = true; ins.hidden = true; $("mc-note").textContent = "";
      return;
    }

    var best = rows[0], worst = rows[rows.length-1];
    var item = state.weight + "g " + state.cat.toLowerCase();

    head.hidden = false;
    head.innerHTML =
      '<div class="mh-k">Cheapest for a ' + esc(item) + ' in ' + state.karat + 'K</div>'
      + '<div class="mh-v">' + inr(best.total) + ' &middot; <b>' + esc(best.name) + '</b></div>'
      + '<div class="mh-sub">All-in: gold + making charge + 3% GST.'
      + (rows.length > 1
          ? ' You would pay ' + inr(worst.total - best.total)
            + ' more at ' + esc(worst.name) + '.'
          : '')
      + '</div>';

    // The headline insight: lowest per-gram rate is often NOT the best deal.
    var byRate = rows.slice().sort(function(a,b){ return a.rate - b.rate; });
    var cheapRate = byRate[0];
    if(rows.length > 1 && cheapRate.name !== best.name){
      var diff = cheapRate.total - best.total;
      ins.hidden = false;
      ins.className = "mc-insight warn";
      ins.innerHTML = "⚠️ <strong>" + esc(cheapRate.name) + " has the lowest gold rate ("
        + inr(cheapRate.rate) + "/g) but is not the cheapest overall.</strong> Its "
        + cheapRate.pct + "% making charge on this piece makes it " + inr(diff)
        + " dearer than " + esc(best.name) + ". This is exactly the trap a rate-only "
        + "comparison hides.";
    } else if(rows.length > 1){
      ins.hidden = false;
      ins.className = "mc-insight good";
      ins.innerHTML = "✓ <strong>" + esc(best.name) + " wins on both counts</strong> — "
        + "lowest gold rate (" + inr(best.rate) + "/g) and the lowest all-in price "
        + "for this piece, helped by a " + best.pct + "% making charge.";
    } else { ins.hidden = true; }

    host.innerHTML = rows.map(function(r, i){
      var gp = r.gold/r.total*100, mp = r.making/r.total*100, sp = r.gst/r.total*100;
      var confLab = r.conf === "high" ? "" :
        '<span class="mc-badge soft">' + (r.n||0) + ' item' + (r.n===1?'':'s') + '</span>';
      return '<div class="mc-row' + (i===0?' best':'') + '">'
        + '<div class="mc-top">'
          + '<span class="mc-rank">' + (i+1) + '</span>'
          + '<span class="mc-brand">' + esc(r.name) + '</span>'
          + (i===0 ? '<span class="mc-badge">Best price</span>' : '')
          + confLab
          + '<span class="mc-total">' + inr(r.total)
          + (i>0 ? '<span class="mc-delta">+' + inr(r.total-best.total) + '</span>' : '')
          + '</span>'
        + '</div>'
        + '<div class="mc-bar">'
          + '<i class="b-gold" style="width:' + gp.toFixed(1) + '%"></i>'
          + '<i class="b-mc" style="width:' + mp.toFixed(1) + '%"></i>'
          + '<i class="b-gst" style="width:' + sp.toFixed(1) + '%"></i>'
        + '</div>'
        + '<div class="mc-legend">'
          + '<span><i class="b-gold" style="background:linear-gradient(90deg,#E3BF63,#B07E12)"></i>'
            + 'Gold <b>' + inr(r.gold) + '</b> <span style="opacity:.6">@'
            + inr(r.rate) + '/g</span></span>'
          + '<span><i style="background:var(--warm)"></i>Making <b>' + inr(r.making)
            + '</b> <span style="opacity:.6">' + r.pct + '%</span></span>'
          + '<span><i style="background:var(--ink-3);opacity:.55"></i>GST <b>'
            + inr(r.gst) + '</b></span>'
        + '</div>'
      + '</div>';
    }).join("");

    $("mc-note").textContent = "Comparing " + rows.length + " jeweller"
      + (rows.length===1?"":"s") + " we have verified making-charge data for. "
      + "Badges show how many real products the median is based on.";
  }

  // ---- build controls ----
  function build(){
    seg($("mc-cats"), D.cats.map(function(c){ return [c,c]; }), state.cat,
        function(v){ state.cat = v; build(); });
    seg($("mc-karats"), KARATS, state.karat,
        function(v){ state.karat = v; build(); });
    render();
  }

  var chips = $("mc-wchips");
  WEIGHTS.forEach(function(w){
    var b = document.createElement("button");
    b.type = "button"; b.textContent = w.label;
    b.onclick = function(){ state.weight = w.g; $("mc-weight").value = w.g; render(); };
    chips.appendChild(b);
  });
  $("mc-weight").addEventListener("input", function(){
    var v = parseFloat(this.value);
    if(!isNaN(v) && v > 0){ state.weight = v; render(); }
  });

  build();
})();
</script>
"""


# =====================================================================
# Private analytics dashboard. Built to docs/analytics.html. Placeholders
# __SB__ / __KEY__ / __DATE__ are filled at build time via str.replace()
# (NOT f-string / Template) so JS braces and $ are literal. Reads aggregates
# through the secret-gated analytics_report() RPC; the raw anon key alone can
# only INSERT, never read. The access token is NOT embedded - it is read at
# view time from the URL fragment (.../analytics#token), so the hosted file
# holds no secret. noindex + robots-disallowed + unlinked.
# =====================================================================
ANALYTICS_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>Private Analytics - MyGoldRates</title>
<style>
:root{--bg:#0f1115;--card:#181b22;--line:#272b34;--ink:#eef1f6;--ink2:#a7afbe;
  --gold:#e3bf63;--emerald:#54c08a;--warm:#e08a6a;--accent:#6aa0e0}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1060px;margin:0 auto;padding:22px 18px 60px}
h1{font-size:21px;margin:0 0 2px;letter-spacing:.02em}
h1 b{color:var(--gold)}
.sub{color:var(--ink2);font-size:12.5px;margin:0 0 18px}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;
  background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:14px 16px;margin-bottom:16px}
.filters label{display:block;font-size:11px;text-transform:uppercase;
  letter-spacing:.06em;color:var(--ink2);margin-bottom:4px}
.filters input,.filters select{background:var(--bg);border:1px solid var(--line);
  color:var(--ink);border-radius:8px;padding:8px 10px;font-size:13px;min-width:150px}
.btn{background:var(--gold);color:#231a02;border:0;border-radius:8px;
  padding:9px 16px;font-weight:600;font-size:13px;cursor:pointer}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:12px;margin-bottom:18px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpi .n{font-size:28px;font-weight:700;letter-spacing:.01em}
.kpi .l{color:var(--ink2);font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-top:2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px;margin-bottom:16px}
.card h2{font-size:14px;margin:0 0 12px;color:var(--ink);letter-spacing:.03em}
.chart{display:flex;align-items:flex-end;gap:4px;height:170px;padding-top:6px;overflow-x:auto}
.bar{flex:1;min-width:14px;display:flex;flex-direction:column;justify-content:flex-end;
  align-items:center;gap:4px;height:100%}
.bar .fill{width:70%;background:linear-gradient(180deg,var(--gold),#b8952f);
  border-radius:4px 4px 0 0;min-height:2px;transition:height .2s}
.bar .v{font-size:10px;color:var(--ink2)}
.bar .d{font-size:9.5px;color:var(--ink2);white-space:nowrap;transform:rotate(0deg)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--ink2);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
td.path{color:var(--accent);word-break:break-all}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:720px){.grid2{grid-template-columns:1fr}}
.msg{color:var(--ink2);padding:22px 4px;text-align:center;font-size:13px}
.err{color:var(--warm)}
.status{font-size:12px;color:var(--ink2);margin-left:auto}
.foot{color:var(--ink2);font-size:11.5px;margin-top:24px;line-height:1.6}
</style>
</head>
<body>
<div class="wrap">
  <h1>My<b>Gold</b>Rates - Private Analytics</h1>
  <p class="sub">Day-wise visitor activity. Built __DATE__. Private: readable only via your secret link (the URL ending in #your-token).</p>

  <div class="filters">
    <div><label>From</label><input type="date" id="from"></div>
    <div><label>To</label><input type="date" id="to"></div>
    <div><label>Page</label><select id="page"><option value="">All pages</option></select></div>
    <button class="btn" id="apply">Apply</button>
    <button class="btn ghost" id="today">Today</button>
    <button class="btn ghost" id="quick7">Last 7d</button>
    <button class="btn ghost" id="quick30">Last 30d</button>
    <span class="status" id="status"></span>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="card">
    <h2>Daily page views</h2>
    <div class="chart" id="chart"></div>
  </div>

  <div class="grid2">
    <div class="card"><h2>Top pages</h2><div id="pages"></div></div>
    <div class="card"><h2>Most-clicked elements</h2><div id="clicks"></div></div>
  </div>

  <div class="grid2">
    <div class="card"><h2>Traffic sources (referrers)</h2><div id="refs"></div></div>
    <div class="card"><h2>Traffic by host (www vs apex)</h2><div id="hosts"></div></div>
  </div>

  <p class="foot" id="foot"></p>
</div>

<script>
(function(){
  // SECRET-LINK MODEL: the access token is read from the URL fragment
  // (e.g. .../analytics#your-token), never embedded in this file. The fragment
  // is never sent to any server, logged, or put in the Referer header - so the
  // hosted page carries no secret; only someone with the full link can read data.
  var SB="__SB__", KEY="__KEY__",
      TOKEN=(location.hash ? decodeURIComponent(location.hash.slice(1)) : "");
  var $=function(id){return document.getElementById(id);};
  function nfmt(n){try{return Number(n).toLocaleString('en-IN');}catch(e){return n;}}
  // toISOString() renders in UTC, not IST - for the ~5.5h window between
  // midnight IST and midnight UTC (00:00-05:30 IST), that made "Today"
  // still show yesterday's date, out of step with the server's `day`
  // column (generated as IST calendar date). en-CA locale formats as
  // YYYY-MM-DD, giving an ISO-shaped string in the zone we actually want.
  function iso(d){
    return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata'}).format(d);
  }
  // A Date pinned to IST-midnight-as-UTC, so getUTCDate()/setUTCDate() day
  // arithmetic is immune to the visitor's own browser timezone - getDate()/
  // setDate() read local time, which would silently disagree with iso()'s
  // IST-based formatting again for any visitor not set to IST.
  function todayIST(){
    var p=iso(new Date()).split('-');
    return new Date(Date.UTC(+p[0],+p[1]-1,+p[2]));
  }
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}

  // default range: today only
  var today=todayIST();
  $('from').value=iso(today); $('to').value=iso(today);

  // friendly names for click labels (raw element ids -> readable actions)
  var CLICK_LABELS={
    'drtab':'Rate-trend drawer','cdtab':'Calculator drawer','coindtab':'Coin drawer',
    'nearbtn':'Brands near me','gstbtn':'GST toggle (+3%)','brandsearch':'Jeweller search',
    'navtog':'Menu (hamburger)','gate-close':'Sign-in gate: dismissed',
    'gate-gbtn':'Sign-in gate: Continue with Google','gate-form':'Sign-in gate: manual form',
    'gate-enrich':'Sign-in gate: details step','m-form':'Subscribe form','mbtn':'Subscribe button',
    'inq':'Inquiry form','apply':'Analytics: Apply','today':'Analytics: Today'};
  function friendly(t){
    if(t==null||t==='')return '(unlabelled)';
    if(CLICK_LABELS[t])return CLICK_LABELS[t];
    var s=String(t);
    if(s.indexOf('Use my current location')>-1||s.indexOf('location to autofill')>-1)
      return 'Use my location (autofill)';
    if(/^(24K|22K|18K|14K)$/.test(s))return s+' rate column';
    s=s.replace(/^[^\x00-\x7F]+\s*/,'').trim();   // drop a leading emoji/pin
    return s||String(t);
  }

  function setStatus(t,isErr){var s=$('status');s.textContent=t;
    s.className='status'+(isErr?' err':'');}

  function rpc(){
    var body={p_secret:TOKEN,p_from:$('from').value,p_to:$('to').value,
      p_page:$('page').value||null};
    setStatus('Loading...');
    return fetch(SB+'/rest/v1/rpc/analytics_report',{method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,
        'Authorization':'Bearer '+KEY},
      body:JSON.stringify(body)}).then(function(r){return r.json();});
  }

  function renderKPIs(t){
    var k=$('kpis');
    var items=[['Page views',t.views],['Unique visitors',t.visitors],['Clicks',t.clicks]];
    k.innerHTML=items.map(function(it){
      return '<div class="kpi"><div class="n">'+nfmt(it[1]||0)+
        '</div><div class="l">'+it[0]+'</div></div>';}).join('');
  }

  function renderChart(daily){
    var c=$('chart');
    if(!daily||!daily.length){c.innerHTML='<div class="msg">No views in this range yet.</div>';return;}
    var max=0; daily.forEach(function(d){if(d.views>max)max=d.views;});
    max=max||1;
    c.innerHTML=daily.map(function(d){
      var h=Math.round((d.views/max)*130)+8;
      var dd=(d.day||'').slice(8,10);
      return '<div class="bar" title="'+esc(d.day)+': '+nfmt(d.views)+' views, '+
        nfmt(d.visitors)+' visitors"><span class="v">'+nfmt(d.views)+
        '</span><div class="fill" style="height:'+h+'px"></div>'+
        '<span class="d">'+dd+'</span></div>';}).join('');
  }

  function renderTable(el,rows,cols){
    if(!rows||!rows.length){el.innerHTML='<div class="msg">No data yet.</div>';return;}
    var head='<tr>'+cols.map(function(c){
      return '<th'+(c.num?' class="num"':'')+'>'+c.h+'</th>';}).join('')+'</tr>';
    var body=rows.map(function(r){
      return '<tr>'+cols.map(function(c){
        var v=r[c.k]; if(c.num)return '<td class="num">'+nfmt(v||0)+'</td>';
        return '<td class="'+(c.path?'path':'')+'">'+esc(v)+'</td>';
      }).join('')+'</tr>';}).join('');
    el.innerHTML='<table>'+head+body+'</table>';
  }

  function fillPages(list){
    var sel=$('page'); if(!list||!list.length)return;
    var cur=sel.value;
    var opts='<option value="">All pages</option>'+list.map(function(p){
      return '<option value="'+esc(p)+'">'+esc(p)+'</option>';}).join('');
    sel.innerHTML=opts; sel.value=cur;
  }

  function load(){
    rpc().then(function(d){
      if(!d||d.error){
        setStatus(d&&d.error==='unauthorized'?'Access token not configured':'Error',true);
        $('kpis').innerHTML='<div class="msg err">'+
          (d&&d.error==='unauthorized'
            ? 'Open this page using your private link (the URL ending in #your-token). Without it, no data is shown.'
            : 'Could not load analytics.')+'</div>';
        return;
      }
      var t=d.totals||{views:0,visitors:0,clicks:0};
      renderKPIs(t);
      renderChart(d.daily);
      renderTable($('pages'),d.top_pages,[{h:'Page',k:'page',path:true},
        {h:'Views',k:'views',num:true},{h:'Visitors',k:'visitors',num:true}]);
      (d.top_clicks||[]).forEach(function(r){r.target=friendly(r.target);});
      renderTable($('clicks'),d.top_clicks,[{h:'Action',k:'target'},
        {h:'Clicks',k:'clicks',num:true}]);
      renderTable($('refs'),d.top_referrers,[{h:'Referrer',k:'referrer',path:true},
        {h:'Views',k:'views',num:true}]);
      renderTable($('hosts'),d.top_hosts,[{h:'Host',k:'host'},
        {h:'Views',k:'views',num:true}]);
      fillPages(d.pages_list);
      $('foot').textContent='Range '+d.from+' to '+d.to+
        (d.page_filter?(' - filtered to '+d.page_filter):'')+
        '. No personal data is collected: only page path, referrer, a random '+
        'session id and click labels.';
      setStatus('Updated '+new Date().toLocaleTimeString());
    }).catch(function(){setStatus('Network error',true);});
  }

  $('apply').onclick=load;
  $('today').onclick=function(){var a=todayIST();
    $('from').value=iso(a);$('to').value=iso(a);load();};
  $('quick7').onclick=function(){var a=todayIST(),b=todayIST();b.setUTCDate(b.getUTCDate()-6);
    $('from').value=iso(b);$('to').value=iso(a);load();};
  $('quick30').onclick=function(){var a=todayIST(),b=todayIST();b.setUTCDate(b.getUTCDate()-29);
    $('from').value=iso(b);$('to').value=iso(a);load();};
  $('page').onchange=load;
  load();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
