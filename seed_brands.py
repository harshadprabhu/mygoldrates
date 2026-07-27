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
