"""The outlook engine: indicators, levels, size, and the board link.

Every test here uses a series whose right answer is known in advance,
because the failure mode this file exists to catch is not a crash - it is
a plausible number. A wrong RSI still prints as a number between 0 and 100,
and a support level pulled from a different price regime still looks like a
support level. Both of those shipped once during this build.
"""
import math
from datetime import date

import pytest

import outlook as O


def bars(closes, start="2025-01-01", spread=10.0):
    """Daily bars from a close series, with a fixed high/low spread."""
    d0 = date.fromisoformat(start)
    from datetime import timedelta
    return [{"d": (d0 + timedelta(days=i)).isoformat(),
             "o": c, "h": c + spread, "l": c - spread, "c": c}
            for i, c in enumerate(closes)]


# ─── moving averages ────────────────────────────────────────────────────

def test_sma_aligns_with_the_price_series():
    xs = [1, 2, 3, 4, 5]
    out = O.sma(xs, 3)
    assert len(out) == len(xs)
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(2.0)
    assert out[4] == pytest.approx(4.0)


def test_ema_seeds_from_the_simple_mean_then_smooths():
    xs = [1, 2, 3, 4, 5, 6]
    out = O.ema(xs, 3)
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(2.0)          # seed = mean(1,2,3)
    assert out[3] == pytest.approx(4 * 0.5 + 2.0 * 0.5)
    assert len(out) == len(xs)


def test_ema_is_all_none_when_there_is_not_enough_history():
    assert O.ema([1, 2], 5) == [None, None]


# ─── RSI ────────────────────────────────────────────────────────────────

def test_rsi_is_100_when_every_day_is_an_up_day():
    out = O.rsi(list(range(1, 40)), 14)
    assert out[-1] == pytest.approx(100.0)


def test_rsi_is_0_when_every_day_is_a_down_day():
    out = O.rsi(list(range(40, 1, -1)), 14)
    assert out[-1] == pytest.approx(0.0)


def test_rsi_uses_wilder_smoothing_not_a_rolling_mean():
    """A single large drop after a long rally.

    Wilder's smoothing carries that drop forward for many bars; a naive
    rolling mean drops it out of the window after 14 and snaps back to 100.
    Their disagreement is the whole point of the assertion.
    """
    xs = list(range(1, 31)) + [20]
    out = O.rsi(xs, 14)
    assert out[-1] is not None
    assert 50 < out[-1] < 95, out[-1]


def test_rsi_of_an_unchanged_price_is_50_not_100():
    """A feed that stalls repeats one price. Read naively that is zero
    losses, which the textbook shortcut turns into RSI 100 - the single
    most bullish reading available, produced by a feed that has stopped."""
    assert O.rsi([100.0] * 40, 14)[-1] == pytest.approx(50.0)


def test_rsi_has_no_value_until_it_has_enough_bars():
    out = O.rsi([1, 2, 3], 14)
    assert out == [None, None, None]


# ─── ATR ────────────────────────────────────────────────────────────────

def test_atr_on_constant_range_bars_equals_that_range():
    b = bars([100] * 40, spread=5.0)     # every bar spans exactly 10
    out = O.atr(b, 14)
    assert out[-1] == pytest.approx(10.0)


def test_true_range_accounts_for_a_gap_from_the_previous_close():
    b = [{"d": "a", "o": 100, "h": 101, "l": 99, "c": 100},
         {"d": "b", "o": 120, "h": 121, "l": 119, "c": 120}]
    tr = O.true_range(b)
    # 21, from the previous close to today's high - not the 2-point bar range
    assert tr[1] == pytest.approx(21.0)


# ─── support and resistance ─────────────────────────────────────────────

def test_swing_points_finds_the_peak_of_a_tent():
    b = bars([1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1], spread=0)
    highs, lows = O.swing_points(b, k=5)
    assert [i for i, _ in highs] == [5]


def test_cluster_levels_merges_near_identical_pivots():
    b = bars([100] * 10, spread=0)
    pts = [(1, 100.0), (3, 100.5), (5, 130.0)]
    zones = O.cluster_levels(pts, tol=2.0, bars=b)
    assert len(zones) == 2
    merged = [z for z in zones if z["touches"] == 2][0]
    assert merged["price"] == pytest.approx(100.25)
    assert merged["last_touch"] == b[3]["d"]


def test_levels_ignore_an_old_price_regime():
    """The regression test for the bug this engine shipped with first.

    Five years ago the market traded near 4,800 and turned there dozens of
    times. Ranking the whole history by touch count offered 4,800 as
    "support" for a market at 12,800 - archaeology presented as a level.
    Only the recent window may produce levels.
    """
    old = [4800 + (i % 7) * 20 for i in range(700)]
    recent = [12000 + (i % 11) * 80 for i in range(260)]
    b = bars(old + recent)
    a = O.atr(b, 14)[-1]
    sup, res = O.levels_around(b, price=12700, atr_now=a)
    assert sup, "expected at least one support zone in the recent window"
    for z in sup + res:
        assert z["price"] > 10000, f"level {z['price']} came from the old regime"


def test_levels_are_ordered_by_nearness_to_price():
    b = bars([12000 + (i % 13) * 70 for i in range(300)])
    a = O.atr(b, 14)[-1]
    price = b[-1]["c"]
    sup, res = O.levels_around(b, price, a)
    assert all(z["price"] < price for z in sup)
    assert all(z["price"] > price for z in res)
    if len(sup) > 1:
        assert sup[0]["price"] >= sup[-1]["price"]


def test_levels_report_signed_distance():
    b = bars([12000 + (i % 13) * 70 for i in range(300)])
    a = O.atr(b, 14)[-1]
    price = b[-1]["c"]
    sup, res = O.levels_around(b, price, a)
    assert all(z["distance_pct"] <= 0 for z in sup)
    assert all(z["distance_pct"] >= 0 for z in res)


def test_levels_return_nothing_rather_than_guessing_without_atr():
    assert O.levels_around(bars([1, 2, 3]), 2, None) == ([], [])


def test_floor_pivots_bracket_the_pivot():
    b = bars(list(range(100, 130)))
    p = O.pivot_points(b, n=21)
    assert p["s2"] < p["s1"] < p["pivot"] < p["r1"] < p["r2"]


def test_floor_pivots_need_a_full_window():
    assert O.pivot_points(bars([1, 2, 3]), n=21) is None


# ─── magnitude ──────────────────────────────────────────────────────────

def test_expected_move_scales_with_the_square_root_of_time():
    import random
    random.seed(11)
    closes, p = [1000.0], 1000.0
    for _ in range(400):
        p *= 1 + random.gauss(0, 0.01)
        closes.append(p)
    out = O.expected_range(closes, atr_now=12.0, price=closes[-1])
    by_h = {r["days"]: r for r in out if "sigma_pct" in r}
    assert by_h[5]["sigma_pct"] == pytest.approx(
        by_h[1]["sigma_pct"] * math.sqrt(5), rel=0.02)


def test_expected_move_reports_the_observed_spread_beside_the_model():
    import random
    random.seed(3)
    closes, p = [1000.0], 1000.0
    for _ in range(400):
        p *= 1 + random.gauss(0, 0.012)
        closes.append(p)
    out = O.expected_range(closes, atr_now=15.0, price=closes[-1])
    for r in out:
        if "sigma_pct" in r:
            assert r["observed_68_pct"] > 0
            assert r["n"] >= 20


def test_expected_move_says_nothing_on_a_short_series():
    assert O.expected_range([1, 2, 3], 1.0, 3) == []


# ─── seasonality ────────────────────────────────────────────────────────

def test_seasonality_refuses_to_speak_from_two_years():
    b = ([{"d": f"2024-03-{d:02d}", "o": 1, "h": 1, "l": 1, "c": 100}
          for d in range(1, 21)] +
         [{"d": f"2025-03-{d:02d}", "o": 1, "h": 1, "l": 1, "c": 100}
          for d in range(1, 21)])
    out = O.month_seasonality(b, 3)
    assert out["n"] == 2
    assert "mean_pct" not in out


def test_seasonality_carries_its_sample_size_and_spread():
    b = []
    for i, yr in enumerate((2021, 2022, 2023, 2024, 2025)):
        for d in range(1, 21):
            b.append({"d": f"{yr}-10-{d:02d}", "o": 1, "h": 1, "l": 1,
                      "c": 100 + d * (1 if i % 2 == 0 else -1)})
    out = O.month_seasonality(b, 10)
    assert out["n"] == 5
    assert out["month"] == "October"
    assert out["positive_years"] == 3
    assert out["stdev_pct"] > 0
    assert len(out["years"]) == 5


def test_seasonality_skips_a_stub_of_a_month():
    b = ([{"d": f"2024-03-{d:02d}", "o": 1, "h": 1, "l": 1, "c": 100 + d}
          for d in range(1, 4)] +                       # 3 days: not a month
         [{"d": f"2025-03-{d:02d}", "o": 1, "h": 1, "l": 1, "c": 100 + d}
          for d in range(1, 21)])
    assert O.month_seasonality(b, 3)["n"] == 1


# ─── board pass-through ─────────────────────────────────────────────────

def _lagged_board(parity, beta, lag):
    """A board that mechanically follows parity by `beta` after `lag` days."""
    board = [("2026-01-01", 1000.0)]
    for i in range(1, len(parity)):
        if i - lag >= 1:
            move = parity[i - lag][1] / parity[i - lag - 1][1] - 1
        else:
            move = 0.0
        board.append((parity[i][0], board[-1][1] * (1 + beta * move)))
    return board


def test_passthrough_recovers_the_lag_and_coefficient_it_was_given():
    import random
    random.seed(5)
    parity, p = [], 1000.0
    for i in range(120):
        p *= 1 + random.gauss(0, 0.01)
        parity.append((f"d{i:03d}", p))
    board = _lagged_board(parity, beta=0.6, lag=1)
    out = O.passthrough(board, parity)
    assert out["best_lag"]["lag_days"] == 1
    assert out["best_lag"]["beta"] == pytest.approx(0.6, abs=0.05)
    assert out["best_lag"]["corr"] > 0.95


def test_passthrough_reports_the_board_premium_over_parity():
    parity = [(f"d{i:03d}", 10000.0) for i in range(40)]
    board = [(f"d{i:03d}", 11500.0) for i in range(40)]
    out = O.passthrough(board, parity)
    assert out["board_over_parity"]["median"] == pytest.approx(1.15)
    assert out["board_over_parity"]["n"] == 40


def test_passthrough_needs_a_real_sample():
    assert O.passthrough([("a", 1)], [("a", 1)]) is None


def test_board_forecast_stands_down_when_the_link_is_weak():
    import random
    random.seed(9)
    parity, board, p, b = [], [], 1000.0, 1000.0
    for i in range(120):                   # two unrelated random walks
        p *= 1 + random.gauss(0, 0.01)
        b *= 1 + random.gauss(0, 0.01)
        parity.append((f"d{i:03d}", p))
        board.append((f"d{i:03d}", b))
    pt = O.passthrough(board, parity)
    inr = [{"d": d, "o": v, "h": v, "l": v, "c": v} for d, v in parity]
    out = O.board_forecast(board, inr, pt)
    assert out["usable"] is False
    assert "not currently tracking" in out["why"]


def test_board_forecast_applies_the_measured_coefficient():
    parity = [("2026-01-01", 10000.0), ("2026-01-02", 10100.0)]
    inr = [{"d": d, "o": v, "h": v, "l": v, "c": v} for d, v in parity]
    board = [("2026-01-01", 11500.0), ("2026-01-02", 11500.0)]
    pt = {"best_lag": {"lag_days": 1, "beta": 0.5, "corr": 0.7, "n": 70}}
    out = O.board_forecast(board, inr, pt)
    assert out["usable"] is True
    assert out["international_move_pct"] == pytest.approx(1.0, abs=0.01)
    assert out["implied_board_move_pct"] == pytest.approx(0.5, abs=0.01)
    assert out["to_board"] == pytest.approx(11500 * 1.005, abs=1)


# ─── stance ─────────────────────────────────────────────────────────────

def _trend(n=320, step=0.0, noise=0.0, start=10000.0, seed=1):
    import random
    random.seed(seed)
    out, p = [], start
    for _ in range(n):
        p *= 1 + step + (random.gauss(0, noise) if noise else 0)
        out.append(p)
    return out


def test_stance_calls_a_sustained_rally_bullish():
    s = O.stance(bars(_trend(step=0.002, noise=0.003)))
    assert s["direction"] == "up"
    assert s["score"] > 15


def test_stance_calls_a_sustained_slide_bearish():
    s = O.stance(bars(_trend(step=-0.002, noise=0.003)))
    assert s["direction"] == "down"
    assert s["score"] < -15


def test_stance_calls_a_market_pinned_to_its_own_average_neutral():
    """Price flat on every measure: no gap to the averages, no momentum.

    A driftless RANDOM WALK is not this test - over 320 days it wanders
    several percent from where it started and reads as a trend, which is
    the correct reading of that snapshot. Neutral is a property of the
    moment, not of the process that generated it.
    """
    s = O.stance(bars([10000.0] * 320))
    assert s["label"] == "Neutral", (s["label"], s["score"])
    assert abs(s["score"]) < 15


def test_stance_orders_a_strong_trend_above_a_weak_one():
    strong = O.stance(bars(_trend(step=0.004, noise=0.002)))
    weak = O.stance(bars(_trend(step=0.0005, noise=0.002)))
    falling = O.stance(bars(_trend(step=-0.004, noise=0.002)))
    assert strong["score"] > weak["score"] > falling["score"]


def test_stance_needs_enough_history_to_have_a_200_day_average():
    assert O.stance(bars(_trend(n=100))) is None


def test_stance_components_carry_their_own_weight_and_detail():
    s = O.stance(bars(_trend(step=0.001, noise=0.004)))
    assert s["components"]
    for c in s["components"]:
        assert -1.0 <= c["score"] <= 1.0
        assert 0 < c["weight"] <= 1
        assert c["detail"]


def test_stance_discounts_conviction_when_price_is_stretched():
    """A near-vertical rally should read bullish but NOT confident.

    An RSI in the 80s is the market at its most convincing and its least
    reliable. If conviction did not fall here, the page would shout loudest
    exactly where it is most likely to be wrong.
    """
    hot = O.stance(bars(_trend(step=0.006, noise=0.001)))
    assert hot["direction"] == "up"
    assert hot["caveats"], "a stretched market should say so"
    assert hot["penalties"], "a stretched market should carry a penalty"
    # The claim is not that a melt-up is less convincing than a chop - a
    # strong trend genuinely agrees with itself. It is that the stretch is
    # deducted from what the agreement alone would have claimed.
    assert hot["conviction"] < hot["agreement"]
    assert hot["conviction"] == pytest.approx(
        hot["agreement"] * math.prod(p["factor"] for p in hot["penalties"]),
        abs=0.01)


def test_stance_conviction_equals_agreement_when_nothing_is_stretched():
    calm = O.stance(bars([10000.0] * 320))
    assert calm["penalties"] == []
    assert calm["conviction"] == pytest.approx(calm["agreement"], abs=0.01)


def test_stance_reads_a_weak_rupee_as_bullish_for_rupee_gold():
    flat = bars(_trend(step=0.0, noise=0.002, seed=4))
    firm = [90.0] * 320
    weak = [90.0 * (1 + 0.0006) ** i for i in range(320)]
    s_firm = O.stance(flat, firm)
    s_weak = O.stance(flat, weak)
    assert s_weak["score"] > s_firm["score"]
    names = [c["name"] for c in s_weak["components"]]
    assert "Rupee (USD/INR)" in names


# ─── what moved it ──────────────────────────────────────────────────────

def test_decompose_attributes_a_pure_gold_move_to_gold():
    usd = [100.0] * 30 + [110.0]
    fx = [90.0] * 31
    out = O.decompose(usd, fx, days=20)
    assert out["driver"] == "gold"
    assert out["rupee_pct"] == pytest.approx(0.0)
    assert out["gold_usd_pct"] == pytest.approx(10.0)


def test_decompose_attributes_a_pure_currency_move_to_the_rupee():
    usd = [100.0] * 31
    fx = [90.0] * 30 + [99.0]
    out = O.decompose(usd, fx, days=20)
    assert out["driver"] == "rupee"
    assert out["gold_usd_pct"] == pytest.approx(0.0)


def test_decompose_total_is_the_compounded_move_not_the_sum():
    usd = [100.0] * 30 + [110.0]
    fx = [90.0] * 30 + [99.0]
    out = O.decompose(usd, fx, days=20)
    assert out["total_pct"] == pytest.approx(21.0, abs=0.01)   # not 20
    assert out["driver"] == "both"


# ─── event risk ─────────────────────────────────────────────────────────

CAL = [
    {"title": "Non-Farm Employment Change", "date": "10-02-2026",
     "impact": "High", "country": "USD"},
    {"title": "Unemployment Rate", "date": "10-02-2026",
     "impact": "High", "country": "USD"},
    {"title": "FOMC Member Waller Speaks", "date": "09-30-2026",
     "impact": "Medium", "country": "USD"},
    {"title": "JOLTS Job Openings", "date": "09-29-2026",
     "impact": "Medium", "country": "USD"},
    {"title": "Natural Gas Storage", "date": "09-30-2026",
     "impact": "Low", "country": "USD"},
    {"title": "Core CPI m/m", "date": "2026-10-01",
     "impact": "High", "country": "USD"},
]


def test_event_risk_parses_the_feeds_mm_dd_yyyy_dates():
    """The bug that made a payrolls week look quiet.

    The calendar feed dates as MM-DD-YYYY. Parsing it as ISO threw on every
    row and the list came back empty, which reads exactly like a week with
    nothing scheduled.
    """
    out = O.event_risk(CAL, today=date(2026, 9, 29))
    assert out, "MM-DD-YYYY dates must parse"
    assert {e["title"] for e in out} >= {"Non-Farm Employment Change",
                                         "Unemployment Rate"}


def test_event_risk_accepts_iso_dates_too():
    out = O.event_risk(CAL, today=date(2026, 9, 29))
    assert "Core CPI m/m" in {e["title"] for e in out}


def test_event_risk_drops_speaker_chatter():
    out = O.event_risk(CAL, today=date(2026, 9, 29))
    assert all("Speaks" not in e["title"] for e in out)


def test_event_risk_drops_low_impact_noise():
    out = O.event_risk(CAL, today=date(2026, 9, 29))
    assert all(e["title"] != "Natural Gas Storage" for e in out)


def test_event_risk_keeps_every_high_impact_release_over_the_cap():
    """Friday's payrolls must not be crowded out by Tuesday's minor prints.

    Sorting by date and truncating did exactly that once.
    """
    filler = [{"title": f"JOLTS Job Openings {i}", "date": "09-29-2026",
               "impact": "Medium", "country": "USD"} for i in range(20)]
    out = O.event_risk(filler + CAL, today=date(2026, 9, 29))
    titles = {e["title"] for e in out}
    assert "Non-Farm Employment Change" in titles
    assert "Unemployment Rate" in titles
    assert "Core CPI m/m" in titles


def test_event_risk_ignores_anything_past_the_horizon():
    far = [{"title": "Non-Farm Employment Change", "date": "12-04-2026",
            "impact": "High", "country": "USD"}]
    assert O.event_risk(far, today=date(2026, 9, 29)) == []


def test_event_risk_survives_an_unparseable_date():
    bad = [{"title": "Core CPI m/m", "date": "sometime", "impact": "High"}]
    assert O.event_risk(bad, today=date(2026, 9, 29)) == []


def test_event_risk_on_an_empty_feed_is_empty_not_an_error():
    assert O.event_risk([], today=date(2026, 9, 29)) == []
    assert O.event_risk(None, today=date(2026, 9, 29)) == []


# ─── assembly ───────────────────────────────────────────────────────────

def _inr_bars(n=400, step=0.001, seed=2):
    import random
    random.seed(seed)
    from datetime import timedelta
    d0 = date(2025, 1, 1)
    out, usd, fx = [], 2000.0, 85.0
    for i in range(n):
        usd *= 1 + step + random.gauss(0, 0.004)
        fx *= 1 + random.gauss(0, 0.001)
        c = usd * fx / O.OZ_GRAMS
        out.append({"d": (d0 + timedelta(days=i)).isoformat(),
                    "o": c, "h": c * 1.004, "l": c * 0.996, "c": c,
                    "usd": usd, "fx": fx})
    return out


def test_build_produces_every_section():
    d = O.build(_inr_bars(), calendar=CAL)
    for key in ("basis", "stance", "levels", "expected_move",
                "seasonality", "drivers", "events", "disclaimer"):
        assert key in d, key
    assert d["basis"]["price"] > 0
    assert d["basis"]["history_days"] == 400


def test_build_works_without_a_board_or_a_calendar():
    d = O.build(_inr_bars())
    assert d["board"] is None
    assert d["events"] == []
    assert "board_forecast" not in d
    assert d["stance"] is not None


def test_build_reports_the_basis_it_actually_used():
    b = _inr_bars()
    d = O.build(b)
    assert d["as_of"] == b[-1]["d"]
    assert d["basis"]["usd_oz"] == pytest.approx(b[-1]["usd"], abs=0.01)
    assert d["basis"]["usd_inr"] == pytest.approx(b[-1]["fx"], abs=0.001)


def test_build_ties_the_board_to_the_international_series():
    b = _inr_bars()
    board = [(x["d"], x["c"] * 1.15) for x in b[-80:]]
    d = O.build(b, board=board)
    assert d["board"]["board_over_parity"]["median"] == pytest.approx(1.15, abs=0.01)
    assert "board_forecast" in d


def test_align_drops_board_days_with_no_international_bar_from_both_sides():
    """If one side is trimmed and the other is not, every correlation below
    is computed against a series shifted by a day and is garbage."""
    b = _inr_bars(n=300)
    board = [("2024-06-01", 100.0)] + [(x["d"], x["c"] * 1.1) for x in b[-40:]]
    aligned = O._align(board, b)
    assert len(aligned) == len(board)
    assert all(p is not None for _, p in aligned)


def test_align_carries_the_last_close_onto_a_non_trading_day():
    b = [{"d": "2026-01-02", "o": 1, "h": 1, "l": 1, "c": 100.0},
         {"d": "2026-01-05", "o": 1, "h": 1, "l": 1, "c": 110.0}]
    board = [("2026-01-03", 1.0), ("2026-01-05", 1.0)]
    aligned = O._align(board, b)
    # Saturday reads Friday's close, which is the price the board reacted to
    assert aligned[0][1] == 100.0
    assert aligned[1][1] == 110.0


def test_to_inr_per_gram_converts_and_keeps_the_inputs():
    bars_usd = [{"d": "2026-01-05", "o": 2000.0, "h": 2010.0,
                 "l": 1990.0, "c": 2000.0}]
    out = O.to_inr_per_gram(bars_usd, {"2026-01-05": 90.0})
    assert out[0]["c"] == pytest.approx(2000 * 90 / O.OZ_GRAMS)
    assert out[0]["usd"] == 2000.0
    assert out[0]["fx"] == 90.0


def test_to_inr_per_gram_uses_the_last_published_fx_on_a_holiday():
    bars_usd = [{"d": "2026-01-06", "o": 2000.0, "h": 2000.0,
                 "l": 2000.0, "c": 2000.0}]
    out = O.to_inr_per_gram(bars_usd, {"2026-01-05": 90.0})
    assert out[0]["fx"] == 90.0


def test_to_inr_per_gram_drops_a_bar_with_no_fx_before_it():
    bars_usd = [{"d": "2020-01-01", "o": 1, "h": 1, "l": 1, "c": 1}]
    assert O.to_inr_per_gram(bars_usd, {"2026-01-05": 90.0}) == []


def test_build_disclaims_what_it_is():
    d = O.build(_inr_bars())
    assert "not investment advice" in d["disclaimer"]


# ─── translating parity levels onto the board ───────────────────────────

RATIO = {"median": 1.15, "stdev": 0.01, "n": 72}


def test_to_board_applies_the_measured_premium():
    out = O.to_board([{"price": 10000.0, "touches": 3, "distance_pct": -2.0,
                       "last_touch": "2026-09-01"}], RATIO)
    assert out[0]["price"] == pytest.approx(11500)
    assert out[0]["parity_price"] == 10000.0


def test_to_board_bands_the_level_by_the_premiums_own_dispersion():
    out = O.to_board([{"price": 10000.0, "touches": 3, "distance_pct": -2.0,
                       "last_touch": "2026-09-01"}], RATIO)
    assert out[0]["low"] == pytest.approx(11400)
    assert out[0]["high"] == pytest.approx(11600)
    assert out[0]["low"] < out[0]["price"] < out[0]["high"]


def test_to_board_widens_the_band_when_the_premium_is_unstable():
    steady = O.to_board([{"price": 10000.0, "touches": 1, "distance_pct": 0,
                          "last_touch": "x"}], {"median": 1.15, "stdev": 0.005})
    drifting = O.to_board([{"price": 10000.0, "touches": 1, "distance_pct": 0,
                            "last_touch": "x"}], {"median": 1.15, "stdev": 0.04})
    assert ((drifting[0]["high"] - drifting[0]["low"])
            > (steady[0]["high"] - steady[0]["low"]))


def test_to_board_says_nothing_without_a_measured_premium():
    assert O.to_board([{"price": 1.0, "touches": 1, "distance_pct": 0,
                        "last_touch": "x"}], None) == []
