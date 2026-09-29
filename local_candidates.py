#!/usr/bin/env python3
"""Candidate local / regional jewellers, per state, for discover_local.py.

WHY THIS IS A HAND-CURATED LIST AND NOT A WEB SEARCH

Appending a candidate is cheap; verifying one is not, and verification is
what actually needs automating. A search engine is also not available to a
CI job: DuckDuckGo's HTML endpoint answers a 202 challenge page to a plain
request and Bing's RSS returns essentially nothing, so a job cannot
discover domains on its own. So the split is deliberate - a person (or an
agent with a search tool) appends candidates here, and discover_local.py
does the repetitive part: probe every candidate, work out whether it
publishes a readable rate, and say so.

Re-probing on a schedule is the point, not a nicety. In one week this
repo saw Senco rename a product handle (breaking a pinned URL) and IBJA
switch from per-10g to per-gram (breaking a parser). A candidate that
answers "blocked" or "no rate" today can become usable later, and one that
works today can stop.

WHAT COUNTS AS A CANDIDATE

A jeweller with its OWN site that plausibly publishes its OWN rate.
Explicitly NOT aggregators - bankbazaar, groww, goodreturns, goldchimp,
allindiabullion and similar rank first for "gold rate <city>" but they
republish someone else's number. Reading a rate from them would make this
site a copy of a copy, and the whole point is the jeweller's own figure.

Searching "<state> jewellers gold rate" mostly returns those aggregators
plus the national chains already on the board; genuinely local shops
overwhelmingly show a board in the shop and publish nothing. Expect a low
hit rate and treat that as information, not failure - seed_brands.py
already carries six regional brands parked as active=False for exactly
this reason.

`state` should match the names used in REGION_MAP / STATES in
generate_site.py so a promoted brand lands in the right region.
"""

# state -> the jewellery cities worth searching, for whoever extends this.
STATE_CITIES = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur"],
    "Arunachal Pradesh": ["Itanagar"],
    "Assam": ["Guwahati", "Dibrugarh"],
    "Bihar": ["Patna", "Gaya"],
    "Chhattisgarh": ["Raipur", "Bilaspur"],
    "Goa": ["Panaji", "Margao"],
    "Gujarat": ["Ahmedabad", "Surat", "Rajkot", "Vadodara"],
    "Haryana": ["Gurugram", "Faridabad", "Karnal"],
    "Himachal Pradesh": ["Shimla"],
    "Jharkhand": ["Ranchi", "Jamshedpur"],
    "Karnataka": ["Bengaluru", "Mysuru", "Hubballi"],
    "Kerala": ["Thrissur", "Kochi", "Kozhikode", "Thiruvananthapuram"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Gwalior"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik"],
    "Manipur": ["Imphal"],
    "Meghalaya": ["Shillong"],
    "Mizoram": ["Aizawl"],
    "Nagaland": ["Kohima"],
    "Odisha": ["Bhubaneswar", "Cuttack"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur"],
    "Sikkim": ["Gangtok"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem"],
    "Telangana": ["Hyderabad", "Warangal"],
    "Tripura": ["Agartala"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Varanasi", "Agra"],
    "Uttarakhand": ["Dehradun", "Haridwar"],
    "West Bengal": ["Kolkata", "Siliguri", "Asansol"],
    # Union territories
    "Andaman and Nicobar Islands": ["Port Blair"],
    "Chandigarh": ["Chandigarh"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Silvassa", "Daman"],
    "Delhi": ["New Delhi", "Karol Bagh", "Chandni Chowk"],
    "Jammu and Kashmir": ["Srinagar", "Jammu"],
    "Ladakh": ["Leh"],
    "Lakshadweep": ["Kavaratti"],
    "Puducherry": ["Puducherry"],
}

# Aggregators and marketplaces - never candidates. Kept as a guard so a
# future contributor cannot quietly add one.
DENY_HOSTS = {
    "bankbazaar.com", "groww.in", "goodreturns.in", "goldchimp.in",
    "allindiabullion.com", "kotakneo.com", "coinbazaar.in", "indiamart.com",
    "todaygoldsilverrate.com", "bullions.co.in", "ibjarates.com",
    "ibjaprice.com", "paisabazaar.com", "policybazaar.com", "amazon.in",
    "flipkart.com", "justdial.com", "scribd.com", "linkedin.com",
    "wikipedia.org", "ibja.co",
}

# CANDIDATES - {state, city, name, domain}. `domain` only; the prober walks
# CANDIDATE_PATHS itself, so a rate URL is not needed up front (and guessing
# one wrong is worse than leaving it out).
CANDIDATES = [
    # ---- Delhi / North: no coverage on the board at all today ----
    #
    # All four investigated by hand 2026-09-27, beyond what the prober does,
    # because their pages responded and looked promising. None is usable. The
    # findings are kept so the next person does not repeat the work:
    #
    # PC JEWELLER - no rate anywhere in the served HTML. What looked like rate
    # wording was product tag lists ("22K Gold Bracelet", "22K Gold
    # Necklace"). A large catalogue site with no rate board.
    {"state": "Delhi", "city": "New Delhi", "name": "PC Jeweller",
     "domain": "pcjeweller.com"},
    #
    # KHANNA JEWELLERS - the interesting one, and the reason
    # discover_local.ladder_sane() exists. The homepage ships a real, daily
    # updated rate config in a script:
    #
    #   metalPriceConfig = {"gold_price_24k":16200,"gold_price_22k":14040,
    #     "gold_price_21k":6343.75,"gold_price_18k":11487,...,
    #     "include_taxes":true,"default_tax":3,
    #     "last_updated_on":"2026-09-26T06:44:27.955Z"}
    #
    # It parses perfectly and is genuinely maintained - and it is NOT a board
    # rate. 24K at 16,200 is +6.0% over the market median; the 22K/24K ratio
    # is 0.867 where a purity ladder is 0.9167; gold_price_21k is 6,343.75
    # where the ladder says ~14,175, and the 8K/9K/10K entries are similarly
    # dead placeholders. include_taxes:true says outright that these are
    # GST-inclusive retail figures, while this site stores
    # canonical_24k_pre_gst.
    #
    # Left as a candidate deliberately: the prober now returns "suspect" for
    # it rather than silently passing or silently skipping, so if Khanna ever
    # publishes a clean pre-GST ladder the weekly run will say so.
    {"state": "Delhi", "city": "New Delhi", "name": "Khanna Jewellers",
     "domain": "khannajeweller.com"},
    # MEHRASONS - domain does not resolve. The brand is real (Karol Bagh,
    # Janpath, Tilak Nagar) but mehrasons.com is not its live site; if a
    # working domain turns up, replace this entry rather than adding a second.
    {"state": "Delhi", "city": "New Delhi", "name": "Mehrasons Jewellers",
     "domain": "mehrasons.com"},
    # ANMOL - no rate wording in the HTML at all. A bridal/high-jewellery
    # brand; those price per piece and publish no per-gram rate.
    {"state": "Maharashtra", "city": "Mumbai", "name": "Anmol Jewellers",
     "domain": "anmoljewellers.in"},

    # ---- Already-parked regional brands, re-probed for free ----
    # seed_brands.py has these at active=False because no rate was found
    # when they were first tried. Sites change; let the job re-check rather
    # than leaving them written off.
    {"state": "Tamil Nadu", "city": "Chennai", "name": "Lalithaa Jewellery",
     "domain": "lalithaajewellery.com"},
    {"state": "Tamil Nadu", "city": "Coimbatore", "name": "Kirtilals",
     "domain": "kirtilals.com"},
    {"state": "Kerala", "city": "Thrissur", "name": "Josco Jewellers",
     "domain": "joscogroup.com"},
    {"state": "Gujarat", "city": "Ahmedabad", "name": "RBZ Jewellers",
     "domain": "rbzjewellers.com"},
    {"state": "Karnataka", "city": "Bengaluru", "name": "Sri Kumaran",
     "domain": "srikumaran.com"},
    # BHINDI - checked by hand 2026-09-27: no rate in the served HTML. The
    # apparent rate wording was Shopify product handles
    # ("22k-gold-ganesh-statue-...", "elegant-7-inch-22k-yellow-gold-
    # bracelet-..."), i.e. product names, not a rate board.
    {"state": "Maharashtra", "city": "Mumbai", "name": "Bhindi Jewellers",
     "domain": "bhindi.com"},
]
