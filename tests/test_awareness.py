import json

import awareness as aw
import social_post as sp


def test_every_carousel_renders_six_slides_that_fit(tmp_path):
    from PIL import Image
    for t in aw.TOPICS:
        slides = aw.CONTENT[t]["slides"]
        assert len(slides) == 6
        for i, s in enumerate(slides, 1):
            p = tmp_path / f"{t}-{i}.jpg"
            aw.render(s, i, len(slides), str(p))               # raises if the text does not fit
            im = Image.open(p)
            assert im.size == (1080, 1350)
            assert sum(im.getpixel((570, 81))) < 120           # the dark logo pill on every slide


def test_awareness_cards_state_no_rates_and_no_banned_words():
    text = json.dumps([aw.CONTENT[t] for t in aw.TOPICS], ensure_ascii=False) + " ".join(aw.caption(t) for t in aw.TOPICS)
    assert "₹" not in text                                  # rates change daily: none on these cards
    for w in ("scrap", "guarantee"):
        assert w not in text.lower()
    for t in aw.TOPICS:
        assert "not investment advice" in aw.caption(t) and len(aw.caption(t)) < 2200


def test_topics_rotate_by_how_many_have_been_posted():
    assert aw.next_topic({}) == "purity"
    assert aw.next_topic({"awareness-2026-10-29": "1"}) == "hallmark"
    assert aw.next_topic({"awareness-a": "1", "awareness-b": "2", "2026-10-27": "x", "news-2026-10-28": "y"}) == "huid"
    assert aw.next_topic({"awareness-a": "1", "awareness-b": "2", "awareness-c": "3"}) == "purity"


def test_a_carousel_is_posted_as_children_then_parent_then_publish(monkeypatch):
    calls = []

    class R:
        ok = True
        def __init__(self, j): self._j = j
        def json(self): return self._j

    def post(url, data=None, timeout=0):
        calls.append(("POST", url.rsplit("/", 1)[-1], dict(data)))
        return R({"id": f"id{len(calls)}"})

    def get(url, params=None, timeout=0):
        return R({"status_code": "FINISHED"})

    import requests
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(sp, "_token", lambda: "tok")
    assert sp.publish_carousel(["u1", "u2", "u3"], "cap") == "id5"
    assert [c[2].get("is_carousel_item") for c in calls[:3]] == ["true"] * 3
    assert calls[3][2]["media_type"] == "CAROUSEL" and calls[3][2]["children"] == "id1,id2,id3"
    assert calls[4][1] == "media_publish" and calls[4][2]["creation_id"] == "id4"


def test_the_one_job_also_posts_the_awareness_carousel():
    wf = open(".github/workflows/social.yml", encoding="utf-8").read()
    assert '"47 13 * * 2,4,6") k=awareness' in wf and "awareness.py publish" in wf
