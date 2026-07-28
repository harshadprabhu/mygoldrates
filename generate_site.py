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
PURITY_FRACTION = {"24K": 0.999, "22K": 0.916, "18K": 0.750, "14K": 0.583}
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


# City/state landing pages: same national board, one URL per location.
LOCATIONS = [
    # metros & major cities
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kanpur", "Nagpur",
    "Indore", "Bhopal", "Patna", "Chandigarh", "Kochi", "Coimbatore",
    "Madurai", "Visakhapatnam", "Vijayawada", "Mysuru", "Thrissur",
    "Kozhikode", "Thiruvananthapuram", "Guwahati", "Bhubaneswar",
    "Ludhiana", "Amritsar", "Vadodara", "Nashik", "Rajkot", "Varanasi",
    "Agra", "Meerut", "Faridabad", "Ghaziabad", "Gurugram", "Noida",
    "Ranchi", "Raipur", "Jodhpur", "Udaipur", "Kota", "Dehradun",
    "Jamshedpur", "Dhanbad", "Aurangabad", "Solapur", "Tiruchirappalli",
    "Salem", "Tirupati", "Guntur", "Warangal", "Mangaluru", "Hubli",
    "Belagavi", "Kolhapur", "Jalandhar", "Siliguri", "Cuttack", "Ajmer",
    "Gwalior", "Jabalpur", "Allahabad", "Bareilly", "Moradabad", "Aligarh",
    "Vijayapura", "Davanagere", "Erode", "Tirunelveli", "Kollam", "Kannur",
    # states & UTs
    "Maharashtra", "Tamil Nadu", "Karnataka", "Kerala", "Telangana",
    "Andhra Pradesh", "Gujarat", "Rajasthan", "West Bengal",
    "Uttar Pradesh", "Madhya Pradesh", "Punjab", "Haryana", "Bihar",
    "Odisha", "Assam", "Jharkhand", "Uttarakhand", "Himachal Pradesh",
    "Goa",
]


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
  <p>The number before the "K" (karat) tells you how pure the gold is. Pure
  gold is 24 karat; lower karats mix in other metals for strength.</p>
  <h2>24K gold (99.9% pure)</h2>
  <p>24K, also stamped <strong>999</strong>, is the purest investment-grade
  gold, used for coins, bars and digital gold. It is soft and scratches
  easily, so it is rarely used for intricate jewellery. Today the 24K rate is
  about <strong>{rate_str}/g</strong> (pre-GST).</p>
  <h2>22K gold (91.6% pure)</h2>
  <p>22K, stamped <strong>916</strong>, is 91.6% gold with 8.4% alloy for
  durability - the standard for Indian jewellery. At today's rates 22K works
  out to roughly <strong>{inr(med['22K'])}/g</strong>.</p>
  <h2>Which should you buy?</h2>
  <ul>
    <li><strong>For investment:</strong> 24K coins/bars - maximum purity, easy
    to value and resell.</li>
    <li><strong>For jewellery you'll wear:</strong> 22K - holds designs and
    stones far better.</li>
    <li><strong>For diamond or daily-wear pieces:</strong> 18K (75%) is harder
    still.</li>
  </ul>
  <p>Whatever you choose, compare the <a href="{SITE_URL}/">gold rate today</a>
  across jewellers first - the per-gram rate can differ by &#8377;50-150.</p>"""),
        ("gold-hallmarking",
         "Gold Hallmarking in India - BIS Hallmark & HUID Explained | MyGoldRates",
         "What the BIS hallmark and 6-digit HUID mean, how to check purity, and "
         "why hallmarked gold protects you when buying jewellery in India.",
         "Gold Hallmarking (BIS): What to Check Before You Buy",
         f"""
  <p>A <strong>BIS hallmark</strong> is an official certification that your
  gold's purity is genuine. Since 2021 hallmarking is mandatory for gold
  jewellery sold in most of India.</p>
  <h2>The three marks to look for</h2>
  <ul>
    <li>The <strong>BIS logo</strong> (a triangle).</li>
    <li>The <strong>purity/fineness</strong>, e.g. 22K916, 18K750 or 24K999.</li>
    <li>A <strong>6-digit alphanumeric HUID</strong> (Hallmark Unique ID)
    unique to that piece.</li>
  </ul>
  <h2>Why it matters</h2>
  <p>Hallmarking guarantees you are paying for the purity you are billed for.
  You can verify a HUID in the free BIS Care app. Always insist on a proper
  tax invoice that states the purity and net gold weight separately from
  making charges.</p>
  <h2>Check the rate too</h2>
  <p>Hallmarking confirms purity, not price. Compare the day's
  <a href="{SITE_URL}/">gold rate</a> and the
  <a href="{SITE_URL}/making-charges-calculator">making charges</a> so you know
  the fair billed amount before you pay.</p>"""),
        ("how-gold-rates-are-set",
         "How Gold Rates Are Set in India - Explained | MyGoldRates",
         "How daily gold rates in India are decided: international spot price, "
         "rupee-dollar rate, import duty, GST, and jeweller premiums.",
         "How Are Gold Rates Set in India?",
         f"""
  <p>The gold rate you see at a jeweller is built up from several layers.</p>
  <h2>1. International spot price</h2>
  <p>Gold trades globally in US dollars per troy ounce. This is the base that
  moves 24x7 with demand, interest rates and global risk.</p>
  <h2>2. Rupee-dollar exchange rate</h2>
  <p>The dollar price is converted to rupees, so a weaker rupee pushes Indian
  gold prices up even if global gold is flat.</p>
  <h2>3. Import duty &amp; GST</h2>
  <p>India imports most of its gold, so customs duty is added, then 3% GST on
  top at billing.</p>
  <h2>4. Association benchmark &amp; jeweller premium</h2>
  <p>Bodies like the <strong>IBJA</strong> publish a daily bullion reference.
  Individual jewellers add a small premium over this for sourcing and
  hallmarking - which is why rates differ slightly between brands.</p>
  <p>We track that gap for you: see the live
  <a href="{SITE_URL}/">gold rate today</a> and each jeweller's premium over
  the IBJA benchmark.</p>"""),
        ("making-charges-explained",
         "Gold Making Charges Explained - How They Work | MyGoldRates",
         "What gold making charges and wastage are, how they're calculated "
         "(% or per gram), and how to reduce what you pay in India.",
         "Gold Making Charges &amp; Wastage, Explained",
         f"""
  <p><strong>Making charges</strong> are what a jeweller charges to turn raw
  gold into a finished piece - the labour and design cost - on top of the metal
  value.</p>
  <h2>How they're charged</h2>
  <ul>
    <li><strong>As a percentage</strong> of the gold value (commonly 8-25%).</li>
    <li><strong>As a flat rate per gram</strong> (e.g. &#8377;400-800/g).</li>
  </ul>
  <p>Intricate or machine-light handmade designs cost more; plain coins and
  bars have little or no making charge.</p>
  <h2>The final bill</h2>
  <p>Billed price = gold value + making charges + 3% GST (on the total). On a
  &#8377;1,00,000 piece, a 15% making charge plus GST can add roughly
  &#8377;18,000.</p>
  <h2>How to pay less</h2>
  <ul>
    <li>Compare making charges between jewellers - they are negotiable.</li>
    <li>Prefer lightweight or plain designs for better value.</li>
    <li>Use our <a href="{SITE_URL}/making-charges-calculator">making charges
    calculator</a> to see the true final price before you buy.</li>
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

    median24 = statistics.median(r["canonical_24k_pre_gst"] for r in live)
    lowest = min(live, key=lambda r: r["canonical_24k_pre_gst"])
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

    # --------------------------------------------------------------- IBJA
    ibja = fetch_ibja()
    if ibja:
        r999, r916 = ibja
        premium_med = (median24 / r999 - 1) * 100
        ibja_tiles = f'''
<section class="ibja-ref" aria-labelledby="ibjarefh">
  <p class="eyebrow">Bullion &amp; Futures Reference</p>
  <h2 id="ibjarefh">IBJA Gold Rate Today</h2>
  <p class="hint">The India Bullion &amp; Jewellers Association 24K benchmark,
  pre-GST - the wholesale rate jewellers price above - alongside the
  exchange-traded gold futures quote.</p>
  <div class="ref-tiles">
    <div class="rtile"><div class="k">IBJA 999 Fine · 24K</div>
      <div class="v">{inr(r999)}</div><div class="u">per gram, pre-GST</div></div>
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
        ibja_tiles = (f'<section class="ibja-ref"><p class="eyebrow">Futures '
                      f'Reference</p><div class="ref-tiles">{mcx_tile}</div>'
                      f'</section>') if mcx_tile else ""
        ibja_faq = ("The IBJA (India Bullion and Jewellers Association) "
                    "publishes India's twice-daily bullion reference rate. "
                    "Jeweller board rates typically sit slightly above it, "
                    "reflecting sourcing and hallmarking premiums.")

    # ---------------------------------------------------------- table rows
    body_rows = []
    for r in sorted(live, key=lambda x: x["canonical_24k_pre_gst"]):
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
        body_rows.append(
            f'<tr data-states="{data_states}"><th scope="row">'
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

    # Google sign-in: dormant until the GOOGLE_CLIENT_ID secret is set.
    gclient = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    gsi = ('<script src="https://accounts.google.com/gsi/client" async defer>'
           '</script>') if gclient else ""

    sig_ver = hashlib.md5(SIGNUP_JS.encode()).hexdigest()[:8]
    common = dict(site_url=SITE_URL, date=display_date, time=display_time,
                  iso_now=now_ist.isoformat(), year=str(now_ist.year),
                  base_css=BASE_CSS, ads_head=ads_head,
                  gclient=gclient, gsi=gsi, google_btn="",
                  sig_ver=sig_ver, nav=NAV)
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
        """Unique per-city body so city pages aren't near-duplicates."""
        if nm == "India":
            return ""
        return (
            f'<section class="seo"><h2>Gold Rate Today in {nm}</h2>'
            f'<p>The <strong>gold rate today in {nm}</strong> is '
            f'<strong>{inr(med["24K"])} per gram for 24K (999)</strong> and '
            f'<strong>{inr(med["22K"])} per gram for 22K (916)</strong>, '
            f'pre-GST - the live median from {len(live)} of India’s leading '
            f'jewellers shown above. National chains such as Tanishq, Malabar '
            f'Gold and Kalyan Jewellers quote the same board rate in {nm} as '
            f'across India, so these figures are accurate for buyers in {nm} '
            f'today. Right now {lowest["brands"]["name"]} lists the lowest 24K '
            f'rate at {low_g} per gram.</p>'
            f'<p>Buying gold in {nm}? Compare each jeweller and its premium in '
            f'the table above, estimate the billed price with our '
            f'<a href="{SITE_URL}/making-charges-calculator">making charges '
            f'calculator</a> (3% GST and making charges are extra), and read '
            f'<a href="{SITE_URL}/learn/22k-vs-24k-gold">22K vs 24K gold</a> '
            f'before you choose. Prefer a daily update? Get '
            f'<a href="{SITE_URL}/inquiry">free {nm} gold rate alerts</a> by '
            f'email.</p></section>')

    tvars = dict(
        n_brands=str(len(live)),
        med24=inr(med["24K"]), med22=inr(med["22K"]), med18=inr(med["18K"]),
        low24=inr(ladder(lowest["canonical_24k_pre_gst"])["24K"]),
        low_brand=lowest["brands"]["name"],
        low_logo=low_logo,
        ibja_tiles=ibja_tiles, ibja_section=ibja_section, ads_unit=ads_unit,
        calc_brands=json.dumps(calc_brands),
        supabase_url=supabase_url, anon_key=anon_key,
        rows="\n".join(body_rows), faq=faq_html, jsonld=jsonld,
        seo_content=seo_content, drawer=drawer, news_home=news_home, **common)
    html = TEMPLATE.substitute(
        where="in India", where_note="", local_intro="",
        canonical_url=f"{SITE_URL}/", city_links=city_cloud(), **tvars)
    inquiry = INQUIRY_TEMPLATE.substitute(
        supabase_url=supabase_url, anon_key=anon_key, **common)
    unsub = UNSUB_TEMPLATE.substitute(
        supabase_url=supabase_url, anon_key=anon_key, **common)

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
  <p>We'd love to hear from you - whether it's feedback, a correction to a
  rate, a partnership enquiry, or a data-privacy request.</p>
  <h2>Email</h2>
  <p><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a><br>
  We aim to reply within 2-3 working days.</p>
  <h2>Daily rate alerts</h2>
  <p>To get the day's gold-rate comparison in your inbox each morning,
  <a href="{SITE_URL}/inquiry.html">subscribe here</a>. You can unsubscribe from
  any email at any time.</p>
  <h2>Privacy requests</h2>
  <p>To access or delete the personal details you've shared with us, email the
  address above or see our
  <a href="{SITE_URL}/privacy.html">Privacy Policy</a>.</p>""")

    write_page(
        "privacy",
        "Privacy Policy - GoldRates",
        "How GoldRates collects, uses and protects your personal information, "
        "including cookies and advertising.",
        "Privacy Policy",
        f"""
  <p>This policy explains what information GoldRates ("we", "us") collects when
  you use <a href="{SITE_URL}/">mygoldrates.com</a>, how we use it, and the
  choices you have.</p>
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
  <p>We may display ads served by Google, using
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

    def render_content(slug, title, desc, body, extra_js="", jsonld_block=""):
        path = f"docs/{slug}.html"
        d = os.path.dirname(path)
        if d and d != "docs":
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(CONTENT_TEMPLATE.substitute(
                title=title, desc=desc, canonical=f"{SITE_URL}/{slug}",
                body=body, extra_js=extra_js, jsonld_block=jsonld_block,
                **common))

    rate24 = round(median24, 2)
    rate_str = inr(med["24K"])

    def crumbs(*items):
        parts = [f'<a href="{SITE_URL}/">Home</a>']
        for label, href in items:
            parts.append(f'<a href="{href}">{label}</a>' if href else label)
        return '<p class="crumbs">' + ' &rsaquo; '.join(parts) + '</p>'

    # ---- Calculators hub ----
    tools = [
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
    hub_cards = (f'<a class="toolcard" href="{SITE_URL}/#calch"><b>Gold Price '
                 f'Calculator</b><span>Cost of gold by weight, purity and '
                 f'brand.</span></a>' + hub_cards)
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

    # ---- News: auto daily market recap from the rate history ----
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
        render_content(f"news/recap/{slug}",
                       f"Gold Rate Daily Recap - {disp} | MyGoldRates",
                       f"Gold price recap for {disp}: 24K median {inr(m24)}/g, "
                       f"{sign}{abs(pct):.2f}% vs the previous session. 22K, 18K "
                       "and jeweller medians.",
                       body)
        recaps.append((slug, dt, disp, m24, move, pct))
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
    print(f"content pages: 4 calculators, "
          f"{len(list(_articles(rate_str, med, inr)))} articles, "
          f"{len(recaps)} recaps")
    with open("docs/robots.txt", "w", encoding="utf-8") as f:
        # Explicitly welcome AI/LLM crawlers so generative engines (ChatGPT,
        # Claude, Perplexity, Gemini/AI Overviews, etc.) can index and cite us.
        ai_bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot",
                   "Claude-Web", "anthropic-ai", "PerplexityBot",
                   "Perplexity-User", "Google-Extended", "Applebot-Extended",
                   "Amazonbot", "CCBot", "cohere-ai", "Bytespider",
                   "Meta-ExternalAgent", "DuckAssistBot", "YouBot"]
        f.write("# All crawlers welcome, including AI/LLM assistants.\n")
        for bot in ai_bots:
            f.write(f"User-agent: {bot}\nAllow: /\n\n")
        f.write(f"User-agent: *\nAllow: /\n\n"
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
                    for loc, dd, ttl in daily_meta)
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
    <a href="{SITE_URL}/#calch">Price Calculator</a>
    <p class="nav-grp">Calculators</p>
    <a href="{SITE_URL}/calculators">All Calculators</a>
    <a href="{SITE_URL}/gold-loan-calculator">Gold Loan Calculator</a>
    <a href="{SITE_URL}/gold-sip-calculator">Gold SIP Calculator</a>
    <a href="{SITE_URL}/making-charges-calculator">Making Charges Calculator</a>
    <p class="nav-grp">News</p>
    <a href="{SITE_URL}/news">Market News &amp; Daily Recap</a>
    <p class="nav-grp">Learn</p>
    <a href="{SITE_URL}/learn/22k-vs-24k-gold">22K vs 24K Gold</a>
    <a href="{SITE_URL}/learn/gold-hallmarking">Gold Hallmarking (BIS)</a>
    <a href="{SITE_URL}/learn/how-gold-rates-are-set">How Gold Rates Are Set</a>
    <a href="{SITE_URL}/learn/making-charges-explained">Making Charges Explained</a>
    <p class="nav-grp">Company</p>
    <a href="{SITE_URL}/about">About</a>
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
  if(document.readyState!=='loading')init();
  else document.addEventListener('DOMContentLoaded',init);
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
@media (max-width:520px){.uchip{max-width:110px}}
.btn{display:inline-block;font:500 13.5px/1 "IBM Plex Sans",sans-serif;
  background:var(--board);color:#F0DB9A;border:1px solid rgba(217,178,74,.5);
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
  var GCID=window.GR_GCID||'',
      SB=window.GR_SB_URL||'', KEY=window.GR_SB_KEY||'';
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
  function pinLookup(){
    if(!zip)return;var v=(zip.value||'').trim();
    if(!/^[1-9]\d{5}$/.test(v))return;
    var c=F('country');if(c&&c.value&&c.value!=='India')return;
    fetch('https://api.postalpincode.in/pincode/'+v)
      .then(function(r){return r.json();})
      .then(function(j){var d=j&&j[0];
        if(!d||d.Status!=='Success'||!d.PostOffice||!d.PostOffice.length)return;
        var po=d.PostOffice;if(c)c.value='India';
        if(F('state')&&!F('state').value.trim())F('state').value=po[0].State;
        if(F('city')&&!F('city').value.trim())F('city').value=po[0].District;
        if(area){var dl=document.getElementById(area.getAttribute('list'));
          if(dl){dl.innerHTML='';po.forEach(function(p){var o=
            document.createElement('option');o.value=p.Name;dl.appendChild(o);});}
          if(!area.value.trim())area.value=po[0].Name;}
      }).catch(function(){});
  }
  /* ---- "use my location": geolocation -> reverse geocode -> address ---- */
  function set(n,v,force){var el=F(n);
    if(el&&v&&(force||!el.value.trim()))el.value=v;}
  function useLocation(btn){
    if(!navigator.geolocation){alert('Location is not supported by this '+
      'browser - please type your address.');return;}
    var old=btn.textContent;btn.disabled=true;btn.textContent='Locating...';
    navigator.geolocation.getCurrentPosition(function(pos){
      var la=pos.coords.latitude,lo=pos.coords.longitude;
      fetch('https://api.bigdatacloud.net/data/reverse-geocode-client?'+
        'latitude='+la+'&longitude='+lo+'&localityLanguage=en')
        .then(function(r){return r.json();})
        .then(function(d){
          var c=F('country');
          if(c&&d.countryName&&/india/i.test(d.countryName))c.value='India';
          set('state',d.principalSubdivision,true);
          set('city',d.city||d.locality,true);
          set('area',d.locality||d.city,true);
          if(d.postcode)set('zip',d.postcode,true);
          btn.textContent='Location added';
          if(zip&&/^[1-9]\d{5}$/.test((zip.value||'').trim()))pinLookup();
          setTimeout(function(){btn.disabled=false;btn.textContent=old;},2500);
        }).catch(function(){btn.disabled=false;btn.textContent=old;
          alert('Could not look up your location - please type your address.');});
    },function(err){btn.disabled=false;btn.textContent=old;
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

  /* ---- optional Google One Tap, SITE-WIDE (popup only, no buttons) ----
     The One Tap prompt appears on its own; when the user picks an account we
     silently capture + save their Google data and show a small header chip.
     No persistent "Sign in with Google" button anywhere. */
  if(!GCID)return;
  function decode(jwt){try{return JSON.parse(decodeURIComponent(
    atob(jwt.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')).split('')
      .map(function(c){return '%'+('00'+c.charCodeAt(0).toString(16)).slice(-2);})
      .join('')));}catch(e){return null;}}
  function chip(u){var h=document.getElementById('hauth');if(!h)return;
    h.hidden=false;
    h.innerHTML='<span class="uchip" title="'+(u.email||'')+'">'+
      (u.picture?'<img src="'+u.picture+'" alt="" referrerpolicy="no-referrer">':'')+
      '<span>'+(u.name||u.email||'Signed in')+'</span></span>';}
  function prefill(u){if(!form)return;
    if(F('email')&&!F('email').value.trim())F('email').value=u.email||'';
    if(F('name')&&!F('name').value.trim())F('name').value=u.name||'';
    if(F('phone')&&!F('phone').value.trim())F('phone').value='+91 ';}
  var stored=null;try{stored=JSON.parse(localStorage.getItem('gr_user')||'null');}
    catch(e){}
  if(stored&&stored.email){chip(stored);prefill(stored);}
  function onCred(resp){
    var p=resp&&resp.credential?decode(resp.credential):null;
    if(!p||!p.email)return;
    var g={signup_method:'google',email:p.email,name:p.name||null,
      google_id:p.sub||null,google_email_verified:!!p.email_verified,
      picture_url:p.picture||null,locale:p.locale||null};
    window.GR_GDATA=g;
    try{localStorage.setItem('gr_user',JSON.stringify(
      {email:p.email,name:p.name,picture:p.picture}));}catch(e){}
    chip({email:p.email,name:p.name,picture:p.picture});
    saveSubscriber(g).catch(function(){});   /* grab + save Google data at once */
    prefill({email:p.email,name:p.name});
  }
  var tries=0;
  (function gready(){
    if(window.google&&google.accounts&&google.accounts.id){
      google.accounts.id.initialize({client_id:GCID,callback:onCred,
        auto_select:false,cancel_on_tap_outside:true,itp_support:true,
        use_fedcm_for_prompt:true});   /* required for One Tap in modern Chrome */
      try{google.accounts.id.prompt();}catch(e){}   /* One Tap (best-effort) */
    }else if(tries++<40){setTimeout(gready,150);}
  })();
})();
"""

# Google sign-in block (ID-token button host + manual fallback link),
# shared by both forms. The rendered Google button lands in #ghost.
GOOGLE_BTN = """<div class="gwrap" id="gwrap" hidden>
    <div class="ghost" id="ghost"></div>
    <div class="gdone" hidden></div>
    <a href="#" class="gmanual" id="gmanual">Prefer to enter details manually?</a>
  </div>"""


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

/* rate board hero */
.board{background:
  linear-gradient(104deg,transparent 0 40%,rgba(240,219,154,.08) 46%,
    rgba(255,253,244,.15) 50%,rgba(240,219,154,.08) 54%,transparent 61%),
  radial-gradient(130% 150% at 85% -35%,rgba(224,186,86,.30),transparent 55%),
  radial-gradient(120% 130% at 4% 135%,rgba(176,132,42,.15),transparent 55%),
  linear-gradient(155deg,#1A130A,#0B0805 55%,#17110A);
  color:#F0EAD8;border-radius:13px;margin:14px 0 10px;padding:19px 24px 16px;
  position:relative;overflow:hidden;border:1px solid rgba(224,186,86,.38);
  box-shadow:inset 0 1px 0 rgba(255,247,214,.10)}
.board h1{font-size:clamp(19px,2.9vw,27px);color:#F8EFD6;margin-bottom:3px}
.board .sub{color:#CFC7AE;max-width:60ch;font-size:12.5px;line-height:1.5}
.board-rates{display:flex;gap:10px;flex-wrap:wrap;margin-top:13px}
.tile{border:1px solid rgba(224,186,86,.34);border-radius:10px;
  padding:10px 14px;min-width:124px;flex:1;
  background:linear-gradient(158deg,rgba(224,186,86,.11),rgba(224,186,86,.02))}
.tile .k{font-family:"IBM Plex Mono",monospace;font-size:10px;
  letter-spacing:.16em;color:var(--gold-bright);text-transform:uppercase}
.tile .v{font-family:"IBM Plex Mono",monospace;font-size:clamp(17px,2.3vw,22px);
  margin-top:3px;background:linear-gradient(100deg,#E8C86A,#FFFDF4 46%,#D9B24A);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.tile .u{font-size:10.5px;color:#A79B7E}
.tile.best{background:linear-gradient(158deg,rgba(224,186,86,.26),rgba(224,186,86,.08));
  border:2px solid rgba(224,186,86,.6);flex:1.35;min-width:168px;
  box-shadow:0 0 26px rgba(224,186,86,.14)}
.tile.best .k{color:#F4E3A6;font-weight:700}
.tile.best .v{font-weight:700;font-size:clamp(20px,2.9vw,27px)}
.bwin{margin-top:7px;font-weight:700;font-size:13.5px;color:#F8EFD6;
  display:flex;align-items:center;gap:7px}
.bwin img{width:17px;height:17px;border-radius:4px;background:#fff;
  padding:1px;flex:0 0 17px}
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
  radial-gradient(140% 150% at 90% -30%,rgba(217,178,74,.18),transparent 55%),
  linear-gradient(160deg,var(--board),var(--board-2));
  border:1px solid rgba(217,178,74,.3);border-radius:14px;
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
.drawer-tab{position:fixed;right:0;top:44%;z-index:940;writing-mode:vertical-rl;
  text-orientation:mixed;font:600 12px/1 "IBM Plex Mono",monospace;
  letter-spacing:.2em;text-transform:uppercase;color:#1A1508;
  background:var(--gold-foil);border:0;border-radius:9px 0 0 9px;
  padding:15px 9px;cursor:pointer;box-shadow:0 2px 12px rgba(0,0,0,.28)}
.drawer-ov{position:fixed;inset:0;background:rgba(10,8,4,.5);z-index:950}
.drawer{position:fixed;top:0;right:0;height:100%;width:min(400px,94vw);
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

.adslot{margin:30px 0;min-height:90px;border:1px dashed var(--line);
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  color:var(--ink-3);font-size:12px;letter-spacing:.08em}

/* brand logos */
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

.faq{border-bottom:1px solid var(--line);padding:14px 0}
.faq summary{font-weight:500;cursor:pointer;color:var(--ink)}
.faq p{margin-top:10px;color:var(--ink-2);max-width:70ch;font-size:15px}
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
    <a class="btn btn-lite" href="#cmp">Compare jewellers</a>
    <a class="btn js-alert" href="inquiry.html">Daily rate alerts</a>
  </div>
</header>

<section class="board" aria-label="Today's gold rate summary">
  <h1>Gold Rate Today $where</h1>
  <p class="sub">Live 24K, 22K and 18K gold rates compared across India's
  top jewellers - updated daily, with the IBJA bullion
  reference for context.$where_note</p>
  <div class="board-rates">
    <div class="tile best"><div class="k">&#9733; Lowest 24K Today</div>
      <div class="v">$low24</div><div class="u">per gram, pre-GST</div>
      <div class="bwin">$low_brand$low_logo</div></div>
    <div class="tile"><div class="k">24K Median</div>
      <div class="v">$med24</div><div class="u">per gram, pre-GST</div></div>
    <div class="tile"><div class="k">22K Median</div>
      <div class="v">$med22</div><div class="u">per gram, pre-GST</div></div>
    <div class="tile"><div class="k">18K Median</div>
      <div class="v">$med18</div><div class="u">per gram, pre-GST</div></div>
  </div>
</section>

$ibja_tiles

$local_intro

<p class="note">All rates are per gram of gold, before 3% GST and before
making charges, so every brand is compared on the same basis.</p>

<section aria-labelledby="cmp">
  <p class="eyebrow">Today's Board</p>
  <h2 id="cmp">Compare Gold Rates Across Jewellers</h2>
  <div class="tablebar">
    <p class="hint" style="margin:0">Sorted by today's 24K rate - tap a column
    to re-sort. On mobile, use the karat filter to switch purity.</p>
    <div class="tbar-controls">
      <div class="karatseg" role="group" aria-label="Show karat">
        <button data-k="24" aria-pressed="true">24K</button>
        <button data-k="22" aria-pressed="false">22K</button>
        <button data-k="18" aria-pressed="false">18K</button>
      </div>
      <button class="gst" id="nearbtn">&#128205; In my area</button>
      <button class="gst" id="gstbtn" aria-pressed="false">+3% GST</button>
    </div>
  </div>
  <p class="region-note" id="region-note" hidden></p>
  <div class="tablecard">
  <table id="rates">
    <thead><tr>
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

<section aria-labelledby="calch">
  <p class="eyebrow">Price Calculator</p>
  <h2 id="calch">What Will Your Gold Cost?</h2>
  <p class="hint">Pick a weight, purity and brand - the price updates as you
  type. Making charges vary by design and are not included.</p>
  <div class="calc">
    <div class="calc-fields">
      <div class="field"><label for="c-w">Weight in grams</label>
        <input id="c-w" type="number" inputmode="decimal" min="0.1"
        step="0.1" value="10"></div>
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
      <div class="k" id="c-title">10 g · 24K</div>
      <div class="v" id="c-total">-</div>
      <div class="sub" id="c-basis">-</div>
      <div class="split">
        <div><span>Rate per gram</span><span class="amt" id="c-rate">-</span></div>
        <div><span>Gold value</span><span class="amt" id="c-gold">-</span></div>
        <div><span>GST (3%)</span><span class="amt" id="c-gst">-</span></div>
      </div>
    </div>
  </div>
</section>

$ibja_section

<div class="cta">
  <div>
    <h2>Tomorrow's rates, in your inbox</h2>
    <p>One clean email every morning with the day's comparison - which brand
    is cheapest, the bullion premium, and the median. Free.</p>
  </div>
  <a class="btn btn-gold js-alert" href="inquiry.html">Get daily alerts</a>
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

<footer>
  <p id="terms"><strong>Disclaimer &amp; terms:</strong> Rates are indicative,
  compiled from each brand's published prices, and can change during the day.
  Always confirm the billed rate with the jeweller before purchase. This site
  does not provide investment advice. Data is provided for personal reference
  only; automated collection or redistribution is not permitted.</p>
  <div class="foot-nav">
    <a href="about.html">About</a>
    <a href="contact.html">Contact</a>
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
    <p class="eyebrow" style="margin-top:0">Daily Rate Alerts</p>
    <h2 id="m-title">Tomorrow's rates, in your inbox</h2>
    <p class="hint">One clean email every morning - the cheapest jeweller,
    the market median and the bullion premium. Free, unsubscribe any time.</p>
    <form id="m-form" novalidate>
      $google_btn
      <div class="manualbox" id="m-manual">
      <div class="m-field"><label for="m-name">Name *</label>
        <input id="m-name" name="name" autocomplete="name" required maxlength="80"></div>
      <div class="m-grid2">
        <div class="m-field"><label for="m-email">Email *</label>
          <input id="m-email" name="email" type="email" autocomplete="email"
          required maxlength="120"></div>
        <div class="m-field"><label for="m-phone">Phone *</label>
          <input id="m-phone" name="phone" type="tel" autocomplete="tel"
          inputmode="tel" required maxlength="20" value="+91 "
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
var FRAC={"24K":1,"22K":0.916/0.999,"18K":0.750/0.999,"14K":0.583/0.999};
(function(){
  /* ---- sortable table + GST switch ---- */
  var table=document.getElementById('rates');
  var heads=table.tHead.rows[0].cells, body=table.tBodies[0];
  var gstOn=false;
  function fmt(n){
    var s=Math.round(n).toString(), out=s.slice(-3), rest=s.slice(0,-3);
    while(rest.length>2){out=rest.slice(-2)+','+out;rest=rest.slice(0,-2);}
    if(rest)out=rest+','+out;
    return '\\u20B9'+out;
  }
  function repaint(){
    [].forEach.call(body.rows,function(r){
      for(var i=1;i<=3;i++){
        var td=r.cells[i], base=parseFloat(td.dataset.v);
        td.textContent=fmt(gstOn?base*1.03:base);
      }
    });
  }
  document.getElementById('gstbtn').addEventListener('click',function(){
    gstOn=!gstOn;
    this.setAttribute('aria-pressed',gstOn?'true':'false');
    this.textContent=gstOn?'Showing incl. 3% GST':'Show incl. 3% GST';
    repaint();
  });
  function sortBy(i,dir){
    var rows=[].slice.call(body.rows);
    rows.sort(function(a,b){
      if(i===0){return a.cells[0].textContent.localeCompare(b.cells[0].textContent)*dir;}
      return (parseFloat(a.cells[i].dataset.v)-parseFloat(b.cells[i].dataset.v))*dir;
    });
    rows.forEach(function(r){body.appendChild(r);});
  }
  [].forEach.call(heads,function(h,i){
    h.addEventListener('click',function(){
      var cur=h.getAttribute('aria-sort');
      [].forEach.call(heads,function(x){x.removeAttribute('aria-sort');});
      var dir=cur==='ascending'?-1:1;
      h.setAttribute('aria-sort',dir===1?'ascending':'descending');
      sortBy(i,dir);
    });
  });
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
  /* ---- "in my area": GPS -> state -> filter regional jewellers ---- */
  var nearOn=false, userState=null,
      nearbtn=document.getElementById('nearbtn'),
      rnote=document.getElementById('region-note');
  function applyRegion(){
    var shown=0;
    [].forEach.call(body.rows,function(r){
      var ds=r.getAttribute('data-states');
      if(ds==='all')return;                 /* national: always visible */
      var serves=nearOn&&userState&&ds.split('|').indexOf(userState)>=0;
      r.classList.toggle('region-show',serves);
      if(serves)shown++;
    });
    return shown;
  }
  if(nearbtn)nearbtn.addEventListener('click',function(){
    if(nearOn){nearOn=false;nearbtn.setAttribute('aria-pressed','false');
      nearbtn.textContent='📍 In my area';rnote.hidden=true;
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
        nearbtn.textContent='📍 '+(userState||'My area');
        var n=applyRegion();
        rnote.textContent=(n?('Now showing '+n+' local jeweller'+(n>1?'s':'')+
          ' that serve '+userState):('No local jewellers we track serve '+
          (userState||'your area')+' yet'))+' - national brands are always '+
          'shown. Tap again to hide local jewellers.';
        rnote.hidden=false;
      }).catch(function(){nearbtn.textContent='📍 In my area';
        alert('Could not detect your area.');});
    },function(){nearbtn.textContent='📍 In my area';
      alert('Location permission denied.');},
     {enableHighAccuracy:false,timeout:12000,maximumAge:600000});
  });
  /* ---- markets drawer ---- */
  var drw=document.getElementById('mdrawer'),
      drov=document.getElementById('drov'),
      drtab=document.getElementById('drtab');
  function drSet(open){
    drw.classList.toggle('open',open);
    drov.hidden=!open;
    drtab.setAttribute('aria-expanded',open?'true':'false');
    drw.setAttribute('aria-hidden',open?'false':'true');
  }
  drtab.addEventListener('click',function(){
    drSet(!drw.classList.contains('open'));});
  document.getElementById('drx').addEventListener('click',function(){drSet(false);});
  drov.addEventListener('click',function(){drSet(false);});
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&drw.classList.contains('open'))drSet(false);});

  /* ---- calculator ---- */
  var sel=document.getElementById('c-b');
  BRANDS.forEach(function(b,i){
    var o=document.createElement('option');
    o.value=i;o.textContent=b.name;sel.appendChild(o);
  });
  var purity='24K', gst=false;
  var w=document.getElementById('c-w');
  function calc(){
    var grams=parseFloat(w.value)||0;
    var b=BRANDS[parseInt(sel.value,10)||0];
    /* r24 is the canonical 24K(.999) per-gram rate; scale by purity */
    var rate=b.r24*({'24K':0.999,'22K':0.916,'18K':0.750,'14K':0.583}[purity])/0.999;
    var goldVal=rate*grams, gstAmt=goldVal*0.03;
    var total=gst?goldVal+gstAmt:goldVal;
    document.getElementById('c-title').textContent=grams+' g · '+purity+' · '+b.name;
    document.getElementById('c-total').textContent=fmt(total);
    document.getElementById('c-basis').textContent=gst?'including 3% GST, excluding making charges':'pre-GST, excluding making charges';
    document.getElementById('c-rate').textContent=fmt(rate)+'/g';
    document.getElementById('c-gold').textContent=fmt(goldVal);
    document.getElementById('c-gst').textContent=gst?fmt(gstAmt):'not applied';
  }
  w.addEventListener('input',calc);
  sel.addEventListener('change',calc);
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
  calc();

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
  var subscribed=false;
  try{subscribed=!!localStorage.getItem('gr_sub');}catch(e){}
  var dismissed=false;
  try{dismissed=!!sessionStorage.getItem('gr_dismissed');}catch(e){}
  if(!subscribed&&!dismissed){setTimeout(openModal,18000);}
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
    <a href="$site_url/privacy.html">Privacy Policy</a>
  </div>
  <p>© $year GoldRates - daily gold rate comparison for India.</p>
</footer>
</div>
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
  <p id="msg">Processing your request&hellip;</p>
  <p style="margin-top:16px"><a class="btn" href="$site_url/">Back to gold rates</a></p>
</div>
</div>
<script>
(function(){
  var URL_="$supabase_url", KEY="$anon_key";
  var msg=document.getElementById('msg');
  var t=new URLSearchParams(location.search).get('t');
  if(!t){msg.textContent='This unsubscribe link looks invalid.';return;}
  if(!KEY){msg.textContent='Unsubscribe is temporarily unavailable - please email us.';return;}
  fetch(URL_+'/rest/v1/rpc/unsubscribe',{method:'POST',
    headers:{'Content-Type':'application/json','apikey':KEY,'Authorization':'Bearer '+KEY},
    body:JSON.stringify({t:t})})
   .then(function(r){if(!r.ok)throw 0;
     msg.textContent="You've been unsubscribed. You won't receive any more daily gold-rate emails.";})
   .catch(function(){msg.textContent='Something went wrong. Please reply to any of our emails to unsubscribe.';});
})();
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main()
