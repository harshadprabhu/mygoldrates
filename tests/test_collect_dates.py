from datetime import date

import collect

CARDS = ("24K Pure Gold 99.9% Fine ₹ 1,42,621 / 10g ₹ 971 ( 0.69 %) vs yesterday Per 1g ₹ 14,262 Per 100g ₹ 14,26,200 "
         "22K Hallmark Gold 91.6% Fine ₹ 1,31,211 / 10g Per 1g ₹ 13,121 18K Classic Gold 75.0% Fine ₹ 1,08,392 / 10g "
         "Per 1g ₹ 10,839 Last synced: 28 Oct 2026")


def test_per_gram_cards_are_read_by_their_own_karat():
    assert collect.extract_per_1g_card(CARDS) == {"24K": [14262.0], "22K": [13121.0], "18K": [10839.0]}
    assert collect.extract_per_1g_card("22K gold rate 13,121 per gram") == {}


def test_a_rate_dated_more_than_a_day_back_is_refused():
    today = date(2026, 10, 28)
    assert collect.stale_page("<p>Wednesday, 28th October, 2026 : Gold 22K: ₹1,34,900/10gms</p>", today) is None
    assert collect.stale_page("<p>Last synced: 27 Oct 2026</p>", today) is None
    assert collect.stale_page("<p>Rates updated on 11 October 2026</p>", today) == "STALE: rate dated 2026-10-11"
    assert collect.stale_page("<p>22K: 13,880/g</p>", today) == "STALE: no date on the page"
    assert {"swarn-jewellers", "rushabh"} <= collect.DATED_PAGES


def test_the_rate_is_taken_from_the_22k_a_jeweller_publishes():
    png = {"24K": 14276.0, "22K": 13213.0, "18K": 10900.0}
    assert collect.basis_purity(png) == "22K"
    assert collect.basis_purity({"24K": 14400.0, "18K": 10800.0}) == "24K"
    assert collect.basis_purity(png, "24K") == "24K"
    assert collect.basis_purity({"14K": 8431.0}) == "14K"


def test_caratlane_rate_cards_and_not_its_coin_prices():
    page = ("Select City ₹ 14,545 /Gram · 24KT 22KT ₹ 13,333 18KT ₹ 10,909 14KT ₹ 8,509 9KT ₹ 5,454 "
            "*Price may vary by city ₹15,881 1g, 24Kt Lakshmi Gold Coin ₹14,557 1g, 22Kt Lakshmi Gold Coin "
            "22KT Plain Gold Coin ₹1,25,843 8g")
    assert collect.extract_rate_cards(page) == {"24K": [14545.0], "22K": [13333.0], "18K": [10909.0], "14K": [8509.0]}
    assert collect.extract_rate_cards("22KT ₹ 13,333 only one karat") == {}
