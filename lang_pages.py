"""Today's gold rate in Indian languages (owner, 6 Nov 2026).

One page per language at /<code>/gold-rate-today: the answer in one sentence,
the weights people buy, the last 10 days and every jeweller's rate today,
from the same figures as the English homepage. Many people search in their
own language ("aaj ka sone ka bhav", "inraya thangam vilai"), where fewer
sites answer. Jeweller names stay in English, as they appear on shop signs.

Each page names the others and the English homepage as alternates
(hreflang), so search engines show the right language to each reader.
"""
import html as _html

# (code, hreflang, name in its own script, weight for the "how much" question)
LANGS = [
    ("hi", "hi-IN", "हिन्दी", 10),
    ("ta", "ta-IN", "தமிழ்", 8),
    ("te", "te-IN", "తెలుగు", 10),
    ("kn", "kn-IN", "ಕನ್ನಡ", 10),
    ("ml", "ml-IN", "മലയാളം", 8),
    ("mr", "mr-IN", "मराठी", 10),
]
SLUG = "gold-rate-today"

S = {
    "hi": {
        "title": "आज का सोने का भाव {d}: 24 कैरेट और 22 कैरेट सोने की कीमत",
        "h1": "आज का सोने का भाव ({d})",
        "lead": "आज ({d}) भारत में सोने का भाव 24 कैरेट के लिए {r24} प्रति ग्राम, 22 कैरेट के लिए {r22} और 18 कैरेट के लिए {r18} है (3% GST से पहले)। {move} यह {n} बड़े ज्वैलर्स के भाव का मध्य मान (median) है।",
        "up": "कल से 22 कैरेट {x} प्रति ग्राम बढ़ा।", "down": "कल से 22 कैरेट {x} प्रति ग्राम घटा।",
        "same": "कल के मुकाबले भाव में बदलाव नहीं।",
        "h_weight": "वज़न के हिसाब से सोने की कीमत", "weight": "वज़न", "g": "ग्राम", "sov": "",
        "h_days": "पिछले 10 दिनों का सोने का भाव (1 ग्राम)", "date": "तारीख",
        "h_jw": "आज हर ज्वैलर का भाव", "jw": "ज्वैलर",
        "note": "भाव प्रति ग्राम, 3% GST से पहले; मेकिंग चार्ज अलग से लगता है। कोष्ठक में कल से बदलाव।",
        "q1": "आज {w} ग्राम 22 कैरेट सोना कितने का है?",
        "a1": "आज {w} ग्राम 22 कैरेट सोना GST से पहले {a} और 3% GST के साथ {b} का है। गहनों पर मेकिंग चार्ज अलग से लगता है।",
        "q2": "आज सबसे सस्ता सोना किस ज्वैलर के पास है?",
        "a2": "आज राष्ट्रीय ज्वैलर्स में {name} का 22 कैरेट भाव सबसे कम है: {r} प्रति ग्राम।",
        "en": "English में देखें",
        "desc": "आज का सोने का भाव {d}: 24 कैरेट {r24}/ग्राम, 22 कैरेट {r22}/ग्राम। {n} ज्वैलर्स के भाव की तुलना, पिछले 10 दिन का भाव।",
    },
    "ta": {
        "title": "இன்றைய தங்கம் விலை {d}: 22 காரட், 24 காரட் தங்கம் விலை",
        "h1": "இன்றைய தங்கம் விலை ({d})",
        "lead": "இன்று ({d}) இந்தியாவில் தங்கம் விலை 24 காரட் ஒரு கிராமுக்கு {r24}, 22 காரட் {r22}, 18 காரட் {r18} (3% GST சேர்க்காமல்). {move} இது {n} பெரிய நகைக்கடைகளின் விலைகளின் நடுநிலை (median) மதிப்பு.",
        "up": "நேற்றை விட 22 காரட் கிராமுக்கு {x} உயர்ந்துள்ளது.", "down": "நேற்றை விட 22 காரட் கிராமுக்கு {x} குறைந்துள்ளது.",
        "same": "நேற்றைய விலையில் மாற்றம் இல்லை.",
        "h_weight": "எடை வாரியாக தங்கம் விலை", "weight": "எடை", "g": "கிராம்", "sov": " (1 சவரன்)",
        "h_days": "கடந்த 10 நாட்களின் தங்கம் விலை (1 கிராம்)", "date": "தேதி",
        "h_jw": "இன்று ஒவ்வொரு நகைக்கடையின் விலை", "jw": "நகைக்கடை",
        "note": "விலை ஒரு கிராமுக்கு, 3% GST சேர்க்காமல்; செய்கூலி தனி. அடைப்புக்குறிக்குள் நேற்றிலிருந்து மாற்றம்.",
        "q1": "இன்று 1 சவரன் ({w} கிராம்) 22 காரட் தங்கம் விலை என்ன?",
        "a1": "இன்று {w} கிராம் 22 காரட் தங்கம் GST இல்லாமல் {a}, 3% GST உடன் {b}. நகைகளுக்கு செய்கூலி தனியாக சேரும்.",
        "q2": "இன்று எந்த நகைக்கடையில் தங்கம் விலை குறைவு?",
        "a2": "இன்று தேசிய நகைக்கடைகளில் {name} இன் 22 காரட் விலை மிகக் குறைவு: கிராமுக்கு {r}.",
        "en": "ஆங்கிலத்தில் பார்க்க",
        "desc": "இன்றைய தங்கம் விலை {d}: 24 காரட் {r24}/கிராம், 22 காரட் {r22}/கிராம். {n} நகைக்கடைகளின் விலை ஒப்பீடு, கடந்த 10 நாள் விலை.",
    },
    "te": {
        "title": "ఈరోజు బంగారం ధర {d}: 22 క్యారెట్, 24 క్యారెట్ బంగారం ధర",
        "h1": "ఈరోజు బంగారం ధర ({d})",
        "lead": "ఈరోజు ({d}) భారతదేశంలో బంగారం ధర 24 క్యారెట్ గ్రాముకు {r24}, 22 క్యారెట్ {r22}, 18 క్యారెట్ {r18} (3% GST లేకుండా). {move} ఇది {n} ప్రధాన జ్యువెలర్ల ధరల మధ్యస్థ (median) విలువ.",
        "up": "నిన్నటి కంటే 22 క్యారెట్ గ్రాముకు {x} పెరిగింది.", "down": "నిన్నటి కంటే 22 క్యారెట్ గ్రాముకు {x} తగ్గింది.",
        "same": "నిన్నటి ధరలో మార్పు లేదు.",
        "h_weight": "బరువు ప్రకారం బంగారం ధర", "weight": "బరువు", "g": "గ్రాము", "sov": "",
        "h_days": "గత 10 రోజుల బంగారం ధర (1 గ్రాము)", "date": "తేదీ",
        "h_jw": "ఈరోజు ప్రతి జ్యువెలర్ ధర", "jw": "జ్యువెలర్",
        "note": "ధర గ్రాముకు, 3% GST లేకుండా; తయారీ ఛార్జీలు అదనం. బ్రాకెట్‌లో నిన్నటి నుండి మార్పు.",
        "q1": "ఈరోజు {w} గ్రాముల 22 క్యారెట్ బంగారం ధర ఎంత?",
        "a1": "ఈరోజు {w} గ్రాముల 22 క్యారెట్ బంగారం GST లేకుండా {a}, 3% GST తో {b}. ఆభరణాలకు తయారీ ఛార్జీలు అదనం.",
        "q2": "ఈరోజు ఏ జ్యువెలర్ వద్ద బంగారం ధర తక్కువ?",
        "a2": "ఈరోజు జాతీయ జ్యువెలర్లలో {name} 22 క్యారెట్ ధర అత్యల్పం: గ్రాముకు {r}.",
        "en": "ఇంగ్లీష్‌లో చూడండి",
        "desc": "ఈరోజు బంగారం ధర {d}: 24 క్యారెట్ {r24}/గ్రాము, 22 క్యారెట్ {r22}/గ్రాము. {n} జ్యువెలర్ల ధరల పోలిక, గత 10 రోజుల ధర.",
    },
    "kn": {
        "title": "ಇಂದಿನ ಚಿನ್ನದ ದರ {d}: 22 ಕ್ಯಾರೆಟ್, 24 ಕ್ಯಾರೆಟ್ ಚಿನ್ನದ ಬೆಲೆ",
        "h1": "ಇಂದಿನ ಚಿನ್ನದ ದರ ({d})",
        "lead": "ಇಂದು ({d}) ಭಾರತದಲ್ಲಿ ಚಿನ್ನದ ದರ 24 ಕ್ಯಾರೆಟ್ ಪ್ರತಿ ಗ್ರಾಂಗೆ {r24}, 22 ಕ್ಯಾರೆಟ್ {r22}, 18 ಕ್ಯಾರೆಟ್ {r18} (3% GST ಇಲ್ಲದೆ). {move} ಇದು {n} ಪ್ರಮುಖ ಆಭರಣ ಮಳಿಗೆಗಳ ದರಗಳ ಮಧ್ಯಮ (median) ಮೌಲ್ಯ.",
        "up": "ನಿನ್ನೆಗಿಂತ 22 ಕ್ಯಾರೆಟ್ ಪ್ರತಿ ಗ್ರಾಂಗೆ {x} ಏರಿಕೆಯಾಗಿದೆ.", "down": "ನಿನ್ನೆಗಿಂತ 22 ಕ್ಯಾರೆಟ್ ಪ್ರತಿ ಗ್ರಾಂಗೆ {x} ಇಳಿಕೆಯಾಗಿದೆ.",
        "same": "ನಿನ್ನೆಯ ದರದಲ್ಲಿ ಬದಲಾವಣೆ ಇಲ್ಲ.",
        "h_weight": "ತೂಕದ ಪ್ರಕಾರ ಚಿನ್ನದ ಬೆಲೆ", "weight": "ತೂಕ", "g": "ಗ್ರಾಂ", "sov": "",
        "h_days": "ಕಳೆದ 10 ದಿನಗಳ ಚಿನ್ನದ ದರ (1 ಗ್ರಾಂ)", "date": "ದಿನಾಂಕ",
        "h_jw": "ಇಂದು ಪ್ರತಿ ಆಭರಣ ಮಳಿಗೆಯ ದರ", "jw": "ಆಭರಣ ಮಳಿಗೆ",
        "note": "ದರ ಪ್ರತಿ ಗ್ರಾಂಗೆ, 3% GST ಇಲ್ಲದೆ; ತಯಾರಿಕಾ ಶುಲ್ಕ ಪ್ರತ್ಯೇಕ. ಆವರಣದಲ್ಲಿ ನಿನ್ನೆಯಿಂದ ಬದಲಾವಣೆ.",
        "q1": "ಇಂದು {w} ಗ್ರಾಂ 22 ಕ್ಯಾರೆಟ್ ಚಿನ್ನದ ಬೆಲೆ ಎಷ್ಟು?",
        "a1": "ಇಂದು {w} ಗ್ರಾಂ 22 ಕ್ಯಾರೆಟ್ ಚಿನ್ನ GST ಇಲ್ಲದೆ {a}, 3% GST ಸೇರಿ {b}. ಆಭರಣಗಳಿಗೆ ತಯಾರಿಕಾ ಶುಲ್ಕ ಪ್ರತ್ಯೇಕ.",
        "q2": "ಇಂದು ಯಾವ ಆಭರಣ ಮಳಿಗೆಯಲ್ಲಿ ಚಿನ್ನ ಅಗ್ಗ?",
        "a2": "ಇಂದು ರಾಷ್ಟ್ರೀಯ ಮಳಿಗೆಗಳಲ್ಲಿ {name} ನ 22 ಕ್ಯಾರೆಟ್ ದರ ಅತಿ ಕಡಿಮೆ: ಪ್ರತಿ ಗ್ರಾಂಗೆ {r}.",
        "en": "ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ನೋಡಿ",
        "desc": "ಇಂದಿನ ಚಿನ್ನದ ದರ {d}: 24 ಕ್ಯಾರೆಟ್ {r24}/ಗ್ರಾಂ, 22 ಕ್ಯಾರೆಟ್ {r22}/ಗ್ರಾಂ. {n} ಆಭರಣ ಮಳಿಗೆಗಳ ದರ ಹೋಲಿಕೆ, ಕಳೆದ 10 ದಿನಗಳ ದರ.",
    },
    "ml": {
        "title": "ഇന്നത്തെ സ്വർണവില {d}: 22 കാരറ്റ്, 24 കാരറ്റ് സ്വർണവില",
        "h1": "ഇന്നത്തെ സ്വർണവില ({d})",
        "lead": "ഇന്ന് ({d}) ഇന്ത്യയിൽ സ്വർണവില 24 കാരറ്റ് ഗ്രാമിന് {r24}, 22 കാരറ്റ് {r22}, 18 കാരറ്റ് {r18} (3% GST ഇല്ലാതെ). {move} ഇത് {n} പ്രമുഖ ജ്വല്ലറികളുടെ വിലകളുടെ മീഡിയൻ (median) ആണ്.",
        "up": "ഇന്നലത്തേക്കാൾ 22 കാരറ്റിന് ഗ്രാമിന് {x} കൂടി.", "down": "ഇന്നലത്തേക്കാൾ 22 കാരറ്റിന് ഗ്രാമിന് {x} കുറഞ്ഞു.",
        "same": "ഇന്നലത്തെ വിലയിൽ മാറ്റമില്ല.",
        "h_weight": "തൂക്കം അനുസരിച്ച് സ്വർണവില", "weight": "തൂക്കം", "g": "ഗ്രാം", "sov": " (1 പവൻ)",
        "h_days": "കഴിഞ്ഞ 10 ദിവസത്തെ സ്വർണവില (1 ഗ്രാം)", "date": "തീയതി",
        "h_jw": "ഇന്ന് ഓരോ ജ്വല്ലറിയുടെയും വില", "jw": "ജ്വല്ലറി",
        "note": "വില ഗ്രാമിന്, 3% GST ഇല്ലാതെ; പണിക്കൂലി പുറമേ. ബ്രാക്കറ്റിൽ ഇന്നലെ മുതലുള്ള മാറ്റം.",
        "q1": "ഇന്ന് ഒരു പവൻ ({w} ഗ്രാം) 22 കാരറ്റ് സ്വർണത്തിന് എന്ത് വില?",
        "a1": "ഇന്ന് {w} ഗ്രാം 22 കാരറ്റ് സ്വർണത്തിന് GST ഇല്ലാതെ {a}, 3% GST ചേർത്ത് {b}. ആഭരണങ്ങൾക്ക് പണിക്കൂലി പുറമേ.",
        "q2": "ഇന്ന് ഏത് ജ്വല്ലറിയിലാണ് സ്വർണത്തിന് വില കുറവ്?",
        "a2": "ഇന്ന് ദേശീയ ജ്വല്ലറികളിൽ {name} ന്റെ 22 കാരറ്റ് വിലയാണ് ഏറ്റവും കുറവ്: ഗ്രാമിന് {r}.",
        "en": "ഇംഗ്ലീഷിൽ കാണുക",
        "desc": "ഇന്നത്തെ സ്വർണവില {d}: 24 കാരറ്റ് {r24}/ഗ്രാം, 22 കാരറ്റ് {r22}/ഗ്രാം. {n} ജ്വല്ലറികളുടെ വില താരതമ്യം, കഴിഞ്ഞ 10 ദിവസത്തെ വില.",
    },
    "mr": {
        "title": "आजचा सोन्याचा दर {d}: 22 कॅरेट, 24 कॅरेट सोन्याचा भाव",
        "h1": "आजचा सोन्याचा दर ({d})",
        "lead": "आज ({d}) भारतात सोन्याचा दर 24 कॅरेटसाठी प्रति ग्रॅम {r24}, 22 कॅरेटसाठी {r22} आणि 18 कॅरेटसाठी {r18} आहे (3% GST शिवाय). {move} हा {n} प्रमुख ज्वेलर्सच्या दरांचा मध्यम (median) दर आहे.",
        "up": "कालपेक्षा 22 कॅरेट प्रति ग्रॅम {x} ने वाढला.", "down": "कालपेक्षा 22 कॅरेट प्रति ग्रॅम {x} ने कमी झाला.",
        "same": "कालच्या दरात बदल नाही.",
        "h_weight": "वजनानुसार सोन्याचा दर", "weight": "वजन", "g": "ग्रॅम", "sov": "",
        "h_days": "मागील 10 दिवसांचा सोन्याचा दर (1 ग्रॅम)", "date": "तारीख",
        "h_jw": "आज प्रत्येक ज्वेलरचा दर", "jw": "ज्वेलर",
        "note": "दर प्रति ग्रॅम, 3% GST शिवाय; घडणावळ वेगळी. कंसात कालपासूनचा बदल.",
        "q1": "आज {w} ग्रॅम 22 कॅरेट सोन्याचा भाव किती?",
        "a1": "आज {w} ग्रॅम 22 कॅरेट सोने GST शिवाय {a} आणि 3% GST सह {b}. दागिन्यांवर घडणावळ वेगळी लागते.",
        "q2": "आज कोणत्या ज्वेलरकडे सोने स्वस्त आहे?",
        "a2": "आज राष्ट्रीय ज्वेलर्समध्ये {name} चा 22 कॅरेट दर सर्वात कमी आहे: प्रति ग्रॅम {r}.",
        "en": "English मध्ये पहा",
        "desc": "आजचा सोन्याचा दर {d}: 24 कॅरेट {r24}/ग्रॅम, 22 कॅरेट {r22}/ग्रॅम. {n} ज्वेलर्सच्या दरांची तुलना, मागील 10 दिवसांचे दर.",
    },
}

F22, F18 = 22 / 24, 18 / 24


def alternates(site):
    """<link rel=alternate hreflang> for the English homepage and every
    language page; the same set goes on each of them."""
    out = [f'<link rel="alternate" hreflang="en-IN" href="{site}/">',
           f'<link rel="alternate" hreflang="x-default" href="{site}/">']
    out += [f'<link rel="alternate" hreflang="{hl}" href="{site}/{c}/{SLUG}">'
            for c, hl, _n, _w in LANGS]
    return "\n".join(out)


def lang_links(site, current=None):
    """A row of links to every language version."""
    items = [f'<a href="{site}/" hreflang="en-IN">English</a>'] + [
        f'<a href="{site}/{c}/{SLUG}" hreflang="{hl}"'
        + (' aria-current="page"' if c == current else "") + f'>{n}</a>'
        for c, hl, n, _w in LANGS]
    return " &middot; ".join(items)


def build(code, *, inr, d, series, rows, national, site):
    """(title, desc, body, faq) for one language.

    series: [(iso_date, 24K median)] oldest first, today last.
    rows: today's rates, [(jeweller name, 24K)], cheapest first.
    national: the same for national chains only (for "cheapest").
    """
    s = S[code]
    w = next(x[3] for x in LANGS if x[0] == code)
    e = _html.escape
    cur, prev = series[-1][1], (series[-2][1] if len(series) > 1 else series[-1][1])
    d22 = (cur - prev) * F22
    move = (s["same"] if abs(d22) < 1 else
            (s["up"] if d22 > 0 else s["down"]).format(x=inr(abs(d22))))
    r24, r22, r18 = inr(cur), inr(cur * F22), inr(cur * F18)
    n = len(national) or len(rows)
    title = s["title"].format(d=d) + " | MyGoldRates"
    desc = s["desc"].format(d=d, r24=r24, r22=r22, n=len(rows))

    def ch(v):
        v = round(v)
        if v == 0:
            return "(0)"
        return f'({"+" if v > 0 else "-"}{inr(abs(v))})'
    wrows = "".join(
        f'<tr><td>{g} {s["g"]}{s["sov"] if g == 8 else ""}</td>'
        + "".join(f'<td>{inr(round(cur * f * g))}<small style="display:block;white-space:nowrap">'
                  f"{ch((cur - prev) * f * g)}</small></td>"
                  for f in (1, F22, F18)) + "</tr>"
        for g in (1, 8, 10, 100))
    tail = series[-11:]
    hrows = "".join(
        f'<tr><td>{tail[i][0][8:10]}/{tail[i][0][5:7]}/{tail[i][0][:4]}</td>'
        f'<td>{inr(tail[i][1])} <small style="white-space:nowrap">{ch(tail[i][1] - tail[i - 1][1])}</small></td>'
        f'<td>{inr(tail[i][1] * F22)} <small style="white-space:nowrap">{ch((tail[i][1] - tail[i - 1][1]) * F22)}</small></td></tr>'
        for i in range(len(tail) - 1, 0, -1))
    jrows = "".join(f"<tr><td>{e(nm)}</td><td>{inr(v)}</td><td>{inr(v * F22)}</td></tr>"
                    for nm, v in rows)
    best = (national or rows)[0]
    faq = [(s["q1"].format(w=w),
            s["a1"].format(w=w, a=inr(cur * F22 * w), b=inr(cur * F22 * w * 1.03))),
           (s["q2"], s["a2"].format(name=best[0], r=inr(best[1] * F22)))]
    body = (
        f'<p class="langs">{lang_links(site, code)}</p>'
        f'<h1>{e(s["h1"].format(d=d))}</h1>'
        f'<p>{e(s["lead"].format(d=d, r24=r24, r22=r22, r18=r18, move=move, n=n))}</p>'
        f'<h2>{e(s["h_weight"])}</h2>'
        f'<div style="overflow-x:auto"><table><thead><tr><th>{e(s["weight"])}</th>'
        f"<th>24K</th><th>22K</th><th>18K</th></tr></thead><tbody>{wrows}</tbody></table></div>"
        f'<p><small>{e(s["note"])}</small></p>'
        f'<h2>{e(s["h_days"])}</h2>'
        f'<table><thead><tr><th>{e(s["date"])}</th><th>24K</th><th>22K</th></tr></thead>'
        f"<tbody>{hrows}</tbody></table>"
        f'<h2>{e(s["h_jw"])}</h2>'
        f'<div style="overflow-x:auto"><table><thead><tr><th>{e(s["jw"])}</th><th>24K</th>'
        f"<th>22K</th></tr></thead><tbody>{jrows}</tbody></table></div>"
        + "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in faq)
        + f'<p><a href="{site}/" hreflang="en-IN">{e(s["en"])} &rarr;</a></p>')
    return title, desc, body, faq
