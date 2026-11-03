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


def test_coin_making_back_calculated_from_price():
    import coin_price_making as cp
    # 5 g at 14,000 = 70,000 gold; price 75,705 incl. GST -> 73,500 before -> 5%
    assert cp.making_pct(75705, 5, 14000) == 5.0
    assert cp.making_pct(73500, 5, 14000, incl_gst=False) == 5.0
    assert cp.making_pct(26895, 2, 13963.64) is None        # below gold value at 24K: a 22K coin
    assert cp.making_pct(7000, 0.5, 14000) is None          # under 1 g
    assert cp.making_pct(99000, 5, 14000) is None           # 37%: not a plain coin
    assert cp.weight_g("2 Gram  St.Mary Gold Coin") == 2 and cp.weight_g("gold-coin-5-gm-24kt") == 5


def test_worked_out_coin_rows_never_replace_a_measured_one():
    import coin_price_making as cp
    hist = cp.update_history({}, "2026-11-03", {
        "CKC": [{"url": "https://ckc/a", "g": 5, "price": 1, "pct": 5.5}, {"url": "https://ckc/b", "g": 5, "price": 1, "pct": 8.9}],
        "Tanishq": [{"url": "https://t/a", "g": 1, "price": 1, "pct": 9.0}]})
    rows = cp.coin_rows_from_history(hist, "2026-11-03")
    assert rows["CKC"]["making_pct_median"] == 7.2 and rows["CKC"]["source"] == "price"
    mc = {"brands": [{"brand": "Tanishq", "categories": [{"category": "Coin", "making_pct_median": 6.0}]},
                     {"brand": "CKC", "categories": [{"category": "Ring", "making_pct_median": 19.5}]}]}
    out = {b["brand"]: {c["category"]: c for c in b["categories"]} for b in cp.merge_into_making(mc, rows)["brands"]}
    assert out["Tanishq"]["Coin"]["making_pct_median"] == 6.0          # measured: kept
    assert out["CKC"]["Coin"]["making_pct_median"] == 7.2 and out["CKC"]["Ring"]["making_pct_median"] == 19.5
    old = cp.update_history(hist, "2027-02-01", {})
    assert "2026-11-03" not in old                                    # 60 days kept


def test_coin_gold_factor_from_breakups():
    # PN Gadgil: 995 coin billed at its 24K rate -> 1.0; Khazana: '1 gram' billed 1.028 g
    png = [{"url": "https://www.pngjewellers.com/products/1-gram-24-kt-995-png-gold-coin", "fields": {"gold_value": 13846.0}}]
    assert cc.coin_gold_factor(png, 13846.0) == 1.0
    kz = [{"url": "https://www.khazanajewellery.com/classic-george-1-gram-24kt-gold-coin-1GCOIN24KTG1.html",
           "fields": {"gold_value": 14356.02}},
          {"url": "https://x/5-gram-24kt-gold-coin", "fields": {"gold_value": 71780.0}},
          {"url": "https://x/2-gram-24kt-gold-coin", "fields": {"gold_value": 9000.0}}]     # misread: dropped
    assert cc.coin_gold_factor(kz, 13964.0) == 1.0281
    assert cc.coin_gold_factor(kz, None) is None


def test_coin_page_prices_include_the_gold_factor():
    import coin_section as cs
    mc = {"brands": [{"brand": "K", "categories": [{"category": "Coin", "making_pct_median": 2.0, "gold_factor": 1.028}]}]}
    r = cs.coin_rows(mc, {"K": 13964.0})[0]
    assert r["prices"][1] == round(13964 * 1.028 * 1.02 * 1.03)
    assert "1.028 g of gold" in cs.coin_html([r], "2026-11-03", "https://mygoldrates.com")


def test_coin_purity_is_read_from_the_page():
    # CaratLane's breakup data names it; PN Gadgil's title; WHP's spec
    assert cc.page_purity('{"price_breakup":{"gold":[{"title":"995 Kt Yellow Gold"}]}}') == "995"
    assert cc.page_purity("<h1>1 Gram 24 KT (995) PNG Gold Coin</h1>") == "995"
    assert cc.page_purity("<li>Purity: 24KT 999</li>") == "999"
    assert cc.page_purity("<p>99.99% pure 24K gold</p>") == "999.9"
    assert cc.page_purity("<p>Pay 999 easy EMIs</p>", "https://x/coin") is None   # a bare number
    mixed = [{"fields": {"purity": "995"}}] * 6 + [{"fields": {"purity": "999.9"}}] * 2
    assert cc.coin_purity(mixed) == "995/999.9"                                     # Senco
