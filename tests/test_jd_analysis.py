"""Analysis behind Jewellers Digest, the paid B2B report.

Tested against hand-computed inputs rather than live data: someone is paying
for these numbers, so each one needs to be checkable by reading the test.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jd_analysis as A

BRANDS = [
    {"id": 1, "slug": "cheap", "active": True},
    {"id": 2, "slug": "mid", "active": True},
    {"id": 3, "slug": "dear", "active": True},
    {"id": 9, "slug": "gone", "active": False},
]


def row(bid, d, v, status="published"):
    return {"brand_id": bid, "rate_date": d,
            "canonical_24k_pre_gst": v, "status": status}


# Three brands, three days. Medians are 100, 110, 120.
ROWS = [
    row(1, "2026-01-01", 90), row(2, "2026-01-01", 100), row(3, "2026-01-01", 110),
    row(1, "2026-01-02", 100), row(2, "2026-01-02", 110), row(3, "2026-01-02", 120),
    row(1, "2026-01-03", 110), row(2, "2026-01-03", 120), row(3, "2026-01-03", 130),
]


def built(rows=None, brands=None, **kw):
    dates, matrix, excl = A.build_matrix(rows or ROWS, brands or BRANDS, **kw)
    market = A.daily_market(dates, matrix)
    return dates, matrix, excl, market


# ------------------------------------------------------------------ matrix

def test_only_published_rows_are_used():
    rows = ROWS + [row(2, "2026-01-04", 999, "quarantined"),
                   row(2, "2026-01-05", 888, "estimated")]
    dates, matrix, _, _ = built(rows)
    assert "2026-01-04" not in matrix["mid"]
    assert "2026-01-05" not in matrix["mid"]
    assert len(dates) == 3


def test_inactive_brands_excluded_and_named():
    """A brand off the board must not appear in a paid report - one was
    removed for publishing a product price as a gold rate."""
    rows = ROWS + [row(9, "2026-01-01", 500)]
    _, matrix, excl, _ = built(rows)
    assert "gone" not in matrix
    assert excl == ["gone"], "excluded brands must be reported, not silently dropped"


def test_inactive_can_be_included_deliberately():
    rows = ROWS + [row(9, "2026-01-01", 500)]
    _, matrix, excl, _ = built(rows, active_only=False)
    assert "gone" in matrix and excl == []


def test_missing_day_is_skipped_not_carried_forward():
    rows = [r for r in ROWS if not (r["brand_id"] == 2
                                    and r["rate_date"] == "2026-01-02")]
    _, matrix, _, market = built(rows)
    assert "2026-01-02" not in matrix["mid"]
    day2 = [m for m in market if m["date"] == "2026-01-02"][0]
    assert day2["brands"] == 2, "absent brand must not inflate the count"
    assert day2["median"] == 110, "median of the two present brands"


# ------------------------------------------------------------------ market

def test_daily_market_low_median_high_spread():
    _, _, _, market = built()
    d1 = market[0]
    assert (d1["low"], d1["median"], d1["high"]) == (90, 100, 110)
    assert d1["spread"] == 20
    assert round(d1["spread_pct"], 3) == round(20 / 90 * 100, 3)


def test_market_trend_over_window():
    _, _, _, market = built()
    t = A.market_trend(market)
    assert t["open"] == 100 and t["close"] == 120
    assert t["change"] == 20
    assert t["change_pct"] == 20.0
    assert t["days"] == 3
    assert t["avg_spread"] == 20


# ------------------------------------------------------------------ brands

def test_premium_is_mean_of_daily_gaps():
    """cheap is 10 below a median that rises 100/110/120, so the daily gaps
    differ and their mean is NOT the gap of the means."""
    dates, matrix, _, market = built()
    s = {x["slug"]: x for x in A.brand_stats(dates, matrix, market)}
    expect = sum([(90 / 100 - 1), (100 / 110 - 1), (110 / 120 - 1)]) / 3 * 100
    assert abs(s["cheap"]["premium_vs_median_pct"] - round(expect, 3)) < 0.01
    assert s["mid"]["premium_vs_median_pct"] == 0.0


def test_cheapest_and_dearest_counts():
    dates, matrix, _, market = built()
    s = {x["slug"]: x for x in A.brand_stats(dates, matrix, market)}
    assert s["cheap"]["days_cheapest"] == 3
    assert s["cheap"]["pct_days_cheapest"] == 100.0
    assert s["cheap"]["days_dearest"] == 0
    assert s["dear"]["days_dearest"] == 3


def test_stats_sorted_cheapest_premium_first():
    dates, matrix, _, market = built()
    order = [x["slug"] for x in A.brand_stats(dates, matrix, market)]
    assert order == ["cheap", "mid", "dear"]


def test_daily_move_and_unchanged_days():
    rows = [row(1, "2026-01-01", 100), row(1, "2026-01-02", 100),
            row(1, "2026-01-03", 110)]
    dates, matrix, _, market = built(rows, [{"id": 1, "slug": "cheap",
                                             "active": True}])
    s = A.brand_stats(dates, matrix, market)[0]
    assert s["days_unchanged"] == 1
    assert s["avg_daily_move"] == 5.0    # moves of 0 and 10


def test_coverage_percent():
    rows = [r for r in ROWS if not (r["brand_id"] == 2
                                    and r["rate_date"] == "2026-01-02")]
    dates, matrix, _, market = built(rows)
    s = {x["slug"]: x for x in A.brand_stats(dates, matrix, market)}
    assert s["mid"]["coverage_pct"] == round(2 / 3 * 100, 1)


# -------------------------------------------------------------- disclosure

def test_weekday_reports_sample_size():
    """n must be present - ten weeks cannot support a seasonal claim."""
    _, _, _, market = built()
    for w in A.weekday_pattern(market):
        assert w["n"] >= 1 and "mean_median" in w


def test_confidence_notes_state_the_bullion_gap():
    """The report must say outright that premium-over-bullion is absent,
    since that is the metric a jeweller would most expect to find."""
    dates, matrix, _, market = built()
    notes = " ".join(A.describe_confidence(dates, matrix, market)).lower()
    assert "bullion" in notes
    assert "not" in notes and "premium" in notes


def test_confidence_notes_mention_removed_brands():
    dates, matrix, _, market = built()
    notes = " ".join(A.describe_confidence(dates, matrix, market)).lower()
    assert "removed" in notes or "no longer" in notes
