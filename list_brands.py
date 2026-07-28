#!/usr/bin/env python3
"""One-off: list all jeweller brands with domain + active status."""
import os
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"],
                   os.environ["SUPABASE_SERVICE_KEY"])
rows = sb.table("brands").select("name,slug,domain,active,rate_url") \
         .order("name").execute().data
act = [r for r in rows if r["active"]]
ina = [r for r in rows if not r["active"]]
print(f"=== ACTIVE ({len(act)}) ===")
for r in sorted(act, key=lambda x: x["name"]):
    print(f"{r['name']:26} | {r.get('domain') or '?':30} | "
          f"{r.get('rate_url') or ''}")
print(f"\n=== PARKED/INACTIVE ({len(ina)}) ===")
for r in sorted(ina, key=lambda x: x["name"]):
    print(f"{r['name']:26} | {r.get('domain') or '?':30}")
print(f"\ntotal {len(rows)}")
