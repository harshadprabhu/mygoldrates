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

    # ---- 2026-10-20 sweep: 56 regional jewellers, probed and rendered ----
    # Added to the board the same day, after a hand check against the
    # market median (not listed here, they are brands now): Thangamayil
    # (Madurai), Khazana (Chennai), AVR Swarna Mahal (Salem, 22K only - its
    # 24K is a coin price) and Mahesh Jewellers (Thane, 22K only - its 24K
    # is 995 fineness).
    #
    # Read a rate but NOT added, kept here so the weekly run re-checks them:
    # NAVRATAN - rate page says "updated on 11 October" on 20 October: not
    # maintained daily.
    {"state": "Madhya Pradesh", "city": "Indore", "name": "Navratan Jewellers",
     "domain": "navratanjewellers.com"},
    # BHIMA (Kerala, bhimajewellery.com) - 22K banner 5.5% under the market
    # with no date shown; most likely a stale banner.
    {"state": "Kerala", "city": "Kozhikode", "name": "Bhima Jewellery Kerala",
     "domain": "bhimajewellery.com"},
    #
    # Responded, no rate on the homepage even after render. Several link a
    # rate page or app (Muliya "Today's Gold Rate", Chungath) - worth a
    # pinned-URL look by hand.
    {"state": "Tamil Nadu", "city": "Chennai", "name": "Saravana Selvarathnam",
     "domain": "www.saravanaselvarathnam.com"},
    {"state": "Tamil Nadu", "city": "Coimbatore", "name": "Sree Devi Jewellers",
     "domain": "www.sreedevijewellers.com"},
    {"state": "Kerala", "city": "Kozhikode", "name": "Chemmanur Jewellers",
     "domain": "www.chemmanurinternational.com"},
    {"state": "Kerala", "city": "Thrissur", "name": "Alapatt Jewellers",
     "domain": "www.alapatt.com"},
    {"state": "Kerala", "city": "Thrissur", "name": "Chungath Jewellery",
     "domain": "www.chungathjewellery.com"},
    {"state": "Kerala", "city": "Thrissur", "name": "Manappuram Jewellers",
     "domain": "www.manappuramjewellers.com"},
    {"state": "Karnataka", "city": "Puttur", "name": "Muliya Jewels",
     "domain": "www.muliya.in"},
    {"state": "Karnataka", "city": "Bengaluru", "name": "Navrathan Jewellers",
     "domain": "www.navrathan.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "Manepally Jewellers",
     "domain": "www.manepallyjewellers.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "PMJ Jewels",
     "domain": "www.pmjjewels.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "Sri Krishna Jewellers",
     "domain": "www.srikrishnajewellers.com"},
    {"state": "Andhra Pradesh", "city": "Visakhapatnam", "name": "CMR Jewellery",
     "domain": "www.cmrjewellery.com"},
    {"state": "West Bengal", "city": "Kolkata", "name": "Anjali Jewellers",
     "domain": "www.anjalijewellers.in"},
    {"state": "West Bengal", "city": "Kolkata", "name": "B C Sen Jewellers",
     "domain": "www.bcsenjewellers.com"},
    {"state": "West Bengal", "city": "Kolkata", "name": "Shyam Sundar Co Jewellers",
     "domain": "www.shyamsundarco.com"},
    {"state": "Maharashtra", "city": "Mumbai", "name": "Popley",
     "domain": "www.popley.com"},
    {"state": "Maharashtra", "city": "Pune", "name": "Kothari Jewellers",
     "domain": "www.kotharijewellers.com"},
    {"state": "Gujarat", "city": "Ahmedabad", "name": "Shree Hari Jewellers",
     "domain": "www.shreeharijewellers.com"},
    {"state": "Gujarat", "city": "Surat", "name": "Laxmi Diamonds Jewels",
     "domain": "www.laxmidiamond.com"},
    {"state": "Rajasthan", "city": "Jaipur", "name": "Surana Jewellers",
     "domain": "www.suranajewellers.com"},
    {"state": "Rajasthan", "city": "Jaipur", "name": "Gem Palace",
     "domain": "www.gempalacejaipur.com"},
    {"state": "Uttar Pradesh", "city": "Lucknow", "name": "Lala Jugal Kishore Jewellers",
     "domain": "www.lalajugalkishore.com"},
    {"state": "Odisha", "city": "Bhubaneswar", "name": "Abhushan Jewellers",
     "domain": "www.abhushan.com"},
    {"state": "Assam", "city": "Guwahati", "name": "Rambhajo Jewellers",
     "domain": "www.rambhajo.com"},
    {"state": "Delhi", "city": "New Delhi", "name": "Sawansukha Jewellers",
     "domain": "www.sawansukha.com"},
    {"state": "Bihar", "city": "Patna", "name": "Chandan Jewellers",
     "domain": "www.chandanjewellers.com"},
    {"state": "Goa", "city": "Margao", "name": "Damodar Jewellers",
     "domain": "www.damodarjewellers.com"},

    # ---- 2026-10-20 product breakups ----
    # Added the same day from product pages rather than a rate board:
    # P.C. Chandra (Kolkata; metal value / net weight on a 22KT bangle),
    # Abharan (Udupi; its "Daily Rates" popup is years stale but each coin's
    # breakup uses today's rate), NAC (Chennai; "Metal Rate" line in the
    # breakup) and Prince Jewellery (Chennai; a rate strip on every page).
    #
    # ---- 2026-10-20 second sweep: Hyderabad, Kolkata and North India ----
    # 125 more names checked (homepage and rate pages, plain and rendered).
    # Added to the board: Mehta Jewellers (Prashant Vihar, Delhi; 22K),
    # Reliance Jewels (national; 24K only - its own 22K figure reads Rs 6,682,
    # a site error) and Jewel One (15 showrooms in Tamil Nadu; 22K).
    # Nothing in Hyderabad or Kolkata qualified: the chains there that have
    # websites (PMJ, Manepally, Musaddilal, Kalasha, Mangatrai, Krishna
    # Pearls, Anjali, P C Chandra, B C Sen, M P Jewellers, Sankar) show no
    # rate online. Re-checked weekly in case that changes.
    {"state": "Telangana", "city": "Hyderabad", "name": "Mangatrai Pearls & Jewellers",
     "domain": "www.mangatrai.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "Krishna Pearls & Jewellers",
     "domain": "www.krishnapearls.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "Musaddilal Jewellers",
     "domain": "www.musaddilal.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "Kalasha Fine Jewels",
     "domain": "www.kalashajewels.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "Chandana Brothers",
     "domain": "www.chandanabrothers.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "RS Brothers Jewellery",
     "domain": "www.rsbrothers.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "South India Shopping Mall",
     "domain": "www.southindiashoppingmall.com"},
    {"state": "Telangana", "city": "Hyderabad", "name": "AGS Jewellers",
     "domain": "www.agsjewellers.com"},
    {"state": "West Bengal", "city": "Kolkata", "name": "M P Jewellers",
     "domain": "www.mpjewellers.com"},
    {"state": "West Bengal", "city": "Kolkata", "name": "Sankar Jewellers",
     "domain": "www.sankarjewellers.com"},
    {"state": "West Bengal", "city": "Kolkata", "name": "Kalpataru Jewellers",
     "domain": "www.kalpatarujewellers.com"},
    {"state": "Odisha", "city": "Bhubaneswar", "name": "Lalchand Jewellers",
     "domain": "www.lalchandjewellers.com"},
    {"state": "Delhi", "city": "New Delhi", "name": "Hazoorilal Legacy",
     "domain": "www.hazoorilal.com"},
    {"state": "Delhi", "city": "New Delhi", "name": "Dwarkadas Chandumal",
     "domain": "www.dcjewellers.com"},
    {"state": "Delhi", "city": "New Delhi", "name": "Bhola Sons Jewellers",
     "domain": "www.bholasons.com"},
    {"state": "Uttar Pradesh", "city": "Kanpur", "name": "Paras Jewellers",
     "domain": "www.parasjewellers.com"},
    {"state": "Rajasthan", "city": "Jaipur", "name": "Amrapali Jewels",
     "domain": "www.amrapalijewels.com"},
    {"state": "Rajasthan", "city": "Jaipur", "name": "Birdhichand Ghanshyamdas",
     "domain": "www.birdhichand.com"},
]
