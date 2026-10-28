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
    # Ready answers for what visitors are likely to ask next (questions Sona
    # used to answer with the day's rate, or not at all). Figures here are
    # rules and units that do not change day to day; rates never appear.
    {"q": "How can I check gold purity at home?",
     "k": ["purity", "check", "test", "home", "real", "fake", "genuine", "magnet", "acid", "original", "verify"],
     "a": "There is no reliable home test - magnet, biting or vinegar tricks cannot tell 22K from 18K. "
          "Check the BIS hallmark and verify its 6-character HUID in the BIS CARE app, or ask for a "
          "karatmeter (XRF) test at a jeweller.",
     "u": "/learn/gold-hallmarking"},
    {"q": "What is digital gold and is it safe?",
     "k": ["digital", "online", "app", "paytm", "phonepe", "gpay", "safe", "virtual"],
     "a": "Digital gold lets you buy small amounts of 24K gold online, held in a vault by the seller's "
          "partner. It is not regulated by RBI or SEBI, buying and selling prices differ by a few percent, "
          "and 3% GST applies when you buy. Gold ETFs and gold mutual funds are the regulated alternative."},
    {"q": "Should I buy a gold ETF or physical gold?",
     "k": ["etf", "etfs", "mutual", "fund", "funds", "paper", "demat", "physical", "sip"],
     "a": "Gold ETFs and gold mutual funds follow the gold price, are regulated by SEBI, have no making "
          "charges or storage worries and can be sold on any working day (ETFs need a demat account). "
          "Buy physical gold when you want to wear it; for pure investment, ETFs or 24K coins cost less."},
    {"q": "What are Sovereign Gold Bonds?",
     "k": ["sovereign", "bond", "bonds", "sgb", "rbi", "interest"],
     "a": "Government gold bonds issued through the RBI: they paid 2.5% interest a year plus the gold "
          "price at maturity, tax-free if held to maturity. No new bonds have been issued since early "
          "2024; existing ones can be bought and sold on the stock exchange."},
    {"q": "How much gold can I keep at home?",
     "k": ["keep", "home", "limit", "store", "legal", "income", "seize", "raid", "allowed", "possession"],
     "a": "There is no legal limit if you can show where the gold came from. In income-tax searches, "
          "officers do not seize up to 500 g for a married woman, 250 g for an unmarried woman and "
          "100 g for a man, even without proof of purchase."},
    {"q": "How much gold can I bring from Dubai or abroad?",
     "k": ["dubai", "abroad", "customs", "carry", "bring", "airport", "foreign", "uae", "duty", "free", "allowance", "travel"],
     "a": "Travellers returning to India get a duty-free allowance for gold jewellery that depends on who "
          "is travelling and how long they stayed abroad; above it, customs duty is due, and bars and coins "
          "are dutiable. Check the current rules on the CBIC (Indian Customs) website before you fly."},
    {"q": "Is gold cheaper in Dubai?",
     "k": ["dubai", "uae", "cheaper", "abroad", "singapore", "foreign", "overseas"],
     "a": "Often a little, because the UAE has no import duty. But gold brought into India above your "
          "duty-free allowance pays Indian customs duty, which usually wipes out the saving - compare "
          "the final cost including duty, and the making charges, before you buy."},
    {"q": "What is the hallmarking charge?",
     "k": ["hallmark", "hallmarking", "charge", "fee", "cost", "huid"],
     "a": "BIS charges jewellers a small fee per piece for hallmarking - tens of rupees, not hundreds. "
          "Some bills show it separately; it should never be a large amount.",
     "u": "/learn/gold-hallmarking"},
    {"q": "How much will I get for my old gold?",
     "k": ["old", "sell", "selling", "value", "get", "worth", "resale", "cash", "buy", "back", "exchange"],
     "a": "Old gold is valued by weight times purity (tested at the counter) at the jeweller's buying "
          "rate, which is usually a little below its selling rate; making charges and stones are not paid "
          "back. Exchanging it for new jewellery usually gets more than selling it for cash.",
     "u": "/gold-offers-today"},
    {"q": "What is 916 gold?",
     "k": ["916", "meaning", "mean", "means"],
     "a": "916 means 91.6% pure gold - the same as 22K. On the hallmark it appears as 22K916.",
     "u": "/learn/22k-vs-24k-gold"},
    {"q": "What is KDM gold?",
     "k": ["kdm", "cadmium", "solder"],
     "a": "KDM was a cadmium-based solder once used to join gold; it is no longer used because cadmium "
          "is harmful. Today '916 KDM' simply means 22K - what matters is the BIS hallmark with its HUID.",
     "u": "/learn/gold-hallmarking"},
    {"q": "What is rose gold or white gold?",
     "k": ["rose", "white", "pink", "colour", "color", "rhodium", "yellow"],
     "a": "Rose gold is gold mixed with more copper, giving it a pink colour; white gold is gold mixed "
          "with white metals and usually rhodium-plated. Both are usually 18K or 14K and priced on their "
          "gold content."},
    {"q": "Is 14K gold real gold?",
     "k": ["14k", "585", "real", "fourteen"],
     "a": "Yes - 14K is 58.5% gold (585). It is harder and cheaper than 18K or 22K, and must still carry "
          "a BIS hallmark (14K585)."},
    {"q": "What is 1 gram gold jewellery?",
     "k": ["imitation", "plated", "covering", "artificial", "fashion", "micro", "one gram", "1 gram"],
     "a": "'1 gram gold' jewellery is gold-plated or gold-covered imitation jewellery with very little "
          "gold in it. It is not hallmarked and has almost no resale value."},
    {"q": "How much gold loan can I get?",
     "k": ["loan", "loans", "borrow", "mortgage", "pledge", "nbfc", "interest", "muthoot", "manappuram"],
     "a": "Banks and gold-loan companies lend a share of your gold's value, capped by RBI rules, and "
          "interest rates vary a lot between lenders - compare a few. Our gold loan calculator estimates "
          "how much you could borrow.",
     "u": "/gold-loan-calculator"},
    {"q": "Why does the gold price go up and down?",
     "k": ["why", "increase", "increasing", "rising", "rise", "up", "down", "falling", "change",
           "changes", "high", "expensive", "costly", "reason"],
     "a": "Indian gold rates follow the international gold price in dollars and the rupee-dollar rate, "
          "plus import duty and each jeweller's premium. World events, interest rates and festive demand "
          "move them every day.",
     "u": "/learn/how-gold-rates-are-set"},
    {"q": "What is the best day to buy gold?",
     "k": ["day", "auspicious", "muhurat", "muhurtham", "festival", "when", "week", "month", "shubh"],
     "a": "No day of the week is reliably cheaper. Festivals like Dhanteras and Akshaya Tritiya bring "
          "offers, but also crowds and firmer rates. On whatever day you choose, compare jewellers and "
          "today's offers - the gap between them is bigger than day-to-day moves."},
    {"q": "What about diamond prices?",
     "k": ["diamond", "diamonds", "solitaire", "4c", "clarity", "lab", "grown"],
     "a": "I cover gold only. Diamond prices depend on cut, colour, clarity and carat and are not "
          "comparable shop to shop. For the gold in diamond jewellery (usually 18K), ask me the 18K rate."},
    {"q": "Is this jeweller's gold pure and trustworthy?",
     "k": ["pure", "trust", "trustworthy", "genuine", "reliable", "safe", "fake", "quality", "good", "honest"],
     "a": "Every jeweller here must sell BIS-hallmarked jewellery, so purity is checked the same way at "
          "all of them: look for the hallmark and verify the HUID in the BIS CARE app. We compare their "
          "rates, making charges and offers - not their service.",
     "u": "/learn/gold-hallmarking"},
    {"q": "How often are the rates updated?",
     "k": ["updated", "update", "often", "daily", "refresh", "latest", "live", "time"],
     "a": "Every morning, after jewellers publish their day's rate. Some jewellers change their rate "
          "during the day, so confirm it at the store before you pay.",
     "u": "/methodology"},
    {"q": "Are the rates including GST?",
     "k": ["including", "include", "inclusive", "includes", "gst", "without", "excluding", "tax"],
     "a": "No - all rates here are before GST. Add 3% GST on the gold and making charges for the "
          "billed price."},
    {"q": "How is the price of gold jewellery calculated?",
     "k": ["calculate", "calculated", "calculation", "formula", "bill", "final", "total", "billing"],
     "a": "Price = weight x today's rate for the karat + making charges (+ stones, if any) + 3% GST on "
          "the total. Ask me, for example, \"price of 10 g 22K at Tanishq\" for a worked bill.",
     "u": "/calculators"},
    {"q": "Can I return gold jewellery?",
     "k": ["return", "refund", "cancel", "policy", "exchange"],
     "a": "Return and buyback rules are each jeweller's own - many offer exchange or buyback with a "
          "deduction rather than a refund. Ask for the policy in writing on the bill before you pay."},
    {"q": "How do gold savings schemes work?",
     "k": ["scheme", "schemes", "savings", "saving", "monthly", "plan", "instalment", "installment",
           "harvest", "kitty", "deposit"],
     "a": "You pay the jeweller a fixed amount every month for about 10-11 months, and it adds a bonus "
          "or waives part of the making charges when you buy jewellery at the end. You can redeem it only "
          "as jewellery at that jeweller, and it is not a bank deposit."},
    {"q": "Can I buy gold on EMI?",
     "k": ["emi", "emis", "credit", "card", "finance", "instalments", "installments", "loan"],
     "a": "Usually not: RBI rules stop banks lending to buy gold, and most cards exclude jewellery from "
          "EMI. Jewellers' monthly savings schemes are the usual way to pay in instalments."},
    {"q": "Is PAN needed to buy gold, and is there a cash limit?",
     "k": ["pan", "cash", "limit", "aadhaar", "kyc", "lakh", "documents", "id", "card", "required", "purchase", "mandatory"],
     "a": "PAN is needed for a purchase of Rs 2 lakh or more, and a jeweller may not take Rs 2 lakh or "
          "more in cash for one purchase. Paying by card, UPI or bank transfer avoids both problems."},
    {"q": "How is tax charged when I sell gold?",
     "k": ["tax", "capital", "gains", "gain", "ltcg", "stcg", "sell", "selling", "income"],
     "a": "Physical gold held more than 24 months: long-term capital gains taxed at 12.5% without "
          "indexation. Held less: the gain is added to your income and taxed at your slab rate. Budgets "
          "change these rules, so check with a tax adviser."},
    {"q": "What is the import duty on gold?",
     "k": ["import", "duty", "customs", "budget", "government", "basic"],
     "a": "India imports most of its gold, and the import duty set in the Union Budget is part of every "
          "rate you see here; 3% GST is then added on the bill.",
     "u": "/learn/how-gold-rates-are-set"},
    {"q": "How do I contact MyGoldRates?",
     "k": ["contact", "reach", "feedback", "complaint", "suggestion", "support", "help", "message", "phone"],
     "a": "Write to us from the Contact page - we read every message, and suggestions for Sona are "
          "welcome.",
     "u": "/contact"},
    {"q": "Who runs MyGoldRates?",
     "k": ["who", "made", "owner", "runs", "behind", "created", "built", "founder", "company"],
     "a": "MyGoldRates is an independent site that compares the rates, making charges and offers "
          "jewellers publish. It is not owned by any jeweller and is free to use.",
     "u": "/about"},
    {"q": "Is this website free?",
     "k": ["free", "cost", "charge", "paid", "subscription", "fees", "website", "site", "app"],
     "a": "Yes - completely free, with no sign-up needed. The daily rate email is free too.",
     "u": "/about"},
    {"q": "Do you sell gold?",
     "k": ["sell", "buy", "order", "purchase", "shop", "online", "deliver", "delivery", "website"],
     "a": "No - we don't sell gold. We compare jewellers' rates, making charges and offers so you can "
          "buy wherever it works out cheapest; each jeweller's page links to its own website."},
    {"q": "How do I unsubscribe from the emails?",
     "k": ["unsubscribe", "stop", "remove", "emails", "opt", "out"],
     "a": "Every email has an Unsubscribe link at the bottom - one tap and you are off the list."},
    {"q": "How much does a mangalsutra or chain weigh?",
     "k": ["weigh", "weight", "mangalsutra", "heavy", "grams", "typical", "average"],
     "a": "It varies a lot: a light daily-wear chain or mangalsutra can be 4-8 g, a traditional one 20 g "
          "or more. Tell me the weight and I'll work out today's price, e.g. \"price of 8 g 22K\"."},
    {"q": "What is a pavan?",
     "k": ["pavan", "pavun", "pawan", "sovereign", "savaran", "soverin"],
     "a": "A pavan (or sovereign) is 8 grams of gold, the usual unit in Tamil Nadu and Kerala. Ask me "
          "\"price of 1 pavan 22K\" for today's price."},
    {"q": "What is the difference between carat and karat?",
     "k": ["carat", "karat", "kt", "ct", "purity", "meaning"],
     "a": "Karat (K) is gold purity: 24K is pure, 22K is 91.6%, 18K is 75%. Carat (ct) is the weight "
          "unit for diamonds and gems (1 ct = 0.2 g). In India the two words are often used for both."},
]


def _load_answers():
    try:
        with open(ANSWERS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [{"q": a["q"], "a": a["a"], **({"u": a["u"]} if a.get("u") else {})}
                for a in data.get("answers", []) if a.get("q") and a.get("a")]
    except (FileNotFoundError, ValueError, KeyError):
        return []


def _product_offer(po):
    """(flat %, up-to %) from the offer seen on the products themselves:
    flat only when (nearly) every piece read carried it."""
    pct, top = float(po.get("making_pct_off") or 0), float(po.get("max_pct_off") or 0)
    return (pct if po.get("share", 0) >= 0.9 else 0.0), float(min(max(pct, top), 100))


def _making_offer(offers):
    """(flat %, best up-to %) off the making charge on gold jewellery."""
    import offers_page as op
    flat = max((o["pct_max"] for o in offers if op.flat_making_offer(o)), default=0)
    upto = max((o["pct_max"] for o in offers if o.get("kind") == "making_off" and o.get("pct_max")
                and op._gold_jewellery_applies(o) and not o.get("image")), default=0)
    return float(flat), float(min(upto, 100))


def build(*, live, med, trend, locations, place_state, region_map, brand_home,
          loc_slug, jeweller_pages, making, offers, ring_rows, offer_meaning,
          offer_headline, guides, display_date, updated_iso, site_url, coords=None):
    """Everything the assistant knows today, as a compact dict."""
    rows = {}
    for r in live:
        b = r.get("brands") or {}
        if not b.get("slug"):
            continue
        rows[b["slug"]] = {"s": b["slug"], "n": b["name"],
                           "r24": round(r["canonical_24k_pre_gst"], 2)}
    off_by = {b["slug"]: b for b in (offers or {}).get("brands", [])}
    mk_by, mko_by = {}, {}
    for b in (making or {}).get("brands", []):
        ex = [e.get("url", "") for c in b.get("categories", []) for e in c.get("examples", [])]
        host = ""
        if ex:
            host = ex[0].split("/")[2].replace("www.", "")
        mk_by[host] = {c["category"]: c["making_pct_median"] for c in b.get("categories", [])
                       if c.get("making_pct_median") is not None}
        if b.get("offer"):                     # read from the products themselves (Tanishq)
            mko_by[host] = b["offer"]
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
        # Making-charge offers, for "best offer on a bangle": f = a flat
        # discount on all gold jewellery (used for the ranking), u = the best
        # "up to" / selected-designs discount (shown only as a best case).
        mo_f, mo_u = _making_offer(ob.get("offers") or [])
        po = mko_by.get(dom) if dom else None
        if po and not (mo_f or mo_u):
            mo_f, mo_u = _product_offer(po)
        if mo_f or mo_u:
            rec["mo"] = {"f": mo_f, "u": mo_u}
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
        # "g": the city's centre, for "use my location" (matched on the device)
        cities.append({"n": p, "st": st, "u": f"/gold-rate-today-in-{loc_slug(p)}",
                       **({"loc": [s for s in local if s in rows]} if local else {}),
                       **({"g": list((coords or {})[p])} if p in (coords or {}) else {})})
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
