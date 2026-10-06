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


def _guard(src):
    """The plan-amount check inside handleSignup, not the secrets comment."""
    i = src.index("if (env.JD_EXPECTED_PAISE)")
    return src[i:i + 1400]


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


def test_a_401_counts_as_healthy_not_as_down(html):
    """/jd/status refusing an unauthenticated caller means the Worker is up
    and correct. Treating 401 as an outage would keep the page shut forever."""
    assert "401" in html


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
    assert "/jd/status" in html
    assert "market-api" not in html


# ─── worker-side guard ──────────────────────────────────────────────────

def test_the_worker_verifies_the_plan_amount_before_taking_a_mandate():
    """A plan's amount cannot be edited, so repricing means a new plan id.
    Forgetting to repoint it would charge the old amount silently."""
    src = open("cf-worker-jd/worker.js").read()
    assert "JD_EXPECTED_PAISE" in src
    # The name appears first in the header comment listing the secrets, so
    # anchor on the guard itself rather than on the first mention.
    guard = _guard(src)
    assert "PLAN AMOUNT MISMATCH" in guard
    assert "503" in guard


def test_the_plan_guard_fails_closed():
    """If the plan cannot be read at all, refuse. A refused signup is
    recoverable; a wrong debit on a jeweller's account is not."""
    guard = _guard(open("cf-worker-jd/worker.js").read())
    assert "plan lookup failed" in guard
    assert "!plan.ok" in guard
