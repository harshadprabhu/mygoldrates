#!/usr/bin/env python3
"""Send the daily gold-rate digest to subscribers via Brevo.

Runs after the scrape. No-ops unless BREVO_API_KEY is set. Emails each
subscriber at most once per calendar day (last_emailed guard), personalised,
with a one-click unsubscribe link. Safe to run on every scrape - the guard
prevents duplicates.
"""

from __future__ import annotations

import os
import statistics
import sys
from datetime import datetime, timezone, timedelta

import requests
from supabase import create_client

try:
    from generate_site import REGION_MAP   # regional slugs to exclude
except Exception:
    REGION_MAP = {}

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


def email_html(first, date, med, low, low_brand, unsub, n_brands=14):
    """Branded HTML digest (refreshed design). Inline styles - email clients
    ignore <style>. Text wordmark (no heavy logo image) + one gold button:
    looks premium and is lighter for Primary-inbox placement."""
    def prow(label, val):
        return (
            '<tr>'
            '<td style="padding:11px 2px;border-bottom:1px solid #eee7d8;'
            'font-size:14px;color:#514b41">' + label + '</td>'
            '<td style="padding:11px 2px;border-bottom:1px solid #eee7d8;'
            'font-size:15px;color:#1f1c17;text-align:right;font-weight:bold">'
            + val + ' <span style="color:#9a9284;font-weight:normal;'
            'font-size:12px">/ g</span></td></tr>')
    return f"""\
<!DOCTYPE html><html><body style="margin:0;background:#e9e6df;
padding:26px 12px;font-family:Arial,Helvetica,sans-serif;color:#2c2a26">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0"
  style="width:600px;max-width:600px;margin:0 auto;background:#ffffff;
  border-radius:16px;overflow:hidden;border:1px solid #e7e1d3">
    <tr><td style="height:4px;background:linear-gradient(90deg,#8C6A18,#E3BF63 45%,#F4E3A6 55%,#C79A2E);font-size:0;line-height:0">&nbsp;</td></tr>
    <tr><td style="background:#0b0805;background:linear-gradient(135deg,#1a1307 0%,#0b0805 58%,#17110a 100%);padding:26px 30px 22px">
      <div style="font-family:Georgia,'Times New Roman',serif;font-size:27px;letter-spacing:1.5px;line-height:1">
        <span style="color:#efe8d6">My</span><span style="color:#e6c268">Gold</span><span style="color:#efe8d6">Rates</span><span style="color:#9a8f78">.com</span>
      </div>
      <div style="margin-top:11px;font-family:Arial,sans-serif;font-size:11px;letter-spacing:2.5px;text-transform:uppercase;color:#d3ad4e">
        Gold Rate Today &nbsp;&middot;&nbsp; {date}</div>
    </td></tr>
    <tr><td style="padding:28px 30px 8px">
      <p style="margin:0 0 4px;font-size:15px;color:#3b3833">Good morning, {first}</p>
      <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#6b6459">
        Here's today's median gold rate across India's leading jewellers -
        per gram, before GST.</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
      style="background:#fbf7ec;border:1px solid #efe2c2;border-radius:12px">
        <tr><td style="padding:20px 22px">
          <div style="font-family:Arial,sans-serif;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#a98f45">24K &middot; 999 fine &middot; median</div>
          <div style="font-family:Georgia,serif;font-size:40px;line-height:1.05;color:#1f1c17;font-weight:bold;margin-top:6px">{inr(med['24K'])}<span style="font-size:17px;color:#8a8377;font-weight:normal;font-family:Arial,sans-serif"> / gram</span></div>
        </td></tr>
      </table>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px">
        {prow("22K &middot; 916", inr(med['22K']))}
        {prow("18K &middot; 750", inr(med['18K']))}
      </table>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
      style="margin-top:18px;background:#f3f7f2;border:1px solid #cfe0d6;border-radius:12px">
        <tr><td style="padding:14px 18px">
          <div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#2f7a58;font-weight:bold">Lowest 24K today</div>
          <div style="margin-top:5px;font-size:18px;color:#1f1c17;font-family:Georgia,serif">{inr(low['24K'])} <span style="font-size:14px;color:#5a6b5f;font-family:Arial,sans-serif">/g &nbsp;&middot;&nbsp; {low_brand}</span></div>
        </td></tr>
      </table>
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 6px">
        <tr><td style="border-radius:999px;background:linear-gradient(100deg,#8C6A18,#D9B24A 48%,#C79A2E)">
          <a href="{SITE_URL}/" style="display:inline-block;padding:12px 26px;font-family:Arial,sans-serif;font-size:14px;font-weight:bold;color:#1a1508;text-decoration:none">Compare all {n_brands} jewellers &rarr;</a>
        </td></tr>
      </table>
      <p style="margin:12px 0 4px;font-size:12px;color:#9a9284">Prices are indicative and pre-GST; confirm the billed rate with the jeweller. Not investment advice.</p>
    </td></tr>
    <tr><td style="padding:16px 30px 22px;background:#faf8f2;border-top:1px solid #efe9db;font-family:Arial,sans-serif;font-size:11px;color:#8f887c;line-height:1.6">
      You're receiving this because you subscribed at mygoldrates.com.<br>
      <a href="{unsub}" style="color:#8f887c">Unsubscribe</a> &nbsp;&middot;&nbsp; <a href="{SITE_URL}/" style="color:#8f887c">mygoldrates.com</a>
    </td></tr>
  </table>
</body></html>"""


def parse_sender(raw):
    """'GoldRates <alerts@mygoldrates.com>' -> ('GoldRates', 'alerts@...')."""
    raw = (raw or "").strip()
    if "<" in raw and ">" in raw:
        name = raw[:raw.index("<")].strip() or "GoldRates"
        email = raw[raw.index("<") + 1:raw.index(">")].strip()
        return name, email
    return "GoldRates", (raw or "alerts@mygoldrates.com")


def latest_published_rates(sb, lookback_days=10):
    """Most recent day that has published rates - today, or the latest prior
    day within the lookback window. Carries forward on weekends, holidays, and
    missed/failed scrapes so the digest always has real numbers to send.
    Returns (rows_for_that_day, rate_date_iso). ([], None) if nothing found.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    since = (datetime.now(timezone.utc)
             - timedelta(days=lookback_days)).date().isoformat()
    rows = sb.table("rates").select("*, brands(name, slug)") \
             .lte("rate_date", today).gte("rate_date", since) \
             .eq("status", "published") \
             .order("rate_date", desc=True).execute().data
    live = [r for r in rows if r.get("brands") and r.get("canonical_24k_pre_gst")]
    if not live:
        return [], None
    as_of = max(r["rate_date"] for r in live)
    return [r for r in live if r["rate_date"] == as_of], as_of


def main():
    key = os.environ.get("BREVO_API_KEY", "").strip()
    if not key:
        # Emails are mandatory - fail loudly instead of a silent green no-op so
        # a missing secret is caught, not shrugged off.
        print("alerts: BREVO_API_KEY not set - cannot send", file=sys.stderr)
        sys.exit(1)
    from_name, from_email = parse_sender(
        os.environ.get("ALERTS_FROM", "GoldRates <alerts@mygoldrates.com>"))
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    today = datetime.now(timezone.utc).date().isoformat()

    live, rate_as_of = latest_published_rates(sb)
    if not live:
        print("alerts: no published rates in the last 10 days - skipping")
        return
    if rate_as_of != today:
        print(f"alerts: no rates for {today}; carrying forward {rate_as_of}")
    # Median + lowest over NATIONAL brands only (regional excluded).
    national = [r for r in live
                if (r["brands"] or {}).get("slug") not in REGION_MAP]
    base = national or live
    median24 = statistics.median(r["canonical_24k_pre_gst"] for r in base)
    lowest = min(base, key=lambda r: r["canonical_24k_pre_gst"])
    med, low = ladder(median24), ladder(lowest["canonical_24k_pre_gst"])
    n_brands = len(base)
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
        html = email_html(first, date, med, low, lowest["brands"]["name"],
                          unsub, n_brands)
        to = {"email": s["email"]}
        if s.get("name"):
            to["name"] = s["name"].strip()
        try:
            r = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": key, "accept": "application/json",
                         "content-type": "application/json"},
                json={"sender": {"name": from_name, "email": from_email},
                      "to": [to],
                      "subject": f"Gold Rate Today - {date}",
                      "htmlContent": html,
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
    # Recipients that failed keep their old last_emailed (updated only on
    # success), so the next scheduled run of the day retries just them. If the
    # whole batch failed it's a systemic problem (Brevo down/auth/sender
    # unverified) - fail the run so it's visible and the next run retries.
    if pending and sent == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
