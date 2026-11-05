"""The widget, the jeweller badge and the gold price gap report (owner,
6 Nov 2026: pages other sites can link to)."""
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import outreach_pages as op  # noqa: E402

SITE = "https://mygoldrates.com"
SRC = open("generate_site.py", encoding="utf-8").read()


def _inr():
    ns = {}
    exec(SRC[SRC.index("def inr(v, dec=0):"):SRC.index("def _draw_mark")], ns)
    return ns["inr"]


def test_widget_script_is_ascii_so_any_host_page_shows_the_rupee_sign():
    """A host page with no charset read the literal symbol as "â‚¹"."""
    assert all(ord(c) < 128 for c in op.WIDGET_JS)
    assert "\\u20b9" in op.WIDGET_JS


def test_embed_code_carries_a_plain_visible_credit_link():
    code = op.embed_code(SITE)
    assert '<a href="https://mygoldrates.com/">Gold rates by MyGoldRates</a>' in code
    city = op.embed_code(SITE, "chennai", "Chennai", "dark")
    assert 'href="https://mygoldrates.com/gold-rate-today-in-chennai"' in city
    assert 'data-city="chennai"' in city and 'data-theme="dark"' in city
    # the script keeps the host's link instead of replacing it
    assert "box.appendChild(credit)" in op.WIDGET_JS
    assert "nofollow" not in code


def test_widget_data_rounds_and_ranks():
    d = op.widget_data(display_date="6 Nov", r24=14389.4, r22=13190.2, chg22=-57.6,
                       national_rows=[("A", 14000.0), ("B", 14100.0)], places={})
    assert d["india"]["r24"] == 14389 and d["india"]["chg22"] == -58
    assert d["india"]["top"][0] == {"name": "A", "r22": round(14000 * 22 / 24)}


def test_widget_data_is_served_cross_origin():
    i = SRC.index('"/widget-data.json\\n"')
    assert "Access-Control-Allow-Origin: *" in SRC[i:i + 200]


def test_badge_links_to_the_jewellers_own_page():
    code = op.badge_code(SITE, "tanishq-gold-rate-today", "Tanishq")
    assert code.startswith('<a href="https://mygoldrates.com/tanishq-gold-rate-today"')
    assert 'src="https://mygoldrates.com/badge.svg"' in code and "alt=" in code


def _hist(days=20):
    rows, t = [], date(2026, 11, 6)
    for k in range(days):
        d = (t - timedelta(days=k)).isoformat()
        for i, sl in enumerate(("a", "b", "c", "d", "e", "reg")):
            rows.append({"rate_date": d, "canonical_24k_pre_gst": 14000 + 100 * i + k,
                         "brands": {"slug": sl, "name": sl.upper()}})
    return rows, t


def test_gap_report_figures():
    rows, t = _hist()
    title, desc, body, ld = op.gap_report(rows, {"reg"}, _inr(), t)
    assert "November 2026" in title
    # national spread: e - a = 400 on 24K -> 366.67 on 22K
    assert "₹367 per gram" in body
    assert "REG" not in body                       # regional chains left out
    assert "<strong>A</strong>" in body            # cheapest on average
    assert "100%" in body                          # A cheapest every day
    assert '"@type": "Dataset"' in ld


def test_gap_report_waits_for_a_week_of_readings():
    rows, t = _hist(days=5)
    assert op.gap_report(rows, {"reg"}, _inr(), t) is None


def test_pages_are_built_and_linked():
    for slug in ("gold-price-gap-report", "gold-rate-widget", "jeweller-badge"):
        assert f'"{slug}"' in SRC, slug
    i = SRC.index("def site_links_html():")
    assert "/gold-rate-widget" in SRC[i:i + 4000] and "/gold-price-gap-report" in SRC[i:i + 4000]
