import json

import social_post as sp


def _kb():
    return json.load(open("docs/assistant.json", encoding="utf-8"))


def test_the_post_quotes_only_the_sites_own_figures():
    d = sp.today(_kb())
    cap = sp.caption(d)
    assert d["date"] in cap and "before GST" in cap and "mygoldrates.com" in cap
    assert d["top"][0][0] in cap and sp.inr(d["gap"]) in cap
    assert [p for _, p in d["top"]] == sorted(p for _, p in d["top"])     # cheapest first
    assert "scrap" not in cap.lower() and "guarantee" not in cap.lower()
    assert len(cap) < 2200                                                 # Instagram's caption limit


def test_the_card_is_a_portrait_instagram_jpeg(tmp_path):
    from PIL import Image
    p = tmp_path / "card.jpg"
    sp.card(sp.today(_kb()), str(p))
    im = Image.open(p)
    assert im.format == "JPEG" and im.size == (1080, 1350)


def test_rupees_use_indian_grouping():
    assert sp.inr(155356.4) == "₹1,55,356" and sp.inr(12958) == "₹12,958"


def test_ai_artwork_only_paints_the_background_the_numbers_stay_ours(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert sp.ai_art() is None                                             # no key: the drawn card is used
    p = tmp_path / "card.jpg"
    sp.card(sp.today(_kb()), str(p), Image.new("RGB", (896, 1120), (240, 220, 180)))
    assert Image.open(p).size == (1080, 1350)
    assert "No text, no letters, no numbers" in sp.ART_PROMPT
