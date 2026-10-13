"""The analytics dashboard must say what a click was, not what the HTML calls it.

The click tracker stores a stable key: the element id, or its visible text.
Stable keys are right - if the key changed with the copy, one button would
split into two rows - but they read like "mcBrandTrigger", "m-close" or a
bare glyph like the candlestick button. CLICK_LABELS in generate_site.py
translates them. These tests stop a new button from reaching the dashboard
untranslated.
"""
import glob
import json
import re

import generate_site as gs

PAGES = ["pulse_app.html"] + [
    f for f in ("docs/index.html", "docs/compare.html",
                "docs/gold-rate-today-in-pune.html", "docs/calculators.html")
    if glob.glob(f)]


def _button_ids():
    ids = set()
    for f in PAGES:
        ids |= set(re.findall(r'<button\b[^>]*\bid="([^"]+)"',
                              open(f, encoding="utf-8").read()))
    return ids


def test_every_button_with_an_id_has_a_readable_label():
    missing = sorted(i for i in _button_ids() if i not in gs.CLICK_LABELS)
    assert not missing, (
        "these buttons would appear on the analytics dashboard under their "
        "HTML id - add them to CLICK_LABELS: " + ", ".join(missing))


def test_the_chart_glyph_buttons_have_names():
    """Area, line, candlestick and OHLC are bare symbols on the page, so
    their tracked key is the symbol itself."""
    for glyph, word in (("▲", "area"), ("∼", "line"),
                        ("▣", "candlestick"), ("⋮", "OHLC")):
        assert word in gs.CLICK_LABELS[glyph]


def test_mobile_twins_share_a_label():
    """gstBtn / gstBtnS and friends are the same control at two widths and
    must fold into one dashboard row."""
    L = gs.CLICK_LABELS
    for a, b in (("gstBtn", "gstBtnS"), ("nearBtn", "nearBtnS"),
                 ("mcBrandTrigger", "mcBrandTriggerS"), ("alBtn", "alBtnS")):
        assert L[a] == L[b], (a, b)


def test_the_dashboard_is_built_with_the_map_and_merges_rows():
    page = (gs.ANALYTICS_HTML
            .replace("__CLICK_LABELS__", json.dumps(gs.CLICK_LABELS))
            .replace("__CITIES__", json.dumps(gs.LOCATIONS)))
    assert "__CLICK_LABELS__" not in page and "__CITIES__" not in page
    assert "mergeByLabel(d.top_clicks" in page
    assert "isSynthetic" in page
