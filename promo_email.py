#!/usr/bin/env python3
"""One-off announcement email: meet Sona, the jewellery assistant.

    python promo_email.py --preview out.html   write the email for one sample
                                               subscriber; sends nothing
    python promo_email.py --to you@example.com send one test copy (not recorded)
    python promo_email.py --send               send to every subscriber who has
                                               not had this campaign yet

Every send is recorded in email_campaigns, so running --send again never
emails anyone twice. Each email carries the reader's own invite link and a
one-click unsubscribe. The example answers use today's real rates.
"""
import argparse
import os
import sys
from datetime import datetime

import send_alerts as SA

CAMPAIGN = "sona-launch-2026-10"
SUBJECT = "Meet Sona: ask anything before you buy gold (new and free)"


def examples(live):
    """Three questions and Sona's answers, from today's rates."""
    national = [r for r in live if (r["brands"] or {}).get("slug") not in SA.REGION_MAP] or live
    low = min(national, key=lambda r: r["canonical_24k_pre_gst"])
    high = max(national, key=lambda r: r["canonical_24k_pre_gst"])
    r22 = lambda r: r["canonical_24k_pre_gst"] * 22 / 24
    gap10 = (r22(high) - r22(low)) * 10
    out = [("Which jeweller has the cheapest 22K today?",
            f"{low['brands']['name']}, at {SA.inr(r22(low))}/g. The dearest national "
            f"jeweller is {SA.inr(gap10)} more on 10 g.")]
    line = SA.offers_line(live)
    if line:
        out.append(("Which offer actually saves me the most?", line + "."))
    gold = r22(low) * 10
    out.append(("What does a 10 g 22K chain cost?",
                f"About {SA.inr(gold * 1.03)} for the gold with GST at {low['brands']['name']}, "
                "plus the jeweller's making charge - Sona works it out for any jeweller and weight."))
    return out


def html(first, qa, invite, unsub, date):
    site = SA.SITE_URL
    rows = "".join(
        f'<tr><td style="padding:0 0 12px">'
        f'<div style="display:inline-block;background:#1a1405;color:#f6e7b8;border-radius:14px 14px 4px 14px;'
        f'padding:9px 13px;font-size:14px;font-weight:bold">{q}</div><br>'
        f'<div style="display:inline-block;margin-top:6px;background:#fbf7ec;border:1px solid #efe2c2;color:#2c2a26;'
        f'border-radius:14px 14px 14px 4px;padding:10px 13px;font-size:14px;line-height:1.5">'
        f'<b style="color:#8C6A18">Sona:</b> {a}</div></td></tr>' for q, a in qa)
    return f"""\
<!DOCTYPE html><html><body style="margin:0;background:#e9e6df;padding:26px 12px;font-family:Arial,Helvetica,sans-serif;color:#2c2a26">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e7e1d3">
    <tr><td style="height:4px;background:linear-gradient(90deg,#8C6A18,#E3BF63 45%,#F4E3A6 55%,#C79A2E);font-size:0;line-height:0">&nbsp;</td></tr>
    <tr><td style="background:#0b0805;background:linear-gradient(135deg,#1a1307 0%,#0b0805 58%,#17110a 100%);padding:26px 30px 24px">
      <div style="font-family:Georgia,'Times New Roman',serif;font-size:24px;letter-spacing:1.5px;line-height:1"><span style="color:#efe8d6">My</span><span style="color:#e6c268">Gold</span><span style="color:#efe8d6">Rates</span></div>
      <div style="margin-top:18px;display:inline-block;background:#e6c268;color:#1a1405;border-radius:999px;padding:3px 10px;font-size:11px;font-weight:bold;letter-spacing:1.5px">NEW &middot; FREE</div>
      <div style="margin-top:10px;font-family:Georgia,serif;font-size:30px;line-height:1.2;color:#fff3d6">Meet Sona, your jewellery assistant</div>
      <div style="margin-top:8px;font-size:14px;line-height:1.6;color:#cdbf9f">Ask anything before you buy gold &mdash; she answers instantly from today&rsquo;s real rates at every jeweller we track.</div>
    </td></tr>
    <tr><td style="padding:26px 30px 6px">
      <p style="margin:0 0 14px;font-size:15px;color:#3b3833">Hi {first},</p>
      <p style="margin:0 0 18px;font-size:14px;line-height:1.65;color:#514b41">Thank you for being one of our first subscribers. Today we&rsquo;re launching <b>Sona</b> on MyGoldRates: type a question the way you&rsquo;d ask a friend &mdash; in English or Hinglish &mdash; and get the answer with today&rsquo;s numbers. A few she answered this morning:</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:10px 0 8px">
        <tr><td style="border-radius:999px;background:linear-gradient(100deg,#8C6A18,#D9B24A 48%,#C79A2E)">
          <a href="{site}/?ask=1&amp;from=alert" style="display:inline-block;padding:13px 28px;font-size:15px;font-weight:bold;color:#1a1508;text-decoration:none">Ask Sona now &rarr;</a>
        </td></tr>
      </table>
      <p style="margin:16px 0 0;font-size:14px;line-height:1.6;color:#514b41">Also new: <a href="{site}/gold-offers-today?from=alert" style="color:#8C6A18;font-weight:bold">Gold offers today</a> &mdash; every jeweller&rsquo;s offer in one place, with what it&rsquo;s really worth after making charges and GST. And you can now ask us to email you the day 22K drops to your price.</p>
    </td></tr>
    <tr><td style="padding:18px 30px 24px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fbf7ec;border:1px solid #efe2c2;border-radius:12px">
        <tr><td style="padding:16px 18px">
          <div style="font-size:16px;font-weight:bold;color:#1f1c17">&#127873; Know someone buying gold soon?</div>
          <div style="margin-top:6px;font-size:13.5px;line-height:1.6;color:#514b41">Send them your personal invite link. When they join, we&rsquo;ll email you to say who joined through you.</div>
          <div style="margin-top:10px;font-size:15px"><a href="{invite}" style="color:#8C6A18;font-weight:bold">{invite}</a></div>
        </td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:16px 30px 22px;background:#faf8f2;border-top:1px solid #efe9db;font-size:11px;color:#8f887c;line-height:1.6">
      You're receiving this one-off announcement because you subscribed at mygoldrates.com. {date}.<br>
      <a href="{unsub}" style="color:#8f887c">Unsubscribe</a>
    </td></tr>
  </table>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preview")
    g.add_argument("--to")
    g.add_argument("--send", action="store_true")
    args = ap.parse_args()

    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    live, _ = SA.latest_published_rates(sb)
    if not live:
        sys.exit("promo: no published rates - not sending")
    qa = examples(live)
    date = datetime.now(SA.IST).strftime("%d %B %Y")
    subs = sb.table("inquiries").select("name, email, unsub_token").execute().data
    subs = [s for s in subs if s.get("email") and s.get("unsub_token")]
    codes = SA.ensure_ref_codes(sb, subs)

    def build(s):
        first = (s.get("name") or "there").strip().split(" ")[0] or "there"
        unsub = f"{SA.SITE_URL}/unsubscribe.html?t={s['unsub_token']}"
        return html(first, qa, SA.ref_link(codes.get(s["email"].lower())), unsub, date), unsub

    if args.preview:
        body, _ = build({"name": "Asha", "email": "sample@example.com",
                         "unsub_token": "00000000-0000-0000-0000-000000000000"})
        open(args.preview, "w", encoding="utf-8").write(body)
        print(f"promo: preview written to {args.preview}; nothing sent")
        return

    key = os.environ.get("BREVO_API_KEY", "").strip()
    if not key:
        sys.exit("promo: BREVO_API_KEY not set")
    from_name, from_email = SA.parse_sender(
        os.environ.get("ALERTS_FROM", "GoldRates <alerts@mygoldrates.com>"))

    def send(to_email, body, unsub):
        r = SA.requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": key, "accept": "application/json", "content-type": "application/json"},
            json={"sender": {"name": from_name, "email": from_email}, "to": [{"email": to_email}],
                  "subject": SUBJECT, "htmlContent": body,
                  "headers": {"List-Unsubscribe": f"<{unsub}>",
                              "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}},
            timeout=30)
        return r.status_code < 300

    if args.to:
        sample = next((s for s in subs if s["email"].lower() == args.to.lower()), None) or \
            {"name": "", "email": args.to, "unsub_token": "00000000-0000-0000-0000-000000000000"}
        body, unsub = build(sample)
        print("promo: test copy", "sent" if send(args.to, body, unsub) else "FAILED")
        return

    done = {r["email"].lower() for r in sb.table("email_campaigns").select("email")
            .eq("campaign", CAMPAIGN).execute().data}
    todo = [s for s in subs if s["email"].lower() not in done]
    sent = 0
    for s in todo:
        body, unsub = build(s)
        if send(s["email"], body, unsub):
            sb.table("email_campaigns").insert({"campaign": CAMPAIGN, "email": s["email"].lower()}).execute()
            sent += 1
    print(f"promo: sent {sent} of {len(todo)} ({len(done)} had it already)")


if __name__ == "__main__":
    main()
