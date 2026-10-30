"""D.P. Jewellers' rate feed: the per-gram gold rates, current days only."""
from datetime import date

import collect

FEED = {"success": True, "data": [
    {"metal_type": "gold", "purity_description": "18KT", "sale_rate": "10440.0", "open_date": "2026-10-30"},
    {"metal_type": "gold", "purity_description": "14KT", "sale_rate": "8120.0", "open_date": "2026-10-30"},
    {"metal_type": "silver", "purity_description": "Silver", "sale_rate": "182.0", "open_date": "2026-10-30"},
    {"metal_type": "gold", "purity_description": "24KT", "sale_rate": "13920.0", "open_date": "2026-10-30"},
    {"metal_type": "gold", "purity_description": "22KT", "sale_rate": "12751.0", "open_date": "2026-10-30"},
    {"metal_type": "platinum", "purity_description": "Platinum", "sale_rate": "5300.0", "open_date": "2026-10-30"},
]}


def test_reads_every_gold_karat_and_nothing_else():
    found, counts = collect.parse_dp_rates(FEED, today=date(2026, 10, 30))
    assert found == {"24K": 13920.0, "22K": 12751.0, "18K": 10440.0, "14K": 8120.0}
    assert collect.ordering_sane(found)[0]


def test_yesterdays_board_still_counts_before_the_morning_update():
    assert collect.parse_dp_rates(FEED, today=date(2026, 10, 31))


def test_an_old_board_is_refused():
    assert collect.parse_dp_rates(FEED, today=date(2026, 11, 2)) is None


def test_a_failed_answer_is_refused():
    assert collect.parse_dp_rates({"success": False, "data": FEED["data"]}) is None
    assert collect.parse_dp_rates("<html>Just a moment...</html>") is None
