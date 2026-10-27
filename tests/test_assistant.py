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
    "bn": [("কলকাতায় আজ সোনার দাম", "rate_city", "Kolkata"),
           ("আজকে সবচেয়ে সস্তা সোনা", "cheapest", None)],      # Bengali stays Bengali beside Assamese
    "kn": [("ಬೆಂಗಳೂರಿನಲ್ಲಿ ಇಂದಿನ ಚಿನ್ನದ ದರ", "rate_city", "Bengaluru"), ("ಹತ್ತು ಗ್ರಾಂ ಚಿನ್ನದ ಬೆಲೆ", "price", None)],
    "ta": [("சென்னையில் இன்றைய தங்க விலை", "rate_city", "Chennai"), ("தனிஷ்க் தங்க விலை", "rate_brand", "Tanishq"),
           ("கோயம்புத்தூர் தங்க விலை", "rate_city", "Coimbatore")],
    "te": [("హైదరాబాద్‌లో ఈరోజు బంగారం ధర", "rate_city", "Hyderabad")],
    "ml": [("കൊച്ചിയിലെ ഇന്നത്തെ സ്വർണവില", "rate_city", "Kochi"), ("നമസ്കാരം", "hello", None)],
    "ur": [("ممبئی میں آج سونے کا بھاؤ", "rate_city", "Mumbai"), ("سب سے سستا سونا کہاں ہے؟", "cheapest", None),
           ("تنشق سونے کا بھاؤ", "rate_brand", "Tanishq"), ("دس گرام سونے کی قیمت", "price", None),
           ("دہلی میں سونے کا ریٹ", "rate_city", "Delhi")],
    "or": [("ଭୁବନେଶ୍ୱରରେ ଆଜି ସୁନା ଦର", "rate_city", "Bhubaneswar"), ("ଆଜି ସବୁଠୁ ଶସ୍ତା ସୁନା", "cheapest", None),
           ("ତନିଷ୍କ ସୁନା ଦର", "rate_brand", "Tanishq"), ("ଦଶ ଗ୍ରାମ ସୁନାର ଦାମ", "price", None)],
    "as": [("গুৱাহাটীত আজি সোণৰ দৰ", "rate_city", "Guwahati"), ("আজি আটাইতকৈ সস্তা সোণ", "cheapest", None),
           ("দহ গ্ৰাম সোণৰ দাম", "price", None)],
}


def _sona(qs, kb="docs/assistant.json"):
    inp = json.dumps({"kb": kb, "qs": qs})
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


def test_my_city_is_the_visitors_own_never_the_last_city_asked_about(tmp_path):
    kb = json.load(open("docs/assistant.json", encoding="utf-8"))
    for c in kb["cities"]:
        if c["n"] in gs.CITY_COORDS:
            c["g"] = list(gs.CITY_COORDS[c["n"]])
    p = tmp_path / "kb.json"
    p.write_text(json.dumps(kb), encoding="utf-8")
    r = _sona([
        {"lang": "en", "q": "Gold rate in Kanpur"},       # asking about a city...
        {"q": "Gold rate in my city", "chip": True},      # ...does not make it "my city"
        {"q": "Mumbai", "chip": True},                    # the answer to "which city?" does
        {"q": "Gold rate in Kanpur"},
        {"q": "Gold rate in my city", "chip": True},
        {"lang": "gu", "q": "Gold rate in my city", "chip": True},
        {"near": [19.06, 72.84]},                         # Bandra
        {"near": [28.61, 77.21]},                         # Connaught Place
    ], kb=str(p))
    assert r[0]["intent"] == "rate_city" and "Kanpur" in r[0]["say"]
    assert r[1]["intent"] == "ask_city" and r[1]["chips"][0] == "#loc"
    assert r[2]["intent"] == "rate_city" and "Mumbai" in r[2]["say"] and "#city" in r[2]["chips"]
    assert "Kanpur" in r[3]["say"] and "#city" not in r[3]["chips"]
    assert r[4]["intent"] == "rate_city" and "Mumbai" in r[4]["say"]
    assert r[5]["lang"] == "gu" and "Mumbai" in r[5]["html"]
    assert r[6]["city"] == "Mumbai" and r[7]["city"] == "Delhi"
    assert "localStorage.setItem('sona_city'" not in JS


def test_making_charges_for_an_unmeasured_jewel_say_so_instead_of_showing_another():
    kb = json.load(open("docs/assistant.json", encoding="utf-8"))
    measured = {c for b in kb["brands"] for c in (b.get("mk") or {})}
    r = _sona([{"lang": "en", "q": "lowest making charge on a chain"}, {"q": "lowest making charge on a ring"}])
    if "Chain" not in measured:
        assert "haven’t measured making charges on a <b>chain</b>" in r[0]["html"]
    assert "Lowest making charges on a <b>ring</b>" in r[1]["html"]


def test_every_language_has_every_reply_with_the_same_blanks():
    out = subprocess.run(["node", "-e", """
const S=require('./sona_i18n.js'), ph=s=>JSON.stringify((s.match(/\\{\\w+\\}/g)||[]).sort());
const bad=[];for(const l in S)for(const k in S.en){if(!(k in S[l])||ph(S[l][k])!==ph(S.en[k]))bad.push(l+':'+k);}
console.log(JSON.stringify({langs:Object.keys(S),bad}));"""], capture_output=True, text=True, check=True).stdout
    res = json.loads(out)
    assert sorted(res["langs"]) == sorted(["en", "hi", "ur", "mr", "gu", "pa", "bn", "as", "or", "kn", "ta", "te", "ml"])
    assert res["bad"] == []


def test_voice_is_the_browsers_own_and_the_bundle_ships_all_three_files():
    assert "SpeechRecognition" in JS and "speechSynthesis" in JS
    assert "api.anthropic" not in JS and "openai" not in JS.lower()
    b = gs.sona_bundle()
    assert b.index("root.SONA_STR") < b.index("root.SONA_LANG") < b.index("Sona - the MyGoldRates")


def test_offers_answer_lists_every_jeweller_with_an_offer_and_singles_out_none():
    kb = json.load(open("docs/assistant.json", encoding="utf-8"))
    names = sorted(b["n"] for b in kb["brands"] if b.get("off"))
    r = _sona([{"lang": "hi", "q": "मुझे सब ज्वेलर्स का ऑफर बताइए"}])[0]
    assert r["intent"] == "offers"
    shown = [n for n in names if n.replace("&", "&amp;") in r["html"]]
    assert shown == names                                   # every one, none left out
    pos = [r["html"].index(n.replace("&", "&amp;")) for n in names]
    assert pos == sorted(pos)                               # A to Z, not by who has the offer
    assert "<em>" not in r["html"]                          # no badge on one jeweller


def test_language_is_automatic_and_the_mic_follows_the_visitor():
    """No language to choose: each reply follows its question, and once a
    visitor asks in Tamil the mic listens in Tamil (the browser's recogniser
    has to be told a language; Hindi's also takes English, so it starts there)."""
    got = _sona([{"lang": "auto", "q": "cheapest gold today"},
                 {"q": "சென்னையில் இன்றைய தங்க விலை"},
                 {"q": "Cheapest 22K today", "chip": True},
                 {"q": "tanishq gold rate"},
                 {"lang": "auto", "q": "आज सोने का भाव"}])
    assert [g["lang"] for g in got] == ["en", "ta", "ta", "en", "hi"]
    assert [g["mic"] for g in got] == ["hi", "ta", "ta", "ta", "hi"]


def test_the_daily_rate_email_stays_free_of_marketing():
    """The digest moved to Gmail's Promotions tab the day an invite box and
    an offers line were added (23 Oct 2026). It carries the rates only, and
    a plain-text part."""
    med = {"24K": 14050.0, "22K": 12879.0, "18K": 10537.0}
    html = sa.email_html("Asha", "25 October 2026", med, med, "PN Gadgil", "https://u", 34)
    text = sa.email_text("Asha", "25 October 2026", med, med, "PN Gadgil", "https://u", 34)
    for word in ("invite", "?ref=", "offer", "&#127873;", "free"):
        assert word not in html.lower() and word not in text.lower(), word
    assert "₹14,050" in text and "Unsubscribe: https://u" in text
    assert sa.masked("harshad@example.com") == "ha…"


def test_the_launch_email_has_no_invite_link():
    import promo_email as P
    qa = [("Which jeweller has the cheapest 22K today?", "PN Gadgil, at ₹12,958/g.")]
    body, text = P.letter("Asha", qa, "https://u")
    for out in (body, text, P.html("Asha", qa, "https://u", "25 October 2026")):
        assert "invite" not in out.lower() and "?ref=" not in out


def test_compare_jewellers_lists_every_one_and_making_comparisons_give_the_ranking():
    # questions Sona once missed (learned from visitors' thumbs-down and unanswered ones)
    kb = json.load(open("docs/assistant.json", encoding="utf-8"))
    n = sum(1 for b in kb["brands"] if b.get("nat"))
    qs = ["compare jewellers", "rate difference between jewellers",
          "How do gold rates compare across different jewellers?", "compare making charges",
          "making charges comparison", "why do jewellers rates differ", "difference between 22k and 24k"]
    got = _sona([{"lang": "en", "q": q} for q in qs])
    for r in got[:3]:
        assert r["intent"] == "cheapest", (r["q"], r["intent"])
        assert r["html"].count('class="sn-row"') >= n or r["html"].count("<tr") >= n, r["q"]   # all of them
    assert [r["intent"] for r in got[3:5]] == ["making", "making"]
    assert got[5]["intent"] == "faq" and got[6]["intent"] == "faq"         # "why" and karat questions explain
