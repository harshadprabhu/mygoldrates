"""Sona, the site assistant: its knowledge file, learning export, referrals."""
import json
import subprocess

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


# ------------------------------------------------- languages and voice
SONA = {
    "hi": [("आज तनिष्क में 22 कैरेट सोने का भाव क्या है", "rate_brand", "Tanishq"),
           ("सबसे सस्ता सोना कहाँ मिलेगा", "cheapest", None),
           ("मुंबई में सोने का भाव", "rate_city", "Mumbai"),
           ("दस ग्राम 22 कैरेट चेन की कीमत", "price", "10 ग्राम"),
           ("तनिष्क या कल्याण", "compare", None),
           ("मेकिंग चार्ज सबसे कम कहाँ है", "making", None),
           ("आज का सबसे अच्छा ऑफ़र", "offers", None),
           ("चांदी का भाव", "silver", None)],
    "mr": [("पुण्यात आज सोन्याचा दर किती आहे", "rate_city", "Pune")],
    "gu": [("અમદાવાદમાં આજે સોનાનો ભાવ", "rate_city", "Ahmedabad"), ("સૌથી સસ્તું સોનું", "cheapest", None)],
    "pa": [("ਲੁਧਿਆਣਾ ਵਿੱਚ ਸੋਨੇ ਦਾ ਰੇਟ", "rate_city", "Ludhiana")],
    "bn": [("কলকাতায় আজ সোনার দাম", "rate_city", "Kolkata")],
    "kn": [("ಬೆಂಗಳೂರಿನಲ್ಲಿ ಇಂದಿನ ಚಿನ್ನದ ದರ", "rate_city", "Bengaluru"), ("ಹತ್ತು ಗ್ರಾಂ ಚಿನ್ನದ ಬೆಲೆ", "price", None)],
    "ta": [("சென்னையில் இன்றைய தங்க விலை", "rate_city", "Chennai"), ("தனிஷ்க் தங்க விலை", "rate_brand", "Tanishq"),
           ("கோயம்புத்தூர் தங்க விலை", "rate_city", "Coimbatore")],
    "te": [("హైదరాబాద్‌లో ఈరోజు బంగారం ధర", "rate_city", "Hyderabad")],
    "ml": [("കൊച്ചിയിലെ ഇന്നത്തെ സ്വർണവില", "rate_city", "Kochi"), ("നമസ്കാരം", "hello", None)],
}


def _sona(qs):
    inp = json.dumps({"kb": "docs/assistant.json", "qs": qs})
    r = subprocess.run(["node", "tests/sona_harness.js"], input=inp, capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def test_sona_understands_every_language_and_answers_in_it():
    qs = [{"lang": "en", "q": q} for lang in SONA for q, _, _ in SONA[lang]]
    got = _sona(qs)
    want = [(lang, intent, word) for lang in SONA for _, intent, word in SONA[lang]]
    for r, (lang, intent, word) in zip(got, want):
        assert r["intent"] == intent, (r["q"], r["text"], r["intent"])
        assert r["lang"] == lang, (r["q"], r["lang"])           # the reply follows the question's language
        assert word is None or word in r["html"] + r["say"], (r["q"], r["say"])
        assert r["say"], r["q"]                                  # something to read aloud


def test_a_chip_in_english_is_answered_in_the_chosen_language():
    r = _sona([{"lang": "ta", "q": "Cheapest 22K today"}])[0]
    assert r["intent"] == "cheapest" and r["lang"] == "ta"
    assert "மலிவான" in r["html"] and "ரூபாய்" in r["say"]


def test_every_language_has_every_reply_with_the_same_blanks():
    out = subprocess.run(["node", "-e", """
const S=require('./sona_i18n.js'), ph=s=>JSON.stringify((s.match(/\\{\\w+\\}/g)||[]).sort());
const bad=[];for(const l in S)for(const k in S.en){if(!(k in S[l])||ph(S[l][k])!==ph(S.en[k]))bad.push(l+':'+k);}
console.log(JSON.stringify({langs:Object.keys(S),bad}));"""], capture_output=True, text=True, check=True).stdout
    res = json.loads(out)
    assert sorted(res["langs"]) == sorted(["en", "hi", "mr", "gu", "pa", "bn", "kn", "ta", "te", "ml"])
    assert res["bad"] == []


def test_voice_is_the_browsers_own_and_the_bundle_ships_all_three_files():
    assert "SpeechRecognition" in JS and "speechSynthesis" in JS
    assert "api.anthropic" not in JS and "openai" not in JS.lower()
    b = gs.sona_bundle()
    assert b.index("root.SONA_STR") < b.index("root.SONA_LANG") < b.index("Sona - the MyGoldRates")
