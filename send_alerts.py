#!/usr/bin/env python3
"""Send the daily gold-rate digest to subscribers via Resend.

Runs after the scrape. No-ops unless RESEND_API_KEY is set. Emails each
subscriber at most once per calendar day (last_emailed guard), personalised,
with a one-click unsubscribe link. Safe to run on every scrape - the guard
prevents duplicates.
"""

from __future__ import annotations

import os
import statistics
from datetime import datetime, timezone, timedelta

import requests
from supabase import create_client

SITE_URL = "https://mygoldrates.com"
PURITY_FRACTION = {"24K": 0.999, "22K": 0.916, "18K": 0.750, "14K": 0.583}
IST = timezone(timedelta(hours=5, minutes=30))


def inr(v):
    """Indian-style grouping: 1,23,456."""
    s = f"{v:,.0f}"
    parts = s.split(",")
    if len(parts) <= 2:
        return "₹" + s
    digits = parts[0] + "".join(parts[1:-1])
    groups = []
    while len(digits) > 2:
        groups.insert(0, digits[-2:])
        digits = digits[:-2]
    if digits:
        groups.insert(0, digits)
    return "₹" + ",".join(groups) + "," + parts[-1]


def ladder(c):
    return {p: c * f for p, f in PURITY_FRACTION.items()}


def email_html(first, date, med, low, low_brand, unsub):
    """Branded HTML digest. Inline styles - email clients ignore <style>."""
    row = ('<tr><td style="padding:8px 0;color:#4A5A50;font-size:14px">{k}</td>'
           '<td style="padding:8px 0;text-align:right;font-family:monospace;'
           'font-size:15px;color:#152420;font-weight:600">{v}</td></tr>')
    rows = (row.format(k="24K (999) median", v=inr(med["24K"]) + " / g")
            + row.format(k="22K (916) median", v=inr(med["22K"]) + " / g")
            + row.format(k="18K (750) median", v=inr(med["18K"]) + " / g"))
    return f"""\
<!DOCTYPE html><html><body style="margin:0;background:#FBF9F4;
padding:24px 12px;font-family:Arial,Helvetica,sans-serif;color:#152420">
  <table role="presentation" width="100%" style="max-width:520px;margin:0 auto;
  background:#FFFFFF;border:1px solid #E7E1D3;border-radius:14px;overflow:hidden">
    <tr><td style="background:#152420;padding:22px 26px">
      <div style="font-size:20px;letter-spacing:3px;color:#F6F1E3">
        GOLD<span style="color:#D9B24A">RATES</span></div>
      <div style="color:#B9C2B4;font-size:13px;margin-top:2px">
        Gold Rate Today &middot; {date}</div>
    </td></tr>
    <tr><td style="padding:24px 26px">
      <p style="margin:0 0 14px;font-size:15px">Hi {first},</p>
      <p style="margin:0 0 18px;font-size:15px;color:#4A5A50">
        Today's median gold rate across India's leading jewellers, per gram,
        pre-GST:</p>
      <table role="presentation" width="100%"
      style="border-top:1px solid #E7E1D3;border-bottom:1px solid #E7E1D3">
        {rows}
      </table>
      <div style="margin:20px 0;padding:14px 16px;background:#F4F7F2;
      border:1px solid #cfe0d6;border-radius:10px">
        <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;
        color:#1E5C46">Lowest 24K today</div>
        <div style="font-size:20px;font-family:monospace;color:#152420;
        margin-top:4px">{inr(low['24K'])} / g
          <span style="font-size:14px;color:#4A5A50">&mdash; {low_brand}</span>
        </div>
      </div>
      <a href="{SITE_URL}/" style="display:inline-block;background:#D9B24A;
      color:#1A1508;text-decoration:none;font-weight:bold;font-size:14px;
      padding:12px 22px;border-radius:999px">See all {14} jewellers &rarr;</a>
    </td></tr>
    <tr><td style="padding:16px 26px;background:#FBF9F4;border-top:1px solid
    #E7E1D3;font-size:11px;color:#79847D">
      <p style="margin:0 0 6px">Rates are indicative and pre-GST; confirm with
      the jeweller before purchase. Not investment advice.</p>
      <p style="margin:0">You're getting this because you subscribed at
      mygoldrates.com. <a href="{unsub}" style="color:#79847D">Unsubscribe</a>.</p>
    </td></tr>
  </table>
</body></html>"""


def main():
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        print("alerts: RESEND_API_KEY not set - skipping")
        return
    frm = os.environ.get("ALERTS_FROM", "GoldRates <alerts@mygoldrates.com>")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    today = datetime.now(timezone.utc).date().isoformat()

    rows = sb.table("rates").select("*, brands(name)") \
             .eq("rate_date", today).execute().data
    live = [r for r in rows if r.get("brands") and r.get("canonical_24k_pre_gst")
            and r["status"] == "published"]
    if not live:
        print("alerts: no published rates today - skipping")
        return
    median24 = statistics.median(r["canonical_24k_pre_gst"] for r in live)
    lowest = min(live, key=lambda r: r["canonical_24k_pre_gst"])
    med, low = ladder(median24), ladder(lowest["canonical_24k_pre_gst"])
    date = datetime.now(IST).strftime("%d %B %Y")

    try:
        subs = sb.table("inquiries") \
                 .select("id, name, email, unsub_token, last_emailed").execute().data
    except Exception as e:
        print(f"alerts: cannot read subscribers (run the emailer SQL?): {e}")
        return
    pending = [s for s in subs if s.get("email") and s.get("unsub_token")
               and (not s.get("last_emailed") or s["last_emailed"] < today)]
    if not pending:
        print("alerts: nobody to email today")
        return

    sent = 0
    for s in pending:
        first = (s.get("name") or "there").strip().split(" ")[0] or "there"
        unsub = f"{SITE_URL}/unsubscribe.html?t={s['unsub_token']}"
        html = email_html(first, date, med, low, lowest["brands"]["name"], unsub)
        try:
            r = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"from": frm, "to": [s["email"]],
                      "subject": f"Gold Rate Today - {date}", "html": html,
                      "headers": {"List-Unsubscribe": f"<{unsub}>",
                                  "List-Unsubscribe-Post":
                                      "List-Unsubscribe=One-Click"}},
                timeout=30)
            if r.status_code < 300:
                sb.table("inquiries").update({"last_emailed": today}) \
                  .eq("id", s["id"]).execute()
                sent += 1
            else:
                print(f"  send failed {s['email']}: {r.status_code} {r.text[:140]}")
        except requests.RequestException as e:
            print(f"  send error {s['email']}: {type(e).__name__}")
    print(f"alerts: sent {sent}/{len(pending)}")


if __name__ == "__main__":
    main()
