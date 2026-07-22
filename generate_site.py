#!/usr/bin/env python3
"""Render the public gold-rate comparison site from today's scraped rates.

Runs in CI right after scrape.py. Reads today's rates from Supabase, fetches
the IBJA reference rate, and bakes everything into static HTML written to
docs/ for GitHub Pages. The inquiry page posts to Supabase with the public
anon key (insert-only table behind RLS); no privileged keys are shipped.
"""

from __future__ import annotations

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
    rows = sb.table("rates").select("*, brands(name, slug, domain)") \
             .eq("rate_date", today).execute().data
    rows = [r for r in rows if r.get("brands") and r.get("canonical_24k_pre_gst")]
    live = [r for r in rows if r["status"] == "published"]
    if not live:
        print("no published rates today; site not regenerated")
        return

    median24 = statistics.median(r["canonical_24k_pre_gst"] for r in live)
    lowest = min(live, key=lambda r: r["canonical_24k_pre_gst"])
    now_ist = datetime.now(IST)
    display_date = now_ist.strftime("%d %B %Y")
    display_time = now_ist.strftime("%I:%M %p IST").lstrip("0")

    def ladder(c):
        return {p: c * f for p, f in PURITY_FRACTION.items()}

    med = ladder(median24)

    # --------------------------------------------------------------- IBJA
    ibja = fetch_ibja()
    if ibja:
        r999, r916 = ibja
        premium_med = (median24 / r999 - 1) * 100
        ibja_tiles = f'''
<section class="ibja-ref" aria-labelledby="ibjarefh">
  <p class="eyebrow">Bullion Reference</p>
  <h2 id="ibjarefh">IBJA Gold Rate Today</h2>
  <p class="hint">The India Bullion &amp; Jewellers Association benchmark,
  pre-GST - the wholesale rate jewellers price above.</p>
  <div class="ref-tiles">
    <div class="rtile"><div class="k">999 Fine · 24K</div>
      <div class="v">{inr(r999)}</div><div class="u">per gram, pre-GST</div></div>
    <div class="rtile"><div class="k">916 · 22K</div>
      <div class="v">{inr(r916)}</div><div class="u">per gram, pre-GST</div></div>
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
  <p class="hint">IBJA's bullion reference today is <strong>{inr(r999)}/g</strong>
  (999) and <strong>{inr(r916)}/g</strong> (916), pre-GST. Each bar is a
  brand's premium (or discount) per gram of pure gold versus bullion,
  smallest first. Hover a bar for the rupee difference.</p>
  <div class="chartcard pbar-card">
{bars}
  </div>
</section>'''
        ibja_faq = (
            f"The IBJA (India Bullion and Jewellers Association) reference rate "
            f"today is {inr(r999)} per gram for 999 gold and {inr(r916)} per "
            f"gram for 916 gold, before GST. Jewellery brands price on average "
            f"{premium_med:+.1f}% above the bullion reference today; the gap "
            "reflects each brand's sourcing and hallmarking premium.")
    else:
        ibja_tiles, ibja_section = "", ""
        ibja_faq = ("The IBJA (India Bullion and Jewellers Association) "
                    "publishes India's twice-daily bullion reference rate. "
                    "Jeweller board rates typically sit slightly above it, "
                    "reflecting sourcing and hallmarking premiums.")

    # ---------------------------------------------------------- table rows
    body_rows = []
    for r in sorted(live, key=lambda x: x["canonical_24k_pre_gst"]):
        b = r["brands"]
        lad = ladder(r["canonical_24k_pre_gst"])
        drift = (r["canonical_24k_pre_gst"] - median24) / median24 * 100
        if drift <= -0.05:
            dcls, dtxt = "delta-low", f"{drift:+.1f}%"
        elif drift >= 0.05:
            dcls, dtxt = "delta-high", f"{drift:+.1f}%"
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
        body_rows.append(
            f'<tr><th scope="row"><span class="bcell">{logo}'
            f'<span>{b["name"]}{best}{est}</span></span></th>'
            f'<td class="num" data-v="{lad["24K"]:.2f}">{inr(lad["24K"])}</td>'
            f'<td class="num" data-v="{lad["22K"]:.2f}">{inr(lad["22K"])}</td>'
            f'<td class="num" data-v="{lad["18K"]:.2f}">{inr(lad["18K"])}</td>'
            f'<td class="{dcls}" data-v="{drift:.2f}">{dtxt}</td></tr>')

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
        {"@context": "https://schema.org", "@type": "Dataset",
         "name": f"Gold rates across Indian jewellers on {display_date}",
         "description": "Daily 24K, 22K and 18K per-gram gold rates compared "
                        "across major Indian jewellery brands, with the IBJA "
                        "bullion reference and per-brand premium.",
         "dateModified": now_ist.isoformat(), "url": SITE_URL,
         "license": f"{SITE_URL}/#terms",
         "isAccessibleForFree": True,
         "creator": {"@type": "Organization", "name": "GoldRates",
                     "url": SITE_URL}},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}}
                        for q, a in faq]},
    ])

    faq_html = "\n".join(
        f'<details class="faq"><summary>{q}</summary><p>{a}</p></details>'
        for q, a in faq)

    common = dict(site_url=SITE_URL, date=display_date, time=display_time,
                  iso_now=now_ist.isoformat(), year=str(now_ist.year),
                  base_css=BASE_CSS, ads_head=ads_head)
    html = TEMPLATE.substitute(
        n_brands=str(len(live)),
        med24=inr(med["24K"]), med22=inr(med["22K"]), med18=inr(med["18K"]),
        low24=inr(ladder(lowest["canonical_24k_pre_gst"])["24K"]),
        low_brand=lowest["brands"]["name"],
        ibja_tiles=ibja_tiles, ibja_section=ibja_section, ads_unit=ads_unit,
        calc_brands=json.dumps(calc_brands),
        supabase_url=supabase_url, anon_key=anon_key,
        rows="\n".join(body_rows), faq=faq_html, jsonld=jsonld, **common)
    inquiry = INQUIRY_TEMPLATE.substitute(
        supabase_url=supabase_url, anon_key=anon_key, **common)
    unsub = UNSUB_TEMPLATE.substitute(
        supabase_url=supabase_url, anon_key=anon_key, **common)

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("docs/inquiry.html", "w", encoding="utf-8") as f:
        f.write(inquiry)
    with open("docs/unsubscribe.html", "w", encoding="utf-8") as f:
        f.write(unsub)

    # ---- static content pages (About / Contact / Privacy) ----
    def write_page(slug, title, desc, heading, body):
        with open(f"docs/{slug}.html", "w", encoding="utf-8") as fp:
            fp.write(PAGE_TEMPLATE.substitute(
                title=title, desc=desc, heading=heading, body=body,
                canonical=f"{SITE_URL}/{slug}.html", **common))

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
    with open("docs/robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n")
    with open("docs/sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                f"  <url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod>"
                "<changefreq>daily</changefreq><priority>1.0</priority></url>\n"
                f"  <url><loc>{SITE_URL}/inquiry.html</loc>"
                f"<lastmod>{today}</lastmod>"
                "<changefreq>monthly</changefreq><priority>0.6</priority></url>\n"
                + "".join(
                    f"  <url><loc>{SITE_URL}/{p}.html</loc><lastmod>{today}"
                    "</lastmod><changefreq>monthly</changefreq>"
                    "<priority>0.4</priority></url>\n"
                    for p in ("about", "contact", "privacy"))
                + "</urlset>\n")
    with open("docs/ads.txt", "w", encoding="utf-8") as f:
        if ads_client:
            pub = ads_client.replace("ca-", "")   # ca-pub-XXXX -> pub-XXXX
            f.write(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
        else:
            f.write("# Set the ADSENSE_CLIENT secret to publish your ads.txt "
                    "line automatically.\n"
                    "# google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0\n")
    with open("docs/.nojekyll", "w", encoding="utf-8") as f:
        f.write("")
    with open("docs/CNAME", "w", encoding="utf-8") as f:
        f.write(CUSTOM_DOMAIN + "\n")
    print(f"site generated: {len(live)} brands, median 24K {inr(med['24K'])}, "
          f"IBJA {'ok' if ibja else 'unavailable'}, "
          f"inquiry form {'armed' if anon_key else 'DISABLED (no anon key)'}")


BASE_CSS = """
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
header.top{display:flex;justify-content:space-between;align-items:center;
  flex-wrap:wrap;gap:6px 18px;padding:18px 0 14px}
.brand{font-size:22px;letter-spacing:.14em;text-transform:uppercase;
  text-decoration:none;color:var(--ink)}
.brand .karat{background:var(--gold-foil);-webkit-background-clip:text;
  background-clip:text;color:transparent}
.topright{display:flex;align-items:center;gap:16px}
.updated{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink-3)}
.btn{display:inline-block;font:500 13.5px/1 "IBM Plex Sans",sans-serif;
  background:var(--board);color:#F0DB9A;border:1px solid rgba(217,178,74,.5);
  padding:11px 18px;border-radius:999px;text-decoration:none;cursor:pointer;
  transition:transform .15s ease, box-shadow .15s ease}
.btn:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(0,0,0,.18)}
.btn-gold{background:var(--gold-foil);color:#1A1508;border:0;font-weight:600}
h2{font-size:24px;margin:2px 0 6px}
.hint{font-size:13.5px;color:var(--ink-3);margin-bottom:14px;max-width:72ch}
.chartcard{background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:18px}
.stamp{display:inline-block;font:500 10.5px/1 "IBM Plex Mono",monospace;
  letter-spacing:.08em;text-transform:uppercase;border-radius:4px;
  padding:3px 7px;margin-left:8px;vertical-align:2px}
.stamp-best{color:var(--gold);border:1px solid var(--gold)}
.stamp-est{color:var(--ink-3);border:1px solid var(--ink-3)}
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

TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gold Rate Today in India ($date) - Compare 24K, 22K &amp; 18K Rates Across $n_brands Jewellers</title>
<meta name="description" content="Live gold rate comparison for $date: 24K median $med24/g, 22K $med22/g pre-GST. Compare today's gold rates across $n_brands top Indian jewellers, check the IBJA bullion premium, and calculate gold prices instantly.">
<link rel="canonical" href="$site_url/">
<meta property="og:type" content="website">
<meta property="og:title" content="Gold Rate Today in India - Compare $n_brands Jewellers">
<meta property="og:description" content="24K median $med24/g today. Compare jewellers, check the bullion premium, calculate prices.">
<meta property="og:url" content="$site_url/">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
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
  radial-gradient(130% 150% at 84% -30%,rgba(224,186,86,.34),transparent 56%),
  radial-gradient(120% 130% at 8% 130%,rgba(176,132,42,.18),transparent 55%),
  linear-gradient(155deg,#171106,#0B0805 55%,#1B1409);
  color:#F0EAD8;border-radius:14px;margin:16px 0 10px;padding:24px 28px 20px;
  position:relative;overflow:hidden;border:1px solid rgba(224,186,86,.34)}
.board::after{content:"999 · 916 · 750";position:absolute;right:20px;bottom:12px;
  font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.35em;
  color:var(--gold-bright);opacity:.5}
.board h1{font-size:clamp(21px,3.4vw,31px);color:#F8EFD6;margin-bottom:4px}
.board .sub{color:#CFC7AE;max-width:58ch;font-size:13.5px;line-height:1.55}
.board-rates{display:flex;gap:11px;flex-wrap:wrap;margin-top:16px}
.tile{border:1px solid rgba(224,186,86,.32);border-radius:11px;
  padding:11px 15px;min-width:132px;flex:1;background:rgba(224,186,86,.05)}
.tile .k{font-family:"IBM Plex Mono",monospace;font-size:10.5px;
  letter-spacing:.18em;color:var(--gold-bright);text-transform:uppercase}
.tile .v{font-family:"IBM Plex Mono",monospace;font-size:clamp(18px,2.5vw,23px);
  margin-top:3px;background:linear-gradient(100deg,#F0DB9A,#FFFDF4 45%,#E8C86A);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.tile .u{font-size:11px;color:#A79B7E}
.tile.best{background:rgba(224,186,86,.13)}
.note{font-size:13px;color:var(--ink-3);margin:12px 0 24px}

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
<div class="wrap">

<header class="top">
  <a class="brand" href="$site_url/">Gold<span class="karat">Rates</span></a>
  <div class="topright">
    <span class="updated">Updated $date, $time</span>
    <a class="btn js-alert" href="inquiry.html">Daily rate alerts</a>
  </div>
</header>

<section class="board" aria-label="Today's gold rate summary">
  <h1>Gold Rate Today in India</h1>
  <p class="sub">Live 24K, 22K and 18K gold rates compared across $n_brands of
  India's top jewellery brands - updated daily, with the IBJA bullion
  reference for context.</p>
  <div class="board-rates">
    <div class="tile"><div class="k">24K Median</div>
      <div class="v">$med24</div><div class="u">per gram, pre-GST</div></div>
    <div class="tile"><div class="k">22K Median</div>
      <div class="v">$med22</div><div class="u">per gram, pre-GST</div></div>
    <div class="tile"><div class="k">18K Median</div>
      <div class="v">$med18</div><div class="u">per gram, pre-GST</div></div>
    <div class="tile best"><div class="k">Lowest 24K - $low_brand</div>
      <div class="v">$low24</div><div class="u">per gram, pre-GST</div></div>
  </div>
</section>

$ibja_tiles

<p class="note">All rates are per gram of gold, before 3% GST and before
making charges, so every brand is compared on the same basis.</p>

<section aria-labelledby="cmp">
  <p class="eyebrow">Today's Board</p>
  <h2 id="cmp">Compare Gold Rates Across Jewellers</h2>
  <div class="tablebar">
    <p class="hint" style="margin:0">Sorted by today's effective 24K rate -
    tap a column to re-sort.</p>
    <button class="gst" id="gstbtn" aria-pressed="false">Show incl. 3% GST</button>
  </div>
  <div class="tablecard">
  <table id="rates">
    <thead><tr>
      <th scope="col">Jeweller</th>
      <th scope="col" aria-sort="ascending">24K / g</th>
      <th scope="col">22K / g</th>
      <th scope="col">18K / g</th>
      <th scope="col">Δ vs median</th>
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
      <div class="m-field"><label for="m-name">Name *</label>
        <input id="m-name" name="name" autocomplete="name" required maxlength="80"></div>
      <div class="m-grid2">
        <div class="m-field"><label for="m-email">Email *</label>
          <input id="m-email" name="email" type="email" autocomplete="email"
          required maxlength="120"></div>
        <div class="m-field"><label for="m-phone">Phone *</label>
          <input id="m-phone" name="phone" type="tel" autocomplete="tel"
          inputmode="tel" required maxlength="20" placeholder="+91"></div>
      </div>
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
      <div class="hp" aria-hidden="true">
        <label>Website<input name="website" tabindex="-1" autocomplete="off"></label>
      </div>
      <label class="consent"><input type="checkbox" name="offers" checked>
        <span>Also send me gold offers, festive-scheme alerts and buying
        guides by email. You can opt out any time.</span></label>
      <button class="btn btn-gold" type="submit" id="m-btn">Subscribe</button>
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
      /* older table without the offers column: retry once without it */
      if(!retried&&payload.offers_optin!==undefined){
        var p2={};for(var k in payload){if(k!=='offers_optin')p2[k]=payload[k];}
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
    send({
      name:mform.name.value.trim(), email:mform.email.value.trim(),
      phone:mform.phone.value.trim(), country:mform.country.value,
      state:mform.state.value.trim(), city:mform.city.value.trim(),
      zip:mform.zip.value.trim(), offers_optin:mform.offers.checked
    },false).then(function(){
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
<link rel="canonical" href="$site_url/inquiry.html">
<meta name="robots" content="index,follow">
$ads_head
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
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
<div class="wrap">

<header class="top">
  <a class="brand" href="$site_url/">Gold<span class="karat">Rates</span></a>
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
  <div class="field"><label for="f-name">Name <span class="req">*</span></label>
    <input id="f-name" name="name" autocomplete="name" required maxlength="80"></div>
  <div class="grid2">
    <div class="field"><label for="f-email">Email <span class="req">*</span></label>
      <input id="f-email" name="email" type="email" autocomplete="email"
      required maxlength="120"></div>
    <div class="field"><label for="f-phone">Phone <span class="req">*</span></label>
      <input id="f-phone" name="phone" type="tel" autocomplete="tel"
      inputmode="tel" required maxlength="20" placeholder="+91"></div>
  </div>
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
    fetch(URL_+'/rest/v1/inquiries',{
      method:'POST',
      headers:{'Content-Type':'application/json','apikey':KEY,
               'Authorization':'Bearer '+KEY,'Prefer':'return=minimal'},
      body:JSON.stringify({
        name:form.name.value.trim(), email:form.email.value.trim(),
        phone:form.phone.value.trim(), country:form.country.value,
        state:form.state.value.trim(), city:form.city.value.trim(),
        zip:form.zip.value.trim(), offers_optin:form.offers.checked
      })
    }).then(function(r){
      if(!r.ok){throw new Error('bad status');}
      form.reset();ok.style.display='block';
      btn.textContent='Subscribed';
    }).catch(function(){
      err.style.display='block';
      btn.disabled=false;btn.textContent='Subscribe to daily rates';
    });
  });
})();
</script>
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
<div class="wrap">
<header class="top">
  <a class="brand" href="$site_url/">Gold<span class="karat">Rates</span></a>
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


UNSUB_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unsubscribe - GoldRates</title>
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="$site_url/unsubscribe.html">
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
<div class="wrap">
<header class="top">
  <a class="brand" href="$site_url/">Gold<span class="karat">Rates</span></a>
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
