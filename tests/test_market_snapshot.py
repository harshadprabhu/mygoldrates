"""market_snapshot.py reads the worker's current payloads.

It wrote nothing to vendor_rates and ohlc_history for weeks because it only
understood the worker's original shapes. These fixtures are the shapes the
worker serves now (October 2026)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import market_snapshot as ms  # noqa: E402


def test_vendor_rows_from_current_worker_shape():
    v = {"vendors": [{"dealer_id": "arihant", "dealer": "Arihant Spot",
                      "gold_995": {"commodity": "GOLD 995", "price": 143840},
                      "all_rows": [
                          {"code": "2580", "name": "GOLD SPOT", "buy": 4116.55,
                           "sell": 4116.55, "high": 4142.95, "low": 4105.25},
                          {"code": "2710", "name": "GOLD 995 (1kg) IND-BIS T+0",
                           "buy": 143640, "sell": 143840, "high": 143840, "low": 143839}]}],
         "count": 1}
    rows = ms.vendor_rows(v)
    assert len(rows) == 2
    assert rows[1] == {"dealer": "arihant", "metal": "GOLD 995 (1kg) IND-BIS T+0",
                       "buy": 143640, "sell": 143840, "high": 143840, "low": 143839}


def test_vendor_rows_still_read_the_original_shape():
    v = {"dealers": [{"dealer": "safari", "rates": {"GOLD_995": {"buy": 1, "sell": 2}}}]}
    assert ms.vendor_rows(v)[0]["metal"] == "GOLD_995"


def test_ohlc_rows_from_epoch_candles():
    o = {"symbol": "XAU", "ticker": "GC=F", "candles": [
        {"t": 1784865600, "o": 4053.4, "h": 4085.2, "l": 4024, "c": 4070.8}]}
    rows = ms.ohlc_rows("GC=F", o)
    assert rows == [{"symbol": "GC=F", "d": "2026-07-24", "open": 4053.4,
                     "high": 4085.2, "low": 4024, "close": 4070.8}]


def test_ohlc_rows_original_shape():
    o = {"candles": [{"date": "2026-09-01", "open": 1, "high": 2, "low": 0.5, "close": 1.5}]}
    assert ms.ohlc_rows("SI=F", o)[0]["d"] == "2026-09-01"


def test_ohlc_asks_the_worker_for_each_metal_by_its_own_name():
    # ?symbol=SI=F was ignored by the worker, which returned gold for both.
    src = open("market_snapshot.py", encoding="utf-8").read()
    assert '("SI=F", "XAG")' in src and "/ohlc?sym={wsym}" in src


def test_calendar_rows_keep_us_events_with_their_timestamps():
    ev = [{"title": "CPI m/m", "country": "USD", "date": "2026-10-23T08:30:00-04:00",
           "impact": "High", "forecast": "0.3%", "previous": "0.4%"},
          {"title": "Trade Balance", "country": "NZD", "date": "2026-10-18T17:45:00-04:00",
           "impact": "Low", "forecast": "-775M", "previous": "-1349M"}]
    rows = ms.calendar_rows(ev)
    assert rows == [{"event_at": "2026-10-23T08:30:00-04:00", "title": "CPI m/m",
                     "country": "USD", "impact": "High", "actual": None,
                     "forecast": "0.3%", "previous": "0.4%"}]


def test_news_rows_from_google_news_rss():
    xml = ("<rss><channel><item><title>Gold hits record - Reuters</title>"
           "<link>https://news.google.com/rss/articles/abc</link>"
           "<pubDate>Wed, 22 Oct 2026 07:00:00 GMT</pubDate>"
           "<source url='https://reuters.com'>Reuters</source></item></channel></rss>")
    assert ms.news_rows_from_rss(xml) == [{
        "title": "Gold hits record", "url": "https://news.google.com/rss/articles/abc",
        "published_at": "2026-10-22T07:00:00+00:00", "source": "Reuters"}]
