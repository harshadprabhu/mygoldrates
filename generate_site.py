#!/usr/bin/env python3
"""Render the public gold-rate comparison site from today's scraped rates.

Runs in CI right after scrape.py. Reads today's rates from Supabase, bakes
them into static HTML (crawlers index real numbers, no keys shipped), and
writes docs/ for GitHub Pages. Pure stdlib + supabase client.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from string import Template

from supabase import create_client

SITE_URL = "https://harshadprabhu.github.io/goldrates"
PURITY_FRACTION = {"24K": 0.999, "22K": 0.916, "18K": 0.750, "14K": 0.583}
IST = timezone(timedelta(hours=5, minutes=30))


def inr(v):
    """Indian-style grouping: 1,23,456."""
    s = f"{v:,.0f}"
    parts = s.split(",")
    if len(parts) <= 2:
        return "₹" + s
    head, tail = parts[0], parts[-1]
    mid = ",".join(parts[1:-1]).replace(",", "")
    digits = head + mid
    groups = []
    while len(digits) > 2:
        groups.insert(0, digits[-2:])
        digits = digits[:-2]
    if digits:
        groups.insert(0, digits)
    return "₹" + ",".join(groups) + "," + tail


def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    today = datetime.now(timezone.utc).date().isoformat()
    rows = sb.table("rates").select("*, brands(name, slug, domain)") \
             .eq("rate_date", today).execute().data
    rows = [r for r in rows if r.get("brands") and r.get("canonical_24k_pre_gst")]
    live = [r for r in rows if r["status"] == "published"]
    if not live:
        print("no published rates today; site not regenerated")
        return

    import statistics
    median24 = statistics.median(r["canonical_24k_pre_gst"] for r in live)
    lowest = min(live, key=lambda r: r["canonical_24k_pre_gst"])
    now_ist = datetime.now(IST)
    display_date = now_ist.strftime("%d %B %Y")
    display_time = now_ist.strftime("%I:%M %p IST").lstrip("0")

    def ladder(c):
        return {p: c * f for p, f in PURITY_FRACTION.items()}

    med = ladder(median24)

    # ---------------------------------------------------------- table rows
    body_rows, faq_low = [], ""
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
    faq_low = lowest["brands"]["name"]

    # ---------------------------------------------------------- JSON-LD
    import json as _json
    faq = [
        ("What is the gold rate today in India?",
         f"On {display_date}, the market median 24K gold rate across major Indian "
         f"jewellers is {inr(med['24K'])} per gram (pre-GST). The 22K rate is "
         f"{inr(med['22K'])} per gram. Rates on this page are compared across "
         f"{len(live)} leading jewellery brands and updated daily."),
        ("Which jeweller has the lowest gold rate today?",
         f"Today, {faq_low} lists the lowest effective 24K gold rate at "
         f"{inr(ladder(lowest['canonical_24k_pre_gst'])['24K'])} per gram. "
         "Jewellers' rates typically differ by 1-3% because each brand embeds "
         "slightly different sourcing premiums in its pricing."),
        ("Are these gold rates inclusive of GST?",
         "Rates shown are per gram, pre-GST, so brands can be compared on the "
         "same basis. Add 3% GST for the billed price of the gold value. Making "
         "charges vary by design and are always extra."),
        ("What is the difference between 24K, 22K and 18K gold?",
         "24K (99.9% pure) is investment-grade gold used for coins and bars. "
         "22K (91.6%) is the standard for traditional Indian jewellery. 18K "
         "(75%) is harder and common in diamond and everyday jewellery. Purity "
         "scales the price: the 22K rate is 91.6% of the pure-gold rate."),
        ("How are these rates collected?",
         "Every rate comes from the brand's own published prices - official "
         "rate pages or the gold price breakup on the brand's product pages - "
         "collected automatically several times a day, cross-checked against "
         "the market median, and normalised to a per-gram pre-GST basis."),
    ]
    jsonld = _json.dumps([
        {"@context": "https://schema.org", "@type": "WebSite",
         "name": "GoldRates - Daily Gold Rate Comparison India",
         "url": SITE_URL},
        {"@context": "https://schema.org", "@type": "Dataset",
         "name": f"Gold rates across Indian jewellers on {display_date}",
         "description": "Daily 24K, 22K and 18K per-gram gold rates compared "
                        "across major Indian jewellery brands.",
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
        iso_now=now_ist.isoformat(),
        n_brands=str(len(live)),
        med24=inr(med["24K"]), med22=inr(med["22K"]), med18=inr(med["18K"]),
        low24=inr(ladder(lowest["canonical_24k_pre_gst"])["24K"]),
        low_brand=lowest["brands"]["name"],
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
    print(f"site generated: {len(live)} brands, median 24K {inr(med['24K'])}")


TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gold Rate Today in India ($date) - Compare 24K, 22K &amp; 18K Rates Across $n_brands Jewellers</title>
<meta name="description" content="Live gold rate comparison for $date: 24K median $med24/g, 22K $med22/g pre-GST. Compare today's gold rates across $n_brands top Indian jewellers - Tanishq, Kalyan, Malabar, CaratLane and more. Updated daily.">
<link rel="canonical" href="$site_url/">
<meta property="og:type" content="website">
<meta property="og:title" content="Gold Rate Today in India - Compare $n_brands Jewellers">
<meta property="og:description" content="24K median $med24/g today. Daily gold rate comparison across India's top jewellery brands.">
<meta property="og:url" content="$site_url/">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
<script type="application/ld+json">$jsonld</script>
<style>
:root{
  --paper:#FAF8F3; --ink:#17281F; --ink-2:#4A5A50; --ink-3:#7A867E;
  --board:#17281F; --board-2:#1E3428; --gold:#A87E1C; --gold-bright:#D9B24A;
  --emerald:#1E5C46; --line:#E4DFD2; --card:#FFFFFF; --warm:#8A5A2B;
}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#101915; --ink:#EDE9DD; --ink-2:#B4BDB4; --ink-3:#84908A;
    --board:#0B120E; --board-2:#142019; --gold:#D9B24A; --gold-bright:#E8C86A;
    --emerald:#5BBB93; --line:#233229; --card:#16211B; --warm:#D89A5B;
  }
}
*{box-sizing:border-box;margin:0}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}}
body{background:var(--paper);color:var(--ink);
  font:16px/1.6 "IBM Plex Sans",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:0 20px}
a{color:var(--emerald)}
h1,h2,.brand{font-family:"Marcellus",serif;font-weight:400;letter-spacing:.02em}

header.top{display:flex;justify-content:space-between;align-items:baseline;
  flex-wrap:wrap;gap:4px 18px;padding:22px 0;border-bottom:1px solid var(--line)}
.brand{font-size:22px;letter-spacing:.14em;text-transform:uppercase}
.brand .karat{color:var(--gold)}
.updated{font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--ink-3)}

/* rate board hero - the shop-front board */
.board{background:linear-gradient(160deg,var(--board),var(--board-2));
  color:#EDE9DD;border-radius:14px;margin:30px 0;padding:38px 36px;
  position:relative;overflow:hidden}
.board::after{content:"999 · 916 · 750";position:absolute;right:24px;bottom:16px;
  font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.35em;
  color:var(--gold-bright);opacity:.45}
.board h1{font-size:clamp(26px,4.6vw,40px);color:#F6F1E3;margin-bottom:4px}
.board .sub{color:#B9C2B4;max-width:52ch;font-size:15px}
.board-rates{display:flex;gap:14px;flex-wrap:wrap;margin-top:26px}
.tile{border:1px solid rgba(217,178,74,.35);border-radius:10px;
  padding:14px 20px;min-width:150px;flex:1}
.tile .k{font-family:"IBM Plex Mono",monospace;font-size:11.5px;
  letter-spacing:.22em;color:var(--gold-bright);text-transform:uppercase}
.tile .v{font-family:"IBM Plex Mono",monospace;font-size:clamp(20px,3vw,27px);
  color:#F6F1E3;margin-top:4px}
.tile .u{font-size:12px;color:#8E9A8C}
.tile.best{background:rgba(217,178,74,.10)}
.tile.best .k{color:#F6F1E3}

.note{font-size:13px;color:var(--ink-3);margin:10px 0 26px}

/* stamps - hallmark badges */
.stamp{display:inline-block;font:500 10.5px/1 "IBM Plex Mono",monospace;
  letter-spacing:.08em;text-transform:uppercase;border-radius:4px;
  padding:3px 7px;margin-left:8px;vertical-align:2px}
.stamp-best{color:var(--gold);border:1px solid var(--gold)}
.stamp-est{color:var(--ink-3);border:1px solid var(--ink-3)}

/* comparison table */
h2{font-size:24px;margin:34px 0 6px}
.hint{font-size:13.5px;color:var(--ink-3);margin-bottom:14px}
.tablecard{background:var(--card);border:1px solid var(--line);
  border-radius:12px;overflow:auto}
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

/* ads */
.adslot{margin:30px 0;min-height:90px;border:1px dashed var(--line);
  border-radius:10px;display:flex;align-items:center;justify-content:center;
  color:var(--ink-3);font-size:12px;letter-spacing:.08em}

/* prose + faq */
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

<header class="top">
  <div class="brand">Gold<span class="karat">Rates</span></div>
  <div class="updated">Updated $date, $time</div>
</header>

<section class="board" aria-label="Today's gold rate summary">
  <h1>Gold Rate Today in India</h1>
  <p class="sub">Live 24K, 22K and 18K gold rates compared across $n_brands of
  India's top jewellery brands - collected daily from each brand's own
  published prices.</p>
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

<section aria-labelledby="cmp">
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

<section aria-labelledby="how">
  <h2 id="how">How These Rates Are Collected</h2>
  <div class="prose">
    <p>Every figure on this page comes from the jeweller's own published
    pricing: official daily rate pages where a brand publishes one, or the
    gold price breakup a brand prints on its product pages (gold value ÷ gold
    weight). Rates are collected automatically several times a day.</p>
    <p>Each brand's rate is normalised to a per-gram, pre-GST basis and
    cross-checked against the market median; anything that fails a purity
    sanity check (higher-karat gold can never cost less than lower-karat) is
    discarded rather than shown.</p>
  </div>
</section>

<div class="adslot" aria-hidden="true">advertisement</div>

<section aria-labelledby="faqh">
  <h2 id="faqh">Gold Rate FAQs</h2>
$faq
</section>

<footer>
  <p><strong>Disclaimer:</strong> Rates are indicative, derived from each
  brand's published prices, and can change during the day. Always confirm the
  billed rate with the jeweller before purchase. This site does not provide
  investment advice.</p>
  <p>© $year GoldRates - daily gold rate comparison for India. Data refreshed
  automatically; last build $iso_now.</p>
</footer>

</div>
<script>
(function(){
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
})();
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main()
