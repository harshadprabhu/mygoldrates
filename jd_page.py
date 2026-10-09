#!/usr/bin/env python3
"""The Jewellers Digest landing and signup page.

Writes docs/jewellers-digest.html. Kept out of generate_site.py because that
file is already 7,000 lines and this page has its own look, its own form and
its own failure mode.

THE FAILURE MODE IS THE POINT. The signup button talks to the JD Worker,
which may not be deployed, may be missing its Razorpay secrets, or may be
mid-outage. A sales page whose only button silently does nothing is worse
than one that says "not open yet": the first loses the customer and tells
nobody, the second loses the customer and tells you. So the page probes the
Worker on load and shows one of three honest states - open, warming up, or
not open yet - rather than rendering a hopeful button over a dead endpoint.
"""
import os

import jd_pricing as P

OUT = os.environ.get("JD_PAGE_OUT", "docs/jewellers-digest.html")
SITE = "https://mygoldrates.com"
WORKER = os.environ.get(
    "JD_API_BASE", "https://mygoldrates-jd-api.harshads-priority.workers.dev")

SHEETS = [
    ("Summary", "the window, today's board, cheapest first"),
    ("Daily Rates", "date &times; jeweller matrix &mdash; the raw export, pivot it yourself"),
    ("Brand Analysis", "level, dispersion, premium, how often each is cheapest"),
    ("Market Daily", "low / median / high / spread, every day"),
    ("Weekday", "mean by weekday, with the sample size attached"),
    ("Outlook", "direction, the six signals behind it, expected range"),
    ("Horizons", "week, month and quarter &mdash; each with its measured track record"),
    ("Levels", "support and resistance on the jeweller board"),
    ("Event Risk", "releases scheduled to move gold this week"),
    ("Making Charges", "median making % by brand and category"),
    ("Methodology", "what this window supports, and what it does not"),
]


def build(price=P):
    disc = price.DISCOUNT_PCT
    analytics = _analytics()
    sheets = "".join(
        f'<div class="sh"><b>{n}</b><span>{d}</span></div>' for n, d in SHEETS)
    return f"""<!doctype html>
<html lang="en-IN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jewellers Digest &mdash; daily gold rate analysis for jewellers | MyGoldRates</title>
<meta name="description" content="A daily analysis of India's jeweller gold board:
 11-sheet workbook, outlook by week, month and quarter, and support and resistance.
 &#8377;{price.OFFER_INR} a month, launch offer.">
<link rel="canonical" href="{SITE}/jewellers-digest.html">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<meta property="og:title" content="Jewellers Digest &mdash; MyGoldRates">
<meta property="og:description" content="Daily gold rate analysis for the jewellery trade.">
<meta property="og:image" content="{SITE}/og.png">
<meta name="robots" content="index,follow">
<style>
:root{{
  --bg:#0a0804; --card:rgba(22,16,8,.86); --line:rgba(201,162,39,.16);
  --ink:#F4EDE0; --ink2:#C8BDA8; --ink3:#857B69;
  --gold:#D4A63C; --gold-l:#F0D080; --mint:#5CC4A0; --rose:#E88AAE;
  --serif:'Playfair Display',Georgia,serif;
  --sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:var(--gold-l)}}
.wrap{{max-width:940px;margin:0 auto;padding:0 20px}}
header{{padding:22px 0;border-bottom:1px solid var(--line)}}
.brand{{display:flex;align-items:center;gap:9px;font-family:var(--serif);
  font-size:19px;font-weight:700}}
.brand svg{{width:28px;height:28px;flex:0 0 auto}}
.brand .g{{background:linear-gradient(135deg,var(--gold-l),var(--gold));
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
.hero{{padding:56px 0 40px;text-align:center}}
.eyebrow{{font-size:12px;letter-spacing:3px;text-transform:uppercase;
  color:var(--gold);font-weight:700}}
h1{{font-family:var(--serif);font-size:clamp(32px,6.4vw,52px);line-height:1.12;
  margin:16px 0 0;letter-spacing:-.5px;text-wrap:balance}}
.lede{{color:var(--ink2);font-size:17.5px;max-width:58ch;margin:18px auto 0}}

.price{{background:var(--card);border:1px solid var(--line);border-radius:18px;
  padding:30px 26px;margin:34px auto 0;max-width:460px;text-align:center}}
.badge{{display:inline-block;font-size:11px;letter-spacing:2px;text-transform:uppercase;
  font-weight:700;color:#1a0a04;background:linear-gradient(135deg,var(--gold-l),var(--gold));
  border-radius:99px;padding:6px 14px}}
.amt{{display:flex;align-items:baseline;justify-content:center;gap:12px;margin-top:16px}}
.was{{font-size:27px;color:var(--ink3);text-decoration:line-through;
  text-decoration-thickness:2px}}
.now{{font-family:var(--serif);font-size:62px;font-weight:700;line-height:1;
  background:linear-gradient(135deg,var(--gold-l),var(--gold));
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
.per{{color:var(--ink2);font-size:15px;margin-top:6px}}
.save{{color:var(--mint);font-size:13.5px;margin-top:10px;font-weight:600}}

form{{margin-top:22px;display:grid;gap:11px;text-align:left}}
label{{font-size:12.5px;color:var(--ink3);display:block;margin-bottom:5px}}
input{{width:100%;background:rgba(0,0,0,.34);border:1px solid var(--line);
  border-radius:10px;padding:13px 14px;color:var(--ink);font-size:15.5px;
  font-family:inherit}}
input:focus{{outline:2px solid var(--gold);outline-offset:1px}}
button{{width:100%;border:0;border-radius:10px;padding:16px;font-size:16px;
  font-weight:700;font-family:inherit;cursor:pointer;
  background:linear-gradient(135deg,var(--gold-l),var(--gold));color:#1a0a04}}
button:disabled{{opacity:.45;cursor:not-allowed}}
.msg{{font-size:13.5px;margin-top:12px;line-height:1.5}}
.msg.err{{color:var(--rose)}} .msg.ok{{color:var(--mint)}}
.state{{font-size:13px;color:var(--ink3);margin-top:14px}}
.fineprint{{font-size:12.5px;color:var(--ink3);margin-top:16px;line-height:1.55}}

section{{padding:44px 0;border-top:1px solid var(--line)}}
h2{{font-family:var(--serif);font-size:27px;margin-bottom:8px}}
.sub{{color:var(--ink3);font-size:14.5px;margin-bottom:22px}}
.sheets{{display:grid;grid-template-columns:repeat(auto-fit,minmax(248px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:13px;overflow:hidden}}
.sh{{background:var(--card);padding:15px 17px}}
.sh b{{display:block;font-size:14.5px}}
.sh span{{display:block;color:var(--ink3);font-size:12.8px;margin-top:3px}}
.feat{{display:grid;grid-template-columns:repeat(auto-fit,minmax(252px,1fr));gap:18px}}
.ft{{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:19px}}
.ft h3{{font-size:16px;margin-bottom:7px}}
.ft p{{color:var(--ink2);font-size:14px}}
.note{{background:var(--card);border:1px solid var(--line);
  border-left:3px solid var(--gold);border-radius:11px;padding:16px 18px;
  color:var(--ink2);font-size:13.8px;max-width:72ch}}
footer{{padding:34px 0 60px;border-top:1px solid var(--line);
  color:var(--ink3);font-size:12.5px}}
footer a{{color:var(--ink2)}}
@media(max-width:520px){{.now{{font-size:52px}}}}
</style>
{analytics}</head><body>

<header><div class="wrap"><a href="{SITE}/" class="brand" style="text-decoration:none;color:inherit">
<svg viewBox="0 0 48 48" aria-hidden="true"><defs><linearGradient id="bm" x1="4" y1="38" x2="36" y2="4" gradientUnits="userSpaceOnUse"><stop stop-color="#B07E12"/><stop offset=".55" stop-color="#E3BF63"/><stop offset="1" stop-color="#F4E3A6"/></linearGradient></defs><g transform="translate(4,4)"><rect x="4.5" y="21" width="9" height="15" rx="1.6" fill="url(#bm)"/><rect x="16.5" y="12" width="9" height="24" rx="1.6" fill="url(#bm)"/><path d="M5 25.5 17 17 25 21 34 8.5" stroke="url(#bm)" stroke-width="3.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M27.5 7.5 35 6.5 34.5 14" stroke="url(#bm)" stroke-width="3.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g></svg>
<span>My<span class="g">Gold</span>Rates</span></a></div></header>

<div class="wrap">
  <div class="hero">
    <span class="eyebrow">Jewellers Digest</span>
    <h1>Know what the board will do<br>before you buy the metal</h1>
    <p class="lede">A daily analysis of India's jeweller gold board, built for the
    trade. Every jeweller's rate, what the spread has been, where price has turned
    before, and what is scheduled to move it this week.</p>

    <div class="price">
      <span class="badge">Launch offer</span>
      <div class="amt">
        <span class="was">&#8377;{price.REGULAR_INR}</span>
        <span class="now">&#8377;{price.OFFER_INR}</span>
      </div>
      <div class="per">per month &middot; auto-debit by UPI</div>
      <div class="save">Save {disc}% &mdash; and keep this price for as long as you stay subscribed</div>

      <form id="f" novalidate>
        <div><label for="biz">Business name</label>
          <input id="biz" name="biz" autocomplete="organization" placeholder="Your shop"></div>
        <div><label for="em">Email *</label>
          <input id="em" name="em" type="email" autocomplete="email" placeholder="you@yourshop.com" required></div>
        <div><label for="ph">Mobile *</label>
          <input id="ph" name="ph" type="tel" inputmode="numeric" autocomplete="tel" value="+91 " required></div>
        <button id="go" type="submit" disabled>Checking availability&hellip;</button>
      </form>
      <div class="msg" id="msg"></div>
      <div class="state" id="state"></div>
      <p class="fineprint">You will be taken to Razorpay to approve the monthly
      auto-debit. Cancel any time from your UPI app or by emailing us &mdash; cancelling
      stops the next charge.</p>
    </div>
  </div>
</div>

<div class="wrap">
  <section>
    <h2>What arrives</h2>
    <p class="sub">One workbook every morning, covering every jeweller on the board.</p>
    <div class="sheets">{sheets}</div>
  </section>

  <section>
    <h2>And three things the spreadsheet cannot do</h2>
    <div class="feat">
      <div class="ft"><h3>A short read, daily</h3><p>The day's move in a
      paragraph, in your inbox before the shop opens. Written from the computed
      figures, never estimated.</p></div>
      <div class="ft"><h3>Every past issue</h3><p>Pull any day's workbook back,
      by date. Useful when a customer asks what the rate was last Tuesday.</p></div>
      <div class="ft"><h3>The data, as an API</h3><p>A key to pull the rate
      history straight into your own systems, if you would rather not open a
      spreadsheet.</p></div>
    </div>
  </section>

  <section>
    <h2>What it is not</h2>
    <div class="note"><b>This is market analysis for people buying metal to
    stock, and it is not investment advice.</b> It is not a recommendation to
    buy or sell gold or any financial instrument, and not a guarantee of any
    future price. Every figure is computed from rates each jeweller published
    on its own website; rates move continuously and the price on a jeweller's
    own counter at the moment of sale is the only one that governs a sale.
    Forward-looking figures describe how prices have behaved in the past and
    may be wrong &mdash; each one ships with its own measured track record so you
    can see how much weight it deserves. Any commercial decision taken on this
    report is yours.</div>
  </section>
</div>

<footer><div class="wrap">
  <a href="{SITE}/">MyGoldRates.com</a> &middot;
  <a href="{SITE}/about.html">About</a> &middot;
  <a href="{SITE}/contact.html">Contact</a><br>
  Jewellers Digest is a paid subscription. &#8377;{price.OFFER_INR}/month launch
  price, &#8377;{price.REGULAR_INR}/month thereafter for new subscribers.
</div></footer>

<script>
(function(){{
  var API = {WORKER!r};
  var go = document.getElementById('go'),
      msg = document.getElementById('msg'),
      state = document.getElementById('state');

  function say(t, cls){{ msg.textContent = t; msg.className = 'msg ' + (cls||''); }}

  /* Probe before promising. The button stays disabled until billing says it
     can actually take a subscription, so nobody fills in a form that has
     nowhere to go. A sales page that takes details into a void is worse than
     one that admits it is not open.

     This asks /jd/ready, not /jd/status. /jd/status answers 401 to a browser
     whether or not any payment credentials are configured — the route is
     there, correctly refusing an anonymous caller — so treating that as
     health would have opened the form against a Worker that could not charge
     anyone. /jd/ready checks the live plan and says open: true or nothing. */
  fetch(API + '/jd/ready', {{method:'GET'}})
    .then(function(r){{ return r.ok ? r.json() : null; }})
    .then(function(d){{
      if (!d || d.open !== true) throw new Error('not open');
      go.disabled = false; go.textContent = 'Subscribe for \u20B9{price.OFFER_INR}/month';
      state.textContent = '';
    }})
    .catch(function(){{
      go.textContent = 'Opening shortly';
      go.disabled = true;
      state.textContent = 'Subscriptions are not open yet. Leave your email on '
        + 'the homepage and we will tell you the day they are.';
    }});

  document.getElementById('f').addEventListener('submit', function(e){{
    e.preventDefault();
    var email = document.getElementById('em').value.trim().toLowerCase();
    var digits = document.getElementById('ph').value.replace(/\\D/g, '');
    if (digits === '91' || digits === '0' || digits === '091') digits = '';
    else {{
      if (digits.length > 10 && digits.slice(0,2) === '91') digits = digits.slice(2);
      if (digits.length === 11 && digits.charAt(0) === '0') digits = digits.slice(1);
    }}
    if (!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) return say('Enter a valid email address.', 'err');
    if (!digits) return say('Mobile number is required.', 'err');
    if (!/^[6-9]\\d{{9}}$/.test(digits)) return say('Enter a valid 10-digit mobile number.', 'err');

    go.disabled = true; go.textContent = 'Setting up\\u2026'; say('');
    fetch(API + '/jd/signup', {{
      method: 'POST', headers: {{'content-type':'application/json'}},
      body: JSON.stringify({{
        email: email, phone: digits,
        business_name: document.getElementById('biz').value.trim()
      }})
    }})
    .then(function(r){{ return r.json().then(function(j){{ return {{ok:r.ok, j:j}}; }}); }})
    .then(function(res){{
      if (!res.ok || !res.j.authorise_url) {{
        throw new Error(res.j && res.j.error ? res.j.error : 'could not start the subscription');
      }}
      say('Taking you to Razorpay\\u2026', 'ok');
      window.location.href = res.j.authorise_url;
    }})
    .catch(function(err){{
      go.disabled = false; go.textContent = 'Subscribe for \\u20B9{price.OFFER_INR}/month';
      say('Could not start the subscription: ' + err.message
          + '. Nothing has been charged. Please try again, or email us.', 'err');
    }});
  }});
}})();
</script>
</body></html>
"""


def _analytics():
    """The same inline beacon every other page gets.

    This page shipped without one, so every visit to the Jewellers Digest
    landing page since launch went unrecorded - including the ones this
    page most needs to count, because they are the ones deciding whether
    anybody wants to buy it.
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        return ""
    import generate_site
    return generate_site.analytics_snippet(url, key)


def main():
    html = build()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"jd-page: wrote {OUT} ({len(html):,} bytes) "
          f"- Rs {P.REGULAR_INR} struck to Rs {P.OFFER_INR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
