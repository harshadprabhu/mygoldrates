"""Pages other sites can use and link to (owner, 6 Nov 2026).

The site had no outside links (Bing, 6 Nov 2026), which is the main reason
search engines crawl it rarely. These give other sites a reason to link:

- a free gold-rate widget for blogs and jewellers (/gold-rate-widget). Its
  embed code carries a plain, visible credit link in the host's own HTML,
  named for the site rather than stuffed with keywords (Google treats
  keyword-rich widget links as spam);
- a badge for the jewellers whose rates we list (/jeweller-badge), linking
  to that jeweller's page here;
- a monthly report on how far jewellers' gold rates differ
  (/gold-price-gap-report), from our own daily readings, written to be cited
  by journalists.
"""
import html as _html
import json
import statistics
from datetime import date, timedelta

F22 = 22 / 24

# ------------------------------------------------------------------ widget
# The data the widget shows lives in /widget-data.json (rebuilt with the
# site, served with CORS); the script itself rarely changes.
WIDGET_JS = r"""(function(){
var B='https://mygoldrates.com';
function fmt(n){var s=Math.round(n).toString(),o=s.slice(-3),r=s.slice(0,-3);
while(r.length>2){o=r.slice(-2)+','+o;r=r.slice(0,-2);}return '\u20b9'+(r?r+','+o:o);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function draw(box,d){
  var dark=box.getAttribute('data-theme')==='dark';
  var credit=box.querySelector('a[href^="'+B+'"]');
  var c=d.chg22||0, cs=Math.abs(c)<1?'unchanged':(c>0?'\u25b2 '+fmt(c):'\u25bc '+fmt(-c));
  var cc=Math.abs(c)<1?(dark?'#bbb':'#666'):(c>0?'#1f9d55':'#d64545');
  var fg=dark?'#f3ead2':'#2a2112', bg=dark?'#16130d':'#fffaf0', bd=dark?'#3a3222':'#e8d9b0', mu=dark?'#b9ad8f':'#7a6a48';
  var rows=(d.top||[]).slice(0,box.getAttribute('data-rows')?+box.getAttribute('data-rows'):3).map(function(j){
    var td='padding:3px 0;border:0;background:none;color:'+fg+';font-size:13px';
    return '<tr><td style="'+td+'">'+esc(j.name)+'</td><td style="'+td+';text-align:right">'+fmt(j.r22)+'</td></tr>';}).join('');
  var w=document.createElement('div');
  w.setAttribute('style','font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:'+fg+';background:'+bg+';border:1px solid '+bd+';border-radius:12px;padding:14px 16px;max-width:340px;box-sizing:border-box');
  w.innerHTML='<div style="font-weight:700;font-size:15px;margin-bottom:6px">Gold rate today'+(d.place?' in '+esc(d.place):'')+'</div>'
   +'<div style="display:flex;gap:18px;margin-bottom:4px"><div><div style="font-size:11px;color:'+mu+'">24K / gram</div><div style="font-size:20px;font-weight:700">'+fmt(d.r24)+'</div></div>'
   +'<div><div style="font-size:11px;color:'+mu+'">22K / gram</div><div style="font-size:20px;font-weight:700">'+fmt(d.r22)+'</div></div></div>'
   +'<div style="font-size:12px;color:'+cc+';margin-bottom:8px">22K '+cs+' since yesterday</div>'
   +(rows?'<div style="font-size:11px;color:'+mu+';margin-bottom:2px">Lowest 22K today</div><table style="width:100%;border-collapse:collapse;font-size:13px">'+rows+'</table>':'')
   +'<div style="font-size:11px;color:'+mu+';margin-top:8px">'+esc(d.date)+' \u00b7 before 3% GST and making charges</div>';
  box.innerHTML='';box.appendChild(w);
  if(credit){credit.setAttribute('style','display:inline-block;margin-top:6px;font:12px system-ui,sans-serif;color:'+mu);box.appendChild(credit);}
}
function run(){
  var boxes=document.querySelectorAll('.mygoldrates-widget');
  if(!boxes.length)return;
  boxes.forEach(function(box){
    if(box.getAttribute('data-done'))return;box.setAttribute('data-done','1');
    var city=box.getAttribute('data-city')||'';
    fetch(B+'/widget-data.json',{mode:'cors'}).then(function(r){return r.json();}).then(function(all){
      var d=all.india, p=city&&all.places&&all.places[city];
      if(p){d=JSON.parse(JSON.stringify(d));d.place=p.name;d.top=p.top||d.top;}
      draw(box,d);
    }).catch(function(){});
  });
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();
})();
"""


def widget_data(*, display_date, r24, r22, chg22, national_rows, places):
    """national_rows: [(name, 24K)] cheapest first. places: {slug: {name,
    top}} for the cities that have a page (regional chains included)."""
    top = [{"name": n, "r22": round(v * F22)} for n, v in national_rows[:5]]
    return {"india": {"date": display_date, "r24": round(r24), "r22": round(r22),
                      "chg22": round(chg22), "top": top},
            "places": places}


def embed_code(site, city_slug="", city_name="", theme="light"):
    href = f"{site}/gold-rate-today-in-{city_slug}" if city_slug else f"{site}/"
    attrs = (f' data-city="{city_slug}"' if city_slug else "") + (' data-theme="dark"' if theme == "dark" else "")
    text = f"Gold rate in {city_name}: MyGoldRates" if city_slug else "Gold rates by MyGoldRates"
    return (f'<div class="mygoldrates-widget"{attrs}><a href="{href}">{text}</a></div>\n'
            f'<script src="{site}/widget.js" async></script>')


def widget_page_body(site, cities):
    """cities: [(slug, name)] with a page."""
    opts = "".join(f'<option value="{s}">{_html.escape(n)}</option>' for s, n in cities)
    code = _html.escape(embed_code(site))
    return (
        "<h1>Free Gold Rate Widget for Your Website</h1>"
        "<p>Show today's 24K and 22K gold rate, the change since yesterday and the jewellers with the "
        "lowest 22K rate on your blog or shop website. It updates itself every day from the rates we "
        "read from each jeweller's website. Free, no sign-up, no tracking, about 3 KB.</p>"
        '<div style="display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;margin:18px 0">'
        f'<div id="wprev">{embed_code(site).split(chr(10))[0]}</div>'
        '<div style="flex:1;min-width:260px">'
        '<label>City <select id="wcity"><option value="">All India</option>' + opts + "</select></label> "
        '<label>Style <select id="wtheme"><option value="light">Light</option>'
        '<option value="dark">Dark</option></select></label>'
        '<p style="margin:12px 0 6px">Copy this code and paste it where the widget should appear:</p>'
        f'<textarea id="wcode" readonly rows="5" style="width:100%;font:12px monospace">{code}</textarea>'
        '<button id="wcopy" type="button" style="margin-top:6px">Copy code</button>'
        "</div></div>"
        "<h2>What it shows</h2>"
        "<ul><li>Today's median 24K and 22K rate per gram, before GST</li>"
        "<li>The change in the 22K rate since yesterday</li>"
        "<li>The three jewellers with the lowest 22K rate today (for a city, including the regional "
        "chains that sell there)</li></ul>"
        "<h2>Terms</h2>"
        "<p>Free for any website. Please keep the credit link at the bottom of the widget. The rates "
        "are indicative: each jeweller's own rate, as published on its website, before 3% GST and "
        "making charges.</p>"
        f'<p>Want the raw numbers instead? <a href="{site}/rates.json">rates.json</a> is free to use with '
        f'a link to <a href="{site}/">MyGoldRates.com</a>.</p>')


WIDGET_PAGE_JS = """
(function(){
var S='__SITE__';
function code(){var c=document.getElementById('wcity'),t=document.getElementById('wtheme');
 var cs=c.value, cn=cs?c.options[c.selectedIndex].text:'';
 var href=S+'/'+(cs?['gold-rate-today','in',cs].join('-'):'');
 var txt=cs?'Gold rate in '+cn+': MyGoldRates':'Gold rates by MyGoldRates';
 // built as elements, not as markup text, so crawlers find no half-made address here
 var box=document.createElement('div');box.className='mygoldrates-widget';
 if(cs)box.setAttribute('data-city',cs);if(t.value==='dark')box.setAttribute('data-theme','dark');
 var a=document.createElement('a');a.setAttribute('href',href);a.textContent=txt;box.appendChild(a);
 document.getElementById('wcode').value=box.outerHTML+'\\n<script src="'+S+'/widget.js" async><\\/script>';
 var p=document.getElementById('wprev');p.innerHTML='';p.appendChild(box);
 var s=document.createElement('script');s.src=S+'/widget.js?'+Date.now();document.body.appendChild(s);}
document.getElementById('wcity').onchange=code;document.getElementById('wtheme').onchange=code;
document.getElementById('wcopy').onclick=function(){var t=document.getElementById('wcode');t.select();
 try{navigator.clipboard.writeText(t.value);}catch(e){document.execCommand('copy');}this.textContent='Copied';};
code();
})();
"""


# ------------------------------------------------------------------- badge
BADGE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="220" height="56" viewBox="0 0 220 56" role="img" aria-label="Gold rate listed daily on MyGoldRates">
<rect x="0.5" y="0.5" width="219" height="55" rx="10" fill="#16130d" stroke="#c9a23c"/>
<circle cx="28" cy="28" r="15" fill="#d4af37"/><path d="M20 33l5-7 4 4 7-10" fill="none" stroke="#16130d" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
<text x="52" y="24" font-family="Georgia,serif" font-size="15" font-weight="700" fill="#f3e3a6">Gold rate listed</text>
<text x="52" y="42" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="11.5" fill="#cbbf9f">daily on MyGoldRates.com</text>
</svg>
"""


def badge_code(site, page_slug, name):
    return (f'<a href="{site}/{page_slug}" title="{_html.escape(name)} gold rate today on MyGoldRates">'
            f'<img src="{site}/badge.svg" width="220" height="56" '
            f'alt="{_html.escape(name)} gold rate listed daily on MyGoldRates"></a>')


def badge_page_body(site, jewellers):
    """jewellers: [(name, page_slug)]."""
    rows = "".join(
        f"<h3>{_html.escape(n)}</h3>"
        f'<textarea readonly rows="3" style="width:100%;font:12px monospace">'
        f"{_html.escape(badge_code(site, ps, n))}</textarea>"
        for n, ps in sorted(jewellers))
    return (
        "<h1>Badge for Jewellers Listed on MyGoldRates</h1>"
        "<p>We read your gold rate from your website every morning and show it beside the other "
        "jewellers, so shoppers can see it is fair. If you would like to show that on your own "
        "website, add this badge. It links to your page here, where shoppers see your rate today "
        "and how it compares.</p>"
        f'<p><img src="{site}/badge.svg" width="220" height="56" alt="Gold rate listed daily on MyGoldRates"></p>'
        "<p>Find your name below, copy the code and paste it into your website's footer or "
        "\"about us\" page. Not listed yet? "
        f'<a href="{site}/list-your-jewellery">Ask us to add your store</a>.</p>' + rows)


# ---------------------------------------------------------- price gap report
def gap_report(hist_rows, regional_slugs, inr, today, days=30):
    """The month's report on how far jewellers' 22K rates differ, from our
    daily readings: hist_rows [{rate_date, canonical_24k_pre_gst,
    brands{slug,name}}]. Returns (title, desc, body, jsonld) or None."""
    cut = (today - timedelta(days=days)).isoformat()
    by_day, names = {}, {}
    for r in hist_rows:
        b = r.get("brands") or {}
        sl, v = b.get("slug"), r.get("canonical_24k_pre_gst")
        if not sl or not v or r["rate_date"] < cut or sl in regional_slugs:
            continue
        names[sl] = b.get("name") or sl
        by_day.setdefault(r["rate_date"], {})[sl] = float(v) * F22
    days_ok = {d: v for d, v in by_day.items() if len(v) >= 5}
    if len(days_ok) < 7:
        return None
    spreads = {d: max(v.values()) - min(v.values()) for d, v in days_ok.items()}
    med_spread = statistics.median(spreads.values())
    wide_d = max(spreads, key=spreads.get)
    stats = {}
    for d, v in days_ok.items():
        m = statistics.median(v.values())
        lo, hi = min(v, key=v.get), max(v, key=v.get)
        for sl, x in v.items():
            s = stats.setdefault(sl, {"diff": [], "low": 0, "high": 0, "n": 0})
            s["diff"].append(x - m); s["n"] += 1
            s["low"] += sl == lo; s["high"] += sl == hi
    n_days = len(days_ok)
    rows = sorted(((sl, statistics.mean(s["diff"]), s) for sl, s in stats.items()
                   if s["n"] >= max(5, n_days // 2)), key=lambda x: x[1])
    if len(rows) < 4:
        return None
    month = today.strftime("%B %Y")
    first, last = min(days_ok), max(days_ok)
    span = (f"{date.fromisoformat(first).strftime('%-d %b')} to "
            f"{date.fromisoformat(last).strftime('%-d %b %Y')}")
    cheap, dear = rows[0], rows[-1]
    gap_avg = dear[1] - cheap[1]
    e = _html.escape
    trs = "".join(
        f"<tr><td>{e(names[sl])}</td><td>{'+' if d >= 0 else '-'}{inr(abs(d))}</td>"
        f"<td>{'+' if d >= 0 else '-'}{inr(abs(d) * 10 * 1.03)}</td>"
        f"<td>{round(100 * s['low'] / s['n'])}%</td><td>{round(100 * s['high'] / s['n'])}%</td></tr>"
        for sl, d, s in rows)
    key = (f"Across {len(rows)} national jewellery chains from {span}, the gap between the cheapest "
           f"and the dearest 22K gold rate on the same day was typically {inr(med_spread)} per gram, "
           f"or {inr(med_spread * 10 * 1.03)} on 10 grams with GST - before any making charge.")
    title = f"Gold Price Gap Report, {month}: How Much Jewellers' Rates Differ"
    desc = (f"{month}: the same day's 22K gold rate differed by a typical {inr(med_spread)}/g "
            f"({inr(med_spread * 10 * 1.03)} on 10 g) between India's jewellery chains. "
            f"{names[cheap[0]]} was cheapest on average, {names[dear[0]]} dearest.")
    body = (
        f"<h1>{e(title)}</h1>"
        f'<p class="updated-on">{n_days} days of readings, {span}. Updated daily.</p>'
        f"<p><strong>{e(key)}</strong></p>"
        "<h2>Key findings</h2><ul>"
        f"<li>Typical same-day gap between the cheapest and dearest chain: <strong>{inr(med_spread)}"
        f"/g</strong> for 22K ({inr(med_spread * 10 * 1.03)} on 10 g with 3% GST).</li>"
        f"<li>Widest gap: <strong>{inr(spreads[wide_d])}/g</strong> on "
        f"{date.fromisoformat(wide_d).strftime('%-d %B')}.</li>"
        f"<li>Cheapest on average: <strong>{e(names[cheap[0]])}</strong>, {inr(abs(cheap[1]))}/g "
        f"below the day's median; lowest of all on {round(100 * cheap[2]['low'] / cheap[2]['n'])}% of days.</li>"
        f"<li>Dearest on average: <strong>{e(names[dear[0]])}</strong>, {inr(abs(dear[1]))}/g above "
        f"the median.</li>"
        f"<li>Between those two, 10 g of 22K gold cost about <strong>{inr(gap_avg * 10 * 1.03)}"
        f"</strong> more on an average day, with GST.</li></ul>"
        "<h2>Each chain against the day's median</h2>"
        '<div style="overflow-x:auto"><table><thead><tr><th>Jeweller</th><th>22K vs median, /g</th>'
        "<th>On 10 g with GST</th><th>Cheapest on</th><th>Dearest on</th></tr></thead>"
        f"<tbody>{trs}</tbody></table></div>"
        "<p>Cheapest on average first. \"Cheapest on\" and \"Dearest on\" are the share of days that "
        "chain had the lowest or the highest 22K rate of all of them.</p>"
        "<h2>How we measured it</h2>"
        "<p>Every morning we read each chain's own published gold rate from its website (national "
        "chains only here; regional chains sell in a few states and are compared on our city "
        "pages). Rates are per gram, before 3% GST and making charges. A day counts when at least "
        "five chains published a rate. Making charges, which differ far more than rates, are "
        'compared on <a href="https://mygoldrates.com/making-charges-comparison">making charges '
        "compared</a>.</p>"
        "<h2>Using these figures</h2>"
        "<p>Journalists and researchers are welcome to quote these figures. Please credit "
        '<a href="https://mygoldrates.com/gold-price-gap-report">MyGoldRates.com</a> with a link. '
        # email_off: Cloudflare would turn the address into a /cdn-cgi/ link
        # that answers 404 to crawlers
        'For a specific date range, a chain or a city, write to <!--email_off--><a href="mailto:contact@mygoldrates.com">'
        "contact@mygoldrates.com</a><!--/email_off-->; the daily figures are also in "
        '<a href="https://mygoldrates.com/rates.json">rates.json</a>.</p>')
    ld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "Dataset",
        "name": title, "description": desc,
        "url": "https://mygoldrates.com/gold-price-gap-report",
        "temporalCoverage": f"{first}/{last}", "spatialCoverage": {"@type": "Place", "name": "India"},
        "variableMeasured": ["22K gold rate per gram by jeweller", "same-day spread between jewellers"],
        "isAccessibleForFree": True,
        "creator": {"@type": "Organization", "name": "MyGoldRates.com", "url": "https://mygoldrates.com"},
        "license": "https://mygoldrates.com/terms"}) + "</script>")
    return title, desc, body, ld
