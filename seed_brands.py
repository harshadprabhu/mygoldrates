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
    # PN Gadgil & Sons - rate_url is the LIVE API, not the rate page.
    #
    # /gold-rates/ renders its table from
    #   goldpriceeditor.droidinfinity.com/api/external/metal-prices/1085
    # and the numbers baked into the served HTML are a stale fallback the
    # page overwrites on load. Scraping the page gave 24K = 14,450 while the
    # API returned 15,320 - 870/g, 5.7% out of date. That tripped the
    # purity-ratio check AND the 6.5%-off-median outlier gate, so the brand
    # was quarantined and disappeared from the board entirely.
    #
    # The quarantine was correct - it stopped a stale rate publishing. The
    # fix is to read the source the page itself reads. Public endpoint, no
    # auth, clean JSON, and extract_rate_json's Shape C parses it:
    #   {"rates":{"goldPrice24K":15320,"goldPrice22K":14094,...}}
    # The suffixed keys (goldPrice24K995/995GW) are the 995 rate and are
    # deliberately excluded so they cannot drag the 999 figure down.
    #
    # Note their lower karats sit above the flat ratio (18K is +3.3% over
    # 24K x 0.75), so basis_confirmed stays False - that is their real
    # pricing, not an extraction fault. Drift from median is only -0.8%,
    # well inside OUTLIER_TOLERANCE, so it publishes normally.
    {"name": "PN Gadgil & Sons", "slug": "pngsons",
     "domain": "pngadgilandsons.com",
     "rate_url": "https://goldpriceeditor.droidinfinity.com/api/external/metal-prices/1085",
     "active": True, "includes_gst": False},
    # 2026-09-13: rate_url was a 404. /gold-rate-today (and /gold-rate,
    # /metal-rates, /todays-metal-rates) all return HTTP 404 on a fully
    # themed error page. Ranka renders "Today's Metal Rates" as a SITE-WIDE
    # header strip, so that strip is present on the 404 page too - which is
    # why extract_rows kept returning a real, correct ladder
    # (24K 15730 / 22K 14630 / 18K 12585) and the brand never looked broken.
    #
    # That is the WHP failure mode with a happy ending: reading a rate off a
    # page the server is calling "not found". WHP's 404 shell had no rate
    # strip, so `rows` grabbed a product price and we published a fabricated
    # number; Ranka's does, so we got lucky. Not a distinction to depend on.
    # Pin the homepage instead - HTTP 200, same header strip, same numbers,
    # verified identical: {'24K': 15730.0, '22K': 14630.0, '18K': 12585.0}.
    #
    # Their 22K sits at 0.930 of 24K rather than the flat 0.9167, so
    # basis_confirmed stays False - that is Ranka's own pricing (the strip
    # is explicitly labelled "Rates Applicable for online store Only"), not
    # an extraction fault. +1.8% off median, inside OUTLIER_TOLERANCE.
    {"name": "Ranka Jewellers", "slug": "ranka", "domain": "rankajewellers.in",
     "rate_url": "https://www.rankajewellers.in/",
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
    # 2026-09-13: handle RENAMED, pin repaired. Senco renormalised their
    # product slugs and `24k-1-g-9999-pure-gold-coin` began returning a hard
    # 404. Their sitemap-product.xml carries the new handle - the only change
    # is a dot: `24k-1-g-999.9-pure-gold-coin`.
    #
    # Nothing broke loudly, which is the part worth noting. fetch() rejected
    # the 404 correctly, CANDIDATE_PATHS all 404'd too, and scrape_brand fell
    # through to discover_products(), which landed on
    #   /jewellery/22k-1g-916-pure-gold-bar
    # and published off its breakup as `discovered/static/goldvalue` - a
    # single 22K point laddered up to 24K, basis_confirmed False. That is
    # precisely the 22K-inference path the coin pin was introduced to
    # eliminate, silently reinstated. It landed at 15,460.36 against the coin's true 15,460.00, so
    # no drift gate could ever have caught it: the fallback was accurate, just
    # unpinned and free to wander. See pin_health.py, added with this change,
    # which now reports any brand publishing from a `discovered/` method.
    #
    # Re-verified against all three current coin handles:
    #   /jewellery/24k-1-g-999.9-pure-gold-coin  -> {'24K': 15460.0}
    #   /jewellery/24k-2-g-999.9-pure-gold-coin  -> {'24K': 15460.0}
    #   /jewellery/1g-24k-(995)-...-precious-coin -> {'24K': 15385.0}
    # 1g and 2g agreeing confirms a per-gram rate, not a product price, and
    # 15385/15460 = 0.99515 ~ 995/999.9 confirms the purity ladder reads true.
    {"name": "Senco Gold", "slug": "senco",
     "domain": "sencogoldanddiamonds.com",
     "rate_url": "https://sencogoldanddiamonds.com/jewellery/24k-1-g-999.9-pure-gold-coin",
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
