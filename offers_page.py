"""The /gold-offers-today page: every jeweller's published offers, what each
one is really worth, and a like-for-like price after offers.

Pure functions over docs/offers.json (offers.py), docs/making-charges.json
and today's per-jeweller rates, so the page is tested without a build.

The arithmetic is the point of the page. "20% off making charges" means
nothing on its own: on an 18% making charge it leaves 14.4%, which can still
cost more than another jeweller's 12% with no offer at all. So for the
jewellers whose making charges we have, the page prices the same piece - a
10 g 22K ring - before and after each offer, with 3% GST, and ranks them.
"Up to" and selected-design offers are shown as a best case, never folded
into the ranking as if every design got them. Nothing here judges designs.
"""
from __future__ import annotations

import html
import re

GST = 0.03
PIECE_G = 10.0                       # a 10 g 22K ring, the like-for-like piece
PURITY_22 = 0.916

KIND_LABEL = {
    "making_off": "off making charges",
    "making_zero": "Zero making charges",
    "diamond_off": "off diamond / stone value",
    "all_off": "off the price",
    "exchange": "Old-gold exchange",
    "free_coin": "Free coin",
    "rate_protect": "Rate protection / advance booking",
    "scheme": "Monthly savings plan",
    "cashback": "Bank / card offer",
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def inr(v):
    v = int(round(v))
    s = str(abs(v))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join(re.findall(r"\d{1,2}(?=(?:\d{2})*$)", head))
        s = head + "," + tail
    return ("-" if v < 0 else "") + "₹" + s


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _host(u):
    m = re.match(r"https?://(?:www\.)?([^/]+)", u or "")
    return m.group(1).lower() if m else ""


def making_for(mc, name, domain=""):
    """Usual making charge (% of gold value) for a ring at this jeweller,
    falling back to the median of its categories. None if not collected.
    Matched by website where known: "PN Gadgil" and "PN Gadgil & Sons" are
    different companies with similar names."""
    dom = _host("https://" + domain) if domain else ""
    for b in (mc or {}).get("brands", []):
        ex = [e.get("url") for c in b.get("categories", []) for e in c.get("examples", [])]
        same_site = dom and any(_host(u) == dom for u in ex)
        if same_site or (not dom and _norm(b.get("brand")) == _norm(name)):
            cats = {c["category"]: c["making_pct_median"] for c in b.get("categories", [])
                    if c.get("making_pct_median") is not None}
            if not cats:
                return None
            if "Ring" in cats:
                return cats["Ring"]
            v = sorted(cats.values())
            return v[len(v) // 2]
    return None


def headline(o):
    """Short label: "Up to 20% off making charges"."""
    k = o["kind"]
    lo, hi = o.get("pct_min"), o.get("pct_max")
    if k in ("making_off", "diamond_off", "all_off") and hi:
        if o.get("upto"):
            return f"Up to {hi:g}% {KIND_LABEL[k]}"
        if lo and lo != hi:
            return f"{lo:g}–{hi:g}% {KIND_LABEL[k]} on selected designs"
        return f"{hi:g}% {KIND_LABEL[k]}"
    if k == "cashback" and hi:
        return f"{hi:g}% {KIND_LABEL[k].lower()}"
    return KIND_LABEL.get(k, k)


def _gold_jewellery_applies(o):
    tags = o.get("applies_to") or []
    return "diamond jewellery only" not in tags


def flat_making_offer(o):
    """A making-charge discount that applies across gold jewellery, so it can
    go into the ranking: not "up to", not selected designs, not diamond-only."""
    return (o["kind"] == "making_off" and o.get("pct_max") and not o.get("upto")
            and not o.get("selected") and _gold_jewellery_applies(o)
            and (o.get("pct_min") == o.get("pct_max")))


def ring_prices(offers_data, mc, rate22_by_slug):
    """Like-for-like 10 g 22K ring, before and after offers. Rows only for
    jewellers with both a making charge and today's 22K rate."""
    rows = []
    for b in offers_data.get("brands", []):
        m = making_for(mc, b["name"], b.get("domain", ""))
        r22 = rate22_by_slug.get(b["slug"])
        if m is None or not r22:
            continue
        gold = PIECE_G * r22
        before = (gold + gold * m / 100) * (1 + GST)
        flat = [o for o in b.get("offers", []) if flat_making_offer(o)]
        best_flat = max((o["pct_max"] for o in flat), default=0)
        after = (gold + gold * m / 100 * (1 - best_flat / 100)) * (1 + GST)
        bestcase = [o for o in b.get("offers", []) if o["kind"] == "making_off"
                    and o.get("pct_max") and _gold_jewellery_applies(o)]
        bc_pct = max((o["pct_max"] for o in bestcase), default=0)
        best_case = ((gold + gold * m / 100 * (1 - bc_pct / 100)) * (1 + GST)
                     if bc_pct > best_flat else None)
        rows.append({"slug": b["slug"], "name": b["name"], "rate22": r22,
                     "making": m, "flat_pct": best_flat, "before": before,
                     "after": after, "best_case": best_case, "best_case_pct": bc_pct,
                     "online_only": any("online purchases only" in (o.get("applies_to") or [])
                                        for o in flat)})
    rows.sort(key=lambda r: r["after"])
    return rows


def meaning(o, name, mc_pct, rate24):
    """What the offer is really worth, in plain words, from its own terms."""
    k, tags = o["kind"], o.get("applies_to") or []
    hi = o.get("pct_max")
    parts = []
    if k == "making_off":
        parts.append("A discount on the making charge only &mdash; the gold itself is still "
                     "charged at the day&rsquo;s rate.")
        if o.get("upto") or o.get("selected"):
            parts.append("&ldquo;Up to&rdquo; and selected-design offers give the full discount on "
                         "some pieces only; ask what applies to the one you want.")
        if mc_pct and hi and _gold_jewellery_applies(o):
            left = mc_pct * (1 - hi / 100)
            parts.append(f"{esc(name)}&rsquo;s making charge on rings is usually about "
                         f"{mc_pct:g}%; " + (
                             "on the designs it covers, there is no making charge at all."
                             if hi >= 100 else f"{hi:g}% off brings it to about {left:.1f}%."))
        if "diamond jewellery only" in tags:
            parts.append("This one is for diamond jewellery; plain gold jewellery is not included.")
        if "online purchases only" in tags:
            parts.append("Online orders only &mdash; not in the showroom.")
    elif k == "making_zero":
        parts.append("Usually limited to selected designs, coins or a single collection. "
                     "Check the piece is included, and compare its gold rate &mdash; a zero "
                     "making charge can come with a higher rate per gram.")
    elif k == "diamond_off":
        parts.append("Applies to the diamond or stone value only. No saving at all on plain "
                     "gold jewellery.")
    elif k == "all_off":
        parts.append("Check whether it applies to the gold value too &mdash; most discounts "
                     "exclude it and apply to making or stones only.")
    elif k == "exchange":
        parts.append("No deduction on old gold: you get its full value at today&rsquo;s rate "
                     "after a purity test.")
        if "only jewellery bought from them" in tags:
            parts.append("Only for jewellery originally bought from them.")
        else:
            parts.append("Ask whether it also covers jewellery from other shops &mdash; often "
                         "it does not.")
    elif k == "free_coin":
        mp = o.get("min_purchase")
        parts.append("Comes with a minimum purchase" + (f" of {inr(mp)}" if mp else "") +
                     ". Ask the coin&rsquo;s weight and purity.")
        if rate24:
            parts.append(f"For scale, a 0.5 g 24K coin is worth about {inr(0.5 * rate24)} "
                         "at today&rsquo;s rate.")
    elif k == "rate_protect":
        parts.append("Fixes the rate for a period when you book with an advance &mdash; useful if "
                     "gold rises before you buy. Check the advance needed, the booking period, "
                     "and whether you get the lower rate if gold falls instead.")
    elif k == "scheme":
        parts.append("A monthly savings plan: instalments now, jewellery at the end, often with "
                     "one instalment or part of the making charge waived. The money is locked "
                     "in for the plan period and usually redeemable only as jewellery from them.")
    elif k == "cashback":
        parts.append("Needs that bank&rsquo;s card and is usually capped; read the maximum.")
    return " ".join(parts)


def build_body(offers_data, mc, rate22_by_slug, rate24, display_date, site_url, crumbs_html):
    """The page body, a FAQ list for structured data, and a one-line summary
    (for the daily email). offers_data is docs/offers.json."""
    brands = offers_data.get("brands", [])
    with_offers = [b for b in brands if b.get("offers")]
    rows = ring_prices(offers_data, mc, rate22_by_slug)
    mc_by = {b["slug"]: making_for(mc, b["name"], b.get("domain", "")) for b in brands}

    out = [crumbs_html, "<h1>Gold Jewellery Offers Today</h1>",
           f'<p class="updated-on">Offers as published on each jeweller&rsquo;s own website, '
           f'read on {esc(display_date)}</p>',
           f"<p>{len(with_offers)} of {len(brands)} jewellers we track have offers on their "
           "websites today. Below: what each offer really means, the fine print we found "
           "next to it, and what the same 10&nbsp;g 22K ring costs after the offers that "
           "apply to it.</p>"]

    # ---- like-for-like ranking
    summary = ""
    if rows:
        out.append("<h2>What a 10 g 22K ring costs today, after offers</h2>")
        out.append("<p>Gold at each jeweller&rsquo;s own 22K rate, plus its usual making "
                   "charge on rings, minus any making-charge offer that applies to all gold "
                   "jewellery, plus 3% GST. &ldquo;Best case&rdquo; is the price if a "
                   "selected-design or &ldquo;up to&rdquo; discount applies in full.</p>")
        out.append('<div class="lb-wrap"><table class="local-tbl"><thead><tr><th>#</th>'
                   "<th>Jeweller</th><th>Making (usual)</th><th>Offer on making</th>"
                   "<th>Price today</th><th>Best case</th></tr></thead><tbody>")
        for i, r in enumerate(rows, 1):
            offer = (f"{r['flat_pct']:g}% off" + (" (online)" if r["online_only"] else "")
                     if r["flat_pct"] else "&ndash;")
            bc = (f"{inr(r['best_case'])} <small>({r['best_case_pct']:g}% off, some designs)</small>"
                  if r["best_case"] else "&ndash;")
            price = inr(r["after"]) + (f' <small><s>{inr(r["before"])}</s></small>'
                                       if r["flat_pct"] else "")
            out.append(f"<tr><td>{i}</td><td>{esc(r['name'])}</td><td>{r['making']:g}%</td>"
                       f"<td>{offer}</td><td><strong>{price}</strong></td><td>{bc}</td></tr>")
        out.append("</tbody></table></div>")
        low = rows[0]
        summary = (f"Lowest for a 10 g 22K ring today: {low['name']}, {inr(low['after'])} "
                   "with GST")
        out.append(f"<p><strong>{esc(summary)}</strong>"
                   + (f", before making-charge offers {inr(low['before'])}" if low["flat_pct"] else "")
                   + ". Making charges are medians across real products and vary by design "
                   f'&mdash; see the <a href="{site_url}/making-charges-comparison">making '
                   "charges comparison</a>.</p>")

    # ---- quick take
    def names(kind, pred=lambda o: True):
        return [b["name"] for b in with_offers
                if any(o["kind"] == kind and pred(o) for o in b["offers"])]
    take = []
    mk = [(b["name"], o) for b in with_offers for o in b["offers"]
          if o["kind"] == "making_off" and o.get("pct_max") and _gold_jewellery_applies(o)]
    if mk:
        mk.sort(key=lambda x: -x[1]["pct_max"])
        take.append("Biggest making-charge discounts: " + ", ".join(
            f"{esc(n)} ({esc(headline(o).replace(' off making charges', ''))})" for n, o in mk[:4]) + ".")
    ex = names("exchange")
    if ex:
        take.append("No deduction on old-gold exchange: " + ", ".join(map(esc, ex)) + ".")
    fc = names("free_coin")
    if fc:
        take.append("Free coin with a purchase: " + ", ".join(map(esc, fc)) + ".")
    dm = names("diamond_off")
    if dm:
        take.append("Diamond / stone discounts (no saving on plain gold): " + ", ".join(map(esc, dm)) + ".")
    if take:
        out.append("<h2>Today at a glance</h2><ul>" + "".join(f"<li>{t}</li>" for t in take) + "</ul>")

    # ---- each jeweller
    out.append("<h2>Every offer, jeweller by jeweller</h2>")
    for b in with_offers:
        out.append(f'<section class="offer-brand"><h3>{esc(b["name"])}</h3>')
        for o in b["offers"]:
            tags = o.get("applies_to") or []
            seen = (f" &middot; first seen {esc(o['first_seen'])}" if o.get("first_seen") else "")
            out.append(
                '<div class="offer">'
                f'<p class="offer-h"><strong>{esc(headline(o))}</strong>'
                + (" &middot; " + ", ".join(esc(t) for t in tags) if tags else "") + "</p>"
                f'<p class="offer-q">&ldquo;{esc(o["text"])}&rdquo; &mdash; '
                f'<a href="{esc(o["url"])}" rel="nofollow noopener" target="_blank">'
                f'{esc(b["name"])}&rsquo;s page</a>{seen}</p>'
                f'<p class="offer-m"><strong>What it means:</strong> '
                f'{meaning(o, b["name"], mc_by.get(b["slug"]), rate24)}</p>'
                + ("<p class=\"offer-f\"><strong>Fine print we found:</strong> "
                   + " &middot; ".join(f"&ldquo;{esc(c)}&rdquo;" for c in o.get("conditions", []))
                   + "</p>" if o.get("conditions") else "")
                + "</div>")
        out.append("</section>")

    # ---- honesty about gaps
    blocked = [b["name"] for b in brands if str(b.get("status", "")).startswith("not readable")]
    none = [b["name"] for b in brands if not b.get("offers")
            and not str(b.get("status", "")).startswith("not readable")]
    out.append("<h2>Jewellers not covered today</h2>")
    if blocked:
        out.append("<p>These jewellers&rsquo; websites do not allow automated reading, so "
                   "check their offers directly: " + ", ".join(map(esc, blocked)) + ".</p>")
    if none:
        out.append("<p>No offer was published as text on these jewellers&rsquo; websites "
                   "today (some show offers only in pictures): " + ", ".join(map(esc, none)) + ".</p>")
    out.append("<p>We compare prices and published terms. We don&rsquo;t rank designs "
               "&mdash; that&rsquo;s your taste, not a fact we can check. Offers change "
               "often: confirm the terms with the jeweller before you buy.</p>")

    faq = []
    if rows:
        faq.append(("Which jeweller has the lowest price after offers today?",
                    summary + ", for a 10 g 22K ring at its usual making charge on rings "
                    "and any making-charge offer that applies to all gold jewellery."))
    faq.append(("Is a discount on making charges a good deal?",
                "Only if the making charge left after the discount is lower than elsewhere. "
                "A discount on a high making charge can still cost more than a jeweller with "
                "a lower charge and no offer; the discount never applies to the gold itself."))
    faq.append(("What does 0% deduction on old gold mean?",
                "You get the full value of your old gold at the day's rate after a purity "
                "test. It is often limited to jewellery originally bought from that jeweller."))
    return "".join(out), faq, summary
