"""Jeweller-vs-jeweller pages: "Tanishq vs Kalyan gold rate today" and the
like, for the big national chains, plus a hub that ranks every jeweller.

Questions put to search engines and AI assistants are often comparisons, so
each page answers one in its first lines: whose gold is cheaper today, by how
much per gram and per 10 g, and what a 10 g 22K ring works out to at each
after the making charge, its offer and 3% GST - then the making charge by
jewel and each side's offers. Every figure comes from the assistant's
knowledge file (the same numbers Sona and the jeweller pages use); a making
charge we have not measured is said to be missing, never invented.

    pages(kb, med, display_date, date_iso, site_url, inr) -> [(slug, title, desc, body, jsonld)]
"""
import html
import json
from itertools import combinations

# The national chains people most often compare, by the knowledge file's slug,
# and the short name used in page addresses.
MAJORS = [("tanishq", "tanishq"), ("kalyan", "kalyan-jewellers"), ("malabar", "malabar"),
          ("joyalukkas", "joyalukkas"), ("caratlane", "caratlane"), ("senco", "senco")]
CATS = ["Ring", "Bangle", "Earrings", "Mangalsutra", "Chain", "Necklace"]
GST = 0.03
HUB = "compare-jewellers-gold-rate"


def slug(a, b):
    return f"{a}-vs-{b}-gold-rate-today"


def _ring(b):
    """Approximate bill for a 10 g 22K ring at jeweller b, or None without a making figure."""
    mk = (b.get("mk") or {}).get("Ring")
    if not b.get("r24") or mk is None:
        return None
    gold = b["r24"] * 22 / 24 * 10
    off = (b.get("mo") or {}).get("f") or 0
    making = gold * mk / 100 * (1 - off / 100)
    return {"gold": gold, "mk": mk, "off": off, "making": making, "total": (gold + making) * (1 + GST)}


def _ring_mk(b):
    v = (b.get("mk") or {}).get("Ring")
    return "-" if v is None else f"{v:g}%"


def _faq_ld(faq):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}


def pages(kb, med, display_date, date_iso, site_url, inr):
    from datetime import date as _date
    short = _date.fromisoformat(date_iso).strftime("%-d %b")          # "1 Nov", for titles
    by = {b["s"]: b for b in kb.get("brands", []) if b.get("r24")}
    majors = [(s, u) for s, u in MAJORS if s in by]
    e = html.escape
    out, links = [], []
    for (sa, ua), (sb, ub) in combinations(majors, 2):
        A, B = by[sa], by[sb]
        na, nb = A["n"], B["n"]
        a22, b22 = A["r24"] * 22 / 24, B["r24"] * 22 / 24
        lo, hi = (A, B) if a22 <= b22 else (B, A)
        d22 = abs(a22 - b22)
        ra, rb = _ring(A), _ring(B)
        if d22 < 0.5:
            verdict = f"{na} and {nb} quote the same 22K rate today, {inr(a22)} per gram."
        else:
            verdict = (f"{lo['n']} is cheaper today: 22K at {inr(lo['r24'] * 22 / 24)} per gram against "
                       f"{inr(hi['r24'] * 22 / 24)} at {hi['n']} - {inr(d22)} less per gram, "
                       f"{inr(d22 * 10)} on 10 g.")
        ring_line = ""
        if ra and rb:
            cheap = A if ra["total"] <= rb["total"] else B
            gap = abs(ra["total"] - rb["total"])
            ring_line = (f"For a 10 g 22K ring, after each jeweller's making charge, its making offer and 3% GST, "
                         f"{cheap['n']} works out about {inr(gap)} cheaper "
                         f"({inr(ra['total'])} at {na}, {inr(rb['total'])} at {nb}).")

        def cell(x, fmt):
            return fmt(x) if x is not None else "not measured"
        rows = [("22K per gram", inr(a22), inr(b22)), ("24K per gram", inr(A["r24"]), inr(B["r24"])),
                ("10 g of 22K (gold only, before GST)", inr(a22 * 10), inr(b22 * 10))]
        for c in CATS:
            ma, mb = (A.get("mk") or {}).get(c), (B.get("mk") or {}).get(c)
            if ma is not None or mb is not None:
                rows.append((f"Making charge, {c.lower()}", cell(ma, lambda v: f"{v:g}%"), cell(mb, lambda v: f"{v:g}%")))
        oa, ob = (A.get("mo") or {}), (B.get("mo") or {})
        rows.append(("Offer on making charge", (f"{oa['f']:g}% off" if oa.get("f") else (f"up to {oa['u']:g}% on some designs" if oa.get("u") else "none listed")),
                     (f"{ob['f']:g}% off" if ob.get("f") else (f"up to {ob['u']:g}% on some designs" if ob.get("u") else "none listed"))))
        if ra or rb:
            rows.append(("10 g 22K ring, approximate bill", cell(ra and ra["total"], inr), cell(rb and rb["total"], inr)))
        table = ("<div class=\"tbl-wrap\"><table class=\"jt\"><tr><th></th>"
                 f"<th><a href=\"{site_url}{A.get('u', '')}\">{e(na)}</a></th><th><a href=\"{site_url}{B.get('u', '')}\">{e(nb)}</a></th></tr>"
                 + "".join(f"<tr><td>{e(k)}</td><td>{v1}</td><td>{v2}</td></tr>" for k, v1, v2 in rows)
                 + "</table></div>")

        def offers(b):
            o = b.get("off") or []
            return ("<ul>" + "".join(f"<li><b>{e(x.get('h', ''))}</b>: {e(x.get('t', ''))[:160]}</li>" for x in o[:4]) + "</ul>"
                    if o else "<p>No offer published on its website today.</p>")
        faq = [(f"Which is cheaper today, {na} or {nb}?", verdict + (" " + ring_line if ring_line else "")),
               (f"What is the making charge at {na} and {nb}?",
                "; ".join(f"{b['n']}: " + (", ".join(f"{c.lower()} {v:g}%" for c, v in sorted((b.get("mk") or {}).items()))
                                           or "not measured yet") for b in (A, B))
                + ". Medians of plain 22K pieces read from each jeweller's own price breakup; your design will differ."),
               (f"Is gold at {na} and {nb} the same purity?",
                "Yes. Both sell BIS-hallmarked jewellery: 22K is 91.6% gold (stamped 916) and every piece carries a "
                "6-digit HUID you can check in the BIS Care app. The rate difference is the jeweller's own pricing."),
               ("How is the final bill worked out?",
                "Gold value (rate x weight) + making charge (a % of the gold value, less any offer) + 3% GST on both, "
                "plus a small hallmarking fee. Confirm the exact figure with the jeweller.")]
        title = f"{na} vs {nb} Gold Rate Today ({short}): Which Is Cheaper?"
        desc = (f"{na} vs {nb} today: 22K {inr(a22)} vs {inr(b22)} per gram. "
                + (f"{lo['n']} is {inr(d22)}/g cheaper. " if d22 >= 0.5 else "Same rate. ")
                + "Making charges, offers and a 10 g ring bill compared.")
        body = (f"<h1>{e(na)} vs {e(nb)} Gold Rate Today</h1>"
                f"<p class=\"updated-on\">{display_date} - rates read from each jeweller's own website, before GST.</p>"
                f"<p><b>{e(verdict)}</b> {e(ring_line)}</p>" + table
                + "<p class=\"calc-note\">Making charges are medians of plain 22K pieces from each jeweller's published price "
                "breakup, and vary by design; the ring bill is an approximation. Confirm with the jeweller before buying.</p>"
                f"<h2>Offers today at {e(na)}</h2>" + offers(A) + f"<h2>Offers today at {e(nb)}</h2>" + offers(B)
                + "<h2>Questions</h2>" + "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in faq)
                + f"<p>Compare more: <a href=\"{site_url}/{HUB}\">every jeweller ranked today</a> · "
                f"<a href=\"{site_url}/making-charges-comparison\">making charges</a> · "
                f"<a href=\"{site_url}/gold-offers-today\">today's offers</a> · <a href=\"{site_url}/\">gold rate today</a>.</p>")
        url = f"{site_url}/{slug(ua, ub)}"
        ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": url, "inLanguage": "en-IN",
               "dateModified": date_iso, "about": [{"@type": "Organization", "name": na}, {"@type": "Organization", "name": nb}]},
              _faq_ld(faq)]
        out.append((slug(ua, ub), title, desc, body, ld))
        links.append((na, nb, slug(ua, ub), lo["n"] if d22 >= 0.5 else None, d22))

    # the hub: every jeweller today, cheapest 22K first, and the comparisons
    allb = sorted(by.values(), key=lambda b: b["r24"])
    rows = "".join(
        f"<tr><td>{i}</td><td><a href=\"{site_url}{b.get('u', '')}\">{e(b['n'])}</a></td><td>{inr(b['r24'] * 22 / 24)}</td>"
        f"<td>{inr(b['r24'])}</td><td>{'national' if b.get('nat') else 'regional'}</td>"
        f"<td>{_ring_mk(b)}</td></tr>"
        for i, b in enumerate(allb, 1))
    pair_list = "".join(
        f"<li><a href=\"{site_url}/{s}\">{e(a)} vs {e(b)}</a> - "
        + (f"{e(c)} cheaper by {inr(d)}/g today" if c else "same rate today") + "</li>"
        for a, b, s, c, d in links)
    nat = [b for b in allb if b.get("nat")]
    faq = [("Which jeweller has the cheapest gold today?",
            f"{allb[0]['n']}, with 22K at {inr(allb[0]['r24'] * 22 / 24)} per gram before GST. Among national chains, "
            f"{nat[0]['n']} at {inr(nat[0]['r24'] * 22 / 24)}." if nat else ""),
           ("Which jeweller is the most expensive today?",
            f"{allb[-1]['n']}, 22K at {inr(allb[-1]['r24'] * 22 / 24)} per gram - "
            f"{inr((allb[-1]['r24'] - allb[0]['r24']) * 22 / 24)} more than the cheapest."),
           ("Is the cheapest rate the cheapest bill?",
            "Not always. The making charge (a % of the gold value) and its offer often decide the bill. "
            "Compare the full price for your piece; Sona on mygoldrates.com works it out for each jeweller.")]
    hub_title = f"Compare Jewellers' Gold Rates Today ({short}): Tanishq, Kalyan, Malabar"
    hub_body = (f"<h1>Compare Jewellers' Gold Rates Today</h1><p class=\"updated-on\">{display_date} - "
                f"{len(allb)} jewellers, 22K and 24K per gram before GST, cheapest first.</p>"
                f"<p><b>{e(faq[0][1])}</b></p>"
                "<div class=\"tbl-wrap\"><table class=\"jt\"><tr><th>#</th><th>Jeweller</th><th>22K /g</th><th>24K /g</th>"
                f"<th>Sells</th><th>Ring making</th></tr>{rows}</table></div>"
                f"<h2>Head-to-head</h2><ul>{pair_list}</ul>"
                + "<h2>Questions</h2>" + "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in faq if a))
    hub_ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": hub_title, "url": f"{site_url}/{HUB}",
               "inLanguage": "en-IN", "dateModified": date_iso},
              {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
                  {"@type": "ListItem", "position": i + 1, "name": f"{a} vs {b}", "url": f"{site_url}/{s}"}
                  for i, (a, b, s, c, d) in enumerate(links)]},
              _faq_ld([q for q in faq if q[1]])]
    out.append((HUB, hub_title, f"Every jeweller's 22K and 24K gold rate today, cheapest first, and head-to-head "
                                f"comparisons of Tanishq, Kalyan, Malabar, Joyalukkas, CaratLane and Senco.",
                hub_body, hub_ld))
    return out


def jsonld(ld):
    return '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>"
