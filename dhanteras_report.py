"""Dhanteras 2026 gold report: what the same jewellery costs at each jeweller.

A page written to be cited. Journalists covering Dhanteras (Friday,
6 November 2026) need a fresh, checkable number, and this site holds one few
others do: making charges measured from each jeweller's own product listings,
joined to the gold rate each jeweller publishes the same day. The page is
regenerated with every build, so the figures stay current up to the festival,
and it ships the full table as CSV so anyone quoting it can check the sums.

Everything here is computed from two inputs and nothing else:

  * ``dash``  - {jeweller: {"rates": {"22": rate per gram, ...},
                            "mc": {category: {"pct", "n", "conf"}}}}
                the same join the making-charges calculator uses, so the two
                pages can never disagree;
  * ``hist``  - [(date, national median 24K per gram)], oldest first.

Low-confidence making-charge figures (fewer than a handful of products) are
excluded rather than shown with a caveat: a reporter quoting a headline number
will not quote the caveat.
"""
import csv
import html
import io
import json
from datetime import date

SLUG = "dhanteras-gold-report-2026"
DHANTERAS = date(2026, 11, 6)
GRAMS = 10            # every price is for 10 g of 22K, so items compare
GST = 0.03
KARAT_22 = 22 / 24    # 916 fineness as a fraction of 24K (the site's ladder)
CONF_OK = {"high", "medium"}
BAR = "#C9982F"       # one series, one hue (.rb-b in STYLE); >= 3:1 on the dark surface
# How each category reads in a sentence: "a 22K pair of earrings weighing 10 g".
ITEM = {"Earrings": "pair of earrings", "Ring": "ring", "Bangle": "bangle",
        "Mangalsutra": "mangalsutra", "Chain": "chain", "Necklace": "necklace",
        "Pendant": "pendant"}


def item(cat):
    return f"22K {ITEM.get(cat, cat.lower())} weighing 10 g"


def bill(rate22, pct):
    """Gold value, making charge, GST and total for GRAMS of 22K."""
    gold = rate22 * GRAMS
    making = gold * pct / 100
    gst = (gold + making) * GST
    return {"gold": gold, "making": making, "gst": gst,
            "total": gold + making + gst}


def compute(dash):
    """Per category: priced rows cheapest first, plus the spread."""
    cats = {}
    for name, b in dash.items():
        r22 = (b.get("rates") or {}).get("22")
        if not r22:
            continue
        for cat, m in (b.get("mc") or {}).items():
            if m.get("conf") not in CONF_OK:
                continue
            row = {"jeweller": name, "category": cat, "rate22": r22,
                   "pct": m["pct"], "n": m.get("n", 0), "conf": m["conf"]}
            row.update(bill(r22, m["pct"]))
            cats.setdefault(cat, []).append(row)
    out = {}
    for cat, rows in cats.items():
        if len(rows) < 3:          # a "spread" of two shops is not a finding
            continue
        rows.sort(key=lambda r: r["total"])
        lo, hi = rows[0], rows[-1]
        out[cat] = {"rows": rows, "cheapest": lo, "dearest": hi,
                    "gap": hi["total"] - lo["total"],
                    "gap_pct": (hi["total"] / lo["total"] - 1) * 100}
    return out


def rate_gap(cats):
    """How far apart the jewellers' own 22K rates are, per 10 g."""
    rates = {r["jeweller"]: r["rate22"] for c in cats.values() for r in c["rows"]}
    if len(rates) < 2:
        return 0.0, None, None
    lo = min(rates, key=rates.get)
    hi = max(rates, key=rates.get)
    return (rates[hi] - rates[lo]) * GRAMS, lo, hi


def price_move(hist, days=None):
    """(from_date, from_22K, to_22K, % change) over the history or last N days."""
    if len(hist) < 2:
        return None
    to_d, to_24 = hist[-1]
    if days is None:
        fr_d, fr_24 = hist[0]
    else:
        cands = [h for h in hist if (to_d - h[0]).days >= days]
        if not cands:
            return None
        fr_d, fr_24 = cands[-1]
    return (fr_d, fr_24 * KARAT_22, to_24 * KARAT_22, (to_24 / fr_24 - 1) * 100)


def findings(cats, hist, inr):
    """The quotable sentences, each computed, none hand-written."""
    out = []
    if not cats:
        return out
    widest = max(cats.items(), key=lambda kv: kv[1]["gap"])
    cat, c = widest
    out.append(
        f"A {item(cat)} costs {inr(round(c['cheapest']['total']))} at "
        f"{c['cheapest']['jeweller']} and {inr(round(c['dearest']['total']))} at "
        f"{c['dearest']['jeweller']} once making charges and 3% GST are added - "
        f"a difference of {inr(round(c['gap']))} ({c['gap_pct']:.0f}%).")
    rg, rlo, rhi = rate_gap(cats)
    if rlo and rg > 0:
        out.append(
            f"The gold rate itself barely differs: {rlo} and {rhi}, the lowest and "
            f"highest 22K rates among these jewellers, are {inr(round(rg))} apart per "
            f"10 g, while the bill for the same {item(cat)} differs by "
            f"{inr(round(c['gap']))}. Making charges, not the rate, decide the price.")
    for cat, c in sorted(cats.items()):
        lowest_rate = min(c["rows"], key=lambda r: r["rate22"])
        if lowest_rate["jeweller"] != c["cheapest"]["jeweller"]:
            out.append(
                f"The lowest gold rate does not buy the cheapest jewellery: "
                f"{lowest_rate['jeweller']} has the lowest 22K rate of these jewellers, "
                f"but {c['cheapest']['jeweller']} works out cheapest for a "
                f"{item(cat)}.")
            break
    pcts = [r["pct"] for c in cats.values() for r in c["rows"]]
    out.append(f"Making charges run from {min(pcts):.0f}% to {max(pcts):.0f}% of the gold "
               "value across the jewellers and items in this report.")
    since = price_move(hist)
    month = price_move(hist, 30)
    if since:
        s = (f"The 22K market median has moved from {inr(round(since[1]))}/g on "
             f"{since[0]:%-d %B} to {inr(round(since[2]))}/g today "
             f"({since[3]:+.1f}%)")
        if month:
            s += f", {month[3]:+.1f}% over the last 30 days"
        out.append(s + ".")
    return out


def chart_html(cat, c, inr):
    """Ranked horizontal bars, one hue, cheapest tagged in text not colour.

    Plain HTML rather than SVG so the labels stay at body size on a phone
    instead of shrinking with a scaled viewBox."""
    rows = c["rows"]
    vmax = max(r["total"] for r in rows)
    vmin = min(r["total"] for r in rows)
    # Bars start from a floor below the cheapest so the differences - the
    # point of the chart - are visible; the floor is stated under the chart.
    floor = vmin * 0.9
    out = [f'<div class="rep-bars" role="img" aria-label="All-in price of '
           f'{html.escape(item(cat))} at each jeweller, cheapest first">']
    for i, r in enumerate(rows):
        pct = max(3.0, (r["total"] - floor) / (vmax - floor) * 100)
        name = html.escape(r["jeweller"])
        tip = (f'{name}: {inr(round(r["total"]))} - gold {inr(round(r["gold"]))}, '
               f'making {r["pct"]:.1f}% {inr(round(r["making"]))}, '
               f'GST {inr(round(r["gst"]))}')
        out.append(
            f'<div class="rb{" rb-lo" if i == 0 else ""}" title="{tip}">'
            f'<span class="rb-n">{name}</span><span class="rb-t">'
            f'<span class="rb-b" style="width:{pct * 0.62:.1f}%"></span>'
            f'<span class="rb-v">{html.escape(inr(round(r["total"])))}'
            f'{" (lowest)" if i == 0 else ""}</span></span></div>')
    out.append(f'<p class="rb-note">Bars start at {html.escape(inr(round(floor)))}, '
               'not zero, so the gaps are visible.</p></div>')
    return "".join(out)


def table_html(c, inr):
    trs = "".join(
        f'<tr><td>{html.escape(r["jeweller"])}{" <em>(lowest)</em>" if i == 0 else ""}</td>'
        f'<td>{inr(round(r["rate22"]))}</td><td>{r["pct"]:.1f}%'
        f'{" *" if r["conf"] == "medium" else ""}</td><td>{r["n"]}</td>'
        f'<td>{inr(round(r["making"]))}</td><td>{inr(round(r["gst"]))}</td>'
        f'<td><strong>{inr(round(r["total"]))}</strong></td></tr>'
        for i, r in enumerate(c["rows"]))
    return ('<div class="rep-tbl"><table><thead><tr><th>Jeweller</th><th>22K rate /g</th>'
            '<th>Making</th><th>Products</th><th>Making &#8377;</th><th>GST</th>'
            f'<th>Total, 10 g</th></tr></thead><tbody>{trs}</tbody></table></div>')


def to_csv(cats, rates_date, mc_date):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["category", "jeweller", "rate_22k_per_g_pre_gst", "making_pct_median",
                "products_sampled", "confidence", "gold_value_10g", "making_10g",
                "gst_10g", "total_10g", "rates_as_of", "making_data_as_of"])
    for cat in sorted(cats):
        for r in cats[cat]["rows"]:
            w.writerow([cat, r["jeweller"], round(r["rate22"], 2), r["pct"], r["n"],
                        r["conf"], round(r["gold"]), round(r["making"]),
                        round(r["gst"]), round(r["total"]), rates_date, mc_date])
    return buf.getvalue()


STYLE = """<style>
.rep-key{border:1px solid rgba(212,166,60,.28);border-radius:14px;padding:16px 18px;
  background:rgba(212,166,60,.06);margin:16px 0}
.rep-key li{margin:8px 0;line-height:1.6}
.rep-fig{margin:18px 0 8px;padding:14px 12px 8px;border:1px solid rgba(200,160,60,.16);
  border-radius:14px;background:rgba(255,255,255,.02)}
.rb{display:grid;grid-template-columns:minmax(92px,34%) 1fr;gap:10px;
  align-items:center;margin:7px 0;font-size:13.5px}
.rb-n{color:#C8BDA8;text-align:right;line-height:1.25}
.rb-t{display:flex;align-items:center;gap:8px;min-width:0}
.rb-b{display:block;height:16px;background:#C9982F;border-radius:0 4px 4px 0;
  flex:none}
.rb-v{color:#F4EDE0;white-space:nowrap;font-variant-numeric:tabular-nums}
.rb-lo .rb-v{font-weight:700}
.rb-note{margin:10px 0 2px;font-size:12px;color:#9B907B}
.rep-tbl{overflow-x:auto;margin:6px 0 18px}
.rep-tbl table{width:100%;border-collapse:collapse;font-size:13.5px}
.rep-tbl th,.rep-tbl td{padding:8px 8px;text-align:right;white-space:nowrap;
  border-bottom:1px solid rgba(200,160,60,.14)}
.rep-tbl th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#9B907B}
.rep-tbl th:first-child,.rep-tbl td:first-child{text-align:left}
.rep-cite{border-left:3px solid #D4A63C;padding:10px 14px;margin:14px 0;
  background:rgba(255,255,255,.03);font-size:14px}
.rep-cite code{white-space:normal;word-break:break-word}
</style>"""


def build(dash, hist, mc_date, rates_date, display_date, site_url, inr, today=None):
    """Return (title, description, body_html, jsonld_block, csv_text)."""
    cats = compute(dash)
    facts = findings(cats, hist, inr)
    today = today or date.today()
    days_left = (DHANTERAS - today).days
    url = f"{site_url}/{SLUG}"
    csv_name = f"{SLUG}.csv"
    when = (f"Dhanteras falls on Friday, 6 November 2026 - {days_left} days from "
            f"today." if days_left > 0 else
            "Dhanteras fell on Friday, 6 November 2026.")
    title = ("Dhanteras 2026 Gold Report: What the Same Jewellery Costs at Each "
             "Jeweller | MyGoldRates")
    desc = (facts[0] if facts else
            "Making charges, gold rate and GST compared across jewellers for "
            "Dhanteras 2026.")[:300]

    sections = []
    for cat in sorted(cats, key=lambda k: -cats[k]["gap"]):
        c = cats[cat]
        sections.append(
            f'<h2>{html.escape(cat)}: 10 g of 22K, all-in</h2>'
            f'<p>Cheapest <strong>{html.escape(c["cheapest"]["jeweller"])}</strong> at '
            f'{inr(round(c["cheapest"]["total"]))}; dearest '
            f'{html.escape(c["dearest"]["jeweller"])} at {inr(round(c["dearest"]["total"]))}'
            f' - {inr(round(c["gap"]))} apart.</p>'
            f'<figure class="rep-fig">{chart_html(cat, c, inr)}</figure>'
            + table_html(c, inr))
    excluded = sorted({f'{n} ({cat.lower()})' for n, b in dash.items()
                       for cat, m in (b.get("mc") or {}).items()
                       if m.get("conf") not in CONF_OK})

    body = (
        STYLE +
        f'<p class="crumbs"><a href="{site_url}/">Home</a> &rsaquo; '
        f'<a href="{site_url}/news">News</a> &rsaquo; Dhanteras 2026 report</p>'
        '<h1>Dhanteras 2026: what the same gold jewellery costs at each jeweller</h1>'
        f'<p class="updated-on">Gold rates as of {html.escape(display_date)} &middot; '
        f'making charges measured {html.escape(mc_date)}</p>'
        f'<p>{when} It is the busiest day of the year for gold buying, and most '
        'buyers compare one number before they go: the gold rate. This report '
        'compares the number that decides the bill. Every price below is for '
        '<strong>10 grams of 22K gold</strong> - gold value at the jeweller&rsquo;s '
        'own published rate, plus its making charge, plus 3% GST.</p>'
        '<div class="rep-key"><strong>Key findings</strong><ul>'
        + "".join(f"<li>{html.escape(f)}</li>" for f in facts) +
        '</ul></div>'
        + "".join(sections) +
        '<h2>How these numbers are made</h2>'
        '<p><strong>Gold rate:</strong> each jeweller&rsquo;s own published 22K rate '
        f'per gram, pre-GST, on {html.escape(rates_date)}. '
        '<strong>Making charge:</strong> the median making charge, as a percentage of '
        'gold value, across real products in that category on the jeweller&rsquo;s '
        'own website, read from each product&rsquo;s published price breakup. The '
        '<em>Products</em> column is how many were measured; figures marked * rest on '
        'a smaller sample. <strong>Total</strong> = gold value + making charge + 3% GST '
        'on both.</p>'
        + (f'<p>Left out because too few products could be measured to give a '
           f'reliable median: {html.escape(", ".join(excluded))}.</p>' if excluded else '')
        + '<p>Making charges vary by design, and in-store offers and exchange terms '
          'are not included, so treat these as like-for-like indications rather than '
          'quotes. This is not investment advice.</p>'
          '<h2>Use this data</h2>'
          f'<p><a href="{site_url}/{csv_name}" download>Download the full table (CSV)</a> '
          '&mdash; every jeweller, every category, with the sample sizes.</p>'
          '<div class="rep-cite">Suggested citation:<br><code>Source: MyGoldRates.com '
          f'Dhanteras 2026 gold report ({html.escape(display_date)}), {url}</code></div>'
          f'<p>Journalists and researchers: for the underlying product data or a '
          f'comment, <a href="{site_url}/contact">get in touch</a>. Today&rsquo;s rates '
          f'for every jeweller are on the <a href="{site_url}/">live board</a>, and you '
          f'can price any item yourself with the <a href="{site_url}/making-charges-'
          'comparison">making charge calculator</a>.</p>')

    ld = [{
        "@context": "https://schema.org", "@type": "Article",
        "headline": "Dhanteras 2026: what the same gold jewellery costs at each jeweller",
        "description": desc, "url": url, "mainEntityOfPage": url,
        "datePublished": "2026-10-14", "dateModified": today.isoformat(),
        "author": {"@type": "Organization", "name": "MyGoldRates.com", "url": site_url},
        "publisher": {"@type": "Organization", "name": "MyGoldRates.com",
                      "logo": {"@type": "ImageObject", "url": f"{site_url}/icon-512.png"}},
        "inLanguage": "en-IN"}, {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "Gold jewellery all-in prices by jeweller, Dhanteras 2026",
        "description": "Gold rate, median making charge and GST for 10 g of 22K "
                       "jewellery by category, per jeweller.",
        "url": url, "creator": {"@type": "Organization", "name": "MyGoldRates.com"},
        "license": f"{site_url}/terms", "isAccessibleForFree": True,
        "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv",
                          "contentUrl": f"{site_url}/{csv_name}"}]}]
    jsonld = ('<script type="application/ld+json">'
              + json.dumps(ld, ensure_ascii=False) + "</script>")
    return title, desc, body, jsonld, to_csv(cats, rates_date, mc_date)
