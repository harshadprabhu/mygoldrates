import news_post as n

ITEMS = [("Economic Times", "Gold prices dip Rs 500/10 grams; silver falls Rs 2,400/kg as traders eye US Fed meet", ""),
         ("Moneycontrol", "Gold may remain choppy, but buying may emerge at lower levels: Kotak Securities", ""),
         ("Mint", "Chinese households are buying gold's dip as prices test $4,000", "")]
GOOD = {"headline": "Gold eases before the US Fed meeting",
        "points": ["Gold dips Rs 500/10 grams as traders wait for the Fed.", "Silver falls Rs 2,400/kg.",
                   "Buyers in China pick up gold as it tests $4,000."],
        "outlook": "Kotak Securities expects choppy trade with buying at lower levels.",
        "sources": ["Economic Times", "Moneycontrol"]}


def test_a_summary_quotes_only_numbers_from_the_news_and_attributes_the_view():
    ok, why = n.check(GOOD, ITEMS)
    assert ok and not why
    assert n.check(dict(GOOD, points=GOOD["points"][:2] + ["Gold will hit 99,999 next week."]), ITEMS)[1].startswith("numbers")
    assert n.check(dict(GOOD, outlook="Gold will rise tomorrow."), ITEMS)[1] == "outlook not attributed"
    assert n.check(dict(GOOD, headline="Guaranteed gains in gold"), ITEMS)[1] == "banned word"
    assert n.check(dict(GOOD, points=GOOD["points"][:2]), ITEMS)[1] == "bad shape"


def test_the_news_card_carries_the_logo_header_and_the_caption_says_not_advice(tmp_path):
    from PIL import Image
    p = tmp_path / "news.jpg"
    n.card(GOOD, "27 October 2026", str(p))
    im = Image.open(p)
    assert im.size == (1080, 1350)
    assert sum(im.getpixel((570, 81))) < 120                               # the dark logo pill at the top
    cap = n.caption(GOOD, "27 October 2026")
    assert "not investment advice" in cap and "Economic Times" in cap and "mygoldrates.com" in cap
