"""The guard on AI-written commentary.

The model is shown facts computed by code and asked to write them up. This
tests the check that runs on what it writes: every rupee-scale figure in the
note must trace back to those facts. A paid report that quotes an invented
rate is worse than one with no commentary at all, and fluent prose is far
better at looking plausible than a bad collector ever was.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jd_ai_report as R

FACTS = {
    "market": {"median_last_day": 14889.0, "avg_spread": 479.89,
               "change_pct": 3.72, "high": 16396.36},
    "today": {"cheapest": 14685.0, "dearest": 15730.0, "spread": 1045.0},
    "cheapest_jewellers": [{"brand": "png", "latest": 14685.0,
                            "avg_premium_vs_market_pct": -0.96}],
}


def test_clean_note_passes():
    note = ("The market median closed at 14,889 today. The gap between the "
            "cheapest counter at 14,685 and the dearest at 15,730 was 1,045.")
    assert R.untraceable_figures(note, FACTS) == []


def test_invented_rate_is_caught():
    """The failure that matters: a plausible rate nobody computed."""
    note = "The market median closed at 15,240 today."
    assert R.untraceable_figures(note, FACTS) == ["15,240"]


def test_one_invented_figure_among_real_ones_is_caught():
    note = ("Median 14,889, spread 1,045, and bullion sat at 14,100 " 
            "for most of the session.")
    bad = R.untraceable_figures(note, FACTS)
    assert "14,100" in bad and "14,889" not in bad


def test_rounding_is_tolerated():
    """'about 14,890' for 14,889.0 is honest prose, not invention."""
    assert R.untraceable_figures("around 14,890 per gram", FACTS) == []


def test_unformatted_and_formatted_match_equally():
    assert R.untraceable_figures("14889 per gram", FACTS) == []
    assert R.untraceable_figures("14,889 per gram", FACTS) == []


def test_integer_part_of_a_decimal_fact_matches():
    """avg_spread is 479.89; writing 'Rs 480' is the same number."""
    assert R.untraceable_figures("an average spread of 480", FACTS) == []


def test_percentages_are_not_policed():
    """Percentages are routinely derived in prose and are not rupee figures."""
    assert R.untraceable_figures("up 3.72% over the window, about 2% of that "
                                 "in the last week", FACTS) == []


def test_small_counts_are_not_policed():
    assert R.untraceable_figures("across 21 jewellers over 72 days", FACTS) == []


def test_facts_carry_no_bullion_benchmark():
    """The note must not be able to cite one, because none is supplied."""
    ctx = {"trend": {"from": "2026-07-20", "to": "2026-09-29", "days": 72,
                     "open": 14355.0, "close": 14889.0, "change": 534.0,
                     "change_pct": 3.72, "high": 16396.0, "low": 14355.0,
                     "range_pct": 14.22, "avg_spread": 480.0,
                     "widest_spread": 1090.0, "widest_spread_date": "2026-07-22"},
           "stats": [{"slug": "a", "latest": 1.0, "premium_vs_median_pct": 0.0,
                      "pct_days_cheapest": 1.0}] * 8,
           "market": [{"date": "2026-09-28", "brands": 21, "low": 1.0,
                       "median": 2.0, "high": 3.0, "spread": 1.0},
                      {"date": "2026-09-29", "brands": 21, "low": 1.0,
                       "median": 2.0, "high": 3.0, "spread": 1.0}]}
    f = R.facts_from(ctx)
    # No fact VALUE may be a benchmark; the only mention of one is the
    # explicit statement that it is absent.
    numeric_keys = str({k: v for k, v in f.items()
                        if k != "not_in_this_data"}).lower()
    assert "ibja" not in numeric_keys and "bullion" not in numeric_keys
    assert any("bullion" in s for s in f["not_in_this_data"])


def test_generate_withholds_the_note_when_a_figure_is_untraceable(monkeypatch):
    """End to end: a bad note must not be returned as if it were fine."""
    monkeypatch.setattr(R, "write_note",
                        lambda facts, key=None: ("Median was 99,999 today.", None))
    ctx = {"trend": {"from": "a", "to": "b", "days": 1, "open": 1, "close": 1,
                     "change": 0, "change_pct": 0, "high": 1, "low": 1,
                     "range_pct": 0, "avg_spread": 1, "widest_spread": 1,
                     "widest_spread_date": "a"},
           "stats": [{"slug": "x", "latest": 1, "premium_vs_median_pct": 0,
                      "pct_days_cheapest": 0}] * 8,
           "market": [{"date": "a", "brands": 1, "low": 1, "median": 1,
                       "high": 1, "spread": 0}]}
    out = R.generate(ctx)
    assert out["ok"] is False
    assert out["note"] is None, "a note with an invented figure must not ship"
    assert "99,999" in out["reason"]
    assert out["draft"], "the rejected draft is kept so the failure can be read"


def test_generate_reports_api_failure_without_crashing(monkeypatch):
    def boom(facts, key=None):
        raise RuntimeError("no API key configured")
    monkeypatch.setattr(R, "write_note", boom)
    out = R.generate({"trend": {"from": "a", "to": "b", "days": 1, "open": 1,
                                "close": 1, "change": 0, "change_pct": 0,
                                "high": 1, "low": 1, "range_pct": 0,
                                "avg_spread": 1, "widest_spread": 1,
                                "widest_spread_date": "a"},
                      "stats": [{"slug": "x", "latest": 1,
                                 "premium_vs_median_pct": 0,
                                 "pct_days_cheapest": 0}] * 8,
                      "market": [{"date": "a", "brands": 1, "low": 1,
                                  "median": 1, "high": 1, "spread": 0}]})
    assert out["ok"] is False and out["note"] is None
    assert "RuntimeError" in out["reason"]


def test_model_is_the_current_opus():
    assert R.MODEL == "claude-opus-5-5"


def test_system_prompt_forbids_inventing_and_bullion_claims():
    s = R.SYSTEM.lower()
    assert "only numbers present" in s
    assert "bullion" in s and "never" in s
