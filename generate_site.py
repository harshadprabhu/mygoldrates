#!/usr/bin/env python3
"""Render the public gold-rate comparison site from today's scraped rates.

Runs in CI right after scrape.py. Reads today's rates and the full rate
history from Supabase, fetches the IBJA reference rate, and bakes everything
into static HTML (crawlers index real numbers, no keys shipped) written to
docs/ for GitHub Pages.
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

SITE_URL = "https://harshadprabhu.github.io/goldrates"
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
    """IBJA (India Bullion & Jewellers Association) daily reference rates,
    per 10g pre-GST on their site -> per gram. Returns (r999, r916) or None."""
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
    today = datetime.now(timezone.utc).date().isoformat()
    rows = sb.table("rates").select("*, brands(name, slug)") \
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

    # ------------------------------------------------------------ history
    hist = sb.table("rates").select("rate_date, canonical_24k_pre_gst, status") \
             .eq("status", "published").order("rate_date").execute().data
    by_day: dict[str, list[float]] = {}
    for r in hist:
        if r.get("canonical_24k_pre_gst"):
            by_day.setdefault(r["rate_date"], []).append(r["canonical_24k_pre_gst"])
    trend = [[d, round(statistics.median(v), 2)] for d, v in sorted(by_day.items())]

    # --------------------------------------------------------------- IBJA
    ibja = fetch_ibja()
    if ibja:
        r999, r916 = ibja
        premium = (median24 / r999 - 1) * 100
        ibja_strip = (
            '<div class="ibja" role="note">'
            '<span class="ibja-k">IBJA reference</span>'
            f'<span class="ibja-v">999 · {inr(r999)}/g</span>'
            f'<span class="ibja-v">916 · {inr(r916)}/g</span>'
            f'<span class="ibja-p">jeweller premium today {premium:+.1f}%</span>'
            '<span class="ibja-src">India Bullion &amp; Jewellers Assn., pre-GST</span>'
            '</div>')
        ibja_faq = (
            f"The IBJA (India Bullion and Jewellers Association) reference rate "
            f"today is {inr(r999)} per gram for 999 gold and {inr(r916)} per "
            f"gram for 916 gold, before GST. Jewellery brands price on average "
            f"{premium:+.1f}% relative to the bullion reference today; the gap "
            "reflects each brand's sourcing and hallmarking premium.")
    else:
        ibja_strip = ""
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
        body_rows.append(
            f'<tr><th scope="row">{b["name"]}{best}{est}</th>'
            f'<td data-v="{lad["24K"]:.0f}">{inr(lad["24K"])}</td>'
            f'<td data-v="{lad["22K"]:.0f}">{inr(lad["22K"])}</td>'
            f'<td data-v="{lad["18K"]:.0f}">{inr(lad["18K"])}</td>'
            f'<td class="{dcls}" data-v="{drift:.2f}">{dtxt}</td></tr>')

    # ------------------------------------------------------------- JSON-LD
    faq = [
        ("What is the gold rate today in India?",
         f"On {display_date}, the market median 24K gold rate across major "
         f"Indian jewellers is {inr(med['24K'])} per gram (pre-GST). The 22K "
         f"rate is {inr(med['22K'])} per gram. Rates are compared across "
         f"{len(live)} leading jewellery brands and refreshed daily."),
        ("Which jeweller has the lowest gold rate today?",
         f"Today, {lowest['brands']['name']} lists the lowest effective 24K "
         f"gold rate at {inr(ladder(lowest['canonical_24k_pre_gst'])['24K'])} "
         "per gram. Jewellers' rates typically differ by 1-3% because each "
         "brand embeds slightly different premiums in its pricing."),
        ("What is the IBJA gold rate and why does it differ from jeweller rates?",
         ibja_faq),
        ("Are these gold rates inclusive of GST?",
         "Rates shown are per gram, pre-GST, so brands can be compared on the "
         "same basis. Add 3% GST for the billed price of the gold value. "
         "Making charges vary by design and are always extra."),
        ("What is the difference between 24K, 22K and 18K gold?",
         "24K (99.9% pure) is investment-grade gold used for coins and bars. "
         "22K (91.6%) is the standard for traditional Indian jewellery. 18K "
         "(75%) is harder and common in diamond and everyday jewellery. "
         "Purity scales the price: the 22K rate is 91.6% of the pure-gold "
         "rate."),
        ("How often are these rates updated?",
         "Rates are refreshed automatically several times every day, and each "
         "brand's figure is quality-checked against the market before it is "
         "published."),
    ]
    jsonld = json.dumps([
        {"@context": "https://schema.org", "@type": "WebSite",
         "name": "GoldRates - Daily Gold Rate Comparison India",
         "url": SITE_URL},
        {"@context": "https://schema.org", "@type": "Dataset",
         "name": f"Gold rates across Indian jewellers on {display_date}",
         "description": "Daily 24K, 22K and 18K per-gram gold rates compared "
                        "across major Indian jewellery brands, with trend "
                        "history and the IBJA bullion reference.",
         "dateModified": now_ist.isoformat(), "url": SITE_URL,
         "creator": {"@type": "Organization", "name": "GoldRates"}},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}}
                        for q, a in faq]},
    ])

    faq_html = "\n".join(
        f'<details class="faq"><summary>{q}</summary><p>{a}</p></details>'
        for q, a in faq)

    html = TEMPLATE.substitute(
        site_url=SITE_URL, date=display_date, time=display_time,
        iso_now=now_ist.isoformat(), n_brands=str(len(live)),
        med24=inr(med["24K"]), med22=inr(med["22K"]), med18=inr(med["18K"]),
        low24=inr(ladder(lowest["canonical_24k_pre_gst"])["24K"]),
        low_brand=lowest["brands"]["name"],
        ibja_strip=ibja_strip,
        trend_json=json.dumps(trend),
        trend_since=trend[0][0] if trend else today,
        rows="\n".join(body_rows), faq=faq_html, jsonld=jsonld,
        year=str(now_ist.year))

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("docs/robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n")
    with open("docs/sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                f"  <url><loc>{SITE_URL}/</loc>"
                f"<lastmod>{today}</lastmod>"
                "<changefreq>daily</changefreq><priority>1.0</priority></url>\n"
                "</urlset>\n")
    with open("docs/ads.txt", "w", encoding="utf-8") as f:
        f.write("# Replace with your AdSense publisher line after approval:\n"
                "# google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0\n")
    with open("docs/.nojekyll", "w", encoding="utf-8") as f:
        f.write("")
    print(f"site generated: {len(live)} brands, median 24K {inr(med['24K'])}, "
          f"trend points {len(trend)}, IBJA {'ok' if ibja else 'unavailable'}")


TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gold Rate Today in India ($date) - Compare 24K, 22K &amp; 18K Rates Across $n_brands Jewellers</title>
<meta name="description" content="Live gold rate comparison for $date: 24K median $med24/g, 22K $med22/g pre-GST. Compare today's gold rates across $n_brands top Indian jewellers with IBJA bullion reference and price trend. Updated daily.">
<link rel="canonical" href="$site_url/">
<meta property="og:type" content="website">
<meta property="og:title" content="Gold Rate Today in India - Compare $n_brands Jewellers">
<meta property="og:description" content="24K median $med24/g today. Daily gold rate comparison, trend chart and IBJA reference.">
<meta property="og:url" content="$site_url/">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
<script type="application/ld+json">$jsonld</script>
<style>
:root{
  --paper:#FBF9F4; --ink:#181F1B; --ink-2:#49544D; --ink-3:#79847D;
  --board:#152420; --board-2:#1C312A; --gold:#9C7514; --gold-bright:#D9B24A;
  --gold-foil:linear-gradient(100deg,#8C6A18,#D9B24A 45%,#F0DB9A 55%,#C79A2E);
  --emerald:#1E5C46; --line:#E7E1D3; --card:#FFFFFF; --warm:#8A5A2B;
  --chart-line:#B98A1E; --chart-fill:rgba(185,138,30,.12);
}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#0E1613; --ink:#EDE9DD; --ink-2:#B4BDB4; --ink-3:#84908A;
    --board:#0A100D; --board-2:#131E18; --gold:#D9B24A; --gold-bright:#E8C86A;
    --emerald:#5BBB93; --line:#22302A; --card:#151F1A; --warm:#D89A5B;
    --chart-line:#D9B24A; --chart-fill:rgba(217,178,74,.12);
  }
}
*{box-sizing:border-box;margin:0}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}}
body{background:var(--paper);color:var(--ink);
  font:16px/1.6 "IBM Plex Sans",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:980px;margin:0 auto;padding:0 20px}
a{color:var(--emerald)}
h1,h2,.brand{font-family:"Marcellus",serif;font-weight:400;letter-spacing:.02em}
.eyebrow{font:500 11.5px/1 "IBM Plex Mono",monospace;letter-spacing:.28em;
  text-transform:uppercase;color:var(--gold);margin:40px 0 8px}

/* IBJA reference ticker */
.ibja{display:flex;flex-wrap:wrap;align-items:center;gap:8px 22px;
  font-family:"IBM Plex Mono",monospace;font-size:12.5px;
  padding:9px 0;border-bottom:1px solid var(--line);color:var(--ink-2)}
.ibja-k{letter-spacing:.2em;text-transform:uppercase;color:var(--gold);
  font-size:11px}
.ibja-v{color:var(--ink)}
.ibja-p{color:var(--emerald)}
.ibja-src{margin-left:auto;font-size:10.5px;color:var(--ink-3)}

header.top{display:flex;justify-content:space-between;align-items:baseline;
  flex-wrap:wrap;gap:4px 18px;padding:20px 0 16px}
.brand{font-size:22px;letter-spacing:.14em;text-transform:uppercase}
.brand .karat{background:var(--gold-foil);-webkit-background-clip:text;
  background-clip:text;color:transparent}
.updated{font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--ink-3)}

/* rate board hero */
.board{background:
  radial-gradient(120% 160% at 85% -20%,rgba(217,178,74,.16),transparent 55%),
  linear-gradient(160deg,var(--board),var(--board-2));
  color:#EDE9DD;border-radius:16px;margin:22px 0 12px;padding:40px 38px 34px;
  position:relative;overflow:hidden;border:1px solid rgba(217,178,74,.22)}
.board::after{content:"999 · 916 · 750";position:absolute;right:26px;bottom:18px;
  font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.35em;
  color:var(--gold-bright);opacity:.45}
.board h1{font-size:clamp(27px,4.6vw,42px);color:#F6F1E3;margin-bottom:6px}
.board .sub{color:#B9C2B4;max-width:54ch;font-size:15px}
.board-rates{display:flex;gap:14px;flex-wrap:wrap;margin-top:28px}
.tile{border:1px solid rgba(217,178,74,.35);border-radius:12px;
  padding:15px 20px;min-width:150px;flex:1;background:rgba(0,0,0,.14)}
.tile .k{font-family:"IBM Plex Mono",monospace;font-size:11.5px;
  letter-spacing:.22em;color:var(--gold-bright);text-transform:uppercase}
.tile .v{font-family:"IBM Plex Mono",monospace;font-size:clamp(20px,3vw,27px);
  margin-top:5px;background:linear-gradient(100deg,#F0DB9A,#FFFDF4 45%,#E8C86A);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.tile .u{font-size:12px;color:#8E9A8C}
.tile.best{background:rgba(217,178,74,.14)}

.note{font-size:13px;color:var(--ink-3);margin:12px 0 24px}

/* stamps */
.stamp{display:inline-block;font:500 10.5px/1 "IBM Plex Mono",monospace;
  letter-spacing:.08em;text-transform:uppercase;border-radius:4px;
  padding:3px 7px;margin-left:8px;vertical-align:2px}
.stamp-best{color:var(--gold);border:1px solid var(--gold)}
.stamp-est{color:var(--ink-3);border:1px solid var(--ink-3)}

/* trend chart */
h2{font-size:24px;margin:2px 0 6px}
.hint{font-size:13.5px;color:var(--ink-3);margin-bottom:14px}
.chartcard{background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:18px 18px 8px;position:relative}
.ranges{display:flex;gap:8px;margin-bottom:8px}
.ranges button{font:500 12px/1 "IBM Plex Mono",monospace;letter-spacing:.06em;
  background:none;border:1px solid var(--line);color:var(--ink-2);
  border-radius:999px;padding:7px 14px;cursor:pointer}
.ranges button[aria-pressed="true"]{border-color:var(--gold);color:var(--gold)}
#chart{width:100%;height:260px;display:block}
.tip{position:absolute;pointer-events:none;background:var(--board);
  color:#F6F1E3;font:500 12px/1.5 "IBM Plex Mono",monospace;border-radius:8px;
  padding:7px 11px;transform:translate(-50%,-115%);white-space:nowrap;
  display:none;border:1px solid rgba(217,178,74,.4)}
.chart-note{font-size:12px;color:var(--ink-3);padding:6px 2px 8px;
  font-family:"IBM Plex Mono",monospace}

/* comparison table */
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

.adslot{margin:30px 0;min-height:90px;border:1px dashed var(--line);
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  color:var(--ink-3);font-size:12px;letter-spacing:.08em}

.prose{max-width:68ch;color:var(--ink-2);font-size:15px}
.prose p{margin:10px 0}
.faq{border-bottom:1px solid var(--line);padding:14px 0}
.faq summary{font-weight:500;cursor:pointer;color:var(--ink)}
.faq p{margin-top:10px;color:var(--ink-2);max-width:70ch;font-size:15px}
footer{margin:44px 0 30px;padding-top:20px;border-top:1px solid var(--line);
  font-size:13px;color:var(--ink-3)}
footer p{margin:6px 0;max-width:80ch}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
</style>
</head>
<body>
<div class="wrap">

$ibja_strip

<header class="top">
  <div class="brand">Gold<span class="karat">Rates</span></div>
  <div class="updated">Updated $date, $time</div>
</header>

<section class="board" aria-label="Today's gold rate summary">
  <h1>Gold Rate Today in India</h1>
  <p class="sub">Live 24K, 22K and 18K gold rates compared across $n_brands of
  India's top jewellery brands - refreshed daily, with the IBJA bullion
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

<p class="note">All rates are per gram of gold, before 3% GST and before
making charges, so every brand is compared on the same basis.</p>

<!-- AdSense: paste your ad unit snippet inside this div after approval -->
<div class="adslot" aria-hidden="true">advertisement</div>

<section aria-labelledby="trendh">
  <p class="eyebrow">Price History</p>
  <h2 id="trendh">Gold Rate Trend</h2>
  <p class="hint">Median 24K rate per gram across tracked jewellers.</p>
  <div class="chartcard">
    <div class="ranges" role="group" aria-label="Trend range">
      <button data-days="7" aria-pressed="true">1W</button>
      <button data-days="30" aria-pressed="false">1M</button>
      <button data-days="90" aria-pressed="false">3M</button>
      <button data-days="365" aria-pressed="false">1Y</button>
    </div>
    <svg id="chart" role="img" aria-label="Gold rate trend chart"></svg>
    <div class="tip" id="tip"></div>
    <div class="chart-note">tracking daily since $trend_since - history
    deepens automatically every day</div>
  </div>
</section>

<section aria-labelledby="cmp">
  <p class="eyebrow">Today's Board</p>
  <h2 id="cmp">Compare Gold Rates Across Jewellers</h2>
  <p class="hint">Sorted by today's effective 24K rate - tap any column
  heading to re-sort. "Δ vs median" shows how far each brand's pricing sits
  from the market middle.</p>
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

<div class="adslot" aria-hidden="true">advertisement</div>

<section aria-labelledby="faqh">
  <p class="eyebrow">Know Your Gold</p>
  <h2 id="faqh">Gold Rate FAQs</h2>
$faq
</section>

<footer>
  <p><strong>Disclaimer:</strong> Rates are indicative, compiled from each
  brand's published prices, and can change during the day. Always confirm the
  billed rate with the jeweller before purchase. This site does not provide
  investment advice.</p>
  <p>© $year GoldRates - daily gold rate comparison for India. Data refreshed
  automatically; last build $iso_now.</p>
</footer>

</div>
<script>
var TREND=$trend_json;
(function(){
  /* ---- sortable table ---- */
  var table=document.getElementById('rates');
  var heads=table.tHead.rows[0].cells, body=table.tBodies[0];
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

  /* ---- trend chart ---- */
  var svg=document.getElementById('chart'), tip=document.getElementById('tip');
  var css=getComputedStyle(document.documentElement);
  function v(name){return css.getPropertyValue(name).trim();}
  var NS='http://www.w3.org/2000/svg';
  var pts=[];
  function fmt(n){
    var s=Math.round(n).toString(), out=s.slice(-3), rest=s.slice(0,-3);
    while(rest.length>2){out=rest.slice(-2)+','+out;rest=rest.slice(0,-2);}
    if(rest)out=rest+','+out;
    return '\\u20B9'+out;
  }
  function draw(days){
    var cutoff=new Date(); cutoff.setDate(cutoff.getDate()-days);
    var data=TREND.filter(function(d){return new Date(d[0])>=cutoff;});
    if(data.length<2)data=TREND.slice();
    while(svg.firstChild)svg.removeChild(svg.firstChild);
    var W=svg.clientWidth||800, H=260, padL=64, padR=16, padT=18, padB=30;
    svg.setAttribute('viewBox','0 0 '+W+' '+H);
    if(data.length===0)return;
    var ys=data.map(function(d){return d[1];});
    var mn=Math.min.apply(null,ys), mx=Math.max.apply(null,ys);
    var span=Math.max(mx-mn,mx*0.004); mn-=span*0.25; mx+=span*0.25;
    function X(i){return data.length===1?(padL+(W-padL-padR)/2)
      :padL+(W-padL-padR)*i/(data.length-1);}
    function Y(val){return padT+(H-padT-padB)*(1-(val-mn)/(mx-mn));}
    // gridlines + y labels
    for(var g=0;g<3;g++){
      var gv=mn+(mx-mn)*(0.15+0.35*g), gy=Y(gv);
      var ln=document.createElementNS(NS,'line');
      ln.setAttribute('x1',padL);ln.setAttribute('x2',W-padR);
      ln.setAttribute('y1',gy);ln.setAttribute('y2',gy);
      ln.setAttribute('stroke',v('--line'));ln.setAttribute('stroke-width','1');
      svg.appendChild(ln);
      var tx=document.createElementNS(NS,'text');
      tx.setAttribute('x',padL-8);tx.setAttribute('y',gy+4);
      tx.setAttribute('text-anchor','end');
      tx.setAttribute('fill',v('--ink-3'));
      tx.setAttribute('font-size','11');
      tx.setAttribute('font-family','IBM Plex Mono,monospace');
      tx.textContent=fmt(gv);svg.appendChild(tx);
    }
    // x labels: first / last
    [[0,'start'],[data.length-1,'end']].forEach(function(p){
      if(data.length<2&&p[0]>0)return;
      var tx=document.createElementNS(NS,'text');
      tx.setAttribute('x',X(p[0]));tx.setAttribute('y',H-8);
      tx.setAttribute('text-anchor',p[1]);
      tx.setAttribute('fill',v('--ink-3'));tx.setAttribute('font-size','11');
      tx.setAttribute('font-family','IBM Plex Mono,monospace');
      var d=new Date(data[p[0]][0]);
      tx.textContent=d.getDate()+' '+['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];
      svg.appendChild(tx);
    });
    // area + line
    var line='',area='';
    data.forEach(function(d,i){
      line+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(d[1]).toFixed(1);
    });
    area=line+'L'+X(data.length-1).toFixed(1)+' '+(H-padB)
      +'L'+X(0).toFixed(1)+' '+(H-padB)+'Z';
    var ap=document.createElementNS(NS,'path');
    ap.setAttribute('d',area);ap.setAttribute('fill',v('--chart-fill'));
    svg.appendChild(ap);
    var lp=document.createElementNS(NS,'path');
    lp.setAttribute('d',line);lp.setAttribute('fill','none');
    lp.setAttribute('stroke',v('--chart-line'));
    lp.setAttribute('stroke-width','2');lp.setAttribute('stroke-linecap','round');
    svg.appendChild(lp);
    // points + last label
    data.forEach(function(d,i){
      var c=document.createElementNS(NS,'circle');
      c.setAttribute('cx',X(i));c.setAttribute('cy',Y(d[1]));
      c.setAttribute('r',i===data.length-1?4:3);
      c.setAttribute('fill',v('--chart-line'));
      c.setAttribute('stroke',v('--card'));c.setAttribute('stroke-width','2');
      svg.appendChild(c);
    });
    var last=document.createElementNS(NS,'text');
    last.setAttribute('x',Math.min(X(data.length-1),W-padR-4));
    last.setAttribute('y',Y(data[data.length-1][1])-12);
    last.setAttribute('text-anchor','end');
    last.setAttribute('fill',v('--gold'));
    last.setAttribute('font-size','12.5');last.setAttribute('font-weight','600');
    last.setAttribute('font-family','IBM Plex Mono,monospace');
    last.textContent=fmt(data[data.length-1][1]);
    svg.appendChild(last);
    // hover
    svg.onmousemove=function(e){
      var r=svg.getBoundingClientRect();
      var mx_=(e.clientX-r.left)*(W/r.width);
      var best=0,bd=1e9;
      data.forEach(function(d,i){var dd=Math.abs(X(i)-mx_);if(dd<bd){bd=dd;best=i;}});
      var d=new Date(data[best][0]);
      tip.style.display='block';
      tip.style.left=(X(best)*(r.width/W))+'px';
      tip.style.top=(Y(data[best][1])*(r.height/H))+'px';
      tip.textContent=d.getDate()+' '+['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]+' · '+fmt(data[best][1]);
    };
    svg.onmouseleave=function(){tip.style.display='none';};
  }
  var btns=document.querySelectorAll('.ranges button');
  [].forEach.call(btns,function(b){
    b.addEventListener('click',function(){
      [].forEach.call(btns,function(x){x.setAttribute('aria-pressed','false');});
      b.setAttribute('aria-pressed','true');
      draw(parseInt(b.dataset.days,10));
    });
  });
  draw(7);
  window.addEventListener('resize',function(){
    var act=document.querySelector('.ranges button[aria-pressed="true"]');
    draw(parseInt(act.dataset.days,10));
  });
})();
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main()
