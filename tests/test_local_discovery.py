"""discover_local's ladder check, and Shape C's snake_case spelling.

Both exist because of one real page. Khanna Jewellers ships a daily-updated
rate config from a Shopify pricing app:

    metalPriceConfig = {"gold_price_24k":16200,"gold_price_22k":14040,
      "gold_price_21k":6343.75,"gold_price_18k":11487,
      "include_taxes":true,"default_tax":3}

The camelCase-only Shape C pattern missed it entirely. Widening the pattern
makes it readable - and readable is exactly the danger, because the numbers
parse cleanly, descend correctly with purity (so ordering_sane passes) and
are wrong: 24K is +6% over market, the 22K/24K ratio is 0.867 rather than
0.9167, gold_price_21k is 6,343.75 where the ladder says ~14,175, and
include_taxes:true says these are GST-inclusive retail figures while this
site stores pre-GST metal rates.

So the two changes are a pair and are tested as one: the extractor may read
this shape, and the ratio check must refuse to call it a rate.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discover_local as D
import scrape


KHANNA_HTML = """
<script>const metalPriceConfig = {"gold_price_24k":16200,
 "gold_price_22k":14040,"gold_price_21k":6343.75,"gold_price_18k":11487,
 "gold_price_14k":8960,"gold_price_10k":3020.86,"silver_price":0,
 "include_taxes":true,"default_tax":3,"version":"V2"};</script>
"""

PNGSONS_HTML = """
<script>{"rates":{"goldPrice24K":15320,"goldPrice24K995":15290,
 "goldPrice22K":14094,"goldPrice18K":11873,"goldPrice14K":9192}}</script>
"""


# ---------------------------------------------------------------- extractor

def test_snake_case_rate_config_is_read():
    """gold_price_24k must parse, not just goldPrice24K."""
    found, _, how = scrape.extract(KHANNA_HTML)
    assert how == "ratejson"
    assert found["24K"] == 16200.0
    assert found["22K"] == 14040.0


def test_camelcase_shape_still_reads():
    """Widening the spelling must not break the shape it was written for."""
    found, _, how = scrape.extract(PNGSONS_HTML)
    assert how == "ratejson"
    assert found["24K"] == 15320.0


def test_995_variant_keys_still_excluded():
    """goldPrice24K995 is the 995 rate and must never bind to 24K."""
    found, _, _ = scrape.extract(PNGSONS_HTML)
    assert found["24K"] == 15320.0, "995 variant leaked into the 999 figure"


def test_undefined_purities_skipped():
    """10K/9K have no PURITY_FRACTION entry, so they cannot be laddered."""
    found, _, _ = scrape.extract(KHANNA_HTML)
    assert "10K" not in found and "21K" not in found


# -------------------------------------------------------------- ladder check

def test_khannas_real_config_is_rejected():
    """The whole point: parses cleanly, is not a metal rate."""
    found, _, _ = scrape.extract(KHANNA_HTML)
    ok, why = D.ladder_sane(found)
    assert not ok
    assert "ratio" in why.lower()


def test_ordering_sane_alone_would_have_passed_it():
    """Shows why this check is needed on top of the existing one - Khanna's
    values DO descend with purity, so try_html reports 'ok'."""
    found, _, _, note = scrape.try_html(KHANNA_HTML)
    assert found is not None and note == "ok"


def test_a_real_ladder_passes():
    ok, why = D.ladder_sane(scrape.derive_ladder(15278.0))
    assert ok
    assert "consistent" in why


def test_real_published_grt_ladder_passes():
    """Actual values from the live board, so the tolerance is not too tight."""
    ok, _ = D.ladder_sane({"24K": 15278.0, "22K": 14005.0,
                           "18K": 11459.0, "14K": 8912.0})
    assert ok


def test_single_purity_allowed_but_flagged():
    """Plenty of real sources publish one rate; it just cannot be cross-checked."""
    ok, why = D.ladder_sane({"24K": 15278.0})
    assert ok
    assert "single purity" in why


def test_making_inclusive_retail_list_rejected():
    """Making charges are not proportional to purity, so the ratios break."""
    ok, _ = D.ladder_sane({"24K": 16000.0, "22K": 15000.0, "18K": 13000.0})
    assert not ok


# ------------------------------------------------------------ candidate list

def test_no_aggregators_among_candidates():
    """Reading a rate off an aggregator would make this site a copy of a copy."""
    from local_candidates import CANDIDATES, DENY_HOSTS
    for c in CANDIDATES:
        host = c["domain"].lower().removeprefix("www.")
        assert host not in DENY_HOSTS, f"{c['name']} is an aggregator"


def test_every_state_and_ut_is_mapped():
    from local_candidates import STATE_CITIES
    assert len(STATE_CITIES) == 36, "28 states + 8 union territories"
    assert all(v for v in STATE_CITIES.values()), "each needs a city to search"
