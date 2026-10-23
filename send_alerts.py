#!/usr/bin/env python3
"""Send the daily gold-rate digest to subscribers via Brevo.

Runs after the collect. No-ops unless BREVO_API_KEY is set. Emails each
subscriber at most once per calendar day (last_emailed guard), personalised,
with a one-click unsubscribe link. Safe to run on every collect - the guard
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
    n = int(round(v))
    d = str(abs(n))
    if len(d) > 3:
        head, tail = d[:-3], d[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        d = ",".join(groups) + "," + tail
    return ("-" if n < 0 else "") + "₹" + d


def ladder(c):
    return {p: c * f for p, f in PURITY_FRACTION.items()}


def offers_line(live):
    """One line for the digest from today's offers page, or "" - e.g.
    "Lowest for a 10 g 22K ring today: PN Gadgil, Rs 1,55,785 with GST"."""
    try:
        import json as _json
        import offers_page
        offers = _json.load(open("docs/offers.json", encoding="utf-8"))
        try:
            mc = _json.load(open("docs/making-charges.json", encoding="utf-8"))
        except Exception:
            mc = {}
        # 22/24, exactly as the offers page computes it, so the two agree.
        r22 = {(r["brands"] or {}).get("slug"): r["canonical_24k_pre_gst"] * 22 / 24
               for r in live}
        rows = offers_page.ring_prices(offers, mc, r22)
        if not rows:
            return ""
        top = rows[0]
        return (f"Lowest for a 10 g 22K ring today, after offers: {top['name']}, "
                f"{inr(top['after'])} with GST")
    except Exception:
        return ""


# ------------------------------------------------------------- referrals
REF_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"     # no 0/O, 1/I/L


def new_code(taken):
    import secrets
    while True:
        c = "".join(secrets.choice(REF_ALPHABET) for _ in range(7))
        if c not in taken:
            taken.add(c)
            return c


def ensure_ref_codes(sb, subs):
    """A personal invite code for every subscriber who has none yet. New rows
    only; an existing code never changes. Returns {email_lower: code}."""
    try:
        rows = sb.table("referral_codes").select("email, code").execute().data
    except Exception as e:
        print(f"referrals: cannot read codes (run sql/assistant_referrals.sql?): {e}")
        return {}
    codes = {r["email"].lower(): r["code"] for r in rows}
    taken = set(codes.values())
    new = []
    for s in subs:
        em = (s.get("email") or "").strip().lower()
        if em and em not in codes:
            codes[em] = new_code(taken)
            new.append({"email": em, "code": codes[em]})
    for i in range(0, len(new), 200):
        sb.table("referral_codes").insert(new[i:i + 200]).execute()
    if new:
        print(f"referrals: {len(new)} new invite codes")
    return codes


def ref_link(code):
    return f"{SITE_URL}/?ref={code}" if code else ""


def friend_label(name, email):
    """How a referrer is told who joined: first name, or a masked email."""
    first = (name or "").strip().split(" ")[0]
    if first:
        return first
    user, _, dom = (email or "").partition("@")
    return (user[:1] + "\u2022\u2022\u2022@" + dom) if dom else "A friend"


def referral_html(first, friend, total, link, unsub):
    return f"""\
<!DOCTYPE html><html><body style="margin:0;background:#e9e6df;padding:26px 12px;font-family:Arial,Helvetica,sans-serif;color:#2c2a26">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e7e1d3">
    <tr><td style="height:4px;background:linear-gradient(90deg,#8C6A18,#E3BF63 45%,#F4E3A6 55%,#C79A2E);font-size:0;line-height:0">&nbsp;</td></tr>
    <tr><td style="background:#0b0805;padding:22px 30px 18px">
      <div style="font-family:Georgia,'Times New Roman',serif;font-size:24px;letter-spacing:1.5px;line-height:1"><span style="color:#efe8d6">My</span><span style="color:#e6c268">Gold</span><span style="color:#efe8d6">Rates</span></div>
    </td></tr>
    <tr><td style="padding:28px 30px 10px">
      <p style="margin:0 0 10px;font-size:15px;color:#3b3833">Hi {first},</p>
      <p style="margin:0 0 16px;font-size:20px;line-height:1.4;color:#1f1c17;font-family:Georgia,serif">&#127881; <b>{friend}</b> just joined MyGoldRates with your invite link.</p>
      <p style="margin:0 0 18px;font-size:14px;line-height:1.6;color:#6b6459">Thank you for passing it on. {friend} now gets the cheapest jeweller and today&rsquo;s gold rate every morning, just like you. Friends who have joined through you so far: <b>{total}</b>.</p>
      <p style="margin:0 0 6px;font-size:13px;color:#6b6459">Your invite link, to share again:</p>
      <p style="margin:0 0 20px;font-size:15px"><a href="{link}" style="color:#8C6A18;font-weight:bold">{link}</a></p>
    </td></tr>
    <tr><td style="padding:16px 30px 22px;background:#faf8f2;border-top:1px solid #efe9db;font-size:11px;color:#8f887c;line-height:1.6">
      You're receiving this because you subscribed at mygoldrates.com.<br><a href="{unsub}" style="color:#8f887c">Unsubscribe</a>
    </td></tr>
  </table>
</body></html>"""


def send_referral_notices(sb, key, from_name, from_email):
    """Email each referrer once per friend who joined with their link."""
    try:
        refs = sb.table("referrals").select("*").is_("notified_at", "null").execute().data
    except Exception as e:
        print(f"referrals: cannot read (run sql/assistant_referrals.sql?): {e}")
        return 0
    if not refs:
        return 0
    subs = {(s.get("email") or "").lower(): s for s in sb.table("inquiries")
            .select("name, email, unsub_token").execute().data}
    codes = {r["email"].lower(): r["code"] for r in
             sb.table("referral_codes").select("email, code").execute().data}
    allrefs = sb.table("referrals").select("referrer_email").execute().data
    sent = 0
    for r in refs:
        who = subs.get(r["referrer_email"].lower())
        friend = subs.get(r["referred_email"].lower())
        if not who or not friend or not who.get("unsub_token"):
            continue
        first = (who.get("name") or "there").strip().split(" ")[0] or "there"
        label = friend_label(friend.get("name"), friend.get("email"))
        total = sum(1 for x in allrefs if x["referrer_email"].lower() == r["referrer_email"].lower())
        unsub = f"{SITE_URL}/unsubscribe.html?t={who['unsub_token']}"
        try:
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": key, "accept": "application/json",
                         "content-type": "application/json"},
                json={"sender": {"name": from_name, "email": from_email},
                      "to": [{"email": who["email"]}],
                      "subject": f"{label} joined MyGoldRates with your invite \U0001F389",
                      "htmlContent": referral_html(first, label, total,
                                                   ref_link(codes.get(r["referrer_email"].lower())), unsub),
                      "headers": {"List-Unsubscribe": f"<{unsub}>",
                                  "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}},
                timeout=30)
            if resp.status_code < 300:
                sb.table("referrals").update(
                    {"notified_at": datetime.now(timezone.utc).isoformat()}).eq("id", r["id"]).execute()
                sent += 1
        except requests.RequestException as e:
            print(f"  referral notice error {r['id']}: {type(e).__name__}")
    print(f"referrals: {sent} referrer emails sent")
    return sent


def email_html(first, date, med, low, low_brand, unsub, n_brands=14, offers="", invite=""):
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
          <a href="{SITE_URL}/?from=alert" style="display:inline-block;padding:12px 26px;font-family:Arial,sans-serif;font-size:14px;font-weight:bold;color:#1a1508;text-decoration:none">Compare all {n_brands} jewellers &rarr;</a>
        </td></tr>
      </table>
      {('<p style="margin:16px 0 4px;font-size:14px;line-height:1.5;color:#3b3833">'
        + offers + '. <a href="' + SITE_URL + '/gold-offers-today?from=alert" '
        'style="color:#8C6A18;font-weight:bold">See every jeweller&rsquo;s offer &rarr;</a></p>')
        if offers else ''}
      {('<p style="margin:16px 0 4px;font-size:13px;line-height:1.55;color:#3b3833;background:#fbf7ec;border:1px solid #efe2c2;border-radius:10px;padding:12px 14px">'
        '&#127873; <b>Know someone buying gold?</b> Share your invite link &mdash; we&rsquo;ll email you when they join: '
        '<a href="' + invite + '" style="color:#8C6A18;font-weight:bold">' + invite + '</a></p>')
        if invite else ''}
      <p style="margin:12px 0 4px;font-size:12px;color:#9a9284">Prices are indicative and pre-GST; confirm the billed rate with the jeweller. Not investment advice.</p>
    </td></tr>
    <tr><td style="padding:16px 30px 22px;background:#faf8f2;border-top:1px solid #efe9db;font-family:Arial,sans-serif;font-size:11px;color:#8f887c;line-height:1.6">
      You're receiving this because you subscribed at mygoldrates.com.<br>
      <a href="{unsub}" style="color:#8f887c">Unsubscribe</a> &nbsp;&middot;&nbsp; <a href="{SITE_URL}/?from=alert" style="color:#8f887c">mygoldrates.com</a>
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
    missed or failed runs so the digest always has real numbers to send.
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


def price_alert_html(first, karat, rate, brand, target, date, unsub):
    """The one-off email for a price-drop alert."""
    return f"""\
<!DOCTYPE html><html><body style="margin:0;background:#e9e6df;
padding:26px 12px;font-family:Arial,Helvetica,sans-serif;color:#2c2a26">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0"
  style="width:600px;max-width:600px;margin:0 auto;background:#ffffff;
  border-radius:16px;overflow:hidden;border:1px solid #e7e1d3">
    <tr><td style="height:4px;background:linear-gradient(90deg,#8C6A18,#E3BF63 45%,#F4E3A6 55%,#C79A2E);font-size:0;line-height:0">&nbsp;</td></tr>
    <tr><td style="background:#0b0805;padding:22px 30px 18px">
      <div style="font-family:Georgia,'Times New Roman',serif;font-size:24px;letter-spacing:1.5px;line-height:1">
        <span style="color:#efe8d6">My</span><span style="color:#e6c268">Gold</span><span style="color:#efe8d6">Rates</span></div>
      <div style="margin-top:9px;font-size:11px;letter-spacing:2.5px;text-transform:uppercase;color:#d3ad4e">Price alert &nbsp;&middot;&nbsp; {date}</div>
    </td></tr>
    <tr><td style="padding:26px 30px 10px">
      <p style="margin:0 0 6px;font-size:15px;color:#3b3833">Hi {first},</p>
      <p style="margin:0 0 18px;font-size:15px;line-height:1.6;color:#3b3833">
        {karat} gold has dropped to the price you were waiting for.</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
      style="background:#f3f7f2;border:1px solid #cfe0d6;border-radius:12px">
        <tr><td style="padding:18px 22px">
          <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#2f7a58;font-weight:bold">Lowest {karat} today &middot; {brand}</div>
          <div style="font-family:Georgia,serif;font-size:36px;color:#1f1c17;font-weight:bold;margin-top:6px">{inr(rate)}<span style="font-size:15px;color:#5a6b5f;font-weight:normal;font-family:Arial,sans-serif"> / gram</span></div>
          <div style="font-size:13px;color:#5a6b5f;margin-top:4px">Your alert: {inr(target)} / gram or lower</div>
        </td></tr>
      </table>
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0 6px">
        <tr><td style="border-radius:999px;background:linear-gradient(100deg,#8C6A18,#D9B24A 48%,#C79A2E)">
          <a href="{SITE_URL}/?from=alert" style="display:inline-block;padding:12px 26px;font-size:14px;font-weight:bold;color:#1a1508;text-decoration:none">Compare today&rsquo;s rates &rarr;</a>
        </td></tr>
      </table>
      <p style="margin:12px 0 4px;font-size:12px;color:#9a9284">Pre-GST rate as published by the jeweller; confirm the billed price with them. This alert is now used up - set a new one on the site any time. Not investment advice.</p>
    </td></tr>
    <tr><td style="padding:16px 30px 22px;background:#faf8f2;border-top:1px solid #efe9db;font-size:11px;color:#8f887c;line-height:1.6">
      You're receiving this because you set a price alert at mygoldrates.com.<br>
      <a href="{unsub}" style="color:#8f887c">Unsubscribe</a>
    </td></tr>
  </table>
</body></html>"""


def send_price_alerts(sb, key, from_name, from_email, base, date):
    """Email everyone whose price-drop alert has been reached, once each.

    The rate compared is the one the site shows: today's lowest national
    jeweller rate for that purity (24K canonical x purity fraction). Only
    for people still subscribed; the alert is switched off once sent.
    Returns the number sent. Never raises: the daily digest must not be
    held up by this.
    """
    try:
        alerts = sb.table("price_alerts").select("*") \
                   .eq("active", True).execute().data
    except Exception as e:
        print(f"price alerts: cannot read alerts (run sql/price_alerts.sql?): {e}")
        return 0
    if not alerts:
        print("price alerts: none active")
        return 0
    lowest = min(base, key=lambda r: r["canonical_24k_pre_gst"])
    low = ladder(lowest["canonical_24k_pre_gst"])
    brand = lowest["brands"]["name"]
    subs = {(s.get("email") or "").lower(): s for s in sb.table("inquiries")
            .select("name, email, unsub_token").execute().data}
    sent = 0
    for a in alerts:
        rate = low.get(a["karat"])
        if rate is None or rate > float(a["target"]):
            continue
        s = subs.get(a["email"].lower())
        if not s or not s.get("unsub_token"):
            continue                      # unsubscribed since: say nothing
        first = (s.get("name") or "there").strip().split(" ")[0] or "there"
        unsub = f"{SITE_URL}/unsubscribe.html?t={s['unsub_token']}"
        try:
            r = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": key, "accept": "application/json",
                         "content-type": "application/json"},
                json={"sender": {"name": from_name, "email": from_email},
                      "to": [{"email": s["email"]}],
                      "subject": f"Price alert: {a['karat']} gold is now "
                                 f"{inr(rate)}/g",
                      "htmlContent": price_alert_html(
                          first, a["karat"], rate, brand, float(a["target"]),
                          date, unsub),
                      "headers": {"List-Unsubscribe": f"<{unsub}>",
                                  "List-Unsubscribe-Post":
                                      "List-Unsubscribe=One-Click"}},
                timeout=30)
            if r.status_code < 300:
                sb.table("price_alerts").update({
                    "active": False, "fired_rate": round(rate, 2),
                    "fired_at": datetime.now(timezone.utc).isoformat()}) \
                  .eq("id", a["id"]).execute()
                sent += 1
            else:
                print(f"  price alert failed {a['id']}: {r.status_code} {r.text[:140]}")
        except requests.RequestException as e:
            print(f"  price alert error {a['id']}: {type(e).__name__}")
    print(f"price alerts: sent {sent} of {len(alerts)} active")
    return sent


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

    # Price-drop alerts first: they are time-sensitive and independent of
    # whether anyone is due today's digest.
    send_price_alerts(sb, key, from_name, from_email, base, date)
    send_referral_notices(sb, key, from_name, from_email)

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

    offers = offers_line(live)
    codes = ensure_ref_codes(sb, subs)
    sent = 0
    for s in pending:
        first = (s.get("name") or "there").strip().split(" ")[0] or "there"
        unsub = f"{SITE_URL}/unsubscribe.html?t={s['unsub_token']}"
        html = email_html(first, date, med, low, lowest["brands"]["name"],
                          unsub, n_brands, offers,
                          ref_link(codes.get(s["email"].lower())))
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
