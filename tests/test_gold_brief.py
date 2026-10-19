"""The daily gold market brief (gold_brief.py)."""
from datetime import date

import gold_brief as G

H = [
    {"title": "Gold edges lower as firm dollar, elevated yields weigh", "link": "https://x/1", "source": "Reuters"},
    {"title": "Gold rises as Fed rate cut bets build", "link": "https://x/2", "source": "Bloomberg"},
    {"title": "Central banks keep buying gold, WGC says", "link": "https://x/3", "source": "FT"},
    {"title": "Dhanteras demand lifts jewellers' footfall", "link": "https://x/4", "source": "ET"},
    {"title": "Cricket: India win gold at Asian Games", "link": "https://x/5", "source": "X"},
]


def test_headlines_sorted_into_the_forces_that_move_gold():
    t = G.classify(H)
    assert len(t["rates"]) == 2 and len(t["dollar"]) == 1
    assert len(t["central_banks"]) == 1 and len(t["india_demand"]) == 1


def test_brief_reports_measured_moves_and_where_they_came_from():
    b = G.compose(date(2026, 10, 20),
                  {"gold_usd": 4145.0, "usdinr": 95.3, "board24": 14809},
                  {"gold_usd": 4120.0, "usdinr": 95.1, "board24": 14771, "date_disp": "19 Oct"},
                  G.classify(H), [{"title": "Core PCE", "impact": "High"}], 510)
    t = " ".join(b["paragraphs"])
    assert "$4,145 an ounce (+0.61% since 19 Oct)" in t
    assert "weaker by 0.21%" in t
    assert "₹14,809/g" in t and "mostly from the world gold price" in t
    assert "US interest rates (2 headlines)" in t
    assert "Core PCE" in t and "₹510/g" in t
    assert b["summary"].startswith("gold +0.6%")


def test_headlines_are_linked_and_escaped_not_copied():
    b = G.compose(date(2026, 10, 20), {}, None,
                  G.classify([{"title": 'Gold <b>"surges"</b> as Fed pauses', "link": "https://x/9", "source": "S"}]),
                  [], None)
    t = " ".join(b["paragraphs"])
    assert '<a href="https://x/9"' in t and "&lt;b&gt;" in t and 'rel="nofollow noopener"' in t


def test_no_numbers_without_data_and_no_crash_on_empty_day():
    b = G.compose(date(2026, 10, 20), {}, None, {}, [], None)
    assert b["paragraphs"] == ["No clear theme in today's gold headlines."]


def test_previous_day_lookup_skips_today():
    st = {"days": {"2026-10-18": {"snap": {"gold_usd": 1}}, "2026-10-20": {"snap": {"gold_usd": 3}}}}
    p = G.previous(st, date(2026, 10, 20))
    assert p["gold_usd"] == 1 and p["date_disp"] == "18 Oct"
