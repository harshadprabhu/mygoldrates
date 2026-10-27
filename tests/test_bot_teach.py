import json

import bot_teach as bt


def test_learned_answers_never_quote_a_figure_that_goes_stale():
    pages = bt.site_pages()
    ok = bt.check({"i": 0, "q": "Is 22K gold good for daily wear?",
                   "a": "Yes - 22K (916) is strong enough for daily wear.", "u": "/learn/22k-vs-24k-gold"}, pages, 1)
    assert ok and ok["u"] == "/learn/22k-vs-24k-gold"
    assert bt.check({"i": 0, "q": "What is the price today?",
                     "a": "Gold is about 13,092 a gram in Mumbai today.", "u": ""}, pages, 1) is None
    assert bt.check({"i": 0, "q": "Can I sell old gold here?",
                     "a": "We do not scrap or buy gold, we only compare rates.", "u": ""}, pages, 1) is None


def test_links_must_be_real_pages_and_numbers_must_match_a_question():
    pages = bt.site_pages()
    c = bt.check({"i": 0, "q": "Where are today's offers?",
                  "a": "See the offers page for every jeweller's current offers.", "u": "/no-such-page"}, pages, 1)
    assert c and c["u"] == ""                                              # a made-up link is dropped
    assert bt.check({"i": 5, "q": "Where are today's offers?", "a": "See the offers page, updated daily.", "u": ""},
                    pages, 1) is None


def test_only_questions_sona_still_fails_are_taught():
    rows = [
        {"q": "a", "q_norm": "a", "answered": False, "helpful": None, "page": "/", "created_at": "1"},
        {"q": "a", "q_norm": "a", "answered": True, "helpful": None, "page": "/", "created_at": "2"},   # since learned
        {"q": "b", "q_norm": "b", "answered": True, "helpful": False, "page": "/", "created_at": "1"},  # thumbs-down
        {"q": "c", "q_norm": "c", "answered": False, "helpful": None, "page": "/__test", "created_at": "1"},
    ]
    assert bt.pending(rows) == ["b"]


def test_the_prompt_carries_the_sites_facts():
    kb = json.load(open(bt.KB, encoding="utf-8"))
    f = bt.facts(kb)
    assert kb["faq"][0]["q"] in f and "jewellers" in f
