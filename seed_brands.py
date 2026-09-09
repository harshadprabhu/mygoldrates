#!/usr/bin/env python3
"""Upsert regional/local jeweller brands (those with a public online rate).

Edit REGIONAL_BRANDS and run the seed-brands workflow to add more. National
brands already live in the DB; these are region-focused jewellers that publish
a real gold rate on their own website, so they are genuinely scrapeable.
"""
import os
from supabase import create_client

# region is informational (kept in code, not the DB) - see REGION_MAP in
# generate_site.py. Only DB columns are written here.
REGIONAL_BRANDS = [
    {"name": "Vaibhav Jewellers", "slug": "vaibhav",
     "domain": "vaibhavjewellers.com",
     "rate_url": "https://www.vaibhavjewellers.com/gold-rate",
     "active": True, "includes_gst": False},
    {"name": "Vummidi Bangaru", "slug": "vummidi", "domain": "vummidi.com",
     "rate_url": "https://www.vummidi.com/gold-rate-in-chennai",
     "active": True, "includes_gst": False},
    # JS/bot-walled - no static or rendered rate found; parked until we wire
    # a Zyte render for them. Kept inactive so they aren't scraped.
    {"name": "Lalithaa Jewellery", "slug": "lalithaa",
     "domain": "lalithaajewellery.com",
     "rate_url": "https://www.lalithaajewellery.com/gold-rate-today",
     "active": False, "includes_gst": False},
    {"name": "Kirtilals", "slug": "kirtilals", "domain": "kirtilals.com",
     "rate_url": "https://www.kirtilals.com/gold-rate",
     "active": False, "includes_gst": False},
    {"name": "PN Gadgil & Sons", "slug": "pngsons",
     "domain": "pngadgilandsons.com",
     "rate_url": "https://pngadgilandsons.com/gold-rates/",
     "active": True, "includes_gst": False},
    {"name": "Ranka Jewellers", "slug": "ranka", "domain": "rankajewellers.in",
     "rate_url": "https://www.rankajewellers.in/gold-rate-today",
     "active": True, "includes_gst": False},
    {"name": "Josco Jewellers", "slug": "josco", "domain": "joscogroup.com",
     "rate_url": "https://www.joscogroup.com/gold-rate",
     "active": False, "includes_gst": False},
    # trial batch - rates load via API after render (browser saw nothing);
    # parked until wired through Zyte.
    {"name": "RBZ Jewellers", "slug": "rbz", "domain": "rbzjewellers.com",
     "rate_url": "https://www.rbzjewellers.com/gold-rate",
     "active": False, "includes_gst": False},
    {"name": "Sri Kumaran", "slug": "srikumaran", "domain": "srikumaran.com",
     "rate_url": "https://www.srikumaran.com/todays-gold-rate",
     "active": False, "includes_gst": False},
    {"name": "Bhindi Jewellers", "slug": "bhindi", "domain": "bhindi.com",
     "rate_url": "https://www.bhindi.com/gold-rate",
     "active": False, "includes_gst": False},
    # corrected-domain trials (JS SPAs - let the browser-render path test)
    {"name": "Chandukaka Saraf", "slug": "chandukaka",
     "domain": "chandukakasaraf.in",
     "rate_url": "https://www.chandukakasaraf.in/todays-gold-rate/",
     "active": True, "includes_gst": False},
    {"name": "C Krishniah Chetty", "slug": "ckc",
     "domain": "ckcjewellers.com",
     "rate_url": "https://www.ckcjewellers.com/",   # rate is a homepage banner
     "active": True, "includes_gst": False},
    # National player (distinct from our "Jos Alukkas" = josalukkasonline.com).
    # JS-rendered + slow -> parked for Zyte.
    {"name": "Joyalukkas", "slug": "joyalukkas", "domain": "joyalukkas.in",
     "rate_url": "https://www.joyalukkas.in/goldrate",
     "active": True, "includes_gst": False},
    # PN Gadgil (pngjewellers.com) - upsert by slug 'png' to REPLACE the old
    # rate_url (which pointed to a single coin product page and missed today's
    # canonical rate). The /pages/metal-rates page is the brand's own daily
    # rate board and is what the site should be reading.
    {"name": "PN Gadgil", "slug": "png", "domain": "www.pngjewellers.com",
     "rate_url": "https://www.pngjewellers.com/pages/metal-rates",
     "active": True, "includes_gst": False},
    # Novel Jewels (Aditya Birla). Homepage footer banner text:
    # "Today's Gold Rate is Rs.13735 per gm (22kt)". Only 22K published in
    # raw HTML - the extract_value_per_gm_karat pattern picks it up, and
    # the site derives the 24K/18K ladder from the 22K anchor as usual.
    {"name": "Indriya", "slug": "indriya", "domain": "indriya.com",
     "rate_url": "https://www.indriya.com",
     "active": True, "includes_gst": False},
    # ORRA - diamond-jewellery-only brand. The previous rate_url pointed
    # to a specific product (round-diamond-crown-star-pendant-set-in-rose-
    # gold-osp20029) that started 404-ing around 28 Aug 2026, retiring the
    # brand's live scrape and dropping it to `estimated` daily (market
    # median filler, which generate_site.py filters out). ORRA also
    # doesn't publish a per-gram rate on any /gold-rate-today path so
    # scrape.py's path-discovery couldn't rescue it either. Anchor on a
    # bestseller product page - every ORRA product page renders the per-
    # gram gold rate straight into HTML in <span class="GoldRateGrams">
    # ...</span>. Verified live: this earrings URL currently yields
    # {'18K': 11611.72}, which the ladder converts to 24K ~ Rs 15,482/g.
    {"name": "ORRA", "slug": "orra", "domain": "www.orra.co.in",
     "rate_url": "https://www.orra.co.in/product/elegance-of-circle-astra-earrings-asn25a03-d900r1b",
     "active": True, "includes_gst": False},
    # Senco Gold - rate_url is a 24K 999.9 COIN product page, not jewellery.
    #
    # History: this previously pointed at
    #   /jewellery/sleek-n-stylish-gold-mens-chain
    # a 22K Yellow Gold chain. That page has gross_weight but no
    # metal_price/net_weight pair, so extract() fell through to 'goldvalue'
    # and returned a single 22K point (13,961.01/g) off that one chain's
    # breakup. derive_ladder scaled it 22K -> 24K (x 24/22) = 15,230.20,
    # which the site published as Senco's board rate while Senco's own
    # calculator said 15,503.00 - i.e. 272.80/g low (-1.76%). Because that
    # was the cheapest number on the board it also wore the "lowest today"
    # badge. Drift was 1.96% off median, under OUTLIER_TOLERANCE (4%), so
    # the quarantine gate never fired.
    #
    # Fix: use a pure-gold COIN page instead of a jewellery page. A 999.9
    # coin's gold-value breakup IS the 24K per-gram rate - read directly,
    # with no ladder inference from another purity, which is what made the
    # chain page fragile. Verified live against all three coin variants:
    #
    #   /jewellery/24k-1-g-9999-pure-gold-coin  -> {'24K': 15503.0}
    #   /jewellery/24k-2-g-9999-pure-gold-coin  -> {'24K': 15503.0}
    #   /jewellery/1g-24k-(995)-...-coin        -> {'24K': 15427.0}
    #
    # 15,503.00 matches Senco's calculator exactly (24K 99.99 @ 2026-09-08
    # 12:38:27). The 1g and 2g 999.9 coins agree, confirming a per-gram rate
    # is being extracted rather than a raw product price. The 995 coin
    # returning 15,427 lines up with the calculator's separate "24K (99.50)"
    # option, which is a second independent cross-check that the breakup is
    # being read correctly.
    #
    # Prefer the 1g 999.9 coin: smallest denomination, highest purity, so
    # the breakup is the cleanest possible expression of the board rate.
    # Waman Hari Pethe - DEACTIVATED 2026-09-09: publishing a fabricated
    # number. rate_url pointed at /products/whp-24kt-999-10-gm, a product
    # handle that no longer exists. The scraper's own fetch() correctly
    # calls that a 404, but the row was written by the RENDER path
    # (method was `rendered/rows`), which renders whatever the browser is
    # served - including the error page - without re-checking status. The
    # shell page carries no rate table, no "today's gold rate" text and no
    # purity-labelled rows, just scattered product prices (15808, 14041,
    # 14718, 16946...), and `rows` matched one of them. Stored 15,664.00
    # was therefore a product price, not a gold rate. It sat only +0.83%
    # off median, which is why no drift gate ever flagged it.
    #
    # No valid replacement found. WHP publishes no gold-rate page
    # (/pages/gold-rate, /pages/todays-gold-rate, /gold-rate,
    # /pages/gold-rate-today, /pages/metal-rates all 404), and their live
    # coin pages quote retail, not the board rate: the real
    # /products/whp-24kt-999-1-gm-gold-coin extracts {'24K': 17112.0},
    # ~10% over the market median - a 1g coin's minting premium, not a
    # per-gram metal rate. (Senco's coin page works because it exposes a
    # gold-value BREAKUP separating metal from making/GST; WHP's exposes
    # only the retail price, so coin pages are not universally safe.)
    #
    # Effect: falls to `estimated` and is filtered out of the published
    # board. Re-enable only against a source that quotes a pre-GST metal
    # rate - a rate page, or a coin page with a metal/making breakup.
    {"name": "Waman Hari Pethe", "slug": "whp",
     "domain": "whpjewellers.com",
     "rate_url": "https://whpjewellers.com/products/whp-24kt-999-1-gm-gold-coin",
     "active": False, "includes_gst": False},
    {"name": "Senco Gold", "slug": "senco",
     "domain": "sencogoldanddiamonds.com",
     "rate_url": "https://sencogoldanddiamonds.com/jewellery/24k-1-g-9999-pure-gold-coin",
     "active": True, "includes_gst": False},
]


def main():
    sb = create_client(os.environ["SUPABASE_URL"],
                       os.environ["SUPABASE_SERVICE_KEY"])
    sample = sb.table("brands").select("*").limit(1).execute().data
    cols = set(sample[0].keys()) if sample else set()
    for b in REGIONAL_BRANDS:
        row = {k: v for k, v in b.items() if not cols or k in cols}
        ex = sb.table("brands").select("id").eq("slug", b["slug"]).execute().data
        if ex:
            sb.table("brands").update(row).eq("slug", b["slug"]).execute()
            print("updated", b["slug"], "(id", ex[0]["id"], ")")
        else:
            sb.table("brands").insert(row).execute()
            print("inserted", b["slug"])


if __name__ == "__main__":
    main()
