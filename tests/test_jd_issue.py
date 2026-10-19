"""The members' issue JSON (jd_issue) and the page that renders it."""
import jd_issue
import jd_page


def _inputs():
    dates = ["2026-10-18", "2026-10-19"]
    matrix = {"a": {"2026-10-18": 100.0, "2026-10-19": 110.0},
              "b": {"2026-10-18": 102.0, "2026-10-19": 100.0},
              "c": {"2026-10-19": 105.0}}
    market = [{"date": d, "low": 100.0, "median": 101.0, "high": 110.0} for d in dates]
    stats = [{"slug": "a", "coverage_pct": 100.0, "median": 105.0,
              "premium_vs_median_pct": 1.5, "pct_days_cheapest": 50.0,
              "avg_daily_move": 10.0, "stdev": 5.0},
             {"slug": "b", "coverage_pct": 100.0, "median": 101.0,
              "premium_vs_median_pct": -0.5, "pct_days_cheapest": 50.0,
              "avg_daily_move": 2.0, "stdev": 1.0}]
    names = {"a": "Alpha Jewellers", "b": "Beta Gold", "c": "Gamma"}
    return dates, matrix, market, stats, names


def test_board_is_latest_day_cheapest_first_with_premium_over_median():
    dates, matrix, _, _, names = _inputs()
    b = jd_issue.board(dates, matrix, names)
    assert [r["n"] for r in b] == ["Beta Gold", "Gamma", "Alpha Jewellers"]
    assert b[1]["p"] == 0.0                      # 105 is the median of 100/105/110
    assert b[0]["p"] < 0 < b[2]["p"]


def test_issue_has_every_section_the_page_reads():
    dates, matrix, market, stats, names = _inputs()
    i = jd_issue.build(dates, matrix, market, stats, {"days": 2}, ["n1", ""],
                       [], {"stance": {}}, {"ok": True, "note": "Hello"}, None,
                       names, ["zz"], "2026-10-19 06:45 UTC", "Disclaimer")
    for k in ("trend", "series", "board", "stats", "weekday", "confidence",
              "outlook", "note", "disclaimer", "last", "excluded", "generated"):
        assert k in i
    assert i["last"] == "2026-10-19"
    assert i["series"][0] == {"d": "2026-10-18", "lo": 100.0, "md": 101.0, "hi": 110.0}
    assert [s["n"] for s in i["stats"]] == ["Beta Gold", "Alpha Jewellers"]
    assert i["confidence"] == ["n1"] and i["note"] == "Hello"


def test_withheld_ai_note_is_absent_not_published():
    dates, matrix, market, stats, names = _inputs()
    i = jd_issue.build(dates, matrix, market, stats, {}, [], [], None,
                       {"ok": False, "reason": "untraceable"}, None, names, [],
                       "", "")
    assert i["note"] is None


def test_page_is_private_and_carries_no_data():
    h = jd_page.build_today()
    assert 'name="robots" content="noindex' in h
    assert "/jd/issue" in h and jd_page.WORKER in h
    assert '"series"' not in h and "const D = {" not in h   # data comes from the Worker only
    assert "__WORKER__" not in h and "__SITE__" not in h


def test_page_escapes_names_from_data():
    h = jd_page.build_today()
    assert "${E(b.n)}" in h and "${E(s.n)}" in h


def test_member_cards_link_to_todays_issue():
    assert "/jd-today" in jd_page.build()
    assert "/jd-today" in jd_page.build_signin()
