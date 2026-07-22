#!/usr/bin/env python3
"""One-off: send today's digest directly to TEST_EMAIL (no list touched)."""
import os
import statistics
from datetime import datetime, timezone

import requests
from supabase import create_client

from send_alerts import email_html, ladder, parse_sender, IST


def main():
    target = os.environ["TEST_EMAIL"].strip()
    key = os.environ["BREVO_API_KEY"].strip()
    from_name, from_email = parse_sender(
        os.environ.get("ALERTS_FROM", "GoldRates <alerts@mygoldrates.com>"))
    sb = create_client(os.environ["SUPABASE_URL"],
                       os.environ["SUPABASE_SERVICE_KEY"])
    today = datetime.now(timezone.utc).date().isoformat()
    rows = sb.table("rates").select("*, brands(name)") \
             .eq("rate_date", today).execute().data
    live = [r for r in rows if r.get("brands") and r.get("canonical_24k_pre_gst")
            and r["status"] == "published"]
    median24 = statistics.median(r["canonical_24k_pre_gst"] for r in live)
    lowest = min(live, key=lambda r: r["canonical_24k_pre_gst"])
    med, low = ladder(median24), ladder(lowest["canonical_24k_pre_gst"])
    date = datetime.now(IST).strftime("%d %B %Y")
    html = email_html("there", date, med, low, lowest["brands"]["name"],
                      "https://mygoldrates.com/unsubscribe.html?t=test")

    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": key, "accept": "application/json",
                 "content-type": "application/json"},
        json={"sender": {"name": from_name, "email": from_email},
              "to": [{"email": target}],
              "subject": f"[TEST] Gold Rate Today - {date}",
              "htmlContent": html},
        timeout=30)
    print("send status:", r.status_code)
    print("response:", r.text[:400])


if __name__ == "__main__":
    main()
