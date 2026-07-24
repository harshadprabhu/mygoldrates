#!/usr/bin/env python3
"""One-off: show the merged verify row, then delete test rows."""
import os
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"],
                   os.environ["SUPABASE_SERVICE_KEY"])
em = os.environ.get("VERIFY_EMAIL", "")

if em:
    rows = sb.table("inquiries").select(
        "email,name,phone,city,state,area,signup_method,google_id,"
        "google_email_verified,picture_url,locale").eq("email", em).execute().data
    print(f"=== rows for {em}: {len(rows)} (should be 1 = merged) ===")
    for r in rows:
        for k, v in r.items():
            print(f"   {k}: {v}")

# clean up any test rows so they never get emailed
for pat in ("%@example.com", "geo-%", "verify-%", "probe-%"):
    try:
        d = sb.table("inquiries").delete().like("email", pat).execute()
        print(f"deleted like {pat}: {len(d.data)}")
    except Exception as e:
        print(f"cleanup {pat}: {e}")
