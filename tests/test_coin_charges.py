"""24K gold coins in the making-charge collector (owner, 3 Nov 2026)."""
import collect_charges as cc


def test_only_24k_gold_coins_are_coins():
    coin = "https://www.khazanajewellery.com/classic-george-1-gram-24kt-gold-coin-1GCOIN24KTG1.html"
    assert cc.categorize(coin) == "Coin"
    assert cc.categorize("https://www.reliancejewels.com/coins/24-karat-yellow-finish-1-gram-gold-coin-5/") == "Coin"
    assert cc.categorize("https://x.in/gold-coin-999-purity-5-gm") == "Coin"
    assert cc.categorize("https://x.in/22kt-gold-coin-8g") is None              # not 24K
    assert cc.categorize("https://x.in/100-g-(999)-pure-silver-coin") is None   # silver
    assert cc.categorize("https://x.in/rings/the-coin-ring") == "Ring"          # jewellery
    assert cc.categorize("https://x.in/gold-coin-pendant-24kt") is None or \
        cc.categorize("https://x.in/gold-coin-pendant-24kt") != "Coin"


def test_a_coin_reading_far_above_a_few_percent_is_left_out():
    class R:
        ok = True; confidence = 1; strategy = "t"; fields = {}
        def __init__(self, p): self.making_pct = p
    agg, detail = {}, {}
    cc.record_results(agg, detail, "B", [("Coin", "u1", R(2.0), "direct"),
                                          ("Coin", "u2", R(36.0), "direct"),
                                          ("Ring", "u3", R(36.0), "direct")])
    assert agg[("B", "Coin")] == [2.0] and agg[("B", "Ring")] == [36.0]


def test_coin_price_is_own_rate_plus_coin_making_plus_gst():
    import coin_section as cs
    mc = {"brands": [
        {"brand": "A", "categories": [{"category": "Coin", "making_pct_median": 2.0, "items": 12},
                                      {"category": "Ring", "making_pct_median": 20.0}]},
        {"brand": "B", "categories": [{"category": "Coin", "making_pct_median": 5.0, "items": 4}]},
        {"brand": "C", "categories": [{"category": "Ring", "making_pct_median": 12.0}]},   # no coins
        {"brand": "D", "categories": [{"category": "Coin", "making_pct_median": 1.0}]},    # no rate today
    ]}
    rows = cs.coin_rows(mc, {"A": 14000.0, "B": 13900.0, "C": 13800.0})
    assert [r["brand"] for r in rows] == ["A", "B"]          # C has no coins: never priced from rings
    a = rows[0]
    assert a["prices"][10] == round(14000 * 10 * 1.02 * 1.03)
    assert round(a["premium"], 4) == round(1.02 * 1.03 - 1, 4)
    body = cs.coin_html(rows, "2026-11-03T10:00:00+05:30", "https://mygoldrates.com")
    assert "₹1,47,084" in body and "10 g coin" in body and "2026-11-03" in body
    assert cs.coin_html([], "", "") == ""
