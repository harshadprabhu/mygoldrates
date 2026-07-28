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
    # National player (distinct from our "Jos Alukkas" = josalukkasonline.com)
    {"name": "Joyalukkas", "slug": "joyalukkas", "domain": "joyalukkas.in",
     "rate_url": "https://www.joyalukkas.in/goldrate",
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
