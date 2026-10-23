"""Sona, the site assistant: its knowledge file, learning export, referrals."""
import json

import assistant_kb as KB
import bot_learn
import generate_site as gs
import send_alerts as sa

JS = open("assistant.js", encoding="utf-8").read()


def _kb(**over):
    args = dict(
        live=[{"canonical_24k_pre_gst": 14000.0, "brands": {"slug": "png", "name": "PN Gadgil"}},
              {"canonical_24k_pre_gst": 14100.0, "brands": {"slug": "ranka", "name": "Ranka Jewellers"}}],
        med={"24K": 14050.0, "22K": 12879.0, "18K": 10537.0},
        trend=[("2026-10-23", 14200.0), ("2026-10-24", 14050.0)],
        locations=["Pune", "Delhi"], place_state={"Pune": "Maharashtra", "Delhi": "Delhi"},
        region_map={"ranka": ["Maharashtra"]}, brand_home={"ranka": ["Pune"]},
        loc_slug=lambda p: p.lower(), jeweller_pages={"png": "pn-gadgil-gold-rate-today"},
        making={}, offers={}, ring_rows=[], offer_meaning=lambda *a: "", offer_headline=lambda o: "",
        guides=[("22K vs 24K", "/learn/22k-vs-24k-gold", "d")], display_date="24 October 2026",
        updated_iso="2026-10-24T09:00+05:30", site_url="https://mygoldrates.com")
    args.update(over)
    return KB.build(**args)


def test_knowledge_file_has_every_jeweller_and_the_city_jewellers():
    kb = _kb()
    assert [b["s"] for b in kb["brands"]] == ["png", "ranka"]          # cheapest first
    assert kb["brands"][0]["nat"] and not kb["brands"][1]["nat"]
    pune = [c for c in kb["cities"] if c["n"] == "Pune"][0]
    assert pune["loc"] == ["ranka"] and pune["u"] == "/gold-rate-today-in-pune"
    assert kb["brands"][0]["u"] == "/pn-gadgil-gold-rate-today"
    json.dumps(kb)                                                     # serialisable


def test_only_approved_answers_are_exported_to_git():
    out = bot_learn.export([
        {"id": 2, "q": "EMI on gold?", "a": "Ask the jeweller.", "u": "", "active": True,
         "created_at": "2026-10-24T10:00:00"},
        {"id": 1, "q": "old", "a": "x", "active": False}])
    assert [a["q"] for a in out["answers"]] == ["EMI on gold?"]
    assert "never the raw questions" in out["note"]


def test_referrer_learns_the_friends_first_name_or_a_masked_email_only():
    assert sa.friend_label("Asha Rao", "asha@x.in") == "Asha"
    assert sa.friend_label("", "ravi@gmail.com") == "r•••@gmail.com"
    assert "?ref=ABC" in sa.ref_link("ABC")


def test_invite_links_are_captured_on_every_page():
    s = gs.analytics_snippet("https://x", "k")
    assert "gr_ref" in s and "record_referral" in s and "window.GR_REF_DONE" in s


def test_assistant_never_claims_what_we_cannot_prove_and_loads_everywhere():
    assert "India’s first" not in JS and "India's first" not in JS
    assert "log_bot_question" in JS and "[number]" in JS          # redacts before logging
    tpl = gs.CONTENT_TEMPLATE.template if hasattr(gs.CONTENT_TEMPLATE, "template") else str(gs.CONTENT_TEMPLATE)
    assert "assistant.js" in tpl


def test_popups_wait_while_the_assistant_is_open():
    app = open("pulse_app.html", encoding="utf-8").read()
    assert "html.sona-open" in app and "html.sona-open" in gs.ALERTS_POP_JS
