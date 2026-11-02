"""Manubhai Jewellers (manubhai.in/gold-rate/) prints a dated rate line.

The page shows "Gold Rate as on DD/MM/YYYY | 22KT - ₹ 12,700 Per Gram" for
22K and 18K. The reading must take both, and the date guard must refuse the
line once it is more than a day old.
"""
from datetime import date

import collect

PAGE = """<html><body><div class="rate-bar">
<span>Gold Rate as on 02/11/2026 | 22KT - &#8377; 12,700 Per Gram</span>
<span>Gold Rate as on 02/11/2026 | 18KT - &#8377; 10,388 Per Gram</span>
</div><p>24K gold (hallmark 999) is 99.9% pure gold.</p></body></html>"""


def test_reads_22k_and_18k():
    rates = collect.extract(PAGE)[0]
    assert round(rates["22K"]) == 12700 and round(rates["18K"]) == 10388


def test_page_is_date_guarded():
    assert "manubhai" in collect.DATED_PAGES
    assert collect.stale_page(PAGE, today=date(2026, 11, 2)) is None
    assert collect.stale_page(PAGE, today=date(2026, 11, 5)).startswith("STALE")
