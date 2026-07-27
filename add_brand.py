#!/usr/bin/env python3
"""One-off: add/update a jeweller brand row (regional or national)."""
import json
import os
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"],
                   os.environ["SUPABASE_SERVICE_KEY"])
sample = sb.table("brands").select("*").limit(1).execute().data
cols = set(sample[0].keys()) if sample else set()
print("brand columns:", sorted(cols))

b = json.loads(os.environ["BRAND_JSON"])
if cols:
    b = {k: v for k, v in b.items() if k in cols}

existing = sb.table("brands").select("id,slug,rate_url") \
             .eq("slug", b["slug"]).execute().data
if existing:
    sb.table("brands").update(b).eq("slug", b["slug"]).execute()
    print("updated", b["slug"], "(id", existing[0]["id"], ")")
else:
    sb.table("brands").insert(b).execute()
    print("inserted", b["slug"])
