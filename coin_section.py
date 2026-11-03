"""24K gold coin prices by jeweller (owner, 3 Nov 2026).

What a 24K coin really costs at each jeweller: the jeweller's own 24K rate
today, plus the making charge measured on its own 24K coins
(collect_charges.py, category "Coin"), plus 3% GST on both.

Only jewellers with coin readings are shown. A coin's making charge is a few
percent, nothing like jewellery's 15-60%, so a jeweller's jewellery making
charge is never used to price a coin.
"""
import html as _html

GST = 0.03
WEIGHTS = (1, 5, 10)


def coin_rows(mc, rate24):
    """[{brand, pct, n, per_g, prices{g: rupees}, premium}] cheapest first.

    mc: the making-charges payload; rate24: {brand name: 24K pre-GST per gram}.
    per_g is the all-in price of one gram in a coin (making and GST included);
    premium is how far that sits above the jeweller's own 24K rate.
    """
    rows = []
    for b in (mc or {}).get("brands") or []:
        c = next((x for x in b.get("categories") or [] if x.get("category") == "Coin"), None)
        r = rate24.get(b.get("brand"))
        if not c or c.get("making_pct_median") is None or not r:
            continue
        pct = float(c["making_pct_median"])
        per_g = r * (1 + pct / 100) * (1 + GST)
        rows.append({"brand": b["brand"], "pct": pct, "n": c.get("items", 0),
                     "from_price": c.get("source") == "price",
                     "rate": r, "per_g": per_g,
                     "prices": {g: round(per_g * g) for g in WEIGHTS},
                     "premium": per_g / r - 1})
    return sorted(rows, key=lambda x: x["per_g"])


def _inr(v):
    s = f"{int(round(v)):d}"
    if len(s) > 3:                       # Indian grouping: 1,23,456
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return "₹" + s


def coin_html(rows, updated, site):
    """The page body: the table, how it is worked out, and questions."""
    if not rows:
        return ""
    e = _html.escape
    best = rows[0]
    trs = "".join(
        f"<tr><td>{e(r['brand'])}</td><td>{r['pct']:.1f}%{' *' if r.get('from_price') else ''}</td>"
        + "".join(f"<td>{_inr(r['prices'][g])}</td>" for g in WEIGHTS)
        + f"<td>{_inr(r['per_g'])}</td></tr>" for r in rows)
    return (
        '<section class="site-section"><div class="site-container">'
        f"<h2>24K gold coin price by jeweller</h2>"
        "<p>What a 24K (999) gold coin costs at each jeweller today: its own 24K rate, plus the making "
        "charge measured on its own 24K coins, plus 3% GST. Coin making charges are a few percent, far "
        f"below jewellery's. Making charges measured {e(updated[:10])}; rates are today's.</p>"
        '<div class="tbl-wrap"><table class="jt"><tr><th>Jeweller</th><th>Making on coins</th>'
        + "".join(f"<th>{g} g coin</th>" for g in WEIGHTS)
        + "<th>Per gram, all-in</th></tr>" + trs + "</table></div>"
        + ("<p>* Worked out from the coin's listed price and the jeweller's 24K rate (the page shows "
           "no breakup); being watched day by day.</p>" if any(r.get("from_price") for r in rows) else "")
        + f"<p><b>Lowest today:</b> {e(best['brand'])}, {_inr(best['prices'][10])} for a 10 g coin "
        f"({best['pct']:.1f}% making, GST included).</p>"
        "<h2>How the coin price is worked out</h2>"
        "<p>Coin price = weight &times; the jeweller's 24K rate &times; (1 + making %) &times; 1.03 (GST). "
        "The making % is the median over the 24K coins listed on the jeweller's own website. Coin designs "
        "and packaging vary, so confirm the final price with the jeweller.</p>"
        "<h2>Questions</h2>"
        "<h3>Is there a making charge on gold coins?</h3><p>Usually a small one: "
        + "; ".join(f"{e(r['brand'])} {r['pct']:.1f}%" for r in rows[:5])
        + " on 24K coins today, from the table above.</p>"
        "<h3>Is GST charged on gold coins?</h3><p>Yes, 3% on the gold and the making charge together.</p>"
        f'<h3>Where can I compare the 24K rate itself?</h3><p>On the <a href="{site}/">homepage</a>, '
        "every jeweller's rate today, cheapest first.</p>"
        "</div></section>")


def coin_faq(rows):
    if not rows:
        return []
    return [
        ("Is there a making charge on gold coins?",
         "Usually a small one: " + "; ".join(f"{r['brand']} {r['pct']:.1f}%" for r in rows[:5])
         + " on 24K coins today."),
        ("Is GST charged on gold coins?", "Yes, 3% on the gold and the making charge together."),
    ]
