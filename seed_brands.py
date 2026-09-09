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
    # Senco Gold - DEACTIVATED 2026-09-09: the live scrape was publishing a
    # materially wrong rate and there is no scrapeable replacement source.
    #
    # What was happening: rate_url pointed at a single product page
    #   /jewellery/sleek-n-stylish-gold-mens-chain
    # which is a 22K Yellow Gold chain. It carries gross_weight values but
    # no metal_price/net_weight pair, so extract() fell through to the
    # 'goldvalue' path and pulled ONE 22K data point - 13,961.01/g - off
    # that one chain's gold-value breakup. derive_ladder then scaled it
    # 22K -> 24K (x 24/22), giving 15,230.20, which the site published as
    # Senco's 24K board rate.
    #
    # Senco's own calculator (sencogoldanddiamonds.com/gold-price-calculator)
    # showed 24K 99.99 = 15,503.00/g at 2026-09-08 12:38:27, so we were
    # 272.80/g LOW (-1.76%). Because that made Senco the cheapest number on
    # the board it was also carrying the "lowest today" badge, steering
    # buyers there on a false premise (~5,456 misstated on a 20g purchase).
    # Drift was 1.96% off median - under OUTLIER_TOLERANCE (4%) - so the
    # existing quarantine gate never fired.
    #
    # Why no replacement URL: Senco publishes no static pre-GST board rate.
    #   - /gold-rate-today, /gold-rate, /gold-price[-today], /todays-gold-rate
    #     and similar all 404.
    #   - The calculator is a client-rendered Next.js page; extract() on its
    #     served HTML returns {} (the rate only exists after hydration, as an
    #     input value React computes).
    #   - Its data comes from api.sencogoldanddiamonds.com/calculator/list,
    #     which returns 401 Unauthorized; CORS advertises allowed headers
    #     x-store-id,token - i.e. it needs a real session token. Not a public
    #     feed, so we don't go around it.
    #   - The gold-coin listing does carry prices (~16,684/g for 24K) but
    #     that is retail INCLUDING GST and a minting premium; backing a
    #     pre-GST metal rate out of it needs invented constants, which is not
    #     a defensible basis for a board rate.
    #
    # Effect of active=False: no live row is written, so scrape.py's
    # placeholder path marks Senco `estimated` (market median) and
    # generate_site.py filters estimated rows out of the published board.
    # Senco drops off the comparison rather than showing a wrong price -
    # the intended trade: a missing brand beats a wrong "cheapest" badge.
    #
    # To re-enable: wire a render path that loads the calculator and
    # intercepts the calculator/list XHR the page itself makes (the page
    # authenticates itself - no key lifting), then read the 99.99 entry.
    # scrape.py already has render() via Playwright and a Zyte fallback, so
    # the plumbing exists; it needs the response shape confirmed against a
    # real render, which could not be done from the dev sandbox (its proxy
    # resets Chromium's connections to this host; curl works, the browser
    # does not).
    {"name": "Senco Gold", "slug": "senco",
     "domain": "sencogoldanddiamonds.com",
     "rate_url": "https://sencogoldanddiamonds.com/gold-price-calculator",
     "active": False, "includes_gst": False},
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
