import news_post as n

ITEMS = [("Economic Times", "Gold prices dip Rs 500/10 grams; silver falls Rs 2,400/kg as traders eye US Fed meet"),
         ("Moneycontrol", "Gold may remain choppy, but buying may emerge at lower levels: Kotak Securities"),
         ("Mint", "Chinese households are buying gold's dip as prices test $4,000")]
GOOD = {"headline": "Gold eases before the US Fed meeting",
        "points": ["Gold dips Rs 500/10 grams as traders wait for the Fed.", "Silver falls Rs 2,400/kg.",
                   "Buyers in China pick up gold as it tests $4,000."],
        "view": "Kotak Securities expects choppy trade with buying at lower levels.",
        "sources": ["Economic Times", "Moneycontrol"]}


def test_a_summary_quotes_only_numbers_from_the_news_or_our_data_and_attributes_the_view():
    ok, why = n.check(GOOD, ITEMS)
    assert ok and not why
    assert n.check(dict(GOOD, points=GOOD["points"][:2] + ["Gold will hit 99,999 next week."]), ITEMS)[1].startswith("numbers")
    our = dict(GOOD, points=GOOD["points"][:2] + ["22K is 13,135 a gram today."])
    assert n.check(our, ITEMS)[1].startswith("numbers")
    assert n.check(our, ITEMS, ["22K market middle today: ₹13,135/g"])[0]   # our own figure is allowed
    assert n.check(dict(GOOD, view="Gold will rise tomorrow."), ITEMS)[1] == "view not attributed"
    assert n.check(dict(GOOD, headline="Guaranteed gains in gold"), ITEMS)[1] == "banned word"
    assert n.check(dict(GOOD, points=GOOD["points"][:2]), ITEMS)[1] == "bad shape"


def test_both_story_cards_carry_the_logo_header_and_say_not_advice(tmp_path):
    from PIL import Image
    for kind, figs in (("news", None), ("pulse", [("22K today", "₹13,135/g"), ("7-day move", "▼ ₹243/g"), ("Gap on 10 g", "₹2,365")])):
        p = tmp_path / f"{kind}.jpg"
        n.card(kind, GOOD, "27 October 2026", str(p), figs)
        im = Image.open(p)
        assert im.size == (1080, 1350)
        assert sum(im.getpixel((570, 81))) < 120                           # the dark logo pill at the top
        cap = n.caption(kind, GOOD, "27 October 2026", figs)
        assert "not investment advice" in cap and "Economic Times" in cap and "mygoldrates.com" in cap


def test_one_job_posts_all_three_at_their_times():
    wf = open(".github/workflows/social.yml", encoding="utf-8").read()
    for cron, kind in (("17 3 * * *", "news"), ("47 5 * * *", "rates"), ("17 9 * * *", "pulse")):
        assert f'"{cron}") k={kind}' in wf
    import os
    assert not os.path.exists(".github/workflows/news.yml")
