"""The Jewellers Digest landing page and its pricing.

Two things are checked here that a human reviewer reads straight past: that
every rupee figure on the page comes from one constant, and that the page
refuses to take a signup when the billing API is not answering. Both have an
obvious failure mode in production - one charges a different amount than was
advertised, the other collects a jeweller's details into a void.
"""
import re

import pytest

import jd_page
import jd_pricing as P


@pytest.fixture(scope="module")
def html():
    return jd_page.build()


def _ready(src):
    """The body of billingReady(), not the secrets comment above it."""
    i = src.index("async function billingReady(env) {")
    return src[i:i + 1800]


# ─── pricing ────────────────────────────────────────────────────────────

def test_paise_are_integers_not_floats():
    """Money never goes in a float. 99.00 rupees is 9900 and stays 9900."""
    assert isinstance(P.OFFER_PAISE, int) and P.OFFER_PAISE == 9900
    assert isinstance(P.REGULAR_PAISE, int) and P.REGULAR_PAISE == 49900


def test_the_plan_amount_is_the_offer_not_the_regular_price():
    """What Razorpay must be set to is what the customer is promised. Setting
    the plan to the struck-through price would charge five times the ask."""
    assert P.PLAN_AMOUNT_PAISE == P.OFFER_PAISE


def test_the_offer_is_cheaper_than_the_price_it_strikes_through():
    assert P.OFFER_INR < P.REGULAR_INR
    assert 0 < P.DISCOUNT_PCT < 100


def test_rupees_uses_indian_digit_grouping():
    assert P.rupees(100000) == "1,00,000"
    assert P.rupees(1234567) == "12,34,567"
    assert P.rupees(999) == "999"


# ─── the page reflects the constants, not a typed-in number ─────────────

def test_both_prices_appear_and_come_from_the_constants(html):
    assert f"&#8377;{P.OFFER_INR}" in html
    assert f"&#8377;{P.REGULAR_INR}" in html


def test_no_stale_price_is_left_anywhere_on_the_page(html):
    """The product was Rs 50 before this launch. A single forgotten mention
    would read as a second, cheaper offer."""
    text = re.sub(r"<[^>]+>", " ", html)
    for stale in ("50/month", "Rs 50", "₹50 ", "&#8377;50 "):
        assert stale not in text, f"stale price {stale!r} still on the page"


def test_the_struck_price_is_presented_as_the_regular_price(html):
    """Not as a historical price nobody was charged. The page must say what
    the figure means, or the strike-through is a false reference price."""
    assert "thereafter" in html or "regular" in html.lower()


def test_the_discount_claim_matches_the_arithmetic(html):
    assert f"Save {P.DISCOUNT_PCT}%" in html
    assert P.DISCOUNT_PCT == round((1 - P.OFFER_INR / P.REGULAR_INR) * 100)


# ─── the page cannot mislead about what it is ───────────────────────────

def test_the_page_says_it_is_not_investment_advice(html):
    assert "not investment advice" in html


def test_the_page_states_how_to_cancel(html):
    assert "Cancel" in html or "cancel" in html


def test_recurring_billing_is_disclosed_before_the_button(html):
    """An auto-debit mandate must be obvious before someone presses the
    button, not discovered on the Razorpay page."""
    btn = html.index('id="go"')
    assert "auto-debit" in html[:btn]
    assert "per month" in html[:btn]


# ─── the signup button and its failure mode ─────────────────────────────

def test_the_button_starts_disabled(html):
    """It is enabled only once the API answers. Rendering a live-looking
    button over a dead endpoint is how a sales page loses a customer and
    tells nobody."""
    go = html[html.index('id="go"'):html.index('id="go"') + 200]
    assert "disabled" in go


def test_an_unreachable_api_disables_the_button_rather_than_hiding_it(html):
    assert "Opening shortly" in html
    assert "not open yet" in html


def test_the_probe_demands_open_not_merely_a_reachable_worker(html):
    """The earlier version of this page probed /jd/status and counted 401 as
    health, because the route answering at all meant the Worker was up. It
    answers 401 to a browser with no Razorpay credentials set either, so the
    page would enable the button, collect an email and a mobile number, and
    discover only then that nothing could be charged. The probe has to ask a
    question whose answer differs in those two cases."""
    assert "fetch(API + '/jd/ready'" in html
    assert "d.open !== true" in html
    # The comment above the probe explains the old mistake by name, so look
    # for a request to it rather than for the string anywhere on the page.
    assert "fetch(API + '/jd/status'" not in html


def test_a_failed_signup_says_nothing_was_charged(html):
    assert "Nothing has been charged" in html


def test_the_form_requires_a_valid_mobile(html):
    assert "[6-9]" in html
    assert "Mobile number is required" in html


def test_the_bare_country_prefix_counts_as_empty(html):
    """The field is pre-filled '+91 ', so an untouched field leaves '91',
    which is truthy. Without this the commonest case - skipped the field -
    is told it mistyped."""
    assert "digits === '91'" in html


def test_the_page_points_at_the_jd_worker_not_the_market_worker(html):
    assert "/jd/signup" in html
    assert "fetch(API + '/jd/ready'" in html
    assert "market-api" not in html


# ─── worker-side guard ──────────────────────────────────────────────────

def test_the_worker_verifies_the_plan_amount_before_taking_a_mandate():
    """A plan's amount cannot be edited, so repricing means a new plan id.
    Forgetting to repoint it would charge the old amount silently."""
    src = open("cf-worker-jd/worker.js").read()
    assert "JD_EXPECTED_PAISE" in src
    # The name appears first in the header comment listing the secrets, so
    # anchor on the check itself rather than on the first mention.
    ready = _ready(src)
    assert "PLAN AMOUNT MISMATCH" in ready
    # handleSignup refuses on a shut answer rather than repeating the logic.
    assert "const ready = await billingReady(env);" in src
    assert "if (!ready.open) {" in src


def test_the_plan_guard_fails_closed():
    """If the plan cannot be read at all, refuse. A refused signup is
    recoverable; a wrong debit on a jeweller's account is not."""
    ready = _ready(open("cf-worker-jd/worker.js").read())
    assert "plan lookup failed" in ready
    assert "!plan.ok" in ready
    assert "return { open: false };" in ready


def test_readiness_requires_every_secret_including_the_price_check():
    """The signup guard skips itself when JD_EXPECTED_PAISE is unset, which
    is the one case where an unchecked plan amount can charge whatever it
    likes. Readiness treats that secret as required, so the page cannot open
    a form with nothing verifying the price it advertises."""
    src = open("cf-worker-jd/worker.js").read()
    ready = _ready(src)
    for secret in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "RAZORPAY_KEY_ID",
                   "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET",
                   "RAZORPAY_PLAN_ID", "JD_EXPECTED_PAISE"):
        assert secret in ready, f"{secret} is not required for readiness"


def test_readiness_does_not_say_which_secret_is_missing():
    """The reason names this Worker's configuration. It goes to the log, not
    to an unauthenticated caller."""
    src = open("cf-worker-jd/worker.js").read()
    ready = _ready(src)
    # The only thing returned on failure is the bare shut answer.
    assert "return { open: false };" in ready
    assert "missing," not in ready.replace("console.error", "")
    body = ready[ready.index("const missing"):]
    assert "missing.join" in body and "console.error" in body
    # No response path carries the list.
    assert "open: false, missing" not in src
    assert "reason:" not in _ready(src)


def test_only_readiness_is_cacheable():
    """Every other route is per-caller and no-store. Readiness is global and
    carries no entitlement, and without a cache every page load would reach
    Razorpay through an endpoint nobody has to authenticate to."""
    src = open("cf-worker-jd/worker.js").read()
    assert "'cache-control': 'no-store'" in src
    i = src.index("async function handleReady")
    handler = src[i:i + 900]
    assert "public, max-age=60" in handler
    assert "caches.default" in handler
    # A cache failure must not take readiness down with it.
    assert ".catch(() => null)" in handler or ".catch(() => {})" in handler
