"""Search additions of 6 Nov 2026 (owner: "go ahead with all of it" after
the goodreturns.in comparison): one H1, today's change, weights and the last
10 days on city pages, the dated jeweller-by-jeweller report, more indexed
cities with local write-ups, links to every city, and six language pages."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lang_pages  # noqa: E402

SRC = open("generate_site.py", encoding="utf-8").read()
APP = open("pulse_app.html", encoding="utf-8").read()


def _inr():
    ns = {}
    exec(SRC[SRC.index("def inr(v, dec=0):"):SRC.index("def _draw_mark")], ns)
    return ns["inr"]


def test_inr_groups_lakhs_the_indian_way():
    inr = _inr()
    assert inr(115112) == "₹1,15,112"          # was "₹115,112"
    assert inr(1438900) == "₹14,38,900"
    assert inr(999) == "₹999" and inr(14389.6) == "₹14,390"
    assert inr(14389.567, 2) == "₹14,389.57"
    assert inr(-63) == "-₹63"


def test_homepage_template_has_one_h1():
    assert len(re.findall(r"<h1\b", APP)) == 1
    assert '<p class="hero-h">Gold Rate Today in India</p>' in APP


def test_city_pages_lead_with_the_rate_panel():
    i = SRC.index("    def rate_panel(nm):")
    body = SRC[i:SRC.index("    def local_intro(", i)]
    for must in ("99.9% pure", "(1 sovereign)", "for the last {n_days} days",
                 "for w in (1, 8, 10, 100)", "nat_trend[-11:]"):
        assert must in body, must
    assert "return rate_panel(nm) + board_html" in SRC


def test_daily_series_is_on_the_headline_basis():
    """National chains only, ending with today's headline median, so the
    change and the tables agree with the rate at the top of the page."""
    i = SRC.index("    _nat_day = {}")
    blk = SRC[i:i + 900]
    assert "not in REGION_MAP" in blk
    assert "+ [(_live_day, median24)]" in blk


def test_daily_report_is_brand_by_brand_and_kept_30_days():
    i = SRC.index("    def gen_daily(place, place_slug):")
    body = SRC[i:i + 9000]
    assert "load_rates(_prev_d)" in body           # yesterday, per jeweller
    assert '"@type": "NewsArticle"' in body
    assert "DAILY_INDEX_DAYS = 30" in SRC
    assert "Earlier daily reports" in SRC


def test_new_cities_have_local_write_ups():
    import ast
    i = SRC.index("CITY_ENRICHMENT_DATA = {")
    j = SRC.index("\n}\n", i)
    data = ast.literal_eval(SRC[i + len("CITY_ENRICHMENT_DATA = "):j + 2])
    i = SRC.index("INDEXED_PLACES = {")
    places = ast.literal_eval(SRC[i + len("INDEXED_PLACES = "):SRC.index("}", i) + 1])
    for c in ("Thrissur", "Kozhikode", "Madurai", "Salem", "Tiruchirappalli",
              "Mysuru", "Vijayawada", "Amritsar", "Guwahati", "Kolhapur"):
        assert c in places and data[c].get("intro"), c


def test_every_page_links_every_indexed_city_and_language():
    i = SRC.index("def site_links_html():")
    body = SRC[i:SRC.index("def nd_header_html", i)]
    assert "<h3>Gold rate by city</h3>" in body and "INDEXED_PLACES" in body
    assert "<h3>Gold rate in your language</h3>" in body


SERIES = [("2026-11-0%d" % d, 14000 + 50 * d) for d in range(1, 7)]
ROWS = [("Kalyan Jewellers", 14100.0), ("Tanishq", 14300.0), ("GRT Jewellers", 14350.0)]


def test_language_pages_build_in_every_language():
    inr = _inr()
    for code, hl, name, w in lang_pages.LANGS:
        t, desc, body, faq = lang_pages.build(code, inr=inr, d="06/11/2026", series=SERIES,
                                              rows=ROWS, national=ROWS[:2], site="https://x")
        assert "06/11/2026" in t and "MyGoldRates" in t
        assert "₹14,300" in body                        # today's 24K median
        assert "Kalyan Jewellers" in faq[1][1]          # cheapest national chain
        assert body.count("<h1>") == 1
        assert f'aria-current="page">{name}' in body
        assert "{" not in body and "{" not in desc     # every placeholder filled


def test_alternates_are_reciprocal():
    alt = lang_pages.alternates("https://x")
    assert 'hreflang="x-default" href="https://x/"' in alt
    for code, hl, _n, _w in lang_pages.LANGS:
        assert f'hreflang="{hl}" href="https://x/{code}/gold-rate-today"' in alt
    # the homepage gets them, city pages (built from the same HTML) do not
    assert 'lang_pages.alternates(SITE_URL) + "\\n</head>"' in SRC
