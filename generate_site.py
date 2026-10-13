#!/usr/bin/env python3
"""Render the public gold-rate comparison site from today's collected rates.

Runs in CI right after collect.py. Reads today's rates from Supabase, fetches
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
from email.utils import formatdate
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
# used when a brand only publishes one purity. Kept in sync with collect.py.
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
    # favicon-32.png is referenced by the homepage head and by the Jewellers
    # Digest page and was never written, so the request fell through to the
    # index.html fallback and the browser was handed HTML labelled as a PNG.
    # It failed silently, the way a broken favicon always does.
    for size, name in ((32, "favicon-32.png"), (48, "icon-48.png"),
                       (96, "icon-96.png"),
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


# Which state (or union territory) each place on LOCATIONS is in. Plain
# geography, used to show the jewellers that actually serve a place - see
# local_board() in main(). States map to themselves; "India" to None.
PLACE_STATE = {
    "India": None,
    "Delhi": "Delhi", "Chandigarh": "Chandigarh",
    # states listed on LOCATIONS map to themselves (filled in below)
    "Mumbai": "Maharashtra", "Pune": "Maharashtra", "Nagpur": "Maharashtra",
    "Nashik": "Maharashtra", "Aurangabad": "Maharashtra",
    "Solapur": "Maharashtra", "Kolhapur": "Maharashtra",
    "Bengaluru": "Karnataka", "Mysuru": "Karnataka", "Mangaluru": "Karnataka",
    "Hubli": "Karnataka", "Belagavi": "Karnataka", "Vijayapura": "Karnataka",
    "Davanagere": "Karnataka",
    "Chennai": "Tamil Nadu", "Coimbatore": "Tamil Nadu", "Madurai": "Tamil Nadu",
    "Tiruchirappalli": "Tamil Nadu", "Salem": "Tamil Nadu",
    "Erode": "Tamil Nadu", "Tirunelveli": "Tamil Nadu",
    "Hyderabad": "Telangana", "Warangal": "Telangana",
    "Kolkata": "West Bengal", "Siliguri": "West Bengal",
    "Ahmedabad": "Gujarat", "Surat": "Gujarat", "Vadodara": "Gujarat",
    "Rajkot": "Gujarat",
    "Jaipur": "Rajasthan", "Jodhpur": "Rajasthan", "Udaipur": "Rajasthan",
    "Kota": "Rajasthan", "Ajmer": "Rajasthan",
    "Kochi": "Kerala", "Thrissur": "Kerala", "Kozhikode": "Kerala",
    "Thiruvananthapuram": "Kerala", "Kollam": "Kerala", "Kannur": "Kerala",
    "Lucknow": "Uttar Pradesh", "Kanpur": "Uttar Pradesh",
    "Varanasi": "Uttar Pradesh", "Agra": "Uttar Pradesh",
    "Meerut": "Uttar Pradesh", "Ghaziabad": "Uttar Pradesh",
    "Noida": "Uttar Pradesh", "Allahabad": "Uttar Pradesh",
    "Bareilly": "Uttar Pradesh", "Moradabad": "Uttar Pradesh",
    "Aligarh": "Uttar Pradesh",
    "Patna": "Bihar",
    "Indore": "Madhya Pradesh", "Bhopal": "Madhya Pradesh",
    "Gwalior": "Madhya Pradesh", "Jabalpur": "Madhya Pradesh",
    "Visakhapatnam": "Andhra Pradesh", "Vijayawada": "Andhra Pradesh",
    "Tirupati": "Andhra Pradesh", "Guntur": "Andhra Pradesh",
    "Ranchi": "Jharkhand", "Jamshedpur": "Jharkhand", "Dhanbad": "Jharkhand",
    "Guwahati": "Assam",
    "Bhubaneswar": "Odisha", "Cuttack": "Odisha",
    "Ludhiana": "Punjab", "Amritsar": "Punjab", "Jalandhar": "Punjab",
    "Faridabad": "Haryana", "Gurugram": "Haryana",
    "Raipur": "Chhattisgarh",
    "Dehradun": "Uttarakhand",
}
for _p in ("Maharashtra", "Tamil Nadu", "Karnataka", "Kerala", "Telangana",
           "Andhra Pradesh", "Gujarat", "Rajasthan", "West Bengal",
           "Uttar Pradesh", "Madhya Pradesh", "Punjab", "Haryana", "Bihar",
           "Odisha", "Assam", "Jharkhand", "Uttarakhand", "Himachal Pradesh",
           "Goa"):
    PLACE_STATE.setdefault(_p, _p)


# ---------------------------------------------------------------------------
# The new design, for every page that is not the app itself.
#
# The homepage and the 95 city pages are the Market Pulse app (pulse_app.html).
# Everything else - calculators, articles, news, daily reports, recaps, the
# policy pages, the alerts form, unsubscribe, 404 - used to be rendered in the
# old light comparison-site design, so a visitor moving from the homepage to
# any of them walked into a different website. These three pieces put them in
# the new one: its palette, fonts, header and footer links. The old
# templates' own stylesheet is driven by CSS variables (--paper, --ink, ...),
# so restyling it is mostly a matter of redefining those, below.
ND_CSS = """
:root{
  --paper:#0A0804; --ink:#F4EDE0; --ink-2:#C8BDA8; --ink-3:#9B907B;
  --board:#15100A; --board-2:#1E160C; --gold:#D4A63C; --gold-bright:#E8C766;
  --gold-foil:linear-gradient(100deg,#B07E12,#E3BF63 45%,#F4E3A6 55%,#D4A63C);
  --emerald:#5CC4A0; --line:rgba(200,160,60,.16); --card:rgba(255,255,255,.035);
  --warm:#E88AAE; --bar:#D4A63C;
}
html,body{background:#0A0804;color:var(--ink)}
body{font-family:'DM Sans',system-ui,-apple-system,sans-serif;
  background:radial-gradient(1200px 600px at 50% -10%,rgba(212,166,60,.10),transparent 60%),#0A0804}
h1,h2,h3,.page h1,.page h2{font-family:'Playfair Display',Georgia,serif;color:var(--ink)}
.page a,.wrap a:not(.btn):not(.toolcard):not(.newscard){color:var(--gold-bright)}
input,select,textarea{color-scheme:dark}
.calcbox input,.calcbox select,input[type=text],input[type=email],input[type=tel],
input[type=number],select,textarea{background:rgba(255,255,255,.04)!important;
  color:var(--ink)!important;border-color:var(--line)!important}
table{color:var(--ink)}
th,td{border-color:var(--line)!important}
"""

ND_CHROME_CSS = """
.nd-nav{position:sticky;top:0;z-index:50;background:rgba(10,8,4,.82);
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border-bottom:1px solid rgba(200,160,60,.12)}
.nd-nav-in{max-width:1180px;margin:0 auto;padding:14px 20px;display:flex;
  align-items:center;gap:22px}
.nd-logo{font-family:'Playfair Display',Georgia,serif;font-size:20px;font-weight:700;
  color:#F4EDE0;text-decoration:none;white-space:nowrap;display:inline-flex;
  align-items:center;gap:9px}
.nd-logo .nd-word span{background:linear-gradient(135deg,#F4E3A6,#D4A63C);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.nd-links{display:flex;gap:20px;overflow-x:auto;scrollbar-width:none;flex:1}
.nd-links::-webkit-scrollbar{display:none}
.nd-links a{color:#C8BDA8;text-decoration:none;font-size:14px;font-weight:500;
  white-space:nowrap}
.nd-links a:hover,.nd-links a[aria-current]{color:#E8C766}
.nd-cta{margin-left:auto;white-space:nowrap;padding:8px 14px;border-radius:999px;
  background:linear-gradient(135deg,#E8C766,#D4A63C);color:#1A1205!important;
  font-weight:600;font-size:13px;text-decoration:none}
@media(max-width:720px){
  .nd-nav-in{flex-wrap:wrap;gap:10px 16px;padding:12px 16px}
  .nd-links{order:3;flex-basis:100%}
}
.nd-foot{border-top:1px solid rgba(200,160,60,.12);margin-top:36px;padding:26px 16px 34px;
  text-align:center;font-size:12px;color:#9B907B}
.sl{margin:0 auto 10px;max-width:980px;font-size:12.5px;line-height:1.95;color:#9B907B;
  display:flex;flex-wrap:wrap;justify-content:center;row-gap:2px}
.sl h3{flex-basis:100%}
.city-links,.citycloud{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.city-links a,.citycloud a{padding:6px 12px;border-radius:999px;border:1px solid rgba(212,175,55,.25);
  color:#E8C766!important;text-decoration:none;font-size:13px}
.sl h3{font-family:'DM Sans',system-ui,sans-serif;font-size:11px;letter-spacing:.08em;
  text-transform:uppercase;margin:14px 0 4px;color:#9B907B;font-weight:600}
.sl a{color:#C8BDA8;text-decoration:none;margin:0 7px;white-space:nowrap}
.sl a:hover{text-decoration:underline;color:#E8C766}
"""
ND_CSS = ND_CSS + ND_CHROME_CSS

ND_FONTS = ('<link href="https://fonts.googleapis.com/css2?family=DM+Sans:'
            'opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family='
            'Playfair+Display:wght@600;700&family=IBM+Plex+Mono:wght@500;700'
            '&display=swap" rel="stylesheet">')


def site_links_html():
    """Footer links shared by the app pages and every other page. One list,
    so a page added here appears everywhere."""
    states = [p for p in LOCATIONS if PLACE_STATE.get(p) == p]
    return (
        '<nav class="sl" aria-label="Site">'
        f'<a href="{SITE_URL}/">Today&rsquo;s gold rates</a>'
        f'<a href="{SITE_URL}/calculators">Gold calculators</a>'
        f'<a href="{SITE_URL}/making-charges-comparison">Making charges</a>'
        f'<a href="{SITE_URL}/news">Gold news</a>'
        f'<a href="{SITE_URL}/jewellers-digest">Jewellers Digest</a>'
        f'<a href="{SITE_URL}/inquiry">Daily rate alerts</a>'
        '<h3>Gold rate by state</h3>'
        + "".join(f'<a href="{SITE_URL}/gold-rate-today-in-{loc_slug(p)}">{p}</a>'
                  for p in states)
        + '<h3>About</h3>'
        f'<a href="{SITE_URL}/about">About us</a>'
        f'<a href="{SITE_URL}/methodology">How we collect rates</a>'
        f'<a href="{SITE_URL}/contact">Contact</a>'
        f'<a href="{SITE_URL}/privacy">Privacy Policy</a>'
        f'<a href="{SITE_URL}/terms">Terms</a>'
        '</nav>')


def nd_header_html():
    return (
        '<header class="nd-nav"><div class="nd-nav-in">'
        # The gold bars-and-arrow mark, the same drawing the favicon is made
        # from. The old header carried it; the new design's wordmark-only
        # header dropped it when pages moved over.
        f'<a class="nd-logo" href="{SITE_URL}/"><svg class="brand-mark" width="30" height="30" style="flex:none" viewBox="0 0 40 40" fill="none" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="grx-nd" x1="4" y1="38" x2="36" y2="4" gradientUnits="userSpaceOnUse"><stop stop-color="#B07E12"/><stop offset=".55" stop-color="#E3BF63"/><stop offset="1" stop-color="#F4E3A6"/></linearGradient></defs><rect x="4.5" y="21" width="9" height="15" rx="1.6" fill="url(#grx-nd)"/><rect x="16.5" y="12" width="9" height="24" rx="1.6" fill="url(#grx-nd)"/><path d="M5 25.5 17 17 25 21 34 8.5" stroke="url(#grx-nd)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M27.5 7.5 35 6.5 34.5 14" stroke="url(#grx-nd)" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        '<span class="nd-word">My<span>Gold</span>Rates</span></a>'
        '<nav class="nd-links" aria-label="Main">'
        f'<a href="{SITE_URL}/">Today&rsquo;s rates</a>'
        f'<a href="{SITE_URL}/calculators">Calculators</a>'
        f'<a href="{SITE_URL}/making-charges-comparison">Making charges</a>'
        f'<a href="{SITE_URL}/news">News</a>'
        f'<a href="{SITE_URL}/jewellers-digest">For jewellers</a>'
        '</nav>'
        f'<a class="nd-cta" href="{SITE_URL}/inquiry">Get daily alerts</a>'
        '</div></header>')


def nd_footer_html(year):
    return ('<footer class="nd-foot">' + site_links_html()
            + f'<p>&copy; {year} MyGoldRates &middot; Rates are indicative, '
            'updated daily &middot; Not investment advice</p></footer>')


def analytics_snippet(supabase_url, anon_key):
    """The pageview beacon, as an inline <script> for the document head.

    Two things here are deliberate, and both were measured rather than
    assumed (tests/test_analytics_beacon.py records the numbers):

    1. keepalive. The old tracker used a plain fetch(), which the browser
       CANCELS when the document unloads. On a rate-checking site the
       commonest visit is: land, read the number, leave - so the request was
       being killed before it left. Measured on a fast datacentre link, six
       identical fast-bounce loads landed 3 of 6 with a plain fetch and 6 of
       6 with keepalive. On the live site, every visitor who left inside
       about 1.6 seconds was invisible.

    2. Inline, in the head, not in deferred signup.js. The beacon used to
       ride along in an 11.6KB deferred bundle, so it could not fire until
       that file had been fetched and parsed - a whole extra round trip.
       Measured on a live city page, nothing at all was sent if the visitor
       left within 800ms; the homepage, whose copy was already inline,
       managed 200ms. Inline costs no round trip and fires during parse.

    It also exposes window.GR_SID and window.GR_TRACK so the click tracking
    in signup.js reuses this session id and this sender instead of carrying
    a second copy that could drift.
    """
    return (
        '<script>(function(){'
        'var SB=' + json.dumps(supabase_url) + ',KEY=' + json.dumps(anon_key) + ';'
        'if(!SB||!KEY)return;'
        'var SID="";'
        'try{SID=localStorage.getItem("gr_sid")||"";'
        'if(!SID){SID=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():'
        '(Date.now().toString(36)+Math.random().toString(36).slice(2));'
        'localStorage.setItem("gr_sid",SID);}}catch(e){SID="";}'
        'window.GR_SID=SID;'
        'function send(table,row,retried){try{'
        'fetch(SB+"/rest/v1/"+table,{method:"POST",keepalive:true,'
        'headers:{"Content-Type":"application/json","apikey":KEY,'
        '"Authorization":"Bearer "+KEY,"Prefer":"return=minimal"},'
        'body:JSON.stringify(row)}).then(function(r){'
        # A column the live DB does not have yet comes back as a normal
        # HTTP error, not a throw, so without this the whole row is lost.
        'if(!r.ok&&!retried&&row.host!==undefined){'
        'var r2={};for(var k in row){if(k!=="host")r2[k]=row[k];}'
        'send(table,r2,true);}}).catch(function(){});}catch(e){}}'
        'window.GR_TRACK=send;'
        'send("page_views",{page:location.pathname,'
        'referrer:document.referrer||null,session_id:SID,'
        'host:location.hostname});'
        '})();</script>\n')


# City/state landing pages: enriched with local market hubs, regional jeweller tags & unique intro content.
LOCATIONS = [
    # Top major gold trading & retail hubs in India
    "Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Kochi", "Coimbatore", "Lucknow",
    "Surat", "Chandigarh", "Patna", "Indore", "Visakhapatnam", "Vadodara",
    "Nagpur", "Bhopal",
    # Kanpur, Nashik and Ranchi dropped off this list on 31 Jul 2026 but
    # stayed in
    # the homepage's city links, and docs/ is deployed wholesale, so their
    # pages kept being served frozen at that date - a gold rate site quoting
    # a July price in October. Back on the list so the build refreshes them.
    # They have no CITY_ENRICHMENT_DATA entry and fall back to the generic
    # intro, which is the right trade: a plain page with today's rate beats
    # an enriched one with July's.
    "Kanpur", "Nashik", "Ranchi",
    # The 56 places removed on 31 Jul 2026 ("enrich city pages for AdSense
    # compliance"), restored at the owner's request on 13 Oct 2026. The
    # reasons: each place should keep its own URL and heading, so a visitor
    # searching for one sees that place's name, and so analytics shows which
    # locations people come for. Their files had stayed in docs/ unmaintained
    # since July, showing the 31 July rate; on this list they are rebuilt
    # daily with today's. None has a CITY_ENRICHMENT_DATA entry, so each uses
    # the generic intro - local details were not invented for them.
    "Madurai", "Vijayawada", "Mysuru", "Thrissur", "Kozhikode",
    "Thiruvananthapuram", "Guwahati", "Bhubaneswar", "Ludhiana", "Amritsar",
    "Rajkot", "Varanasi", "Agra", "Meerut", "Faridabad", "Ghaziabad",
    "Gurugram", "Noida", "Raipur", "Jodhpur", "Udaipur", "Kota", "Dehradun",
    "Jamshedpur", "Dhanbad", "Aurangabad", "Solapur", "Tiruchirappalli",
    "Salem", "Tirupati", "Guntur", "Warangal", "Mangaluru", "Hubli",
    "Belagavi", "Kolhapur", "Jalandhar", "Siliguri", "Cuttack", "Ajmer",
    "Gwalior", "Jabalpur", "Allahabad", "Bareilly", "Moradabad", "Aligarh",
    "Vijayapura", "Davanagere", "Erode", "Tirunelveli", "Kollam", "Kannur",
    "Jharkhand", "Uttarakhand", "Himachal Pradesh", "Goa",
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
    """IBJA daily reference rates, pre-GST, returned per GRAM.

    Returns (r999, r916) or None.

    Unit-agnostic by design. IBJA used to publish per 10 grams (six or
    seven digits, e.g. 150900) and this parser hard-coded that: it matched
    `[\d,]{6,7}` and divided by 10. By Sep 2026 the site publishes per
    gram instead, labelled "(1 Gram)":

        999 Purity   15090   (1 Gram)
        916 Purity   13823   (1 Gram)

    Five digits no longer matched, so this returned None - and because
    every caller treats None as "IBJA unavailable" and falls back silently,
    the failure was invisible: the homepage's IBJA anchor went to 0, the
    IBJA 24K tile quietly reverted to a spot x (1 + INDIA_PREMIUM)
    ESTIMATE (~15,220 against IBJA's real 15,090), and the "Jeweller
    Premium Over the IBJA Rate" section plus the IBJA FAQ dropped off
    /compare entirely.

    So do not encode the unit at all. Accept 4-7 digits and let the
    magnitude decide: a per-gram gold rate lands in 8k-22k, the same
    figure per 10g lands in 80k-220k. Either publishing convention parses
    correctly, including a revert, and anything outside both bands is
    rejected rather than silently scaled into range.

    The purity label is required in the pattern ("999 Purity", not bare
    "999") so the Chart.js block further up the page - which contains the
    literal strings "999 Purity Gold Rates (PM)" and `chartData.purity999`
    - cannot be mistaken for the rate table.
    """
    try:
        r = requests.get("https://ibjarates.com", headers={"User-Agent": UA},
                         timeout=20)
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text)

        def grab(purity):
            for m in re.finditer(
                    purity + r"\s*Purity\D{0,40}?([\d,]{4,7})", text):
                raw = m.group(1).replace(",", "")
                if not raw.isdigit():
                    continue
                v = float(raw)
                if 80_000 <= v <= 220_000:   # published per 10 grams
                    v /= 10.0
                if 8_000 <= v <= 22_000:     # per gram, as published or scaled
                    return v
            return None

        r999, r916 = grab("999"), grab("916")
        if r999 and r916:
            return r999, r916
    except Exception:
        pass
    return None


def fetch_calendar():
    """This week's US economic events, from FairEconomy's ForexFactory feed.

    Baked into the page at build time rather than fetched by the browser
    from our Cloudflare worker, because the worker CANNOT reach this feed:
    nfs.faireconomy.media is itself behind Cloudflare, and Cloudflare
    rejects worker-to-worker-zone subrequests, so /calendar returned 502 on
    every single call while the identical request with identical headers
    succeeded from anywhere else. The calendar strip was therefore always
    empty. A build runs every 30 minutes and this is a WEEKLY schedule, so
    build-time is ample freshness and removes the failing hop entirely.

    Returns a list of dicts matching the shape the page already renders,
    or [] if the feed is unavailable (the strip then just stays hidden).
    """
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
                         headers={"User-Agent": UA}, timeout=20)
        if r.status_code != 200:
            return []

        def field(block, tag):
            m = re.search(r"<" + tag + r">(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</"
                          + tag + r">", block, re.S)
            return m.group(1).strip() if m else ""

        out = []
        for block in re.findall(r"<event>(.*?)</event>", r.text, re.S):
            country = field(block, "country")
            # US events only - they are what actually moves the gold price.
            if country and country.upper() not in ("USD", "US"):
                continue
            title = field(block, "title")
            if not title:
                continue
            out.append({
                "title": title,
                "country": country or "USD",
                "date": field(block, "date"),
                "time": field(block, "time"),
                "impact": field(block, "impact"),
                "forecast": field(block, "forecast"),
                "previous": field(block, "previous"),
                "actual": field(block, "actual"),
                "url": field(block, "url"),
            })
        return out
    except Exception:
        return []


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


# International spot references + FX rate. These are the same open,
# CORS-friendly APIs the site's client-side rates fetch already uses; here
# we ALSO pull them server-side so the Markets drawer paints correct global
# numbers on first byte (SEO + first-paint), matching how IBJA/MCX tiles
# render today. Powers the Market Pulse tiles: gold spot USD/oz, silver
# spot USD/oz, USD/INR, and a derived silver INR/kg.
OZ_TO_G = 31.1034768
OZ_PER_KG = 32.1507466  # troy oz per kg (silver is quoted per kg in India)
SILVER_INDIA_PREMIUM = 0.12  # duty + local markup vs XAG spot, under gold


def fetch_gold_spot_usd():
    """International spot gold, USD per troy oz. Returns float or None."""
    try:
        r = requests.get("https://api.gold-api.com/price/XAU",
                         headers={"User-Agent": UA}, timeout=15)
        v = float(r.json().get("price") or 0)
        if 500 <= v <= 20000:
            print(f"gold-spot: XAU=${v:.2f}/oz")
            return v
    except Exception as e:
        print("gold-spot: fetch failed:", type(e).__name__, str(e)[:80])
    return None


def fetch_silver_spot_usd():
    """International spot silver, USD per troy oz. Returns float or None."""
    try:
        r = requests.get("https://api.gold-api.com/price/XAG",
                         headers={"User-Agent": UA}, timeout=15)
        v = float(r.json().get("price") or 0)
        if 5 <= v <= 500:
            print(f"silver-spot: XAG=${v:.2f}/oz")
            return v
    except Exception as e:
        print("silver-spot: fetch failed:", type(e).__name__, str(e)[:80])
    return None


def fetch_usdinr():
    """USD/INR reference from open.er-api.com. Returns float or None."""
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD",
                         headers={"User-Agent": UA}, timeout=15)
        v = float(((r.json() or {}).get("rates") or {}).get("INR") or 0)
        if 40 <= v <= 200:
            print(f"usdinr: 1 USD = ₹{v:.2f}")
            return v
    except Exception as e:
        print("usdinr: fetch failed:", type(e).__name__, str(e)[:80])
    return None


def fetch_bullion_news(limit=8):
    """Gold + silver + bullion PRICE headlines via Google News RSS.

    The query asks for the metals in a price/rate context rather than the
    bare words. A plain "gold OR silver India" search returns medals: the
    rail was shipping "Women's cricket at the Asian Games" and "India
    women's kabaddi team targets Asian Games gold" alongside the rate
    stories, because in Indian news those words are far more often about
    sport than about bullion.

    Two defences, because neither is sufficient alone. The query pins the
    metals to price/rate wording, and DROP below removes anything that
    still arrives wearing a medal - a headline can match "gold price" in a
    sports-sponsorship story, and Google's matching is fuzzy enough that
    the query alone does not hold.
    """
    url = ("https://news.google.com/rss/search?q="
           + requests.utils.quote(
               '"gold price" OR "gold rate" OR "silver price" OR '
               '"silver rate" OR "bullion market" India when:3d')
           + "&hl=en-IN&gl=IN&ceid=IN:en")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        items = re.findall(r"<item>(.*?)</item>", r.text, re.S)

        def field(block, tag):
            m = re.search(r"<" + tag + r"[^>]*>(.*?)</" + tag + ">",
                          block, re.S)
            return m.group(1).strip() if m else ""

        keep = re.compile(r"(gold|silver|bullion|xau|xag|mcx|ibja)", re.I)
        # Medals, not metals.
        DROP = re.compile(
            r"(asian games|olympic|commonwealth games|world cup|medal|"
            r"kabaddi|cricket|hockey|badminton|wrestl|athletic|"
            r"championship|tournament|sprint|relay|podium)", re.I)
        out, seen = [], set()
        for it in items:
            title = _html.unescape(re.sub(r"<[^>]+>", "", field(it, "title")))
            link = _html.unescape(field(it, "link"))
            src = _html.unescape(re.sub(r"<[^>]+>", "", field(it, "source")))
            if src and title.endswith(" - " + src):
                title = title[:-(len(src) + 3)].strip()
            if not (title and link) or len(title) < 15:
                continue
            if DROP.search(title):
                continue
            if not keep.search(title):
                continue
            key = title.lower()
            if key in seen:
                continue
            try:
                dt = datetime.strptime(field(it, "pubDate")[:25].strip(),
                                       "%a, %d %b %Y %H:%M:%S")
            except Exception:
                dt = None
            out.append({"title": title, "link": link, "source": src, "dt": dt})
            seen.add(key)
            if len(out) >= limit:
                break
        print(f"bullion-news: {len(out)} gold+silver headlines fetched")
        return out
    except Exception as e:
        print("bullion-news: fetch failed:",
              type(e).__name__, str(e)[:100])
        return []


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
    if ads_client:
        ads_head = (
            '<script async src="https://pagead2.googlesyndication.com/pagead/'
            f'js/adsbygoogle.js?client={ads_client}" crossorigin="anonymous">'
            f'</script>\n<meta name="google-adsense-account" content="{ads_client}">')
    else:
        ads_head = ""
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


    # --------------------------------------------------- MCX gold futures
    mcx = fetch_mcx()
    mcx_expiry_for_js = ""
    if mcx:
        g = next((c for c in mcx if c["symbol"] == "GOLD"), mcx[0])
        mcx_expiry_for_js = g["expiry"]

    # ----------------------------------------- AKGSMA (South India benchmark)
    akgsma = fetch_akgsma()
    if akgsma:
        ak24, ak22, ak18 = akgsma

    # --------------------------------------------------------------- IBJA
    ibja = fetch_ibja()
    if ibja:
        r999, r916 = ibja
        premium_med = (median24 / r999 - 1) * 100
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
        ibja_faq = (
            f"The IBJA (India Bullion and Jewellers Association) 24K reference "
            f"rate today is {inr(r999)} per gram for 999 gold, before GST. "
            f"Jewellery brands price on average {premium_med:+.1f}% above the "
            "bullion reference today; the gap reflects each brand's sourcing "
            "and hallmarking premium.")
    else:
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
         "license": f"{SITE_URL}/terms",
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
    else:
        pass


    # ---------------------------------------- Global Market (spot + FX)
    # Emits four tiles for the Market Pulse strip in the drawer: gold spot
    # USD/oz, silver spot USD/oz, USD/INR, and a derived Silver 999 INR/kg
    # for the Indian buyer. All values come from open, CORS-friendly APIs
    # at build time; the drawer renders whichever tiles came back and
    # silently drops the rest, so a single upstream miss never breaks the
    # layout.
    gold_usd = fetch_gold_spot_usd()
    silver_usd = fetch_silver_spot_usd()
    usdinr = fetch_usdinr()
    global_tiles = []
    if gold_usd:
        global_tiles.append(
            f'<div class="rtile" data-mk="gold-usd">'
            f'<div class="k">Gold Spot &middot; XAU/USD</div>'
            f'<div class="v" data-mk-v>${gold_usd:,.2f}</div>'
            f'<div class="u">per troy oz &middot; international spot</div>'
            f'<div class="rtile-d flat" data-mk-d>± $0.00</div></div>')
    if silver_usd:
        global_tiles.append(
            f'<div class="rtile" data-mk="silver-usd">'
            f'<div class="k">Silver Spot &middot; XAG/USD</div>'
            f'<div class="v" data-mk-v>${silver_usd:,.2f}</div>'
            f'<div class="u">per troy oz &middot; international spot</div>'
            f'<div class="rtile-d flat" data-mk-d>± $0.00</div></div>')
    if usdinr:
        global_tiles.append(
            f'<div class="rtile" data-mk="usdinr">'
            f'<div class="k">USD / INR</div>'
            f'<div class="v" data-mk-v>&#8377;{usdinr:.2f}</div>'
            f'<div class="u">reference FX &middot; live</div>'
            f'<div class="rtile-d flat" data-mk-d>± &#8377;0.00</div></div>')
    if silver_usd and usdinr:
        silver_inr_kg = silver_usd * OZ_PER_KG * usdinr * (1 + SILVER_INDIA_PREMIUM)
        global_tiles.append(
            f'<div class="rtile" data-mk="silver-inr">'
            f'<div class="k">Silver 999 &middot; INR/kg</div>'
            f'<div class="v" data-mk-v>{inr(silver_inr_kg)}</div>'
            f'<div class="u">per kg &middot; spot + India premium</div>'
            f'<div class="rtile-d flat" data-mk-d>± &#8377;0</div></div>')
    if global_tiles:
        pass
    else:
        pass

    # ---------------------------------------- Bullion News (gold + silver)
    bullion_items = fetch_bullion_news()
    if bullion_items:
        pass
    else:
        pass

    # ---- Live-refresh anchors ---------------------------------------------
    # Every 60s the browser re-fetches XAU + XAG + USD/INR + MCX Gold Futures
    # from CORS-open upstreams (gold-api.com, open.er-api.com,
    # priceapi.moneycontrol.com — all confirmed *) and recomputes the
    # derived Indian-rupee tiles. We anchor the derived tiles (IBJA 999,
    # AKGSMA 24K) to today's server-side snapshot via a scale factor
    # instead of a fixed percentage — that way IBJA/AKGSMA move in lock-
    # step with spot without needing us to know today's exact premium.
    # If a required anchor input is missing we simply omit that tile
    # from the live-update set; nothing else breaks.
    mk_anchors = {
        "silverPremiumPct": SILVER_INDIA_PREMIUM,
        "ozToG": OZ_TO_G,
        "ozPerKg": OZ_PER_KG,
        "mcxSymbol": "GOLD",
        "mcxExpiry": mcx_expiry_for_js,  # "" if MCX fetch failed
        "buildTs": datetime.now(IST).isoformat(timespec="seconds"),
    }
    spot_inr_build = None
    if gold_usd and usdinr:
        spot_inr_build = (gold_usd / OZ_TO_G) * usdinr
        mk_anchors["goldUsdBuild"] = gold_usd
        mk_anchors["usdinrBuild"] = usdinr
        mk_anchors["spotInrBuild"] = spot_inr_build
    if silver_usd:
        mk_anchors["silverUsdBuild"] = silver_usd
    if ibja and spot_inr_build:
        r999_b, _ = ibja
        mk_anchors["ibjaFactor"] = r999_b / spot_inr_build
        mk_anchors["ibja999Build"] = r999_b
    if akgsma and spot_inr_build:
        ak24_b = akgsma[0]
        mk_anchors["akgsmaFactor"] = ak24_b / spot_inr_build
        mk_anchors["akgsma24Build"] = ak24_b
    # Median 24K jeweller board rate today — the "Jeweller premium" tile is
    # median24 / ibja_999_live - 1, so as IBJA moves live the % drifts too.
    try:
        mk_anchors["median24"] = float(median24)
    except Exception:
        pass





    # Google sign-in: dormant until the GOOGLE_CLIENT_ID secret is set.
    gclient = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    analytics_token = os.environ.get("ANALYTICS_TOKEN", "").strip()
    gsi = ('<script src="https://accounts.google.com/gsi/client" async defer>'
           '</script>') if gclient else ""

    sig_ver = hashlib.md5(SIGNUP_JS.encode()).hexdigest()[:8]
    gate_html = GATE_HTML if gclient else ""
    gate_js   = GATE_JS   if gclient else ""
    # Freshness signals for Google / social crawlers. updated_http is an
    # RFC-1123 GMT string suitable for the Last-Modified HTTP header and its
    # HTML equivalent; updated_iso is the ISO-8601 form used by JSON-LD
    # dateModified, og:updated_time, and article:modified_time; updated_epoch
    # is the unix seconds the on-page "refreshed X ago" ticker counts up from.
    updated_http = formatdate(now_ist.timestamp(), usegmt=True)
    updated_iso = now_ist.isoformat(timespec="seconds")
    updated_epoch = str(int(now_ist.timestamp()))
    # The pageview beacon, inline and early. See analytics_snippet().
    analytics_js = analytics_snippet(supabase_url, anon_key)
    common = dict(site_url=SITE_URL, date=display_date, time=display_time,
                  iso_now=now_ist.isoformat(), year=str(now_ist.year),
                  updated_http=updated_http, updated_iso=updated_iso,
                  updated_epoch=updated_epoch,
                  base_css=BASE_CSS, ads_head=ads_head,
                  gclient=gclient, gsi=gsi, google_btn="",
                  sig_ver=sig_ver,
                  supabase_url=supabase_url, anon_key=anon_key,
                  gate_css=GATE_CSS if gclient else "",
                  gate_html=gate_html, gate_js=gate_js,
                  analytics_js=analytics_js,
                  nd_css=ND_CSS, nd_fonts=ND_FONTS,
                  nd_header=nd_header_html(),
                  nd_footer=nd_footer_html(now_ist.year))
    def city_cloud(current_slug=None):
        parts = []
        for nm in LOCATIONS:
            sl = loc_slug(nm)
            cur = ' aria-current="page"' if sl == current_slug else ""
            parts.append(
                f'<a href="gold-rate-today-in-{sl}"{cur}>{nm}</a>')
        return "".join(parts)

    low_g = inr(ladder(lowest["canonical_24k_pre_gst"])["24K"])

    def local_intro(nm, dark=False):
        """Enriched, unique per-city body so city pages have genuine local value."""
        if nm == "India":
            return ""
        board_html = local_board(nm, dark)
        data = CITY_ENRICHMENT_DATA.get(nm, {})
        hubs_info = f'<p><strong>Key Shopping Hubs in {nm}:</strong> {data["hubs"]}.</p>' if data.get("hubs") else ""
        brands_info = f'<p><strong>Featured Regional & National Jewellers in {nm}:</strong> {", ".join(data["regional_brands"])} and leading national brands.</p>' if data.get("regional_brands") else ""
        custom_desc = data.get("intro", f"Gold rates in {nm} follow national board rates across major jewellers. Compare live 24K, 22K, and 18K per-gram prices pre-GST below.")
        
        return board_html + (
            f'<section class="seo"><h2>Gold Rate Today in {nm} - Market Overview & Shopping Hubs</h2>'
            f'<p>{custom_desc}</p>'
            f'<p>Today the live median gold rate in <strong>{nm}</strong> is '
            f'<strong>{inr(med["24K"])} per gram for 24K (999 purity)</strong> and '
            f'<strong>{inr(med["22K"])} per gram for 22K (916 purity)</strong>, pre-GST. '
            f'Currently, <strong>{lowest["brands"]["name"]}</strong> offers the lowest 24K rate at '
            f'<strong>{low_g} per gram</strong>.</p>'
            f'{hubs_info}'
            f'{brands_info}'
            f'<p>Before buying gold in {nm}, use our <a href="{SITE_URL}/making-charges-calculator">making charges calculator</a> '
            f'to estimate total billed costs with 3% GST, or read our <a href="{SITE_URL}/learn/22k-vs-24k-gold">22K vs 24K guide</a>. '
            f'You can also <a href="{SITE_URL}/inquiry">subscribe to free daily {nm} rate alerts</a>.</p>'
            f'</section>')


    def local_board(nm, dark=False):
        """The part of a city or state page that is actually about that place.

        Every city page used to be the full /compare page with the place name
        swapped in - measured at 98-100% identical text between any two of
        them, which is the "low value content" AdSense rejects sites for and
        the doorway pattern Google demotes. This section uses data the build
        already has and nothing invented: which of the regional chains in
        REGION_MAP serve the place's state, and today's rate at each.

        It also corrects something. "Cheapest today" elsewhere on the page is
        computed over national chains only, so the Chennai page could name a
        national chain as cheapest while a Tamil Nadu chain was cheaper. Here
        regional chains that serve the state are included.
        """
        state = PLACE_STATE.get(nm)
        if not state:
            return ""
        def k22(r):
            return ladder(r["canonical_24k_pre_gst"])["22K"]
        regional = [r for r in live
                    if state in REGION_MAP.get((r["brands"] or {}).get("slug") or "", [])]
        rows_here = sorted(regional + national, key=k22)
        if not rows_here:
            return ""
        best = rows_here[0]
        nat_med22 = med["22K"]
        where = nm if nm == state else f"{nm} ({state})"
        trs = "".join(
            f'<tr><td class="lb-name">{_html.escape(r["brands"]["name"])}'
            + ('<span class="lb-tag">Regional</span>' if r in regional else '')
            + f'</td><td><strong>{inr(k22(r))}</strong></td>'
            f'<td>{inr(ladder(r["canonical_24k_pre_gst"])["24K"])}</td></tr>'
            for r in rows_here)
        # Regional chains we know serve this state, whether or not they
        # published a rate today - so a quiet day is not reported as "no
        # regional chains here".
        serving = sorted(sl for sl, sts in REGION_MAP.items() if state in sts)
        quiet = len(serving) - len({(r["brands"] or {}).get("slug") for r in regional})
        if regional:
            names = ", ".join(sorted({r["brands"]["name"] for r in regional}))
            who = (f'<p>Of the {len(live)} jewellers we track, {len(regional)} '
                   f'regional chain{"s" if len(regional) > 1 else ""} with stores in '
                   f'{state} published a rate today: {names}. '
                   + (f'{quiet} more that serve{"s" if quiet == 1 else ""} '
                      f'{state} did not. ' if quiet else '')
                   + f'They are listed with the national chains, cheapest 22K '
                   f'first.</p>')
        elif serving:
            who = (f'<p>The {len(serving)} regional chain'
                   f'{"s" if len(serving) > 1 else ""} we track in {state} did '
                   f'not publish a rate today, so the jewellers below are the '
                   f'national chains, which quote one price across India. '
                   f'Cheapest 22K first.</p>')
        else:
            who = (f'<p>We do not track a regional chain in {state} yet, so the '
                   f'jewellers below are the national chains, which quote one '
                   f'price across India. Cheapest 22K first.</p>')
        diff = nat_med22 - k22(best)
        # "Cheapest of these", not "cheapest in <city>": the rates are real,
        # but a national chain's listing here is not a claim that it has a
        # shop in this particular city.
        cheapest = (f'<p>Lowest 22K among these jewellers today: '
                    f'<strong>{_html.escape(best["brands"]["name"])}</strong> at '
                    f'<strong>{inr(k22(best))}/g</strong>'
                    + (f', {inr(round(diff))}/g below the national median.'
                       if diff >= 1 else '.') + '</p>')
        peers = [p for p in LOCATIONS
                 if PLACE_STATE.get(p) == state and p not in (nm, state)]
        links = ""
        if peers or (state != nm and state in LOCATIONS):
            items = []
            if state != nm and state in LOCATIONS:
                items.append(f'<a href="/gold-rate-today-in-{loc_slug(state)}">'
                             f'{state} (state)</a>')
            items += [f'<a href="/gold-rate-today-in-{loc_slug(p)}">{p}</a>'
                      for p in peers]
            links = (f'<h3>Gold rate in other places in {state}</h3>'
                     f'<div class="citycloud">{"".join(items)}</div>')
        if dark:
            # The new design is dark glass: inherit its text colour, draw
            # rules in translucent white, tag in the gold accent.
            style = ('<style>.local-board .lb-wrap{overflow-x:auto;max-width:100%}'
                     '.local-board h2{font-size:20px;margin:0 0 8px}'
                     '.local-board h3{font-size:15px;margin:18px 0 8px}'
                     '.local-board p{line-height:1.6;margin:0 0 10px;opacity:.9}'
                     '.local-tbl{width:100%;border-collapse:collapse;font-size:14px}'
                     '.local-tbl th,.local-tbl td{padding:9px 6px;'
                     'border-bottom:1px solid rgba(255,255,255,.08);'
                     'text-align:right;white-space:nowrap}'
                     '.local-tbl th{font-size:11px;letter-spacing:.06em;'
                     'text-transform:uppercase;opacity:.6;font-weight:500}'
                     '.local-tbl th:first-child,.local-tbl td:first-child'
                     '{text-align:left;white-space:normal}'
                     '.local-tbl .lb-tag{display:inline-block;margin-left:6px;'
                     'font-size:10.5px;padding:1px 6px;border-radius:8px;'
                     'background:rgba(212,175,55,.16);color:#e8c766}'
                     '.local-board .fine{font-size:12px;opacity:.6}'
                     '.local-board .citycloud{display:flex;flex-wrap:wrap;gap:8px}'
                     '.local-board .citycloud a{padding:6px 12px;border-radius:999px;'
                     'border:1px solid rgba(212,175,55,.25);color:inherit;'
                     'text-decoration:none;font-size:13px}'
                     # The new design colours text per element, not on body,
                     # so anything unstyled here would render dark on dark.
                     '.city-local,.city-local h2,.city-local h3,.city-local p,'
                     '.city-local td,.city-local strong{color:#efe4c8}'
                     '.city-local h2,.city-local h3{font-family:\'Playfair Display\','
                     'Georgia,serif}'
                     '.city-local .seo{margin-top:22px}'
                     '.city-local .seo h2{font-size:20px;margin:0 0 8px;'
                     'font-weight:600}'
                     '.city-local .seo p{line-height:1.6;margin:0 0 10px;'
                     'opacity:.9}'
                     '.city-local a{color:#e8c766}</style>')
        else:
            style = ('<style>.local-board .lb-wrap{overflow-x:auto;max-width:100%}'
                     '.local-tbl{width:100%;border-collapse:collapse;font-size:15px}'
                     '.local-tbl th,.local-tbl td{padding:9px 8px;'
                     'border-bottom:1px solid rgba(0,0,0,.08);text-align:right;'
                     'white-space:nowrap}'
                     '.local-tbl th:first-child,.local-tbl td:first-child'
                     '{text-align:left;white-space:normal}'
                     '.local-tbl .lb-tag{display:inline-block;margin-left:6px;'
                     'font-size:11px;padding:1px 6px;border-radius:8px;'
                     'background:rgba(180,140,40,.15);color:#7a5a10}'
                     '.local-board .fine{font-size:13px;opacity:.75}</style>')
        return style + (
            f'<section class="seo local-board"><h2>Jewellers serving {where} '
            f'&mdash; today&rsquo;s rates</h2>{who}{cheapest}'
            f'<div class="lb-wrap"><table class="local-tbl"><thead><tr>'
            f'<th>Jeweller</th><th>22K /g</th><th>24K /g</th></tr></thead>'
            f'<tbody>{trs}</tbody></table></div>'
            f'<p class="fine">Per gram, pre-GST, as published by each jeweller '
            f'on {display_date}. Add 3% GST and making charges for the billed '
            f'price.</p>{links}</section>')


    # As of the Sep-2026 IA swap, the app-test Market Pulse HTML is written
    # to docs/index.html by the /pulse builder further down. What used to be
    # the homepage (this SEO-rich comparison page with the Dataset+FAQPage
    # graph and 14+ jeweller cards) is preserved as /compare so nothing
    # loses its content or its schema.org anchor.
    inquiry = INQUIRY_TEMPLATE.substitute(**common)
    unsub = UNSUB_TEMPLATE.substitute(**common)

    os.makedirs("docs", exist_ok=True)
    build_og_image()
    build_favicons()
    build_email_logo()
    # /compare was the old design's comparison page. The homepage is that
    # comparison now - the full jeweller board, the FAQ with its FAQPage
    # markup, the city links - so /compare 301s to / (see _redirects) instead
    # of keeping a second copy of the homepage in the old design.
    if os.path.exists("docs/compare.html"):
        os.remove("docs/compare.html")
    with open("docs/signup.js", "w", encoding="utf-8") as f:
        # Click tracking rides along in the deferred bundle; it has no
        # urgency. The pageview does not - it is inline in the head.
        f.write(SIGNUP_JS + "\n" + CLICK_JS)

    def write_city_pages(home_html):
        """Every city and state page, in the new design.

        City pages used to be rendered from TEMPLATE - the old comparison
        page design - so anyone arriving from search for a place saw a
        different, older site from the homepage. They are now the homepage
        itself with the place's own title, heading, address, structured data
        and local_board() section, so a visitor lands in the same product,
        including its details popup.
        """
        n_live = len(live)
        for nm in LOCATIONS:
            sl = loc_slug(nm)
            url = f"{SITE_URL}/gold-rate-today-in-{sl}"
            title = (f"Gold Rate Today in {nm} ({display_date}) - 24K, 22K, "
                     f"18K Price | MyGoldRates")
            desc = (f"Gold rate today in {nm}: 24K {inr(med['24K'])}/g, 22K "
                    f"{inr(med['22K'])}/g (pre-GST) on {display_date}. Compare "
                    f"{n_live} jewellers' live rates and the chains that "
                    f"serve {PLACE_STATE.get(nm) or nm}.")
            h = home_html
            def sub(pattern, repl, h, count=1, flags=0):
                out, n = re.subn(pattern, repl, h, count=count, flags=flags)
                if n == 0:
                    raise RuntimeError(f"city page {nm}: no match for {pattern[:50]}")
                return out
            esc = _html.escape
            h = sub(r"<title>[^<]*</title>", f"<title>{esc(title)}</title>", h)
            h = sub(r'(<meta name="description" content=")[^"]*', r"\g<1>" + esc(desc).replace("\\", "\\\\"), h)
            h = sub(r'(<link rel="canonical" href=")[^"]*', r"\g<1>" + url, h)
            h = sub(r'(<meta property="og:url" content=")[^"]*', r"\g<1>" + url, h)
            for prop in ('property="og:title"', 'name="twitter:title"'):
                h = sub(r'(<meta ' + prop + r' content=")[^"]*', r"\g<1>" + esc(title).replace("\\", "\\\\"), h)
            for prop in ('property="og:description"', 'name="twitter:description"'):
                h = sub(r'(<meta ' + prop + r' content=")[^"]*', r"\g<1>" + esc(desc).replace("\\", "\\\\"), h)
            # headings
            # On phones the homepage's h1 is screen-reader only. A visitor
            # who searched for a place must see that place, so on city pages
            # the heading is visible at the top of the price panel.
            h = sub(r'<h1 class="sr-only">Gold Rate Today in India[^<]*</h1>',
                    ('<h1 style="margin:2px 16px 6px;text-align:center;'
                     'font-family:\'Playfair Display\',Georgia,serif;'
                     'font-size:22px;font-weight:700;line-height:1.25;'
                     'color:#f4e3a6">Gold Rate Today in ' + esc(nm)
                     + '<span style="display:block;margin-top:3px;'
                     'font-family:\'DM Sans\',system-ui,sans-serif;'
                     'font-size:12.5px;font-weight:500;color:rgba(255,255,255,.62)">'
                     f'Live 24K, 22K &amp; 18K from {n_live} jewellers</span></h1>')
                    .replace("\\", "\\\\"), h)
            h = sub(r"<h1>Gold Rate Today in India", "<h1>Gold Rate Today in " + esc(nm), h)
            # structured data: the homepage's blocks describe "/", replace them
            h = re.sub(r'<script type="application/ld\+json">.*?</script>\s*',
                       "", h, flags=re.S)
            ld = [x for x in _ld if x.get("@type") in ("WebSite", "Organization")] + [
                {"@context": "https://schema.org", "@type": "WebPage",
                 "url": url, "name": title, "inLanguage": "en-IN",
                 "dateModified": updated_iso,
                 "isPartOf": {"@type": "WebSite", "url": f"{SITE_URL}/"}},
                {"@context": "https://schema.org", "@type": "BreadcrumbList",
                 "itemListElement": [
                     {"@type": "ListItem", "position": 1, "name": "Home",
                      "item": f"{SITE_URL}/"},
                     {"@type": "ListItem", "position": 2,
                      "name": f"Gold Rate Today in {nm}", "item": url}]}]
            h = h.replace("</head>", '<script type="application/ld+json">'
                          + json.dumps(ld, ensure_ascii=False)
                          + "</script>\n</head>", 1)
            # the place's own section, in both layouts
            local = local_intro(nm, dark=True)
            if local:
                phone = f'<div class="city-local" style="margin:18px 12px 6px">{local}</div>\n  '
                i_rates = h.index('id="v-rates"')
                k = h.index('<div class="dv">', i_rates)
                h = h[:k] + phone + h[k:]
                desk = ('<section class="site-section"><div class="site-container">'
                        f'<div class="city-local">{local}</div></div></section>\n  ')
                h = sub(r'(<section class="site-section alt" id="s-market">)',
                        desk.replace("\\", "\\\\") + r"\g<1>", h)
            with open(f"docs/gold-rate-today-in-{sl}.html", "w",
                      encoding="utf-8") as f:
                f.write(h)
        print(f"city pages: wrote {len(LOCATIONS)} in the new design")

    # ---- programmatic city/state pages (same board, local landing page) ----
    # City pages used to be /compare with the place name swapped in: the
    # India FAQ ("What is the gold rate today in India?"), the 560-word
    # "About the Tool: Gold Rate Today in India" guide and the site-wide news
    # rail, repeated on all 95, measured at 97-100% identical text between
    # any two. That is the "low value content" AdSense rejects and the
    # doorway pattern search demotes. Those national sections now live only
    # on /compare and are linked from here; each city page keeps the rate
    # board and tools and leads with local_board(). Their structured data
    # drops the FAQPage (Google forbids FAQ markup for questions not on the
    # page) and the national Dataset, and gets a breadcrumb of its own.
    _ld = [x for x in json.loads(jsonld)
           if x.get("@type") not in ("FAQPage", "Dataset", "BreadcrumbList")]

    # The Jewellers Digest landing page. Its own module: it has its own
    # design, its own signup form, and its own degraded state when the
    # billing Worker is not answering.
    try:
        import jd_page
        jd_page.main()
    except Exception as e:                      # never fail the site build
        print(f"jd-page: SKIPPED ({type(e).__name__}: {e})")
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
  <a href="{SITE_URL}/inquiry">subscribe</a> to get the day's comparison
  by email each morning.</p>
  <h2>A note on the numbers</h2>
  <p>Rates shown are indicative and pre-GST, compiled from each brand's own
  published prices and updated daily. Making charges are extra and vary by
  design. Always confirm the billed rate with the jeweller before purchase.
  GoldRates is not affiliated with any jeweller and does not provide investment
  advice.</p>
  <p>Questions? <a href="{SITE_URL}/contact">Get in touch</a>.</p>""")

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
      <p>To receive the daily gold rate comparison directly in your inbox every morning, <a href="{SITE_URL}/inquiry">subscribe to daily email alerts here</a>.</p>

      <h2>Privacy &amp; Data Rights</h2>
      <p>To request access to or removal of your personal information, email us at <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> or read our <a href="{SITE_URL}/privacy">Privacy Policy</a>.</p>
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
  <p>The layout, design, comparison tools, calculators, and compiled datasets on MyGoldRates.com are protected by copyright and intellectual property laws. You may use this website for personal, non-commercial purposes. Automated collection, data extraction, or redistribution of our compiled data without explicit written consent is strictly prohibited.</p>
  
  <h2>4. Third-Party Advertising &amp; Cookies</h2>
  <p>We work with third-party advertising partners, including <strong>Google AdSense</strong>, to serve advertisements when you visit our website. These partners may use cookies and web beacons to serve ads based on your visit history. For more information, please see our <a href="{SITE_URL}/privacy">Privacy Policy</a>.</p>
  
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
  choices you have. Please also review our <a href="{SITE_URL}/terms">Terms of Service</a>.</p>
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

    # ---- 404 ----
    # Cloudflare Pages serves docs/404.html, with a 404 status, for any path
    # that matches no file. Without this file it falls back to index.html and
    # answers 200, so every mistyped or stale URL looked like a working
    # homepage. That is how the /city/<name>/ links stayed broken: the click
    # appeared to do nothing rather than failing, so the visitor clicked the
    # next city, the relative href resolved against the bad path, and the
    # analytics filled up with /city/jaipur/city/pune/city/nashik/ chains.
    # A 200 for a page that does not exist also invites Google to index an
    # unbounded number of duplicate homepages.
    #
    # Deliberately not in the sitemap, and noindex.
    render_content(
        "404",
        "Page not found | MyGoldRates",
        "That page does not exist. Find today's gold rate by city here.",
        "<h1>That page doesn't exist</h1>"
        "<p>The link you followed may be out of date, or the address may have "
        "been mistyped. Today's rates are all still here:</p>"
        f'<p><a href="{SITE_URL}/"><strong>Gold rate today across India'
        "</strong></a> &mdash; live 24K, 22K and 18K from every jeweller we "
        "track.</p>"
        "<h2>Gold rate by city</h2>"
        f'<div class="city-links">{city_cloud()}</div>',
        robots="noindex, follow")

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

    # ---- Making charges comparison (from collect_charges.py output) ----
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
            f"<h1>Gold Price {where_in} on {display_date}: Daily Report</h1>"
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
            f"Gold Price {where_in} on {display_date}: Daily Report | "
            "MyGoldRates",
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
        .replace("__DATE__", display_date)
        .replace("__CLICK_LABELS__",
                 json.dumps(CLICK_LABELS, ensure_ascii=False))
        .replace("__CITIES__", json.dumps(LOCATIONS)))
    with open("docs/analytics.html", "w", encoding="utf-8") as f:
        f.write(analytics_page)
    print("analytics dashboard: wrote docs/analytics.html (token via URL hash)")

    # Raw international spot in INR per gram at THIS build - the companion
    # to the IBJA anchor injected into the homepage below. The page divides
    # live spot by this to get an intraday movement ratio and applies it to
    # the real IBJA figure, so the India reference tracks the market without
    # inventing a premium. Zero if either upstream was unavailable, in which
    # case the page keeps its old spot x (1 + INDIA_PREMIUM) estimate.
    # Reuse the headlines already fetched above for the /compare page,
    # reshaped to the keys the homepage rail renders.
    _news_json = [{"title": n["title"], "url": n["link"],
                   "source": n["source"] or "Google News",
                   "published": n["dt"].isoformat() if n.get("dt") else ""}
                  for n in bullion_items]
    print(f"news: {len(_news_json)} headlines embedded for the homepage rail")

    _calendar_events = fetch_calendar()
    print(f"calendar: {len(_calendar_events)} US events this week")

    _ibja_anchor_spot = ((gold_usd / 31.1034768) * usdinr
                         if gold_usd and usdinr else 0)

    # ---- HOMEPAGE: Market Pulse (from app-test) --------------------------
    # As of the Sep-2026 IA swap, the app-test single-file Market Pulse HTML
    # is the site's homepage - written to docs/index.html with canonical /.
    # The previous SEO-rich comparison page (with the Dataset + FAQPage +
    # 14 jeweller cards) is preserved at /compare (docs/compare.html
    # emitted above). Both keep their content and schema.org anchors;
    # neither serves duplicate content.
    #
    # /pulse is served as a redirect (see docs/_redirects further down)
    # so old bookmarks and any inbound links to /pulse land on / with a
    # 301 - keeps link equity, avoids duplicate-content dilution.
    try:
        with open("pulse_app.html", encoding="utf-8") as f:
            pulse_html = f.read()

        # -- Hydrate the BRANDS array with LIVE Supabase rates -------------
        # pulse_app.html ships a hardcoded BRANDS array (snapshot from when
        # app-test was built) with stale per-brand rates that only re-scale
        # with live spot - it never re-reads Supabase, so brands added or
        # removed from the DB after that snapshot were mis-represented
        # (missing, wrong price, wrong ordering). We replace that literal
        # array at build time with the same `live` rows the classic /compare
        # page renders, keyed on brand slug + domain + region (national vs
        # regional). Result: pulse's brand comparison drops in with the same
        # 21+ jeweller board that /compare shows, updated daily by the
        # collector, and applyLive() then scales it against live spot.
        _region_pulse = {  # DB slug -> pulse-side region tag
            "vaibhav": "south", "vummidi": "south", "lalithaa": "south",
            "kirtilals": "south", "josco": "south", "srikumaran": "south",
            "ckc": "south", "joyalukkas": "south",
            "pngsons": "west", "ranka": "west", "rbz": "west",
            "chandukaka": "west", "bhindi": "west",
        }
        pulse_brands = []
        for _r in sorted(live, key=lambda x: x["canonical_24k_pre_gst"]):
            _b = _r.get("brands") or {}
            _slug = (_b.get("slug") or "").lower()
            _dom = ((_b.get("domain") or "")
                    .replace("https://", "").replace("http://", "")
                    .split("/")[0]).lstrip("www.")
            pulse_brands.append({
                "n": _b.get("name") or _slug,
                "d": _dom,
                # nat drives pulse's DEFAULT-VIEW visibility. National
                # brands show immediately; region-restricted jewellers
                # (REGION_MAP) appear only once the visitor turns on
                # "Include brands near me", which is the whole point of
                # that control - a Maharashtra-only jeweller is noise to
                # a buyer in Chennai.
                #
                # This was briefly forced to True on the theory that /
                # and /compare must show identical brand counts. They
                # must not: /compare is a full comparison table and
                # renders every row, while / is a personalised board with
                # an explicit near-me toggle. Making everything national
                # did not "unhide" anything - it removed the filter, so
                # regional brands showed to everyone by default.
                "nat": _slug not in REGION_MAP,
                # region tag drives the pulse-side "Near me" filter; default
                # 'all' for national brands and any regional we don't have a
                # mapping for (harmless - just always visible in Near-me).
                "r": _region_pulse.get(_slug, "all"),
                # 24K per-gram pre-GST INR - same value classic /compare uses
                "rate": round(float(_r["canonical_24k_pre_gst"]), 2),
            })
        # Regex-replace the whole hardcoded BRANDS=[...]; block. DOTALL so
        # the multi-line literal collapses. Fail loudly if the block shape
        # changed - a silent no-op would ship stale rates again.
        import re as _re
        _brands_json = json.dumps(pulse_brands, ensure_ascii=False)
        _new_pulse_html, _n = _re.subn(
            r"var BRANDS=\[.*?\n\s*\];",
            f"var BRANDS={_brands_json};",
            pulse_html, count=1, flags=_re.DOTALL)
        if _n != 1:
            raise RuntimeError(
                "pulse_app.html: BRANDS array literal not found - patch the "
                "hydration regex or the source file has drifted")
        pulse_html = _new_pulse_html
        print(f"pulse: hydrated BRANDS with {len(pulse_brands)} live jewellers "
              f"({pulse_brands[0]['n']} lowest at "
              f"₹{pulse_brands[0]['rate']:,.2f}/g)")
        # --------------------------------------------------------------------

        # Homepage title/description stay tuned to what search intent for
        # "gold rate today india" actually rewards - literal, factual, with
        # the number of jewellers and karat coverage - rather than the
        # /pulse-specific "Market Pulse" phrasing. Google matches queries
        # to page title tokens before it looks at anything else.
        home_title = ("Gold Rate Today in India - Live 24K, 22K, 18K "
                      "Rates from 14+ Jewellers | MyGoldRates")
        home_desc = ("Live gold rate today across 14+ Indian jewellers, "
                     "with MCX gold/silver futures, IBJA reference and "
                     "real-time market data updated every 3 seconds. "
                     "Compare 24K, 22K and 18K per-gram prices pre-GST.")
        home_canonical = f"{SITE_URL}/"
        home_url = f"{SITE_URL}/"
        replacements = [
            # canonical stays / - already there, no-op replacement is fine
            ('<link rel="canonical" href="https://mygoldrates.com/">',
             f'<link rel="canonical" href="{home_canonical}">'),
            ('<meta property="og:url" content="https://mygoldrates.com/">',
             f'<meta property="og:url" content="{home_url}">'),
            ("<title>Gold Rate Today in India - Compare 14+ Jewellers | "
             "MyGoldRates</title>",
             f"<title>{home_title}</title>"),
            ('<meta name="description" content="Live 24K, 22K & 18K gold '
             'rates from 14+ Indian jewellers, updated daily. Pre-GST '
             'prices, calculators (loan, SIP, making charges, budget) '
             'and market pulse — MyGoldRates.">',
             f'<meta name="description" content="{home_desc}">'),
            ('<meta property="og:title" content="Gold Rate Today in India '
             '- Compare 14+ Jewellers">',
             '<meta property="og:title" content="Gold Rate Today in India '
             '- Live from 14+ Jewellers">'),
            ('<meta property="og:description" content="Live 24K, 22K & 18K '
             'gold rates from 14+ Indian jewellers, updated daily.">',
             f'<meta property="og:description" content="{home_desc[:160]}">'),
            ('<meta name="twitter:title" content="Gold Rate Today in India '
             '- Compare Jewellers">',
             '<meta name="twitter:title" content="Gold Rate Today in India '
             '- Live Jeweller Rates | MyGoldRates">'),
            ('<meta name="twitter:description" content="Live 24K, 22K & '
             '18K gold rates from 14+ Indian jewellers, updated daily.">',
             f'<meta name="twitter:description" content="{home_desc[:160]}">'),
            # Last-updated stamp for the JEWELLER board rates. Distinct from
            # the live chip, which tracks the spot/MCX feed refreshing every
            # 3s - visitors were being shown a permanently "live" badge with
            # no way to tell how fresh the jeweller comparison itself was.
            # The epoch drives a client-side "x ago" ticker (below), so the
            # figure stays honest across CDN caching rather than freezing at
            # whatever the build time happened to be.
            ("__RATES_EPOCH__", str(int(now_ist.timestamp()))),
            ("__RATES_WHEN__",
             f"{display_date}, {display_time}"),
            # Real IBJA 24K anchor + the raw spot INR/g at this build, so the
            # page's India reference tracks intraday movement from a TRUE
            # published figure. It previously used spot x (1 + 0.14), a
            # guessed premium that sat ~43/g under the actual IBJA rate and
            # - worse - was also used to rebuild every BRAND price, which
            # discarded the collected values and inflated the whole board by
            # ~25/g. Both are "0" when a fetch failed; the page then falls
            # back to the old estimate for the tile only.
            ("__IBJA_ANCHOR_24__",
             f"{r999:.4f}" if ibja and r999 else "0"),
            ("__IBJA_ANCHOR_SPOT__",
             f"{_ibja_anchor_spot:.4f}" if _ibja_anchor_spot else "0"),
            # This week's US economic events, baked in at build time. The
            # browser used to ask our worker for these, but the worker cannot
            # reach the upstream at all (see fetch_calendar) so the strip was
            # permanently empty. "[]" when unavailable - the page then falls
            # back to the worker and, failing that, renders nothing.
            ("__CALENDAR_JSON__", json.dumps(_calendar_events,
                                             separators=(",", ":"))),
            # Bullion headlines, baked in at build time for the same reason
            # as the calendar: the worker cannot reach news.google.com, so
            # its /news answered with an empty list and the rail rendered
            # "no headlines right now" every day. This is the SAME
            # fetch_bullion_news() the /compare page already uses
            # successfully - CI reaches the feed without trouble.
            ("__NEWS_JSON__", json.dumps(_news_json,
                                         separators=(",", ":"))),
            # Google One Tap. pulse_app.html shipped the literal placeholder
            # "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com", so every
            # sign-in from the homepage hit Google's
            #   Error 401: invalid_client - The OAuth client was not found
            # /compare and /inquiry substitute the real id through $gclient
            # and have always worked; this page was never wired to it. With
            # no secret configured we emit an empty id and the One Tap block
            # is stripped below, rather than shipping a broken client.
            ('data-client_id="YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com"',
             f'data-client_id="{_html.escape(gclient, quote=True)}"'
             if gclient else 'data-client_id=""'),
        ]
        pulse_missing = []
        for old, new in replacements:
            if old not in pulse_html:
                pulse_missing.append(old[:60])
                continue
            pulse_html = pulse_html.replace(old, new, 1)
        if pulse_missing:
            raise RuntimeError("pulse_app.html header changed - patch these: "
                               + ", ".join(pulse_missing))
        # Links the homepage never had. It linked 14 city pages and nothing
        # else - no Privacy Policy, About, Contact or Terms, and no route to
        # /compare, /calculators or /news, which is why Search Console showed
        # /calculators and /news as "URL is unknown to Google" and /compare as
        # never crawled. AdSense reviewers look for policy pages and clear
        # navigation from the homepage. On phones the desktop layout and its
        # footer are display:none, and Google indexes the phone version, so
        # the same block goes at the foot of the default phone view too.
        _site_links = site_links_html()
        for _mark in ("<!--SITE_LINKS_APP-->", "<!--SITE_LINKS_SITE-->"):
            if _mark not in pulse_html:
                raise RuntimeError(f"pulse_app.html: {_mark} missing - the "
                                   "homepage would ship without policy links")
            pulse_html = pulse_html.replace(_mark, _site_links, 1)
        # AdSense. pulse_app.html carries the loader COMMENTED OUT with the
        # placeholder ca-pub-0000000000000000 ("INACTIVE by design"), and
        # nothing ever swapped it for the real id - the same unwired-
        # placeholder bug as the One Tap client id above. Every other page
        # gets ads_head from ADSENSE_CLIENT; the homepage, which takes about
        # half of all page views, made no ad request at all. Replace the
        # whole dormant block with the same ads_head the rest of the site
        # uses, or with nothing when the secret is unset.
        _ads_block = re.search(
            r"<!--[^>]*?Google AdSense[\s\S]*?-->", pulse_html)
        if not _ads_block:
            raise RuntimeError("pulse_app.html: dormant AdSense block not "
                               "found - the homepage would ship without ads")
        pulse_html = (pulse_html[:_ads_block.start()] + ads_head
                      + pulse_html[_ads_block.end():])
        # Extra JSON-LD: WebPage + BreadcrumbList + a "See detailed
        # comparison" pointer that carries the schema.org relationship
        # between / and /compare so Google understands the IA split.
        extra_ld = (
            '<script type="application/ld+json">'
            + json.dumps({
                "@context": "https://schema.org",
                "@graph": [
                    {"@type": "WebPage", "@id": f"{SITE_URL}/#webpage",
                     "url": home_url, "name": home_title,
                     "description": home_desc,
                     "inLanguage": "en-IN",
                     "isPartOf": {"@type": "WebSite",
                                  "url": f"{SITE_URL}/",
                                  "name": "MyGoldRates.com"},
                     "dateModified": now_ist.isoformat(),
                     "primaryImageOfPage": f"{SITE_URL}/og.png",
                     "significantLink": [
                         f"{SITE_URL}/news",
                         f"{SITE_URL}/calculators"]},
                    {"@type": "BreadcrumbList",
                     "itemListElement": [
                         {"@type": "ListItem", "position": 1,
                          "name": "Home", "item": home_url}]},
                ]}, ensure_ascii=False)
            + "</script>\n")
        # Analytics tracker: fires a page_views insert on load and delegated
        # click_events inserts on interactive clicks (dedup 2s per label).
        # Same table + shape as the classic TEMPLATE pages use via signup.js,
        # so /compare and / write into the same page_views stream and the
        # dashboard sums them together. pulse_app.html has no signup.js
        # dependency, so we inline the tracker directly here - no extra JS
        # file to load, no gate/modal/OTP code to conflict with the app's
        # own Google Identity Services flow.
        # The same inline beacon every other page gets, from the one
        # builder, rather than a second copy inlined here. The copy this
        # replaces had drifted: it still used a plain fetch() with no
        # keepalive long after the measurement showed that loses every
        # visitor who leaves inside ~1.6s.
        analytics_js = (
            '<script>window.GR_SB_URL=' + json.dumps(supabase_url)
            + ';window.GR_SB_KEY=' + json.dumps(anon_key) + ';</script>\n'
            + analytics_snippet(supabase_url, anon_key)
            # CLICK_JS only. NOT SIGNUP_JS: this app runs its own Google
            # Identity Services flow and the signup bundle's gate/modal/OTP
            # code collides with it.
            + '<script>' + CLICK_JS + '</script>\n')
        # NOTE: no hits/bump_hits injection here. pulse_app.html's own
        # loadHits() now calls bump_hits / hits_count against Supabase
        # directly (it used to read the third-party countapi counter, which
        # is what made / display a few hundred views instead of the real
        # figure). Injecting a second bump here as well would double-count
        # every fresh session, so the page owns that call outright and this
        # builder only supplies the GR_SB_URL / GR_SB_KEY globals via
        # analytics_js above, which loadHits() reads.
        # Live "x ago" next to the rates stamp. Reads the epoch off the DOM
        # rather than baking a string, so a CDN-cached copy still counts up
        # correctly instead of insisting the rates are "just now" hours
        # later. Ticks every 30s - the collect itself runs every 30 min.
        stamp_js = (
            '<script>(function(){\n'
            '  function ago(s){\n'
            '    if(s<60)return "just now";\n'
            '    if(s<120)return "1 min ago";\n'
            '    if(s<3600)return Math.round(s/60)+" min ago";\n'
            '    if(s<7200)return "1 hour ago";\n'
            '    if(s<86400)return Math.round(s/3600)+" hours ago";\n'
            '    var d=Math.round(s/86400);return d===1?"1 day ago":d+" days ago";\n'
            '  }\n'
            '  function tick(){\n'
            '    var el=document.getElementById("ratesStamp");\n'
            '    if(!el)return;\n'
            '    var e=parseInt(el.getAttribute("data-rates-epoch")||"0",10);\n'
            '    if(!e)return;\n'
            '    var out=document.getElementById("ratesStampAgo");\n'
            '    if(out)out.textContent=ago(Math.max(0,(Date.now()/1000|0)-e));\n'
            '  }\n'
            '  if(document.readyState==="loading")'
            'document.addEventListener("DOMContentLoaded",tick);else tick();\n'
            '  setInterval(tick,30000);\n'
            '})();</script>\n')
        # No GOOGLE_CLIENT_ID configured: remove the One Tap block outright.
        # Leaving it with an empty client_id makes the GSI library initialise
        # against nothing and fail on click - the same dead end the literal
        # placeholder produced. The classic templates already go dormant this
        # way; this brings the homepage in line.
        if not gclient:
            pulse_html = re.sub(
                r'<div id="g_id_onload".*?</div>',
                "<!-- Google One Tap disabled: GOOGLE_CLIENT_ID not set -->",
                pulse_html, count=1, flags=re.DOTALL)
            pulse_html = pulse_html.replace(
                '<script src="https://accounts.google.com/gsi/client" '
                'async defer></script>',
                "<!-- GSI client not loaded: GOOGLE_CLIENT_ID not set -->", 1)

        pulse_html = pulse_html.replace(
            "</head>", extra_ld + analytics_js + stamp_js + "</head>", 1)
        # Homepage now lives at docs/index.html - overwrites what TEMPLATE
        # used to write (that content is at docs/compare.html now).
        with open("docs/index.html", "w", encoding="utf-8") as f:
            f.write(pulse_html)
        print(f"homepage: wrote docs/index.html "
              f"({len(pulse_html):,} bytes, from pulse_app.html)")
        write_city_pages(pulse_html)
        # Remove any leftover /pulse/index.html from previous builds so it
        # doesn't compete with / for the same content in the index.
        old_pulse = "docs/pulse/index.html"
        if os.path.exists(old_pulse):
            os.remove(old_pulse)
            try:
                os.rmdir("docs/pulse")
            except OSError:
                pass  # not empty, leave it
            print("homepage: removed old docs/pulse/index.html")
    except FileNotFoundError:
        # No fallback. There used to be one that re-emitted the old design's
        # homepage and city pages when pulse_app.html was missing, which is
        # exactly how an old page reaches production unnoticed. A missing
        # template is a broken build and should look like one.
        raise RuntimeError("pulse_app.html not found - refusing to build the "
                           "site without the new design")

    # ---- no page left in the old design ----
    # Pages the build writes today come out in the new design. But docs/ is
    # deployed wholesale and nothing prunes it, so pages written once and
    # never again - methodology (written by hand in August) and every daily
    # report older than today - would keep the old design forever. This
    # converts any such page: it keeps its title, description, robots,
    # canonical, structured data and article, and re-renders it in the new
    # design. A page in the old design that cannot be converted fails the
    # build rather than shipping.
    def convert_legacy_pages():
        skip = {"docs/analytics.html", "docs/jewellers-digest.html"}
        converted, stuck = 0, []
        for root, _, files in os.walk("docs"):
            for fn in files:
                if not fn.endswith(".html"):
                    continue
                path = os.path.join(root, fn)
                if path in skip:
                    continue
                with open(path, encoding="utf-8") as fh:
                    old = fh.read()
                if 'class="nd-nav"' in old or 'id="v-rates"' in old:
                    continue
                def meta(pat, default=""):
                    m = re.search(pat, old, re.S)
                    return m.group(1) if m else default
                art = re.search(r'<article class="page">(.*)</article>', old, re.S)
                title = meta(r"<title>(.*?)</title>")
                canonical = meta(r'<link rel="canonical" href="([^"]*)"')
                if not (art and title and canonical):
                    stuck.append(path)
                    continue
                tail = old[art.end():]
                extra = "".join(
                    sc for sc in re.findall(r"<script\b[^>]*>.*?</script>", tail, re.S)
                    if "GR_SB_URL" not in sc and "signup.js" not in sc)
                page = CONTENT_TEMPLATE.substitute(
                    title=title,
                    desc=meta(r'<meta name="description" content="([^"]*)"'),
                    canonical=canonical,
                    robots=meta(r'<meta name="robots" content="([^"]*)"',
                                "index, follow, max-image-preview:large"),
                    jsonld_block="".join(re.findall(
                        r'<script type="application/ld\+json">.*?</script>', old, re.S)),
                    body=art.group(1), extra_js=extra, **common)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(page)
                converted += 1
        if stuck:
            raise RuntimeError("pages still in the old design that could not be "
                               "converted: " + ", ".join(sorted(stuck)[:20]))
        print(f"legacy pages: converted {converted} to the new design")

    convert_legacy_pages()

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
                # sitemap.xml is a sitemap-index that references the four
                # per-section sub-sitemaps (main, cities, daily, news).
                # Listing every one here as well is redundant but harmless
                # and gives Google an extra discovery path.
                f"Sitemap: {SITE_URL}/sitemap.xml\n"
                f"Sitemap: {SITE_URL}/sitemap_main.xml\n"
                f"Sitemap: {SITE_URL}/sitemap_cities.xml\n"
                f"Sitemap: {SITE_URL}/sitemap_daily.xml\n"
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
    # W3C-datetime lastmod (with the actual build time) is a stronger
    # freshness signal to Google than a bare date, and matches what our
    # Last-Modified HTTP header serves - so IMS conditional GETs line up.
    lastmod_full = now_ist.strftime("%Y-%m-%dT%H:%M:%S+05:30")

    # Split into per-section sub-sitemaps + a sitemap-index root so Google
    # can process them independently, spot per-section drops, and requeue
    # a single section without invalidating the rest.
    def _url(loc, lm, cf, pr):
        return (f"  <url><loc>{SITE_URL}/{loc}</loc>"
                f"<lastmod>{lm}</lastmod>"
                f"<changefreq>{cf}</changefreq>"
                f"<priority>{pr:.1f}</priority></url>\n")

    # main: home (Market Pulse) + /compare (SEO comparison) + evergreen.
    # /pulse is deliberately absent - it 301-redirects to / (see
    # docs/_redirects), so keeping it in the sitemap would advertise a
    # URL Google should not crawl on its own. The classic SEO comparison
    # page lives at /compare and gets its own sitemap entry so it retains
    # its Dataset/FAQPage schema anchor.
    main_urls = (
        _url("", lastmod_full, "hourly", 1.0)
        + _url("news", lastmod_full, "hourly", 0.85)
        + _url("inquiry", lastmod_full, "monthly", 0.6)
        # The paid product's landing page. Weekly rather than monthly: the
        # price and the offer on it change, and a stale cached version would
        # advertise a price that is no longer on sale.
        + _url("jewellers-digest", today, "weekly", 0.7)
        + "".join(_url(p, today, "monthly", 0.4)
                  for p in ("about", "contact", "privacy", "methodology"))
        + "".join(_url(loc, today, cf, float(pr))
                  for loc, cf, pr in extra_urls)
    )
    with open("docs/sitemap_main.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + main_urls
                + "</urlset>\n")

    # cities: state + city rate pages, refreshed hourly (rates re-fetch
    # multiple times per day)
    city_urls = "".join(
        _url(f"gold-rate-today-in-{loc_slug(nm)}", lastmod_full,
             "hourly", 0.8)
        for nm in LOCATIONS)
    with open("docs/sitemap_cities.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + city_urls
                + "</urlset>\n")

    # daily archive: only pages still inside the indexing window
    daily_urls = "".join(
        _url(loc, (dd or now_ist.date()).isoformat(), "monthly", 0.6)
        for loc, dd, ttl in daily_meta
        if dd and dd >= daily_index_cutoff)
    with open("docs/sitemap_daily.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + daily_urls
                + "</urlset>\n")

    # sitemap.xml is now the INDEX; sitemap_news.xml is written above and
    # referenced here so Google finds it via one canonical entry point.
    subs = ["sitemap_main.xml", "sitemap_cities.xml",
            "sitemap_daily.xml", "sitemap_news.xml"]
    with open("docs/sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/'
                'sitemap/0.9">\n'
                + "".join(
                    f"  <sitemap><loc>{SITE_URL}/{s}</loc>"
                    f"<lastmod>{lastmod_full}</lastmod></sitemap>\n"
                    for s in subs)
                + "</sitemapindex>\n")

    # ---- Cloudflare Pages _headers: freshness + edge caching --------------
    # Two things wrangler's pages-deploy upload flow strips that Google
    # cares about: file mtime (so no Last-Modified goes on the wire) and
    # a validator that lets Googlebot conditionally re-fetch. We rebuild
    # both here in a per-path _headers file that CF Pages honours. HTML
    # gets a short edge TTL (5 min, must-revalidate) with today's build
    # time as Last-Modified so Googlebot's If-Modified-Since either
    # returns 304 (cheap crawl budget) or 200 with a fresher timestamp
    # (freshness signal preserved). Static assets get an aggressive
    # immutable cache. sitemap.xml + rates.json opt out of edge caching
    # so IndexNow pings and RSS pulls always see the newest build.
    headers_lm = updated_http
    with open("docs/_headers", "w", encoding="utf-8") as f:
        f.write(
            "/*\n"
            f"  Last-Modified: {headers_lm}\n"
            "  Cache-Control: public, max-age=300, s-maxage=600, must-revalidate\n"
            "  X-Content-Type-Options: nosniff\n"
            "  Referrer-Policy: strict-origin-when-cross-origin\n"
            "  X-Robots-Tag: index, follow, max-image-preview:large\n"
            "\n"
            "/*.html\n"
            f"  Last-Modified: {headers_lm}\n"
            "  Cache-Control: public, max-age=300, s-maxage=600, must-revalidate\n"
            "\n"
            "/sitemap.xml\n"
            f"  Last-Modified: {headers_lm}\n"
            "  Cache-Control: public, max-age=0, must-revalidate\n"
            "\n"
            "/sitemap_main.xml\n"
            f"  Last-Modified: {headers_lm}\n"
            "  Cache-Control: public, max-age=0, must-revalidate\n"
            "\n"
            "/sitemap_cities.xml\n"
            f"  Last-Modified: {headers_lm}\n"
            "  Cache-Control: public, max-age=0, must-revalidate\n"
            "\n"
            "/sitemap_daily.xml\n"
            f"  Last-Modified: {headers_lm}\n"
            "  Cache-Control: public, max-age=0, must-revalidate\n"
            "\n"
            "/sitemap_news.xml\n"
            f"  Last-Modified: {headers_lm}\n"
            "  Cache-Control: public, max-age=0, must-revalidate\n"
            "\n"
            "/rates.json\n"
            f"  Last-Modified: {headers_lm}\n"
            "  Cache-Control: public, max-age=60, must-revalidate\n"
            "\n"
            "/robots.txt\n"
            "  Cache-Control: public, max-age=3600\n"
            "\n"
            "/*.png\n"
            "  Cache-Control: public, max-age=604800, immutable\n"
            "\n"
            "/*.svg\n"
            "  Cache-Control: public, max-age=604800, immutable\n"
            "\n"
            "/*.ico\n"
            "  Cache-Control: public, max-age=604800, immutable\n"
            "\n"
            "/*.js\n"
            "  Cache-Control: public, max-age=86400, must-revalidate\n"
        )
    print(f"_headers: written with Last-Modified {headers_lm}")

    # ---- _redirects: 301 legacy /pulse -> / after the IA swap -----------
    # /pulse used to serve the Market Pulse app. As of the Sep-2026 swap,
    # the same content is at /. Cloudflare Pages honours _redirects
    # (Netlify syntax): "from  to  status". A 301 keeps link equity on
    # anything Google or humans have already bookmarked as /pulse.
    #
    # The /city/<name>/ rules rescue a broken-link bug: the homepage linked
    # its city list as href="city/pune/", a path that was never built. Those
    # URLs are in analytics, in inbound links and in people's history, so
    # they get a 301 to the page they were always meant to reach. Written one
    # rule per city rather than with a :placeholder so that /city/<anything>
    # still 404s instead of redirecting to a page that does not exist.
    city_rules = "".join(
        f"/city/{loc_slug(nm)}    /gold-rate-today-in-{loc_slug(nm)}    301\n"
        f"/city/{loc_slug(nm)}/   /gold-rate-today-in-{loc_slug(nm)}    301\n"
        for nm in LOCATIONS if nm != "India")
    with open("docs/_redirects", "w", encoding="utf-8") as f:
        f.write("# Legacy /pulse redirects to / (homepage is Market Pulse "
                "since Sep 2026).\n"
                "/pulse    /    301\n"
                "/pulse/   /    301\n"
                "\n# /compare was the old design's comparison page; the homepage\n"
                "# is that comparison now.\n"
                "/compare        /    301\n"
                "/compare/       /    301\n"
                "/compare.html   /    301\n"
                "\n"
                "# The homepage once linked city pages as href=\"city/<name>/\",\n"
                "# which was never a real path. Pages answered 200 with\n"
                "# index.html, so the click looked like it did nothing and the\n"
                "# next click compounded the relative href into\n"
                "# /city/jaipur/city/pune/city/nashik/. Single-segment URLs are\n"
                "# rescued here; the chains fall through to 404.html.\n"
                + city_rules)
    print(f"_redirects: /pulse -> / (301), {len(city_rules.splitlines())} "
          "legacy /city/ rules")

    # ---- IndexNow: instantly notify Bing/Yandex/Seznam of fresh URLs ----
    INDEXNOW_KEY = "b7f3c9a1e04d4f6a8c2b5d9e1f0a3c7d"
    with open(f"docs/{INDEXNOW_KEY}.txt", "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)
    try:
        fresh_now = [f"{SITE_URL}/",
                     f"{SITE_URL}/news"]
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
        "license": f"{SITE_URL}/terms",
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
- Home (Market Pulse - live, ticking every 3s: gold/silver spot, MCX \
futures, IBJA reference, vendor rates, 90-day OHLC, economic calendar): \
{SITE_URL}/
- Detailed jeweller comparison (14+ brands, per-gram 24K/22K/18K, \
lowest-first, GST toggle, FAQ): {SITE_URL}/
- Market news & daily recap: {SITE_URL}/news
- Machine-readable JSON feed: {SITE_URL}/rates.json
- Daily email alerts: {SITE_URL}/inquiry
- About: {SITE_URL}/about
- Methodology: {SITE_URL}/methodology
- Contact: {SITE_URL}/contact
- City & state pages: {SITE_URL}/gold-rate-today-in-<city> \
(e.g. mumbai, delhi, hyderabad, chennai, bengaluru, pune, kolkata)

## Live market APIs (open, CORS-friendly)
- Real-time gold + silver spot, MCX futures, IBJA reference: \
{SITE_URL}/pulse (browser); underlying feed via the CF Worker at \
https://mygoldrates-market-api.harshads-priority.workers.dev/market
- Vendor (bullion dealer) rates: same worker, /vendors
- 90-day OHLC history (gold + silver futures): /ohlc?symbol=GC=F
- This week's economic calendar (gold-relevant events): /calendar
- Bullion news feed: /news

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
CLICK_JS = r"""/* ---- click analytics ----------------------------------------------------
   The PAGEVIEW is not sent from here any more. This file is deferred, so a
   beacon in it could not fire until an extra round trip had completed - on a
   live city page nothing at all was sent if the visitor left within 800ms.
   It now goes inline in the document head (see analytics_snippet()), which
   also owns the session id and the sender. This block only adds the click
   listener, which has no such urgency, and reuses both so the two cannot
   drift apart or double-count. */
(function(){
  var send=window.GR_TRACK;
  if(typeof send!=='function')return;        /* head snippet absent */
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
    send('click_events',{page:location.pathname,target:label,
      session_id:window.GR_SID||''});
  },true);
})();
"""

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

  /* ---- subscribe popup, once per browser, right after One Tap concludes ----
     Reuses the existing full modal (openModal, further down this file) -
     it was previously auto-opened by the hard sign-in gate, which analytics
     showed drove ~79% of visitors to just close it and leave, so that gate
     was removed. This is a softer re-introduction: it only ever fires once
     per browser (gr_otp_seen), never for an already-subscribed visitor, and
     never on top of the enrich-details modal that already opens when
     someone actually signs in via One Tap - it waits for One Tap's own
     moment to conclude (shown-and-dismissed, skipped, or never displayed at
     all - e.g. no Google session, cooldown, third-party cookies blocked)
     before deciding whether to show anything, so the two never compete for
     the same moment on screen. */
  function maybeShowSubscribePopup(){
    if(isAuthed())return;   // signed in via One Tap - enrich modal owns this moment
    try{if(localStorage.getItem('gr_sub')==='1')return;}catch(e){}      // already subscribed
    try{if(localStorage.getItem('gr_otp_seen'))return;}catch(e){}       // already shown once, ever
    try{if(sessionStorage.getItem('gr_dismissed'))return;}catch(e){}    // dismissed something already, this session
    // openModal() lives in a separate top-level IIFE further down this
    // script (the "daily-alerts modal" section) - not reachable by normal
    // closure from here, same reason this codebase already exposes
    // GR_OPENGATE globally for cross-section reuse. GR_OPENMODAL follows
    // that same pattern; it may not exist yet this early in page load, so
    // poll briefly instead of giving up after one failed check.
    // Not on arrival. This used to open the moment One Tap concluded - for
    // most visitors (no Google session in the browser) that is within a
    // second of landing, so a full-screen popup covered 100% of a phone
    // screen before the visitor had seen a single rate. Measured on the
    // live city pages: covering at 1s, 3s, 6s, 10s and 15s. That is the
    // "intrusive interstitial" Google demotes in mobile search, on exactly
    // the pages people arrive at from search, and Googlebot - always a
    // first-time visitor - saw it too. Now it waits until the visitor has
    // scrolled through half the page: they have had the answer they came
    // for, and an offer of daily alerts is a reasonable next step.
    whenEngaged(function(){
      var tries=0;
      (function tryOpen(){
        if(window.GR_OPENMODAL){
          try{localStorage.setItem('gr_otp_seen','1');}catch(e){}
          if(!isAuthed())window.GR_OPENMODAL();
        }else if(tries++<40){setTimeout(tryOpen,150);}
      })();
    });
  }
  function whenEngaged(fn){
    var fired=false;
    function check(){
      if(fired)return;
      var max=document.documentElement.scrollHeight-window.innerHeight;
      if(max>0&&window.scrollY/max>=0.5){
        fired=true;window.removeEventListener('scroll',check);fn();
      }
    }
    window.addEventListener('scroll',check,{passive:true});
  }

  /* ---- auto One Tap on page load ---- */
  (function autoOneTap(){
    if(!GCID||isAuthed()){maybeShowSubscribePopup();return;}
    var tries=0;
    (function tryG(){
      if(initIdClient()){
        try{
          google.accounts.id.prompt(function(n){
            var concluded=false;
            try{
              if(typeof n.isNotDisplayed==='function'&&n.isNotDisplayed())concluded=true;
              if(typeof n.isSkippedMoment==='function'&&n.isSkippedMoment())concluded=true;
              if(typeof n.isDismissedMoment==='function'&&n.isDismissedMoment())concluded=true;
            }catch(e){concluded=true;}
            if(concluded)maybeShowSubscribePopup();
          });
        }catch(e){maybeShowSubscribePopup();}
      }
      else if(tries++<40){setTimeout(tryG,150);}
      else{maybeShowSubscribePopup();}   // GSI never loaded at all - still offer it
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
$nd_fonts
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
$nd_css
</style>
$analytics_js</head>
<body>
$nd_header
<div class="wrap">

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



</div>
$nd_footer
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
<meta name="last-modified" content="$updated_http">
<meta http-equiv="last-modified" content="$updated_http">
<meta property="og:updated_time" content="$updated_iso">
<meta property="article:modified_time" content="$updated_iso">
<link rel="canonical" href="$canonical">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage","url":"$canonical","name":"$title","inLanguage":"en-IN","isPartOf":{"@type":"WebSite","url":"$site_url/","name":"MyGoldRates.com"},"dateModified":"$updated_iso"}</script>
<link rel="icon" href="$site_url/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="96x96" href="$site_url/icon-96.png">
<link rel="icon" type="image/png" sizes="48x48" href="$site_url/icon-48.png">
<link rel="icon" type="image/svg+xml" href="$site_url/favicon.svg">
<link rel="apple-touch-icon" href="$site_url/apple-touch-icon.png">
$ads_head
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
$nd_fonts
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
$nd_css
</style>
$analytics_js</head>
<body>
$nd_header
<div class="wrap">
<article class="page">
  <h1>$heading</h1>
  <p class="updated-on">Last updated $date</p>
$body
</article>

</div>
$nd_footer
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
$nd_fonts
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
$nd_css
</style>
$analytics_js</head>
<body>
$nd_header
<div class="wrap">
<article class="page">
$body
</article>

</div>
$nd_footer
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
$nd_fonts
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
$nd_css
</style>
</head>
<body>
$nd_header
<div class="wrap">
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
$nd_footer
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
# What each tracked click actually is, for the private analytics dashboard.
#
# The click tracker records a stable key - the element id when there is one,
# otherwise its visible text - because keys must not change when copy does,
# or one button splits into two rows. The price of a stable key is that it
# reads like "mcBrandTrigger" or "\u25a3". This map is where the meaning
# lives. tests/test_click_labels.py fails if a button with an id appears on
# the homepage without an entry here, so a new button cannot quietly show up
# on the dashboard under its HTML name.
#
# Keys with no entry fall through to rules in the dashboard's friendly():
# jeweller names, "Buy X 24K", weights, purities and so on.
CLICK_LABELS = {
    # bottom navigation (the four main views)
    "Rates": "Nav: Today's rates",
    "Market": "Nav: Live market",
    "Calc": "Nav: Calculators",
    "Making Charges": "Nav: Making charges",
    # top menu
    "navtog": "Menu: open",
    "nav-x": "Menu: close",
    "siteSignin": "Sign in (header)",
    # side drawers
    "drtab": "Gold markets panel: open",
    "drx": "Gold markets panel: close",
    "cdtab": "Calculators panel: open",
    "cdx": "Calculators panel: close",
    "coindtab": "Gold coins panel: open",
    "coindx": "Gold coins panel: close",
    # karat pills on the rate board
    "24K": "Rate board: show 24K",
    "22K": "Rate board: show 22K",
    "18K": "Rate board: show 18K",
    "14K": "Rate board: show 14K",
    # rate board controls (each has a mobile twin ending in S)
    "gstbtn": "Rate board: add 3% GST",
    "gstBtn": "Rate board: add 3% GST",
    "gstBtnS": "Rate board: add 3% GST",
    "nearbtn": "Rate board: brands near me",
    "nearBtn": "Rate board: brands near me",
    "nearBtnS": "Rate board: brands near me",
    # making-charges tool
    "mcBrandTrigger": "Making charges: choose jeweller",
    "mcBrandTriggerS": "Making charges: choose jeweller",
    # calculator tabs
    "Value": "Calculator: gold value",
    "Budget": "Calculator: gold for my budget",
    "Loan": "Calculator: gold loan",
    "SIP": "Calculator: gold SIP",
    "Making": "Calculator: making charges",
    # live chart - timeframe
    "LIVE": "Chart: live",
    "1D": "Chart: 1 day", "5D": "Chart: 5 days", "1M": "Chart: 1 month",
    "1m": "Chart: 1 month", "6M": "Chart: 6 months", "1Y": "Chart: 1 year",
    "5Y": "Chart: 5 years", "1W": "Chart: 1 week", "3M": "Chart: 3 months",
    "MAX": "Chart: all history", "5m": "Chart: 5-minute candles",
    "15m": "Chart: 15-minute candles",
    # live chart - type (the buttons are bare glyphs, hence the odd keys)
    "\u25b2": "Chart: area view",
    "\u223c": "Chart: line view",
    "\u25a3": "Chart: candlestick view",
    "\u22ee": "Chart: OHLC bar view",
    # hallmark checker
    "huid-scan-btn": "Hallmark (HUID) checker: verify",
    # email alert popup
    "spClose": "Alerts popup: closed",
    "spLater": "Alerts popup: maybe later",
    "m-close": "Add-your-city popup: closed",
    "m-btn": "Add-your-city popup: subscribe",
    "m-loc": "Add-your-city popup: use my location",
    "qs-btn": "Get free alerts (quick signup)",
    "alBtn": "Alerts: subscribe",
    "alBtnP": "Alerts: subscribe free",
    "alLocate": "Alerts: use my location",
    "alLocateP": "Alerts: use my location",
    "alLocateS": "Alerts: use my location",
    "alBtnS": "Alerts: subscribe",
    "f-loc": "Form: use my location",
    # sign-in gate
    "gate-close": "Sign-in gate: dismissed",
    "gate-gbtn": "Sign-in gate: continue with Google",
    "gate-enrich-skip": "Sign-in gate: skip details",
    "gate-form": "Sign-in gate: manual form",
    "gate-enrich": "Sign-in gate: details step",
    # forms
    "c-submit": "Contact form: send",
    "m-form": "Subscribe form", "mbtn": "Subscribe button",
    "inq": "Inquiry form",
    "brandsearch": "Jeweller search",
    # links and buttons on /compare and elsewhere
    "Compare jewellers": "Compare: jump to comparison table",
    "Making Charges Comparison": "Link: making-charges comparison page",
    # retired: a menu button removed in mid-September 2026; kept so old
    # date ranges still read properly
    "Charges": "Nav: Charges (old menu, removed Sep 2026)",
    # the dashboard's own buttons - shown so they can be recognised and ignored
    "apply": "(dashboard) Apply", "today": "(dashboard) Today",
}


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
    <button class="btn ghost" id="quick90">Last 90d</button>
    <button class="btn ghost" id="alltime">All time</button>
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

  // default range: last 30 days (was today only, which made the KPIs read
  // as if the site had only ever had today's traffic - a bad first-look
  // impression when the site has hundreds of pageviews/day for months).
  // 30d is a common default across analytics tools; users can drop back
  // to Today or extend to All time with the buttons below.
  var today=todayIST();
  var d30=todayIST(); d30.setUTCDate(d30.getUTCDate()-29);
  $('from').value=iso(d30); $('to').value=iso(today);

  // Readable names for click keys. The map is generated from CLICK_LABELS
  // in generate_site.py (one source, tested); rules below cover the
  // free-text keys that cannot be listed in advance.
  var CLICK_LABELS=__CLICK_LABELS__;
  var CITIES=__CITIES__;
  function friendly(t){
    if(t==null||t==='')return '(unlabelled)';
    if(CLICK_LABELS[t])return CLICK_LABELS[t];
    var s=String(t).trim(),m;
    if(s.indexOf('Use my current location')>-1||s.indexOf('location to autofill')>-1)
      return 'Use my location (autofill)';
    if((m=s.match(/^Buy (.+?) (24K|22K|18K)/)))return 'Buy link: '+m[1]+' '+m[2];
    if((m=s.match(/^Show full grid/)))return 'Dealer rates: show full grid';
    if((m=s.match(/^(\d+(?:\.\d+)?)\s*g$/i)))return 'Weight picked: '+m[1]+'g';
    if((m=s.match(/^(\d+K) \((\d+)\)$/)))return 'Making charges: purity '+m[1]+' ('+m[2]+')';
    if(/^(Gold Spot|MCX Gold|Silver Spot|MCX Silver|USD\/INR)$/i.test(s))
      return 'Market ticker: '+s;
    if((m=s.match(/^(\d+(?:\.\d+)?)g\s*\u00b7\s*(.+)$/)))
      return 'Making charges: '+m[1]+'g '+m[2];
    if(/^(Rings?|Earrings|Chains?|Bangles?|Necklaces?|Pendants?|Bracelets?|Coins?|Mangalsutras?|Nose ?pins?|Anklets?|Kadas?|Studs?|Jhumkas?)$/i.test(s))
      return 'Making charges: item '+s;
    if(/(Jewell?ers?|Tanishq|Kalyan|Malabar|CaratLane|ORRA|Bhima|Joyalukkas|Chetty|Gadgil|Senco|Reliance|Khazana|Kisna|Candere|BlueStone|PC Chandra|Waman Hari|Lalithaa|Thangamayil)/i.test(s))
      return 'Jeweller picked: '+s;
    if(CITIES.indexOf(s)>-1)return 'City picked: '+s;
    if(/^MyGoldRates/i.test(s))return 'Logo: back to home';
    if(/^\u20b9/.test(s))return 'Budget picked: '+s;
    if(/^(\d+(?:\.\d+)?\s*g\b.*|\d+\s*Tola)$/i.test(s))return 'Weight picked: '+s;
    // A card's title and blurb arrive run together (\"Gold SIP CalculatorProject
    // the future...\"); keep the title.
    if(s.length>30&&(m=s.match(/^(.{6,40}?[a-z])([A-Z][a-z].{8,})$/)))return 'Card: '+m[1];
    if(s.length>45)return 'Article link: '+s.slice(0,60)+'\u2026';
    s=s.replace(/^[^\x00-\x7F]+\s*/,'').trim();   // drop a leading emoji/pin
    // Anything still shaped like an HTML id gets flagged rather than passed
    // off as an action name, so a missing label is visible, not mysterious.
    if(/^[a-z]+[A-Z-][\w-]*$/.test(s))return s+' (unnamed button)';
    return s||String(t);
  }
  // Several keys mean the same action (a button and its mobile twin, or an
  // old key and a new one). Fold them into one row after renaming.
  function mergeByLabel(rows,key,val){
    var by={},out=[];
    rows.forEach(function(r){
      var k=r[key];
      if(!by[k]){by[k]={};by[k][key]=k;by[k][val]=0;out.push(by[k]);}
      by[k][val]+=Number(r[val])||0;
    });
    return out.sort(function(a,b){return b[val]-a[val];});
  }
  // Synthetic rows - build health probes and test traffic - all live under
  // paths starting "/__". They are not visitors.
  function isSynthetic(p){var x=String(p||'');
    return /^\/?__/.test(x)||x==='probe'||x==='diag';}

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

  // LIFETIME visits come from a DIFFERENT table than everything else on
  // this page. `hits` is the site's original visit counter (bumped once
  // per session via the bump_hits RPC from every page); `page_views` is
  // the newer per-pageview log that powers the charts and tables below.
  // They are not interchangeable and page_views is NOT a superset - it
  // only started collecting later. Showing only page_views totals made
  // the dashboard read ~164 when the real lifetime figure was ~6,400.
  // hits_count is a public RPC (anon may call it), so no secret needed
  // and no date range applies - it is always all-time.
  var LIFETIME=null;
  function loadLifetime(){
    return fetch(SB+'/rest/v1/rpc/hits_count',{method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,
        'Authorization':'Bearer '+KEY},body:'{}'})
      .then(function(r){return r.ok?r.json():Promise.reject(r.status);})
      .then(function(n){if(!isNaN(Number(n)))LIFETIME=Number(n);})
      .catch(function(){/* leave null - tile renders as an em dash */});
  }

  function renderKPIs(t){
    var k=$('kpis');
    var items=[
      ['Total visits (all time)',LIFETIME,'hits'],
      ['Page views',t.views,'range'],
      ['Unique visitors',t.visitors,'range'],
      ['Clicks',t.clicks,'range']];
    k.innerHTML=items.map(function(it){
      var val=(it[1]==null)?'&mdash;':nfmt(it[1]||0);
      var note=(it[2]==='hits')
        ? '<div class="l" style="font-size:10px;opacity:.65;text-transform:none;letter-spacing:0">from hits table &middot; ignores date filter</div>'
        : '';
      return '<div class="kpi"><div class="n">'+val+
        '</div><div class="l">'+it[0]+'</div>'+note+'</div>';}).join('');
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
      d.top_clicks=(d.top_clicks||[]).filter(function(r){return !isSynthetic(r.target);});
      d.top_clicks.forEach(function(r){r.target=friendly(r.target);});
      d.top_clicks=mergeByLabel(d.top_clicks,'target','clicks');
      d.top_pages=(d.top_pages||[]).filter(function(r){return !isSynthetic(r.page);});
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
  $('quick90').onclick=function(){var a=todayIST(),b=todayIST();b.setUTCDate(b.getUTCDate()-89);
    $('from').value=iso(b);$('to').value=iso(a);load();};
  // All time: earliest possible - the site launched mid-2026, but pick a
  // date safely earlier so no history is chopped off if analytics landed
  // sooner than expected.
  $('alltime').onclick=function(){var a=todayIST();
    $('from').value='2024-01-01';$('to').value=iso(a);load();};
  $('page').onchange=load;
  // Fetch the lifetime hits total first so the KPI row renders complete on
  // first paint; load() runs regardless of whether that call succeeds.
  loadLifetime().then(load,load);
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
