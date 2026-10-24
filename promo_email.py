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

It is written as a short personal letter (plain layout, one small picture,
links in the text, a plain-text part, from a person), which Gmail is far
likelier to put in Primary than a designed newsletter. --designed sends the
newsletter-style version instead.
"""
import argparse
import os
import sys
from datetime import datetime

import send_alerts as SA

CAMPAIGN = "sona-launch-2026-10"
SUBJECT = "Sona can now answer your gold questions"
SUBJECT_DESIGNED = "Meet Sona: ask about gold in your own language, type or talk (free)"
LETTER_FROM = "Harshad from MyGoldRates"
# The launch goes out from its own address, never the daily alerts' one:
# whatever Gmail learns about an announcement must not move the daily rate
# email out of Primary. PROMO_FROM overrides; default hello@<alerts domain>.
PROMO_LOCAL = "hello"


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
                "plus the jeweller's making charge &mdash; Sona works it out for any jeweller and weight."))
    return out


def letter(first, qa, invite, unsub):
    """The personal-letter email: (html, text)."""
    import html as H
    site = SA.SITE_URL
    ask = f"{site}/?ask=1&from=alert"
    offers = f"{site}/gold-offers-today?from=alert"
    plain = lambda x: H.unescape(x)
    p = 'style="margin:0 0 14px"'
    link = 'style="color:#8C6A18;font-weight:bold;text-decoration:underline"'
    qa_html = "".join(
        f'<tr><td style="padding:0 0 10px"><div style="background:#fbf7ec;border-left:3px solid #e0b64f;'
        f'border-radius:0 10px 10px 0;padding:11px 14px">'
        f'<div style="font-weight:bold;color:#2b2620">&ldquo;{q}&rdquo;</div>'
        f'<div style="margin-top:3px;color:#4a443b">{a}</div></div></td></tr>' for q, a in qa)
    body = f"""\
<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4efe4">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4efe4"><tr><td style="padding:22px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e9dfc8;border-radius:14px;overflow:hidden">
  <tr><td style="background:#14100a;padding:16px 22px"><a href="{site}/?from=alert"><img src="{site}/email-logo.png" width="200" height="34" alt="MyGoldRates" style="display:block;width:200px;height:34px;border:0"></a></td></tr>
  <tr><td style="height:3px;background:#e0b64f;background:linear-gradient(90deg,#8C6A18,#E3BF63 45%,#F4E3A6 55%,#C79A2E);font-size:0;line-height:0">&nbsp;</td></tr>
  <tr><td style="padding:24px 22px 8px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#2b2620">
<p {p}>Hi {first},</p>
<p {p}>I wanted to tell you about something new on MyGoldRates.</p>
<p {p}>You can now ask <b>Sona</b>, our jewellery assistant, any question before you buy gold, and she answers straight away from today&rsquo;s real rates at every jeweller we track. Type it, or tap the mic and just ask out loud &mdash; in English or in your own language: Hindi, Marathi, Gujarati, Punjabi, Bengali, Kannada, Tamil, Telugu or Malayalam.</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:4px 0 12px"><tr>
  <td style="padding-right:10px"><img src="{site}/email-sona-face.png" width="44" height="44" alt="Sona" style="display:block;width:44px;height:44px;border:0"></td>
  <td style="font-size:15px;color:#2b2620">Here is what she told me this morning:</td></tr></table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{qa_html}</table>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 18px"><tr>
  <td style="border-radius:999px;background:#d9b24a;background:linear-gradient(100deg,#b98a24,#e6c268 50%,#c79a2e)">
    <a href="{ask}" style="display:inline-block;padding:11px 22px;font-size:15px;font-weight:bold;color:#1a1405;text-decoration:none">Ask Sona a question &rarr;</a></td></tr></table>
<p {p}>We have also started putting every jeweller&rsquo;s offers in one place, with what each is really worth after making charges and GST: <a href="{offers}" {link}>gold offers today</a>. And if you tell us your target price, we will email you the day 22K drops to it.</p>
<div style="margin:0 0 16px;padding:12px 14px;border:1px dashed #e0c98a;border-radius:10px;background:#fffdf7">If a friend is buying gold soon, this is your personal invite link:<br><a href="{invite}" {link}>{invite}</a><br><span style="color:#6b6458;font-size:13.5px">When they join, we will let you know.</span></div>
<p style="margin:0 0 18px;font-size:13.5px;color:#6b6458;font-style:italic">One small request: if this email landed in your Promotions tab, please move it to Primary, so the daily rate alerts reach you too.</p>
<p style="margin:0 0 2px">Thank you for being one of our first subscribers,</p>
<p style="margin:0 0 20px"><b>Harshad</b><br><span style="color:#8C6A18">MyGoldRates</span></p>
  </td></tr>
</table>
<p style="max-width:560px;margin:12px auto 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.5;color:#8f887c;text-align:center">You are getting this because you subscribed at mygoldrates.com. <a href="{unsub}" style="color:#8f887c">Unsubscribe</a></p>
</td></tr></table></body></html>"""
    text = "\n\n".join([
        f"Hi {first},",
        "I wanted to tell you about something new on MyGoldRates.",
        "You can now ask Sona, our jewellery assistant, any question before you buy gold, and she "
        "answers straight away from today's real rates at every jeweller we track. Type it, or tap the "
        "mic and just ask out loud - in English or in your own language: Hindi, Marathi, Gujarati, "
        "Punjabi, Bengali, Kannada, Tamil, Telugu or Malayalam.",
        "Here is what she told me this morning:",
        *[f'"{plain(q)}"\n{plain(a)}' for q, a in qa],
        f"Try her here: {ask}",
        "We have also started putting every jeweller's offers in one place, with what each is really "
        f"worth after making charges and GST: {offers}\nAnd if you tell us your target price, we will "
        "email you the day 22K drops to it.",
        f"If a friend is buying gold soon, this is your personal invite link: {invite}\n"
        "When they join, we will let you know.",
        "One small request: if this email landed in your Promotions tab, please move it to Primary, "
        "so the daily rate alerts reach you too.",
        "Thank you for being one of our first subscribers,\nHarshad\nMyGoldRates",
        f"--\nYou are getting this because you subscribed at mygoldrates.com. Unsubscribe: {unsub}"])
    return body, text


def html(first, qa, invite, unsub, date):
    site = SA.SITE_URL
    rows = "".join(
        f'<tr><td style="padding:0 0 12px">'
        f'<div style="display:inline-block;background:#1a1405;color:#f6e7b8;border-radius:14px 14px 4px 14px;'
        f'padding:9px 13px;font-size:14px;font-weight:bold">{q}</div><br>'
        f'<div style="display:inline-block;margin-top:6px;background:#fbf7ec;border:1px solid #efe2c2;color:#2c2a26;'
        f'border-radius:14px 14px 14px 4px;padding:10px 13px;font-size:14px;line-height:1.5">'
        f'<img src="{SA.SITE_URL}/email-sona-face.png" width="22" height="22" alt="" '
        f'style="width:22px;height:22px;vertical-align:-6px;margin-right:4px;border:0">'
        f'<b style="color:#8C6A18">Sona:</b> {a}</div></td></tr>' for q, a in qa)
    return f"""\
<!DOCTYPE html><html><body style="margin:0;background:#e9e6df;padding:26px 12px;font-family:Arial,Helvetica,sans-serif;color:#2c2a26">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e7e1d3">
    <tr><td style="height:4px;background:linear-gradient(90deg,#8C6A18,#E3BF63 45%,#F4E3A6 55%,#C79A2E);font-size:0;line-height:0">&nbsp;</td></tr>
    <tr><td style="background:#0b0805;background:linear-gradient(135deg,#1a1307 0%,#0b0805 58%,#17110a 100%);padding:26px 30px 24px">
      <div style="font-family:Georgia,'Times New Roman',serif;font-size:24px;letter-spacing:1.5px;line-height:1"><span style="color:#efe8d6">My</span><span style="color:#e6c268">Gold</span><span style="color:#efe8d6">Rates</span></div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px"><tr>
        <td valign="middle" style="padding-right:14px">
          <div style="display:inline-block;background:#e6c268;color:#1a1405;border-radius:999px;padding:3px 10px;font-size:11px;font-weight:bold;letter-spacing:1.5px">NEW &middot; FREE</div>
          <div style="margin-top:10px;font-family:Georgia,serif;font-size:30px;line-height:1.2;color:#fff3d6">Meet Sona, your jewellery assistant</div>
          <div style="margin-top:8px;font-size:14px;line-height:1.6;color:#cdbf9f">Ask anything before you buy gold &mdash; type it, or just say it out loud. She answers instantly from today&rsquo;s real rates at every jeweller we track.</div>
        </td>
        <td valign="middle" width="110" style="width:110px;text-align:center">
          <a href="{site}/?ask=1&amp;from=alert"><img src="{site}/email-sona.png" width="110" height="120" alt="Sona, the MyGoldRates assistant" style="display:block;width:110px;height:120px;border:0;margin:0 auto"></a>
        </td>
      </tr></table>
      <div style="margin-top:12px;font-size:13px;line-height:1.7;color:#e6c268">English &middot; &#2361;&#2367;&#2344;&#2381;&#2342;&#2368; &middot; &#2350;&#2352;&#2366;&#2336;&#2368; &middot; &#2711;&#2753;&#2716;&#2736;&#2750;&#2724;&#2752; &middot; &#2602;&#2672;&#2588;&#2622;&#2604;&#2624; &middot; &#2476;&#2494;&#2434;&#2482;&#2494; &middot; &#3221;&#3240;&#3277;&#3240;&#3233; &middot; &#2980;&#2990;&#3007;&#2996;&#3021; &middot; &#3108;&#3142;&#3122;&#3137;&#3095;&#3137; &middot; &#3374;&#3378;&#3375;&#3390;&#3379;&#3330;</div>
    </td></tr>
    <tr><td style="padding:26px 30px 6px">
      <p style="margin:0 0 14px;font-size:15px;color:#3b3833">Hi {first},</p>
      <p style="margin:0 0 18px;font-size:14px;line-height:1.65;color:#514b41">Thank you for being one of our first subscribers. Today we&rsquo;re launching <b>Sona</b> on MyGoldRates: type a question the way you&rsquo;d ask a friend, or tap the &#127908; and simply ask out loud &mdash; in English, Hindi, Marathi, Gujarati, Punjabi, Bengali, Kannada, Tamil, Telugu or Malayalam. She answers in your language with today&rsquo;s numbers, and can read the answer out to you. A few she answered this morning:</p>
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
    ap.add_argument("--designed", action="store_true", help="the newsletter-style version")
    args = ap.parse_args()

    def compose(first, invite, unsub):
        """(html, text or None, subject, sender name or None)"""
        if args.designed:
            return html(first, qa, invite, unsub, date), None, SUBJECT_DESIGNED, None
        b, tx = letter(first, qa, invite, unsub)
        return b, tx, SUBJECT, LETTER_FROM

    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    live, _ = SA.latest_published_rates(sb)
    if not live:
        sys.exit("promo: no published rates - not sending")
    qa = examples(live)
    date = datetime.now(SA.IST).strftime("%d %B %Y")
    if args.preview:                 # reads rates only; writes nothing anywhere
        body, text, _, _ = compose("Asha", SA.ref_link("SAMPLE1"),
                                   f"{SA.SITE_URL}/unsubscribe.html?t=00000000-0000-0000-0000-000000000000")
        open(args.preview, "w", encoding="utf-8").write(body)
        if text:
            open(args.preview + ".txt", "w", encoding="utf-8").write(text)
        print(f"promo: preview written to {args.preview}; nothing sent")
        return
    subs = sb.table("inquiries").select("name, email, unsub_token").execute().data
    subs = [s for s in subs if s.get("email") and s.get("unsub_token")]
    codes = {}

    def build(s):
        first = (s.get("name") or "there").strip().split(" ")[0] or "there"
        unsub = f"{SA.SITE_URL}/unsubscribe.html?t={s['unsub_token']}"
        code = codes.get(s["email"].lower())
        return compose(first, SA.ref_link(code) if code else f"{SA.SITE_URL}/", unsub), unsub

    key = os.environ.get("BREVO_API_KEY", "").strip()
    if not key:
        sys.exit("promo: BREVO_API_KEY not set")
    from_name, alerts_email = SA.parse_sender(
        os.environ.get("ALERTS_FROM", "GoldRates <alerts@mygoldrates.com>"))
    from_email = (os.environ.get("PROMO_FROM", "").strip()
                  or f"{PROMO_LOCAL}@{alerts_email.split('@')[-1]}")
    if from_email.lower() == alerts_email.lower():
        sys.exit("promo: refusing to send the launch from the daily alerts address")

    def send(to_email, mail, unsub):
        body, text, subject, sender = mail
        msg = {"sender": {"name": sender or from_name, "email": from_email}, "to": [{"email": to_email}],
               "subject": subject, "htmlContent": body,
               "headers": {"List-Unsubscribe": f"<{unsub}>",
                           "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}}
        if text:
            msg["textContent"] = text
        r = SA.requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": key, "accept": "application/json", "content-type": "application/json"},
            json=msg, timeout=30)
        if r.status_code >= 300:
            print(f"promo: {to_email[:2]}… not sent: HTTP {r.status_code} {r.text[:200]}")
        return r.status_code < 300

    if args.to:
        # A test touches no one else: an invite code for this address only,
        # if it is a subscriber, and nothing recorded.
        sample = next((s for s in subs if s["email"].lower() == args.to.lower()), None)
        if sample:
            codes.update(SA.ensure_ref_codes(sb, [sample]))
        else:
            sample = {"name": "", "email": args.to, "unsub_token": "00000000-0000-0000-0000-000000000000"}
        body, unsub = build(sample)
        ok = send(args.to, body, unsub)
        print("promo: test copy", "sent" if ok else "FAILED")
        if not ok:
            sys.exit(1)                 # a red run, not a quiet green one
        return

    codes.update(SA.ensure_ref_codes(sb, subs))
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
    if sent < len(todo):
        sys.exit(1)                     # some failed: the run shows red; re-running sends only those


if __name__ == "__main__":
    main()
