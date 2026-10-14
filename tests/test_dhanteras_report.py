"""The Dhanteras report is written to be quoted, so its numbers must be right
and its claims must be ones the data supports."""
import csv
import io
from datetime import date

import dhanteras_report as dr


def inr(x):
    return f"₹{x:,.0f}"


DASH = {
    # rate22 per gram; making % per category
    "Alpha":   {"rates": {"22": 13600.0}, "mc": {"Ring": {"pct": 20.0, "n": 40, "conf": "high"},
                                                "Bangle": {"pct": 15.0, "n": 30, "conf": "high"}}},
    "Beta":    {"rates": {"22": 13500.0}, "mc": {"Ring": {"pct": 30.0, "n": 25, "conf": "high"},
                                                "Bangle": {"pct": 25.0, "n": 12, "conf": "medium"}}},
    "Gamma":   {"rates": {"22": 13700.0}, "mc": {"Ring": {"pct": 18.0, "n": 50, "conf": "high"},
                                                "Bangle": {"pct": 40.0, "n": 2, "conf": "low"}}},
    "Delta":   {"rates": {"22": 13650.0}, "mc": {"Ring": {"pct": 22.0, "n": 9, "conf": "medium"},
                                                "Bangle": {"pct": 18.0, "n": 20, "conf": "high"}}},
}


def test_bill_matches_the_calculator_formula():
    """gold + making on gold + 3% GST on both - same as the calculator."""
    b = dr.bill(13000.0, 20.0)
    assert b["gold"] == 130000.0
    assert b["making"] == 26000.0
    assert round(b["gst"], 2) == round((130000 + 26000) * 0.03, 2)
    assert round(b["total"], 2) == round(156000 * 1.03, 2)


def test_low_confidence_is_excluded_not_caveated():
    cats = dr.compute(DASH)
    bangle = [r["jeweller"] for r in cats["Bangle"]["rows"]]
    assert "Gamma" not in bangle          # n=2, low confidence


def test_rows_are_cheapest_first_and_the_gap_is_right():
    cats = dr.compute(DASH)
    ring = cats["Ring"]
    totals = [r["total"] for r in ring["rows"]]
    assert totals == sorted(totals)
    assert ring["gap"] == ring["dearest"]["total"] - ring["cheapest"]["total"]


def test_a_category_needs_three_jewellers():
    tiny = {k: v for k, v in DASH.items() if k in ("Alpha", "Beta")}
    assert dr.compute(tiny) == {}


def test_lowest_rate_is_not_assumed_to_be_cheapest():
    """Beta has the lowest rate but its 30% ring making charge makes it the
    dearest ring - the finding the report exists to surface."""
    cats = dr.compute(DASH)
    facts = dr.findings(cats, [], inr)
    assert any("lowest gold rate does not buy the cheapest" in f for f in facts)
    assert cats["Ring"]["dearest"]["jeweller"] == "Beta"


def test_findings_do_not_claim_a_ratio():
    """An earlier draft said making charges move the bill "N times as much"
    as the rate, dividing a bill gap that already contains the rate gap.
    State both gaps instead."""
    facts = " ".join(dr.findings(dr.compute(DASH), [], inr))
    assert "times as much" not in facts
    assert "apart per 10 g" in facts


def test_price_move_uses_22k_and_real_dates():
    hist = [(date(2026, 7, 20), 12000.0), (date(2026, 9, 13), 13000.0),
            (date(2026, 10, 13), 14000.0)]
    since = dr.price_move(hist)
    assert since[0] == date(2026, 7, 20)
    assert round(since[1]) == round(12000 * 22 / 24)
    assert round(since[3], 1) == round((14000 / 12000 - 1) * 100, 1)
    month = dr.price_move(hist, 30)
    assert month[0] == date(2026, 9, 13)


def test_page_csv_and_markup():
    t, d, body, ld, csv_text = dr.build(DASH, [], "2026-10-01", "2026-10-13",
                                        "14 October 2026", "https://mygoldrates.com",
                                        inr, today=date(2026, 10, 14))
    assert "Dhanteras" in t and "6 November 2026" in body
    assert "23 days from today" in body
    assert '"@type": "Article"' in ld and '"@type": "Dataset"' in ld
    assert "dhanteras-gold-report-2026.csv" in body
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert {r["category"] for r in rows} == {"Ring", "Bangle"}
    assert all(r["confidence"] in ("high", "medium") for r in rows)
    # the chart marks the cheapest in words, not only in colour
    assert "(lowest)" in body
    # the bar baseline is disclosed, since it is not zero
    assert "not zero" in body


def test_after_dhanteras_the_page_says_so():
    _, _, body, _, _ = dr.build(DASH, [], "2026-10-01", "2026-11-08", "8 November 2026",
                                "https://mygoldrates.com", inr, today=date(2026, 11, 8))
    assert "Dhanteras fell on Friday, 6 November 2026." in body


def test_report_variables_do_not_shadow_the_city_page_builder():
    """The report's structured data was first held in `_ld`, the name the
    city-page builder uses for its own list - the report overwrote it and the
    build crashed writing city pages."""
    src = open("generate_site.py", encoding="utf-8").read()
    i = src.index("# ---- Dhanteras 2026 report")
    block = src[i:src.index('print("dhanteras report: skipped -"', i)]
    assert not __import__("re").search(r"(?<![\w])_ld(?![\w])", block)


def test_amounts_over_a_lakh_use_indian_grouping():
    from jd_pricing import rupees
    _, _, body, _, _ = dr.build(DASH, [], "2026-10-01", "2026-10-13", "14 October 2026",
                                "https://mygoldrates.com", lambda x: "₹" + rupees(round(x)),
                                today=date(2026, 10, 14))
    assert "₹1,6" in body or "₹1,7" in body
    assert not __import__("re").search(r"₹\d{3},\d{3}\b", body)
