"""The rules-written morning note (jd_narrative)."""
import re

import jd_narrative as N


def issue(as_of="2026-10-19"):
    return {
        "last": "2026-10-19",
        "trend": {"avg_spread": 480.0},
        "series": [{"d": f"2026-10-{d:02d}", "lo": 14600.0, "md": m, "hi": 15000.0}
                   for d, m in zip(range(13, 20), [14836, 14836, 14800, 14790, 14771, 14771, 14809])],
        "board": [{"n": "Chandukaka Saraf", "v": 14580.0, "p": -1.55},
                  {"n": "PN Gadgil", "v": 14656.0, "p": -1.03}],
        "stats": [{"n": "Chandukaka Saraf", "cheap": 40.5}, {"n": "PN Gadgil", "cheap": 47.0}],
        "outlook": {
            "as_of": as_of,
            "horizons": [{"label": "Next week", "verdict": "Bearish", "range": {"pct": 3.08},
                          "skill": {"usable": True, "ic": -0.046}}],
            "board_levels": {"resistance": [{"price": 15019.0, "distance_pct": 1.86, "touches": 8}],
                             "support": [{"price": 13987.0, "distance_pct": -5.13, "touches": 1}]},
            "board_forecast": {"usable": True, "implied_board_move_pct": 0.29,
                               "implied_board_rupees": 43.0, "unexplained_share": 0.71},
            "expected_move": [{"days": 1, "sigma_rupees": 182.0}],
            "events": [{"title": "Core PCE", "impact": "high", "days_away": 1},
                       {"title": "JOLTS", "impact": "medium", "days_away": 0}],
        },
    }


def test_note_states_todays_board_and_moves():
    t = N.compose(issue())
    assert "₹14,809/g" in t and "up ₹38 on the day" in t
    assert "down ₹27 over the last five sessions" in t


def test_cheapest_names_habit_and_the_regular_cheapest():
    t = N.compose(issue())
    assert "Chandukaka Saraf is cheapest at ₹14,580/g, 1.55% under the median" in t
    assert "PN Gadgil is the most frequent cheapest (47% of days)" in t


def test_a_signal_with_a_bad_record_is_called_that():
    t = N.compose(issue())
    assert "Next week Bearish".lower() in t.lower()
    assert "pointed the wrong way" in t


def test_only_high_impact_events_are_named():
    t = N.compose(issue())
    assert "Core PCE" in t and "JOLTS" not in t


def test_stale_outlook_is_left_out_and_said_so():
    t = N.compose(issue(as_of="2026-09-29"))
    assert "Bearish" not in t and "resistance" not in t and "Core PCE" not in t
    assert "not refreshed today" in t


def test_every_rupee_figure_comes_from_the_issue():
    i = issue(); t = N.compose(i)
    allowed = {14809, 38, 27, 400, 480, 14580, 15019, 13987, 43, 182}
    for m in re.findall(r"₹([\d,]+)", t):
        assert int(m.replace(",", "")) in allowed, m


def test_missing_sections_drop_quietly():
    assert N.compose({"last": "2026-10-19"}) == ""
    t = N.compose({**issue(), "board": []})
    assert "cheapest at" not in t and "₹14,809" in t


def test_indian_grouping():
    assert N._inr(163205) == "₹1,63,205" and N._inr(999) == "₹999"
