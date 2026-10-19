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
    # The site's shared header (with the logo and main menu) and footer, so
    # this page is not the one place that looks like a different website.
    import generate_site as _gs
    from datetime import date as _date
    nd_header = _gs.nd_header_html()
    nd_footer = _gs.nd_footer_html(_date.today().year)
    nd_chrome = _gs.ND_CHROME_CSS
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
<link rel="canonical" href="{SITE}/jewellers-digest">
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
footer a{{color:var(--ink2)}}
@media(max-width:520px){{.now{{font-size:52px}}}}
</style>
<style>{nd_chrome}
[hidden]{{display:none!important}}
.jd-disclosure{{max-width:720px;margin:30px auto 0;padding:0 20px;text-align:center;font-size:13px;opacity:.7}}</style>
{analytics}</head><body>

{nd_header}

<div class="wrap">
  <div class="hero">
    <span class="eyebrow">Jewellers Digest</span>
    <h1>Know what the board will do<br>before you buy the metal</h1>
    <p class="lede">A daily analysis of India's jeweller gold board, built for the
    trade. Every jeweller's rate, what the spread has been, where price has turned
    before, and what is scheduled to move it this week.</p>

    <!-- Shown instead of the offer when the visitor is signed in with access. -->
    <div class="price" id="member" hidden>
      <span class="badge">Your Jewellers Digest</span>
      <p class="per" style="margin-top:14px">Signed in as <b id="m-who"></b></p>
      <p class="save" id="m-access"></p>
      <p style="margin-top:16px"><a href="{SITE}/jd-today" id="m-open"
        style="display:block;padding:16px;border-radius:10px;font-weight:700;text-decoration:none;
        background:linear-gradient(135deg,var(--gold-l),var(--gold));color:#1a0a04;text-align:center">Open today&rsquo;s issue</a></p>
      <form id="m-dl" style="margin-top:10px"><button id="m-btn" type="submit"
        style="background:transparent;color:var(--gold-l);border:1px solid var(--line)">Download the workbook (.xlsx)</button></form>
      <div class="msg" id="m-msg"></div>
      <p class="fineprint"><a href="{SITE}/jd-sign-in">Your account</a> &middot;
        <a href="#" id="m-out">Sign out</a></p>
    </div>

    <div class="price" id="buy">
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
      <p class="fineprint">Already subscribed? <a href="{SITE}/jd-sign-in">Sign in</a></p>
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

<p class="jd-disclosure">Jewellers Digest is a paid subscription. &#8377;{price.OFFER_INR}/month launch
  price, &#8377;{price.REGULAR_INR}/month thereafter for new subscribers.</p>
{nd_footer}

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
  /* Signed in (a session from /jd-sign-in) with live access: show the
     member panel and the download, not the offer. Access is checked live
     by the Worker on every call, so a lapsed subscription falls back to
     the offer. */
  var token = null;
  try {{ token = localStorage.getItem('jd_session'); }} catch (e) {{}}
  function authed(path){{
    return fetch(API + path, {{headers: {{'Authorization': 'Bearer ' + token}}}})
      .then(function(r){{ return r.json().catch(function(){{ return {{}}; }})
        .then(function(j){{ return {{status: r.status, ok: r.ok, j: j}}; }}); }});
  }}
  if (token) {{
    authed('/jd/status').then(function(r){{
      var e = r.j && r.j.entitlement;
      if (!r.ok || !e || !e.active) return;
      document.getElementById('buy').hidden = true;
      document.getElementById('member').hidden = false;
      document.getElementById('m-who').textContent = r.j.email || '';
      var end = e.current_end ? new Date(e.current_end) : null;
      document.getElementById('m-access').textContent = e.status === 'complimentary'
        ? (end && end.getFullYear() > 2090 ? 'Complimentary access'
           : 'Complimentary access until ' + end.toLocaleDateString('en-IN'))
        : 'Subscription active' + (end ? ', paid until ' + end.toLocaleDateString('en-IN') : '');
    }}).catch(function(){{}});
  }}
  document.getElementById('m-dl').addEventListener('submit', function(ev){{
    ev.preventDefault();
    var b = document.getElementById('m-btn'), m = document.getElementById('m-msg');
    b.disabled = true; m.className = 'msg'; m.textContent = 'Preparing your download\u2026';
    authed('/jd/report').then(function(r){{
      b.disabled = false;
      if (r.ok && r.j.url) {{ m.className = 'msg ok'; m.textContent = 'Downloading ' + r.j.report + '.';
        window.location.href = r.j.url; return; }}
      m.className = 'msg err';
      m.textContent = r.status === 404 ? 'Today\u2019s workbook is not ready yet. It is published every morning.'
        : r.status === 401 ? 'Your session has ended. Sign in again.'
        : (r.j.error || 'Could not get the workbook. Try again shortly.');
    }}).catch(function(){{ b.disabled = false; m.className = 'msg err';
      m.textContent = 'Could not reach the server. Check your connection.'; }});
  }});
  document.getElementById('m-out').addEventListener('click', function(ev){{
    ev.preventDefault();
    try {{ localStorage.removeItem('jd_session'); }} catch (e) {{}}
    location.reload();
  }});

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


SIGNIN_OUT = os.environ.get("JD_SIGNIN_OUT", "docs/jd-sign-in.html")
TODAY_OUT = os.environ.get("JD_TODAY_OUT", "docs/jd-today.html")


def build_today():
    """The members-only issue page: the day's analysis in the Jewellers
    Digest design. The page holds no data; it asks the Worker for the
    latest issue with the visitor's session, and the Worker only answers
    an account whose access is current."""
    import json as _json
    import generate_site as _gs
    from datetime import date as _date
    here = os.path.dirname(os.path.abspath(__file__))
    tpl = open(os.path.join(here, "jd_today.html"), encoding="utf-8").read()
    tpl = tpl.split("-->", 1)[1]          # drop the template's own comment
    tpl = tpl.replace("__WORKER__", _json.dumps(WORKER)).replace("__SITE__", SITE)
    return f"""<!doctype html>
<html lang="en-IN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Today&rsquo;s issue &mdash; Jewellers Digest | MyGoldRates</title>
<meta name="robots" content="noindex,nofollow">
<link rel="canonical" href="{SITE}/jd-today">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>body{{margin:0;background:#0a0804;color:#F4EDE0}}</style>
<style>{_gs.ND_CHROME_CSS}</style>
{_analytics()}</head><body>
{_gs.nd_header_html()}
{tpl}
{_gs.nd_footer_html(_date.today().year)}
</body></html>
"""


def build_signin():
    """The Jewellers Digest sign-in page: email, then a 6-digit code.

    No password to forget or leak. The Worker emails a code only to an
    address that already has an account, answers the same either way, and
    hands back a session token that names the account and nothing more -
    access is checked live on every download, so a lapsed subscription
    stops working immediately whatever the browser still holds.
    """
    import generate_site as _gs
    from datetime import date as _date
    return f"""<!doctype html>
<html lang="en-IN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in &mdash; Jewellers Digest | MyGoldRates</title>
<meta name="description" content="Sign in to Jewellers Digest with a code sent to your email.">
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{SITE}/jd-sign-in">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<style>
:root{{--bg:#0a0804;--card:rgba(22,16,8,.86);--line:rgba(201,162,39,.16);
  --ink:#F4EDE0;--ink2:#C8BDA8;--ink3:#857B69;--gold:#D4A63C;--gold-l:#F0D080;
  --mint:#5CC4A0;--rose:#E88AAE;--serif:'Playfair Display',Georgia,serif;
  --sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:16px;
  line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:var(--gold-l)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;
  padding:28px 24px;margin:48px auto;max-width:420px}}
h1{{font-family:var(--serif);font-size:30px;line-height:1.2}}
.sub{{color:var(--ink2);font-size:14.5px;margin-top:8px}}
form{{margin-top:20px;display:grid;gap:12px}}
label{{font-size:12.5px;color:var(--ink3);display:block;margin-bottom:5px}}
input{{width:100%;background:rgba(0,0,0,.34);border:1px solid var(--line);
  border-radius:10px;padding:13px 14px;color:var(--ink);font-size:16px;font-family:inherit}}
input:focus{{outline:2px solid var(--gold);outline-offset:1px}}
#code{{font-size:24px;letter-spacing:8px;text-align:center}}
button{{width:100%;border:0;border-radius:10px;padding:15px;font-size:16px;
  font-weight:700;font-family:inherit;cursor:pointer;
  background:linear-gradient(135deg,var(--gold-l),var(--gold));color:#1a0a04}}
button:disabled{{opacity:.45;cursor:not-allowed}}
.link{{background:none;color:var(--gold-l);padding:6px;font-weight:500;
  font-size:14px;text-decoration:underline}}
.msg{{font-size:14px;margin-top:12px;line-height:1.5}}
.msg.err{{color:var(--rose)}} .msg.ok{{color:var(--mint)}}
.acc{{margin-top:16px;padding:14px 16px;border:1px solid var(--line);border-radius:12px;
  font-size:14.5px;color:var(--ink2)}}
.acc b{{color:var(--ink)}}
.foot{{font-size:13px;color:var(--ink3);margin-top:18px}}
[hidden]{{display:none!important}}
</style>
<style>{_gs.ND_CHROME_CSS}</style>
{_analytics()}</head><body>
{_gs.nd_header_html()}
<div style="padding:0 16px">
<div class="card">
  <h1>Jewellers Digest</h1>

  <div id="v-email">
    <p class="sub">Sign in with the email you subscribed with. We will send
    you a 6-digit code &mdash; no password needed.</p>
    <form id="f-email" novalidate>
      <div><label for="em">Email</label>
        <input id="em" type="email" autocomplete="email" placeholder="you@yourshop.com" required></div>
      <button id="b-email" type="submit">Email me a code</button>
    </form>
  </div>

  <div id="v-code" hidden>
    <p class="sub">If <b id="em-show"></b> has a Jewellers Digest account, a
    code is on its way. It expires in 10 minutes.</p>
    <form id="f-code" novalidate>
      <div><label for="code">6-digit code</label>
        <input id="code" inputmode="numeric" autocomplete="one-time-code"
          maxlength="6" pattern="[0-9]*" required></div>
      <button id="b-code" type="submit">Sign in</button>
    </form>
    <button class="link" id="b-back" type="button">Use a different email</button>
  </div>

  <div id="v-in" hidden>
    <p class="sub">Signed in as <b id="who"></b></p>
    <div class="acc" id="acc"></div>
    <p style="margin-top:16px" id="open-wrap"><a href="{SITE}/jd-today"
      style="display:block;padding:15px;border-radius:10px;font-weight:700;text-decoration:none;text-align:center;
      background:linear-gradient(135deg,var(--gold-l),var(--gold));color:#1a0a04">Open today&rsquo;s issue</a></p>
    <form id="f-dl" style="margin-top:10px"><button id="b-dl" type="submit">Download today&rsquo;s workbook</button></form>
    <button class="link" id="b-out" type="button">Sign out</button>
  </div>

  <div class="msg" id="msg" role="status"></div>
  <p class="foot">Not subscribed yet? <a href="{SITE}/jewellers-digest">See Jewellers Digest</a>.</p>
</div>
</div>
{_gs.nd_footer_html(_date.today().year)}
<script>
(function(){{
  var API = {WORKER!r}, KEY = 'jd_session', token = null, email = '';
  try {{ token = localStorage.getItem(KEY); }} catch (e) {{}}
  function $(id){{ return document.getElementById(id); }}
  function say(t, cls){{ $('msg').textContent = t || ''; $('msg').className = 'msg ' + (cls||''); }}
  function show(v){{ ['v-email','v-code','v-in'].forEach(function(x){{ $(x).hidden = (x !== v); }}); }}
  function keep(t){{ token = t; try {{ t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); }} catch (e) {{}} }}
  function call(method, path, body){{
    var h = {{'content-type':'application/json'}};
    if (token) h['Authorization'] = 'Bearer ' + token;
    return fetch(API + path, {{method: method, headers: h,
        body: body ? JSON.stringify(body) : undefined}})
      .then(function(r){{ return r.json().catch(function(){{ return {{}}; }})
        .then(function(j){{ return {{status: r.status, ok: r.ok, j: j}}; }}); }});
  }}
  function day(iso){{ return new Date(iso).toLocaleDateString('en-IN',
      {{day:'numeric', month:'short', year:'numeric'}}); }}
  function account(who, e){{
    $('who').textContent = who || '';
    var a = $('acc'), dl = $('b-dl');
    if (e && e.active && e.status === 'complimentary') {{
      a.textContent = new Date(e.current_end).getFullYear() > 2090
        ? 'Complimentary access.' : 'Complimentary access until ' + day(e.current_end) + '.';
    }} else if (e && e.active) {{
      a.textContent = 'Subscription active' + (e.current_end ? ', paid until ' + day(e.current_end) : '') + '.';
    }} else {{
      a.textContent = 'There is no active subscription on this email.';
    }}
    dl.hidden = !(e && e.active);
    $('open-wrap').hidden = !(e && e.active);
    show('v-in');
  }}

  if (token) {{
    call('GET', '/jd/status').then(function(r){{
      if (r.ok) account(r.j.email, r.j.entitlement);
      else {{ keep(null); show('v-email'); }}
    }}).catch(function(){{ say('Could not reach the server. Check your connection.', 'err'); }});
  }}

  $('f-email').addEventListener('submit', function(ev){{
    ev.preventDefault();
    email = $('em').value.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return say('Enter a valid email address.', 'err');
    $('b-email').disabled = true; say('');
    call('POST', '/jd/login/start', {{email: email}}).then(function(r){{
      $('b-email').disabled = false;
      if (!r.ok) return say(r.j.error || 'Could not send the code. Try again shortly.', 'err');
      $('em-show').textContent = email; show('v-code'); $('code').focus();
    }}).catch(function(){{ $('b-email').disabled = false;
      say('Could not reach the server. Check your connection.', 'err'); }});
  }});

  $('f-code').addEventListener('submit', function(ev){{
    ev.preventDefault();
    var code = $('code').value.replace(/\D/g, '');
    if (code.length !== 6) return say('Enter the 6-digit code from the email.', 'err');
    $('b-code').disabled = true; say('');
    call('POST', '/jd/login/verify', {{email: email, code: code}}).then(function(r){{
      $('b-code').disabled = false;
      if (!r.ok || !r.j.token) return say(r.j.error || 'That code is wrong or has expired.', 'err');
      keep(r.j.token); $('code').value = ''; account(r.j.email, r.j.entitlement);
    }}).catch(function(){{ $('b-code').disabled = false;
      say('Could not reach the server. Check your connection.', 'err'); }});
  }});

  $('b-back').addEventListener('click', function(){{ say(''); show('v-email'); }});
  $('b-out').addEventListener('click', function(){{ keep(null); say('Signed out.', 'ok'); show('v-email'); }});

  $('f-dl').addEventListener('submit', function(ev){{
    ev.preventDefault();
    $('b-dl').disabled = true; say('Preparing your download\u2026');
    call('GET', '/jd/report').then(function(r){{
      $('b-dl').disabled = false;
      if (r.ok && r.j.url) {{ say('Downloading ' + r.j.report + '.', 'ok'); window.location.href = r.j.url; return; }}
      if (r.status === 401) {{ keep(null); show('v-email'); return say('Your session has ended. Sign in again.', 'err'); }}
      if (r.status === 404) return say('Today\u2019s workbook is not ready yet. It is published every morning.', 'err');
      say(r.j.error || 'Could not get the workbook. Try again shortly.', 'err');
    }}).catch(function(){{ $('b-dl').disabled = false;
      say('Could not reach the server. Check your connection.', 'err'); }});
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
    # The pageview beacon, plus the shared click listener: these pages load
    # no signup.js, which is where every other page gets it.
    return (generate_site.analytics_snippet(url, key)
            + "<script>" + generate_site.CLICK_JS + "</script>")


def main():
    html = build()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"jd-page: wrote {OUT} ({len(html):,} bytes) "
          f"- Rs {P.REGULAR_INR} struck to Rs {P.OFFER_INR}")
    signin = build_signin()
    with open(SIGNIN_OUT, "w", encoding="utf-8") as f:
        f.write(signin)
    print(f"jd-page: wrote {SIGNIN_OUT} ({len(signin):,} bytes)")
    today = build_today()
    with open(TODAY_OUT, "w", encoding="utf-8") as f:
        f.write(today)
    print(f"jd-page: wrote {TODAY_OUT} ({len(today):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
