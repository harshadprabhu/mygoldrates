"""IBJA reference-rate parsing.

Regression cover for the Sep-2026 break: IBJA switched from publishing per
10 grams to per gram, the parser's hard-coded 6-7 digit / divide-by-10
assumption stopped matching, fetch_ibja() returned None, and every caller
treated that as "IBJA unavailable" and fell back silently - the homepage
anchor went to 0 and the IBJA tile reverted to a spot estimate with nothing
reporting it.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate_site as G


class _Resp:
    def __init__(self, text):
        self.text = text


def _run(monkeypatch, html):
    monkeypatch.setattr(G.requests, "get", lambda *a, **k: _Resp(html))
    return G.fetch_ibja()


PER_GRAM = """
<table><tr><td>999 Purity</td><td>15090</td><td>(1 Gram)</td></tr>
<tr><td>995 Purity</td><td>15030</td><td>(1 Gram)</td></tr>
<tr><td>916 Purity</td><td>13823</td><td>(1 Gram)</td></tr>
<tr><td>750 Purity</td><td>11318</td><td>(1 Gram)</td></tr></table>
"""

PER_10G = """
<table><tr><td>999 Purity</td><td>150900</td><td>(10 Gram)</td></tr>
<tr><td>916 Purity</td><td>138230</td><td>(10 Gram)</td></tr></table>
"""

# The Chart.js block IBJA ships above the rate table. Bare-"999" matching
# would bind here instead of the real rates.
CHART_NOISE = """
<script>datasets: [ { label: "999 Purity Gold Rates (PM)",
data: chartData.purity999, borderWidth: 2 },
{ label: "916 Purity Gold Rates (PM)", data: chartData.purity916 } ]</script>
"""


def test_per_gram_publishing(monkeypatch):
    assert _run(monkeypatch, PER_GRAM) == (15090.0, 13823.0)


def test_per_10g_publishing_still_parses(monkeypatch):
    """The old convention must keep working if IBJA ever reverts."""
    assert _run(monkeypatch, PER_10G) == (15090.0, 13823.0)


def test_chart_script_is_not_mistaken_for_rates(monkeypatch):
    """Chart labels carry the purity words but no rate - must not bind."""
    assert _run(monkeypatch, CHART_NOISE) is None


def test_chart_noise_before_real_table(monkeypatch):
    """Real page shape: chart script first, rate table after."""
    assert _run(monkeypatch, CHART_NOISE + PER_GRAM) == (15090.0, 13823.0)


def test_out_of_band_values_rejected(monkeypatch):
    """A figure in neither the per-gram nor the per-10g band is not a rate."""
    bad = "<td>999 Purity</td><td>42</td><td>916 Purity</td><td>37</td>"
    assert _run(monkeypatch, bad) is None


def test_returns_none_when_only_one_purity_present(monkeypatch):
    """Both anchors are required - a half-read table is not usable."""
    half = "<td>999 Purity</td><td>15090</td><td>(1 Gram)</td>"
    assert _run(monkeypatch, half) is None
