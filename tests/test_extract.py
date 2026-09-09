"""Regression tests for the rate extractors.

Every case here is a real failure that reached production and cost a wrong
rate on the public board. They exist so the extractor stops being re-edited
by hand each time a brand breaks: change the patterns freely, but these
shapes must keep working.

Run: python -m pytest tests/ -q     (CI: .github/workflows/tests.yml)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scrape  # noqa: E402


def _extract(text):
    """extract() takes HTML; these fixtures are the text shapes that matter."""
    return scrape.extract(f"<html><body>{text}</body></html>")


# --------------------------------------------------------------------------
# C Krishniah Chetty, 2026-09-09.
#
# Their board prints the fineness code on the 24K row only:
#     24Kt Gold (999) : Rs 15685.35 /Gram
# _LABELED_RE used to allow only NON-DIGITS between the karat label and the
# rate, so "(999)" broke the match and the 24K row - the one row we most
# needed - was silently dropped. 22K and 18K, which carry no code, matched
# fine, so the ladder inferred 24K from the 22K and published 15,534.55
# against a real 15,685.35: 150.80/g low.
#
# The inference was wrong because CKC prices 22K BELOW the flat 22/24 ratio
# (14240/15685.35 = 0.9079 vs 0.9167). Never assume a jeweller's purities
# sit on exact ratios - read the published number whenever there is one.
# --------------------------------------------------------------------------
CKC_BOARD = """
METAL RATES TODAY
24Kt Gold (999) : &#8377; 15685.35 /Gram
22Kt Gold : &#8377; 14240.0 /Gram
18Kt Gold : &#8377; 11781.27 /Gram
"""


def test_fineness_code_does_not_block_the_karat_row():
    found, _, _ = _extract(CKC_BOARD)
    assert found.get("24K") == 15685.35, (
        "24K row carrying '(999)' must still match - this is the CKC "
        "regression that published a rate 150.80/g low")
    assert found.get("22K") == 14240.0
    assert found.get("18K") == 11781.27


def test_published_24k_wins_over_ladder_inference():
    """With a real 24K on the page we must use it, not derive one."""
    found, _, _ = _extract(CKC_BOARD)
    top = max(found, key=lambda k: scrape.PURITY_FRACTION[k])
    assert top == "24K"
    implied = found[top] / scrape.PURITY_FRACTION[top]
    assert abs(implied - 15685.35) < 0.01
    # The value the old bug produced must NOT come back.
    assert abs(implied - 15534.55) > 100


def test_ckc_three_purities_confirm_the_basis():
    found, _, _ = _extract(CKC_BOARD)
    ok, why = scrape.basis_confirmed(found)
    assert ok, f"CKC's three purities should cross-validate, got: {why}"


# --------------------------------------------------------------------------
# Senco Gold, 2026-09-08.
#
# rate_url pointed at a 22K CHAIN product page. It had no
# metal_price/net_weight pair, so extract() fell through to 'goldvalue' and
# took a single 22K point (13,961.01) off that one chain, which the ladder
# scaled x 24/22 to 15,230.20 - 272.80/g under Senco's own calculator
# (15,503.00). Cheap enough that it wore the "lowest today" badge.
#
# Fixed by reading a 999.9 COIN page instead: a pure-gold coin's gold-value
# breakup IS the 24K per-gram rate, so no ladder inference is involved.
# --------------------------------------------------------------------------
SENCO_COIN = """
<div class="price-breakup">
  <span>Gold Value</span>
  <span>24KT (999.9)</span>
  <span>&#8377; 15503.00 / g</span>
</div>
"""


def test_pure_gold_coin_reads_24k_directly():
    found, _, _ = _extract(SENCO_COIN)
    assert "24K" in found, "a 999.9 coin page must yield a direct 24K read"
    assert abs(found["24K"] - 15503.00) < 0.01
    assert "22K" not in found, "must not invent a 22K anchor for a 24K coin"


# --------------------------------------------------------------------------
# A lower-purity anchor is still allowed - GRT and Indriya publish 22K only,
# and laddering from a published BOARD rate is exactly what derive_ladder is
# for. What must never happen is silently preferring it when a 24K exists
# (see test_published_24k_wins_over_ladder_inference).
# --------------------------------------------------------------------------
def test_lower_purity_only_page_still_extracts():
    found, _, _ = _extract("22Kt Gold : &#8377; 14145.00 /Gram")
    assert found.get("22K") == 14145.0
    implied = found["22K"] / scrape.PURITY_FRACTION["22K"]
    assert abs(implied - 15430.91) < 0.5


def test_single_purity_is_not_basis_confirmed():
    ok, why = scrape.basis_confirmed({"22K": 14145.0})
    assert not ok and "single" in why.lower()


# --------------------------------------------------------------------------
# Fineness codes must not be mistaken for rates. Only the recognised codes
# are permitted inside the label-to-rate gap, never an arbitrary number, so
# an unrelated figure standing between a karat label and a price cannot be
# swallowed.
# --------------------------------------------------------------------------
def test_labeled_re_spans_only_a_fineness_code_not_any_number():
    """The widened gap must admit fineness codes and nothing else.

    Asserted against _LABELED_RE directly, because that is the pattern the
    CKC fix widened. extract() as a whole may still bind this text through
    extract_proximity, which is a deliberately looser fallback and is what
    GRT's board is read with - that is existing, intended behaviour and is
    not what this test governs.
    """
    ok = "22Kt Gold (916) : \u20b9 14240.00 /Gram"
    assert [m.group(2) for m in scrape._LABELED_RE.finditer(ok)] == ["14240.00"]

    # "4821" is not a fineness code, so the label must not reach the rate.
    bad = "22Kt Gold, item 4821 in stock, priced at \u20b9 14240.00 /Gram"
    assert not [m for m in scrape._LABELED_RE.finditer(bad)], (
        "_LABELED_RE must not span an arbitrary number between the karat "
        "label and the rate")


def test_ratio_check_rejects_inconsistent_purities():
    # 22K quoted far off the 22/24 ratio against the 24K on the same page.
    ok, _ = scrape.basis_confirmed({"24K": 15685.35, "22K": 9000.0})
    assert not ok
