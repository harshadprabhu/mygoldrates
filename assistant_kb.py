"""Knowledge file for Sona, the site's jewellery assistant (docs/assistant.json).

Built by generate_site.py on every run from the same data as the pages:
today's rate at every jeweller, the city each place belongs to and the
jewellers that sell there, 90 days of the market median, making charges,
today's offers with what each means, a like-for-like ring price after offers,
the core FAQ, the guides, and the answers the owner has approved from real
visitor questions (data/assistant_answers.json, kept in git).

The assistant (assistant.js) answers in the visitor's browser from this file
alone: no server, no paid AI, and every number it shows is one of these.
"""
from __future__ import annotations

import json
import os

ANSWERS_FILE = "data/assistant_answers.json"

# The core FAQ. Short, factual, and checked against how the site works.
# "k" are the words that point to an answer; the matcher in assistant.js
# scores a question against them as well as against the wording of "q".
FAQ = [
    {"q": "What is the difference between 22K and 24K gold?",
     "k": ["22k", "24k", "difference", "purity", "which", "better", "916", "999"],
     "a": "24K is 99.9% pure gold (999) - soft, used for coins and bars. 22K is "
          "91.6% gold (916) with 8.4% other metals that make it strong enough for "
          "jewellery. Jewellery is almost always 22K or 18K; 24K is the choice for "
          "coins and investment.",
     "u": "/learn/22k-vs-24k-gold"},
    {"q": "What are making charges?",
     "k": ["making", "charges", "wastage", "va", "value", "addition", "labour"],
     "a": "The jeweller's fee for crafting the piece, on top of the gold. It is "
          "quoted as a % of the gold value or per gram and varies a lot by jeweller "
          "and design - often 8% to 25% for plain gold, higher for intricate work. "
          "It is usually the most negotiable part of the bill.",
     "u": "/making-charges-comparison"},
    {"q": "How much GST is there on gold jewellery?",
     "k": ["gst", "tax", "3%", "5%"],
     "a": "3% GST on the value of the gold plus making charges. The rates on "
          "MyGoldRates are before GST, so add 3% for the billed price."},
    {"q": "What is BIS hallmarking and HUID?",
     "k": ["hallmark", "hallmarking", "bis", "huid", "certificate", "pure", "fake"],
     "a": "Every piece of gold jewellery sold in India must carry a BIS hallmark: the "
          "BIS logo, the purity (e.g. 22K916) and a 6-character HUID code unique to "
          "that piece. You can check the HUID in the government's BIS CARE app.",
     "u": "/learn/gold-hallmarking"},
    {"q": "How many grams is one tola?",
     "k": ["tola", "sovereign", "pavan", "pavun", "gram", "grams", "convert"],
     "a": "1 tola = 11.664 grams. In South India a sovereign (pavan) is 8 grams. "
          "Ask me the price of any weight, for example \"price of 1 tola 22K\"."},
    {"q": "Why do jewellers charge different gold rates?",
     "k": ["different", "why", "vary", "differ", "rates", "jewellers", "same"],
     "a": "Each jeweller sets its own daily rate from the bullion price plus its "
          "own premium, so the same 22K can differ by a few hundred rupees per "
          "10 g. That's why we compare them side by side every day."},
    {"q": "Where do these rates come from?",
     "k": ["source", "where", "data", "accurate", "official", "how", "collect", "trust"],
     "a": "From each jeweller's own published rate, checked against the market: a "
          "rate more than 4% away from the other jewellers' is held back as a "
          "probable error, not shown. Rates are per gram, before GST.",
     "u": "/methodology"},
    {"q": "What does 0% deduction on old gold exchange mean?",
     "k": ["exchange", "old", "sell", "resale", "deduction", "buyback", "buy back"],
     "a": "You get the full value of your old gold at today's rate after a purity "
          "test, with nothing deducted. Often it applies only to jewellery bought "
          "from that same jeweller, and selling for cash usually gets less than "
          "exchanging for new jewellery.",
     "u": "/gold-offers-today"},
    {"q": "Is now a good time to buy gold?",
     "k": ["buy", "now", "good", "time", "should", "invest", "predict", "will",
           "future", "fall", "rise", "tomorrow", "next"],
     "a": "Nobody can reliably predict tomorrow's gold price, and we don't try. "
          "What helps: compare jewellers (the gap is often several thousand rupees "
          "on 10 g), watch the recent trend, and set a price alert for the rate "
          "you want - we'll email you when it gets there."},
    {"q": "How do I get daily gold rate alerts?",
     "k": ["alert", "alerts", "email", "subscribe", "notify", "notification",
           "daily", "whatsapp", "sms"],
     "a": "Subscribe free with your email: every morning you get the cheapest "
          "jeweller and the market rate, and you can ask to be emailed the day 22K "
          "drops to your price.",
     "u": "/inquiry"},
    {"q": "Is 20% off making charges a good deal?",
     "k": ["good", "deal", "worth", "discount", "off", "making", "offer", "real"],
     "a": "Only if the making charge left after the discount is lower than at other "
          "jewellers. 20% off an 18% making charge leaves 14.4% - still dearer than a "
          "jeweller charging 12% with no offer. The discount never applies to the gold "
          "itself. Compare the final price, not the size of the discount.",
     "u": "/gold-offers-today"},
    {"q": "Is 18K gold good for jewellery?",
     "k": ["18k", "750", "diamond", "light", "lightweight"],
     "a": "18K is 75% gold. It is harder than 22K, holds stones securely, and costs "
          "about 18% less per gram - the usual choice for diamond and lightweight "
          "daily-wear jewellery."},
    {"q": "Should I buy gold coins or jewellery?",
     "k": ["coin", "coins", "bar", "bars", "invest", "investment"],
     "a": "For investment, 24K coins or bars: low making charges and easier resale. "
          "Jewellery carries making charges you don't get back when you sell. Bank "
          "coins often cost more than jewellers' coins - compare the per-gram price."},
]


def _load_answers():
    try:
        with open(ANSWERS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [{"q": a["q"], "a": a["a"], **({"u": a["u"]} if a.get("u") else {})}
                for a in data.get("answers", []) if a.get("q") and a.get("a")]
    except (FileNotFoundError, ValueError, KeyError):
        return []


def build(*, live, med, trend, locations, place_state, region_map, brand_home,
          loc_slug, jeweller_pages, making, offers, ring_rows, offer_meaning,
          offer_headline, guides, display_date, updated_iso, site_url):
    """Everything the assistant knows today, as a compact dict."""
    rows = {}
    for r in live:
        b = r.get("brands") or {}
        if not b.get("slug"):
            continue
        rows[b["slug"]] = {"s": b["slug"], "n": b["name"],
                           "r24": round(r["canonical_24k_pre_gst"], 2)}
    off_by = {b["slug"]: b for b in (offers or {}).get("brands", [])}
    mk_by = {}
    for b in (making or {}).get("brands", []):
        ex = [e.get("url", "") for c in b.get("categories", []) for e in c.get("examples", [])]
        host = ""
        if ex:
            host = ex[0].split("/")[2].replace("www.", "")
        mk_by[host] = {c["category"]: c["making_pct_median"] for c in b.get("categories", [])
                       if c.get("making_pct_median") is not None}
    brands = []
    for slug, b in sorted(rows.items(), key=lambda kv: kv[1]["r24"]):
        rec = dict(b)
        rec["nat"] = slug not in region_map
        if slug in region_map:
            rec["st"] = region_map[slug]
        if brand_home.get(slug):
            rec["home"] = brand_home[slug]
        if jeweller_pages.get(slug):
            rec["u"] = "/" + jeweller_pages[slug]
        ob = off_by.get(slug) or {}
        dom = (ob.get("domain") or "").replace("www.", "")
        if dom and mk_by.get(dom):
            rec["mk"] = mk_by[dom]
        if ob.get("offers"):
            rec["off"] = [{"h": offer_headline(o), "t": o["text"][:160], "u": o["url"],
                           "m": offer_meaning(o, b["n"], None, med["24K"])}
                          for o in ob["offers"][:5]]
        brands.append(rec)
    cities = []
    for p in locations:
        st = place_state.get(p) or p
        local = sorted({s for s, sts in region_map.items() if st in sts}
                       | {s for s, hs in brand_home.items() if p in hs})
        cities.append({"n": p, "st": st, "u": f"/gold-rate-today-in-{loc_slug(p)}",
                       **({"loc": [s for s in local if s in rows]} if local else {})})
    hist = [[d, round(v, 2)] for d, v in trend[-90:]]
    ring = [{"s": r["slug"], "n": r["name"], "a": round(r["after"]), "b": round(r["before"]),
             "mk": r["making"], "p": r["flat_pct"]} for r in (ring_rows or [])]
    return {
        "v": 1,
        "date": display_date,
        "updated": updated_iso,
        "site": site_url,
        "med": {k: round(med[k], 2) for k in ("24K", "22K", "18K")},
        "brands": brands,
        "cities": cities,
        "hist": hist,
        "ring": ring,
        "faq": FAQ,
        "guides": [{"t": t, "u": u, "d": d} for t, u, d in guides],
        "learned": _load_answers(),
    }


def write(kb, path="docs/assistant.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, separators=(",", ":"))
    return os.path.getsize(path)
