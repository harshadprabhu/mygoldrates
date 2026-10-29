import deals_post as dp

KB = {"brands": [
    {"n": "A", "r24": 14400.0, "mk": {"Ring": 20.0}, "mo": {"f": 25.0, "u": 25.0}},
    {"n": "B", "r24": 14400.0, "mk": {"Ring": 16.0}, "mo": {"f": 0.0, "u": 30.0}},
    {"n": "C", "r24": 14300.0, "mk": {"Bangle": 12.0}},
]}


def test_ranking_is_sonas_best_offer_sum():
    rows = dp.deals(KB, "Ring")
    gold = 14400 * 22 / 24 * 10
    assert [r["n"] for r in rows] == ["A", "B"]                       # 20% less a flat 25% = 15% beats 16%
    a = next(r for r in rows if r["n"] == "A")
    assert round(a["after"], 2) == 15.0 and round(a["tot"]) == round(gold * 1.15 * 1.03)
    b = next(r for r in rows if r["n"] == "B")
    assert b["best"] is not None and b["best"] < b["tot"]              # "up to" shown as a best case only
    assert dp.deals(KB, "Mangalsutra") == []


def test_caption_names_each_jewels_cheapest():
    kb = dict(KB, date="29 October 2026", med={"22K": 13200.0})
    d = {c: dp.deals(kb, c) for c, _ in dp.CATS}
    cap = dp.caption(kb, d)
    assert "Ring:" in cap and "Bangle: C" in cap and "#makingcharges" in cap and "no affiliation" in cap
