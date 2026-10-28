/* Sona's replies in thirteen languages (Urdu right to left). {x} marks a value filled in at answer
 * time (a jeweller, a city, a price); "say_" lines are what she speaks
 * aloud, so they carry words, not tables. Missing keys fall back to
 * English. Figures stay in Western digits, as Indian sites print them.
 */
(function (root) {
  'use strict';
  var S = {};

  S.en = {
    ui_sub: 'Jewellery assistant · answers from today’s real rates',
    ui_ph: 'Ask about rates, jewellers, offers…',
    ui_listen: 'Listening… speak now',
    ui_mic: 'Speak your question',
    ui_foot: 'Free · type or talk · answers from published data, not advice',
    ui_lang: 'Language', ui_speak: 'Read aloud', ui_mute: 'Stop reading aloud',
    greet1: 'Namaste! 🙏 I’m <b>Sona</b>, your jewellery assistant.',
    greet2: 'Ask me anything about buying gold — today’s rate at any jeweller, the cheapest in your city, making charges, offers, or the price of any weight. Type, or tap the 🎤 and talk.',
    lang_hint: 'Ask in your own language — typed or spoken — and I reply in the same one. Speaking a language other than Hindi or English? Tap it once:',
    ui_auto: 'Auto (detect)',
    src: 'Today’s rates from {n} jewellers, before GST · {d}',
    med_h: 'Gold rate in India today, the middle of {n} jewellers:',
    med_low: 'Lowest 22K among national jewellers: <b>{b}</b> at <b>{p}/g</b>.',
    brand_h: '<b>{b}</b> today:',
    brand_rank: 'That’s <b>#{r} of {n}</b> jewellers today — {rel}.',
    rel_at: 'right at the market middle for {k}', rel_below: '{p}/g below the market middle for {k}', rel_above: '{p}/g above the market middle for {k}',
    brand_mk: 'Usual making charges: {list}.',
    brand_off: 'Offer on their site: <b>{o}</b>.',
    brand_st: 'Sells in {s}.',
    brand_link: '{b}’s 30-day rates →',
    city_h: 'Cheapest {k} for <b>{c}</b> today ({note}):',
    city_loc: 'national jewellers plus {l} that sell in {s}', city_nat: 'national jewellers',
    city_link: 'Full board for {c} →',
    cheap_h: 'Cheapest {k} among national jewellers today:',
    cheap_gap: 'The gap from cheapest to dearest is <b>{p}</b> on 10 g — worth checking before you buy.',
    cmp_h: 'Side by side today ({k}):', cmp_10: '{p} for 10 g', cmp_mk: 'Making ~{p}', cmp_nomk: 'Making: not measured',
    cmp_win: '<b>{b}</b> has the lower {k} rate by <b>{p}</b> on 10 g. The final bill also depends on the making charge for the design you pick.',
    mk_none: 'We haven’t measured <b>{b}</b>’s making charges yet. We have them for {list}.',
    mk_link: 'Making charges compared →',
    mk_brand_h: '<b>{b}</b>’s usual making charges (median of real products, % of gold value):',
    mk_note: 'Varies by design; it’s the most negotiable part of the bill.',
    mk_all: 'Compare all jewellers →',
    mk_h: 'Lowest making charges on a <b>{c}</b> (median of real products):',
    mk_nocat: 'We haven’t measured making charges on a <b>{c}</b> yet. Here they are for a <b>{r}</b>:',
    mk_every: 'Every jeweller and category →',
    bo_ask: 'Which piece should I find the best offer for?',
    bo_h: 'Best price for <b>{w}</b> of 22K <b>{c}</b> after today’s making-charge offers:',
    bo_note: 'Total = gold + making charge after the offer + 3% GST. Offer % is tentative; * means “up to”, on some designs only (best case in brackets). Confirm with the jeweller.',
    bo_none: 'I don’t have making charges for a {c} at enough jewellers yet.',
    say_bo: 'For {w} of 22K {c}, {b} is cheapest after offers, about {p} with GST.',
    bo_upto: 'up to',
    bo_noff: 'no offer',
    off_none: 'No offer is published as text on <b>{b}</b>’s website today.',
    off_see: 'See who has offers →',
    off_brand_h: 'Offers on <b>{b}</b>’s website today:',
    off_page: 'Their page ↗', off_all: 'All jewellers’ offers compared →',
    off_all_h: '{n} jewellers have offers on their own websites today (A–Z):',
    off_ring: 'Counting only offers that apply to every design, the lowest price for a 10 g 22K ring today is at <b>{b}</b>: {p} with GST. “Up to” and selected-design offers vary by piece — confirm with the jeweller.',
    off_every: 'Every offer, and what it really means →',
    price_h: '{w} of {k} at {who} today:', price_who: 'the cheapest national jeweller ({b})',
    price_gold: 'Gold ({g} g × {p})', price_mk: 'Making (~{p}, {c})', price_typ: 'typical', price_total: 'Total',
    price_nomk: 'Making charges not included — add the jeweller’s charge for your design (often 8–25%).',
    trend_none: 'Not enough history yet.', hist_link: 'Gold rate history →',
    trend_h: '{k} market middle: <b>{p}/g</b> today.',
    vs1: 'vs previous day', vs7: 'vs 7 days ago', vs30: 'vs 30 days ago',
    trend_note: 'Past moves, not a forecast — nobody can reliably predict tomorrow’s price.',
    full_hist: 'Full history →',
    alerts: 'Get the cheapest jeweller and today’s rate every morning, free — and an email the day 22K drops to your price.',
    alerts_cta: 'Get free daily alerts',
    more: 'Read more →', guide_h: 'This guide covers it: <b>{t}</b> — {d}', guide_link: 'Read the guide →',
    en_only: 'This answer is in English for now:', translated: 'Translated on your device',
    ask_city: 'Which city are you in?',
    ch_loc: 'Use my location', loc_wait: 'Finding your nearest city…',
    loc_fail: 'I couldn\'t get your location. Type your city, or pick one:', ch_chcity: 'Change city',
    silver: 'I cover gold for now — jewellers’ 22K, 24K and 18K rates. Silver is on its way.',
    hello: 'Namaste! 🙏 I’m Sona. Ask me anything about buying gold — today’s rates at {n} jewellers, your city, making charges, offers or a price for any weight.',
    thanks: 'Happy to help! Anything else?',
    about: 'I’m Sona, MyGoldRates’ assistant. I answer from today’s real data — {n} jewellers’ published rates, making charges measured from real products, and the offers on their websites — so I never guess a number.',
    unknown: 'I’m still learning that one — I’ve noted your question so we can add a proper answer soon. Meanwhile, I’m good at these:',
    nodata: 'I couldn’t load today’s data. Please check your connection and try again.',
    no_voice: 'This device has no {l} voice for reading aloud, so I’ll answer in text.',
    mic_denied: 'The microphone is blocked. Allow it for this site in your browser settings, then tap the 🎤 again.',
    mic_none: 'I didn’t catch that — tap the 🎤 and try again.',
    rupees: 'rupees', carat: 'carat',
    say_med: 'Today {k} gold is about {p} per gram, the middle of {n} jewellers. The lowest is {b}, at {q}.',
    say_brand: '{b}: {k} gold is {p} per gram today, number {r} of {n} jewellers.',
    say_city: 'In {c}, the cheapest {k} today is at {b}: {p} per gram.',
    say_cheap: 'The cheapest {k} today is at {b}: {p} per gram. On 10 grams, the dearest jeweller charges {q} more.',
    say_cmp: '{b} is cheaper, by {p} on 10 grams of {k}.',
    say_mk_brand: '{b}’s usual making charge on a {c} is about {p}.',
    say_mk: 'The lowest making charge on a {c} is at {b}, about {p}.',
    say_mk_none: 'We have not measured {b}’s making charges yet.',
    say_off_all: '{n} jewellers have offers today. Counting only offers that apply to every design, a 10 gram 22 carat ring costs the least at {b}: {p} with GST.',
    say_off_brand: '{b} has {n} offers on its website today.',
    say_off_none: 'No offer is published on {b}’s website today.',
    say_price: '{w} of {k} gold at {b} comes to about {p}, with GST.',
    say_trend_up: '{k} gold is {p} per gram today, up {q} from the previous day.',
    say_trend_dn: '{k} gold is {p} per gram today, down {q} from the previous day.',
    say_trend_same: '{k} gold is {p} per gram today, the same as the previous day.',
    u_g: '{n} g', u_tola: '{n} tola', u_sov: '{n} sovereign', u_kg: '{n} kg',
    c_Ring: 'ring', c_Chain: 'chain', c_Bangle: 'bangle', c_Necklace: 'necklace', c_Earrings: 'earrings',
    c_Mangalsutra: 'mangalsutra', c_Pendant: 'pendant', c_Bracelet: 'bracelet', c_Coin: 'coin',
    ch_cheap22: 'Cheapest 22K today', ch_mycity: 'Gold rate in my city', ch_tvk: 'Tanishq vs Kalyan',
    ch_bestoff: 'Best offer today', ch_p10chain: 'Price of 10 g 22K chain', ch_k22v24: '22K vs 24K?',
    ch_p10: 'Price of 10 g 22K', ch_afteroff: 'Price after offers', ch_mkcmp: 'Making charges compared',
    ch_goodmk: 'Is 20% off making a good deal?', ch_whatmk: 'What are making charges?', ch_alert: 'Set a price alert',
    ch_goodtime: 'Is now a good time to buy?', ch_rate: 'Gold rate today', ch_another: 'Same at another jeweller',
    ch_bmk: '{b} making charges', ch_boff: '{b} offers'
  };

  S.hi = {
    ui_sub: 'ज्वेलरी असिस्टेंट · आज के असली भाव से जवाब',
    ui_ph: 'भाव, ज्वैलर, ऑफ़र के बारे में पूछें…',
    ui_listen: 'सुन रही हूँ… बोलिए',
    ui_mic: 'बोलकर पूछें',
    ui_foot: 'मुफ़्त · लिखें या बोलें · प्रकाशित आँकड़ों से जवाब, सलाह नहीं',
    ui_lang: 'भाषा', ui_speak: 'सुनें', ui_mute: 'बोलना बंद करें',
    greet1: 'नमस्ते! 🙏 मैं <b>सोना</b> हूँ, आपकी ज्वेलरी असिस्टेंट।',
    greet2: 'सोना ख़रीदने से जुड़ा कुछ भी पूछिए — किसी भी ज्वैलर का आज का भाव, आपके शहर में सबसे सस्ता, मेकिंग चार्ज, ऑफ़र या किसी भी वज़न की क़ीमत। लिखिए, या 🎤 दबाकर बोलिए।',
    lang_hint: 'अपनी भाषा में पूछिए — लिखकर या बोलकर — मैं उसी भाषा में जवाब दूँगी। हिन्दी या अंग्रेज़ी के अलावा कोई और भाषा बोलनी है? उसे एक बार चुनें:',
    ui_auto: 'अपने-आप (पहचानें)',
    src: 'आज के भाव {n} ज्वैलर्स से, GST से पहले · {d}',
    med_h: 'भारत में आज सोने का भाव, {n} ज्वैलर्स का बीच का भाव:',
    med_low: 'राष्ट्रीय ज्वैलर्स में सबसे कम 22K: <b>{b}</b>, <b>{p}/ग्राम</b>।',
    brand_h: '<b>{b}</b> आज:',
    brand_rank: 'आज {n} ज्वैलर्स में यह <b>#{r}</b> पर है — {rel}।',
    rel_at: '{k} के बाज़ार के बीच के भाव के बराबर', rel_below: '{k} के बीच के भाव से {p}/ग्राम कम', rel_above: '{k} के बीच के भाव से {p}/ग्राम ज़्यादा',
    brand_mk: 'आम मेकिंग चार्ज: {list}।',
    brand_off: 'उनकी साइट पर ऑफ़र: <b>{o}</b>।',
    brand_st: 'इन राज्यों में: {s}।',
    brand_link: '{b} के 30 दिन के भाव →',
    city_h: '<b>{c}</b> में आज सबसे सस्ता {k} ({note}):',
    city_loc: 'राष्ट्रीय ज्वैलर्स और {s} के {l} स्थानीय ज्वैलर', city_nat: 'राष्ट्रीय ज्वैलर्स',
    city_link: '{c} की पूरी सूची →',
    cheap_h: 'राष्ट्रीय ज्वैलर्स में आज सबसे सस्ता {k}:',
    cheap_gap: 'सबसे सस्ते और सबसे महँगे में 10 ग्राम पर <b>{p}</b> का फ़र्क़ है — ख़रीदने से पहले ज़रूर देखें।',
    cmp_h: 'आज आमने-सामने ({k}):', cmp_10: '10 ग्राम: {p}', cmp_mk: 'मेकिंग ~{p}', cmp_nomk: 'मेकिंग: मापा नहीं गया',
    cmp_win: '<b>{b}</b> का {k} भाव 10 ग्राम पर <b>{p}</b> कम है। आख़िरी बिल आपके चुने डिज़ाइन के मेकिंग चार्ज पर भी निर्भर करता है।',
    mk_none: '<b>{b}</b> का मेकिंग चार्ज हमने अभी नहीं मापा है। इनका मापा है: {list}।',
    mk_link: 'मेकिंग चार्ज की तुलना →',
    mk_brand_h: '<b>{b}</b> का आम मेकिंग चार्ज (असली प्रोडक्ट्स का बीच का आँकड़ा, सोने की क़ीमत का %):',
    mk_note: 'डिज़ाइन के हिसाब से बदलता है; बिल में इसी पर सबसे ज़्यादा मोलभाव हो सकता है।',
    mk_all: 'सभी ज्वैलर्स की तुलना →',
    mk_h: '<b>{c}</b> पर सबसे कम मेकिंग चार्ज (असली प्रोडक्ट्स का बीच का आँकड़ा):',
    mk_nocat: '<b>{c}</b> का मेकिंग चार्ज हमने अभी नहीं मापा है। <b>{r}</b> का यह है:',
    mk_every: 'हर ज्वैलर और हर कैटेगरी →',
    bo_ask: 'किस गहने पर सबसे अच्छा ऑफ़र निकालूँ?',
    bo_h: 'आज के मेकिंग-चार्ज ऑफ़र के बाद <b>{w}</b> 22K <b>{c}</b> की सबसे अच्छी क़ीमत:',
    bo_note: 'कुल = सोना + ऑफ़र के बाद मेकिंग चार्ज + 3% GST. ऑफ़र % अनुमानित है; * यानी “तक”, सिर्फ़ कुछ डिज़ाइनों पर (कोष्ठक में सबसे अच्छी स्थिति). ज्वैलर से पक्का करें.',
    bo_none: '{c} के मेकिंग चार्ज अभी काफ़ी ज्वैलर्स के मेरे पास नहीं हैं.',
    say_bo: '{w} 22K {c} के लिए ऑफ़र के बाद {b} सबसे सस्ता है, GST के साथ लगभग {p}.',
    bo_upto: 'तक',
    bo_noff: 'कोई ऑफ़र नहीं',
    off_none: 'आज <b>{b}</b> की वेबसाइट पर कोई ऑफ़र लिखा हुआ नहीं है।',
    off_see: 'देखें किसके पास ऑफ़र है →',
    off_brand_h: 'आज <b>{b}</b> की वेबसाइट पर ऑफ़र:',
    off_page: 'उनका पेज ↗', off_all: 'सभी ज्वैलर्स के ऑफ़र की तुलना →',
    off_all_h: 'आज {n} ज्वैलर्स की अपनी वेबसाइट पर ऑफ़र हैं (A–Z):',
    off_ring: 'सिर्फ़ हर डिज़ाइन पर लागू ऑफ़र गिनकर, आज 10 ग्राम 22K अंगूठी सबसे कम <b>{b}</b> पर है: GST के साथ {p}। “अप टू” और चुनिंदा डिज़ाइन वाले ऑफ़र हर गहने पर अलग होते हैं — ज्वैलर से पक्का कर लें।',
    off_every: 'हर ऑफ़र, और उसका असली मतलब →',
    price_h: 'आज {who} पर {w} {k}:', price_who: 'सबसे सस्ता राष्ट्रीय ज्वैलर ({b})',
    price_gold: 'सोना ({g} ग्राम × {p})', price_mk: 'मेकिंग (~{p}, {c})', price_typ: 'आम तौर पर', price_total: 'कुल',
    price_nomk: 'मेकिंग चार्ज शामिल नहीं — अपने डिज़ाइन का चार्ज जोड़ें (अक्सर 8–25%)।',
    trend_none: 'अभी पर्याप्त इतिहास नहीं है।', hist_link: 'सोने के भाव का इतिहास →',
    trend_h: '{k} का बाज़ार का बीच का भाव: आज <b>{p}/ग्राम</b>।',
    vs1: 'पिछले दिन से', vs7: '7 दिन पहले से', vs30: '30 दिन पहले से',
    trend_note: 'यह बीता हुआ बदलाव है, भविष्यवाणी नहीं — कल का भाव कोई पक्का नहीं बता सकता।',
    full_hist: 'पूरा इतिहास →',
    alerts: 'हर सुबह सबसे सस्ता ज्वैलर और आज का भाव, मुफ़्त — और जिस दिन 22K आपके भाव तक गिरे, उस दिन ईमेल।',
    alerts_cta: 'मुफ़्त रोज़ाना अलर्ट पाएँ',
    more: 'और पढ़ें →', guide_h: 'यह गाइड इसी बारे में है: <b>{t}</b> — {d}', guide_link: 'गाइड पढ़ें →',
    en_only: 'यह जवाब अभी अंग्रेज़ी में है:', translated: 'आपके डिवाइस पर अनुवाद किया गया',
    ask_city: 'आप किस शहर में हैं?',
    ch_loc: 'मेरी लोकेशन से', loc_wait: 'आपका नज़दीकी शहर ढूँढ रही हूँ…',
    loc_fail: 'लोकेशन नहीं मिली। अपने शहर का नाम लिखिए या चुनिए:', ch_chcity: 'शहर बदलें',
    silver: 'अभी मैं सिर्फ़ सोने की जानकारी देती हूँ — ज्वैलर्स के 22K, 24K और 18K भाव। चाँदी जल्द आ रही है।',
    hello: 'नमस्ते! 🙏 मैं सोना हूँ। सोना ख़रीदने से जुड़ा कुछ भी पूछिए — {n} ज्वैलर्स के आज के भाव, आपका शहर, मेकिंग चार्ज, ऑफ़र या किसी भी वज़न की क़ीमत।',
    thanks: 'ख़ुशी हुई! और कुछ?',
    about: 'मैं सोना हूँ, MyGoldRates की असिस्टेंट। मैं आज के असली आँकड़ों से जवाब देती हूँ — {n} ज्वैलर्स के प्रकाशित भाव, असली प्रोडक्ट्स से मापे गए मेकिंग चार्ज, और उनकी वेबसाइट के ऑफ़र — इसलिए मैं कोई आँकड़ा अंदाज़े से नहीं बताती।',
    unknown: 'यह मैं अभी सीख रही हूँ — आपका सवाल नोट कर लिया है ताकि जल्द सही जवाब जोड़ सकें। तब तक, इनमें मैं अच्छी हूँ:',
    nodata: 'आज के आँकड़े लोड नहीं हो पाए। कृपया इंटरनेट देखकर फिर कोशिश करें।',
    no_voice: 'इस डिवाइस में {l} आवाज़ नहीं है, इसलिए मैं लिखकर जवाब दूँगी।',
    mic_denied: 'माइक बंद है। ब्राउज़र की सेटिंग में इस साइट के लिए माइक चालू करें, फिर 🎤 दबाएँ।',
    mic_none: 'मैं सुन नहीं पाई — 🎤 दबाकर फिर बोलिए।',
    rupees: 'रुपये', carat: 'कैरेट',
    say_med: 'आज {k} सोना लगभग {p} प्रति ग्राम है, {n} ज्वैलर्स का बीच का भाव। सबसे कम {b} पर है, {q}।',
    say_brand: '{b} पर आज {k} सोना {p} प्रति ग्राम है, {n} ज्वैलर्स में नंबर {r}।',
    say_city: '{c} में आज सबसे सस्ता {k} {b} पर है, {p} प्रति ग्राम।',
    say_cheap: 'आज सबसे सस्ता {k} {b} पर है, {p} प्रति ग्राम। 10 ग्राम पर सबसे महँगा ज्वैलर {q} ज़्यादा लेता है।',
    say_cmp: '{b} सस्ता है, 10 ग्राम {k} पर {p} कम।',
    say_mk_brand: '{b} पर {c} का आम मेकिंग चार्ज लगभग {p} है।',
    say_mk: '{c} पर सबसे कम मेकिंग चार्ज {b} पर है, लगभग {p}।',
    say_mk_none: '{b} का मेकिंग चार्ज हमने अभी नहीं मापा है।',
    say_off_all: 'आज {n} ज्वैलर्स के पास ऑफ़र हैं। सिर्फ़ हर डिज़ाइन पर लागू ऑफ़र गिनकर, 10 ग्राम 22 कैरेट अंगूठी सबसे कम {b} पर है: GST के साथ {p}।',
    say_off_brand: 'आज {b} की वेबसाइट पर {n} ऑफ़र हैं।',
    say_off_none: 'आज {b} की वेबसाइट पर कोई ऑफ़र नहीं है।',
    say_price: '{b} पर {w} {k} सोना GST के साथ लगभग {p} का पड़ेगा।',
    say_trend_up: 'आज {k} सोना {p} प्रति ग्राम है, पिछले दिन से {q} ज़्यादा।',
    say_trend_dn: 'आज {k} सोना {p} प्रति ग्राम है, पिछले दिन से {q} कम।',
    say_trend_same: 'आज {k} सोना {p} प्रति ग्राम है, पिछले दिन जितना ही।',
    u_g: '{n} ग्राम', u_tola: '{n} तोला', u_sov: '{n} सॉवरेन', u_kg: '{n} किलो',
    c_Ring: 'अंगूठी', c_Chain: 'चेन', c_Bangle: 'चूड़ी', c_Necklace: 'हार', c_Earrings: 'झुमके',
    c_Mangalsutra: 'मंगलसूत्र', c_Pendant: 'पेंडेंट', c_Bracelet: 'ब्रेसलेट', c_Coin: 'सिक्का',
    ch_cheap22: 'आज सबसे सस्ता 22K', ch_mycity: 'मेरे शहर में भाव', ch_tvk: 'तनिष्क या कल्याण',
    ch_bestoff: 'आज का सबसे अच्छा ऑफ़र', ch_p10chain: '10 ग्राम 22K चेन की क़ीमत', ch_k22v24: '22K और 24K में फ़र्क़?',
    ch_p10: '10 ग्राम 22K की क़ीमत', ch_afteroff: 'ऑफ़र के बाद क़ीमत', ch_mkcmp: 'मेकिंग चार्ज की तुलना',
    ch_goodmk: 'क्या मेकिंग पर 20% छूट अच्छी है?', ch_whatmk: 'मेकिंग चार्ज क्या है?', ch_alert: 'भाव अलर्ट लगाएँ',
    ch_goodtime: 'क्या अभी ख़रीदना ठीक है?', ch_rate: 'आज सोने का भाव', ch_another: 'दूसरे ज्वैलर पर यही',
    ch_bmk: '{b} मेकिंग चार्ज', ch_boff: '{b} ऑफ़र'
  };

  S.mr = {
    ui_sub: 'दागिने सहाय्यक · आजच्या खऱ्या दरांवरून उत्तरे',
    ui_ph: 'दर, ज्वेलर्स, ऑफर्सबद्दल विचारा…',
    ui_listen: 'ऐकतेय… बोला',
    ui_mic: 'बोलून विचारा',
    ui_foot: 'मोफत · लिहा किंवा बोला · प्रसिद्ध माहितीवरून उत्तरे, सल्ला नाही',
    ui_lang: 'भाषा', ui_speak: 'ऐका', ui_mute: 'बोलणे थांबवा',
    greet1: 'नमस्कार! 🙏 मी <b>सोना</b>, तुमची दागिने सहाय्यक.',
    greet2: 'सोने खरेदीबद्दल काहीही विचारा — कोणत्याही ज्वेलरचा आजचा दर, तुमच्या शहरात सर्वात स्वस्त, मजुरी (मेकिंग चार्ज), ऑफर्स किंवा कोणत्याही वजनाची किंमत. लिहा, किंवा 🎤 दाबून बोला.',
    lang_hint: 'तुमच्या भाषेत विचारा — लिहून किंवा बोलून — मी त्याच भाषेत उत्तर देईन. हिंदी किंवा इंग्रजीशिवाय दुसरी भाषा बोलायची आहे? ती एकदा निवडा:',
    ui_auto: 'आपोआप (ओळखा)',
    src: 'आजचे दर {n} ज्वेलर्सकडून, GST आधी · {d}',
    med_h: 'भारतात आजचा सोन्याचा दर, {n} ज्वेलर्सचा मधला दर:',
    med_low: 'राष्ट्रीय ज्वेलर्समध्ये सर्वात कमी 22K: <b>{b}</b>, <b>{p}/ग्रॅम</b>.',
    brand_h: '<b>{b}</b> आज:',
    brand_rank: 'आज {n} ज्वेलर्समध्ये हे <b>#{r}</b> वर आहे — {rel}.',
    rel_at: '{k} च्या बाजारातील मधल्या दराइतकेच', rel_below: '{k} च्या मधल्या दरापेक्षा {p}/ग्रॅम कमी', rel_above: '{k} च्या मधल्या दरापेक्षा {p}/ग्रॅम जास्त',
    brand_mk: 'नेहमीची मजुरी: {list}.',
    brand_off: 'त्यांच्या साइटवरील ऑफर: <b>{o}</b>.',
    brand_st: 'या राज्यांत: {s}.',
    brand_link: '{b} चे 30 दिवसांचे दर →',
    city_h: '<b>{c}</b> मध्ये आज सर्वात स्वस्त {k} ({note}):',
    city_loc: 'राष्ट्रीय ज्वेलर्स आणि {s} मधील {l} स्थानिक ज्वेलर्स', city_nat: 'राष्ट्रीय ज्वेलर्स',
    city_link: '{c} ची संपूर्ण यादी →',
    cheap_h: 'राष्ट्रीय ज्वेलर्समध्ये आज सर्वात स्वस्त {k}:',
    cheap_gap: 'सर्वात स्वस्त आणि सर्वात महाग यांत 10 ग्रॅमवर <b>{p}</b> फरक आहे — खरेदीपूर्वी नक्की पाहा.',
    cmp_h: 'आज समोरासमोर ({k}):', cmp_10: '10 ग्रॅम: {p}', cmp_mk: 'मजुरी ~{p}', cmp_nomk: 'मजुरी: मोजलेली नाही',
    cmp_win: '<b>{b}</b> चा {k} दर 10 ग्रॅमवर <b>{p}</b> ने कमी आहे. अंतिम बिल तुम्ही निवडलेल्या डिझाइनच्या मजुरीवरही अवलंबून असते.',
    mk_none: '<b>{b}</b> ची मजुरी आम्ही अजून मोजलेली नाही. यांची मोजली आहे: {list}.',
    mk_link: 'मजुरीची तुलना →',
    mk_brand_h: '<b>{b}</b> ची नेहमीची मजुरी (खऱ्या उत्पादनांचा मधला आकडा, सोन्याच्या किमतीच्या %):',
    mk_note: 'डिझाइननुसार बदलते; बिलात सर्वाधिक घासाघीस याच भागावर होऊ शकते.',
    mk_all: 'सर्व ज्वेलर्सची तुलना →',
    mk_h: '<b>{c}</b> वर सर्वात कमी मजुरी (खऱ्या उत्पादनांचा मधला आकडा):',
    mk_nocat: '<b>{c}</b>चा मेकिंग चार्ज आम्ही अजून मोजलेला नाही. <b>{r}</b>चा हा आहे:',
    mk_every: 'प्रत्येक ज्वेलर आणि प्रकार →',
    bo_ask: 'कोणत्या दागिन्यावर सर्वोत्तम ऑफर शोधू?',
    bo_h: 'आजच्या मजुरी ऑफरनंतर <b>{w}</b> 22K <b>{c}</b> ची सर्वोत्तम किंमत:',
    bo_note: 'एकूण = सोने + ऑफरनंतरची मजुरी + 3% GST. ऑफर % अंदाजे आहे; * म्हणजे “पर्यंत”, फक्त काही डिझाइनवर (कंसात सर्वोत्तम स्थिती). ज्वेलरकडून खात्री करा.',
    bo_none: '{c} ची मजुरी अजून पुरेशा ज्वेलर्सची माझ्याकडे नाही.',
    say_bo: '{w} 22K {c} साठी ऑफरनंतर {b} सर्वात स्वस्त आहे, GST सह सुमारे {p}.',
    bo_upto: 'पर्यंत',
    bo_noff: 'ऑफर नाही',
    off_none: 'आज <b>{b}</b> च्या वेबसाइटवर कोणतीही ऑफर लिहिलेली नाही.',
    off_see: 'कोणाकडे ऑफर आहे ते पाहा →',
    off_brand_h: 'आज <b>{b}</b> च्या वेबसाइटवरील ऑफर्स:',
    off_page: 'त्यांचे पान ↗', off_all: 'सर्व ज्वेलर्सच्या ऑफर्सची तुलना →',
    off_all_h: 'आज {n} ज्वेलर्सच्या स्वतःच्या वेबसाइटवर ऑफर्स आहेत (A–Z):',
    off_ring: 'फक्त प्रत्येक डिझाइनवर लागू ऑफर धरून, आज 10 ग्रॅम 22K अंगठी सर्वात कमी <b>{b}</b> येथे आहे: GST सह {p}. “अप टू” आणि निवडक डिझाइनच्या ऑफर्स प्रत्येक दागिन्यावर वेगळ्या असतात — ज्वेलरकडे खात्री करा.',
    off_every: 'प्रत्येक ऑफर, आणि तिचा खरा अर्थ →',
    price_h: 'आज {who} येथे {w} {k}:', price_who: 'सर्वात स्वस्त राष्ट्रीय ज्वेलर ({b})',
    price_gold: 'सोने ({g} ग्रॅम × {p})', price_mk: 'मजुरी (~{p}, {c})', price_typ: 'साधारण', price_total: 'एकूण',
    price_nomk: 'मजुरी समाविष्ट नाही — तुमच्या डिझाइनची मजुरी जोडा (अनेकदा 8–25%).',
    trend_none: 'अजून पुरेसा इतिहास नाही.', hist_link: 'सोन्याच्या दरांचा इतिहास →',
    trend_h: '{k} चा बाजारातील मधला दर: आज <b>{p}/ग्रॅम</b>.',
    vs1: 'कालच्या तुलनेत', vs7: '7 दिवसांपूर्वीच्या तुलनेत', vs30: '30 दिवसांपूर्वीच्या तुलनेत',
    trend_note: 'हे झालेले बदल आहेत, अंदाज नाही — उद्याचा दर कोणीही खात्रीने सांगू शकत नाही.',
    full_hist: 'संपूर्ण इतिहास →',
    alerts: 'दररोज सकाळी सर्वात स्वस्त ज्वेलर आणि आजचा दर, मोफत — आणि 22K तुमच्या दरापर्यंत उतरेल त्या दिवशी ईमेल.',
    alerts_cta: 'मोफत दैनिक अलर्ट मिळवा',
    more: 'अधिक वाचा →', guide_h: 'हे मार्गदर्शक याबद्दलच आहे: <b>{t}</b> — {d}', guide_link: 'मार्गदर्शक वाचा →',
    en_only: 'हे उत्तर सध्या इंग्रजीत आहे:', translated: 'तुमच्या डिव्हाइसवर भाषांतर केले',
    ask_city: 'तुम्ही कोणत्या शहरात आहात?',
    ch_loc: 'माझे लोकेशन वापरा', loc_wait: 'तुमचे जवळचे शहर शोधत आहे…',
    loc_fail: 'लोकेशन मिळाले नाही. तुमच्या शहराचे नाव लिहा किंवा निवडा:', ch_chcity: 'शहर बदला',
    silver: 'सध्या मी फक्त सोन्याची माहिती देते — ज्वेलर्सचे 22K, 24K आणि 18K दर. चांदी लवकरच येत आहे.',
    hello: 'नमस्कार! 🙏 मी सोना. सोने खरेदीबद्दल काहीही विचारा — {n} ज्वेलर्सचे आजचे दर, तुमचे शहर, मजुरी, ऑफर्स किंवा कोणत्याही वजनाची किंमत.',
    thanks: 'आनंद झाला! आणखी काही?',
    about: 'मी सोना, MyGoldRates ची सहाय्यक. मी आजच्या खऱ्या माहितीवरून उत्तर देते — {n} ज्वेलर्सचे प्रसिद्ध दर, खऱ्या उत्पादनांवरून मोजलेली मजुरी, आणि त्यांच्या वेबसाइटवरील ऑफर्स — त्यामुळे मी कोणताही आकडा अंदाजाने सांगत नाही.',
    unknown: 'हे मी अजून शिकतेय — तुमचा प्रश्न नोंदवला आहे, लवकरच योग्य उत्तर जोडू. तोपर्यंत, यात मी चांगली आहे:',
    nodata: 'आजची माहिती लोड झाली नाही. कृपया इंटरनेट तपासून पुन्हा प्रयत्न करा.',
    no_voice: 'या डिव्हाइसमध्ये {l} आवाज नाही, त्यामुळे मी लिहून उत्तर देईन.',
    mic_denied: 'माइक बंद आहे. ब्राउझरच्या सेटिंगमध्ये या साइटसाठी माइक सुरू करा, मग पुन्हा 🎤 दाबा.',
    mic_none: 'मला ऐकू आले नाही — 🎤 दाबून पुन्हा बोला.',
    rupees: 'रुपये', carat: 'कॅरेट',
    say_med: 'आज {k} सोने साधारण {p} प्रति ग्रॅम आहे, {n} ज्वेलर्सचा मधला दर. सर्वात कमी {b} येथे, {q}.',
    say_brand: '{b} येथे आज {k} सोने {p} प्रति ग्रॅम आहे, {n} ज्वेलर्समध्ये क्रमांक {r}.',
    say_city: '{c} मध्ये आज सर्वात स्वस्त {k} {b} येथे आहे, {p} प्रति ग्रॅम.',
    say_cheap: 'आज सर्वात स्वस्त {k} {b} येथे आहे, {p} प्रति ग्रॅम. 10 ग्रॅमवर सर्वात महाग ज्वेलर {q} जास्त घेतो.',
    say_cmp: '{b} स्वस्त आहे, 10 ग्रॅम {k} वर {p} ने कमी.',
    say_mk_brand: '{b} येथे {c} ची नेहमीची मजुरी साधारण {p} आहे.',
    say_mk: '{c} वर सर्वात कमी मजुरी {b} येथे आहे, साधारण {p}.',
    say_mk_none: '{b} ची मजुरी आम्ही अजून मोजलेली नाही.',
    say_off_all: 'आज {n} ज्वेलर्सकडे ऑफर्स आहेत. फक्त प्रत्येक डिझाइनवर लागू ऑफर धरून, 10 ग्रॅम 22 कॅरेट अंगठी सर्वात कमी {b} येथे आहे: GST सह {p}.',
    say_off_brand: 'आज {b} च्या वेबसाइटवर {n} ऑफर्स आहेत.',
    say_off_none: 'आज {b} च्या वेबसाइटवर कोणतीही ऑफर नाही.',
    say_price: '{b} येथे {w} {k} सोने GST सह साधारण {p} ला पडेल.',
    say_trend_up: 'आज {k} सोने {p} प्रति ग्रॅम आहे, कालपेक्षा {q} जास्त.',
    say_trend_dn: 'आज {k} सोने {p} प्रति ग्रॅम आहे, कालपेक्षा {q} कमी.',
    say_trend_same: 'आज {k} सोने {p} प्रति ग्रॅम आहे, कालइतकेच.',
    u_g: '{n} ग्रॅम', u_tola: '{n} तोळे', u_sov: '{n} सॉव्हरिन', u_kg: '{n} किलो',
    c_Ring: 'अंगठी', c_Chain: 'चेन', c_Bangle: 'बांगडी', c_Necklace: 'हार', c_Earrings: 'कानातले',
    c_Mangalsutra: 'मंगळसूत्र', c_Pendant: 'पेंडंट', c_Bracelet: 'ब्रेसलेट', c_Coin: 'नाणे',
    ch_cheap22: 'आज सर्वात स्वस्त 22K', ch_mycity: 'माझ्या शहरातील दर', ch_tvk: 'तनिष्क की कल्याण',
    ch_bestoff: 'आजची सर्वोत्तम ऑफर', ch_p10chain: '10 ग्रॅम 22K चेनची किंमत', ch_k22v24: '22K आणि 24K मध्ये फरक?',
    ch_p10: '10 ग्रॅम 22K ची किंमत', ch_afteroff: 'ऑफरनंतरची किंमत', ch_mkcmp: 'मजुरीची तुलना',
    ch_goodmk: 'मजुरीवर 20% सूट चांगली आहे का?', ch_whatmk: 'मजुरी म्हणजे काय?', ch_alert: 'दर अलर्ट लावा',
    ch_goodtime: 'आता खरेदी करावी का?', ch_rate: 'आजचा सोन्याचा दर', ch_another: 'दुसऱ्या ज्वेलरकडे हेच',
    ch_bmk: '{b} मजुरी', ch_boff: '{b} ऑफर्स'
  };

  S.gu = {
    ui_sub: 'જ્વેલરી સહાયક · આજના સાચા ભાવ પરથી જવાબ',
    ui_ph: 'ભાવ, જ્વેલર્સ, ઑફર વિશે પૂછો…',
    ui_listen: 'સાંભળું છું… બોલો',
    ui_mic: 'બોલીને પૂછો',
    ui_foot: 'મફત · લખો કે બોલો · પ્રકાશિત માહિતી પરથી જવાબ, સલાહ નહીં',
    ui_lang: 'ભાષા', ui_speak: 'સાંભળો', ui_mute: 'બોલવાનું બંધ કરો',
    greet1: 'નમસ્તે! 🙏 હું <b>સોના</b> છું, તમારી જ્વેલરી સહાયક.',
    greet2: 'સોનું ખરીદવા વિશે કંઈ પણ પૂછો — કોઈ પણ જ્વેલરનો આજનો ભાવ, તમારા શહેરમાં સૌથી સસ્તું, ઘડામણ (મેકિંગ ચાર્જ), ઑફર કે કોઈ પણ વજનની કિંમત. લખો, અથવા 🎤 દબાવીને બોલો.',
    lang_hint: 'તમારી ભાષામાં પૂછો — લખીને કે બોલીને — હું એ જ ભાષામાં જવાબ આપીશ. હિન્દી કે અંગ્રેજી સિવાયની ભાષા બોલવી છે? તેને એક વાર પસંદ કરો:',
    ui_auto: 'આપમેળે (ઓળખો)',
    src: 'આજના ભાવ {n} જ્વેલર્સના, GST પહેલાં · {d}',
    med_h: 'ભારતમાં આજનો સોનાનો ભાવ, {n} જ્વેલર્સનો વચ્ચેનો ભાવ:',
    med_low: 'રાષ્ટ્રીય જ્વેલર્સમાં સૌથી ઓછો 22K: <b>{b}</b>, <b>{p}/ગ્રામ</b>.',
    brand_h: '<b>{b}</b> આજે:',
    brand_rank: 'આજે {n} જ્વેલર્સમાં આ <b>#{r}</b> પર છે — {rel}.',
    rel_at: '{k} ના બજારના વચ્ચેના ભાવ જેટલો જ', rel_below: '{k} ના વચ્ચેના ભાવ કરતાં {p}/ગ્રામ ઓછો', rel_above: '{k} ના વચ્ચેના ભાવ કરતાં {p}/ગ્રામ વધુ',
    brand_mk: 'સામાન્ય ઘડામણ: {list}.',
    brand_off: 'તેમની સાઇટ પર ઑફર: <b>{o}</b>.',
    brand_st: 'આ રાજ્યોમાં: {s}.',
    brand_link: '{b} ના 30 દિવસના ભાવ →',
    city_h: '<b>{c}</b> માં આજે સૌથી સસ્તું {k} ({note}):',
    city_loc: 'રાષ્ટ્રીય જ્વેલર્સ અને {s} ના {l} સ્થાનિક જ્વેલર્સ', city_nat: 'રાષ્ટ્રીય જ્વેલર્સ',
    city_link: '{c} ની પૂરી યાદી →',
    cheap_h: 'રાષ્ટ્રીય જ્વેલર્સમાં આજે સૌથી સસ્તું {k}:',
    cheap_gap: 'સૌથી સસ્તા અને સૌથી મોંઘા વચ્ચે 10 ગ્રામ પર <b>{p}</b> નો ફરક છે — ખરીદતા પહેલાં જરૂર જુઓ.',
    cmp_h: 'આજે સામસામે ({k}):', cmp_10: '10 ગ્રામ: {p}', cmp_mk: 'ઘડામણ ~{p}', cmp_nomk: 'ઘડામણ: માપ્યું નથી',
    cmp_win: '<b>{b}</b> નો {k} ભાવ 10 ગ્રામ પર <b>{p}</b> ઓછો છે. અંતિમ બિલ તમે પસંદ કરેલી ડિઝાઇનના ઘડામણ પર પણ આધાર રાખે છે.',
    mk_none: '<b>{b}</b> નું ઘડામણ અમે હજી માપ્યું નથી. આમનું માપ્યું છે: {list}.',
    mk_link: 'ઘડામણની સરખામણી →',
    mk_brand_h: '<b>{b}</b> નું સામાન્ય ઘડામણ (સાચાં ઉત્પાદનોનો વચ્ચેનો આંકડો, સોનાની કિંમતના %):',
    mk_note: 'ડિઝાઇન મુજબ બદલાય છે; બિલમાં સૌથી વધુ ભાવતાલ આના પર થઈ શકે.',
    mk_all: 'બધા જ્વેલર્સની સરખામણી →',
    mk_h: '<b>{c}</b> પર સૌથી ઓછું ઘડામણ (સાચાં ઉત્પાદનોનો વચ્ચેનો આંકડો):',
    mk_nocat: '<b>{c}</b>નો મેકિંગ ચાર્જ અમે હજી માપ્યો નથી. <b>{r}</b>નો આ છે:',
    mk_every: 'દરેક જ્વેલર અને પ્રકાર →',
    bo_ask: 'કયા દાગીના પર શ્રેષ્ઠ ઑફર શોધું?',
    bo_h: 'આજની ઘડામણ ઑફર પછી <b>{w}</b> 22K <b>{c}</b> ની શ્રેષ્ઠ કિંમત:',
    bo_note: 'કુલ = સોનું + ઑફર પછી ઘડામણ + 3% GST. ઑફર % અંદાજિત છે; * એટલે “સુધી”, ફક્ત કેટલીક ડિઝાઇન પર (કૌંસમાં શ્રેષ્ઠ સ્થિતિ). જ્વેલર પાસે ખાતરી કરો.',
    bo_none: '{c} ની ઘડામણ હજી પૂરતા જ્વેલર્સની મારી પાસે નથી.',
    say_bo: '{w} 22K {c} માટે ઑફર પછી {b} સૌથી સસ્તું છે, GST સાથે આશરે {p}.',
    bo_upto: 'સુધી',
    bo_noff: 'કોઈ ઑફર નથી',
    off_none: 'આજે <b>{b}</b> ની વેબસાઇટ પર કોઈ ઑફર લખેલી નથી.',
    off_see: 'કોની પાસે ઑફર છે તે જુઓ →',
    off_brand_h: 'આજે <b>{b}</b> ની વેબસાઇટ પરની ઑફર:',
    off_page: 'તેમનું પેજ ↗', off_all: 'બધા જ્વેલર્સની ઑફરની સરખામણી →',
    off_all_h: 'આજે {n} જ્વેલર્સની પોતાની વેબસાઇટ પર ઑફર છે (A–Z):',
    off_ring: 'ફક્ત દરેક ડિઝાઇન પર લાગુ ઑફર ગણીને, આજે 10 ગ્રામ 22K વીંટી સૌથી ઓછી <b>{b}</b> પર છે: GST સાથે {p}. “અપ ટુ” અને પસંદગીની ડિઝાઇનની ઑફર દરેક દાગીના પર અલગ હોય છે — જ્વેલર પાસે ખાતરી કરો.',
    off_every: 'દરેક ઑફર, અને તેનો સાચો અર્થ →',
    price_h: 'આજે {who} પર {w} {k}:', price_who: 'સૌથી સસ્તો રાષ્ટ્રીય જ્વેલર ({b})',
    price_gold: 'સોનું ({g} ગ્રામ × {p})', price_mk: 'ઘડામણ (~{p}, {c})', price_typ: 'સામાન્ય', price_total: 'કુલ',
    price_nomk: 'ઘડામણ સામેલ નથી — તમારી ડિઝાઇનનું ઘડામણ ઉમેરો (ઘણી વાર 8–25%).',
    trend_none: 'હજી પૂરતો ઇતિહાસ નથી.', hist_link: 'સોનાના ભાવનો ઇતિહાસ →',
    trend_h: '{k} નો બજારનો વચ્ચેનો ભાવ: આજે <b>{p}/ગ્રામ</b>.',
    vs1: 'ગઈકાલની સરખામણીએ', vs7: '7 દિવસ પહેલાંની સરખામણીએ', vs30: '30 દિવસ પહેલાંની સરખામણીએ',
    trend_note: 'આ થઈ ગયેલા ફેરફાર છે, આગાહી નહીં — આવતીકાલનો ભાવ કોઈ ખાતરીથી કહી શકે નહીં.',
    full_hist: 'પૂરો ઇતિહાસ →',
    alerts: 'દરરોજ સવારે સૌથી સસ્તો જ્વેલર અને આજનો ભાવ, મફત — અને જે દિવસે 22K તમારા ભાવ સુધી ઘટે તે દિવસે ઇમેઇલ.',
    alerts_cta: 'મફત દૈનિક અલર્ટ મેળવો',
    more: 'વધુ વાંચો →', guide_h: 'આ માર્ગદર્શિકા આ વિશે જ છે: <b>{t}</b> — {d}', guide_link: 'માર્ગદર્શિકા વાંચો →',
    en_only: 'આ જવાબ હાલ અંગ્રેજીમાં છે:', translated: 'તમારા ડિવાઇસ પર અનુવાદ કર્યો',
    ask_city: 'તમે કયા શહેરમાં છો?',
    ch_loc: 'મારું લોકેશન વાપરો', loc_wait: 'તમારું નજીકનું શહેર શોધી રહી છું…',
    loc_fail: 'લોકેશન ન મળ્યું. તમારા શહેરનું નામ લખો અથવા પસંદ કરો:', ch_chcity: 'શહેર બદલો',
    silver: 'હાલ હું ફક્ત સોનાની માહિતી આપું છું — જ્વેલર્સના 22K, 24K અને 18K ભાવ. ચાંદી જલદી આવે છે.',
    hello: 'નમસ્તે! 🙏 હું સોના છું. સોનું ખરીદવા વિશે કંઈ પણ પૂછો — {n} જ્વેલર્સના આજના ભાવ, તમારું શહેર, ઘડામણ, ઑફર કે કોઈ પણ વજનની કિંમત.',
    thanks: 'આનંદ થયો! બીજું કંઈ?',
    about: 'હું સોના છું, MyGoldRates ની સહાયક. હું આજની સાચી માહિતી પરથી જવાબ આપું છું — {n} જ્વેલર્સના પ્રકાશિત ભાવ, સાચાં ઉત્પાદનો પરથી માપેલું ઘડામણ, અને તેમની વેબસાઇટની ઑફર — એટલે હું કોઈ આંકડો અંદાજથી કહેતી નથી.',
    unknown: 'આ હું હજી શીખું છું — તમારો પ્રશ્ન નોંધી લીધો છે, જલદી સાચો જવાબ ઉમેરીશું. ત્યાં સુધી, આમાં હું સારી છું:',
    nodata: 'આજની માહિતી લોડ ન થઈ. કૃપા કરીને ઇન્ટરનેટ તપાસીને ફરી પ્રયત્ન કરો.',
    no_voice: 'આ ડિવાઇસમાં {l} અવાજ નથી, એટલે હું લખીને જવાબ આપીશ.',
    mic_denied: 'માઇક બંધ છે. બ્રાઉઝરના સેટિંગમાં આ સાઇટ માટે માઇક ચાલુ કરો, પછી ફરી 🎤 દબાવો.',
    mic_none: 'હું સાંભળી ન શકી — 🎤 દબાવીને ફરી બોલો.',
    rupees: 'રૂપિયા', carat: 'કેરેટ',
    say_med: 'આજે {k} સોનું લગભગ {p} પ્રતિ ગ્રામ છે, {n} જ્વેલર્સનો વચ્ચેનો ભાવ. સૌથી ઓછો {b} પર, {q}.',
    say_brand: '{b} પર આજે {k} સોનું {p} પ્રતિ ગ્રામ છે, {n} જ્વેલર્સમાં નંબર {r}.',
    say_city: '{c} માં આજે સૌથી સસ્તું {k} {b} પર છે, {p} પ્રતિ ગ્રામ.',
    say_cheap: 'આજે સૌથી સસ્તું {k} {b} પર છે, {p} પ્રતિ ગ્રામ. 10 ગ્રામ પર સૌથી મોંઘો જ્વેલર {q} વધુ લે છે.',
    say_cmp: '{b} સસ્તું છે, 10 ગ્રામ {k} પર {p} ઓછું.',
    say_mk_brand: '{b} પર {c} નું સામાન્ય ઘડામણ લગભગ {p} છે.',
    say_mk: '{c} પર સૌથી ઓછું ઘડામણ {b} પર છે, લગભગ {p}.',
    say_mk_none: '{b} નું ઘડામણ અમે હજી માપ્યું નથી.',
    say_off_all: 'આજે {n} જ્વેલર્સ પાસે ઑફર છે. ફક્ત દરેક ડિઝાઇન પર લાગુ ઑફર ગણીને, 10 ગ્રામ 22 કેરેટ વીંટી સૌથી ઓછી {b} પર છે: GST સાથે {p}.',
    say_off_brand: 'આજે {b} ની વેબસાઇટ પર {n} ઑફર છે.',
    say_off_none: 'આજે {b} ની વેબસાઇટ પર કોઈ ઑફર નથી.',
    say_price: '{b} પર {w} {k} સોનું GST સાથે લગભગ {p} થશે.',
    say_trend_up: 'આજે {k} સોનું {p} પ્રતિ ગ્રામ છે, ગઈકાલ કરતાં {q} વધુ.',
    say_trend_dn: 'આજે {k} સોનું {p} પ્રતિ ગ્રામ છે, ગઈકાલ કરતાં {q} ઓછું.',
    say_trend_same: 'આજે {k} સોનું {p} પ્રતિ ગ્રામ છે, ગઈકાલ જેટલું જ.',
    u_g: '{n} ગ્રામ', u_tola: '{n} તોલા', u_sov: '{n} સોવરિન', u_kg: '{n} કિલો',
    c_Ring: 'વીંટી', c_Chain: 'ચેન', c_Bangle: 'બંગડી', c_Necklace: 'હાર', c_Earrings: 'બુટ્ટી',
    c_Mangalsutra: 'મંગળસૂત્ર', c_Pendant: 'પેન્ડન્ટ', c_Bracelet: 'બ્રેસલેટ', c_Coin: 'સિક્કો',
    ch_cheap22: 'આજે સૌથી સસ્તું 22K', ch_mycity: 'મારા શહેરમાં ભાવ', ch_tvk: 'તનિષ્ક કે કલ્યાણ',
    ch_bestoff: 'આજની શ્રેષ્ઠ ઑફર', ch_p10chain: '10 ગ્રામ 22K ચેનની કિંમત', ch_k22v24: '22K અને 24K માં ફરક?',
    ch_p10: '10 ગ્રામ 22K ની કિંમત', ch_afteroff: 'ઑફર પછીની કિંમત', ch_mkcmp: 'ઘડામણની સરખામણી',
    ch_goodmk: 'ઘડામણ પર 20% છૂટ સારી છે?', ch_whatmk: 'ઘડામણ એટલે શું?', ch_alert: 'ભાવ અલર્ટ મૂકો',
    ch_goodtime: 'અત્યારે ખરીદવું યોગ્ય છે?', ch_rate: 'આજનો સોનાનો ભાવ', ch_another: 'બીજા જ્વેલર પર આ જ',
    ch_bmk: '{b} ઘડામણ', ch_boff: '{b} ઑફર'
  };

  S.pa = {
    ui_sub: 'ਗਹਿਣਿਆਂ ਦੀ ਸਹਾਇਕ · ਅੱਜ ਦੇ ਅਸਲ ਭਾਅ ਤੋਂ ਜਵਾਬ',
    ui_ph: 'ਭਾਅ, ਜਿਊਲਰ, ਆਫ਼ਰ ਬਾਰੇ ਪੁੱਛੋ…',
    ui_listen: 'ਸੁਣ ਰਹੀ ਹਾਂ… ਬੋਲੋ',
    ui_mic: 'ਬੋਲ ਕੇ ਪੁੱਛੋ',
    ui_foot: 'ਮੁਫ਼ਤ · ਲਿਖੋ ਜਾਂ ਬੋਲੋ · ਛਪੇ ਅੰਕੜਿਆਂ ਤੋਂ ਜਵਾਬ, ਸਲਾਹ ਨਹੀਂ',
    ui_lang: 'ਭਾਸ਼ਾ', ui_speak: 'ਸੁਣੋ', ui_mute: 'ਬੋਲਣਾ ਬੰਦ ਕਰੋ',
    greet1: 'ਸਤ ਸ੍ਰੀ ਅਕਾਲ! 🙏 ਮੈਂ <b>ਸੋਨਾ</b> ਹਾਂ, ਤੁਹਾਡੀ ਗਹਿਣਿਆਂ ਦੀ ਸਹਾਇਕ।',
    greet2: 'ਸੋਨਾ ਖ਼ਰੀਦਣ ਬਾਰੇ ਕੁਝ ਵੀ ਪੁੱਛੋ — ਕਿਸੇ ਵੀ ਜਿਊਲਰ ਦਾ ਅੱਜ ਦਾ ਭਾਅ, ਤੁਹਾਡੇ ਸ਼ਹਿਰ ਵਿੱਚ ਸਭ ਤੋਂ ਸਸਤਾ, ਘੜਾਈ (ਮੇਕਿੰਗ ਚਾਰਜ), ਆਫ਼ਰ ਜਾਂ ਕਿਸੇ ਵੀ ਭਾਰ ਦੀ ਕੀਮਤ। ਲਿਖੋ, ਜਾਂ 🎤 ਦਬਾ ਕੇ ਬੋਲੋ।',
    lang_hint: 'ਆਪਣੀ ਭਾਸ਼ਾ ਵਿੱਚ ਪੁੱਛੋ — ਲਿਖ ਕੇ ਜਾਂ ਬੋਲ ਕੇ — ਮੈਂ ਉਸੇ ਭਾਸ਼ਾ ਵਿੱਚ ਜਵਾਬ ਦਿਆਂਗੀ। ਹਿੰਦੀ ਜਾਂ ਅੰਗਰੇਜ਼ੀ ਤੋਂ ਇਲਾਵਾ ਕੋਈ ਹੋਰ ਭਾਸ਼ਾ ਬੋਲਣੀ ਹੈ? ਉਸਨੂੰ ਇੱਕ ਵਾਰ ਚੁਣੋ:',
    ui_auto: 'ਆਪਣੇ-ਆਪ (ਪਛਾਣੋ)',
    src: 'ਅੱਜ ਦੇ ਭਾਅ {n} ਜਿਊਲਰਾਂ ਤੋਂ, GST ਤੋਂ ਪਹਿਲਾਂ · {d}',
    med_h: 'ਭਾਰਤ ਵਿੱਚ ਅੱਜ ਸੋਨੇ ਦਾ ਭਾਅ, {n} ਜਿਊਲਰਾਂ ਦਾ ਵਿਚਕਾਰਲਾ ਭਾਅ:',
    med_low: 'ਕੌਮੀ ਜਿਊਲਰਾਂ ਵਿੱਚ ਸਭ ਤੋਂ ਘੱਟ 22K: <b>{b}</b>, <b>{p}/ਗ੍ਰਾਮ</b>।',
    brand_h: '<b>{b}</b> ਅੱਜ:',
    brand_rank: 'ਅੱਜ {n} ਜਿਊਲਰਾਂ ਵਿੱਚ ਇਹ <b>#{r}</b> ਉੱਤੇ ਹੈ — {rel}।',
    rel_at: '{k} ਦੇ ਬਾਜ਼ਾਰ ਦੇ ਵਿਚਕਾਰਲੇ ਭਾਅ ਦੇ ਬਰਾਬਰ', rel_below: '{k} ਦੇ ਵਿਚਕਾਰਲੇ ਭਾਅ ਤੋਂ {p}/ਗ੍ਰਾਮ ਘੱਟ', rel_above: '{k} ਦੇ ਵਿਚਕਾਰਲੇ ਭਾਅ ਤੋਂ {p}/ਗ੍ਰਾਮ ਵੱਧ',
    brand_mk: 'ਆਮ ਘੜਾਈ: {list}।',
    brand_off: 'ਉਹਨਾਂ ਦੀ ਸਾਈਟ ’ਤੇ ਆਫ਼ਰ: <b>{o}</b>।',
    brand_st: 'ਇਹਨਾਂ ਰਾਜਾਂ ਵਿੱਚ: {s}।',
    brand_link: '{b} ਦੇ 30 ਦਿਨਾਂ ਦੇ ਭਾਅ →',
    city_h: '<b>{c}</b> ਵਿੱਚ ਅੱਜ ਸਭ ਤੋਂ ਸਸਤਾ {k} ({note}):',
    city_loc: 'ਕੌਮੀ ਜਿਊਲਰ ਅਤੇ {s} ਦੇ {l} ਸਥਾਨਕ ਜਿਊਲਰ', city_nat: 'ਕੌਮੀ ਜਿਊਲਰ',
    city_link: '{c} ਦੀ ਪੂਰੀ ਸੂਚੀ →',
    cheap_h: 'ਕੌਮੀ ਜਿਊਲਰਾਂ ਵਿੱਚ ਅੱਜ ਸਭ ਤੋਂ ਸਸਤਾ {k}:',
    cheap_gap: 'ਸਭ ਤੋਂ ਸਸਤੇ ਅਤੇ ਸਭ ਤੋਂ ਮਹਿੰਗੇ ਵਿੱਚ 10 ਗ੍ਰਾਮ ’ਤੇ <b>{p}</b> ਦਾ ਫ਼ਰਕ ਹੈ — ਖ਼ਰੀਦਣ ਤੋਂ ਪਹਿਲਾਂ ਜ਼ਰੂਰ ਵੇਖੋ।',
    cmp_h: 'ਅੱਜ ਆਹਮੋ-ਸਾਹਮਣੇ ({k}):', cmp_10: '10 ਗ੍ਰਾਮ: {p}', cmp_mk: 'ਘੜਾਈ ~{p}', cmp_nomk: 'ਘੜਾਈ: ਮਾਪੀ ਨਹੀਂ',
    cmp_win: '<b>{b}</b> ਦਾ {k} ਭਾਅ 10 ਗ੍ਰਾਮ ’ਤੇ <b>{p}</b> ਘੱਟ ਹੈ। ਆਖ਼ਰੀ ਬਿੱਲ ਤੁਹਾਡੇ ਚੁਣੇ ਡਿਜ਼ਾਈਨ ਦੀ ਘੜਾਈ ’ਤੇ ਵੀ ਨਿਰਭਰ ਕਰਦਾ ਹੈ।',
    mk_none: '<b>{b}</b> ਦੀ ਘੜਾਈ ਅਸੀਂ ਅਜੇ ਨਹੀਂ ਮਾਪੀ। ਇਹਨਾਂ ਦੀ ਮਾਪੀ ਹੈ: {list}।',
    mk_link: 'ਘੜਾਈ ਦੀ ਤੁਲਨਾ →',
    mk_brand_h: '<b>{b}</b> ਦੀ ਆਮ ਘੜਾਈ (ਅਸਲ ਉਤਪਾਦਾਂ ਦਾ ਵਿਚਕਾਰਲਾ ਅੰਕੜਾ, ਸੋਨੇ ਦੀ ਕੀਮਤ ਦਾ %):',
    mk_note: 'ਡਿਜ਼ਾਈਨ ਮੁਤਾਬਕ ਬਦਲਦੀ ਹੈ; ਬਿੱਲ ਵਿੱਚ ਸਭ ਤੋਂ ਵੱਧ ਮੋਲ-ਭਾਅ ਇਸੇ ’ਤੇ ਹੋ ਸਕਦਾ ਹੈ।',
    mk_all: 'ਸਾਰੇ ਜਿਊਲਰਾਂ ਦੀ ਤੁਲਨਾ →',
    mk_h: '<b>{c}</b> ’ਤੇ ਸਭ ਤੋਂ ਘੱਟ ਘੜਾਈ (ਅਸਲ ਉਤਪਾਦਾਂ ਦਾ ਵਿਚਕਾਰਲਾ ਅੰਕੜਾ):',
    mk_nocat: '<b>{c}</b> ਦਾ ਮੇਕਿੰਗ ਚਾਰਜ ਅਸੀਂ ਅਜੇ ਨਹੀਂ ਮਾਪਿਆ। <b>{r}</b> ਦਾ ਇਹ ਹੈ:',
    mk_every: 'ਹਰ ਜਿਊਲਰ ਅਤੇ ਹਰ ਕਿਸਮ →',
    bo_ask: 'ਕਿਸ ਗਹਿਣੇ ’ਤੇ ਸਭ ਤੋਂ ਵਧੀਆ ਆਫ਼ਰ ਲੱਭਾਂ?',
    bo_h: 'ਅੱਜ ਦੀਆਂ ਘੜਾਈ ਆਫ਼ਰਾਂ ਤੋਂ ਬਾਅਦ <b>{w}</b> 22K <b>{c}</b> ਦੀ ਸਭ ਤੋਂ ਵਧੀਆ ਕੀਮਤ:',
    bo_note: 'ਕੁੱਲ = ਸੋਨਾ + ਆਫ਼ਰ ਤੋਂ ਬਾਅਦ ਘੜਾਈ + 3% GST. ਆਫ਼ਰ % ਅੰਦਾਜ਼ਨ ਹੈ; * ਮਤਲਬ “ਤੱਕ”, ਸਿਰਫ਼ ਕੁਝ ਡਿਜ਼ਾਈਨਾਂ ’ਤੇ (ਬਰੈਕਟ ਵਿੱਚ ਸਭ ਤੋਂ ਵਧੀਆ ਹਾਲਤ). ਜਿਊਲਰ ਤੋਂ ਪੱਕਾ ਕਰੋ.',
    bo_none: '{c} ਦੀ ਘੜਾਈ ਅਜੇ ਕਾਫ਼ੀ ਜਿਊਲਰਾਂ ਦੀ ਮੇਰੇ ਕੋਲ ਨਹੀਂ ਹੈ.',
    say_bo: '{w} 22K {c} ਲਈ ਆਫ਼ਰ ਤੋਂ ਬਾਅਦ {b} ਸਭ ਤੋਂ ਸਸਤਾ ਹੈ, GST ਸਮੇਤ ਲਗਭਗ {p}.',
    bo_upto: 'ਤੱਕ',
    bo_noff: 'ਕੋਈ ਆਫ਼ਰ ਨਹੀਂ',
    off_none: 'ਅੱਜ <b>{b}</b> ਦੀ ਵੈੱਬਸਾਈਟ ’ਤੇ ਕੋਈ ਆਫ਼ਰ ਲਿਖੀ ਨਹੀਂ ਹੈ।',
    off_see: 'ਵੇਖੋ ਕਿਸ ਕੋਲ ਆਫ਼ਰ ਹੈ →',
    off_brand_h: 'ਅੱਜ <b>{b}</b> ਦੀ ਵੈੱਬਸਾਈਟ ’ਤੇ ਆਫ਼ਰ:',
    off_page: 'ਉਹਨਾਂ ਦਾ ਪੰਨਾ ↗', off_all: 'ਸਾਰੇ ਜਿਊਲਰਾਂ ਦੀਆਂ ਆਫ਼ਰਾਂ ਦੀ ਤੁਲਨਾ →',
    off_all_h: 'ਅੱਜ {n} ਜਿਊਲਰਾਂ ਦੀਆਂ ਆਪਣੀਆਂ ਵੈੱਬਸਾਈਟਾਂ ’ਤੇ ਆਫ਼ਰਾਂ ਹਨ (A–Z):',
    off_ring: 'ਸਿਰਫ਼ ਹਰ ਡਿਜ਼ਾਈਨ ’ਤੇ ਲਾਗੂ ਆਫ਼ਰ ਗਿਣ ਕੇ, ਅੱਜ 10 ਗ੍ਰਾਮ 22K ਮੁੰਦਰੀ ਸਭ ਤੋਂ ਘੱਟ <b>{b}</b> ’ਤੇ ਹੈ: GST ਸਮੇਤ {p}। “ਅੱਪ ਟੂ” ਅਤੇ ਚੁਣੇ ਡਿਜ਼ਾਈਨਾਂ ਵਾਲੀਆਂ ਆਫ਼ਰਾਂ ਹਰ ਗਹਿਣੇ ’ਤੇ ਵੱਖਰੀਆਂ ਹੁੰਦੀਆਂ ਹਨ — ਜਿਊਲਰ ਤੋਂ ਪੱਕਾ ਕਰ ਲਓ।',
    off_every: 'ਹਰ ਆਫ਼ਰ, ਅਤੇ ਉਸਦਾ ਅਸਲ ਮਤਲਬ →',
    price_h: 'ਅੱਜ {who} ’ਤੇ {w} {k}:', price_who: 'ਸਭ ਤੋਂ ਸਸਤਾ ਕੌਮੀ ਜਿਊਲਰ ({b})',
    price_gold: 'ਸੋਨਾ ({g} ਗ੍ਰਾਮ × {p})', price_mk: 'ਘੜਾਈ (~{p}, {c})', price_typ: 'ਆਮ ਤੌਰ ’ਤੇ', price_total: 'ਕੁੱਲ',
    price_nomk: 'ਘੜਾਈ ਸ਼ਾਮਲ ਨਹੀਂ — ਆਪਣੇ ਡਿਜ਼ਾਈਨ ਦੀ ਘੜਾਈ ਜੋੜੋ (ਅਕਸਰ 8–25%)।',
    trend_none: 'ਅਜੇ ਕਾਫ਼ੀ ਇਤਿਹਾਸ ਨਹੀਂ ਹੈ।', hist_link: 'ਸੋਨੇ ਦੇ ਭਾਅ ਦਾ ਇਤਿਹਾਸ →',
    trend_h: '{k} ਦਾ ਬਾਜ਼ਾਰ ਦਾ ਵਿਚਕਾਰਲਾ ਭਾਅ: ਅੱਜ <b>{p}/ਗ੍ਰਾਮ</b>।',
    vs1: 'ਪਿਛਲੇ ਦਿਨ ਨਾਲੋਂ', vs7: '7 ਦਿਨ ਪਹਿਲਾਂ ਨਾਲੋਂ', vs30: '30 ਦਿਨ ਪਹਿਲਾਂ ਨਾਲੋਂ',
    trend_note: 'ਇਹ ਬੀਤੇ ਬਦਲਾਅ ਹਨ, ਭਵਿੱਖਬਾਣੀ ਨਹੀਂ — ਕੱਲ੍ਹ ਦਾ ਭਾਅ ਕੋਈ ਪੱਕਾ ਨਹੀਂ ਦੱਸ ਸਕਦਾ।',
    full_hist: 'ਪੂਰਾ ਇਤਿਹਾਸ →',
    alerts: 'ਹਰ ਸਵੇਰ ਸਭ ਤੋਂ ਸਸਤਾ ਜਿਊਲਰ ਅਤੇ ਅੱਜ ਦਾ ਭਾਅ, ਮੁਫ਼ਤ — ਅਤੇ ਜਿਸ ਦਿਨ 22K ਤੁਹਾਡੇ ਭਾਅ ਤੱਕ ਡਿੱਗੇ, ਉਸ ਦਿਨ ਈਮੇਲ।',
    alerts_cta: 'ਮੁਫ਼ਤ ਰੋਜ਼ਾਨਾ ਅਲਰਟ ਲਓ',
    more: 'ਹੋਰ ਪੜ੍ਹੋ →', guide_h: 'ਇਹ ਗਾਈਡ ਇਸੇ ਬਾਰੇ ਹੈ: <b>{t}</b> — {d}', guide_link: 'ਗਾਈਡ ਪੜ੍ਹੋ →',
    en_only: 'ਇਹ ਜਵਾਬ ਅਜੇ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਹੈ:', translated: 'ਤੁਹਾਡੇ ਡਿਵਾਈਸ ’ਤੇ ਅਨੁਵਾਦ ਕੀਤਾ',
    ask_city: 'ਤੁਸੀਂ ਕਿਹੜੇ ਸ਼ਹਿਰ ਵਿੱਚ ਹੋ?',
    ch_loc: 'ਮੇਰੀ ਲੋਕੇਸ਼ਨ ਵਰਤੋ', loc_wait: 'ਤੁਹਾਡਾ ਨੇੜਲਾ ਸ਼ਹਿਰ ਲੱਭ ਰਹੀ ਹਾਂ…',
    loc_fail: 'ਲੋਕੇਸ਼ਨ ਨਹੀਂ ਮਿਲੀ। ਆਪਣੇ ਸ਼ਹਿਰ ਦਾ ਨਾਮ ਲਿਖੋ ਜਾਂ ਚੁਣੋ:', ch_chcity: 'ਸ਼ਹਿਰ ਬਦਲੋ',
    silver: 'ਅਜੇ ਮੈਂ ਸਿਰਫ਼ ਸੋਨੇ ਦੀ ਜਾਣਕਾਰੀ ਦਿੰਦੀ ਹਾਂ — ਜਿਊਲਰਾਂ ਦੇ 22K, 24K ਅਤੇ 18K ਭਾਅ। ਚਾਂਦੀ ਜਲਦੀ ਆ ਰਹੀ ਹੈ।',
    hello: 'ਸਤ ਸ੍ਰੀ ਅਕਾਲ! 🙏 ਮੈਂ ਸੋਨਾ ਹਾਂ। ਸੋਨਾ ਖ਼ਰੀਦਣ ਬਾਰੇ ਕੁਝ ਵੀ ਪੁੱਛੋ — {n} ਜਿਊਲਰਾਂ ਦੇ ਅੱਜ ਦੇ ਭਾਅ, ਤੁਹਾਡਾ ਸ਼ਹਿਰ, ਘੜਾਈ, ਆਫ਼ਰ ਜਾਂ ਕਿਸੇ ਵੀ ਭਾਰ ਦੀ ਕੀਮਤ।',
    thanks: 'ਖ਼ੁਸ਼ੀ ਹੋਈ! ਹੋਰ ਕੁਝ?',
    about: 'ਮੈਂ ਸੋਨਾ ਹਾਂ, MyGoldRates ਦੀ ਸਹਾਇਕ। ਮੈਂ ਅੱਜ ਦੇ ਅਸਲ ਅੰਕੜਿਆਂ ਤੋਂ ਜਵਾਬ ਦਿੰਦੀ ਹਾਂ — {n} ਜਿਊਲਰਾਂ ਦੇ ਛਪੇ ਭਾਅ, ਅਸਲ ਉਤਪਾਦਾਂ ਤੋਂ ਮਾਪੀ ਘੜਾਈ, ਅਤੇ ਉਹਨਾਂ ਦੀਆਂ ਵੈੱਬਸਾਈਟਾਂ ਦੀਆਂ ਆਫ਼ਰਾਂ — ਇਸ ਲਈ ਮੈਂ ਕੋਈ ਅੰਕੜਾ ਅੰਦਾਜ਼ੇ ਨਾਲ ਨਹੀਂ ਦੱਸਦੀ।',
    unknown: 'ਇਹ ਮੈਂ ਅਜੇ ਸਿੱਖ ਰਹੀ ਹਾਂ — ਤੁਹਾਡਾ ਸਵਾਲ ਨੋਟ ਕਰ ਲਿਆ ਹੈ, ਜਲਦੀ ਸਹੀ ਜਵਾਬ ਜੋੜਾਂਗੇ। ਤਦ ਤੱਕ, ਇਹਨਾਂ ਵਿੱਚ ਮੈਂ ਚੰਗੀ ਹਾਂ:',
    nodata: 'ਅੱਜ ਦੇ ਅੰਕੜੇ ਲੋਡ ਨਹੀਂ ਹੋਏ। ਕਿਰਪਾ ਕਰਕੇ ਇੰਟਰਨੈੱਟ ਵੇਖ ਕੇ ਫਿਰ ਕੋਸ਼ਿਸ਼ ਕਰੋ।',
    no_voice: 'ਇਸ ਡਿਵਾਈਸ ਵਿੱਚ {l} ਆਵਾਜ਼ ਨਹੀਂ ਹੈ, ਇਸ ਲਈ ਮੈਂ ਲਿਖ ਕੇ ਜਵਾਬ ਦਿਆਂਗੀ।',
    mic_denied: 'ਮਾਈਕ ਬੰਦ ਹੈ। ਬ੍ਰਾਊਜ਼ਰ ਦੀ ਸੈਟਿੰਗ ਵਿੱਚ ਇਸ ਸਾਈਟ ਲਈ ਮਾਈਕ ਚਾਲੂ ਕਰੋ, ਫਿਰ 🎤 ਦਬਾਓ।',
    mic_none: 'ਮੈਂ ਸੁਣ ਨਹੀਂ ਸਕੀ — 🎤 ਦਬਾ ਕੇ ਫਿਰ ਬੋਲੋ।',
    rupees: 'ਰੁਪਏ', carat: 'ਕੈਰਟ',
    say_med: 'ਅੱਜ {k} ਸੋਨਾ ਲਗਭਗ {p} ਪ੍ਰਤੀ ਗ੍ਰਾਮ ਹੈ, {n} ਜਿਊਲਰਾਂ ਦਾ ਵਿਚਕਾਰਲਾ ਭਾਅ। ਸਭ ਤੋਂ ਘੱਟ {b} ’ਤੇ, {q}।',
    say_brand: '{b} ’ਤੇ ਅੱਜ {k} ਸੋਨਾ {p} ਪ੍ਰਤੀ ਗ੍ਰਾਮ ਹੈ, {n} ਜਿਊਲਰਾਂ ਵਿੱਚ ਨੰਬਰ {r}।',
    say_city: '{c} ਵਿੱਚ ਅੱਜ ਸਭ ਤੋਂ ਸਸਤਾ {k} {b} ’ਤੇ ਹੈ, {p} ਪ੍ਰਤੀ ਗ੍ਰਾਮ।',
    say_cheap: 'ਅੱਜ ਸਭ ਤੋਂ ਸਸਤਾ {k} {b} ’ਤੇ ਹੈ, {p} ਪ੍ਰਤੀ ਗ੍ਰਾਮ। 10 ਗ੍ਰਾਮ ’ਤੇ ਸਭ ਤੋਂ ਮਹਿੰਗਾ ਜਿਊਲਰ {q} ਵੱਧ ਲੈਂਦਾ ਹੈ।',
    say_cmp: '{b} ਸਸਤਾ ਹੈ, 10 ਗ੍ਰਾਮ {k} ’ਤੇ {p} ਘੱਟ।',
    say_mk_brand: '{b} ’ਤੇ {c} ਦੀ ਆਮ ਘੜਾਈ ਲਗਭਗ {p} ਹੈ।',
    say_mk: '{c} ’ਤੇ ਸਭ ਤੋਂ ਘੱਟ ਘੜਾਈ {b} ’ਤੇ ਹੈ, ਲਗਭਗ {p}।',
    say_mk_none: '{b} ਦੀ ਘੜਾਈ ਅਸੀਂ ਅਜੇ ਨਹੀਂ ਮਾਪੀ।',
    say_off_all: 'ਅੱਜ {n} ਜਿਊਲਰਾਂ ਕੋਲ ਆਫ਼ਰਾਂ ਹਨ। ਸਿਰਫ਼ ਹਰ ਡਿਜ਼ਾਈਨ ’ਤੇ ਲਾਗੂ ਆਫ਼ਰ ਗਿਣ ਕੇ, 10 ਗ੍ਰਾਮ 22 ਕੈਰਟ ਮੁੰਦਰੀ ਸਭ ਤੋਂ ਘੱਟ {b} ’ਤੇ ਹੈ: GST ਸਮੇਤ {p}।',
    say_off_brand: 'ਅੱਜ {b} ਦੀ ਵੈੱਬਸਾਈਟ ’ਤੇ {n} ਆਫ਼ਰਾਂ ਹਨ।',
    say_off_none: 'ਅੱਜ {b} ਦੀ ਵੈੱਬਸਾਈਟ ’ਤੇ ਕੋਈ ਆਫ਼ਰ ਨਹੀਂ ਹੈ।',
    say_price: '{b} ’ਤੇ {w} {k} ਸੋਨਾ GST ਸਮੇਤ ਲਗਭਗ {p} ਦਾ ਪਵੇਗਾ।',
    say_trend_up: 'ਅੱਜ {k} ਸੋਨਾ {p} ਪ੍ਰਤੀ ਗ੍ਰਾਮ ਹੈ, ਪਿਛਲੇ ਦਿਨ ਨਾਲੋਂ {q} ਵੱਧ।',
    say_trend_dn: 'ਅੱਜ {k} ਸੋਨਾ {p} ਪ੍ਰਤੀ ਗ੍ਰਾਮ ਹੈ, ਪਿਛਲੇ ਦਿਨ ਨਾਲੋਂ {q} ਘੱਟ।',
    say_trend_same: 'ਅੱਜ {k} ਸੋਨਾ {p} ਪ੍ਰਤੀ ਗ੍ਰਾਮ ਹੈ, ਪਿਛਲੇ ਦਿਨ ਜਿੰਨਾ ਹੀ।',
    u_g: '{n} ਗ੍ਰਾਮ', u_tola: '{n} ਤੋਲਾ', u_sov: '{n} ਸਾਵਰਿਨ', u_kg: '{n} ਕਿੱਲੋ',
    c_Ring: 'ਮੁੰਦਰੀ', c_Chain: 'ਚੇਨ', c_Bangle: 'ਚੂੜੀ', c_Necklace: 'ਹਾਰ', c_Earrings: 'ਝੁਮਕੇ',
    c_Mangalsutra: 'ਮੰਗਲਸੂਤਰ', c_Pendant: 'ਪੈਂਡੈਂਟ', c_Bracelet: 'ਬ੍ਰੇਸਲੈੱਟ', c_Coin: 'ਸਿੱਕਾ',
    ch_cheap22: 'ਅੱਜ ਸਭ ਤੋਂ ਸਸਤਾ 22K', ch_mycity: 'ਮੇਰੇ ਸ਼ਹਿਰ ਵਿੱਚ ਭਾਅ', ch_tvk: 'ਤਨਿਸ਼ਕ ਜਾਂ ਕਲਿਆਣ',
    ch_bestoff: 'ਅੱਜ ਦੀ ਸਭ ਤੋਂ ਵਧੀਆ ਆਫ਼ਰ', ch_p10chain: '10 ਗ੍ਰਾਮ 22K ਚੇਨ ਦੀ ਕੀਮਤ', ch_k22v24: '22K ਅਤੇ 24K ਵਿੱਚ ਫ਼ਰਕ?',
    ch_p10: '10 ਗ੍ਰਾਮ 22K ਦੀ ਕੀਮਤ', ch_afteroff: 'ਆਫ਼ਰ ਤੋਂ ਬਾਅਦ ਕੀਮਤ', ch_mkcmp: 'ਘੜਾਈ ਦੀ ਤੁਲਨਾ',
    ch_goodmk: 'ਕੀ ਘੜਾਈ ’ਤੇ 20% ਛੋਟ ਚੰਗੀ ਹੈ?', ch_whatmk: 'ਘੜਾਈ ਕੀ ਹੈ?', ch_alert: 'ਭਾਅ ਅਲਰਟ ਲਾਓ',
    ch_goodtime: 'ਕੀ ਹੁਣ ਖ਼ਰੀਦਣਾ ਠੀਕ ਹੈ?', ch_rate: 'ਅੱਜ ਸੋਨੇ ਦਾ ਭਾਅ', ch_another: 'ਦੂਜੇ ਜਿਊਲਰ ’ਤੇ ਇਹੀ',
    ch_bmk: '{b} ਘੜਾਈ', ch_boff: '{b} ਆਫ਼ਰਾਂ'
  };

  S.bn = {
    ui_sub: 'গয়নার সহকারী · আজকের আসল দাম থেকে উত্তর',
    ui_ph: 'দাম, জুয়েলার, অফার নিয়ে জিজ্ঞেস করুন…',
    ui_listen: 'শুনছি… বলুন',
    ui_mic: 'বলে জিজ্ঞেস করুন',
    ui_foot: 'বিনামূল্যে · লিখুন বা বলুন · প্রকাশিত তথ্য থেকে উত্তর, পরামর্শ নয়',
    ui_lang: 'ভাষা', ui_speak: 'শুনুন', ui_mute: 'বলা থামান',
    greet1: 'নমস্কার! 🙏 আমি <b>সোনা</b>, আপনার গয়নার সহকারী।',
    greet2: 'সোনা কেনা নিয়ে যা খুশি জিজ্ঞেস করুন — যেকোনো জুয়েলারের আজকের দাম, আপনার শহরে সবচেয়ে সস্তা, মজুরি (মেকিং চার্জ), অফার বা যেকোনো ওজনের দাম। লিখুন, বা 🎤 টিপে বলুন।',
    lang_hint: 'নিজের ভাষায় জিজ্ঞেস করুন — লিখে বা বলে — আমি সেই ভাষাতেই উত্তর দেব। হিন্দি বা ইংরেজি ছাড়া অন্য ভাষায় বলবেন? একবার সেটা বেছে নিন:',
    ui_auto: 'নিজে থেকে (চিনে নেবে)',
    src: 'আজকের দাম {n}টি জুয়েলারের, GST ছাড়া · {d}',
    med_h: 'ভারতে আজ সোনার দাম, {n}টি জুয়েলারের মাঝামাঝি দাম:',
    med_low: 'জাতীয় জুয়েলারদের মধ্যে সবচেয়ে কম 22K: <b>{b}</b>, <b>{p}/গ্রাম</b>।',
    brand_h: '<b>{b}</b> আজ:',
    brand_rank: 'আজ {n}টি জুয়েলারের মধ্যে এটি <b>#{r}</b> — {rel}।',
    rel_at: '{k}-এর বাজারের মাঝামাঝি দামের সমান', rel_below: '{k}-এর মাঝামাঝি দামের চেয়ে {p}/গ্রাম কম', rel_above: '{k}-এর মাঝামাঝি দামের চেয়ে {p}/গ্রাম বেশি',
    brand_mk: 'সাধারণ মজুরি: {list}।',
    brand_off: 'ওদের সাইটে অফার: <b>{o}</b>।',
    brand_st: 'এই রাজ্যগুলিতে: {s}।',
    brand_link: '{b}-এর 30 দিনের দাম →',
    city_h: '<b>{c}</b>-এ আজ সবচেয়ে সস্তা {k} ({note}):',
    city_loc: 'জাতীয় জুয়েলার এবং {s}-এর {l}টি স্থানীয় জুয়েলার', city_nat: 'জাতীয় জুয়েলার',
    city_link: '{c}-এর পুরো তালিকা →',
    cheap_h: 'জাতীয় জুয়েলারদের মধ্যে আজ সবচেয়ে সস্তা {k}:',
    cheap_gap: 'সবচেয়ে সস্তা আর সবচেয়ে দামির মধ্যে 10 গ্রামে <b>{p}</b> তফাত — কেনার আগে অবশ্যই দেখুন।',
    cmp_h: 'আজ পাশাপাশি ({k}):', cmp_10: '10 গ্রাম: {p}', cmp_mk: 'মজুরি ~{p}', cmp_nomk: 'মজুরি: মাপা হয়নি',
    cmp_win: '<b>{b}</b>-এর {k} দাম 10 গ্রামে <b>{p}</b> কম। চূড়ান্ত বিল আপনার বেছে নেওয়া ডিজাইনের মজুরির ওপরও নির্ভর করে।',
    mk_none: '<b>{b}</b>-এর মজুরি আমরা এখনও মাপিনি। এদের মাপা আছে: {list}।',
    mk_link: 'মজুরির তুলনা →',
    mk_brand_h: '<b>{b}</b>-এর সাধারণ মজুরি (আসল পণ্যের মাঝামাঝি হিসাব, সোনার দামের %):',
    mk_note: 'ডিজাইন অনুযায়ী বদলায়; বিলের এই অংশেই সবচেয়ে বেশি দরদাম করা যায়।',
    mk_all: 'সব জুয়েলারের তুলনা →',
    mk_h: '<b>{c}</b>-এ সবচেয়ে কম মজুরি (আসল পণ্যের মাঝামাঝি হিসাব):',
    mk_nocat: '<b>{c}</b>-এর মজুরি আমরা এখনও মাপিনি। <b>{r}</b>-এর এটা:',
    mk_every: 'প্রতিটি জুয়েলার ও প্রতিটি ধরন →',
    bo_ask: 'কোন গয়নার সেরা অফার খুঁজব?',
    bo_h: 'আজকের মজুরি অফারের পরে <b>{w}</b> 22K <b>{c}</b>-এর সেরা দাম:',
    bo_note: 'মোট = সোনা + অফারের পরে মজুরি + 3% GST. অফার % আনুমানিক; * মানে “পর্যন্ত”, শুধু কিছু ডিজাইনে (বন্ধনীতে সেরা অবস্থা). জুয়েলারের কাছে নিশ্চিত করুন.',
    bo_none: '{c}-এর মজুরি এখনও যথেষ্ট জুয়েলারের আমার কাছে নেই.',
    say_bo: '{w} 22K {c}-এর জন্য অফারের পরে {b} সবচেয়ে সস্তা, GST সহ প্রায় {p}.',
    bo_upto: 'পর্যন্ত',
    bo_noff: 'অফার নেই',
    off_none: 'আজ <b>{b}</b>-এর ওয়েবসাইটে কোনো অফার লেখা নেই।',
    off_see: 'কার অফার আছে দেখুন →',
    off_brand_h: 'আজ <b>{b}</b>-এর ওয়েবসাইটে অফার:',
    off_page: 'ওদের পেজ ↗', off_all: 'সব জুয়েলারের অফারের তুলনা →',
    off_all_h: 'আজ {n}টি জুয়েলারের নিজস্ব ওয়েবসাইটে অফার আছে (A–Z):',
    off_ring: 'শুধু সব ডিজাইনে প্রযোজ্য অফার ধরে, আজ 10 গ্রাম 22K আংটি সবচেয়ে কমে <b>{b}</b>-এ: GST সহ {p}। “আপ টু” আর বাছাই করা ডিজাইনের অফার গয়না ভেদে আলাদা — জুয়েলারের কাছে নিশ্চিত হয়ে নিন।',
    off_every: 'প্রতিটি অফার, আর তার আসল মানে →',
    price_h: 'আজ {who}-এ {w} {k}:', price_who: 'সবচেয়ে সস্তা জাতীয় জুয়েলার ({b})',
    price_gold: 'সোনা ({g} গ্রাম × {p})', price_mk: 'মজুরি (~{p}, {c})', price_typ: 'সাধারণত', price_total: 'মোট',
    price_nomk: 'মজুরি ধরা হয়নি — আপনার ডিজাইনের মজুরি যোগ করুন (প্রায়ই 8–25%)।',
    trend_none: 'এখনও যথেষ্ট ইতিহাস নেই।', hist_link: 'সোনার দামের ইতিহাস →',
    trend_h: '{k}-এর বাজারের মাঝামাঝি দাম: আজ <b>{p}/গ্রাম</b>।',
    vs1: 'আগের দিনের তুলনায়', vs7: '7 দিন আগের তুলনায়', vs30: '30 দিন আগের তুলনায়',
    trend_note: 'এগুলো অতীতের ওঠানামা, পূর্বাভাস নয় — কালকের দাম কেউ নিশ্চিত করে বলতে পারে না।',
    full_hist: 'পুরো ইতিহাস →',
    alerts: 'প্রতিদিন সকালে সবচেয়ে সস্তা জুয়েলার আর আজকের দাম, বিনামূল্যে — আর যেদিন 22K আপনার দামে নামবে, সেদিন ইমেল।',
    alerts_cta: 'বিনামূল্যে রোজের অ্যালার্ট নিন',
    more: 'আরও পড়ুন →', guide_h: 'এই গাইডে এটাই আছে: <b>{t}</b> — {d}', guide_link: 'গাইড পড়ুন →',
    en_only: 'এই উত্তরটি আপাতত ইংরেজিতে:', translated: 'আপনার ডিভাইসে অনুবাদ করা',
    ask_city: 'আপনি কোন শহরে আছেন?',
    ch_loc: 'আমার লোকেশন ব্যবহার করুন', loc_wait: 'আপনার কাছের শহর খুঁজছি…',
    loc_fail: 'লোকেশন পাওয়া গেল না। আপনার শহরের নাম লিখুন বা বেছে নিন:', ch_chcity: 'শহর বদলান',
    silver: 'আপাতত আমি শুধু সোনার তথ্য দিই — জুয়েলারদের 22K, 24K আর 18K দাম। রুপো শিগগিরই আসছে।',
    hello: 'নমস্কার! 🙏 আমি সোনা। সোনা কেনা নিয়ে যা খুশি জিজ্ঞেস করুন — {n}টি জুয়েলারের আজকের দাম, আপনার শহর, মজুরি, অফার বা যেকোনো ওজনের দাম।',
    thanks: 'খুশি হলাম! আর কিছু?',
    about: 'আমি সোনা, MyGoldRates-এর সহকারী। আমি আজকের আসল তথ্য থেকে উত্তর দিই — {n}টি জুয়েলারের প্রকাশিত দাম, আসল পণ্য থেকে মাপা মজুরি, আর ওদের ওয়েবসাইটের অফার — তাই কোনো সংখ্যা আন্দাজে বলি না।',
    unknown: 'এটা আমি এখনও শিখছি — আপনার প্রশ্ন লিখে রেখেছি, শিগগিরই ঠিক উত্তর যোগ করব। ততক্ষণ, এগুলোতে আমি ভালো:',
    nodata: 'আজকের তথ্য লোড হয়নি। ইন্টারনেট দেখে আবার চেষ্টা করুন।',
    no_voice: 'এই ডিভাইসে {l} কণ্ঠ নেই, তাই আমি লিখে উত্তর দেব।',
    mic_denied: 'মাইক বন্ধ আছে। ব্রাউজারের সেটিংসে এই সাইটের জন্য মাইক চালু করুন, তারপর আবার 🎤 টিপুন।',
    mic_none: 'আমি শুনতে পাইনি — 🎤 টিপে আবার বলুন।',
    rupees: 'টাকা', carat: 'ক্যারেট',
    say_med: 'আজ {k} সোনা প্রায় {p} প্রতি গ্রাম, {n}টি জুয়েলারের মাঝামাঝি দাম। সবচেয়ে কম {b}-এ, {q}।',
    say_brand: '{b}-এ আজ {k} সোনা {p} প্রতি গ্রাম, {n}টি জুয়েলারের মধ্যে {r} নম্বর।',
    say_city: '{c}-এ আজ সবচেয়ে সস্তা {k} {b}-এ, {p} প্রতি গ্রাম।',
    say_cheap: 'আজ সবচেয়ে সস্তা {k} {b}-এ, {p} প্রতি গ্রাম। 10 গ্রামে সবচেয়ে দামি জুয়েলার {q} বেশি নেয়।',
    say_cmp: '{b} সস্তা, 10 গ্রাম {k}-এ {p} কম।',
    say_mk_brand: '{b}-এ {c}-এর সাধারণ মজুরি প্রায় {p}।',
    say_mk: '{c}-এ সবচেয়ে কম মজুরি {b}-এ, প্রায় {p}।',
    say_mk_none: '{b}-এর মজুরি আমরা এখনও মাপিনি।',
    say_off_all: 'আজ {n}টি জুয়েলারের অফার আছে। শুধু সব ডিজাইনে প্রযোজ্য অফার ধরে, 10 গ্রাম 22 ক্যারেট আংটি সবচেয়ে কমে {b}-এ: GST সহ {p}।',
    say_off_brand: 'আজ {b}-এর ওয়েবসাইটে {n}টি অফার আছে।',
    say_off_none: 'আজ {b}-এর ওয়েবসাইটে কোনো অফার নেই।',
    say_price: '{b}-এ {w} {k} সোনা GST সহ প্রায় {p} পড়বে।',
    say_trend_up: 'আজ {k} সোনা {p} প্রতি গ্রাম, আগের দিনের চেয়ে {q} বেশি।',
    say_trend_dn: 'আজ {k} সোনা {p} প্রতি গ্রাম, আগের দিনের চেয়ে {q} কম।',
    say_trend_same: 'আজ {k} সোনা {p} প্রতি গ্রাম, আগের দিনের মতোই।',
    u_g: '{n} গ্রাম', u_tola: '{n} ভরি', u_sov: '{n} সভরেন', u_kg: '{n} কেজি',
    c_Ring: 'আংটি', c_Chain: 'চেন', c_Bangle: 'চুড়ি', c_Necklace: 'হার', c_Earrings: 'কানের দুল',
    c_Mangalsutra: 'মঙ্গলসূত্র', c_Pendant: 'লকেট', c_Bracelet: 'ব্রেসলেট', c_Coin: 'কয়েন',
    ch_cheap22: 'আজ সবচেয়ে সস্তা 22K', ch_mycity: 'আমার শহরে দাম', ch_tvk: 'তানিষ্ক না কল্যাণ',
    ch_bestoff: 'আজকের সেরা অফার', ch_p10chain: '10 গ্রাম 22K চেনের দাম', ch_k22v24: '22K আর 24K-এর তফাত?',
    ch_p10: '10 গ্রাম 22K-এর দাম', ch_afteroff: 'অফারের পরে দাম', ch_mkcmp: 'মজুরির তুলনা',
    ch_goodmk: 'মজুরিতে 20% ছাড় কি ভালো?', ch_whatmk: 'মজুরি কী?', ch_alert: 'দামের অ্যালার্ট দিন',
    ch_goodtime: 'এখন কেনা কি ঠিক?', ch_rate: 'আজ সোনার দাম', ch_another: 'অন্য জুয়েলারে একই',
    ch_bmk: '{b} মজুরি', ch_boff: '{b} অফার'
  };

  S.kn = {
    ui_sub: 'ಆಭರಣ ಸಹಾಯಕಿ · ಇಂದಿನ ನಿಜವಾದ ದರಗಳಿಂದ ಉತ್ತರ',
    ui_ph: 'ದರ, ಜ್ಯುವೆಲ್ಲರ್ಸ್, ಆಫರ್‌ಗಳ ಬಗ್ಗೆ ಕೇಳಿ…',
    ui_listen: 'ಕೇಳುತ್ತಿದ್ದೇನೆ… ಮಾತನಾಡಿ',
    ui_mic: 'ಮಾತನಾಡಿ ಕೇಳಿ',
    ui_foot: 'ಉಚಿತ · ಟೈಪ್ ಮಾಡಿ ಅಥವಾ ಮಾತನಾಡಿ · ಪ್ರಕಟಿತ ಮಾಹಿತಿಯಿಂದ ಉತ್ತರ, ಸಲಹೆ ಅಲ್ಲ',
    ui_lang: 'ಭಾಷೆ', ui_speak: 'ಕೇಳಿ', ui_mute: 'ಮಾತು ನಿಲ್ಲಿಸಿ',
    greet1: 'ನಮಸ್ಕಾರ! 🙏 ನಾನು <b>ಸೋನಾ</b>, ನಿಮ್ಮ ಆಭರಣ ಸಹಾಯಕಿ.',
    greet2: 'ಚಿನ್ನ ಖರೀದಿಯ ಬಗ್ಗೆ ಏನಾದರೂ ಕೇಳಿ — ಯಾವುದೇ ಜ್ಯುವೆಲ್ಲರ್‌ನ ಇಂದಿನ ದರ, ನಿಮ್ಮ ನಗರದಲ್ಲಿ ಅತಿ ಕಡಿಮೆ ದರ, ಮೇಕಿಂಗ್ ಚಾರ್ಜ್, ಆಫರ್‌ಗಳು ಅಥವಾ ಯಾವುದೇ ತೂಕದ ಬೆಲೆ. ಟೈಪ್ ಮಾಡಿ, ಅಥವಾ 🎤 ಒತ್ತಿ ಮಾತನಾಡಿ.',
    lang_hint: 'ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲೇ ಕೇಳಿ — ಬರೆದು ಅಥವಾ ಮಾತನಾಡಿ — ನಾನು ಅದೇ ಭಾಷೆಯಲ್ಲಿ ಉತ್ತರಿಸುತ್ತೇನೆ. ಹಿಂದಿ ಅಥವಾ ಇಂಗ್ಲಿಷ್ ಬಿಟ್ಟು ಬೇರೆ ಭಾಷೆ ಮಾತನಾಡುತ್ತೀರಾ? ಅದನ್ನು ಒಮ್ಮೆ ಆರಿಸಿ:',
    ui_auto: 'ಸ್ವಯಂ (ಗುರುತಿಸು)',
    src: 'ಇಂದಿನ ದರಗಳು {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನಿಂದ, GST ಮೊದಲು · {d}',
    med_h: 'ಭಾರತದಲ್ಲಿ ಇಂದಿನ ಚಿನ್ನದ ದರ, {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನ ಮಧ್ಯದ ದರ:',
    med_low: 'ರಾಷ್ಟ್ರೀಯ ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನಲ್ಲಿ ಅತಿ ಕಡಿಮೆ 22K: <b>{b}</b>, <b>{p}/ಗ್ರಾಂ</b>.',
    brand_h: '<b>{b}</b> ಇಂದು:',
    brand_rank: 'ಇಂದು {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನಲ್ಲಿ ಇದು <b>#{r}</b> ಸ್ಥಾನದಲ್ಲಿದೆ — {rel}.',
    rel_at: '{k} ಮಾರುಕಟ್ಟೆಯ ಮಧ್ಯದ ದರಕ್ಕೆ ಸಮ', rel_below: '{k} ಮಧ್ಯದ ದರಕ್ಕಿಂತ {p}/ಗ್ರಾಂ ಕಡಿಮೆ', rel_above: '{k} ಮಧ್ಯದ ದರಕ್ಕಿಂತ {p}/ಗ್ರಾಂ ಹೆಚ್ಚು',
    brand_mk: 'ಸಾಮಾನ್ಯ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್: {list}.',
    brand_off: 'ಅವರ ಸೈಟ್‌ನಲ್ಲಿ ಆಫರ್: <b>{o}</b>.',
    brand_st: 'ಈ ರಾಜ್ಯಗಳಲ್ಲಿ: {s}.',
    brand_link: '{b} ನ 30 ದಿನಗಳ ದರಗಳು →',
    city_h: '<b>{c}</b> ನಲ್ಲಿ ಇಂದು ಅತಿ ಕಡಿಮೆ {k} ({note}):',
    city_loc: 'ರಾಷ್ಟ್ರೀಯ ಜ್ಯುವೆಲ್ಲರ್ಸ್ ಮತ್ತು {s} ನ {l} ಸ್ಥಳೀಯ ಜ್ಯುವೆಲ್ಲರ್ಸ್', city_nat: 'ರಾಷ್ಟ್ರೀಯ ಜ್ಯುವೆಲ್ಲರ್ಸ್',
    city_link: '{c} ನ ಪೂರ್ಣ ಪಟ್ಟಿ →',
    cheap_h: 'ರಾಷ್ಟ್ರೀಯ ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನಲ್ಲಿ ಇಂದು ಅತಿ ಕಡಿಮೆ {k}:',
    cheap_gap: 'ಅತಿ ಕಡಿಮೆ ಮತ್ತು ಅತಿ ಹೆಚ್ಚು ದರದ ನಡುವೆ 10 ಗ್ರಾಂಗೆ <b>{p}</b> ವ್ಯತ್ಯಾಸ ಇದೆ — ಖರೀದಿಸುವ ಮೊದಲು ನೋಡಿ.',
    cmp_h: 'ಇಂದು ಅಕ್ಕಪಕ್ಕ ({k}):', cmp_10: '10 ಗ್ರಾಂ: {p}', cmp_mk: 'ಮೇಕಿಂಗ್ ~{p}', cmp_nomk: 'ಮೇಕಿಂಗ್: ಅಳೆದಿಲ್ಲ',
    cmp_win: '<b>{b}</b> ನ {k} ದರ 10 ಗ್ರಾಂಗೆ <b>{p}</b> ಕಡಿಮೆ. ಅಂತಿಮ ಬಿಲ್ ನೀವು ಆರಿಸುವ ವಿನ್ಯಾಸದ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಮೇಲೂ ಅವಲಂಬಿತ.',
    mk_none: '<b>{b}</b> ನ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಅನ್ನು ನಾವು ಇನ್ನೂ ಅಳೆದಿಲ್ಲ. ಇವರದ್ದು ಅಳೆದಿದ್ದೇವೆ: {list}.',
    mk_link: 'ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಹೋಲಿಕೆ →',
    mk_brand_h: '<b>{b}</b> ನ ಸಾಮಾನ್ಯ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ (ನಿಜವಾದ ಉತ್ಪನ್ನಗಳ ಮಧ್ಯದ ಅಂಕಿ, ಚಿನ್ನದ ಬೆಲೆಯ %):',
    mk_note: 'ವಿನ್ಯಾಸದ ಪ್ರಕಾರ ಬದಲಾಗುತ್ತದೆ; ಬಿಲ್‌ನಲ್ಲಿ ಹೆಚ್ಚು ಚೌಕಾಸಿ ಮಾಡಬಹುದಾದ ಭಾಗ ಇದೇ.',
    mk_all: 'ಎಲ್ಲಾ ಜ್ಯುವೆಲ್ಲರ್ಸ್ ಹೋಲಿಕೆ →',
    mk_h: '<b>{c}</b> ಮೇಲೆ ಅತಿ ಕಡಿಮೆ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ (ನಿಜವಾದ ಉತ್ಪನ್ನಗಳ ಮಧ್ಯದ ಅಂಕಿ):',
    mk_nocat: '<b>{c}</b> ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಅನ್ನು ನಾವು ಇನ್ನೂ ಅಳೆದಿಲ್ಲ. <b>{r}</b> ದ್ದು ಇಲ್ಲಿದೆ:',
    mk_every: 'ಪ್ರತಿ ಜ್ಯುವೆಲ್ಲರ್ ಮತ್ತು ವಿಭಾಗ →',
    bo_ask: 'ಯಾವ ಆಭರಣಕ್ಕೆ ಉತ್ತಮ ಆಫರ್ ಹುಡುಕಲಿ?',
    bo_h: 'ಇಂದಿನ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಆಫರ್ ನಂತರ <b>{w}</b> 22K <b>{c}</b> ಉತ್ತಮ ಬೆಲೆ:',
    bo_note: 'ಒಟ್ಟು = ಚಿನ್ನ + ಆಫರ್ ನಂತರದ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ + 3% GST. ಆಫರ್ % ಅಂದಾಜು; * ಎಂದರೆ “ವರೆಗೆ”, ಕೆಲವು ವಿನ್ಯಾಸಗಳಿಗೆ ಮಾತ್ರ (ಆವರಣದಲ್ಲಿ ಉತ್ತಮ ಸ್ಥಿತಿ). ಜ್ಯುವೆಲ್ಲರ್ ಬಳಿ ಖಚಿತಪಡಿಸಿ.',
    bo_none: '{c} ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಇನ್ನೂ ಸಾಕಷ್ಟು ಜ್ಯುವೆಲ್ಲರ್‌ಗಳದ್ದು ನನ್ನ ಬಳಿ ಇಲ್ಲ.',
    say_bo: '{w} 22K {c}ಗೆ ಆಫರ್ ನಂತರ {b} ಅಗ್ಗ, GST ಸೇರಿ ಸುಮಾರು {p}.',
    bo_upto: 'ವರೆಗೆ',
    bo_noff: 'ಆಫರ್ ಇಲ್ಲ',
    off_none: 'ಇಂದು <b>{b}</b> ನ ವೆಬ್‌ಸೈಟ್‌ನಲ್ಲಿ ಯಾವುದೇ ಆಫರ್ ಬರೆದಿಲ್ಲ.',
    off_see: 'ಯಾರ ಬಳಿ ಆಫರ್ ಇದೆ ನೋಡಿ →',
    off_brand_h: 'ಇಂದು <b>{b}</b> ನ ವೆಬ್‌ಸೈಟ್‌ನಲ್ಲಿರುವ ಆಫರ್‌ಗಳು:',
    off_page: 'ಅವರ ಪುಟ ↗', off_all: 'ಎಲ್ಲಾ ಜ್ಯುವೆಲ್ಲರ್ಸ್ ಆಫರ್ ಹೋಲಿಕೆ →',
    off_all_h: 'ಇಂದು {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನ ಸ್ವಂತ ವೆಬ್‌ಸೈಟ್‌ಗಳಲ್ಲಿ ಆಫರ್‌ಗಳಿವೆ (A–Z):',
    off_ring: 'ಎಲ್ಲಾ ವಿನ್ಯಾಸಗಳಿಗೆ ಅನ್ವಯಿಸುವ ಆಫರ್‌ಗಳನ್ನು ಮಾತ್ರ ಸೇರಿಸಿ, ಇಂದು 10 ಗ್ರಾಂ 22K ಉಂಗುರ ಅತಿ ಕಡಿಮೆ <b>{b}</b> ನಲ್ಲಿ: GST ಸೇರಿ {p}. “ಅಪ್ ಟು” ಮತ್ತು ಆಯ್ದ ವಿನ್ಯಾಸಗಳ ಆಫರ್‌ಗಳು ಆಭರಣದಿಂದ ಆಭರಣಕ್ಕೆ ಬದಲಾಗುತ್ತವೆ — ಜ್ಯುವೆಲ್ಲರ್ ಬಳಿ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ.',
    off_every: 'ಪ್ರತಿ ಆಫರ್, ಮತ್ತು ಅದರ ನಿಜವಾದ ಅರ್ಥ →',
    price_h: 'ಇಂದು {who} ನಲ್ಲಿ {w} {k}:', price_who: 'ಅತಿ ಕಡಿಮೆ ದರದ ರಾಷ್ಟ್ರೀಯ ಜ್ಯುವೆಲ್ಲರ್ ({b})',
    price_gold: 'ಚಿನ್ನ ({g} ಗ್ರಾಂ × {p})', price_mk: 'ಮೇಕಿಂಗ್ (~{p}, {c})', price_typ: 'ಸಾಮಾನ್ಯ', price_total: 'ಒಟ್ಟು',
    price_nomk: 'ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಸೇರಿಲ್ಲ — ನಿಮ್ಮ ವಿನ್ಯಾಸದ ಚಾರ್ಜ್ ಸೇರಿಸಿ (ಸಾಮಾನ್ಯವಾಗಿ 8–25%).',
    trend_none: 'ಇನ್ನೂ ಸಾಕಷ್ಟು ಇತಿಹಾಸ ಇಲ್ಲ.', hist_link: 'ಚಿನ್ನದ ದರದ ಇತಿಹಾಸ →',
    trend_h: '{k} ಮಾರುಕಟ್ಟೆಯ ಮಧ್ಯದ ದರ: ಇಂದು <b>{p}/ಗ್ರಾಂ</b>.',
    vs1: 'ಹಿಂದಿನ ದಿನಕ್ಕೆ ಹೋಲಿಸಿದರೆ', vs7: '7 ದಿನಗಳ ಹಿಂದಿಗೆ ಹೋಲಿಸಿದರೆ', vs30: '30 ದಿನಗಳ ಹಿಂದಿಗೆ ಹೋಲಿಸಿದರೆ',
    trend_note: 'ಇವು ಹಿಂದಿನ ಬದಲಾವಣೆಗಳು, ಮುನ್ಸೂಚನೆ ಅಲ್ಲ — ನಾಳೆಯ ದರವನ್ನು ಯಾರೂ ಖಚಿತವಾಗಿ ಹೇಳಲಾರರು.',
    full_hist: 'ಪೂರ್ಣ ಇತಿಹಾಸ →',
    alerts: 'ಪ್ರತಿದಿನ ಬೆಳಿಗ್ಗೆ ಅತಿ ಕಡಿಮೆ ದರದ ಜ್ಯುವೆಲ್ಲರ್ ಮತ್ತು ಇಂದಿನ ದರ, ಉಚಿತ — ಮತ್ತು 22K ನಿಮ್ಮ ದರಕ್ಕೆ ಇಳಿದ ದಿನ ಇಮೇಲ್.',
    alerts_cta: 'ಉಚಿತ ದೈನಂದಿನ ಅಲರ್ಟ್ ಪಡೆಯಿರಿ',
    more: 'ಇನ್ನಷ್ಟು ಓದಿ →', guide_h: 'ಈ ಮಾರ್ಗದರ್ಶಿ ಇದರ ಬಗ್ಗೆಯೇ: <b>{t}</b> — {d}', guide_link: 'ಮಾರ್ಗದರ್ಶಿ ಓದಿ →',
    en_only: 'ಈ ಉತ್ತರ ಸದ್ಯಕ್ಕೆ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿದೆ:', translated: 'ನಿಮ್ಮ ಸಾಧನದಲ್ಲೇ ಅನುವಾದಿಸಲಾಗಿದೆ',
    ask_city: 'ನೀವು ಯಾವ ನಗರದಲ್ಲಿದ್ದೀರಿ?',
    ch_loc: 'ನನ್ನ ಸ್ಥಳ ಬಳಸಿ', loc_wait: 'ನಿಮ್ಮ ಹತ್ತಿರದ ನಗರವನ್ನು ಹುಡುಕುತ್ತಿದ್ದೇನೆ…',
    loc_fail: 'ಸ್ಥಳ ಸಿಗಲಿಲ್ಲ. ನಿಮ್ಮ ನಗರದ ಹೆಸರು ಬರೆಯಿರಿ ಅಥವಾ ಆಯ್ಕೆಮಾಡಿ:', ch_chcity: 'ನಗರ ಬದಲಿಸಿ',
    silver: 'ಸದ್ಯಕ್ಕೆ ನಾನು ಚಿನ್ನದ ಮಾಹಿತಿ ಮಾತ್ರ ನೀಡುತ್ತೇನೆ — ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನ 22K, 24K ಮತ್ತು 18K ದರಗಳು. ಬೆಳ್ಳಿ ಶೀಘ್ರದಲ್ಲೇ ಬರಲಿದೆ.',
    hello: 'ನಮಸ್ಕಾರ! 🙏 ನಾನು ಸೋನಾ. ಚಿನ್ನ ಖರೀದಿಯ ಬಗ್ಗೆ ಏನಾದರೂ ಕೇಳಿ — {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನ ಇಂದಿನ ದರಗಳು, ನಿಮ್ಮ ನಗರ, ಮೇಕಿಂಗ್ ಚಾರ್ಜ್, ಆಫರ್‌ಗಳು ಅಥವಾ ಯಾವುದೇ ತೂಕದ ಬೆಲೆ.',
    thanks: 'ಸಂತೋಷ! ಇನ್ನೇನಾದರೂ?',
    about: 'ನಾನು ಸೋನಾ, MyGoldRates ನ ಸಹಾಯಕಿ. ನಾನು ಇಂದಿನ ನಿಜವಾದ ಮಾಹಿತಿಯಿಂದ ಉತ್ತರಿಸುತ್ತೇನೆ — {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನ ಪ್ರಕಟಿತ ದರಗಳು, ನಿಜವಾದ ಉತ್ಪನ್ನಗಳಿಂದ ಅಳೆದ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್, ಮತ್ತು ಅವರ ವೆಬ್‌ಸೈಟ್‌ಗಳ ಆಫರ್‌ಗಳು — ಹಾಗಾಗಿ ನಾನು ಯಾವ ಅಂಕಿಯನ್ನೂ ಊಹಿಸುವುದಿಲ್ಲ.',
    unknown: 'ಇದನ್ನು ನಾನು ಇನ್ನೂ ಕಲಿಯುತ್ತಿದ್ದೇನೆ — ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಗುರುತಿಸಿಕೊಂಡಿದ್ದೇನೆ, ಶೀಘ್ರದಲ್ಲೇ ಸರಿಯಾದ ಉತ್ತರ ಸೇರಿಸುತ್ತೇವೆ. ಅಲ್ಲಿಯವರೆಗೆ, ಇವುಗಳಲ್ಲಿ ನಾನು ಚೆನ್ನಾಗಿ ಉತ್ತರಿಸಬಲ್ಲೆ:',
    nodata: 'ಇಂದಿನ ಮಾಹಿತಿ ಲೋಡ್ ಆಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಇಂಟರ್ನೆಟ್ ಪರಿಶೀಲಿಸಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    no_voice: 'ಈ ಸಾಧನದಲ್ಲಿ {l} ಧ್ವನಿ ಇಲ್ಲ, ಹಾಗಾಗಿ ನಾನು ಬರೆದು ಉತ್ತರಿಸುತ್ತೇನೆ.',
    mic_denied: 'ಮೈಕ್ ನಿರ್ಬಂಧಿಸಲಾಗಿದೆ. ಬ್ರೌಸರ್ ಸೆಟ್ಟಿಂಗ್‌ನಲ್ಲಿ ಈ ಸೈಟ್‌ಗೆ ಮೈಕ್ ಅನುಮತಿಸಿ, ನಂತರ ಮತ್ತೆ 🎤 ಒತ್ತಿ.',
    mic_none: 'ನನಗೆ ಕೇಳಿಸಲಿಲ್ಲ — 🎤 ಒತ್ತಿ ಮತ್ತೆ ಮಾತನಾಡಿ.',
    rupees: 'ರೂಪಾಯಿ', carat: 'ಕ್ಯಾರೆಟ್',
    say_med: 'ಇಂದು {k} ಚಿನ್ನ ಗ್ರಾಂಗೆ ಸುಮಾರು {p}, {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನ ಮಧ್ಯದ ದರ. ಅತಿ ಕಡಿಮೆ {b} ನಲ್ಲಿ, {q}.',
    say_brand: '{b} ನಲ್ಲಿ ಇಂದು {k} ಚಿನ್ನ ಗ್ರಾಂಗೆ {p}, {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್‌ನಲ್ಲಿ ಸ್ಥಾನ {r}.',
    say_city: '{c} ನಲ್ಲಿ ಇಂದು ಅತಿ ಕಡಿಮೆ {k} {b} ನಲ್ಲಿ, ಗ್ರಾಂಗೆ {p}.',
    say_cheap: 'ಇಂದು ಅತಿ ಕಡಿಮೆ {k} {b} ನಲ್ಲಿ, ಗ್ರಾಂಗೆ {p}. 10 ಗ್ರಾಂಗೆ ಅತಿ ದುಬಾರಿ ಜ್ಯುವೆಲ್ಲರ್ {q} ಹೆಚ್ಚು ತೆಗೆದುಕೊಳ್ಳುತ್ತಾರೆ.',
    say_cmp: '{b} ಕಡಿಮೆ ದರ, 10 ಗ್ರಾಂ {k} ಗೆ {p} ಕಡಿಮೆ.',
    say_mk_brand: '{b} ನಲ್ಲಿ {c} ಗೆ ಸಾಮಾನ್ಯ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಸುಮಾರು {p}.',
    say_mk: '{c} ಗೆ ಅತಿ ಕಡಿಮೆ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ {b} ನಲ್ಲಿ, ಸುಮಾರು {p}.',
    say_mk_none: '{b} ನ ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಅನ್ನು ನಾವು ಇನ್ನೂ ಅಳೆದಿಲ್ಲ.',
    say_off_all: 'ಇಂದು {n} ಜ್ಯುವೆಲ್ಲರ್ಸ್ ಬಳಿ ಆಫರ್‌ಗಳಿವೆ. ಎಲ್ಲಾ ವಿನ್ಯಾಸಗಳಿಗೆ ಅನ್ವಯಿಸುವ ಆಫರ್‌ಗಳನ್ನು ಮಾತ್ರ ಸೇರಿಸಿ, 10 ಗ್ರಾಂ 22 ಕ್ಯಾರೆಟ್ ಉಂಗುರ ಅತಿ ಕಡಿಮೆ {b} ನಲ್ಲಿ: GST ಸೇರಿ {p}.',
    say_off_brand: 'ಇಂದು {b} ನ ವೆಬ್‌ಸೈಟ್‌ನಲ್ಲಿ {n} ಆಫರ್‌ಗಳಿವೆ.',
    say_off_none: 'ಇಂದು {b} ನ ವೆಬ್‌ಸೈಟ್‌ನಲ್ಲಿ ಯಾವುದೇ ಆಫರ್ ಇಲ್ಲ.',
    say_price: '{b} ನಲ್ಲಿ {w} {k} ಚಿನ್ನ GST ಸೇರಿ ಸುಮಾರು {p} ಆಗುತ್ತದೆ.',
    say_trend_up: 'ಇಂದು {k} ಚಿನ್ನ ಗ್ರಾಂಗೆ {p}, ಹಿಂದಿನ ದಿನಕ್ಕಿಂತ {q} ಹೆಚ್ಚು.',
    say_trend_dn: 'ಇಂದು {k} ಚಿನ್ನ ಗ್ರಾಂಗೆ {p}, ಹಿಂದಿನ ದಿನಕ್ಕಿಂತ {q} ಕಡಿಮೆ.',
    say_trend_same: 'ಇಂದು {k} ಚಿನ್ನ ಗ್ರಾಂಗೆ {p}, ಹಿಂದಿನ ದಿನದಷ್ಟೇ.',
    u_g: '{n} ಗ್ರಾಂ', u_tola: '{n} ತೊಲ', u_sov: '{n} ಪವನ್', u_kg: '{n} ಕೆಜಿ',
    c_Ring: 'ಉಂಗುರ', c_Chain: 'ಸರ', c_Bangle: 'ಬಳೆ', c_Necklace: 'ನೆಕ್ಲೇಸ್', c_Earrings: 'ಕಿವಿಯೋಲೆ',
    c_Mangalsutra: 'ಮಾಂಗಲ್ಯ ಸರ', c_Pendant: 'ಪೆಂಡೆಂಟ್', c_Bracelet: 'ಬ್ರೇಸ್ಲೆಟ್', c_Coin: 'ನಾಣ್ಯ',
    ch_cheap22: 'ಇಂದು ಅತಿ ಕಡಿಮೆ 22K', ch_mycity: 'ನನ್ನ ನಗರದಲ್ಲಿ ದರ', ch_tvk: 'ತನಿಷ್ಕ್ ಅಥವಾ ಕಲ್ಯಾಣ್',
    ch_bestoff: 'ಇಂದಿನ ಉತ್ತಮ ಆಫರ್', ch_p10chain: '10 ಗ್ರಾಂ 22K ಸರದ ಬೆಲೆ', ch_k22v24: '22K ಮತ್ತು 24K ವ್ಯತ್ಯಾಸ?',
    ch_p10: '10 ಗ್ರಾಂ 22K ಬೆಲೆ', ch_afteroff: 'ಆಫರ್ ನಂತರದ ಬೆಲೆ', ch_mkcmp: 'ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಹೋಲಿಕೆ',
    ch_goodmk: 'ಮೇಕಿಂಗ್ ಮೇಲೆ 20% ರಿಯಾಯಿತಿ ಒಳ್ಳೆಯದೇ?', ch_whatmk: 'ಮೇಕಿಂಗ್ ಚಾರ್ಜ್ ಎಂದರೇನು?', ch_alert: 'ದರ ಅಲರ್ಟ್ ಹೊಂದಿಸಿ',
    ch_goodtime: 'ಈಗ ಖರೀದಿಸುವುದು ಸರಿಯೇ?', ch_rate: 'ಇಂದಿನ ಚಿನ್ನದ ದರ', ch_another: 'ಬೇರೆ ಜ್ಯುವೆಲ್ಲರ್‌ನಲ್ಲಿ ಇದೇ',
    ch_bmk: '{b} ಮೇಕಿಂಗ್ ಚಾರ್ಜ್', ch_boff: '{b} ಆಫರ್‌ಗಳು'
  };

  S.ta = {
    ui_sub: 'நகை உதவியாளர் · இன்றைய உண்மை விலைகளிலிருந்து பதில்',
    ui_ph: 'விலை, நகைக்கடை, ஆஃபர் பற்றி கேளுங்கள்…',
    ui_listen: 'கேட்கிறேன்… பேசுங்கள்',
    ui_mic: 'பேசிக் கேளுங்கள்',
    ui_foot: 'இலவசம் · தட்டச்சு செய்யுங்கள் அல்லது பேசுங்கள் · வெளியிடப்பட்ட தரவிலிருந்து பதில், ஆலோசனை அல்ல',
    ui_lang: 'மொழி', ui_speak: 'கேளுங்கள்', ui_mute: 'பேசுவதை நிறுத்து',
    greet1: 'வணக்கம்! 🙏 நான் <b>சோனா</b>, உங்கள் நகை உதவியாளர்.',
    greet2: 'தங்கம் வாங்குவது பற்றி எதையும் கேளுங்கள் — எந்த நகைக்கடையின் இன்றைய விலை, உங்கள் நகரில் மலிவான விலை, செய்கூலி, ஆஃபர்கள் அல்லது எந்த எடையின் விலையும். தட்டச்சு செய்யுங்கள், அல்லது 🎤 அழுத்திப் பேசுங்கள்.',
    lang_hint: 'உங்கள் மொழியிலேயே கேளுங்கள் — எழுதியோ பேசியோ — அதே மொழியில் பதில் தருகிறேன். இந்தி, ஆங்கிலம் தவிர வேறு மொழியில் பேசுவீர்களா? அதை ஒருமுறை தேர்ந்தெடுங்கள்:',
    ui_auto: 'தானாக (கண்டறி)',
    src: 'இன்றைய விலைகள் {n} நகைக்கடைகளிடமிருந்து, GST இல்லாமல் · {d}',
    med_h: 'இந்தியாவில் இன்றைய தங்க விலை, {n} நகைக்கடைகளின் நடு விலை:',
    med_low: 'தேசிய நகைக்கடைகளில் குறைந்த 22K: <b>{b}</b>, <b>{p}/கிராம்</b>.',
    brand_h: '<b>{b}</b> இன்று:',
    brand_rank: 'இன்று {n} நகைக்கடைகளில் இது <b>#{r}</b> இடத்தில் — {rel}.',
    rel_at: '{k} சந்தை நடு விலைக்குச் சமம்', rel_below: '{k} நடு விலையை விட {p}/கிராம் குறைவு', rel_above: '{k} நடு விலையை விட {p}/கிராம் அதிகம்',
    brand_mk: 'வழக்கமான செய்கூலி: {list}.',
    brand_off: 'அவர்கள் தளத்தில் ஆஃபர்: <b>{o}</b>.',
    brand_st: 'இந்த மாநிலங்களில்: {s}.',
    brand_link: '{b} 30 நாள் விலைகள் →',
    city_h: '<b>{c}</b> இல் இன்று மலிவான {k} ({note}):',
    city_loc: 'தேசிய நகைக்கடைகள் மற்றும் {s} இல் உள்ள {l} உள்ளூர் கடைகள்', city_nat: 'தேசிய நகைக்கடைகள்',
    city_link: '{c} முழுப் பட்டியல் →',
    cheap_h: 'தேசிய நகைக்கடைகளில் இன்று மலிவான {k}:',
    cheap_gap: 'மலிவானதற்கும் விலை அதிகமானதற்கும் 10 கிராமுக்கு <b>{p}</b> வித்தியாசம் — வாங்கும் முன் பாருங்கள்.',
    cmp_h: 'இன்று அருகருகே ({k}):', cmp_10: '10 கிராம்: {p}', cmp_mk: 'செய்கூலி ~{p}', cmp_nomk: 'செய்கூலி: அளவிடப்படவில்லை',
    cmp_win: '<b>{b}</b> இன் {k} விலை 10 கிராமுக்கு <b>{p}</b> குறைவு. இறுதி பில் நீங்கள் தேர்ந்தெடுக்கும் டிசைனின் செய்கூலியையும் பொறுத்தது.',
    mk_none: '<b>{b}</b> இன் செய்கூலியை நாங்கள் இன்னும் அளவிடவில்லை. இவற்றுக்கு அளவிட்டுள்ளோம்: {list}.',
    mk_link: 'செய்கூலி ஒப்பீடு →',
    mk_brand_h: '<b>{b}</b> இன் வழக்கமான செய்கூலி (உண்மைப் பொருட்களின் நடு அளவு, தங்க மதிப்பின் %):',
    mk_note: 'டிசைனைப் பொறுத்து மாறும்; பில்லில் அதிகம் பேரம் பேசக்கூடிய பகுதி இதுதான்.',
    mk_all: 'எல்லா நகைக்கடைகளையும் ஒப்பிடுக →',
    mk_h: '<b>{c}</b> க்கு குறைந்த செய்கூலி (உண்மைப் பொருட்களின் நடு அளவு):',
    mk_nocat: '<b>{c}</b> செய்கூலியை நாங்கள் இன்னும் அளக்கவில்லை. <b>{r}</b>க்கு இதோ:',
    mk_every: 'ஒவ்வொரு நகைக்கடையும் வகையும் →',
    bo_ask: 'எந்த நகைக்கு சிறந்த ஆஃபரைக் கண்டுபிடிக்கட்டும்?',
    bo_h: 'இன்றைய செய்கூலி ஆஃபர்களுக்குப் பின் <b>{w}</b> 22K <b>{c}</b> சிறந்த விலை:',
    bo_note: 'மொத்தம் = தங்கம் + ஆஃபருக்குப் பின் செய்கூலி + 3% GST. ஆஃபர் % தோராயமானது; * என்றால் “வரை”, சில வடிவமைப்புகளுக்கு மட்டும் (அடைப்புக்குள் சிறந்த நிலை). நகைக்கடையிடம் உறுதிசெய்யுங்கள்.',
    bo_none: '{c} செய்கூலி போதுமான நகைக்கடைகளுக்கு இன்னும் என்னிடம் இல்லை.',
    say_bo: '{w} 22K {c}க்கு ஆஃபருக்குப் பின் {b} மலிவானது, GST உடன் சுமார் {p}.',
    bo_upto: 'வரை',
    bo_noff: 'ஆஃபர் இல்லை',
    off_none: 'இன்று <b>{b}</b> இணையதளத்தில் எந்த ஆஃபரும் எழுதப்படவில்லை.',
    off_see: 'யாரிடம் ஆஃபர் உள்ளது பாருங்கள் →',
    off_brand_h: 'இன்று <b>{b}</b> இணையதளத்தில் உள்ள ஆஃபர்கள்:',
    off_page: 'அவர்கள் பக்கம் ↗', off_all: 'எல்லா நகைக்கடைகளின் ஆஃபர் ஒப்பீடு →',
    off_all_h: 'இன்று {n} நகைக்கடைகளின் சொந்த இணையதளங்களில் ஆஃபர்கள் உள்ளன (A–Z):',
    off_ring: 'எல்லா டிசைன்களுக்கும் பொருந்தும் ஆஃபர்களை மட்டும் சேர்த்து, இன்று 10 கிராம் 22K மோதிரம் குறைந்த விலையில் <b>{b}</b> இல்: GST உடன் {p}. “அப் டு” மற்றும் தேர்ந்தெடுத்த டிசைன் ஆஃபர்கள் நகைக்கு நகை மாறும் — கடையில் உறுதிசெய்யுங்கள்.',
    off_every: 'ஒவ்வொரு ஆஃபரும், அதன் உண்மையான அர்த்தமும் →',
    price_h: 'இன்று {who} இல் {w} {k}:', price_who: 'மலிவான தேசிய நகைக்கடை ({b})',
    price_gold: 'தங்கம் ({g} கிராம் × {p})', price_mk: 'செய்கூலி (~{p}, {c})', price_typ: 'வழக்கமான', price_total: 'மொத்தம்',
    price_nomk: 'செய்கூலி சேர்க்கப்படவில்லை — உங்கள் டிசைனுக்கான கூலியைச் சேர்க்கவும் (பெரும்பாலும் 8–25%).',
    trend_none: 'இன்னும் போதுமான வரலாறு இல்லை.', hist_link: 'தங்க விலை வரலாறு →',
    trend_h: '{k} சந்தை நடு விலை: இன்று <b>{p}/கிராம்</b>.',
    vs1: 'முந்தைய நாளை விட', vs7: '7 நாட்களுக்கு முன்பை விட', vs30: '30 நாட்களுக்கு முன்பை விட',
    trend_note: 'இவை கடந்த மாற்றங்கள், கணிப்பு அல்ல — நாளைய விலையை யாராலும் உறுதியாகச் சொல்ல முடியாது.',
    full_hist: 'முழு வரலாறு →',
    alerts: 'தினமும் காலையில் மலிவான நகைக்கடையும் இன்றைய விலையும், இலவசமாக — 22K உங்கள் விலைக்கு இறங்கும் நாளில் ஒரு மின்னஞ்சல்.',
    alerts_cta: 'இலவச தினசரி அலர்ட் பெறுங்கள்',
    more: 'மேலும் படிக்க →', guide_h: 'இந்த வழிகாட்டி இதைப் பற்றியது: <b>{t}</b> — {d}', guide_link: 'வழிகாட்டியைப் படிக்க →',
    en_only: 'இந்தப் பதில் இப்போதைக்கு ஆங்கிலத்தில்:', translated: 'உங்கள் சாதனத்திலேயே மொழிபெயர்க்கப்பட்டது',
    ask_city: 'நீங்கள் எந்த நகரில் இருக்கிறீர்கள்?',
    ch_loc: 'என் இருப்பிடம்', loc_wait: 'உங்கள் அருகிலுள்ள நகரத்தைத் தேடுகிறேன்…',
    loc_fail: 'இருப்பிடம் கிடைக்கவில்லை. உங்கள் நகரத்தின் பெயரை எழுதுங்கள் அல்லது தேர்ந்தெடுங்கள்:', ch_chcity: 'நகரத்தை மாற்று',
    silver: 'இப்போதைக்கு நான் தங்கம் பற்றி மட்டும் சொல்கிறேன் — நகைக்கடைகளின் 22K, 24K, 18K விலைகள். வெள்ளி விரைவில் வருகிறது.',
    hello: 'வணக்கம்! 🙏 நான் சோனா. தங்கம் வாங்குவது பற்றி எதையும் கேளுங்கள் — {n} நகைக்கடைகளின் இன்றைய விலைகள், உங்கள் நகரம், செய்கூலி, ஆஃபர்கள் அல்லது எந்த எடையின் விலையும்.',
    thanks: 'மகிழ்ச்சி! வேறு ஏதாவது?',
    about: 'நான் சோனா, MyGoldRates இன் உதவியாளர். இன்றைய உண்மைத் தரவிலிருந்து பதில் சொல்கிறேன் — {n} நகைக்கடைகளின் வெளியிட்ட விலைகள், உண்மைப் பொருட்களிலிருந்து அளந்த செய்கூலி, அவர்கள் இணையதள ஆஃபர்கள் — அதனால் எந்த எண்ணையும் ஊகிப்பதில்லை.',
    unknown: 'இதை நான் இன்னும் கற்றுக்கொண்டிருக்கிறேன் — உங்கள் கேள்வியைக் குறித்துக்கொண்டேன், விரைவில் சரியான பதிலைச் சேர்ப்போம். அதுவரை, இவற்றில் நான் நன்றாகப் பதில் சொல்வேன்:',
    nodata: 'இன்றைய தரவு ஏற்றப்படவில்லை. இணைய இணைப்பைச் சரிபார்த்து மீண்டும் முயலுங்கள்.',
    no_voice: 'இந்தச் சாதனத்தில் {l} குரல் இல்லை, அதனால் எழுத்தில் பதில் தருகிறேன்.',
    mic_denied: 'மைக் தடுக்கப்பட்டுள்ளது. உலாவி அமைப்புகளில் இந்தத் தளத்துக்கு மைக்கை அனுமதித்து, மீண்டும் 🎤 அழுத்துங்கள்.',
    mic_none: 'எனக்குக் கேட்கவில்லை — 🎤 அழுத்தி மீண்டும் பேசுங்கள்.',
    rupees: 'ரூபாய்', carat: 'கேரட்',
    say_med: 'இன்று {k} தங்கம் கிராமுக்கு சுமார் {p}, {n} நகைக்கடைகளின் நடு விலை. குறைந்தது {b} இல், {q}.',
    say_brand: '{b} இல் இன்று {k} தங்கம் கிராமுக்கு {p}, {n} கடைகளில் இடம் {r}.',
    say_city: '{c} இல் இன்று மலிவான {k} {b} இல், கிராமுக்கு {p}.',
    say_cheap: 'இன்று மலிவான {k} {b} இல், கிராமுக்கு {p}. 10 கிராமுக்கு விலை அதிகமான கடை {q} கூடுதலாக வாங்குகிறது.',
    say_cmp: '{b} மலிவு, 10 கிராம் {k} க்கு {p} குறைவு.',
    say_mk_brand: '{b} இல் {c} க்கு வழக்கமான செய்கூலி சுமார் {p}.',
    say_mk: '{c} க்கு குறைந்த செய்கூலி {b} இல், சுமார் {p}.',
    say_mk_none: '{b} இன் செய்கூலியை நாங்கள் இன்னும் அளவிடவில்லை.',
    say_off_all: 'இன்று {n} நகைக்கடைகளில் ஆஃபர்கள் உள்ளன. எல்லா டிசைன்களுக்கும் பொருந்தும் ஆஃபர்களை மட்டும் சேர்த்து, 10 கிராம் 22 கேரட் மோதிரம் குறைந்த விலையில் {b} இல்: GST உடன் {p}.',
    say_off_brand: 'இன்று {b} இணையதளத்தில் {n} ஆஃபர்கள் உள்ளன.',
    say_off_none: 'இன்று {b} இணையதளத்தில் எந்த ஆஃபரும் இல்லை.',
    say_price: '{b} இல் {w} {k} தங்கம் GST உடன் சுமார் {p} ஆகும்.',
    say_trend_up: 'இன்று {k} தங்கம் கிராமுக்கு {p}, முந்தைய நாளை விட {q} அதிகம்.',
    say_trend_dn: 'இன்று {k} தங்கம் கிராமுக்கு {p}, முந்தைய நாளை விட {q} குறைவு.',
    say_trend_same: 'இன்று {k} தங்கம் கிராமுக்கு {p}, முந்தைய நாளைப் போலவே.',
    u_g: '{n} கிராம்', u_tola: '{n} தோலா', u_sov: '{n} பவுன்', u_kg: '{n} கிலோ',
    c_Ring: 'மோதிரம்', c_Chain: 'செயின்', c_Bangle: 'வளையல்', c_Necklace: 'நெக்லஸ்', c_Earrings: 'கம்மல்',
    c_Mangalsutra: 'தாலி', c_Pendant: 'பெண்டன்ட்', c_Bracelet: 'பிரேஸ்லெட்', c_Coin: 'நாணயம்',
    ch_cheap22: 'இன்று மலிவான 22K', ch_mycity: 'என் நகரில் விலை', ch_tvk: 'தனிஷ்க் அல்லது கல்யாண்',
    ch_bestoff: 'இன்றைய சிறந்த ஆஃபர்', ch_p10chain: '10 கிராம் 22K செயின் விலை', ch_k22v24: '22K, 24K வித்தியாசம்?',
    ch_p10: '10 கிராம் 22K விலை', ch_afteroff: 'ஆஃபருக்குப் பின் விலை', ch_mkcmp: 'செய்கூலி ஒப்பீடு',
    ch_goodmk: 'செய்கூலியில் 20% தள்ளுபடி நல்லதா?', ch_whatmk: 'செய்கூலி என்றால் என்ன?', ch_alert: 'விலை அலர்ட் அமைக்க',
    ch_goodtime: 'இப்போது வாங்கலாமா?', ch_rate: 'இன்றைய தங்க விலை', ch_another: 'வேறு கடையில் இதே',
    ch_bmk: '{b} செய்கூலி', ch_boff: '{b} ஆஃபர்கள்'
  };

  S.te = {
    ui_sub: 'నగల సహాయకురాలు · ఈరోజు నిజమైన ధరల నుంచి సమాధానాలు',
    ui_ph: 'ధరలు, జ్యువెలర్లు, ఆఫర్ల గురించి అడగండి…',
    ui_listen: 'వింటున్నాను… మాట్లాడండి',
    ui_mic: 'మాట్లాడి అడగండి',
    ui_foot: 'ఉచితం · టైప్ చేయండి లేదా మాట్లాడండి · ప్రచురించిన డేటా నుంచి సమాధానాలు, సలహా కాదు',
    ui_lang: 'భాష', ui_speak: 'వినండి', ui_mute: 'చదవడం ఆపండి',
    greet1: 'నమస్కారం! 🙏 నేను <b>సోనా</b>, మీ నగల సహాయకురాలు.',
    greet2: 'బంగారం కొనడం గురించి ఏదైనా అడగండి — ఏ జ్యువెలర్ దగ్గరైనా ఈరోజు ధర, మీ నగరంలో చౌకైనది, మేకింగ్ చార్జీలు, ఆఫర్లు లేదా ఏ బరువుకైనా ధర. టైప్ చేయండి, లేదా 🎤 నొక్కి మాట్లాడండి.',
    lang_hint: 'మీ భాషలోనే అడగండి — రాసి లేదా మాట్లాడి — అదే భాషలో సమాధానం ఇస్తాను. హిందీ, ఇంగ్లీష్ కాకుండా వేరే భాష మాట్లాడతారా? దాన్ని ఒకసారి ఎంచుకోండి:',
    ui_auto: 'ఆటోమేటిక్ (గుర్తించు)',
    src: 'ఈరోజు ధరలు {n} జ్యువెలర్ల నుంచి, GST లేకుండా · {d}',
    med_h: 'భారతదేశంలో ఈరోజు బంగారం ధర, {n} జ్యువెలర్ల మధ్యస్థ ధర:',
    med_low: 'జాతీయ జ్యువెలర్లలో తక్కువ 22K: <b>{b}</b>, <b>{p}/గ్రాము</b>.',
    brand_h: '<b>{b}</b> ఈరోజు:',
    brand_rank: 'ఈరోజు {n} జ్యువెలర్లలో ఇది <b>#{r}</b> స్థానంలో ఉంది — {rel}.',
    rel_at: '{k} మార్కెట్ మధ్యస్థ ధరకు సమానం', rel_below: '{k} మధ్యస్థ ధర కంటే {p}/గ్రాము తక్కువ', rel_above: '{k} మధ్యస్థ ధర కంటే {p}/గ్రాము ఎక్కువ',
    brand_mk: 'సాధారణ మేకింగ్ చార్జీలు: {list}.',
    brand_off: 'వారి సైట్‌లో ఆఫర్: <b>{o}</b>.',
    brand_st: 'ఈ రాష్ట్రాల్లో: {s}.',
    brand_link: '{b} 30 రోజుల ధరలు →',
    city_h: '<b>{c}</b> లో ఈరోజు చౌకైన {k} ({note}):',
    city_loc: 'జాతీయ జ్యువెలర్లు మరియు {s} లోని {l} స్థానిక జ్యువెలర్లు', city_nat: 'జాతీయ జ్యువెలర్లు',
    city_link: '{c} పూర్తి జాబితా →',
    cheap_h: 'జాతీయ జ్యువెలర్లలో ఈరోజు చౌకైన {k}:',
    cheap_gap: 'చౌకైనదానికి, ఖరీదైనదానికి మధ్య 10 గ్రాములకు <b>{p}</b> తేడా ఉంది — కొనే ముందు చూడండి.',
    cmp_h: 'ఈరోజు పక్కపక్కనే ({k}):', cmp_10: '10 గ్రాములు: {p}', cmp_mk: 'మేకింగ్ ~{p}', cmp_nomk: 'మేకింగ్: కొలవలేదు',
    cmp_win: '<b>{b}</b> {k} ధర 10 గ్రాములకు <b>{p}</b> తక్కువ. తుది బిల్లు మీరు ఎంచుకునే డిజైన్ మేకింగ్ చార్జీపై కూడా ఆధారపడి ఉంటుంది.',
    mk_none: '<b>{b}</b> మేకింగ్ చార్జీలను మేము ఇంకా కొలవలేదు. వీటికి కొలిచాము: {list}.',
    mk_link: 'మేకింగ్ చార్జీల పోలిక →',
    mk_brand_h: '<b>{b}</b> సాధారణ మేకింగ్ చార్జీలు (నిజమైన ఉత్పత్తుల మధ్యస్థం, బంగారం విలువలో %):',
    mk_note: 'డిజైన్‌ను బట్టి మారుతుంది; బిల్లులో ఎక్కువగా బేరం ఆడగలిగే భాగం ఇదే.',
    mk_all: 'అన్ని జ్యువెలర్లను పోల్చండి →',
    mk_h: '<b>{c}</b> పై తక్కువ మేకింగ్ చార్జీలు (నిజమైన ఉత్పత్తుల మధ్యస్థం):',
    mk_nocat: '<b>{c}</b> మేకింగ్ చార్జీలు మేము ఇంకా కొలవలేదు. <b>{r}</b>కు ఇవి:',
    mk_every: 'ప్రతి జ్యువెలర్, ప్రతి రకం →',
    bo_ask: 'ఏ నగకు ఉత్తమ ఆఫర్ వెతకాలి?',
    bo_h: 'నేటి మేకింగ్ చార్జీ ఆఫర్ల తర్వాత <b>{w}</b> 22K <b>{c}</b> ఉత్తమ ధర:',
    bo_note: 'మొత్తం = బంగారం + ఆఫర్ తర్వాత మేకింగ్ చార్జీ + 3% GST. ఆఫర్ % అంచనా మాత్రమే; * అంటే “వరకు”, కొన్ని డిజైన్లకే (బ్రాకెట్‌లో ఉత్తమ స్థితి). జ్యువెలర్‌తో నిర్ధారించుకోండి.',
    bo_none: '{c} మేకింగ్ చార్జీలు ఇంకా తగినన్ని జ్యువెలర్లవి నా దగ్గర లేవు.',
    say_bo: '{w} 22K {c}కి ఆఫర్ తర్వాత {b} చౌక, GST తో సుమారు {p}.',
    bo_upto: 'వరకు',
    bo_noff: 'ఆఫర్ లేదు',
    off_none: 'ఈరోజు <b>{b}</b> వెబ్‌సైట్‌లో ఏ ఆఫర్ రాసి లేదు.',
    off_see: 'ఎవరి దగ్గర ఆఫర్ ఉందో చూడండి →',
    off_brand_h: 'ఈరోజు <b>{b}</b> వెబ్‌సైట్‌లోని ఆఫర్లు:',
    off_page: 'వారి పేజీ ↗', off_all: 'అన్ని జ్యువెలర్ల ఆఫర్ల పోలిక →',
    off_all_h: 'ఈరోజు {n} జ్యువెలర్ల సొంత వెబ్‌సైట్లలో ఆఫర్లు ఉన్నాయి (A–Z):',
    off_ring: 'అన్ని డిజైన్లకు వర్తించే ఆఫర్లు మాత్రమే కలిపి, ఈరోజు 10 గ్రాముల 22K ఉంగరం తక్కువ ధర <b>{b}</b> వద్ద: GST తో {p}. “అప్ టు” మరియు ఎంపిక చేసిన డిజైన్ల ఆఫర్లు నగను బట్టి మారుతాయి — జ్యువెలర్ వద్ద నిర్ధారించుకోండి.',
    off_every: 'ప్రతి ఆఫర్, దాని అసలు అర్థం →',
    price_h: 'ఈరోజు {who} వద్ద {w} {k}:', price_who: 'చౌకైన జాతీయ జ్యువెలర్ ({b})',
    price_gold: 'బంగారం ({g} గ్రా × {p})', price_mk: 'మేకింగ్ (~{p}, {c})', price_typ: 'సాధారణంగా', price_total: 'మొత్తం',
    price_nomk: 'మేకింగ్ చార్జీలు చేర్చలేదు — మీ డిజైన్ చార్జీ కలపండి (తరచుగా 8–25%).',
    trend_none: 'ఇంకా తగినంత చరిత్ర లేదు.', hist_link: 'బంగారం ధరల చరిత్ర →',
    trend_h: '{k} మార్కెట్ మధ్యస్థ ధర: ఈరోజు <b>{p}/గ్రాము</b>.',
    vs1: 'ముందు రోజుతో పోలిస్తే', vs7: '7 రోజుల క్రితంతో పోలిస్తే', vs30: '30 రోజుల క్రితంతో పోలిస్తే',
    trend_note: 'ఇవి గత మార్పులు, అంచనా కాదు — రేపటి ధరను ఎవరూ ఖచ్చితంగా చెప్పలేరు.',
    full_hist: 'పూర్తి చరిత్ర →',
    alerts: 'ప్రతి ఉదయం చౌకైన జ్యువెలర్, ఈరోజు ధర, ఉచితంగా — 22K మీ ధరకు దిగిన రోజు ఒక ఈమెయిల్.',
    alerts_cta: 'ఉచిత రోజువారీ అలర్ట్‌లు పొందండి',
    more: 'ఇంకా చదవండి →', guide_h: 'ఈ గైడ్ దీని గురించే: <b>{t}</b> — {d}', guide_link: 'గైడ్ చదవండి →',
    en_only: 'ఈ సమాధానం ప్రస్తుతానికి ఇంగ్లీష్‌లో ఉంది:', translated: 'మీ పరికరంలోనే అనువదించబడింది',
    ask_city: 'మీరు ఏ నగరంలో ఉన్నారు?',
    ch_loc: 'నా లొకేషన్ వాడండి', loc_wait: 'మీ దగ్గరి నగరాన్ని వెతుకుతున్నాను…',
    loc_fail: 'లొకేషన్ దొరకలేదు. మీ నగరం పేరు రాయండి లేదా ఎంచుకోండి:', ch_chcity: 'నగరం మార్చండి',
    silver: 'ప్రస్తుతానికి నేను బంగారం గురించి మాత్రమే చెబుతాను — జ్యువెలర్ల 22K, 24K, 18K ధరలు. వెండి త్వరలో వస్తుంది.',
    hello: 'నమస్కారం! 🙏 నేను సోనా. బంగారం కొనడం గురించి ఏదైనా అడగండి — {n} జ్యువెలర్ల ఈరోజు ధరలు, మీ నగరం, మేకింగ్ చార్జీలు, ఆఫర్లు లేదా ఏ బరువుకైనా ధర.',
    thanks: 'సంతోషం! ఇంకేమైనా?',
    about: 'నేను సోనా, MyGoldRates సహాయకురాలిని. ఈరోజు నిజమైన డేటా నుంచి సమాధానం ఇస్తాను — {n} జ్యువెలర్ల ప్రచురించిన ధరలు, నిజమైన ఉత్పత్తుల నుంచి కొలిచిన మేకింగ్ చార్జీలు, వారి వెబ్‌సైట్ ఆఫర్లు — అందుకే ఏ సంఖ్యనూ ఊహించను.',
    unknown: 'ఇది నేను ఇంకా నేర్చుకుంటున్నాను — మీ ప్రశ్నను నమోదు చేశాను, త్వరలో సరైన సమాధానం చేరుస్తాము. అప్పటి వరకు, వీటిలో నేను బాగా చెప్పగలను:',
    nodata: 'ఈరోజు డేటా లోడ్ కాలేదు. దయచేసి ఇంటర్నెట్ చూసి మళ్లీ ప్రయత్నించండి.',
    no_voice: 'ఈ పరికరంలో {l} గొంతు లేదు, కాబట్టి నేను రాసి సమాధానం ఇస్తాను.',
    mic_denied: 'మైక్ బ్లాక్ అయింది. బ్రౌజర్ సెట్టింగ్‌లలో ఈ సైట్‌కు మైక్ అనుమతించి, మళ్లీ 🎤 నొక్కండి.',
    mic_none: 'నాకు వినిపించలేదు — 🎤 నొక్కి మళ్లీ మాట్లాడండి.',
    rupees: 'రూపాయలు', carat: 'క్యారెట్',
    say_med: 'ఈరోజు {k} బంగారం గ్రాముకు సుమారు {p}, {n} జ్యువెలర్ల మధ్యస్థ ధర. తక్కువది {b} వద్ద, {q}.',
    say_brand: '{b} వద్ద ఈరోజు {k} బంగారం గ్రాముకు {p}, {n} జ్యువెలర్లలో స్థానం {r}.',
    say_city: '{c} లో ఈరోజు చౌకైన {k} {b} వద్ద, గ్రాముకు {p}.',
    say_cheap: 'ఈరోజు చౌకైన {k} {b} వద్ద, గ్రాముకు {p}. 10 గ్రాములకు ఖరీదైన జ్యువెలర్ {q} ఎక్కువ తీసుకుంటారు.',
    say_cmp: '{b} చౌక, 10 గ్రాముల {k} పై {p} తక్కువ.',
    say_mk_brand: '{b} వద్ద {c} పై సాధారణ మేకింగ్ చార్జీ సుమారు {p}.',
    say_mk: '{c} పై తక్కువ మేకింగ్ చార్జీ {b} వద్ద, సుమారు {p}.',
    say_mk_none: '{b} మేకింగ్ చార్జీలను మేము ఇంకా కొలవలేదు.',
    say_off_all: 'ఈరోజు {n} జ్యువెలర్ల వద్ద ఆఫర్లు ఉన్నాయి. అన్ని డిజైన్లకు వర్తించే ఆఫర్లు మాత్రమే కలిపి, 10 గ్రాముల 22 క్యారెట్ ఉంగరం తక్కువ ధర {b} వద్ద: GST తో {p}.',
    say_off_brand: 'ఈరోజు {b} వెబ్‌సైట్‌లో {n} ఆఫర్లు ఉన్నాయి.',
    say_off_none: 'ఈరోజు {b} వెబ్‌సైట్‌లో ఏ ఆఫర్ లేదు.',
    say_price: '{b} వద్ద {w} {k} బంగారం GST తో సుమారు {p} అవుతుంది.',
    say_trend_up: 'ఈరోజు {k} బంగారం గ్రాముకు {p}, ముందు రోజు కంటే {q} ఎక్కువ.',
    say_trend_dn: 'ఈరోజు {k} బంగారం గ్రాముకు {p}, ముందు రోజు కంటే {q} తక్కువ.',
    say_trend_same: 'ఈరోజు {k} బంగారం గ్రాముకు {p}, ముందు రోజు లాగానే.',
    u_g: '{n} గ్రాములు', u_tola: '{n} తులం', u_sov: '{n} సావరిన్', u_kg: '{n} కిలో',
    c_Ring: 'ఉంగరం', c_Chain: 'చైన్', c_Bangle: 'గాజులు', c_Necklace: 'నెక్లెస్', c_Earrings: 'చెవిపోగులు',
    c_Mangalsutra: 'మంగళసూత్రం', c_Pendant: 'పెండెంట్', c_Bracelet: 'బ్రేస్లెట్', c_Coin: 'నాణెం',
    ch_cheap22: 'ఈరోజు చౌకైన 22K', ch_mycity: 'నా నగరంలో ధర', ch_tvk: 'తనిష్క్ లేదా కళ్యాణ్',
    ch_bestoff: 'ఈరోజు ఉత్తమ ఆఫర్', ch_p10chain: '10 గ్రాముల 22K చైన్ ధర', ch_k22v24: '22K, 24K తేడా?',
    ch_p10: '10 గ్రాముల 22K ధర', ch_afteroff: 'ఆఫర్ తర్వాత ధర', ch_mkcmp: 'మేకింగ్ చార్జీల పోలిక',
    ch_goodmk: 'మేకింగ్‌పై 20% తగ్గింపు మంచిదేనా?', ch_whatmk: 'మేకింగ్ చార్జీలు అంటే ఏమిటి?', ch_alert: 'ధర అలర్ట్ పెట్టండి',
    ch_goodtime: 'ఇప్పుడు కొనడం మంచిదేనా?', ch_rate: 'ఈరోజు బంగారం ధర', ch_another: 'వేరే జ్యువెలర్ వద్ద ఇదే',
    ch_bmk: '{b} మేకింగ్ చార్జీలు', ch_boff: '{b} ఆఫర్లు'
  };

  S.ml = {
    ui_sub: 'ആഭരണ സഹായി · ഇന്നത്തെ യഥാർത്ഥ വിലകളിൽ നിന്ന് ഉത്തരം',
    ui_ph: 'വില, ജ്വല്ലറികൾ, ഓഫറുകൾ എന്നിവയെക്കുറിച്ച് ചോദിക്കൂ…',
    ui_listen: 'കേൾക്കുന്നു… സംസാരിക്കൂ',
    ui_mic: 'സംസാരിച്ച് ചോദിക്കൂ',
    ui_foot: 'സൗജന്യം · ടൈപ്പ് ചെയ്യൂ അല്ലെങ്കിൽ സംസാരിക്കൂ · പ്രസിദ്ധീകരിച്ച വിവരങ്ങളിൽ നിന്ന് ഉത്തരം, ഉപദേശമല്ല',
    ui_lang: 'ഭാഷ', ui_speak: 'കേൾക്കൂ', ui_mute: 'വായന നിർത്തൂ',
    greet1: 'നമസ്കാരം! 🙏 ഞാൻ <b>സോണ</b>, നിങ്ങളുടെ ആഭരണ സഹായി.',
    greet2: 'സ്വർണം വാങ്ങുന്നതിനെക്കുറിച്ച് എന്തും ചോദിക്കൂ — ഏത് ജ്വല്ലറിയുടെയും ഇന്നത്തെ വില, നിങ്ങളുടെ നഗരത്തിലെ കുറഞ്ഞ വില, പണിക്കൂലി, ഓഫറുകൾ, അല്ലെങ്കിൽ ഏത് തൂക്കത്തിന്റെയും വില. ടൈപ്പ് ചെയ്യൂ, അല്ലെങ്കിൽ 🎤 അമർത്തി സംസാരിക്കൂ.',
    lang_hint: 'നിങ്ങളുടെ ഭാഷയിൽ തന്നെ ചോദിക്കൂ — എഴുതിയോ സംസാരിച്ചോ — അതേ ഭാഷയിൽ ഞാൻ മറുപടി നൽകാം. ഹിന്ദിയോ ഇംഗ്ലീഷോ അല്ലാത്ത ഭാഷയിലാണോ സംസാരിക്കുന്നത്? അത് ഒരിക്കൽ തിരഞ്ഞെടുക്കൂ:',
    ui_auto: 'സ്വയം (കണ്ടെത്തും)',
    src: 'ഇന്നത്തെ വിലകൾ {n} ജ്വല്ലറികളിൽ നിന്ന്, GST കൂടാതെ · {d}',
    med_h: 'ഇന്ത്യയിൽ ഇന്നത്തെ സ്വർണവില, {n} ജ്വല്ലറികളുടെ മധ്യവില:',
    med_low: 'ദേശീയ ജ്വല്ലറികളിൽ കുറഞ്ഞ 22K: <b>{b}</b>, <b>{p}/ഗ്രാം</b>.',
    brand_h: '<b>{b}</b> ഇന്ന്:',
    brand_rank: 'ഇന്ന് {n} ജ്വല്ലറികളിൽ ഇത് <b>#{r}</b> സ്ഥാനത്താണ് — {rel}.',
    rel_at: '{k} വിപണിയിലെ മധ്യവിലയ്ക്ക് തുല്യം', rel_below: '{k} മധ്യവിലയേക്കാൾ {p}/ഗ്രാം കുറവ്', rel_above: '{k} മധ്യവിലയേക്കാൾ {p}/ഗ്രാം കൂടുതൽ',
    brand_mk: 'സാധാരണ പണിക്കൂലി: {list}.',
    brand_off: 'അവരുടെ സൈറ്റിലെ ഓഫർ: <b>{o}</b>.',
    brand_st: 'ഈ സംസ്ഥാനങ്ങളിൽ: {s}.',
    brand_link: '{b} 30 ദിവസത്തെ വിലകൾ →',
    city_h: '<b>{c}</b> ൽ ഇന്ന് കുറഞ്ഞ {k} ({note}):',
    city_loc: 'ദേശീയ ജ്വല്ലറികളും {s} ലെ {l} പ്രാദേശിക ജ്വല്ലറികളും', city_nat: 'ദേശീയ ജ്വല്ലറികൾ',
    city_link: '{c} മുഴുവൻ പട്ടിക →',
    cheap_h: 'ദേശീയ ജ്വല്ലറികളിൽ ഇന്ന് കുറഞ്ഞ {k}:',
    cheap_gap: 'കുറഞ്ഞതും കൂടിയതും തമ്മിൽ 10 ഗ്രാമിന് <b>{p}</b> വ്യത്യാസമുണ്ട് — വാങ്ങുന്നതിന് മുമ്പ് നോക്കൂ.',
    cmp_h: 'ഇന്ന് അടുത്തടുത്ത് ({k}):', cmp_10: '10 ഗ്രാം: {p}', cmp_mk: 'പണിക്കൂലി ~{p}', cmp_nomk: 'പണിക്കൂലി: അളന്നിട്ടില്ല',
    cmp_win: '<b>{b}</b> ന്റെ {k} വില 10 ഗ്രാമിന് <b>{p}</b> കുറവാണ്. അന്തിമ ബിൽ നിങ്ങൾ തിരഞ്ഞെടുക്കുന്ന ഡിസൈനിന്റെ പണിക്കൂലിയെയും ആശ്രയിച്ചിരിക്കും.',
    mk_none: '<b>{b}</b> ന്റെ പണിക്കൂലി ഞങ്ങൾ ഇതുവരെ അളന്നിട്ടില്ല. ഇവയുടേത് അളന്നിട്ടുണ്ട്: {list}.',
    mk_link: 'പണിക്കൂലി താരതമ്യം →',
    mk_brand_h: '<b>{b}</b> ന്റെ സാധാരണ പണിക്കൂലി (യഥാർത്ഥ ഉൽപ്പന്നങ്ങളുടെ മധ്യമൂല്യം, സ്വർണവിലയുടെ %):',
    mk_note: 'ഡിസൈൻ അനുസരിച്ച് മാറും; ബില്ലിൽ ഏറ്റവും കൂടുതൽ വിലപേശാവുന്ന ഭാഗം ഇതാണ്.',
    mk_all: 'എല്ലാ ജ്വല്ലറികളും താരതമ്യം ചെയ്യൂ →',
    mk_h: '<b>{c}</b> ന് കുറഞ്ഞ പണിക്കൂലി (യഥാർത്ഥ ഉൽപ്പന്നങ്ങളുടെ മധ്യമൂല്യം):',
    mk_nocat: '<b>{c}</b> പണിക്കൂലി ഞങ്ങൾ ഇതുവരെ അളന്നിട്ടില്ല. <b>{r}</b>യുടേത് ഇതാ:',
    mk_every: 'എല്ലാ ജ്വല്ലറികളും വിഭാഗങ്ങളും →',
    bo_ask: 'ഏത് ആഭരണത്തിനാണ് മികച്ച ഓഫർ കണ്ടെത്തേണ്ടത്?',
    bo_h: 'ഇന്നത്തെ പണിക്കൂലി ഓഫറുകൾക്ക് ശേഷം <b>{w}</b> 22K <b>{c}</b> മികച്ച വില:',
    bo_note: 'ആകെ = സ്വർണം + ഓഫറിന് ശേഷമുള്ള പണിക്കൂലി + 3% GST. ഓഫർ % ഏകദേശമാണ്; * എന്നാൽ “വരെ”, ചില ഡിസൈനുകൾക്ക് മാത്രം (ബ്രാക്കറ്റിൽ മികച്ച നില). ജ്വല്ലറിയിൽ ഉറപ്പാക്കുക.',
    bo_none: '{c} പണിക്കൂലി വേണ്ടത്ര ജ്വല്ലറികളുടേത് ഇതുവരെ എന്റെ പക്കലില്ല.',
    say_bo: '{w} 22K {c}ന് ഓഫറിന് ശേഷം {b} ആണ് വിലകുറഞ്ഞത്, GST ഉൾപ്പെടെ ഏകദേശം {p}.',
    bo_upto: 'വരെ',
    bo_noff: 'ഓഫർ ഇല്ല',
    off_none: 'ഇന്ന് <b>{b}</b> ന്റെ വെബ്സൈറ്റിൽ ഓഫറൊന്നും എഴുതിയിട്ടില്ല.',
    off_see: 'ആർക്കൊക്കെ ഓഫറുണ്ടെന്ന് നോക്കൂ →',
    off_brand_h: 'ഇന്ന് <b>{b}</b> ന്റെ വെബ്സൈറ്റിലെ ഓഫറുകൾ:',
    off_page: 'അവരുടെ പേജ് ↗', off_all: 'എല്ലാ ജ്വല്ലറികളുടെയും ഓഫറുകൾ താരതമ്യം →',
    off_all_h: 'ഇന്ന് {n} ജ്വല്ലറികളുടെ സ്വന്തം വെബ്സൈറ്റുകളിൽ ഓഫറുകളുണ്ട് (A–Z):',
    off_ring: 'എല്ലാ ഡിസൈനുകൾക്കും ബാധകമായ ഓഫറുകൾ മാത്രം ചേർത്ത്, ഇന്ന് 10 ഗ്രാം 22K മോതിരം ഏറ്റവും കുറവ് <b>{b}</b> ൽ: GST ഉൾപ്പെടെ {p}. “അപ് ടു”, തിരഞ്ഞെടുത്ത ഡിസൈൻ ഓഫറുകൾ ആഭരണം അനുസരിച്ച് മാറും — ജ്വല്ലറിയിൽ ഉറപ്പാക്കൂ.',
    off_every: 'എല്ലാ ഓഫറുകളും, അവയുടെ യഥാർത്ഥ അർത്ഥവും →',
    price_h: 'ഇന്ന് {who} ൽ {w} {k}:', price_who: 'ഏറ്റവും കുറഞ്ഞ ദേശീയ ജ്വല്ലറി ({b})',
    price_gold: 'സ്വർണം ({g} ഗ്രാം × {p})', price_mk: 'പണിക്കൂലി (~{p}, {c})', price_typ: 'സാധാരണ', price_total: 'ആകെ',
    price_nomk: 'പണിക്കൂലി ഉൾപ്പെടുത്തിയിട്ടില്ല — നിങ്ങളുടെ ഡിസൈനിന്റെ കൂലി ചേർക്കൂ (പലപ്പോഴും 8–25%).',
    trend_none: 'ആവശ്യത്തിന് ചരിത്രം ഇനിയും ഇല്ല.', hist_link: 'സ്വർണവില ചരിത്രം →',
    trend_h: '{k} വിപണി മധ്യവില: ഇന്ന് <b>{p}/ഗ്രാം</b>.',
    vs1: 'തലേ ദിവസത്തേക്കാൾ', vs7: '7 ദിവസം മുമ്പത്തേക്കാൾ', vs30: '30 ദിവസം മുമ്പത്തേക്കാൾ',
    trend_note: 'ഇവ കഴിഞ്ഞ മാറ്റങ്ങളാണ്, പ്രവചനമല്ല — നാളത്തെ വില ആർക്കും ഉറപ്പിച്ച് പറയാനാവില്ല.',
    full_hist: 'മുഴുവൻ ചരിത്രം →',
    alerts: 'എല്ലാ ദിവസവും രാവിലെ ഏറ്റവും കുറഞ്ഞ ജ്വല്ലറിയും ഇന്നത്തെ വിലയും, സൗജന്യമായി — 22K നിങ്ങളുടെ വിലയിലേക്ക് താഴുന്ന ദിവസം ഒരു ഇമെയിലും.',
    alerts_cta: 'സൗജന്യ ദൈനംദിന അലർട്ട് നേടൂ',
    more: 'കൂടുതൽ വായിക്കൂ →', guide_h: 'ഈ ഗൈഡ് ഇതിനെക്കുറിച്ചാണ്: <b>{t}</b> — {d}', guide_link: 'ഗൈഡ് വായിക്കൂ →',
    en_only: 'ഈ ഉത്തരം ഇപ്പോൾ ഇംഗ്ലീഷിലാണ്:', translated: 'നിങ്ങളുടെ ഉപകരണത്തിൽ തന്നെ വിവർത്തനം ചെയ്തത്',
    ask_city: 'നിങ്ങൾ ഏത് നഗരത്തിലാണ്?',
    ch_loc: 'എന്റെ ലൊക്കേഷൻ', loc_wait: 'നിങ്ങളുടെ അടുത്തുള്ള നഗരം തിരയുന്നു…',
    loc_fail: 'ലൊക്കേഷൻ കിട്ടിയില്ല. നിങ്ങളുടെ നഗരത്തിന്റെ പേര് എഴുതുക അല്ലെങ്കിൽ തിരഞ്ഞെടുക്കുക:', ch_chcity: 'നഗരം മാറ്റുക',
    silver: 'ഇപ്പോൾ ഞാൻ സ്വർണത്തെക്കുറിച്ച് മാത്രമേ പറയൂ — ജ്വല്ലറികളുടെ 22K, 24K, 18K വിലകൾ. വെള്ളി ഉടൻ വരുന്നു.',
    hello: 'നമസ്കാരം! 🙏 ഞാൻ സോണ. സ്വർണം വാങ്ങുന്നതിനെക്കുറിച്ച് എന്തും ചോദിക്കൂ — {n} ജ്വല്ലറികളുടെ ഇന്നത്തെ വിലകൾ, നിങ്ങളുടെ നഗരം, പണിക്കൂലി, ഓഫറുകൾ, അല്ലെങ്കിൽ ഏത് തൂക്കത്തിന്റെയും വില.',
    thanks: 'സന്തോഷം! മറ്റെന്തെങ്കിലും?',
    about: 'ഞാൻ സോണ, MyGoldRates ന്റെ സഹായി. ഇന്നത്തെ യഥാർത്ഥ വിവരങ്ങളിൽ നിന്നാണ് ഞാൻ ഉത്തരം നൽകുന്നത് — {n} ജ്വല്ലറികളുടെ പ്രസിദ്ധീകരിച്ച വിലകൾ, യഥാർത്ഥ ഉൽപ്പന്നങ്ങളിൽ നിന്ന് അളന്ന പണിക്കൂലി, അവരുടെ വെബ്സൈറ്റിലെ ഓഫറുകൾ — അതിനാൽ ഒരു സംഖ്യയും ഊഹിക്കില്ല.',
    unknown: 'ഇത് ഞാൻ ഇപ്പോഴും പഠിക്കുകയാണ് — നിങ്ങളുടെ ചോദ്യം കുറിച്ചെടുത്തു, ഉടൻ ശരിയായ ഉത്തരം ചേർക്കും. അതുവരെ, ഇവയിൽ എനിക്ക് നന്നായി സഹായിക്കാനാകും:',
    nodata: 'ഇന്നത്തെ വിവരങ്ങൾ ലോഡ് ആയില്ല. ഇന്റർനെറ്റ് പരിശോധിച്ച് വീണ്ടും ശ്രമിക്കൂ.',
    no_voice: 'ഈ ഉപകരണത്തിൽ {l} ശബ്ദമില്ല, അതിനാൽ ഞാൻ എഴുതി ഉത്തരം നൽകാം.',
    mic_denied: 'മൈക്ക് തടഞ്ഞിരിക്കുന്നു. ബ്രൗസർ ക്രമീകരണങ്ങളിൽ ഈ സൈറ്റിന് മൈക്ക് അനുവദിച്ച്, വീണ്ടും 🎤 അമർത്തൂ.',
    mic_none: 'എനിക്ക് കേൾക്കാനായില്ല — 🎤 അമർത്തി വീണ്ടും സംസാരിക്കൂ.',
    rupees: 'രൂപ', carat: 'കാരറ്റ്',
    say_med: 'ഇന്ന് {k} സ്വർണം ഗ്രാമിന് ഏകദേശം {p}, {n} ജ്വല്ലറികളുടെ മധ്യവില. ഏറ്റവും കുറവ് {b} ൽ, {q}.',
    say_brand: '{b} ൽ ഇന്ന് {k} സ്വർണം ഗ്രാമിന് {p}, {n} ജ്വല്ലറികളിൽ സ്ഥാനം {r}.',
    say_city: '{c} ൽ ഇന്ന് കുറഞ്ഞ {k} {b} ൽ, ഗ്രാമിന് {p}.',
    say_cheap: 'ഇന്ന് കുറഞ്ഞ {k} {b} ൽ, ഗ്രാമിന് {p}. 10 ഗ്രാമിന് ഏറ്റവും വിലകൂടിയ ജ്വല്ലറി {q} കൂടുതൽ വാങ്ങുന്നു.',
    say_cmp: '{b} ആണ് കുറവ്, 10 ഗ്രാം {k} ന് {p} കുറവ്.',
    say_mk_brand: '{b} ൽ {c} ന് സാധാരണ പണിക്കൂലി ഏകദേശം {p}.',
    say_mk: '{c} ന് കുറഞ്ഞ പണിക്കൂലി {b} ൽ, ഏകദേശം {p}.',
    say_mk_none: '{b} ന്റെ പണിക്കൂലി ഞങ്ങൾ ഇതുവരെ അളന്നിട്ടില്ല.',
    say_off_all: 'ഇന്ന് {n} ജ്വല്ലറികളിൽ ഓഫറുകളുണ്ട്. എല്ലാ ഡിസൈനുകൾക്കും ബാധകമായ ഓഫറുകൾ മാത്രം ചേർത്ത്, 10 ഗ്രാം 22 കാരറ്റ് മോതിരം ഏറ്റവും കുറവ് {b} ൽ: GST ഉൾപ്പെടെ {p}.',
    say_off_brand: 'ഇന്ന് {b} ന്റെ വെബ്സൈറ്റിൽ {n} ഓഫറുകളുണ്ട്.',
    say_off_none: 'ഇന്ന് {b} ന്റെ വെബ്സൈറ്റിൽ ഓഫറൊന്നുമില്ല.',
    say_price: '{b} ൽ {w} {k} സ്വർണത്തിന് GST ഉൾപ്പെടെ ഏകദേശം {p} ആകും.',
    say_trend_up: 'ഇന്ന് {k} സ്വർണം ഗ്രാമിന് {p}, തലേ ദിവസത്തേക്കാൾ {q} കൂടുതൽ.',
    say_trend_dn: 'ഇന്ന് {k} സ്വർണം ഗ്രാമിന് {p}, തലേ ദിവസത്തേക്കാൾ {q} കുറവ്.',
    say_trend_same: 'ഇന്ന് {k} സ്വർണം ഗ്രാമിന് {p}, തലേ ദിവസത്തെ പോലെ തന്നെ.',
    u_g: '{n} ഗ്രാം', u_tola: '{n} തോല', u_sov: '{n} പവൻ', u_kg: '{n} കിലോ',
    c_Ring: 'മോതിരം', c_Chain: 'മാല', c_Bangle: 'വള', c_Necklace: 'നെക്ലേസ്', c_Earrings: 'കമ്മൽ',
    c_Mangalsutra: 'താലി', c_Pendant: 'ലോക്കറ്റ്', c_Bracelet: 'ബ്രേസ്ലെറ്റ്', c_Coin: 'നാണയം',
    ch_cheap22: 'ഇന്ന് കുറഞ്ഞ 22K', ch_mycity: 'എന്റെ നഗരത്തിലെ വില', ch_tvk: 'തനിഷ്ക് അല്ലെങ്കിൽ കല്യാൺ',
    ch_bestoff: 'ഇന്നത്തെ മികച്ച ഓഫർ', ch_p10chain: '10 ഗ്രാം 22K മാലയുടെ വില', ch_k22v24: '22K, 24K വ്യത്യാസം?',
    ch_p10: '10 ഗ്രാം 22K വില', ch_afteroff: 'ഓഫറിന് ശേഷമുള്ള വില', ch_mkcmp: 'പണിക്കൂലി താരതമ്യം',
    ch_goodmk: 'പണിക്കൂലിയിൽ 20% കിഴിവ് നല്ലതാണോ?', ch_whatmk: 'പണിക്കൂലി എന്നാൽ എന്ത്?', ch_alert: 'വില അലർട്ട് വെക്കൂ',
    ch_goodtime: 'ഇപ്പോൾ വാങ്ങുന്നത് നല്ലതാണോ?', ch_rate: 'ഇന്നത്തെ സ്വർണവില', ch_another: 'മറ്റൊരു ജ്വല്ലറിയിൽ ഇതേ',
    ch_bmk: '{b} പണിക്കൂലി', ch_boff: '{b} ഓഫറുകൾ'
  };

  S.ur = {
    ui_sub: 'زیورات کی اسسٹنٹ · آج کے اصل بھاؤ سے جواب',
    ui_ph: 'بھاؤ، جیولرز، آفرز کے بارے میں پوچھیں…',
    ui_listen: 'سن رہی ہوں… بولیے',
    ui_mic: 'بول کر پوچھیں',
    ui_foot: 'مفت · لکھیں یا بولیں · شائع شدہ اعداد و شمار سے جواب، مشورہ نہیں',
    ui_lang: 'زبان', ui_speak: 'سنیں', ui_mute: 'بولنا بند کریں',
    greet1: 'آداب! 🙏 میں <b>سونا</b> ہوں، آپ کی زیورات کی اسسٹنٹ۔',
    greet2: 'سونا خریدنے سے متعلق کچھ بھی پوچھیے — کسی بھی جیولر کا آج کا بھاؤ، آپ کے شہر میں سب سے سستا، میکنگ چارج، آفرز یا کسی بھی وزن کی قیمت۔ لکھیے، یا 🎤 دبا کر بولیے۔',
    lang_hint: 'اپنی زبان میں پوچھیے — لکھ کر یا بول کر — میں اسی زبان میں جواب دوں گی۔ ہندی یا انگریزی کے علاوہ کوئی اور زبان بولنی ہے؟ اسے ایک بار چنیں:',
    ui_auto: 'خودکار (پہچانیں)',
    src: 'آج کے بھاؤ {n} جیولرز سے، GST سے پہلے · {d}',
    med_h: 'بھارت میں آج سونے کا بھاؤ، {n} جیولرز کا درمیانی بھاؤ:',
    med_low: 'قومی جیولرز میں سب سے کم 22K: <b>{b}</b>، <b>{p}/گرام</b>۔',
    brand_h: '<b>{b}</b> آج:',
    brand_rank: 'آج {n} جیولرز میں یہ <b>#{r}</b> پر ہے — {rel}۔',
    rel_at: '{k} کے بازار کے درمیانی بھاؤ کے برابر', rel_below: '{k} کے درمیانی بھاؤ سے {p}/گرام کم', rel_above: '{k} کے درمیانی بھاؤ سے {p}/گرام زیادہ',
    brand_mk: 'عام میکنگ چارج: {list}۔',
    brand_off: 'ان کی سائٹ پر آفر: <b>{o}</b>۔',
    brand_st: 'ان ریاستوں میں: {s}۔',
    brand_link: '{b} کے 30 دن کے بھاؤ ←',
    city_h: '<b>{c}</b> میں آج سب سے سستا {k} ({note}):',
    city_loc: 'قومی جیولرز اور {s} کے {l} مقامی جیولرز', city_nat: 'قومی جیولرز',
    city_link: '{c} کی پوری فہرست ←',
    cheap_h: 'قومی جیولرز میں آج سب سے سستا {k}:',
    cheap_gap: 'سب سے سستے اور سب سے مہنگے میں 10 گرام پر <b>{p}</b> کا فرق ہے — خریدنے سے پہلے ضرور دیکھیں۔',
    cmp_h: 'آج آمنے سامنے ({k}):', cmp_10: '10 گرام: {p}', cmp_mk: 'میکنگ ~{p}', cmp_nomk: 'میکنگ: ناپا نہیں گیا',
    cmp_win: '<b>{b}</b> کا {k} بھاؤ 10 گرام پر <b>{p}</b> کم ہے۔ آخری بل آپ کے چنے ہوئے ڈیزائن کے میکنگ چارج پر بھی منحصر ہے۔',
    mk_none: '<b>{b}</b> کا میکنگ چارج ہم نے ابھی نہیں ناپا۔ ان کا ناپا ہے: {list}۔',
    mk_link: 'میکنگ چارج کا موازنہ ←',
    mk_brand_h: '<b>{b}</b> کا عام میکنگ چارج (اصل پروڈکٹس کا درمیانی عدد، سونے کی قیمت کا %):',
    mk_note: 'ڈیزائن کے حساب سے بدلتا ہے؛ بل میں اسی پر سب سے زیادہ مول بھاؤ ہو سکتا ہے۔',
    mk_all: 'تمام جیولرز کا موازنہ ←',
    mk_h: '<b>{c}</b> پر سب سے کم میکنگ چارج (اصل پروڈکٹس کا درمیانی عدد):',
    mk_nocat: '<b>{c}</b> کا میکنگ چارج ہم نے ابھی نہیں ناپا۔ <b>{r}</b> کا یہ ہے:',
    mk_every: 'ہر جیولر اور ہر قسم ←',
    bo_ask: 'کس زیور پر بہترین آفر نکالوں؟',
    bo_h: 'آج کے میکنگ چارج آفرز کے بعد <b>{w}</b> 22K <b>{c}</b> کی بہترین قیمت:',
    bo_note: 'کل = سونا + آفر کے بعد میکنگ چارج + 3% GST. آفر % اندازاً ہے؛ * یعنی “تک”، صرف کچھ ڈیزائنوں پر (قوسین میں بہترین صورت). جیولر سے تصدیق کریں.',
    bo_none: '{c} کے میکنگ چارج ابھی کافی جیولرز کے میرے پاس نہیں ہیں.',
    say_bo: '{w} 22K {c} کے لیے آفر کے بعد {b} سب سے سستا ہے، GST سمیت تقریباً {p}.',
    bo_upto: 'تک',
    bo_noff: 'کوئی آفر نہیں',
    off_none: 'آج <b>{b}</b> کی ویب سائٹ پر کوئی آفر لکھی ہوئی نہیں ہے۔',
    off_see: 'دیکھیں کس کے پاس آفر ہے ←',
    off_brand_h: 'آج <b>{b}</b> کی ویب سائٹ پر آفرز:',
    off_page: 'ان کا صفحہ ↗', off_all: 'تمام جیولرز کی آفرز کا موازنہ ←',
    off_all_h: 'آج {n} جیولرز کی اپنی ویب سائٹ پر آفرز ہیں (A–Z):',
    off_ring: 'صرف ہر ڈیزائن پر لاگو آفرز گن کر، آج 10 گرام 22K انگوٹھی سب سے کم <b>{b}</b> پر ہے: GST کے ساتھ {p}۔ “اپ ٹو” اور منتخب ڈیزائن والی آفرز ہر زیور پر الگ ہوتی ہیں — جیولر سے پکا کر لیں۔',
    off_every: 'ہر آفر، اور اس کا اصل مطلب ←',
    price_h: 'آج {who} پر {w} {k}:', price_who: 'سب سے سستا قومی جیولر ({b})',
    price_gold: 'سونا ({g} گرام × {p})', price_mk: 'میکنگ (~{p}، {c})', price_typ: 'عام طور پر', price_total: 'کل',
    price_nomk: 'میکنگ چارج شامل نہیں — اپنے ڈیزائن کا چارج جوڑیں (اکثر 8–25%)۔',
    trend_none: 'ابھی کافی تاریخ نہیں ہے۔', hist_link: 'سونے کے بھاؤ کی تاریخ ←',
    trend_h: '{k} کا بازار کا درمیانی بھاؤ: آج <b>{p}/گرام</b>۔',
    vs1: 'پچھلے دن سے', vs7: '7 دن پہلے سے', vs30: '30 دن پہلے سے',
    trend_note: 'یہ گزری ہوئی تبدیلی ہے، پیش گوئی نہیں — کل کا بھاؤ کوئی یقین سے نہیں بتا سکتا۔',
    full_hist: 'پوری تاریخ ←',
    alerts: 'ہر صبح سب سے سستا جیولر اور آج کا بھاؤ، مفت — اور جس دن 22K آپ کے بھاؤ تک گرے، اس دن ای میل۔',
    alerts_cta: 'مفت روزانہ الرٹ پائیں',
    more: 'مزید پڑھیں ←', guide_h: 'یہ گائیڈ اسی بارے میں ہے: <b>{t}</b> — {d}', guide_link: 'گائیڈ پڑھیں ←',
    en_only: 'یہ جواب ابھی انگریزی میں ہے:', translated: 'آپ کے ڈیوائس پر ترجمہ کیا گیا',
    ask_city: 'آپ کس شہر میں ہیں؟',
    ch_loc: 'میری لوکیشن سے', loc_wait: 'آپ کا قریبی شہر ڈھونڈ رہی ہوں…',
    loc_fail: 'لوکیشن نہیں ملی۔ اپنے شہر کا نام لکھیے یا چنیے:', ch_chcity: 'شہر بدلیں',
    silver: 'ابھی میں صرف سونے کی معلومات دیتی ہوں — جیولرز کے 22K، 24K اور 18K بھاؤ۔ چاندی جلد آ رہی ہے۔',
    hello: 'آداب! 🙏 میں سونا ہوں۔ سونا خریدنے سے متعلق کچھ بھی پوچھیے — {n} جیولرز کے آج کے بھاؤ، آپ کا شہر، میکنگ چارج، آفرز یا کسی بھی وزن کی قیمت۔',
    thanks: 'خوشی ہوئی! اور کچھ؟',
    about: 'میں سونا ہوں، MyGoldRates کی اسسٹنٹ۔ میں آج کے اصل اعداد و شمار سے جواب دیتی ہوں — {n} جیولرز کے شائع شدہ بھاؤ، اصل پروڈکٹس سے ناپے گئے میکنگ چارج، اور ان کی ویب سائٹ کی آفرز — اس لیے میں کوئی عدد اندازے سے نہیں بتاتی۔',
    unknown: 'یہ میں ابھی سیکھ رہی ہوں — آپ کا سوال نوٹ کر لیا ہے تاکہ جلد صحیح جواب جوڑ سکیں۔ تب تک، ان میں میں اچھی ہوں:',
    nodata: 'آج کے اعداد و شمار لوڈ نہیں ہو سکے۔ براہ کرم انٹرنیٹ دیکھ کر پھر کوشش کریں۔',
    no_voice: 'اس ڈیوائس میں {l} آواز نہیں ہے، اس لیے میں لکھ کر جواب دوں گی۔',
    mic_denied: 'مائیک بند ہے۔ براؤزر کی سیٹنگز میں اس سائٹ کے لیے مائیک چالو کریں، پھر 🎤 دبائیں۔',
    mic_none: 'میں سن نہیں پائی — 🎤 دبا کر پھر بولیے۔',
    rupees: 'روپے', carat: 'قیراط',
    say_med: 'آج {k} سونا تقریباً {p} فی گرام ہے، {n} جیولرز کا درمیانی بھاؤ۔ سب سے کم {b} پر ہے، {q}۔',
    say_brand: '{b} پر آج {k} سونا {p} فی گرام ہے، {n} جیولرز میں نمبر {r}۔',
    say_city: '{c} میں آج سب سے سستا {k} {b} پر ہے، {p} فی گرام۔',
    say_cheap: 'آج سب سے سستا {k} {b} پر ہے، {p} فی گرام۔ 10 گرام پر سب سے مہنگا جیولر {q} زیادہ لیتا ہے۔',
    say_cmp: '{b} سستا ہے، 10 گرام {k} پر {p} کم۔',
    say_mk_brand: '{b} پر {c} کا عام میکنگ چارج تقریباً {p} ہے۔',
    say_mk: '{c} پر سب سے کم میکنگ چارج {b} پر ہے، تقریباً {p}۔',
    say_mk_none: '{b} کا میکنگ چارج ہم نے ابھی نہیں ناپا۔',
    say_off_all: 'آج {n} جیولرز کے پاس آفرز ہیں۔ صرف ہر ڈیزائن پر لاگو آفرز گن کر، 10 گرام 22 قیراط انگوٹھی سب سے کم {b} پر ہے: GST کے ساتھ {p}۔',
    say_off_brand: 'آج {b} کی ویب سائٹ پر {n} آفرز ہیں۔',
    say_off_none: 'آج {b} کی ویب سائٹ پر کوئی آفر نہیں ہے۔',
    say_price: '{b} پر {w} {k} سونا GST کے ساتھ تقریباً {p} کا پڑے گا۔',
    say_trend_up: 'آج {k} سونا {p} فی گرام ہے، پچھلے دن سے {q} زیادہ۔',
    say_trend_dn: 'آج {k} سونا {p} فی گرام ہے، پچھلے دن سے {q} کم۔',
    say_trend_same: 'آج {k} سونا {p} فی گرام ہے، پچھلے دن جتنا ہی۔',
    u_g: '{n} گرام', u_tola: '{n} تولہ', u_sov: '{n} ساورن', u_kg: '{n} کلو',
    c_Ring: 'انگوٹھی', c_Chain: 'چین', c_Bangle: 'چوڑی', c_Necklace: 'ہار', c_Earrings: 'جھمکے',
    c_Mangalsutra: 'منگل سوتر', c_Pendant: 'لاکٹ', c_Bracelet: 'بریسلیٹ', c_Coin: 'سکہ',
    ch_cheap22: 'آج سب سے سستا 22K', ch_mycity: 'میرے شہر میں بھاؤ', ch_tvk: 'تنشق یا کلیان',
    ch_bestoff: 'آج کی سب سے اچھی آفر', ch_p10chain: '10 گرام 22K چین کی قیمت', ch_k22v24: '22K اور 24K میں فرق؟',
    ch_p10: '10 گرام 22K کی قیمت', ch_afteroff: 'آفر کے بعد قیمت', ch_mkcmp: 'میکنگ چارج کا موازنہ',
    ch_goodmk: 'کیا میکنگ پر 20% چھوٹ اچھی ہے؟', ch_whatmk: 'میکنگ چارج کیا ہے؟', ch_alert: 'بھاؤ الرٹ لگائیں',
    ch_goodtime: 'کیا ابھی خریدنا ٹھیک ہے؟', ch_rate: 'آج سونے کا بھاؤ', ch_another: 'دوسرے جیولر پر یہی',
    ch_bmk: '{b} میکنگ چارج', ch_boff: '{b} آفرز'
  };

  S.as = {
    ui_sub: 'অলংকাৰ সহায়ক · আজিৰ প্ৰকৃত দৰৰ পৰা উত্তৰ',
    ui_ph: 'দৰ, জুৱেলাৰ, অফাৰৰ বিষয়ে সোধক…',
    ui_listen: 'শুনি আছোঁ… কওক',
    ui_mic: 'কৈ সোধক',
    ui_foot: 'বিনামূলীয়া · লিখক বা কওক · প্ৰকাশিত তথ্যৰ পৰা উত্তৰ, পৰামৰ্শ নহয়',
    ui_lang: 'ভাষা', ui_speak: 'শুনক', ui_mute: 'পঢ়া বন্ধ কৰক',
    greet1: 'নমস্কাৰ! 🙏 মই <b>সোনা</b>, আপোনাৰ অলংকাৰ সহায়ক।',
    greet2: 'সোণ কিনাৰ বিষয়ে যিকোনো কথা সোধক — যিকোনো জুৱেলাৰৰ আজিৰ দৰ, আপোনাৰ চহৰত আটাইতকৈ সস্তা, মেকিং চাৰ্জ, অফাৰ বা যিকোনো ওজনৰ দাম। লিখক, বা 🎤 টিপি কওক।',
    lang_hint: 'নিজৰ ভাষাত সোধক — লিখি বা কৈ — মই সেই ভাষাতে উত্তৰ দিম। হিন্দী বা ইংৰাজীৰ বাহিৰে আন ভাষা ক’ব? এবাৰ বাছক:',
    ui_auto: 'স্বয়ংক্ৰিয় (চিনাক্ত)',
    src: 'আজিৰ দৰ {n} জুৱেলাৰৰ পৰা, GSTৰ আগত · {d}',
    med_h: 'ভাৰতত আজি সোণৰ দৰ, {n} জুৱেলাৰৰ মাজৰ দৰ:',
    med_low: 'ৰাষ্ট্ৰীয় জুৱেলাৰৰ ভিতৰত আটাইতকৈ কম 22K: <b>{b}</b>, <b>{p}/গ্ৰাম</b>।',
    brand_h: '<b>{b}</b> আজি:',
    brand_rank: 'আজি {n} জুৱেলাৰৰ ভিতৰত ই <b>#{r}</b> — {rel}।',
    rel_at: '{k}ৰ বজাৰৰ মাজৰ দৰৰ সমান', rel_below: '{k}ৰ মাজৰ দৰতকৈ {p}/গ্ৰাম কম', rel_above: '{k}ৰ মাজৰ দৰতকৈ {p}/গ্ৰাম বেছি',
    brand_mk: 'সাধাৰণ মেকিং চাৰ্জ: {list}।',
    brand_off: 'তেওঁলোকৰ ছাইটত অফাৰ: <b>{o}</b>।',
    brand_st: 'এই ৰাজ্যসমূহত: {s}।',
    brand_link: '{b}ৰ 30 দিনৰ দৰ →',
    city_h: '<b>{c}</b>ত আজি আটাইতকৈ সস্তা {k} ({note}):',
    city_loc: 'ৰাষ্ট্ৰীয় জুৱেলাৰ আৰু {s}ৰ {l}টা স্থানীয় জুৱেলাৰ', city_nat: 'ৰাষ্ট্ৰীয় জুৱেলাৰ',
    city_link: '{c}ৰ সম্পূৰ্ণ তালিকা →',
    cheap_h: 'ৰাষ্ট্ৰীয় জুৱেলাৰৰ ভিতৰত আজি আটাইতকৈ সস্তা {k}:',
    cheap_gap: 'আটাইতকৈ সস্তা আৰু আটাইতকৈ দামীৰ মাজত 10 গ্ৰামত <b>{p}</b> পাৰ্থক্য — কিনাৰ আগতে নিশ্চয় চাওক।',
    cmp_h: 'আজি কাষে কাষে ({k}):', cmp_10: '10 গ্ৰাম: {p}', cmp_mk: 'মেকিং ~{p}', cmp_nomk: 'মেকিং: জোখা হোৱা নাই',
    cmp_win: '<b>{b}</b>ৰ {k} দৰ 10 গ্ৰামত <b>{p}</b> কম। শেষ বিল আপুনি বাছনি কৰা ডিজাইনৰ মেকিং চাৰ্জৰ ওপৰতো নিৰ্ভৰ কৰে।',
    mk_none: '<b>{b}</b>ৰ মেকিং চাৰ্জ আমি এতিয়াও জোখা নাই। এওঁলোকৰ জুখিছোঁ: {list}।',
    mk_link: 'মেকিং চাৰ্জৰ তুলনা →',
    mk_brand_h: '<b>{b}</b>ৰ সাধাৰণ মেকিং চাৰ্জ (প্ৰকৃত সামগ্ৰীৰ মাজৰ হিচাপ, সোণৰ মূল্যৰ %):',
    mk_note: 'ডিজাইন অনুসৰি সলনি হয়; বিলত ইয়াতেই আটাইতকৈ বেছি দৰদাম কৰিব পাৰি।',
    mk_all: 'সকলো জুৱেলাৰৰ তুলনা →',
    mk_h: '<b>{c}</b>ত আটাইতকৈ কম মেকিং চাৰ্জ (প্ৰকৃত সামগ্ৰীৰ মাজৰ হিচাপ):',
    mk_nocat: '<b>{c}</b>ৰ মেকিং চাৰ্জ আমি এতিয়াও জোখা নাই। <b>{r}</b>ৰ এইটো:',
    mk_every: 'প্ৰতিজন জুৱেলাৰ আৰু শ্ৰেণী →',
    bo_ask: 'কোন গহনাৰ বাবে শ্ৰেষ্ঠ অফাৰ বিচাৰিম?',
    bo_h: 'আজিৰ মেকিং চাৰ্জ অফাৰৰ পিছত <b>{w}</b> 22K <b>{c}</b>ৰ শ্ৰেষ্ঠ দাম:',
    bo_note: 'মুঠ = সোণ + অফাৰৰ পিছৰ মেকিং চাৰ্জ + 3% GST. অফাৰ % আনুমানিক; * মানে “লৈকে”, কেৱল কিছুমান ডিজাইনত (বন্ধনীত শ্ৰেষ্ঠ অৱস্থা). জুৱেলাৰৰ পৰা নিশ্চিত কৰক.',
    bo_none: '{c}ৰ মেকিং চাৰ্জ এতিয়াও যথেষ্ট জুৱেলাৰৰ মোৰ ওচৰত নাই.',
    say_bo: '{w} 22K {c}ৰ বাবে অফাৰৰ পিছত {b} আটাইতকৈ সস্তা, GST সহ প্ৰায় {p}.',
    bo_upto: 'লৈকে',
    bo_noff: 'অফাৰ নাই',
    off_none: 'আজি <b>{b}</b>ৰ ৱেবছাইটত কোনো অফাৰ লিখা নাই।',
    off_see: 'কাৰ অফাৰ আছে চাওক →',
    off_brand_h: 'আজি <b>{b}</b>ৰ ৱেবছাইটত অফাৰ:',
    off_page: 'তেওঁলোকৰ পৃষ্ঠা ↗', off_all: 'সকলো জুৱেলাৰৰ অফাৰৰ তুলনা →',
    off_all_h: 'আজি {n}জন জুৱেলাৰৰ নিজৰ ৱেবছাইটত অফাৰ আছে (A–Z):',
    off_ring: 'কেৱল সকলো ডিজাইনত প্ৰযোজ্য অফাৰ গণি, আজি 10 গ্ৰাম 22K আঙঠি আটাইতকৈ কমত <b>{b}</b>ত: GSTৰ সৈতে {p}। “আপ টু” আৰু বাছনি কৰা ডিজাইনৰ অফাৰ প্ৰতিটো অলংকাৰত বেলেগ — জুৱেলাৰৰ পৰা নিশ্চিত কৰক।',
    off_every: 'প্ৰতিটো অফাৰ, আৰু ইয়াৰ প্ৰকৃত অৰ্থ →',
    price_h: 'আজি {who}ত {w} {k}:', price_who: 'আটাইতকৈ সস্তা ৰাষ্ট্ৰীয় জুৱেলাৰ ({b})',
    price_gold: 'সোণ ({g} গ্ৰাম × {p})', price_mk: 'মেকিং (~{p}, {c})', price_typ: 'সাধাৰণতে', price_total: 'মুঠ',
    price_nomk: 'মেকিং চাৰ্জ যোগ কৰা নাই — আপোনাৰ ডিজাইনৰ চাৰ্জ যোগ কৰক (প্ৰায়ে 8–25%)।',
    trend_none: 'এতিয়াও যথেষ্ট ইতিহাস নাই।', hist_link: 'সোণৰ দৰৰ ইতিহাস →',
    trend_h: '{k}ৰ বজাৰৰ মাজৰ দৰ: আজি <b>{p}/গ্ৰাম</b>।',
    vs1: 'আগৰ দিনৰ তুলনাত', vs7: '7 দিন আগৰ তুলনাত', vs30: '30 দিন আগৰ তুলনাত',
    trend_note: 'এয়া অতীতৰ পৰিৱৰ্তন, ভৱিষ্যদ্বাণী নহয় — কাইলৈৰ দৰ কোনেও নিশ্চিতকৈ ক’ব নোৱাৰে।',
    full_hist: 'সম্পূৰ্ণ ইতিহাস →',
    alerts: 'প্ৰতিদিনে ৰাতিপুৱা আটাইতকৈ সস্তা জুৱেলাৰ আৰু আজিৰ দৰ, বিনামূলীয়াকৈ — আৰু যিদিনা 22K আপোনাৰ দৰলৈ নামিব, সেইদিনা ইমেইল।',
    alerts_cta: 'বিনামূলীয়া দৈনিক এলাৰ্ট লওক',
    more: 'অধিক পঢ়ক →', guide_h: 'এই গাইডত এই বিষয়ে আছে: <b>{t}</b> — {d}', guide_link: 'গাইড পঢ়ক →',
    en_only: 'এই উত্তৰ এতিয়া ইংৰাজীত:', translated: 'আপোনাৰ ডিভাইচত অনুবাদ কৰা হৈছে',
    ask_city: 'আপুনি কোন চহৰত আছে?',
    ch_loc: 'মোৰ লোকেচন ব্যৱহাৰ কৰক', loc_wait: 'আপোনাৰ ওচৰৰ চহৰ বিচাৰি আছোঁ…',
    loc_fail: 'লোকেচন পোৱা নগ’ল। আপোনাৰ চহৰৰ নাম লিখক বা বাছক:', ch_chcity: 'চহৰ সলনি কৰক',
    silver: 'এতিয়া মই কেৱল সোণৰ কথা কওঁ — জুৱেলাৰৰ 22K, 24K আৰু 18K দৰ। ৰূপ সোনকালে আহিব।',
    hello: 'নমস্কাৰ! 🙏 মই সোনা। সোণ কিনাৰ বিষয়ে যিকোনো কথা সোধক — {n} জুৱেলাৰৰ আজিৰ দৰ, আপোনাৰ চহৰ, মেকিং চাৰ্জ, অফাৰ বা যিকোনো ওজনৰ দাম।',
    thanks: 'ভাল লাগিল! আৰু কিবা?',
    about: 'মই সোনা, MyGoldRatesৰ সহায়ক। মই আজিৰ প্ৰকৃত তথ্যৰ পৰা উত্তৰ দিওঁ — {n} জুৱেলাৰৰ প্ৰকাশিত দৰ, প্ৰকৃত সামগ্ৰীৰ পৰা জোখা মেকিং চাৰ্জ, আৰু তেওঁলোকৰ ৱেবছাইটৰ অফাৰ — সেয়েহে মই কোনো সংখ্যা অনুমানত নকওঁ।',
    unknown: 'এইটো মই এতিয়াও শিকি আছোঁ — আপোনাৰ প্ৰশ্নটো টুকি ৰাখিছোঁ যাতে সোনকালে সঠিক উত্তৰ যোগ কৰিব পাৰোঁ। তেতিয়ালৈকে, এইবোৰত মই ভাল:',
    nodata: 'আজিৰ তথ্য ল’ড কৰিব পৰা নগ’ল। অনুগ্ৰহ কৰি ইণ্টাৰনেট চাই পুনৰ চেষ্টা কৰক।',
    no_voice: 'এই ডিভাইচত {l} মাত নাই, সেয়েহে মই লিখি উত্তৰ দিম।',
    mic_denied: 'মাইক বন্ধ আছে। ব্ৰাউজাৰৰ ছেটিংছত এই ছাইটৰ বাবে মাইক অন কৰক, তাৰ পিছত 🎤 টিপক।',
    mic_none: 'মই শুনিব নোৱাৰিলোঁ — 🎤 টিপি পুনৰ কওক।',
    rupees: 'টকা', carat: 'কেৰেট',
    say_med: 'আজি {k} সোণ প্ৰায় {p} প্ৰতি গ্ৰাম, {n} জুৱেলাৰৰ মাজৰ দৰ। আটাইতকৈ কম {b}ত, {q}।',
    say_brand: '{b}ত আজি {k} সোণ {p} প্ৰতি গ্ৰাম, {n} জুৱেলাৰৰ ভিতৰত নম্বৰ {r}।',
    say_city: '{c}ত আজি আটাইতকৈ সস্তা {k} {b}ত, {p} প্ৰতি গ্ৰাম।',
    say_cheap: 'আজি আটাইতকৈ সস্তা {k} {b}ত, {p} প্ৰতি গ্ৰাম। 10 গ্ৰামত আটাইতকৈ দামী জুৱেলাৰে {q} বেছি লয়।',
    say_cmp: '{b} সস্তা, 10 গ্ৰাম {k}ত {p} কম।',
    say_mk_brand: '{b}ত {c}ৰ সাধাৰণ মেকিং চাৰ্জ প্ৰায় {p}।',
    say_mk: '{c}ত আটাইতকৈ কম মেকিং চাৰ্জ {b}ত, প্ৰায় {p}।',
    say_mk_none: '{b}ৰ মেকিং চাৰ্জ আমি এতিয়াও জোখা নাই।',
    say_off_all: 'আজি {n}জন জুৱেলাৰৰ অফাৰ আছে। কেৱল সকলো ডিজাইনত প্ৰযোজ্য অফাৰ গণি, 10 গ্ৰাম 22 কেৰেট আঙঠি আটাইতকৈ কমত {b}ত: GSTৰ সৈতে {p}।',
    say_off_brand: 'আজি {b}ৰ ৱেবছাইটত {n}টা অফাৰ আছে।',
    say_off_none: 'আজি {b}ৰ ৱেবছাইটত কোনো অফাৰ নাই।',
    say_price: '{b}ত {w} {k} সোণৰ দাম GSTৰ সৈতে প্ৰায় {p} হ’ব।',
    say_trend_up: 'আজি {k} সোণ {p} প্ৰতি গ্ৰাম, আগৰ দিনতকৈ {q} বেছি।',
    say_trend_dn: 'আজি {k} সোণ {p} প্ৰতি গ্ৰাম, আগৰ দিনতকৈ {q} কম।',
    say_trend_same: 'আজি {k} সোণ {p} প্ৰতি গ্ৰাম, আগৰ দিনৰ সমান।',
    u_g: '{n} গ্ৰাম', u_tola: '{n} তোলা', u_sov: '{n} চভৰেইন', u_kg: '{n} কিলো',
    c_Ring: 'আঙঠি', c_Chain: 'চেইন', c_Bangle: 'খাৰু', c_Necklace: 'হাৰ', c_Earrings: 'কাণফুলি',
    c_Mangalsutra: 'মংগলসূত্ৰ', c_Pendant: 'লকেট', c_Bracelet: 'ব্ৰেচলেট', c_Coin: 'মুদ্ৰা',
    ch_cheap22: 'আজি আটাইতকৈ সস্তা 22K', ch_mycity: 'মোৰ চহৰত দৰ', ch_tvk: 'তনিষ্ক নে কল্যাণ',
    ch_bestoff: 'আজিৰ আটাইতকৈ ভাল অফাৰ', ch_p10chain: '10 গ্ৰাম 22K চেইনৰ দাম', ch_k22v24: '22K আৰু 24Kৰ পাৰ্থক্য?',
    ch_p10: '10 গ্ৰাম 22Kৰ দাম', ch_afteroff: 'অফাৰৰ পিছত দাম', ch_mkcmp: 'মেকিং চাৰ্জৰ তুলনা',
    ch_goodmk: 'মেকিংত 20% ৰেহাই ভাল নে?', ch_whatmk: 'মেকিং চাৰ্জ কি?', ch_alert: 'দৰৰ এলাৰ্ট ছেট কৰক',
    ch_goodtime: 'এতিয়া কিনাটো ঠিক নে?', ch_rate: 'আজি সোণৰ দৰ', ch_another: 'আন জুৱেলাৰত এইটো',
    ch_bmk: '{b} মেকিং চাৰ্জ', ch_boff: '{b} অফাৰ'
  };

  S.or = {
    ui_sub: 'ଗହଣା ସହାୟକ · ଆଜିର ପ୍ରକୃତ ଦରରୁ ଉତ୍ତର',
    ui_ph: 'ଦର, ଜୁଏଲର୍ସ, ଅଫର ବିଷୟରେ ପଚାରନ୍ତୁ…',
    ui_listen: 'ଶୁଣୁଛି… କୁହନ୍ତୁ',
    ui_mic: 'କହି ପଚାରନ୍ତୁ',
    ui_foot: 'ମାଗଣା · ଲେଖନ୍ତୁ ବା କୁହନ୍ତୁ · ପ୍ରକାଶିତ ତଥ୍ୟରୁ ଉତ୍ତର, ପରାମର୍ଶ ନୁହେଁ',
    ui_lang: 'ଭାଷା', ui_speak: 'ଶୁଣନ୍ତୁ', ui_mute: 'ପଢ଼ିବା ବନ୍ଦ କରନ୍ତୁ',
    greet1: 'ନମସ୍କାର! 🙏 ମୁଁ <b>ସୋନା</b>, ଆପଣଙ୍କ ଗହଣା ସହାୟକ।',
    greet2: 'ସୁନା କିଣିବା ବିଷୟରେ ଯାହା ବି ପଚାରନ୍ତୁ — ଯେକୌଣସି ଜୁଏଲରଙ୍କ ଆଜିର ଦର, ଆପଣଙ୍କ ସହରରେ ସବୁଠୁ ଶସ୍ତା, ମେକିଂ ଚାର୍ଜ, ଅଫର ବା ଯେକୌଣସି ଓଜନର ଦାମ। ଲେଖନ୍ତୁ, ବା 🎤 ଦବାଇ କୁହନ୍ତୁ।',
    lang_hint: 'ନିଜ ଭାଷାରେ ପଚାରନ୍ତୁ — ଲେଖି ବା କହି — ମୁଁ ସେହି ଭାଷାରେ ଉତ୍ତର ଦେବି। ହିନ୍ଦୀ ବା ଇଂରାଜୀ ଛଡ଼ା ଅନ୍ୟ ଭାଷା କହିବେ? ଥରେ ବାଛନ୍ତୁ:',
    ui_auto: 'ସ୍ୱୟଂଚାଳିତ (ଚିହ୍ନଟ)',
    src: 'ଆଜିର ଦର {n} ଜୁଏଲର୍ସଙ୍କଠାରୁ, GST ପୂର୍ବରୁ · {d}',
    med_h: 'ଭାରତରେ ଆଜି ସୁନା ଦର, {n} ଜୁଏଲର୍ସଙ୍କ ମଝି ଦର:',
    med_low: 'ଜାତୀୟ ଜୁଏଲର୍ସଙ୍କ ମଧ୍ୟରେ ସବୁଠୁ କମ 22K: <b>{b}</b>, <b>{p}/ଗ୍ରାମ</b>।',
    brand_h: '<b>{b}</b> ଆଜି:',
    brand_rank: 'ଆଜି {n} ଜୁଏଲର୍ସଙ୍କ ମଧ୍ୟରେ ଏହା <b>#{r}</b> — {rel}।',
    rel_at: '{k} ବଜାର ମଝି ଦର ସହ ସମାନ', rel_below: '{k} ମଝି ଦରଠାରୁ {p}/ଗ୍ରାମ କମ', rel_above: '{k} ମଝି ଦରଠାରୁ {p}/ଗ୍ରାମ ଅଧିକ',
    brand_mk: 'ସାଧାରଣ ମେକିଂ ଚାର୍ଜ: {list}।',
    brand_off: 'ସେମାନଙ୍କ ସାଇଟରେ ଅଫର: <b>{o}</b>।',
    brand_st: 'ଏହି ରାଜ୍ୟରେ: {s}।',
    brand_link: '{b}ର 30 ଦିନର ଦର →',
    city_h: '<b>{c}</b>ରେ ଆଜି ସବୁଠୁ ଶସ୍ତା {k} ({note}):',
    city_loc: 'ଜାତୀୟ ଜୁଏଲର୍ସ ଓ {s}ର {l}ଟି ସ୍ଥାନୀୟ ଜୁଏଲର୍ସ', city_nat: 'ଜାତୀୟ ଜୁଏଲର୍ସ',
    city_link: '{c}ର ସମ୍ପୂର୍ଣ୍ଣ ତାଲିକା →',
    cheap_h: 'ଜାତୀୟ ଜୁଏଲର୍ସଙ୍କ ମଧ୍ୟରେ ଆଜି ସବୁଠୁ ଶସ୍ତା {k}:',
    cheap_gap: 'ସବୁଠୁ ଶସ୍ତା ଓ ସବୁଠୁ ମହଙ୍ଗା ମଧ୍ୟରେ 10 ଗ୍ରାମରେ <b>{p}</b> ଫରକ — କିଣିବା ପୂର୍ବରୁ ନିଶ୍ଚୟ ଦେଖନ୍ତୁ।',
    cmp_h: 'ଆଜି ପାଖାପାଖି ({k}):', cmp_10: '10 ଗ୍ରାମ: {p}', cmp_mk: 'ମେକିଂ ~{p}', cmp_nomk: 'ମେକିଂ: ମପା ହୋଇନାହିଁ',
    cmp_win: '<b>{b}</b>ର {k} ଦର 10 ଗ୍ରାମରେ <b>{p}</b> କମ। ଶେଷ ବିଲ୍ ଆପଣ ବାଛିଥିବା ଡିଜାଇନର ମେକିଂ ଚାର୍ଜ ଉପରେ ମଧ୍ୟ ନିର୍ଭର କରେ।',
    mk_none: '<b>{b}</b>ର ମେକିଂ ଚାର୍ଜ ଆମେ ଏଯାଏଁ ମାପିନାହୁଁ। ଏମାନଙ୍କର ମାପିଛୁ: {list}।',
    mk_link: 'ମେକିଂ ଚାର୍ଜ ତୁଳନା →',
    mk_brand_h: '<b>{b}</b>ର ସାଧାରଣ ମେକିଂ ଚାର୍ଜ (ପ୍ରକୃତ ଉତ୍ପାଦର ମଝି ହିସାବ, ସୁନା ମୂଲ୍ୟର %):',
    mk_note: 'ଡିଜାଇନ ଅନୁସାରେ ବଦଳେ; ବିଲରେ ଏଥିରେ ହିଁ ସବୁଠୁ ଅଧିକ ଦରଦାମ ହୋଇପାରେ।',
    mk_all: 'ସବୁ ଜୁଏଲର୍ସଙ୍କ ତୁଳନା →',
    mk_h: '<b>{c}</b> ଉପରେ ସବୁଠୁ କମ ମେକିଂ ଚାର୍ଜ (ପ୍ରକୃତ ଉତ୍ପାଦର ମଝି ହିସାବ):',
    mk_nocat: '<b>{c}</b>ର ମେକିଂ ଚାର୍ଜ ଆମେ ଏଯାଏଁ ମାପିନାହୁଁ। <b>{r}</b>ର ଏହା:',
    mk_every: 'ପ୍ରତ୍ୟେକ ଜୁଏଲର ଓ ବର୍ଗ →',
    bo_ask: 'କେଉଁ ଗହଣା ପାଇଁ ସର୍ବୋତ୍ତମ ଅଫର ଖୋଜିବି?',
    bo_h: 'ଆଜିର ମେକିଂ ଚାର୍ଜ ଅଫର ପରେ <b>{w}</b> 22K <b>{c}</b>ର ସର୍ବୋତ୍ତମ ଦାମ:',
    bo_note: 'ମୋଟ = ସୁନା + ଅଫର ପରେ ମେକିଂ ଚାର୍ଜ + 3% GST. ଅଫର % ଆନୁମାନିକ; * ଅର୍ଥ “ପର୍ଯ୍ୟନ୍ତ”, କେବଳ କିଛି ଡିଜାଇନରେ (ବନ୍ଧନୀରେ ସର୍ବୋତ୍ତମ ସ୍ଥିତି). ଜୁଏଲରଙ୍କ ଠାରୁ ନିଶ୍ଚିତ କରନ୍ତୁ.',
    bo_none: '{c}ର ମେକିଂ ଚାର୍ଜ ଏପର୍ଯ୍ୟନ୍ତ ଯଥେଷ୍ଟ ଜୁଏଲରଙ୍କର ମୋ ପାଖରେ ନାହିଁ.',
    say_bo: '{w} 22K {c} ପାଇଁ ଅଫର ପରେ {b} ସବୁଠୁ ଶସ୍ତା, GST ସହ ପ୍ରାୟ {p}.',
    bo_upto: 'ପର୍ଯ୍ୟନ୍ତ',
    bo_noff: 'ଅଫର ନାହିଁ',
    off_none: 'ଆଜି <b>{b}</b>ର ୱେବସାଇଟରେ କୌଣସି ଅଫର ଲେଖାଯାଇନାହିଁ।',
    off_see: 'କାହାର ଅଫର ଅଛି ଦେଖନ୍ତୁ →',
    off_brand_h: 'ଆଜି <b>{b}</b>ର ୱେବସାଇଟରେ ଅଫର:',
    off_page: 'ସେମାନଙ୍କ ପେଜ ↗', off_all: 'ସବୁ ଜୁଏଲର୍ସଙ୍କ ଅଫର ତୁଳନା →',
    off_all_h: 'ଆଜି {n} ଜୁଏଲର୍ସଙ୍କ ନିଜ ୱେବସାଇଟରେ ଅଫର ଅଛି (A–Z):',
    off_ring: 'କେବଳ ସବୁ ଡିଜାଇନରେ ଲାଗୁ ହେଉଥିବା ଅଫର ଗଣି, ଆଜି 10 ଗ୍ରାମ 22K ମୁଦି ସବୁଠୁ କମ <b>{b}</b>ରେ: GST ସହ {p}। “ଅପ୍ ଟୁ” ଓ ବଛା ଡିଜାଇନର ଅଫର ପ୍ରତି ଗହଣାରେ ଅଲଗା — ଜୁଏଲରଙ୍କ ସହ ନିଶ୍ଚିତ କରନ୍ତୁ।',
    off_every: 'ପ୍ରତ୍ୟେକ ଅଫର, ଓ ତାର ପ୍ରକୃତ ଅର୍ଥ →',
    price_h: 'ଆଜି {who}ରେ {w} {k}:', price_who: 'ସବୁଠୁ ଶସ୍ତା ଜାତୀୟ ଜୁଏଲର ({b})',
    price_gold: 'ସୁନା ({g} ଗ୍ରାମ × {p})', price_mk: 'ମେକିଂ (~{p}, {c})', price_typ: 'ସାଧାରଣତଃ', price_total: 'ମୋଟ',
    price_nomk: 'ମେକିଂ ଚାର୍ଜ ମିଶିନାହିଁ — ଆପଣଙ୍କ ଡିଜାଇନର ଚାର୍ଜ ଯୋଡ଼ନ୍ତୁ (ପ୍ରାୟତଃ 8–25%)।',
    trend_none: 'ଏଯାଏଁ ଯଥେଷ୍ଟ ଇତିହାସ ନାହିଁ।', hist_link: 'ସୁନା ଦରର ଇତିହାସ →',
    trend_h: '{k} ବଜାର ମଝି ଦର: ଆଜି <b>{p}/ଗ୍ରାମ</b>।',
    vs1: 'ପୂର୍ବ ଦିନ ତୁଳନାରେ', vs7: '7 ଦିନ ପୂର୍ବ ତୁଳନାରେ', vs30: '30 ଦିନ ପୂର୍ବ ତୁଳନାରେ',
    trend_note: 'ଏହା ଅତୀତର ପରିବର୍ତ୍ତନ, ଭବିଷ୍ୟବାଣୀ ନୁହେଁ — କାଲିର ଦର କେହି ନିଶ୍ଚିତ କହିପାରିବେ ନାହିଁ।',
    full_hist: 'ସମ୍ପୂର୍ଣ୍ଣ ଇତିହାସ →',
    alerts: 'ପ୍ରତିଦିନ ସକାଳେ ସବୁଠୁ ଶସ୍ତା ଜୁଏଲର ଓ ଆଜିର ଦର, ମାଗଣା — ଓ ଯେଉଁଦିନ 22K ଆପଣଙ୍କ ଦରକୁ ଖସିବ, ସେଦିନ ଇମେଲ।',
    alerts_cta: 'ମାଗଣା ଦୈନିକ ଆଲର୍ଟ ପାଆନ୍ତୁ',
    more: 'ଅଧିକ ପଢ଼ନ୍ତୁ →', guide_h: 'ଏହି ଗାଇଡ ଏହା ବିଷୟରେ: <b>{t}</b> — {d}', guide_link: 'ଗାଇଡ ପଢ଼ନ୍ତୁ →',
    en_only: 'ଏହି ଉତ୍ତର ଏବେ ଇଂରାଜୀରେ:', translated: 'ଆପଣଙ୍କ ଡିଭାଇସରେ ଅନୁବାଦ ହୋଇଛି',
    ask_city: 'ଆପଣ କେଉଁ ସହରରେ ଅଛନ୍ତି?',
    ch_loc: 'ମୋ ଲୋକେସନ ବ୍ୟବହାର କରନ୍ତୁ', loc_wait: 'ଆପଣଙ୍କ ନିକଟତମ ସହର ଖୋଜୁଛି…',
    loc_fail: 'ଲୋକେସନ ମିଳିଲା ନାହିଁ। ଆପଣଙ୍କ ସହରର ନାମ ଲେଖନ୍ତୁ ବା ବାଛନ୍ତୁ:', ch_chcity: 'ସହର ବଦଳାନ୍ତୁ',
    silver: 'ଏବେ ମୁଁ କେବଳ ସୁନା ବିଷୟରେ କହେ — ଜୁଏଲର୍ସଙ୍କ 22K, 24K ଓ 18K ଦର। ରୁପା ଶୀଘ୍ର ଆସୁଛି।',
    hello: 'ନମସ୍କାର! 🙏 ମୁଁ ସୋନା। ସୁନା କିଣିବା ବିଷୟରେ ଯାହା ବି ପଚାରନ୍ତୁ — {n} ଜୁଏଲର୍ସଙ୍କ ଆଜିର ଦର, ଆପଣଙ୍କ ସହର, ମେକିଂ ଚାର୍ଜ, ଅଫର ବା ଯେକୌଣସି ଓଜନର ଦାମ।',
    thanks: 'ଖୁସି ଲାଗିଲା! ଆଉ କିଛି?',
    about: 'ମୁଁ ସୋନା, MyGoldRatesର ସହାୟକ। ମୁଁ ଆଜିର ପ୍ରକୃତ ତଥ୍ୟରୁ ଉତ୍ତର ଦିଏ — {n} ଜୁଏଲର୍ସଙ୍କ ପ୍ରକାଶିତ ଦର, ପ୍ରକୃତ ଉତ୍ପାଦରୁ ମପା ମେକିଂ ଚାର୍ଜ, ଓ ସେମାନଙ୍କ ୱେବସାଇଟର ଅଫର — ତେଣୁ ମୁଁ କୌଣସି ସଂଖ୍ୟା ଅନୁମାନରେ କହେ ନାହିଁ।',
    unknown: 'ଏହା ମୁଁ ଏବେ ଶିଖୁଛି — ଆପଣଙ୍କ ପ୍ରଶ୍ନ ନୋଟ କରିଛି ଯେପରି ଶୀଘ୍ର ଠିକ ଉତ୍ତର ଯୋଡ଼ିପାରିବୁ। ସେତେବେଳ ଯାଏଁ, ଏଥିରେ ମୁଁ ଭଲ:',
    nodata: 'ଆଜିର ତଥ୍ୟ ଲୋଡ ହୋଇପାରିଲା ନାହିଁ। ଦୟାକରି ଇଣ୍ଟରନେଟ ଦେଖି ପୁଣି ଚେଷ୍ଟା କରନ୍ତୁ।',
    no_voice: 'ଏହି ଡିଭାଇସରେ {l} ସ୍ୱର ନାହିଁ, ତେଣୁ ମୁଁ ଲେଖି ଉତ୍ତର ଦେବି।',
    mic_denied: 'ମାଇକ ବନ୍ଦ ଅଛି। ବ୍ରାଉଜର ସେଟିଂସରେ ଏହି ସାଇଟ ପାଇଁ ମାଇକ ଚାଲୁ କରନ୍ତୁ, ତାପରେ 🎤 ଦବାନ୍ତୁ।',
    mic_none: 'ମୁଁ ଶୁଣିପାରିଲି ନାହିଁ — 🎤 ଦବାଇ ପୁଣି କୁହନ୍ତୁ।',
    rupees: 'ଟଙ୍କା', carat: 'କ୍ୟାରେଟ',
    say_med: 'ଆଜି {k} ସୁନା ପ୍ରାୟ {p} ପ୍ରତି ଗ୍ରାମ, {n} ଜୁଏଲର୍ସଙ୍କ ମଝି ଦର। ସବୁଠୁ କମ {b}ରେ, {q}।',
    say_brand: '{b}ରେ ଆଜି {k} ସୁନା {p} ପ୍ରତି ଗ୍ରାମ, {n} ଜୁଏଲର୍ସଙ୍କ ମଧ୍ୟରେ ନମ୍ବର {r}।',
    say_city: '{c}ରେ ଆଜି ସବୁଠୁ ଶସ୍ତା {k} {b}ରେ, {p} ପ୍ରତି ଗ୍ରାମ।',
    say_cheap: 'ଆଜି ସବୁଠୁ ଶସ୍ତା {k} {b}ରେ, {p} ପ୍ରତି ଗ୍ରାମ। 10 ଗ୍ରାମରେ ସବୁଠୁ ମହଙ୍ଗା ଜୁଏଲର {q} ଅଧିକ ନିଅନ୍ତି।',
    say_cmp: '{b} ଶସ୍ତା, 10 ଗ୍ରାମ {k}ରେ {p} କମ।',
    say_mk_brand: '{b}ରେ {c}ର ସାଧାରଣ ମେକିଂ ଚାର୍ଜ ପ୍ରାୟ {p}।',
    say_mk: '{c} ଉପରେ ସବୁଠୁ କମ ମେକିଂ ଚାର୍ଜ {b}ରେ, ପ୍ରାୟ {p}।',
    say_mk_none: '{b}ର ମେକିଂ ଚାର୍ଜ ଆମେ ଏଯାଏଁ ମାପିନାହୁଁ।',
    say_off_all: 'ଆଜି {n} ଜୁଏଲର୍ସଙ୍କ ଅଫର ଅଛି। କେବଳ ସବୁ ଡିଜାଇନରେ ଲାଗୁ ଅଫର ଗଣି, 10 ଗ୍ରାମ 22 କ୍ୟାରେଟ ମୁଦି ସବୁଠୁ କମ {b}ରେ: GST ସହ {p}।',
    say_off_brand: 'ଆଜି {b}ର ୱେବସାଇଟରେ {n}ଟି ଅଫର ଅଛି।',
    say_off_none: 'ଆଜି {b}ର ୱେବସାଇଟରେ କୌଣସି ଅଫର ନାହିଁ।',
    say_price: '{b}ରେ {w} {k} ସୁନା GST ସହ ପ୍ରାୟ {p} ପଡ଼ିବ।',
    say_trend_up: 'ଆଜି {k} ସୁନା {p} ପ୍ରତି ଗ୍ରାମ, ପୂର୍ବ ଦିନଠାରୁ {q} ଅଧିକ।',
    say_trend_dn: 'ଆଜି {k} ସୁନା {p} ପ୍ରତି ଗ୍ରାମ, ପୂର୍ବ ଦିନଠାରୁ {q} କମ।',
    say_trend_same: 'ଆଜି {k} ସୁନା {p} ପ୍ରତି ଗ୍ରାମ, ପୂର୍ବ ଦିନ ସହ ସମାନ।',
    u_g: '{n} ଗ୍ରାମ', u_tola: '{n} ତୋଳା', u_sov: '{n} ସଭରେନ', u_kg: '{n} କିଲୋ',
    c_Ring: 'ମୁଦି', c_Chain: 'ଚେନ', c_Bangle: 'ଚୁଡ଼ି', c_Necklace: 'ହାର', c_Earrings: 'କାନଫୁଲ',
    c_Mangalsutra: 'ମଙ୍ଗଳସୂତ୍ର', c_Pendant: 'ଲକେଟ', c_Bracelet: 'ବ୍ରେସଲେଟ', c_Coin: 'ମୁଦ୍ରା',
    ch_cheap22: 'ଆଜି ସବୁଠୁ ଶସ୍ତା 22K', ch_mycity: 'ମୋ ସହରରେ ଦର', ch_tvk: 'ତନିଷ୍କ କି କଲ୍ୟାଣ',
    ch_bestoff: 'ଆଜିର ସବୁଠୁ ଭଲ ଅଫର', ch_p10chain: '10 ଗ୍ରାମ 22K ଚେନର ଦାମ', ch_k22v24: '22K ଓ 24Kରେ ଫରକ?',
    ch_p10: '10 ଗ୍ରାମ 22Kର ଦାମ', ch_afteroff: 'ଅଫର ପରେ ଦାମ', ch_mkcmp: 'ମେକିଂ ଚାର୍ଜ ତୁଳନା',
    ch_goodmk: 'ମେକିଂରେ 20% ରିହାତି ଭଲ କି?', ch_whatmk: 'ମେକିଂ ଚାର୍ଜ କ’ଣ?', ch_alert: 'ଦର ଆଲର୍ଟ ଲଗାନ୍ତୁ',
    ch_goodtime: 'ଏବେ କିଣିବା ଠିକ କି?', ch_rate: 'ଆଜି ସୁନା ଦର', ch_another: 'ଅନ୍ୟ ଜୁଏଲରରେ ଏହା',
    ch_bmk: '{b} ମେକିଂ ଚାର୍ଜ', ch_boff: '{b} ଅଫର'
  };

  root.SONA_STR = S;
  if (typeof module !== 'undefined' && module.exports) module.exports = S;
})(typeof window !== 'undefined' ? window : globalThis);

/* Sona's languages: understanding a question asked in an Indian language.
 *
 * Free and in the browser, like the rest of Sona. A question typed or spoken
 * in Hindi, Urdu, Marathi, Gujarati, Punjabi, Bengali, Assamese, Odia,
 * Kannada, Tamil, Telugu or Malayalam is turned into the plain words Sona's answer engine already
 * knows ("सबसे सस्ता सोना" -> "cheapest gold"):
 *
 *   - everyday words (gold, rate, cheapest, making charge, offer, ring...)
 *     come from a small word list per meaning, written in each script;
 *   - names (jewellers, cities) are matched by sound: every Indian script is
 *     spelled out in Latin letters and compared, loosely, with the names we
 *     know - so "तनिष्क", "தனிஷ்க்" and "ತನಿಷ್ಕ್" all find Tanishq.
 *
 * The replies themselves are in sona_i18n.js.
 */
(function (root) {
  'use strict';

  var LANGS = [
    { c: 'en', n: 'English', s: 'EN', bcp: 'en-IN' },
    { c: 'hi', n: 'हिन्दी', s: 'हि', bcp: 'hi-IN' },
    { c: 'ur', n: 'اردو', s: 'ار', bcp: 'ur-IN', rtl: 1 },
    { c: 'mr', n: 'मराठी', s: 'म', bcp: 'mr-IN' },
    { c: 'gu', n: 'ગુજરાતી', s: 'ગુ', bcp: 'gu-IN' },
    { c: 'pa', n: 'ਪੰਜਾਬੀ', s: 'ਪੰ', bcp: 'pa-IN' },
    { c: 'bn', n: 'বাংলা', s: 'বা', bcp: 'bn-IN' },
    { c: 'as', n: 'অসমীয়া', s: 'অ', bcp: 'as-IN' },
    { c: 'or', n: 'ଓଡ଼ିଆ', s: 'ଓ', bcp: 'or-IN' },
    { c: 'kn', n: 'ಕನ್ನಡ', s: 'ಕ', bcp: 'kn-IN' },
    { c: 'ta', n: 'தமிழ்', s: 'த', bcp: 'ta-IN' },
    { c: 'te', n: 'తెలుగు', s: 'తె', bcp: 'te-IN' },
    { c: 'ml', n: 'മലയാളം', s: 'മ', bcp: 'ml-IN' }
  ];

  // ------------------------------------------------- any script -> Latin
  // The Indian scripts share one layout (each block is 128 code points with
  // the same letter at the same offset), so one table spells all of them.
  var BLOCKS = [[0x0900, 'deva'], [0x0980, 'beng'], [0x0A00, 'guru'], [0x0A80, 'gujr'],
    [0x0B00, 'orya'], [0x0B80, 'taml'], [0x0C00, 'telu'], [0x0C80, 'knda'], [0x0D00, 'mlym']];
  var SCRIPT_LANG = { deva: 'hi', beng: 'bn', guru: 'pa', gujr: 'gu', orya: 'or', taml: 'ta', telu: 'te', knda: 'kn', mlym: 'ml' };
  // North Indian scripts drop the silent "a" ("सबसे" is sabse, not sabase).
  var DROPS_A = { deva: 1, beng: 1, guru: 1, gujr: 1 };
  var V = { 5: 'a', 6: 'aa', 7: 'i', 8: 'ii', 9: 'u', 10: 'uu', 11: 'ri', 12: 'li', 13: 'e', 14: 'e', 15: 'e', 16: 'ai',
    17: 'o', 18: 'o', 19: 'o', 20: 'au', 114: 'e' };
  var C = { 21: 'k', 22: 'kh', 23: 'g', 24: 'gh', 25: 'ng', 26: 'ch', 27: 'chh', 28: 'j', 29: 'jh', 30: 'ny',
    31: 't', 32: 'th', 33: 'd', 34: 'dh', 35: 'n', 36: 't', 37: 'th', 38: 'd', 39: 'dh', 40: 'n', 41: 'n',
    42: 'p', 43: 'ph', 44: 'b', 45: 'bh', 46: 'm', 47: 'y', 48: 'r', 49: 'r', 50: 'l', 51: 'l', 52: 'l',
    53: 'v', 54: 'sh', 55: 'sh', 56: 's', 57: 'h', 88: 'q', 89: 'kh', 90: 'gh', 91: 'z', 92: 'r', 93: 'rh',
    94: 'f', 95: 'y' };
  var M = { 62: 'aa', 63: 'i', 64: 'ii', 65: 'u', 66: 'uu', 67: 'ri', 68: 'ri', 69: 'e', 70: 'e', 71: 'e', 72: 'ai',
    73: 'o', 74: 'o', 75: 'o', 76: 'au', 87: 'u' };
  var NUKTA = { k: 'q', j: 'z', ph: 'f', d: 'r', dh: 'rh' };

  function scriptOf(cp) {
    for (var i = 0; i < BLOCKS.length; i++) if (cp >= BLOCKS[i][0] && cp < BLOCKS[i][0] + 128) return BLOCKS[i];
    return null;
  }
  // Urdu is written in the Perso-Arabic script, without most vowels; it is
  // read separately (urdu() below). "Indic" here means any script Sona reads.
  var AR = /[\u0600-\u06FF]/;
  function isIndic(s) { return /[\u0600-\u06FF\u0900-\u0D7F]/.test(s); }

  function romWord(w) {
    var syl = [], sc = null, pend = '';
    for (var i = 0; i < w.length; i++) {
      var cp = w.charCodeAt(i), b = scriptOf(cp), last = syl[syl.length - 1];
      if (!b) { if (/[a-z0-9]/i.test(w[i])) syl.push({ c: w[i].toLowerCase(), v: '', lat: 1 }); continue; }
      sc = sc || b[1];
      var o = cp - b[0];
      if (o >= 102 && o <= 111) { syl.push({ c: String(o - 102), v: '', lat: 1 }); continue; }
      var cc = C[o];
      if (b[1] === 'beng' && (o === 112 || o === 113)) cc = o === 112 ? 'r' : 'v';                       // Assamese ৰ ৱ
      if (b[1] === 'orya' && o === 113) cc = 'v';                                                        // Odia ୱ
      if (cc !== undefined) {
        if (last && last.hal) { last.c += cc; last.hal = false; last.v = null; last.conj = true; }
        else syl.push({ c: pend + cc, v: null });
        pend = ''; continue;
      }
      if (M[o] !== undefined) { if (last && !last.lat) { last.v = M[o]; last.hal = false; } continue; }
      if (V[o] !== undefined) { syl.push({ c: '', v: V[o] }); continue; }
      if (o === 77) { if (last && last.v === null) { last.v = ''; last.hal = true; } continue; }        // virama
      if (o === 60) { if (last && NUKTA[last.c]) last.c = NUKTA[last.c]; continue; }                     // nukta
      if (o === 1 || o === 2 || o === 112) { if (last) last.coda = (last.coda || '') + 'n'; continue; } // nasal
      if (o === 3) { if (last) last.coda = (last.coda || '') + 'h'; continue; }
      if (o >= 122 && o <= 127) {                                                                       // Malayalam chillu
        var ch = 'nnrllk'[o - 122];
        if (last) last.coda = (last.coda || '') + ch; else syl.push({ c: ch, v: '' });
        continue;
      }
      if (o === 78) {
        if (b[1] === 'mlym') pend = 'r';
        else if (last) last.coda = (last.coda || '') + 't';                                              // Bengali khanda ta
      }
    }
    if (DROPS_A[sc]) {
      var n = syl.length;
      var voiced = function (s) { return s.v === null ? !s.del : s.v !== ''; };
      if (n > 1 && syl[n - 1].v === null && !syl[n - 1].conj && !syl[n - 1].coda) syl[n - 1].del = true;
      for (var j = n - 2; j >= 1; j--) {
        var s = syl[j];
        if (s.v === null && !s.conj && !s.coda && s.c && voiced(syl[j - 1]) && syl[j + 1].c && !syl[j + 1].lat && voiced(syl[j + 1])) s.del = true;
      }
    }
    return syl.map(function (s) { return s.c + (s.v === null ? (s.del ? '' : 'a') : s.v) + (s.coda || ''); }).join('');
  }

  // A loose spelling key, so "Tanishq" and "tanishka", or "Malabar" and
  // Tamil's "malapaar", compare equal: no vowel length, no aspiration,
  // voiced = unvoiced, doubled letters single.
  function key(s) {
    s = String(s).toLowerCase().replace(/[^a-z0-9]/g, '')
      .replace(/x/g, 'ks').replace(/q/g, 'k').replace(/z/g, 'j').replace(/w/g, 'v').replace(/f/g, 'ph')
      .replace(/c(?!h)/g, 'k');
    s = s.replace(/([kgcjtdpbr])h/g, '$1').replace(/([kgcjtdpbr])h/g, '$1').replace(/sh/g, 's')
      .replace(/ee|ii/g, 'i').replace(/oo|uu/g, 'u').replace(/aa/g, 'a').replace(/y/g, 'i')
      .replace(/g/g, 'k').replace(/d/g, 't').replace(/b/g, 'p').replace(/n(?=[pm])/g, 'm')
      .replace(/(.)\1+/g, '$1');
    if (s.length > 3) s = s.replace(/a$/, '');
    return s;
  }

  function lev(a, b) {
    var d = [], i, j;
    for (i = 0; i <= a.length; i++) d[i] = [i];
    for (j = 1; j <= b.length; j++) d[0][j] = j;
    for (i = 1; i <= a.length; i++)
      for (j = 1; j <= b.length; j++)
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return d[a.length][b.length];
  }
  function common(a, b) { var i = 0; while (i < a.length && i < b.length && a[i] === b[i]) i++; return i; }

  // ------------------------------------------------------- word list
  // Meaning (the word the answer engine knows) -> the same idea in each
  // script, with the usual inflected forms. Prefix-matched, so "सोन्याचा"
  // finds "सोन्या".
  var LEX = {
    gold: 'सोना सोने सोनं सोन्या सोन्याचा सोन्याचे सोन्याची गोल्ड સોનું સોના સોનાનો સોનાના સોનાની ગોલ્ડ ਸੋਨਾ ਸੋਨੇ ਗੋਲਡ সোনা সোনার গোল্ড ಚಿನ್ನ ಚಿನ್ನದ ಬಂಗಾರ ಬಂಗಾರದ ಗೋಲ್ಡ್ தங்கம் தங்க தங்கத்தின் கோல்ட் బంగారం బంగారు గోల్డ్ സ്വർണം സ്വർണ്ണം സ്വർണ സ്വർണ്ണ ഗോൾഡ് ସୁନା ସୁନାର ଗୋଲ୍ଡ সোণ সোণৰ سونا سونے گولڈ',
    rate: 'भाव दाम कीमत क़ीमत क़ीमत रेट रेट्स मूल्य दर किंमत ભાવ કિંમત દર રેટ ਭਾਅ ਰੇਟ ਕੀਮਤ ਮੁੱਲ দাম দর রেট ಬೆಲೆ ದರ ರೇಟ್ விலை விலைய ரேட் ధర ధరలు రేటు రేట్ വില വിലയ നിരക്ക് റേറ്റ് ଦର ଦାମ ମୂଲ୍ୟ ରେଟ দৰ ৰেট بھاؤ بھاو ریٹ قیمت دام نرخ',
    price: 'प्राइस कितना कितने कितनी किती કેટલા કેટલો કેટલું ਕਿੰਨਾ ਕਿੰਨੇ ਕਿੰਨੀ কত ಎಷ್ಟು எவ்வளவு ఎంత എത്ര କେତେ কিমান کتنا کتنے کتنی',
    today: 'आज आजचा आजचे आजची आजचं આજે આજનો આજનું આજના ਅੱਜ ਅਜ আজ আজকের ಇಂದು ಇಂದಿನ ಇವತ್ತು ಇವತ್ತಿನ இன்று இன்றைய ఈరోజు నేడు నేటి ഇന്ന് ഇന്നത്തെ ଆଜି ଆଜିର আজি আজিৰ آج',
    cheapest: 'सस्ता सस्ते सस्ती सबसे-सस्ता कम स्वस्त स्वस्तात સસ્તું સસ્તો સસ્તા સસ્તી ਸਸਤਾ ਸਸਤੇ ਸਸਤੀ ਘੱਟ সস্তা সস্তায় কম ಕಡಿಮೆ ಅಗ್ಗ ಅಗ್ಗದ குறைவு குறைந்த குறைவான மலிவு மலிவான తక్కువ చౌక చౌకైన കുറഞ്ഞ കുറവ് വിലക്കുറവ് ଶସ୍ତା ଶସ୍ତାରେ ସସ୍ତା କମ সস্তীয়া سستا سستے سستی کم',
    making: 'मेकिंग घड़ाई गढ़ाई घडाई बनवाई मजदूरी मजुरी मजूरी घडणावळ चार्ज चार्जेस ઘડામણ ઘડાઈ મેકિંગ મજૂરી ચાર્જ ਘੜਾਈ ਮੇਕਿੰਗ ਬਣਵਾਈ ਚਾਰਜ মজুরি মেকিং বানি চার্জ ಮೇಕಿಂಗ್ ಮಜೂರಿ ಚಾರ್ಜ್ செய்கூலி கூலி மேக்கிங் சார்ஜ் మేకింగ్ మజూరీ మజూరి తయారీ చార్జీ చార్జీలు ఛార్జీలు పణిక్కూలి പണിക്കൂലി പണിക്കുറവ് മേക്കിംഗ് മേക്കിങ് ചാർജ് ମେକିଂ ମଜୁରି ଗଢ଼ାଇ ଚାର୍ଜ বনোৱা মজুৰি চাৰ্জ میکنگ بنوائی مزدوری گھڑائی چارج چارجز',
    wastage: 'सेदारम वेस्टेज சேதாரம் తరుగు ತರುಗು',
    offer: 'ऑफर ऑफ़र ऑफर्स ऑफ़र्स ओफर छूट डिस्काउंट सवलत सूट ઑફર ઓફર ઑફર્સ ડિસ્કાઉન્ટ છૂટ ਆਫ਼ਰ ਆਫਰ ਛੋਟ ਡਿਸਕਾਊਂਟ অফার ছাড় ডিসকাউন্ট ಆಫರ್ ರಿಯಾಯಿತಿ ಡಿಸ್ಕೌಂಟ್ ஆஃபர் ஆபர் தள்ளுபடி சலுகை ఆఫర్ ఆఫర్లు డిస్కౌంట్ తగ్గింపు రాయితీ ഓഫർ ഓഫറ ഡിസ്കൗണ്ട് കിഴിവ് ଅଫର ରିହାତି ଡିସକାଉଣ୍ଟ অফাৰ ৰেহাই ডিচকাউণ্ট آفر آفرز چھوٹ ڈسکاؤنٹ رعایت',
    diwali: 'दिवाली दीवाली दिवाळी धनतेरस धनत्रयोदशी अक्षय દિવાળી ધનતેરસ ਦੀਵਾਲੀ দীপাবলি দিওয়ালি ধনতেরাস ದೀಪಾವಳಿ ಅಕ್ಷಯ தீபாவளி அட்சய దీపావళి అక్షయ ദീപാവലി അക്ഷയ ଦୀପାବଳି ଧନତେରସ দীপাৱলী ধনতেৰাছ دیوالی دھنتیرس',
    yesterday: 'कल काल ગઈકાલ ગઈકાલે ਕੱਲ੍ਹ ਕੱਲ গতকাল ಮೊನ್ನೆ ನಿನ್ನೆ நேற்று నిన్న ഇന്നലെ ଗତକାଲି যোৱাকালি کل',
    trend: 'ट्रेंड इतिहास ટ્રેન્ડ ઇતિહાસ ਟ੍ਰੈਂਡ ইতিহাস ಟ್ರೆಂಡ್ ಇತಿಹಾಸ டிரெண்ட் வரலாறு ట్రెండ్ చరిత్ర ട്രെൻഡ് ചരിത്രം ଟ୍ରେଣ୍ଡ ଇତିହାସ ট্ৰেণ্ড ٹرینڈ تاریخ',
    gram: 'ग्राम ग्रॅम ग्राम्स ગ્રામ ਗ੍ਰਾਮ গ্রাম ಗ್ರಾಂ ಗ್ರಾಮ್ ಗ್ರಾಮು கிராம் గ్రాములు గ్రాము గ్రాం ഗ്രാം ഗ്രാമിന് ଗ୍ରାମ গ্ৰাম گرام',
    tola: 'तोला तोले तोळा तोळे તોલા તોલો ਤੋਲਾ ਤੋਲੇ ভরি তোলা ತೊಲ ತೊಲೆ தோலா తులం తులాలు തോല ତୋଳା ଭରି ভৰি تولہ تولے تولا',
    sovereign: 'पवन सॉवरेन பவுன் சவரன் ಪವನ್ పవను సవరన్ പവൻ പവന്',
    kg: 'किलो કિલો ਕਿੱਲੋ কেজি ಕೆಜಿ கிலோ కిలో കിലോ କିଲୋ کلو',
    carat: 'कैरेट कॅरेट केरेट कैरट કેરેટ ਕੈਰਟ ਕੈਰੇਟ ক্যারেট ಕ್ಯಾರೆಟ್ கேரட் காரட் క్యారెట్ కేరట్ കാരറ്റ് ക്യാരറ്റ് କ୍ୟାରେଟ কেৰেট قیراط کیرٹ کیریٹ',
    chain: 'चेन चैन साखळी ચેન ਚੇਨ চেন ಚೈನ್ செயின் சங்கிலி చైన్ గొలుసు ചെയിൻ ଚେନ চেইন چین زنجیر',
    necklace: 'हार नेकलेस હાર નેકલેસ ਹਾਰ ਨੈਕਲੇਸ হার নেকলেস ನೆಕ್ಲೇಸ್ ಹಾರ நெக்லஸ் ஆரம் నెక్లెస్ హారం നെക്ലേസ് മാല ହାର ନେକଲେସ হাৰ নেকলেচ ہار نیکلس',
    ring: 'अंगूठी अँगूठी अंगूठियां रिंग अंगठी વીંટી રિંગ ਮੁੰਦਰੀ ਅੰਗੂਠੀ আংটি ಉಂಗುರ ರಿಂಗ್ மோதிரம் ரிங் ఉంగరం ఉంగరాలు రింగ్ മോതിരം ମୁଦି ରିଂ আঙঠি ৰিং انگوٹھی رنگ',
    bangle: 'चूड़ी चूड़ियां कंगन कड़ा बांगडी बांगड्या चुडी બંગડી ਚੂੜੀ ਕੰਗਣ চুড়ি বালা ಬಳೆ வளையல் గాజులు గాజు വള വളകൾ ଚୁଡ଼ି କଙ୍କଣ খাৰু چوڑی چوڑیاں کنگن کڑا',
    earrings: 'झुमका झुमके बाली बालियां कानातले कुड्या ઝુમખા બુટ્ટી ਝੁਮਕੇ ਵਾਲੀਆਂ ঝুমকা দুল ಕಿವಿಯೋಲೆ ಓಲೆ ಜುಮ್ಕಿ கம்மல் ஜிமிக்கி தோடு చెవిపోగులు జుంకాలు కమ్మలు കമ്മൽ ജിമിക്കി କାନଫୁଲ ଝୁମୁକା কাণফুলি جھمکے جھمکا بالی بالیاں',
    mangalsutra: 'मंगलसूत्र मंगळसूत्र મંગળસૂત્ર ਮੰਗਲਸੂਤਰ মঙ্গলসূত্র ಮಂಗಳಸೂತ್ರ ತಾಳಿ ಮಾಂಗಲ್ಯ தாலி மாங்கல்யம் తాళి మంగళసూత్రం താലി ମଙ୍ଗଳସୂତ୍ର মংগলসূত্ৰ منگلسوتر',
    pendant: 'पेंडेंट लॉकेट પેન્ડન્ટ ਪੈਂਡੈਂਟ লকেট ಪೆಂಡೆಂಟ್ டாலர் பெண்டன்ட் లాకెట్ పెండెంట్ ലോക്കറ്റ് ଲକେଟ لاکٹ پینڈنٹ',
    bracelet: 'ब्रेसलेट બ્રેસલેટ ਬ੍ਰੇਸਲੈੱਟ ব্রেসলেট ಬ್ರೇಸ್ಲೆಟ್ பிரேஸ்லெட் బ్రేస్లెట్ ബ്രേസ്ലെറ്റ് ବ୍ରେସଲେଟ ব্ৰেচলেট بریسلیٹ',
    coin: 'सिक्का सिक्के कॉइन नाणे નાણું સિક્કો સિક્કા ਸਿੱਕਾ ਸਿੱਕੇ কয়েন মুদ্রা ನಾಣ್ಯ காசு நாணயம் నాణెం కాయిన్ നാണയം കോയിൻ ମୁଦ୍ରା କଏନ মুদ্ৰা কইন سکہ سکے کوائن',
    hello: 'नमस्ते नमस्कार हेलो हैलो નમસ્તે નમસ્કાર ਅਕਾਲ ਹੈਲੋ নমস্কার হ্যালো ನಮಸ್ಕಾರ ಹಲೋ வணக்கம் ஹலோ నమస్కారం హలో നമസ്കാരം ഹലോ ନମସ୍କାର ହେଲୋ নমস্কাৰ سلام آداب ہیلو',
    thanks: 'धन्यवाद शुक्रिया थैंक्स आभार ધન્યવાદ આભાર ਧੰਨਵਾਦ ਸ਼ੁਕਰੀਆ ধন্যবাদ ಧನ್ಯವಾದ ಧನ್ಯವಾದಗಳು நன்றி ధన్యవాదాలు ధన్యవాదం നന്ദി ଧନ୍ୟବାଦ شکریہ',
    silver: 'चांदी चाँदी ચાંદી ਚਾਂਦੀ রুপো রূপা রুপা ಬೆಳ್ಳಿ வெள்ளி వెండి വെള്ളി ରୁପା ৰূপ ৰূপৰ چاندی',
    compare: 'तुलना बनाम फरक फ़र्क़ फर्क अंतर तफावत ફરક સરખામણી ਫ਼ਰਕ ਤੁਲਨਾ তুলনা তফাত পার্থক্য ಹೋಲಿಕೆ ವ್ಯತ್ಯಾಸ ஒப்பீடு வித்தியாசம் పోలిక తేడా താരതമ്യം വ്യത്യാസം ତୁଳନା ଫରକ ପାର୍ଥକ୍ୟ পাৰ্থক্য موازنہ فرق مقابلہ',
    or: 'या किंवा અથવા ਜਾਂ নাকি ಅಥವಾ அல்லது లేదా അല്ലെങ്കിൽ କିମ୍ବା یا',
    my: 'मेरे मेरा मेरी माझ्या माझे माझा મારા મારું ਮੇਰੇ ਮੇਰਾ আমার ನನ್ನ என் எனது నా എന്റെ ମୋ ମୋର মোৰ میرے میرا میری',
    city: 'शहर शहरात શહેર શહેરમાં ਸ਼ਹਿਰ শহর শহরে ನಗರ ನಗರದ ಊರು ಊರಿನ நகரம் நகரில் ஊர் ఊరు నగరం నగరంలో നഗരം നഗരത്തിലെ ସହର ସହରରେ চহৰ চহৰত شہر',
    nearby: 'पास नज़दीक नजदीक जवळ પાસે નજીક ਨੇੜੇ কাছে ಹತ್ತಿರ அருகில் దగ్గర അടുത്ത് ପାଖରେ ନିକଟ ওচৰত ওচৰ پاس قریب نزدیک',
    best: 'बढ़िया बेस्ट श्रेष्ठ सर्वोत्तम શ્રેષ્ઠ ਵਧੀਆ সেরা ಉತ್ತಮ சிறந்த ఉత్తమ മികച്ച ଶ୍ରେଷ୍ଠ শ্ৰেষ্ঠ بہترین',
    alert: 'अलर्ट ઍલર્ટ અલર્ટ ਅਲਰਟ অ্যালার্ট ಅಲರ್ಟ್ அலர்ட் అలర్ట్ അലർട്ട് ଆଲର୍ଟ এলাৰ্ট الرٹ',
    buy: 'खरीद ख़रीद खरीदना खरेदी ખરીદ ખરીદી ਖ਼ਰੀਦ ਖਰੀਦ কেনা কিনব ಖರೀದಿ வாங்க వాంగ కొనడం కొనాలా വാങ്ങ କିଣିବା କିଣିବି কিনিব خرید خریدنا',
    time: 'समय वेळ સમય ਸਮਾਂ সময় ಸಮಯ நேரம் సమయం സമയം ସମୟ وقت',
    where: 'कहाँ कहां कहा कुठे ક્યાં ਕਿੱਥੇ কোথায় ಎಲ್ಲಿ எங்கே ఎక్కడ എവിടെ କେଉଁଠି کہاں',
    vs: 'बनाम विरुद्ध بمقابلہ',
    // Little words that carry no meaning here; listed so they are never
    // mistaken for a jeweller's name ("कहाँ" is not Khazana).
    _: 'का की के को में मे है हैं हे था थी क्या से पर और भी तो ही कौन कौनसा सा वाला वाले आप मुझे बताओ बताइए बताएं चाहिए मिलेगा मिलता होगा रहा रही ' +
       'आहे चा ची चे च्या ला ना काय मला सांगा आणि होता ' +
       'છે નો ની નું ના માં શું મને કહો અને હતો ' +
       'ਦਾ ਦੀ ਦੇ ਵਿੱਚ ਹੈ ਕੀ ਮੈਨੂੰ ਦੱਸੋ ਅਤੇ ' +
       'কি কী এর আছে আমাকে বলুন এবং ' +
       'ಏನು ಇದೆ ಹೇಳಿ ಮತ್ತು ನನಗೆ ' +
       'என்ன உள்ளது சொல்லுங்கள் மற்றும் எனக்கு ' +
       'ఏమిటి ఉంది చెప్పండి మరియు నాకు ' +
       'എന്ത് ഉണ്ട് പറയൂ ഒപ്പം എനിക്ക് ' +
       'ର ରେ କୁ କଣ ଅଛି କୁହନ୍ତୁ ଏବଂ ମୋତେ ଟି ହେବ କି ' +
       'আৰু কওক নেকি মোক ' +
       'کا کی کے کو میں ہے ہیں تھا تھی کیا سے پر اور بھی تو ہی کون سا والا والے آپ مجھے بتاؤ بتائیے بتائیں چاہیے ملے گا ہوگا رہا رہی'
  };
  // Numbers, per language: the same word means different numbers in
  // different languages (Tamil எட்டு is 8, Telugu ఏడు is 7), so only the
  // asker's own are used.
  var NUMS = {
    hi: 'एक:1 दो:2 तीन:3 चार:4 पांच:5 पाँच:5 छह:6 छः:6 सात:7 आठ:8 नौ:9 दस:10 ग्यारह:11 बारह:12 पंद्रह:15 अठारह:18 बीस:20 बाईस:22 चौबीस:24 पच्चीस:25 पचास:50 सौ:100 आधा:0.5',
    mr: 'एक:1 दोन:2 तीन:3 चार:4 पाच:5 सहा:6 सात:7 आठ:8 नऊ:9 दहा:10 अकरा:11 बारा:12 पंधरा:15 अठरा:18 वीस:20 बावीस:22 चोवीस:24 पंचवीस:25 पन्नास:50 शंभर:100 अर्धा:0.5',
    gu: 'એક:1 બે:2 ત્રણ:3 ચાર:4 પાંચ:5 છ:6 સાત:7 આઠ:8 નવ:9 દસ:10 અગિયાર:11 બાર:12 પંદર:15 અઢાર:18 વીસ:20 બાવીસ:22 ચોવીસ:24 પચીસ:25 પચાસ:50 સો:100 અડધો:0.5',
    pa: 'ਇੱਕ:1 ਇਕ:1 ਦੋ:2 ਤਿੰਨ:3 ਚਾਰ:4 ਪੰਜ:5 ਛੇ:6 ਸੱਤ:7 ਅੱਠ:8 ਨੌਂ:9 ਦਸ:10 ਬਾਰਾਂ:12 ਅਠਾਰਾਂ:18 ਵੀਹ:20 ਬਾਈ:22 ਚੌਵੀ:24 ਪੰਜਾਹ:50 ਸੌ:100',
    bn: 'এক:1 দুই:2 তিন:3 চার:4 পাঁচ:5 ছয়:6 সাত:7 আট:8 দশ:10 বারো:12 আঠারো:18 কুড়ি:20 বাইশ:22 চব্বিশ:24 পঁচিশ:25 পঞ্চাশ:50 একশো:100',
    kn: 'ಒಂದು:1 ಒಂದ:1 ಎರಡು:2 ಮೂರು:3 ನಾಲ್ಕು:4 ಐದು:5 ಆರು:6 ಏಳು:7 ಎಂಟು:8 ಒಂಬತ್ತು:9 ಹತ್ತು:10 ಹನ್ನೆರಡು:12 ಹದಿನೆಂಟು:18 ಇಪ್ಪತ್ತು:20 ಇಪ್ಪತ್ತೆರಡು:22 ಇಪ್ಪತ್ನಾಲ್ಕು:24 ಐವತ್ತು:50 ನೂರು:100',
    ta: 'ஒன்று:1 ஒரு:1 இரண்டு:2 மூன்று:3 நான்கு:4 ஐந்து:5 ஆறு:6 ஏழு:7 எட்டு:8 ஒன்பது:9 பத்து:10 பன்னிரண்டு:12 பதினெட்டு:18 இருபது:20 இருபத்திரண்டு:22 இருபத்திநான்கு:24 இருபத்துநான்கு:24 ஐம்பது:50 நூறு:100',
    te: 'ఒకటి:1 ఒక:1 రెండు:2 మూడు:3 నాలుగు:4 ఐదు:5 ఆరు:6 ఏడు:7 ఎనిమిది:8 తొమ్మిది:9 పది:10 పన్నెండు:12 పద్దెనిమిది:18 ఇరవై:20 ఇరవైరెండు:22 ఇరవైనాలుగు:24 యాభై:50 వంద:100',
    or: 'ଏକ:1 ଦୁଇ:2 ତିନି:3 ଚାରି:4 ପାଞ୍ଚ:5 ଛଅ:6 ସାତ:7 ଆଠ:8 ନଅ:9 ଦଶ:10 ବାର:12 ଅଠର:18 କୋଡ଼ିଏ:20 ବାଇଶି:22 ଚବିଶି:24 ପଚିଶି:25 ପଚାଶ:50 ଶହେ:100',
    as: 'এক:1 দুই:2 তিনি:3 চাৰি:4 পাঁচ:5 ছয়:6 সাত:7 আঠ:8 দহ:10 বাৰ:12 ওঠৰ:18 বিশ:20 বাইশ:22 চব্বিশ:24 পঁচিশ:25 পঞ্চাশ:50 এশ:100',
    ur: 'ایک:1 دو:2 تین:3 چار:4 پانچ:5 چھ:6 سات:7 آٹھ:8 نو:9 دس:10 گیارہ:11 بارہ:12 پندرہ:15 اٹھارہ:18 بیس:20 بائیس:22 چوبیس:24 پچیس:25 پچاس:50 سو:100 آدھا:0.5',
    ml: 'ഒന്ന്:1 ഒരു:1 രണ്ട്:2 മൂന്ന്:3 നാല്:4 അഞ്ച്:5 ആറ്:6 ഏഴ്:7 എട്ട്:8 ഒമ്പത്:9 പത്ത്:10 പന്ത്രണ്ട്:12 പതിനെട്ട്:18 ഇരുപത്:20 ഇരുപത്തിരണ്ട്:22 ഇരുപത്തിനാല്:24 അമ്പത്:50 നൂറ്:100'
  };

  // Words are looked up within their own script: in Latin letters Bengali
  // কত ("how much") and Punjabi ਘੱਟ ("less") would read the same.
  var EXACT = null, PREFIX = null, NUMK = {}, UR = {}, URP = [];
  function scriptName(w) { var m = String(w).match(/[ऀ-ൿ]/); return m ? scriptOf(m[0].charCodeAt(0))[1] : ''; }
  function compile() {
    if (EXACT) return;
    EXACT = {}; PREFIX = {};
    Object.keys(LEX).forEach(function (tok) {
      LEX[tok].split(/\s+/).forEach(function (w) {
        if (AR.test(w)) { if (!UR[w]) UR[w] = tok; URP.push([w, tok]); return; }
        var k = key(romWord(w.replace(/-/g, ''))), sc = scriptName(w);
        if (!k) return;
        if (!EXACT[sc + ':' + k]) EXACT[sc + ':' + k] = tok;
        (PREFIX[sc] = PREFIX[sc] || []).push([k, tok]);
      });
    });
    Object.keys(PREFIX).forEach(function (sc) { PREFIX[sc].sort(function (a, b) { return b[0].length - a[0].length; }); });
    URP.sort(function (a, b) { return b[0].length - a[0].length; });
    Object.keys(NUMS).forEach(function (l) {
      NUMK[l] = {};
      NUMS[l].split(/\s+/).forEach(function (p) { var kv = p.split(':'); NUMK[l][AR.test(kv[0]) ? kv[0] : key(romWord(kv[0]))] = kv[1]; });
    });
  }
  function lexPrefix(k, sc) {
    var list = PREFIX[sc] || [];
    for (var i = 0; i < list.length; i++) {
      var e = list[i][0];
      if (k.indexOf(e) === 0 && (e.length >= 4 || (e.length === 3 && k.length - e.length <= 2))) return list[i][1];
    }
    return null;
  }

  // Case endings, in key spelling: "मुंबईत", "சென்னையில்", "హైదరాబాద్‌లో".
  var SUF = ['mathe', 'mate', 'mem', 'mam', 'man', 'ma', 'me', 'la', 'li', 'ali', 'il', 'ile', 'lil', 'lo', 'loni', 'ni', 'ne',
    'na', 'nu', 're', 'ra', 'ke', 'ka', 'ki', 'ce', 'ca', 'ci', 'te', 'at', 't', 'e', 'ar', 'er', 'tu', 'vic', 'il', 'iil'];
  function candidates(k) {
    var out = [k];
    SUF.forEach(function (s) { if (k.length - s.length >= 3 && k.slice(-s.length) === s) out.push(k.slice(0, -s.length)); });
    if (/iat(il)?$/.test(k)) out.push(k.replace(/iat(il)?$/, 'e'));      // Marathi पुण्यात -> Pune
    return out;
  }
  // The closest name (jeweller or city) to a spoken word: [word, score] or null.
  function nameMatch(k, vocab) {
    var best = null, bs = 9, cs = candidates(k);
    vocab.forEach(function (v) {
      var L = v[0].length;
      cs.forEach(function (c, ci) {
        var d;
        if (c === v[0]) d = ci ? 0.2 : 0;
        else if (L >= 4) {
          var thr = L >= 8 ? 2 : L >= 5 ? 1 : 0;
          if (thr && Math.abs(c.length - L) <= thr) { var e = lev(c, v[0]); if (e <= thr) d = e + (ci ? 0.2 : 0); }
          if (d === undefined && L >= 5 && c.length >= L && common(c, v[0]) >= L - 1) d = 1.5;
        }
        if (d !== undefined && d < bs) { bs = d; best = v[1]; }
      });
    });
    return best ? [best, bs] : null;
  }
  function vocabOf(words) {
    var seen = {}, out = [];
    words.forEach(function (w) {
      w = String(w || '').toLowerCase();
      if (w.length < 3 || /^(jewell?ers?|jewell?ery|jewels|gold|diamonds?|and|sons|the|of)$/.test(w)) return;
      var k = key(w);
      if (k.length >= 3 && !seen[k]) { seen[k] = 1; out.push([k, w]); }
    });
    return out;
  }

  // Urdu letters -> Latin, for names. Vowels are mostly unwritten in Urdu, so
  // names are compared by consonants alone: تنشق (t-n-sh-q) is Tanishq.
  var URL_ = { 'ا': 'a', 'آ': 'a', 'ب': 'b', 'پ': 'p', 'ت': 't', 'ٹ': 't', 'ث': 's', 'ج': 'j', 'چ': 'ch', 'ح': 'h', 'خ': 'kh',
    'د': 'd', 'ڈ': 'd', 'ذ': 'z', 'ر': 'r', 'ڑ': 'r', 'ز': 'z', 'ژ': 'zh', 'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'z', 'ط': 't',
    'ظ': 'z', 'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ک': 'k', 'ك': 'k', 'گ': 'g', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ں': 'n', 'و': 'o',
    'ہ': 'h', 'ھ': 'h', 'ۂ': 'h', 'ة': 'h', 'ی': 'i', 'ي': 'i', 'ے': 'e', 'ى': 'i' };
  function skel(k) { return k.replace(/[aeiouyvwh]/g, '').replace(/(.)\1+/g, '$1'); }
  function urdu(w, vocab) {
    var k = skel(key(w.split('').map(function (ch) { return URL_[ch] || ''; }).join(''))), best = null, bs = 9;
    if (k.length < 2) return null;
    (vocab || []).forEach(function (v) {
      var s = v[2] || (v[2] = skel(v[0])), d;
      if (s === k) d = 0;
      else if (k.length >= 4 && Math.abs(s.length - k.length) <= 1 && lev(s, k) <= 1) d = 1;
      if (d !== undefined && d < bs) { bs = d; best = v[1]; }
    });
    return best;
  }
  function urPrefix(w) {
    for (var i = 0; i < URP.length; i++) {
      var e = URP[i][0];
      if (e.length >= 3 && w.indexOf(e) === 0 && w.length - e.length <= 3) return URP[i][1];
    }
    return null;
  }

  var DIGITS = /[०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯]/g;
  var MR = /(आहे|किती|काय|मध्ये|सोन्या|आजचा|आजचे|कुठे|माझ्या|स्वस्त|तोळ|आणि|ाचा|ाचे|ाची|्यात)/;
  // Assamese is written in the Bengali script, with its own ৰ and ৱ.
  var AS = /([ৰৱ]|সোণ|আজি|কিমান|নেকি|মোৰ)/;
  // Hindi's own words, to tell it from Marathi in the same script.
  var HI = /(है|हैं|क्या|कहाँ|कहां|कितना|कितने|कितनी|बताओ|बताइए|बताइये|सबसे|में|चाहिए|मुझे|रहा|रही|वाला|वाली|(^|\s)(का|की|के|को)(\s|$))/g;
  var MRG = new RegExp(MR.source, 'g');
  // cur: the language so far; pinned: the visitor chose it (keep it when the
  // words could be either). Otherwise Hindi or Marathi is decided by the
  // words of this question alone, so a visitor can switch freely.
  function detect(q, cur, pinned) {
    if (AR.test(q)) return 'ur';
    var m = String(q).match(/[ऀ-ൿ]/);
    if (!m) return null;
    var b = scriptOf(m[0].charCodeAt(0));
    if (b[1] === 'deva') {
      if (pinned && (cur === 'mr' || cur === 'hi')) return cur;
      var nm = (q.match(MRG) || []).length, nh = (q.match(HI) || []).length;
      return nm > nh ? 'mr' : nh > nm ? 'hi' : (cur === 'mr' ? 'mr' : 'hi');
    }
    if (b[1] === 'beng') return cur === 'as' || AS.test(q) ? 'as' : 'bn';
    return SCRIPT_LANG[b[1]];
  }

  // Hindi or Marathi typed in English letters ("aaj sone ka bhav kya hai",
  // "sonyacha bhav kay aahe"): a few words only these languages use. Two
  // or more are needed, so an English question never trips it.
  var ROM = {
    mr: ['aahe', 'ahe', 'aahet', 'kay', 'kaay', 'madhe', 'madhye', 'mdhe', 'kuthe', 'kuthla', 'sanga', 'sang', 'kiti',
         'sonyacha', 'sonyache', 'sonyachi', 'sonyachya', 'swasta', 'mahag', 'ajcha', 'aajcha', 'aajche', 'majha',
         'mazha', 'maza', 'pahije', 'dakhva', 'ani', 'tola', 'kasa', 'kashi', 'naahi', 'nahi', 'aaj', 'sone', 'bhav', 'dar'],
    hi: ['kya', 'hai', 'hain', 'kahan', 'kaha', 'batao', 'bataiye', 'bataye', 'kitna', 'kitne', 'kitni', 'chahiye',
         'sabse', 'sasta', 'sasti', 'mein', 'mai', 'wala', 'wali', 'raha', 'rahi', 'karo', 'kijiye', 'ka', 'ki', 'ke',
         'aaj', 'sone', 'sona', 'bhav', 'nahi', 'mehenga', 'mehnga', 'kaise', 'kyun', 'acha', 'accha']
  };
  // Words both share count for neither on their own.
  var ROM_STRONG = { mr: ['aahe', 'ahe', 'aahet', 'kay', 'kaay', 'madhe', 'madhye', 'mdhe', 'kuthe', 'sanga', 'kiti',
    'sonyacha', 'sonyache', 'sonyachi', 'sonyachya', 'swasta', 'ajcha', 'aajcha', 'aajche', 'pahije', 'dakhva'],
    hi: ['kya', 'hai', 'hain', 'kahan', 'batao', 'bataiye', 'kitna', 'kitne', 'kitni', 'chahiye', 'sabse', 'sasta', 'mein', 'kijiye'] };
  function roman(q) {
    var ws = String(q || '').toLowerCase().split(/[^a-z]+/), best = null, bn = 0;
    ['mr', 'hi'].forEach(function (c) {
      var n = 0, s = 0;
      ws.forEach(function (w) { if (ROM[c].indexOf(w) > -1) n += 1; if (ROM_STRONG[c].indexOf(w) > -1) s += 1; });
      if (s >= 1 && n >= 2 && s > bn) { bn = s; best = c; }
    });
    return best;
  }

  // "in Hindi", "marathi madhe sanga", "speak Tamil", or just "Bangla":
  // the visitor asks for a language. Returns {c, rest}: the language, and
  // what is left of the question once the request is taken out.
  var NAMES = {
    en: ['english', 'angrezi', 'angreji', 'इंग्लिश', 'अंग्रेजी', 'अंग्रेज़ी', 'इंग्रजी'],
    hi: ['hindi', 'हिंदी', 'हिन्दी'], mr: ['marathi', 'मराठी'], gu: ['gujarati', 'gujrati', 'ગુજરાતી'],
    pa: ['punjabi', 'panjabi', 'ਪੰਜਾਬੀ'], bn: ['bengali', 'bangla', 'বাংলা'], as: ['assamese', 'asomiya', 'অসমীয়া'],
    or: ['odia', 'oriya', 'ଓଡ଼ିଆ', 'ଓଡିଆ'], ur: ['urdu', 'اردو'], kn: ['kannada', 'ಕನ್ನಡ'],
    ta: ['tamil', 'தமிழ்', 'தமிழில்'], te: ['telugu', 'తెలుగు', 'తెలుగులో'], ml: ['malayalam', 'മലയാളം', 'മലയാളത്തിൽ']
  };
  var FILL = ['in', 'me', 'mein', 'mai', 'madhe', 'madhye', 'mdhe', 'ma', 'mon', 'la', 'language', 'bhasha', 'please',
    'pls', 'plz', 'speak', 'talk', 'bolo', 'bol', 'boliye', 'bola', 'baat', 'karo', 'answer', 'reply', 'tell', 'batao',
    'bataiye', 'sanga', 'sang', 'can', 'you', 'now', 'from', 'only', 'switch', 'to', 'use', 'chat', 'write', 'type',
    'में', 'मध्ये', 'मे', 'बोलो', 'बोलिए', 'बताओ', 'बताइए', 'सांगा', 'बोला', 'भाषा', 'मधे', 'मध्ये'];
  function asked(q) {
    var ws = String(q || '').split(/[\s,.!?।॥;:()"“”‘’؟،۔]+/).filter(Boolean), c = null, at = -1;
    ws.forEach(function (w, i) {
      var l = w.toLowerCase();
      Object.keys(NAMES).forEach(function (k) { if (NAMES[k].indexOf(l) > -1) { c = k; at = i; } });
    });
    if (!c) return null;
    // the name and the request words right around it ("in", "me batao", "speak")
    var rest = ws.filter(function (w, i) {
      return i !== at && !(Math.abs(i - at) <= 5 && FILL.indexOf(w.toLowerCase()) > -1);
    });
    return { c: c, rest: rest.join(' ') };
  }

  // A question in any script -> the words the answer engine knows.
  // vocab: [key, word] for the jewellers and cities (vocabOf()).
  function understand(q, vocab, lang) {
    compile();
    q = String(q || '').replace(/[​-‍]/g, '')
      .replace(DIGITS, function (d) { return String((d.charCodeAt(0) - 0x66) % 16); })
      .replace(/[۰-۹٠-٩]/g, function (d) { return String(d.charCodeAt(0) % 16); })
      .replace(/[\u064B-\u0652\u0670]/g, '')
      .replace(/(\d)([ऀ-ൿ])/g, '$1 $2').replace(/([ऀ-ൿ])(\d)/g, '$1 $2');
    var nums = NUMK[lang] || {}, out = [], indic = false;
    q.split(/[\s,?!।॥;:()"“”‘’؟،۔]+/).forEach(function (w) {
      if (!w) return;
      if (!isIndic(w)) { out.push(w.toLowerCase()); return; }
      indic = true;
      if (AR.test(w)) {
        var u = nums[w] || UR[w] || urdu(w, vocab) || urPrefix(w);
        if (u) out.push(u);
        return;
      }
      var k = key(romWord(w)), sc = scriptName(w);
      if (nums[k]) { out.push(nums[k]); return; }
      if (EXACT[sc + ':' + k]) { out.push(EXACT[sc + ':' + k]); return; }
      var nm = nameMatch(k, vocab || []);
      if (nm && nm[1] <= 1) { out.push(nm[0]); return; }
      var lx = lexPrefix(k, sc);
      if (lx) { out.push(lx); return; }
      if (nm) out.push(nm[0]);
    });
    return { text: out.filter(function (w) { return w !== '_'; }).join(' '), indic: indic };
  }

  root.SONA_LANG = { LANGS: LANGS, romWord: romWord, key: key, detect: detect, understand: understand, roman: roman, asked: asked,
    vocabOf: vocabOf, isIndic: isIndic, LEX: LEX };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.SONA_LANG;
})(typeof window !== 'undefined' ? window : globalThis);

/* Sona - the MyGoldRates jewellery assistant.
 *
 * Answers in the visitor's browser from /assistant.json, which the site build
 * writes every run from the same data as the pages (assistant_kb.py). No
 * server, no paid AI: questions are matched to an intent (rate, cheapest,
 * compare, making charges, offers, price of a weight, trend, FAQ...) and the
 * answer is filled in with today's real numbers, so it can never invent one.
 *
 * Questions are logged to the private database (redacted: no emails or long
 * numbers) so the owner can see what people ask and approve answers for the
 * ones Sona could not handle; approved answers come back through the
 * knowledge file (data/assistant_answers.json in git).
 *
 * Voice and languages, also free: the browser's own speech recognition
 * (tap the mic) and its own voices (read aloud), in English and nine Indian
 * languages. A question in an Indian script is turned into the words this
 * engine knows by sona_lang.js; replies come from sona_i18n.js. The build
 * puts all three in one file, /assistant.js.
 */
(function () {
  if (window.__sona) return; window.__sona = 1;
  var TEST = !!window.__SONA_TEST;
  if (!TEST && /^\/(analytics|unsubscribe|404)(\.html)?\/?$/.test(location.pathname)) return;

  var SB = (window.GR_SB_URL || '').replace(/\/$/, ''), KEY = window.GR_SB_KEY || '';
  var KB = null, kbWait = null, opened = false, home = null, wantHome = false, wantOffer = false;
  // "My city" is the visitor's own city: one they said they live in, picked
  // when Sona asked, or the nearest to the phone's location (worked out on
  // the device, only when they tap for it). Never just the last city asked
  // about - that was 'sona_city', dropped here.
  try { home = localStorage.getItem('sona_home'); localStorage.removeItem('sona_city'); } catch (_) {}
  var LG = window.SONA_LANG, STR = window.SONA_STR || {};
  // Language is automatic. Each reply is in the language of its question
  // (the script it is written in). The browser's free speech recogniser
  // must be told which language to listen for, so the mic listens in the
  // last Indian language Sona read or heard from this visitor - at first the
  // phone's own language, else Hindi, whose recogniser also takes English.
  // A visitor can pin one language instead (PICK).
  var PICK = '', HEARD = '', PHONE = '';
  try { PICK = localStorage.getItem('sona_pick') || ''; HEARD = localStorage.getItem('sona_heard') || ''; } catch (_) {}
  if (!STR[PICK]) PICK = '';
  if (!STR[HEARD]) HEARD = '';
  (navigator.languages || [navigator.language || '']).some(function (l) {
    var c = String(l).slice(0, 2).toLowerCase();
    if (STR[c] && c !== 'en') { PHONE = c; return true; }
    return false;
  });
  function uiLang() { return PICK || HEARD || PHONE || 'en'; }
  function micLang() { return PICK || HEARD || PHONE || 'hi'; }
  var LANG = uiLang(), RL = LANG;      // the language of the labels; of this reply
  // Text in the reply language, falling back to English: t('city_h', {c: 'Pune'}).
  function fill(s, v) { return String(s).replace(/\{(\w+)\}/g, function (_, n) { return v && v[n] != null ? v[n] : ''; }); }
  function t(k, v) { return fill((STR[RL] && STR[RL][k]) || (STR.en && STR.en[k]) || k, v); }
  function en(k, v) { return fill((STR.en && STR.en[k]) || k, v); }
  // Urdu reads right to left.
  function rtl(c) { return (LG ? LG.LANGS : []).some(function (x) { return x.c === c && x.rtl; }); }
  function langName(c) { var l = (LG ? LG.LANGS : []).filter(function (x) { return x.c === c; })[0]; return l ? l.n : c; }

  // ------------------------------------------------------------ helpers
  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  // A price stays "₹12,958" inside right-to-left (Urdu) text too.
  function inr(n) { return '<bdi dir="ltr">₹' + Math.round(n).toLocaleString('en-IN') + '</bdi>'; }
  function pct(n) { return (Math.round(n * 10) / 10).toLocaleString('en-IN') + '%'; }
  var K = { '24K': 1, '22K': 22 / 24, '18K': 18 / 24, '14K': 14 / 24 };
  function rate(b, k) { return b.r24 * K[k]; }
  // For speaking: "12,879 rupees", "22 carat".
  function sInr(n) { return Math.round(n).toLocaleString('en-IN') + ' ' + t('rupees'); }
  function sK(k) { return String(k).replace('K', '') + ' ' + t('carat'); }
  function catName(c) { return (STR[RL] && STR[RL]['c_' + c]) || (STR.en && STR.en['c_' + c]) || String(c).toLowerCase(); }
  function wLabel(w) { return t('u_' + w.u, { n: w.n }); }
  function track(what) { try { if (window.GR_TRACK) window.GR_TRACK('click_events', { page: location.pathname, target: 'sona:' + what, session_id: window.GR_SID || '' }); } catch (_) {} }
  function rpc(fn, body) {
    if (!SB || !KEY) return Promise.resolve(null);
    return fetch(SB + '/rest/v1/rpc/' + fn, { method: 'POST', headers: { 'Content-Type': 'application/json', apikey: KEY, Authorization: 'Bearer ' + KEY }, body: JSON.stringify(body) })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function redact(q) { return String(q).replace(/[^\s@]+@[^\s@]+/g, '[email]').replace(/\+?\d[\d\s-]{6,}\d/g, '[number]').slice(0, 300); }

  function loadKB() {
    if (KB) return Promise.resolve(KB);
    if (kbWait) return kbWait;
    kbWait = fetch('/assistant.json?d=' + new Date().toISOString().slice(0, 13)).then(function (r) { return r.json(); })
      .then(function (d) { KB = d; prep(d); return d; });
    return kbWait;
  }

  // ------------------------------------------------------- understanding
  var CITY_ALIAS = { bangalore: 'bengaluru', bombay: 'mumbai', calcutta: 'kolkata', madras: 'chennai', gurgaon: 'gurugram', vizag: 'visakhapatnam', mysore: 'mysuru', trivandrum: 'thiruvananthapuram', calicut: 'kozhikode', cochin: 'kochi', ernakulam: 'kochi', baroda: 'vadodara', pondicherry: 'puducherry', benaras: 'varanasi', banaras: 'varanasi', poona: 'pune', mangalore: 'mangaluru', hubli: 'hubballi', 'new delhi': 'delhi', ncr: 'delhi' };
  var BRAND_EXTRA = { tbz: 'tbz', 'pn gadgil and sons': 'pngsons', 'png sons': 'pngsons', 'pn gadgil & sons': 'pngsons', 'pn gadgil': 'png', png: 'png', gadgil: 'png', whp: 'whp', 'waman hari': 'whp', ckc: 'ckc', krishniah: 'ckc', 'pc chandra': 'pcchandra', grt: 'grt', avr: 'avr', nac: 'nac', 'jos alukkas': 'josalukkas', joyalukkas: 'joyalukkas', 'joy alukkas': 'joyalukkas' };
  // Spoken names that are not how the site spells them.
  var SPOKEN = { dilli: 'delhi', bambai: 'mumbai', bambay: 'mumbai', kalkatta: 'kolkata', madras: 'chennai', banglore: 'bengaluru',
    amdavad: 'ahmedabad', vadodra: 'vadodara', koyambuthur: 'coimbatore', kovai: 'coimbatore', trichy: 'tiruchirappalli',
    tiruchi: 'tiruchirappalli', thiruvananthapuram: 'thiruvananthapuram', kashi: 'varanasi', prayagraj: 'allahabad',
    gurgaon: 'gurugram', bhagyanagar: 'hyderabad', belgaum: 'belagavi', vishakhapatnam: 'visakhapatnam', kozhikkode: 'kozhikode' };
  var aliases = [], cityIdx = [], VOCAB = [];
  function prep(d) {
    aliases = [];
    d.brands.forEach(function (b) {
      var n = b.n.toLowerCase().replace(/[.]/g, '');
      var short = n.replace(/\b(jewell?ers?|jewell?ery|jewels|gold|diamonds?|and|&|sons|swarna mahal|bangaru)\b/g, ' ').replace(/\s+/g, ' ').trim();
      [n, short, b.s].forEach(function (a) { if (a && a.length >= 3) aliases.push([a, b.s]); });
    });
    Object.keys(BRAND_EXTRA).forEach(function (a) { if (d.brands.some(function (b) { return b.s === BRAND_EXTRA[a]; })) aliases.push([a, BRAND_EXTRA[a]]); });
    aliases.sort(function (x, y) { return y[0].length - x[0].length; });     // longest first: "pn gadgil & sons" before "pn gadgil"
    cityIdx = d.cities.map(function (c) { return [c.n.toLowerCase(), c]; }).sort(function (x, y) { return y[0].length - x[0].length; });
    // Names to match by sound in a question asked in an Indian script.
    if (LG) {
      var words = [];
      aliases.forEach(function (a) { words = words.concat(a[0].split(/[\s&]+/)); });
      d.cities.forEach(function (c) { words = words.concat(c.n.toLowerCase().split(/\s+/)); });
      VOCAB = LG.vocabOf(words.concat(Object.keys(CITY_ALIAS)));
      Object.keys(SPOKEN).forEach(function (s) { VOCAB.push([LG.key(s), SPOKEN[s]]); });
    }
  }
  function norm(q) {
    return (' ' + q.toLowerCase() + ' ')
      .replace(/[‘’']/g, '')
      .replace(/\b(24|22|18|14)\s*(?:k|kt|ct|carat|karat|caret)\b/g, ' $1k ')
      .replace(/\b999\b/g, ' 24k ').replace(/\b916\b/g, ' 22k ').replace(/\b750\b/g, ' 18k ')
      .replace(/[?!,;:()]/g, ' ').replace(/\s+/g, ' ');
  }
  function brandsIn(t) {
    var found = [], used = t;
    aliases.forEach(function (a) {
      var rx = new RegExp('(^|[^a-z])' + a[0].replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?=$|[^a-z])');
      if (rx.test(used) && found.indexOf(a[1]) < 0) { found.push(a[1]); used = used.replace(rx, '$1 '); }
    });
    return found.map(function (s) { return KB.brands.filter(function (b) { return b.s === s; })[0]; }).filter(Boolean);
  }
  function cityIn(t) {
    Object.keys(CITY_ALIAS).forEach(function (a) { t = t.replace(new RegExp('\\b' + a + '\\b', 'g'), CITY_ALIAS[a]); });
    for (var i = 0; i < cityIdx.length; i++) if (new RegExp('\\b' + cityIdx[i][0] + '\\b').test(t)) return cityIdx[i][1];
    return null;
  }
  function karatIn(t) { var m = t.match(/\b(24|22|18|14)k\b/); return m ? m[1] + 'K' : null; }
  function weightIn(t) {
    var m = t.match(/(\d+(?:\.\d+)?)\s*(?:g|gm|gms|gram|grams|gr)\b/); if (m) return { g: +m[1], n: m[1], u: 'g' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:tola|tolas|tole)\b/); if (m) return { g: +m[1] * 11.664, n: m[1], u: 'tola' };
    m = t.match(/\b(?:a|one|1)\s*tola\b/); if (m) return { g: 11.664, n: '1', u: 'tola' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:sovereign|sovereigns|pavan|pavun|pawan)\b/); if (m) return { g: +m[1] * 8, n: m[1], u: 'sov' };
    m = t.match(/(\d+(?:\.\d+)?)\s*(?:kg|kilo)\b/); if (m) return { g: +m[1] * 1000, n: m[1], u: 'kg' };
    return null;
  }
  var CATS = { ring: 'Ring', rings: 'Ring', chain: 'Chain', chains: 'Chain', bangle: 'Bangle', bangles: 'Bangle', kada: 'Bangle', necklace: 'Necklace', haar: 'Necklace', earring: 'Earrings', earrings: 'Earrings', jhumka: 'Earrings', mangalsutra: 'Mangalsutra', pendant: 'Pendant', bracelet: 'Bracelet', coin: 'Coin', coins: 'Coin' };
  function catIn(t) { for (var w in CATS) if (new RegExp('\\b' + w + '\\b').test(t)) return CATS[w]; return null; }
  function has(t, words) { return words.some(function (w) { return new RegExp('\\b' + w + '\\b').test(t); }); }
  var W = {
    rate: ['rate', 'rates', 'price', 'prices', 'bhav', 'bhaav', 'bhaw', 'daam', 'dam', 'kimat', 'keemat', 'kitna', 'kitne', 'cost', 'today', 'aaj', 'current', 'live'],
    cheap: ['cheapest', 'lowest', 'cheap', 'sasta', 'sabse', 'best', 'least', 'minimum', 'lower', 'cheaper', 'where'],
    making: ['making', 'wastage', 'va', 'labour', 'labor', 'mc', 'value addition'],
    offer: ['offer', 'offers', 'discount', 'discounts', 'deal', 'deals', 'sale', 'dhanteras', 'diwali', 'akshaya', 'free', 'cashback', 'promotion'],
    trend: ['trend', 'history', 'yesterday', 'kal', 'week', 'month', 'up', 'down', 'increase', 'decrease', 'change', 'changed', 'chart', 'graph', 'movement', 'rising', 'falling', 'last'],
    compare: ['vs', 'versus', 'compare', 'comparison', 'or', 'better', 'difference', 'between'],
    hello: ['hi', 'hello', 'hey', 'namaste', 'namaskar', 'hii', 'helo', 'good morning', 'good evening'],
    thanks: ['thanks', 'thank', 'thx', 'dhanyavad', 'shukriya', 'great', 'awesome', 'nice', 'ok', 'okay'],
    who: ['who are you', 'what are you', 'your name', 'what can you do', 'help', 'kaun', 'how do you work'],
    silver: ['silver', 'chandi', 'chaandi', 'platinum']
  };

  // ------------------------------------------------------------ answers
  // Each returns {html, say?, chips?, intent}. html is built from KB values
  // only; say is the same answer in a sentence or two, for reading aloud.
  function natBrands() { return KB.brands.filter(function (b) { return b.nat; }); }
  function ranked(list, k) { return list.slice().sort(function (a, b) { return a.r24 - b.r24; }); }
  function rankOf(b, list) { var r = ranked(list); for (var i = 0; i < r.length; i++) if (r[i].s === b.s) return i + 1; return null; }
  function link(u, tx) { return '<a href="' + esc(u) + '">' + tx + '</a>'; }
  function src() { return '<div class="sn-src">' + t('src', { n: KB.brands.length, d: esc(KB.date) }) + '</div>'; }
  // A suggestion chip: shown in the reply language, asked in English.
  function chip(k, v) { return { l: t('ch_' + k, v), q: en('ch_' + k, v) }; }
  function chips(keys) { return keys.map(function (k) { return chip(k); }); }
  function suggest() { return chips(SUGGEST); }
  function cityBrands(c) {
    var loc = (c && c.loc) || [];
    return KB.brands.filter(function (b) { return b.nat || loc.indexOf(b.s) > -1; });
  }
  function table(rows, k) {
    return '<div class="sn-list">' + rows.map(function (b, i) {
      return '<div class="sn-row"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm">' + (b.u ? link(b.u, esc(b.n)) : esc(b.n)) + (b.nat ? '' : ' <em>local</em>') + '</span><span class="sn-v">' + inr(rate(b, k)) + '<small>/g</small></span></div>';
    }).join('') + '</div>';
  }
  function tiles(m, k) {
    return '<div class="sn-tiles">' + ['24K', '22K', '18K'].map(function (x) {
      return '<div' + (x === k ? ' class="on"' : '') + '><b>' + inr(m[x]) + '</b><span>' + x + ' /g</span></div>';
    }).join('') + '</div>';
  }

  // Shops and banks whose prices Sona does not track ("999 rate on Amazon"):
  // say so, give today's jeweller rate to compare, and a Google search the
  // visitor opens themselves - Sona never quotes a price from the web.
  var STORES = { amazon: 'Amazon', flipkart: 'Flipkart', myntra: 'Myntra', ajio: 'AJIO', 'tata cliq': 'Tata CLiQ', tatacliq: 'Tata CLiQ',
    nykaa: 'Nykaa', meesho: 'Meesho', jiomart: 'JioMart', mmtc: 'MMTC-PAMP', augmont: 'Augmont', safegold: 'SafeGold',
    sbi: 'SBI', hdfc: 'HDFC Bank', icici: 'ICICI Bank', axis: 'Axis Bank', kotak: 'Kotak Bank', 'post office': 'the post office',
    bank: 'banks', banks: 'banks', zepto: 'Zepto', blinkit: 'Blinkit', swiggy: 'Swiggy Instamart', bigbasket: 'BigBasket' };
  function storeIn(t) { for (var s in STORES) if (new RegExp('\\b' + s + '\\b').test(t)) return STORES[s]; return null; }
  var rawQ = '';
  function gLink(q) {
    return '<p><a class="sn-g" href="https://www.google.com/search?q=' + encodeURIComponent(q || rawQ) + '" target="_blank" rel="noopener nofollow">\ud83d\udd0e Google</a></p>';
  }
  function aOutside(store, k) {
    k = k || '24K';
    var en = 'I don\'t track ' + store + (/s$/.test(store) ? '\'' : '\'s') + ' prices - my rates come from jewellers\' own websites. To compare, here is today\'s middle rate at ' +
      KB.brands.length + ' jewellers. Tap Google to look up ' + store + '.';
    return { intent: 'outside', en: en, html: '<p>' + esc(en) + '</p>' + tiles(KB.med, k) + gLink(), say: en,
      chips: chips(['cheap22', 'bestoff']) };
  }
  function aMedian(k) {
    k = k || '22K';
    var m = KB.med, low = ranked(natBrands())[0];
    return { intent: 'rate', html: '<p>' + t('med_h', { n: KB.brands.length }) + '</p>' + tiles(m, k) +
      '<p>' + t('med_low', { b: esc(low.n), p: inr(rate(low, '22K')) }) + '</p>' + src(),
      say: t('say_med', { k: sK(k), p: sInr(m[k]), n: KB.brands.length, b: low.n, q: sInr(rate(low, k)) }),
      chips: chips(['cheap22', 'mycity', 'p10']) };
  }
  function aBrand(b, k) {
    k = k || '22K';
    var list = b.nat ? natBrands() : KB.brands, r = rankOf(b, list), n = list.length;
    var diff = rate(b, k) - KB.med[k];
    var rel = Math.abs(diff) < 1 ? t('rel_at', { k: k }) : t(diff < 0 ? 'rel_below' : 'rel_above', { k: k, p: inr(Math.abs(diff)) });
    var h = '<p>' + t('brand_h', { b: esc(b.n) }) + '</p>' + tiles({ '24K': rate(b, '24K'), '22K': rate(b, '22K'), '18K': rate(b, '18K') }, k) +
      '<p>' + t('brand_rank', { r: r, n: n, rel: rel }) + '</p>';
    if (b.mk) h += '<p>' + t('brand_mk', { list: Object.keys(b.mk).map(function (c) { return esc(catName(c)) + ' ' + pct(b.mk[c]); }).join(', ') }) + '</p>';
    if (b.off && b.off.length) h += '<p>' + t('brand_off', { o: esc(b.off[0].h) }) + '</p>';
    if (!b.nat && b.st) h += '<p class="sn-dim">' + t('brand_st', { s: esc(b.st.join(', ')) }) + '</p>';
    if (b.u) h += '<p>' + link(b.u, t('brand_link', { b: esc(b.n) })) + '</p>';
    var nm = b.n.split(' ')[0];
    return { intent: 'rate_brand', html: h + src(), say: t('say_brand', { b: b.n, k: sK(k), p: sInr(rate(b, k)), r: r, n: n }),
      chips: [chip('bmk', { b: nm }), chip('boff', { b: nm }), chip('cheap22')] };
  }
  function aCity(c, k) {
    k = k || '22K';
    var list = ranked(cityBrands(c)).slice(0, 6), locals = (c.loc || []).length;
    var note = locals ? t('city_loc', { l: locals, s: esc(c.st) }) : t('city_nat');
    return { intent: 'rate_city', html: '<p>' + t('city_h', { k: k, c: esc(c.n), note: note }) + '</p>' + table(list, k) +
      '<p>' + link(c.u, t('city_link', { c: esc(c.n) })) + '</p>' + src(),
      say: t('say_city', { c: c.n, k: sK(k), b: list[0].n, p: sInr(rate(list[0], k)) }),
      chips: chips(['p10', 'bestoff', 'k22v24']).concat(c.n === home ? [{ l: t('ch_chcity'), q: '#city' }] : []) };
  }
  function setHome(c) { home = c.n; try { localStorage.setItem('sona_home', c.n); } catch (_) {} }
  // Which city? The visitor's next city answer becomes their own.
  function askCity(msg) {
    wantHome = true;
    var geo = typeof navigator !== 'undefined' && navigator.geolocation;
    return { intent: 'ask_city', html: '<p>' + t(msg) + '</p>', say: t(msg),
      chips: (geo ? [{ l: '📍 ' + t('ch_loc'), q: '#loc' }] : []).concat(['Mumbai', 'Delhi', 'Bengaluru', 'Chennai', 'Hyderabad', 'Kolkata', 'Pune', 'Lucknow']
        .map(function (n) { return { l: n, q: n }; })) };
  }
  // The covered city nearest a point (the knowledge file's centres, "g").
  function nearest(la, lo) {
    var r = Math.PI / 180, best = null, bd = 1e9;
    KB.cities.forEach(function (c) {
      if (!c.g) return;
      var x = Math.sin((c.g[0] - la) * r / 2), y = Math.sin((c.g[1] - lo) * r / 2);
      var d = 12742 * Math.asin(Math.sqrt(x * x + Math.cos(la * r) * Math.cos(c.g[0] * r) * y * y));
      if (d < bd) { bd = d; best = c; }
    });
    return best;
  }
  // all: every national jeweller, cheapest to dearest ("compare jewellers").
  function aCheapest(k, c, all) {
    if (c) return aCity(c, k);
    k = k || '22K';
    var list = ranked(natBrands()).slice(0, all ? 99 : 6), hi = ranked(natBrands()).slice(-1)[0];
    var gap = (rate(hi, k) - rate(list[0], k)) * 10;
    return { intent: 'cheapest', html: '<p>' + t('cheap_h', { k: k }) + '</p>' + table(list, k) +
      '<p>' + t('cheap_gap', { p: inr(gap) }) + '</p>' + src(),
      say: t('say_cheap', { k: sK(k), b: list[0].n, p: sInr(rate(list[0], k)), q: sInr(gap) }),
      chips: chips(['mycity', 'afteroff', 'mkcmp']) };
  }
  function aCompare(bs, k) {
    k = k || '22K';
    var h = '<p>' + t('cmp_h', { k: k }) + '</p><div class="sn-cmp">' + bs.slice(0, 3).map(function (b) {
      return '<div><div class="sn-cn">' + esc(b.n) + '</div><b>' + inr(rate(b, k)) + '<small>/g</small></b>' +
        '<span>' + t('cmp_10', { p: inr(rate(b, k) * 10) }) + '</span>' +
        (b.mk ? '<span>' + t('cmp_mk', { p: pct(b.mk.Ring || b.mk[Object.keys(b.mk)[0]]) }) + '</span>' : '<span class="sn-dim">' + t('cmp_nomk') + '</span>') +
        (b.off && b.off.length ? '<span class="sn-off">' + esc(b.off[0].h) + '</span>' : '') + '</div>';
    }).join('') + '</div>';
    var s = bs.slice(0, 3).sort(function (a, b) { return a.r24 - b.r24; });
    var gap = (rate(s[s.length - 1], k) - rate(s[0], k)) * 10;
    h += '<p>' + t('cmp_win', { b: esc(s[0].n), k: k, p: inr(gap) }) + '</p>';
    return { intent: 'compare', html: h + src(), say: t('say_cmp', { b: s[0].n, p: sInr(gap), k: sK(k) }),
      chips: chips(['afteroff', 'mkcmp', 'bestoff']) };
  }
  function aMaking(bs, ct) {
    var withMk = KB.brands.filter(function (b) { return b.mk; });
    if (bs.length) {
      var b = bs[0];
      if (!b.mk) return { intent: 'making', html: '<p>' + t('mk_none', { b: esc(b.n), list: withMk.map(function (x) { return esc(x.n); }).join(', ') }) + '</p><p>' + link('/making-charges-comparison', t('mk_link')) + '</p>',
        say: t('say_mk_none', { b: b.n }) };
      var c1 = ct && b.mk[ct] != null ? ct : (b.mk.Ring != null ? 'Ring' : Object.keys(b.mk)[0]);
      return { intent: 'making', html: '<p>' + t('mk_brand_h', { b: esc(b.n) }) + '</p><div class="sn-list">' +
        Object.keys(b.mk).map(function (c) { return '<div class="sn-row"><span class="sn-nm">' + esc(catName(c)) + '</span><span class="sn-v">' + pct(b.mk[c]) + '</span></div>'; }).join('') + '</div>' +
        '<p class="sn-dim">' + t('mk_note') + '</p><p>' + link('/making-charges-comparison', t('mk_all')) + '</p>',
        say: t('say_mk_brand', { b: b.n, c: catName(c1), p: pct(b.mk[c1]) }),
        chips: [chip('boff', { b: b.n.split(' ')[0] }), chip('afteroff'), chip('cheap22')] };
    }
    var c = ct && ct !== 'Coin' ? ct : 'Ring', miss = null;      // miss: asked for, not measured
    var rows = withMk.filter(function (b) { return b.mk[c] != null; }).sort(function (a, b) { return a.mk[c] - b.mk[c]; });
    if (!rows.length) { miss = c; c = 'Ring'; rows = withMk.filter(function (b) { return b.mk.Ring != null; }).sort(function (a, b) { return a.mk.Ring - b.mk.Ring; }); }
    return { intent: 'making', html: '<p>' + (miss ? t('mk_nocat', { c: esc(catName(miss)), r: esc(catName(c)) }) : t('mk_h', { c: esc(catName(c)) })) + '</p><div class="sn-list">' +
      rows.slice(0, 6).map(function (b, i) { return '<div class="sn-row"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm">' + esc(b.n) + '</span><span class="sn-v">' + pct(b.mk[c]) + '</span></div>'; }).join('') + '</div>' +
      '<p>' + link('/making-charges-comparison', t('mk_every')) + '</p>',
      say: rows.length ? t('say_mk', { c: catName(c), b: rows[0].n, p: pct(rows[0].mk[c]) }) : '',
      chips: chips(['afteroff', 'bestoff', 'whatmk']) };
  }
  function aOffers(bs) {
    if (bs.length) {
      var b = bs[0];
      if (!b.off || !b.off.length) return { intent: 'offers', html: '<p>' + t('off_none', { b: esc(b.n) }) + ' ' + link('/gold-offers-today', t('off_see')) + '</p>',
        say: t('say_off_none', { b: b.n }) };
      return { intent: 'offers', html: '<p>' + t('off_brand_h', { b: esc(b.n) }) + '</p>' + b.off.map(function (o) {
        return '<div class="sn-card"><b>' + esc(o.h) + '</b><q>' + esc(o.t) + '</q><p>' + o.m + '</p><a href="' + esc(o.u) + '" target="_blank" rel="nofollow noopener">' + t('off_page') + '</a></div>';
      }).join('') + '<p>' + link('/gold-offers-today', t('off_all')) + '</p>',
        say: t('say_off_brand', { b: b.n, n: b.off.length }), chips: chips(['afteroff', 'cheap22']) };
    }
    // Every jeweller with an offer today, A to Z, each with its own offers:
    // no jeweller is singled out. The ring price after offers is one line,
    // because only an offer on every design can be priced into it.
    var withOff = KB.brands.filter(function (b) { return b.off && b.off.length; })
      .sort(function (a, b) { return a.n.localeCompare(b.n); });
    var ring = (KB.ring || [])[0];
    var h = '<p>' + t('off_all_h', { n: withOff.length }) + '</p><div class="sn-list">' + withOff.map(function (b) {
      return '<div class="sn-row sn-orow"><span class="sn-nm"><b>' + esc(b.n) + '</b>' +
        b.off.slice(0, 3).map(function (o) { return '<small>' + esc(o.h) + '</small>'; }).join('') + '</span></div>';
    }).join('') + '</div>' +
      (ring ? '<p class="sn-dim">' + t('off_ring', { b: esc(ring.n), p: inr(ring.a) }) + '</p>' : '') +
      '<p>' + link('/gold-offers-today', t('off_every')) + '</p>';
    return { intent: 'offers', html: h, say: ring ? t('say_off_all', { n: withOff.length, b: ring.n, p: sInr(ring.a) }) : '',
      chips: chips(['goodmk', 'mkcmp', 'cheap22']) };
  }
  // "best offer on a ring": every jeweller with a measured making charge for
  // that piece, priced for 10 g of 22K (or the weight asked) after its flat
  // making-charge offer today; an "up to" offer (some designs only) is shown
  // as the best case beside it, never ranked on.
  var BO_CATS = ['Ring', 'Earrings', 'Bangle', 'Mangalsutra'];
  function aBestOffer(c, w) {
    w = w || { g: 10, n: '10', u: 'g' };
    var rows = KB.brands.filter(function (b) { return b.mk && b.mk[c] != null && rate(b, '22K'); }).map(function (b) {
      var gold = rate(b, '22K') * w.g, mk = b.mk[c], mo = b.mo || {}, f = mo.f || 0, u = mo.u || 0;
      var after = mk * (1 - f / 100);
      return { b: b, mk: mk, f: f, u: u, after: after, tot: (gold + gold * after / 100) * 1.03,
        best: u > f ? (gold + gold * mk * (1 - u / 100) / 100) * 1.03 : null };
    }).sort(function (a, b) { return a.tot - b.tot; });
    var others = BO_CATS.filter(function (x) { return x !== c; }).map(function (x) { return { l: catName(x), q: 'best offer ' + x.toLowerCase() }; });
    if (rows.length < 2) return { intent: 'best_offer', html: '<p>' + t('bo_none', { c: esc(catName(c)) }) + ' ' + link('/gold-offers-today', t('off_see')) + '</p>',
      say: t('bo_none', { c: catName(c) }), chips: others };
    var h = '<p>' + t('bo_h', { w: esc(wLabel(w)), c: esc(catName(c)) }) + '</p><div class="sn-list">' + rows.slice(0, 8).map(function (r, i) {
      var mk = pct(r.mk) + (r.f ? ' → ' + pct(r.after) + ' (−' + pct(r.f) + ')' : r.u ? '' : ' · ' + t('bo_noff'));
      var up = r.best != null ? '<small>(' + t('bo_upto') + ' −' + pct(r.u) + '* → ' + inr(r.best) + ')</small>' : '';
      return '<div class="sn-row sn-orow"><span class="sn-rk">' + (i + 1) + '</span><span class="sn-nm"><b>' + esc(r.b.n) + '</b><small>' + mk + '</small>' + up +
        '</span><span class="sn-v">' + inr(r.tot) + '</span></div>';
    }).join('') + '</div><p class="sn-dim">' + t('bo_note') + '</p><p>' + link('/making-charges-comparison', t('mk_every')) + ' · ' + link('/gold-offers-today', t('off_see')) + '</p>';
    return { intent: 'best_offer', html: h, say: t('say_bo', { w: wLabel(w), c: catName(c), b: rows[0].b.n, p: sInr(rows[0].tot) }), chips: others };
  }
  // Which piece? The next answer is priced (see wantOffer in answer()).
  function askOfferCat() {
    wantOffer = true;
    return { intent: 'ask_cat', html: '<p>' + t('bo_ask') + '</p>', say: t('bo_ask'),
      chips: BO_CATS.map(function (c) { return { l: catName(c), q: 'best offer ' + c.toLowerCase() }; }) };
  }
  function aPrice(w, k, bs, ct) {
    k = k || (ct === 'Coin' ? '24K' : '22K');
    var b = bs[0] || ranked(natBrands())[0], who = bs[0] ? esc(b.n) : t('price_who', { b: esc(b.n) });
    var gold = rate(b, k) * w.g;
    var mkp = b.mk ? (ct && b.mk[ct] != null ? b.mk[ct] : (b.mk.Ring != null ? b.mk.Ring : null)) : null;
    if (ct === 'Coin' || (k === '24K' && !ct)) mkp = null;   // 24K: coins and bars
    var mk = mkp != null ? gold * mkp / 100 : 0, gst = (gold + mk) * 0.03, tot = gold + mk + gst;
    var h = '<p>' + t('price_h', { w: esc(wLabel(w)), k: k, who: who }) + '</p><div class="sn-bill">' +
      '<div><span>' + t('price_gold', { g: Math.round(w.g * 1000) / 1000, p: inr(rate(b, k)) }) + '</span><b>' + inr(gold) + '</b></div>' +
      (mkp != null ? '<div><span>' + t('price_mk', { p: pct(mkp), c: ct && b.mk[ct] != null ? esc(catName(ct)) : t('price_typ') }) + '</span><b>' + inr(mk) + '</b></div>' : '') +
      '<div><span>GST 3%</span><b>' + inr(gst) + '</b></div><div class="sn-tot"><span>' + t('price_total') + '</span><b>' + inr(tot) + '</b></div></div>' +
      (mkp == null && ct !== 'Coin' && k !== '24K' ? '<p class="sn-dim">' + t('price_nomk') + '</p>' : '') + src();
    return { intent: 'price', html: h, say: t('say_price', { w: wLabel(w), k: sK(k), b: b.n, p: sInr(tot) }),
      chips: chips(['another', 'afteroff', 'cheap22']) };
  }
  function aTrend(k) {
    k = k || '22K';
    var h = KB.hist || [], f = K[k];
    if (h.length < 2) return { intent: 'trend', html: '<p>' + t('trend_none') + ' ' + link('/gold-rate-history', t('hist_link')) + '</p>', say: t('trend_none') };
    var last = h[h.length - 1][1] * f;
    function back(n) { var i = Math.max(0, h.length - 1 - n); return h[i][1] * f; }
    function chg(v) { var d = last - v, p = d / v * 100; return '<b class="' + (d >= 0 ? 'up' : 'dn') + '">' + (d >= 0 ? '▲ ' : '▼ ') + inr(Math.abs(d)) + ' (' + pct(Math.abs(p)) + ')</b>'; }
    var pts = h.slice(-30).map(function (x) { return x[1]; }), mn = Math.min.apply(null, pts), mx = Math.max.apply(null, pts);
    var sv = '<svg class="sn-spark" viewBox="0 0 240 48" preserveAspectRatio="none"><polyline fill="none" stroke="#e7bf5a" stroke-width="2" stroke-linejoin="round" points="' +
      pts.map(function (v, i) { return (i * 240 / Math.max(1, pts.length - 1)).toFixed(1) + ',' + (44 - (mx === mn ? 20 : (v - mn) / (mx - mn) * 40)).toFixed(1); }).join(' ') + '"/></svg>';
    var d1 = last - back(1);
    return { intent: 'trend', html: '<p>' + t('trend_h', { k: k, p: inr(last) }) + '</p>' + sv +
      '<div class="sn-list"><div class="sn-row"><span class="sn-nm">' + t('vs1') + '</span><span class="sn-v">' + chg(back(1)) + '</span></div>' +
      '<div class="sn-row"><span class="sn-nm">' + t('vs7') + '</span><span class="sn-v">' + chg(back(7)) + '</span></div>' +
      '<div class="sn-row"><span class="sn-nm">' + t('vs30') + '</span><span class="sn-v">' + chg(back(30)) + '</span></div></div>' +
      '<p class="sn-dim">' + t('trend_note') + ' ' + link('/gold-rate-history', t('full_hist')) + '</p>',
      say: t(Math.abs(d1) < 1 ? 'say_trend_same' : d1 > 0 ? 'say_trend_up' : 'say_trend_dn', { k: sK(k), p: sInr(last), q: sInr(Math.abs(d1)) }),
      chips: chips(['alert', 'cheap22', 'goodtime']) };
  }
  function aAlerts() {
    return { intent: 'alerts', html: '<p>' + t('alerts') + '</p><button class="sn-cta" data-sn="subscribe">' + t('alerts_cta') + '</button>', say: t('alerts') };
  }
  function words(s) { return s.split(/\s+/).filter(function (w) { return w.length > 2 && !/^(the|and|for|what|how|are|you|your|with|does|this|that|from|have|can|why|which|about|gold|is|of)$/.test(w); }); }
  function scoreDoc(s, q, keys) {
    var ws = words(s), qs = norm(q), n = 0;
    ws.forEach(function (w) { if (qs.indexOf(' ' + w) > -1) n += 1; if ((keys || []).indexOf(w) > -1) n += 1.5; });
    return n / Math.max(3, Math.sqrt(words(qs).length + 1) * 2);
  }
  // FAQ and approved answers are written in English: `en` carries the text
  // so it can be translated on the visitor's device, where the browser can.
  // One FAQ answer by its question (b: a jeweller to link as well).
  function faqQ(q, b) {
    var d = KB.faq.filter(function (f) { return f.q === q; })[0];
    if (!d) return null;
    return { intent: 'faq', score: 2, en: d.a, html: '<p>' + esc(d.a) + '</p>' + (d.u ? '<p>' + link(d.u, t('more')) + '</p>' : ''),
      say: d.a, chips: b ? [chip('boff', { b: b.n.split(' ')[0] }), chip('cheap22')] : chips(['cheap22', 'bestoff']) };
  }
  function aSearch(s) {
    var best = null, bs = 0;
    (KB.learned || []).forEach(function (d) { var v = scoreDoc(s, d.q, []) * 1.2; if (v > bs) { bs = v; best = d; } });
    KB.faq.forEach(function (d) { var v = scoreDoc(s, d.q, d.k); if (v > bs) { bs = v; best = d; } });
    if (best && bs >= 0.6) return { intent: 'faq', score: bs, en: best.a, html: '<p>' + esc(best.a) + '</p>' + (best.u ? '<p>' + link(best.u, t('more')) + '</p>' : ''),
      say: best.a, chips: chips(['cheap22', 'bestoff']) };
    var g = null, gs = 0;
    KB.guides.forEach(function (d) { var v = scoreDoc(s, d.t + ' ' + d.d, []); if (v > gs) { gs = v; g = d; } });
    if (g && gs >= 0.6) return { intent: 'guide', score: gs, en: g.t + '. ' + g.d,
      html: '<p>' + t('guide_h', { t: esc(g.t), d: esc(g.d) }) + '</p><p>' + link(g.u, t('guide_link')) + '</p>', say: g.t + '. ' + g.d };
    return null;
  }

  function answer(q) {
    var tx = norm(q), k = karatIn(tx), bs = brandsIn(tx), c = cityIn(tx), w = weightIn(tx), ct = catIn(tx);
    var mine = /\b(my city|near me|nearby|mere sheher|mere shahar|my area)\b/.test(tx);
    if (c && (wantHome || mine || /\b(i am in|i'm in|im in|i live in|i stay in)\b/.test(tx))) setHome(c);
    wantHome = false;
    var offerAsk = wantOffer; wantOffer = false;
    if (offerAsk && ct && ct !== 'Coin') return aBestOffer(ct, w);
    if (mine && !c) {
      c = home && KB.cities.filter(function (x) { return x.n === home; })[0];
      if (!c) return askCity('ask_city');
    }
    if (has(tx, W.silver) && !has(tx, ['gold', 'sona'])) return { intent: 'silver', html: '<p>' + t('silver') + '</p>', say: t('silver'), chips: chips(['rate', 'cheap22']) };
    if (has(tx, ['unsubscribe', 'opt out'])) return faqQ('How do I unsubscribe from the emails?');
    if (has(tx, ['alert', 'alerts', 'notify', 'subscribe', 'email me', 'whatsapp', 'set a price'])) return aAlerts();
    // "gold rate tomorrow", "will gold go up": nobody can say - the honest answer
    if (/\b(tomorrow|next (week|month|year)|forecast|predict|prediction)\b/.test(tx) ||
        /\bwill\b.*\b(go|rise|fall|increase|decrease|drop|come down|go up|go down)\b/.test(tx)) return faqQ('Is now a good time to buy gold?');
    // "is Tanishq gold pure", "is CaratLane trustworthy": the hallmark, not a ranking
    if (bs.length === 1 && has(tx, ['pure', 'purity', 'trust', 'trustworthy', 'genuine', 'reliable', 'safe', 'fake', 'quality', 'honest', 'real', 'original']) &&
        !has(tx, W.making) && !has(tx, W.offer)) return faqQ('Is this jeweller\'s gold pure and trustworthy?', bs[0]);
    // "1 gram gold jewellery" is imitation jewellery, not a weight
    if (/\b(1|one|ek) ?(gram|gm|g) gold (jewell?ery|jewelry|chain|bangles?|necklace|set|ornaments?)\b|\b(imitation|gold plated|gold covering)\b/.test(tx))
      return faqQ('What is 1 gram gold jewellery?');
    if (has(tx, ['free']) && has(tx, ['website', 'site', 'sona', 'app', 'service', 'this', 'it'])) return faqQ('Is this website free?');
    // "what is 916 / 22K gold", "what is carat": a meaning, not the day's rate
    var meaning = /\b(what is|whats|what does|meaning|means|mean|matlab|mhanje)\b/.test(tx) && !has(tx, W.rate) && !w && !bs.length && !c;
    if (meaning && k) return faqQ({ '22K': 'What is 916 gold?', '18K': 'Is 18K gold good for jewellery?', '14K': 'Is 14K gold real gold?' }[k] ||
                                  'What is the difference between 22K and 24K gold?');
    if (meaning && /\b(carat|karat|caret)\b/.test(tx)) return faqQ('What is the difference between carat and karat?');
    var store = storeIn(tx);
    if (store && !has(tx, ['digital', 'etf', 'loan', 'emi', 'scheme', 'bond', 'bonds', 'sgb'])) return aOutside(store, k);
    // "gold rate per gram 18 carat": that karat's rate, not its explainer
    if (k && /\b(rate|rates|price|bhav|dar|per gram|today|aaj)\b/.test(tx) && !meaning && !bs.length && !c && !w &&
        !has(tx, W.cheap) && !has(tx, W.making) && !has(tx, W.offer) && !has(tx, W.trend) && !has(tx, ['difference', 'vs', 'versus', 'better'])) return aMedian(k);
    // "are your rates accurate", "how do you get the rates"
    if (/\b(accurate|correct|reliable|authentic|source|sources|come from|how do you get|where do you get|how do you collect)\b/.test(tx) &&
        /\b(rates?|prices?|data|figures)\b/.test(tx) && !bs.length && !c) return faqQ('Where do these rates come from?');
    if (bs.length >= 2) return aCompare(bs, k);
    var across = has(tx, ['compare', 'comparison', 'compared', 'difference', 'differ', 'gap', 'vs', 'versus', 'across', 'other', 'all']);
    if (has(tx, W.making) && (has(tx, W.cheap) || across) && !w) return aMaking(bs, ct);    // "lowest making charge", "compare making charges": the ranking
    // "what is wastage / VA": the explanation; "making charges on bangles", "making kitna hai": the figures
    if (has(tx, W.making) && !w && !bs.length && !ct && /\b(what is|what are|whats|meaning|explain|define|matlab|mhanje)\b/.test(tx))
      return faqQ('What are making charges?');
    if (has(tx, W.making) && !w && (ct || /\b(how much|kitna|kitni|kitne|kiti)\b/.test(tx))) return aMaking(bs, ct);
    // "compare jewellers", "rate difference between jewellers": all of them, cheapest first
    if (across && /\b(jewell?ers|jewelers|shops|stores|brands|showrooms)\b/.test(tx) && !bs.length && !w &&
        !has(tx, W.offer) && !has(tx, W.making) && !/\b(why|kyon|kyun|kyu)\b/.test(tx)) return aCheapest(k, c, true);
    // "best offer", "best offer on bangles", "which jeweller is cheapest after offers on a ring": the calculator
    if (has(tx, W.offer) && !bs.length && !c && (ct ? ct !== 'Coin' : /\b(best|cheapest|lowest|calculate|which|kaunsa|konsa|kaunsi|sabse)\b/.test(tx)))
      return ct ? aBestOffer(ct, w) : askOfferCat();
    var strong = aSearch(tx);                // a question the FAQ answers word for word
    if (strong && strong.score >= 1.0 && !w && !bs.length && !c) return strong;
    if (has(tx, W.offer) || /\bafter offers?\b/.test(tx)) return aOffers(bs);
    if (has(tx, W.making) && !w) return aMaking(bs, ct);
    if (w) return aPrice(w, k, bs, ct);
    if (has(tx, W.trend) && !bs.length) return aTrend(k);
    var search = aSearch(tx);
    if (search && search.score > 0.9) return search;
    if (search && /\b(dubai|uae|abroad|singapore|overseas|foreign)\b/.test(tx)) return search;   // not "cheapest here"
    if (has(tx, W.cheap)) return aCheapest(k, c);
    if (bs.length) return aBrand(bs[0], k);
    if (c) return aCity(c, k);
    if (search) return search;
    if (has(tx, W.rate) || k) return aMedian(k);
    // "gold" alone, or "gold today": the rate. A real question about gold that
    // nothing above covers is better left unanswered (and learned) than
    // answered with the day's rate.
    if (/\b(gold|sona)\b/.test(tx) && (!/\b(what|how|why|when|can|could|is|are|should|do|does|which|kya|kaise|kyun|kay|kasa|kashi)\b/.test(tx) ||
        tx.split(/\s+/).length <= 3)) return aMedian(k);
    if (has(tx, W.hello)) return { intent: 'hello', html: '<p>' + t('hello', { n: KB.brands.length }) + '</p>', say: t('hello', { n: KB.brands.length }), chips: suggest() };
    if (has(tx, W.thanks)) return { intent: 'thanks', html: '<p>' + t('thanks') + '</p>', say: t('thanks'), chips: chips(['cheap22', 'bestoff']) };
    if (W.who.some(function (x) { return tx.indexOf(x) > -1; })) return { intent: 'about', html: '<p>' + t('about', { n: KB.brands.length }) + '</p>', say: t('about', { n: KB.brands.length }), chips: suggest() };
    return null;
  }
  // A question in any language: Indian scripts are first turned into the
  // words above (sona_lang.js); the reply comes in the asker's language.
  // chip: a suggestion tapped (asked in English, shown in the visitor's language).
  // "in Hindi", "marathi madhe sanga": a language asked for by name is kept
  // (as if picked from the menu); Hindi or Marathi typed in English letters
  // is answered in that language unless the visitor picked one.
  var justPicked = false;
  function understand(q, chip, spoken) {
    justPicked = false;
    var req = !chip && LG && LG.asked(q);
    if (req && STR[req.c]) {
      PICK = req.c; try { localStorage.setItem('sona_pick', PICK); } catch (_) {}
      LANG = uiLang(); RL = PICK; justPicked = true;
      if (panel) labels();
      track('lang_ask_' + PICK);
      q = req.rest;
      if (!q.trim()) return '';
    }
    // On Auto, each question's own words decide its language (Hindi and
    // Marathi told apart word by word), so the visitor can switch freely and
    // the mic follows; a language the visitor chose stays put.
    var d = LG && (LG.detect(q, PICK || HEARD, !!PICK) || (PICK ? null : LG.roman(q)));
    if (d && STR[d]) {
      RL = d;
      if (!PICK && d !== HEARD) {                 // she now listens and labels in it too
        HEARD = d; LANG = d; try { localStorage.setItem('sona_heard', d); } catch (_) {}
        if (panel) labels();
        RL = d;
      }
    } else RL = chip ? LANG : (PICK || 'en');
    if (LG && LG.isIndic(q)) return LG.understand(q, VOCAB, RL).text;
    return q;
  }
  // The answer to a question as typed; a bare "in Marathi" gets a hello in it.
  function reply(q, chip, spoken) {
    rawQ = q;
    var tx = understand(q, chip, spoken);
    if (!tx && justPicked) return { tx: tx, a: { intent: 'lang', html: '<p>' + t('greet1') + '</p><p>' + t('greet2') + '</p>',
      say: (t('greet1') + ' ' + t('greet2')).replace(/<[^>]+>/g, ''), chips: suggest() } };
    return { tx: tx, a: answer(tx) };
  }

  // ------------------------------------------------------------- avatar
  // Sona's face, drawn in SVG (no image to download): ivory-and-gold helmet,
  // black visor, glowing gold eyes, headphone ears, a bun with a gold band
  // and a forehead jewel. CSS brings her to life: she bobs, blinks and
  // smiles while idle, and talks (mouth moving, eyes glancing) while a reply
  // is being written - add the class "sona-talk" to any element holding her.
  var avN = 0;
  function avatar(full) {
    var p = 'sv' + (++avN) + '-';
    return '<svg class="sona-svg" viewBox="0 0 120 ' + (full ? 132 : 120) + '" aria-hidden="true" focusable="false"><defs>' +
      '<radialGradient id="' + p + 's" cx="38%" cy="28%" r="78%"><stop offset="0" stop-color="#fffaf0"/><stop offset=".55" stop-color="#f1e2c4"/><stop offset="1" stop-color="#c9a46c"/></radialGradient>' +
      '<linearGradient id="' + p + 'g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff0b8"/><stop offset=".45" stop-color="#e3b44f"/><stop offset="1" stop-color="#9c6b14"/></linearGradient>' +
      '<radialGradient id="' + p + 'v" cx="42%" cy="32%" r="80%"><stop offset="0" stop-color="#33271a"/><stop offset="1" stop-color="#0a0705"/></radialGradient>' +
      '<radialGradient id="' + p + 'e" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#fff8d6"/><stop offset=".55" stop-color="#ffd25e"/><stop offset="1" stop-color="#e3971a"/></radialGradient>' +
      '<filter id="' + p + 'f" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>' +
      '<g class="sv-bob">' +
      (full ? '<rect x="52" y="96" width="16" height="12" rx="4" fill="url(#' + p + 'g)"/><path d="M30 132 C34 112 48 104 60 104 C72 104 86 112 90 132Z" fill="url(#' + p + 's)"/><path d="M44 107 Q60 116 76 107" stroke="url(#' + p + 'g)" stroke-width="2.4" fill="none"/>' +
        '<circle cx="60" cy="121" r="6.5" fill="url(#' + p + 'g)"/><text x="60" y="124.6" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="9" fill="#5a3d08">S</text>' : '') +
      '<ellipse cx="60" cy="15" rx="13" ry="10" fill="url(#' + p + 's)"/><rect x="46" y="19" width="28" height="5.5" rx="2.7" fill="url(#' + p + 'g)"/>' +
      '<g class="sv-ear"><circle cx="17" cy="61" r="11" fill="url(#' + p + 'g)"/><circle cx="17" cy="61" r="6.6" fill="#2a1d0c"/><circle class="sv-glow" cx="17" cy="61" r="3.8" fill="#ffd25e"/></g>' +
      '<g class="sv-ear"><circle cx="103" cy="61" r="11" fill="url(#' + p + 'g)"/><circle cx="103" cy="61" r="6.6" fill="#2a1d0c"/><circle class="sv-glow" cx="103" cy="61" r="3.8" fill="#ffd25e"/></g>' +
      '<circle cx="60" cy="60" r="42" fill="url(#' + p + 's)"/>' +
      '<ellipse cx="60" cy="64" rx="33.5" ry="27.5" fill="none" stroke="url(#' + p + 'g)" stroke-width="2.6"/>' +
      '<ellipse cx="60" cy="64" rx="31" ry="25" fill="url(#' + p + 'v)"/>' +
      '<path d="M37 55 Q43 42 58 40" stroke="rgba(255,255,255,.16)" stroke-width="3.2" fill="none" stroke-linecap="round"/>' +
      '<path d="M60 25 L65.5 31.5 L60 38 L54.5 31.5Z" fill="url(#' + p + 'g)"/><circle cx="60" cy="31.5" r="1.8" fill="#fff6d0"/>' +
      '<g class="sv-eyes"><g filter="url(#' + p + 'f)"><ellipse class="sv-eye" cx="48" cy="62" rx="5.4" ry="6.6" fill="url(#' + p + 'e)"/><ellipse class="sv-eye" cx="72" cy="62" rx="5.4" ry="6.6" fill="url(#' + p + 'e)"/></g>' +
      '<circle class="sv-eye" cx="50" cy="59.6" r="1.6" fill="#fff"/><circle class="sv-eye" cx="74" cy="59.6" r="1.6" fill="#fff"/></g>' +
      '<ellipse cx="39.5" cy="73" rx="4.6" ry="2.6" fill="#ff8f7d" opacity=".42"/><ellipse cx="80.5" cy="73" rx="4.6" ry="2.6" fill="#ff8f7d" opacity=".42"/>' +
      '<path class="sv-smile" d="M51 74 Q60 82.5 69 74" stroke="#ffd25e" stroke-width="2.7" fill="none" stroke-linecap="round" filter="url(#' + p + 'f)"/>' +
      '<ellipse class="sv-talk" cx="60" cy="76.5" rx="5" ry="3.6" fill="#ffd25e" filter="url(#' + p + 'f)"/>' +
      '</g></svg>';
  }
  window.GR_SONA_AVATAR = avatar;

  // --------------------------------------------------------------- UI
  var SUGGEST = ['cheap22', 'mycity', 'tvk', 'bestoff', 'p10chain', 'k22v24'];      // chip keys (sona_i18n.js ch_*)
  var CSS = '' +
    '.sn-fab{position:fixed;right:16px;bottom:calc(18px + env(safe-area-inset-bottom));z-index:8500;display:flex;align-items:center;gap:9px;height:52px;padding:0 18px 0 7px;border:0;border-radius:999px;cursor:pointer;color:#1a1405;font:700 14.5px/1 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:linear-gradient(135deg,#ffe9a8,#e7bf5a 45%,#b98a24);box-shadow:0 10px 30px rgba(185,138,36,.45),0 0 0 1px rgba(255,255,255,.25) inset;transition:transform .2s}' +
    '.sn-fab:hover{transform:translateY(-2px)}.sn-fab .sn-orb{width:42px;height:42px;flex:none;margin:-2px 0;filter:drop-shadow(0 2px 4px rgba(90,60,0,.35))}' +
    '.sn-fab .sn-ping{position:absolute;top:-3px;right:-3px;width:12px;height:12px;border-radius:50%;background:#2fd18b;box-shadow:0 0 0 0 rgba(47,209,139,.7);animation:snPing 2s infinite}' +
    '@keyframes snPing{0%{box-shadow:0 0 0 0 rgba(47,209,139,.7)}70%{box-shadow:0 0 0 10px rgba(47,209,139,0)}100%{box-shadow:0 0 0 0 rgba(47,209,139,0)}}' +
    'html.sona-bnav .sn-fab{bottom:calc(78px + env(safe-area-inset-bottom))}' +
    '.sona-svg{display:block;width:100%;height:100%;overflow:visible}' +
    '.sona-svg .sv-bob{animation:svBob 3.4s ease-in-out infinite}' +
    '@keyframes svBob{0%,100%{transform:translateY(0)}50%{transform:translateY(-2.5px)}}' +
    '.sona-svg .sv-eyes{transform-box:fill-box;transform-origin:center;animation:svHappy 9s ease-in-out infinite}' +
    '@keyframes svHappy{0%,58%,74%,100%{transform:scaleY(1)}62%,70%{transform:translateY(-1px) scaleY(.5)}}' +
    '.sona-svg .sv-eye{transform-box:fill-box;transform-origin:center;animation:svBlink 4.7s infinite}' +
    '@keyframes svBlink{0%,90%,100%{transform:scaleY(1)}93%{transform:scaleY(.08)}96%{transform:scaleY(1)}}' +
    '.sona-svg .sv-glow{animation:svGlow 2.6s ease-in-out infinite}@keyframes svGlow{50%{opacity:.35}}' +
    '.sona-svg .sv-smile{transition:opacity .15s}.sona-svg .sv-talk{opacity:0;transform-box:fill-box;transform-origin:center}' +
    '.sona-talk .sona-svg .sv-smile{opacity:0}.sona-talk .sona-svg .sv-talk{opacity:1;animation:svTalk .24s ease-in-out infinite alternate}' +
    '@keyframes svTalk{from{transform:scaleY(.25) scaleX(.9)}to{transform:scaleY(1.15) scaleX(1)}}' +
    '.sona-talk .sona-svg .sv-eyes{animation:svLook 1.6s ease-in-out infinite}' +
    '@keyframes svLook{0%,100%{transform:translateX(0)}30%{transform:translateX(-2.4px)}70%{transform:translateX(2.4px)}}' +
    '@media(prefers-reduced-motion:reduce){.sona-svg *{animation:none!important}}' +
    '.sn-m.bot{gap:8px;align-items:flex-end}.sn-mav{width:30px;height:30px;flex:none;margin-bottom:2px;filter:drop-shadow(0 3px 6px rgba(0,0,0,.4))}' +
    '.sn-ban .sn-banav{width:26px;height:26px;flex:none}' +
    'html.sona-open .sn-fab{display:none}@media(max-width:560px){html.sona-open,html.sona-open body{overflow:hidden}}' +
    '.sn-ad{position:relative;overflow:hidden;border-radius:18px;padding:18px;margin:14px 12px;color:#f3eadb;background:radial-gradient(120% 90% at 100% 0%,rgba(231,191,90,.28),transparent 60%),linear-gradient(160deg,#1c160c,#0f0c08);border:1px solid rgba(240,208,128,.3);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}' +
    '.sn-ad .sn-adk{display:inline-flex;align-items:center;gap:6px;font-size:10.5px;font-weight:800;letter-spacing:.12em;color:#1a1405;background:linear-gradient(135deg,#f6d77d,#d4a63c);border-radius:999px;padding:3px 9px}' +
    '.sn-ad h3{font:800 21px/1.25 Georgia,serif;margin:10px 0 4px;padding-right:84px;color:#fff3d6}.sn-ad p{margin:0 0 12px;font-size:13.5px;color:#cfc4ad;line-height:1.5}' +
    '.sn-ad .sn-adq{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:12px}.sn-ad .sn-adq button{border:1px solid rgba(240,208,128,.35);background:rgba(231,191,90,.1);color:#f0d080;border-radius:999px;padding:7px 12px;font-size:12.5px;font-weight:600;cursor:pointer}' +
    '.sn-ad .sn-adgo{border:0;border-radius:12px;padding:12px 18px;font-weight:800;font-size:14px;cursor:pointer;color:#1a1405;background:linear-gradient(135deg,#f6d77d,#d4a63c 55%,#b98a24);box-shadow:0 8px 22px rgba(212,166,60,.3)}' +
    '.sn-ad .sn-adav{position:absolute;right:10px;top:6px;width:84px;height:92px;font-size:0;color:transparent;filter:drop-shadow(0 8px 18px rgba(0,0,0,.45))}' +
    '@media(max-width:520px){.sn-fab{height:50px;padding:0 6px}.sn-fab .sn-lbl{display:none}}' +
    '.sn-panel{position:fixed;right:18px;bottom:18px;z-index:9500;width:410px;height:min(680px,calc(100vh - 36px));display:none;flex-direction:column;border-radius:24px;overflow:hidden;color:#f3eadb;font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:radial-gradient(130% 60% at 100% 0%,rgba(231,191,90,.16),transparent 60%),#120f0a;border:1px solid rgba(240,208,128,.22);box-shadow:0 30px 80px rgba(0,0,0,.6)}' +
    'html.sona-open .sn-panel{display:flex;animation:snIn .28s cubic-bezier(.2,.8,.3,1)}@keyframes snIn{from{opacity:0;transform:translateY(18px) scale(.98)}to{opacity:1;transform:none}}' +
    '@media(max-width:560px){.sn-panel{right:0;bottom:0;width:100%;height:100%;height:100dvh;border-radius:0;border:0}}' +
    '.sn-hd{display:flex;align-items:center;gap:11px;padding:14px 14px 12px 16px;border-bottom:1px solid rgba(240,208,128,.12)}' +
    '.sn-av{position:relative;width:48px;height:48px;flex:none;filter:drop-shadow(0 4px 10px rgba(0,0,0,.45))}' +
    '.sn-av:after{content:"";position:absolute;right:1px;bottom:3px;width:10px;height:10px;border-radius:50%;background:#2fd18b;border:2px solid #120f0a}' +
    '.sn-hd b{display:block;font-size:15.5px}.sn-hd span{font-size:11.5px;color:#a99f8b}.sn-x{margin-left:auto;width:34px;height:34px;border-radius:50%;border:0;background:rgba(255,255,255,.07);color:#f3eadb;font-size:18px;cursor:pointer}' +
    '.sn-body{flex:1;overflow-y:auto;padding:16px 14px 8px;scroll-behavior:smooth}' +
    '.sn-m{display:flex;margin:0 0 12px}.sn-m.me{justify-content:flex-end}' +
    '.sn-b[dir=rtl] .sn-v,.sn-b[dir=rtl] .sn-cmp b,.sn-b[dir=rtl] .sn-tiles span{direction:ltr;unicode-bidi:isolate}' +
    '.sn-b{max-width:88%;padding:10px 13px;border-radius:18px 18px 18px 6px;background:rgba(255,255,255,.06);border:1px solid rgba(240,208,128,.1)}' +
    '.sn-m.me .sn-b{border-radius:18px 18px 6px 18px;background:linear-gradient(135deg,#f6d77d,#d4a63c);color:#1a1405;border:0;font-weight:600}' +
    '.sn-b p{margin:0 0 8px}.sn-b p:last-child{margin-bottom:0}.sn-b a{color:#f0d080;font-weight:600;text-decoration:none}.sn-b em{font-style:normal;font-size:10.5px;color:#a99f8b;border:1px solid rgba(240,208,128,.25);border-radius:6px;padding:0 5px}' +
    '.sn-tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:4px 0 10px}.sn-tiles div{background:rgba(0,0,0,.25);border:1px solid rgba(240,208,128,.12);border-radius:12px;padding:8px 6px;text-align:center}' +
    '.sn-tiles div.on{border-color:#e7bf5a;background:rgba(231,191,90,.12)}.sn-tiles b{display:block;font-size:14.5px}.sn-tiles span{font-size:10.5px;color:#a99f8b}' +
    '.sn-list{background:rgba(0,0,0,.22);border:1px solid rgba(240,208,128,.1);border-radius:12px;margin:4px 0 10px;overflow:hidden}' +
    '.sn-row{display:flex;align-items:center;gap:8px;padding:7px 10px;border-bottom:1px solid rgba(240,208,128,.07);font-size:13px}.sn-row:last-child{border-bottom:0}' +
    '.sn-rk{width:20px;height:20px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;background:rgba(231,191,90,.15);color:#f0d080}.sn-row:first-child .sn-rk{background:#e7bf5a;color:#1a1405}' +
    '.sn-nm{flex:1;min-width:0}.sn-v{font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}.sn-v small{font-weight:400;color:#a99f8b}' +
    '.sn-v .up{color:#5ad59a}.sn-v .dn{color:#f08f8f}.sn-dim{color:#a99f8b;font-size:12.5px}.sn-src{font-size:10.5px;color:#7f7663;margin-top:6px}' +
    '.sn-cmp{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:6px;margin:4px 0 10px}.sn-cmp>div{background:rgba(0,0,0,.25);border:1px solid rgba(240,208,128,.12);border-radius:12px;padding:9px}' +
    '.sn-cmp .sn-cn{font-size:12px;color:#a99f8b;margin-bottom:2px}.sn-cmp b{display:block;font-size:16px}.sn-cmp span{display:block;font-size:11.5px;color:#cfc4ad;margin-top:2px}.sn-cmp .sn-off{color:#5ad59a}' +
    '.sn-bill{background:rgba(0,0,0,.22);border:1px solid rgba(240,208,128,.12);border-radius:12px;padding:6px 10px;margin:4px 0 10px}.sn-bill div{display:flex;justify-content:space-between;gap:10px;padding:5px 0;font-size:13px}.sn-bill span{color:#cfc4ad}.sn-bill .sn-tot{border-top:1px dashed rgba(240,208,128,.3);margin-top:3px;padding-top:8px;font-size:15px}.sn-bill .sn-tot b{color:#f0d080}' +
    '.sn-card{background:rgba(0,0,0,.22);border:1px solid rgba(240,208,128,.12);border-radius:12px;padding:9px 10px;margin:0 0 8px}.sn-card q{display:block;font-style:italic;color:#cfc4ad;font-size:12.5px;margin:3px 0}.sn-card p{font-size:12.5px;color:#d9cfba}' +
    '.sn-spark{width:100%;height:48px;margin:2px 0 8px}' +
    '.sn-cta{width:100%;border:0;border-radius:12px;padding:11px;cursor:pointer;font-weight:800;color:#1a1405;background:linear-gradient(135deg,#f6d77d,#d4a63c 55%,#b98a24)}' +
    '.sn-fb{display:flex;gap:6px;margin-top:6px}.sn-fb button{border:1px solid rgba(240,208,128,.2);background:none;color:#a99f8b;border-radius:999px;padding:2px 9px;font-size:12px;cursor:pointer}.sn-fb button.on{background:rgba(231,191,90,.2);color:#f0d080}' +
    '.sn-chips{display:flex;gap:7px;overflow-x:auto;padding:4px 14px 10px;scrollbar-width:none}.sn-chips::-webkit-scrollbar{display:none}' +
    '.sn-chip{flex:none;border:1px solid rgba(240,208,128,.3);background:rgba(231,191,90,.08);color:#f0d080;border-radius:999px;padding:7px 12px;font-size:12.5px;font-weight:600;cursor:pointer;white-space:nowrap}.sn-chip:hover{background:rgba(231,191,90,.18)}' +
    '.sn-in{display:flex;gap:8px;padding:10px 12px calc(12px + env(safe-area-inset-bottom));border-top:1px solid rgba(240,208,128,.12)}' +
    '.sn-in input{flex:1;min-width:0;border:1px solid rgba(240,208,128,.22);background:rgba(255,255,255,.05);color:#f3eadb;border-radius:999px;padding:12px 16px;font-size:15px;outline:none}.sn-in input:focus{border-color:#e7bf5a}' +
    '.sn-send{width:46px;height:46px;flex:none;border:0;border-radius:50%;cursor:pointer;color:#1a1405;font-size:18px;background:linear-gradient(135deg,#f6d77d,#d4a63c)}' +
    '.sn-typing span{display:inline-block;width:7px;height:7px;margin:0 2px;border-radius:50%;background:#e7bf5a;animation:snDot 1s infinite}.sn-typing span:nth-child(2){animation-delay:.15s}.sn-typing span:nth-child(3){animation-delay:.3s}' +
    '@keyframes snDot{0%,80%,100%{opacity:.25;transform:translateY(0)}40%{opacity:1;transform:translateY(-3px)}}' +
    '.sn-foot{text-align:center;font-size:10px;color:#6f6754;padding:0 0 8px}' +
    '.sn-ban{position:relative;z-index:50;display:flex;align-items:center;justify-content:center;gap:10px;padding:9px 40px 9px 14px;font:600 13px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#1a1405;background:linear-gradient(90deg,#b98a24,#f6d77d 50%,#b98a24);background-size:200% 100%;animation:snShine 6s linear infinite;cursor:pointer;text-align:center}' +
    '@keyframes snShine{to{background-position:-200% 0}}.sn-ban .nw{flex:none;background:#1a1405;color:#f0d080;border-radius:999px;padding:2px 8px;font-size:10.5px;letter-spacing:.08em}.sn-ban u{text-underline-offset:2px}' +
    '.sn-hd .sn-ttl{flex:1;min-width:0}.sn-hd .sn-ttl span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sn-hd .sn-x{margin-left:0;flex:none}' +
    '.sn-lp{height:32px;flex:none;border-radius:999px;border:1px solid rgba(240,208,128,.35);background:rgba(231,191,90,.1);color:#f0d080;font:700 12.5px/1 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:0 11px;cursor:pointer;white-space:nowrap}' +
    '.sn-hb{width:34px;height:34px;flex:none;border-radius:50%;border:0;background:rgba(255,255,255,.07);color:#cfc4ad;cursor:pointer;display:flex;align-items:center;justify-content:center}.sn-hb svg{width:17px;height:17px}.sn-hb.on{background:rgba(231,191,90,.22);color:#f6d77d}' +
    '.sn-lm{display:none;position:absolute;left:12px;right:12px;top:72px;z-index:3;grid-template-columns:repeat(2,1fr);gap:6px;padding:10px;border-radius:16px;background:#1b160e;border:1px solid rgba(240,208,128,.25);box-shadow:0 18px 40px rgba(0,0,0,.55)}.sn-lm.on{display:grid}' +
    '.sn-lm button{border:1px solid rgba(240,208,128,.16);background:rgba(255,255,255,.04);color:#f3eadb;border-radius:10px;padding:10px 12px;text-align:left;font-size:14.5px;cursor:pointer}.sn-lm button.on{border-color:#e7bf5a;background:rgba(231,191,90,.15);color:#f6d77d}.sn-lm .sn-auto{grid-column:1/-1;font-weight:700}' +
    '.sn-lchips{display:flex;flex-wrap:wrap;gap:6px;margin:2px 0 4px}.sn-lchips button{border:1px solid rgba(240,208,128,.25);background:none;color:#f0d080;border-radius:999px;padding:4px 10px;font-size:12.5px;cursor:pointer}.sn-lchips button:hover{background:rgba(231,191,90,.12)}' +
    '.sn-mic{position:relative;width:46px;height:46px;flex:none;border-radius:50%;border:1px solid rgba(240,208,128,.4);background:rgba(231,191,90,.1);color:#f0d080;cursor:pointer;display:flex;align-items:center;justify-content:center}.sn-mic svg{width:21px;height:21px}' +
    '.sn-ml{position:absolute;right:-5px;bottom:-5px;min-width:17px;height:17px;padding:0 4px;border-radius:9px;background:#e7bf5a;color:#1a1405;font:700 10px/17px system-ui,sans-serif;text-align:center;pointer-events:none}' +
    '.sn-g{display:inline-block;padding:7px 14px;border-radius:999px;border:1px solid rgba(240,208,128,.45);color:#f0d080;text-decoration:none;font-weight:600}' +
    '.sn-mic.on{background:#e5484d;border-color:#e5484d;color:#fff;animation:snMic 1.2s infinite}@keyframes snMic{0%{box-shadow:0 0 0 0 rgba(229,72,77,.6)}70%{box-shadow:0 0 0 12px rgba(229,72,77,0)}100%{box-shadow:0 0 0 0 rgba(229,72,77,0)}}' +
    '.sn-orow .sn-nm b{display:block;font-size:13.5px}.sn-orow small{display:block;color:#cfc4ad;font-size:12px;line-height:1.45;margin-top:2px}' +
    '.sn-fb .sn-say{margin-left:auto}.sn-fab .sn-fmic{width:26px;height:26px;margin:0 -6px 0 -2px;border-radius:50%;background:rgba(26,20,5,.12);display:flex;align-items:center;justify-content:center}.sn-fab .sn-fmic svg{width:15px;height:15px}' +
    '@media(max-width:520px){.sn-fab .sn-fmic{display:none}}' +
    '.sn-ban .bx{position:absolute;right:8px;top:50%;transform:translateY(-50%);width:26px;height:26px;border:0;border-radius:50%;background:rgba(26,20,5,.12);color:#1a1405;cursor:pointer;font-size:14px}';

  var panel, body, chipBox, input, mic, spk, lmenu, voiceQ = false;
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition, rec = null, listening = false;
  var TTS = window.speechSynthesis, ttsOn = false;      // read every reply aloud; a spoken question is always answered aloud
  try { ttsOn = localStorage.getItem('sona_tts') === '1'; } catch (_) {}
  var ICON = {
    mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
    on: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg>',
    off: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>'
  };
  function short(c) { var l = (LG ? LG.LANGS : []).filter(function (x) { return x.c === c; })[0]; return l ? l.s : 'EN'; }
  function ui() {
    if (panel) return;
    panel = document.createElement('div'); panel.className = 'sn-panel'; panel.id = 'sonaPanel';
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Sona, the jewellery assistant');
    panel.innerHTML = '<div class="sn-hd"><div class="sn-av" id="sonaHeadAv">' + avatar() + '</div><div class="sn-ttl"><b>Sona</b><span id="sonaSub"></span></div>' +
      (LG ? '<button class="sn-lp" id="sonaLang" type="button" aria-haspopup="true"></button>' : '') +
      (TTS ? '<button class="sn-hb" id="sonaSpk" type="button"></button>' : '') +
      '<button class="sn-x" id="sonaClose" aria-label="Close">×</button></div>' +
      (LG ? '<div class="sn-lm" id="sonaLm" role="menu"><button type="button" role="menuitem" data-lang="auto" class="sn-auto"></button>' + LG.LANGS.map(function (l) { return '<button type="button" role="menuitem" data-lang="' + l.c + '">' + l.n + '</button>'; }).join('') + '</div>' : '') +
      '<div class="sn-body" aria-live="polite"></div><div class="sn-chips"></div>' +
      '<form class="sn-in"><input id="sonaInput" type="text" autocomplete="off" maxlength="200" aria-label="Your question">' +
      (SR ? '<button class="sn-mic" id="sonaMic" type="button">' + ICON.mic + '<span class="sn-ml" id="sonaMl"></span></button>' : '') +
      '<button class="sn-send" id="sonaSend" aria-label="Send">➤</button></form>' +
      '<div class="sn-foot" id="sonaFoot"></div>';
    document.body.appendChild(panel);
    body = $('.sn-body', panel); chipBox = $('.sn-chips', panel); input = $('#sonaInput', panel);
    mic = $('#sonaMic', panel); spk = $('#sonaSpk', panel); lmenu = $('#sonaLm', panel);
    $('#sonaClose', panel).onclick = close;
    $('form', panel).onsubmit = function (e) { e.preventDefault(); ask(input.value); };
    if (mic) mic.onclick = listen;
    if (spk) spk.onclick = function () {
      ttsOn = !ttsOn; try { localStorage.setItem('sona_tts', ttsOn ? '1' : '0'); } catch (_) {}
      if (!ttsOn) hush();
      labels(); track(ttsOn ? 'tts_on' : 'tts_off');
    };
    if (LG) $('#sonaLang', panel).onclick = function (e) { e.stopPropagation(); lmenu.classList.toggle('on'); };
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && opened) close(); });
    panel.addEventListener('click', function (e) {
      var lb = e.target.closest('[data-lang]');
      if (lb) { setLang(lb.getAttribute('data-lang')); return; }
      if (lmenu && !e.target.closest('#sonaLang')) lmenu.classList.remove('on');
      var c = e.target.closest('.sn-chip');
      if (c) {
        var cq = c.getAttribute('data-q') || c.textContent;
        if (cq === '#loc') locate();
        else if (cq === '#city') { home = null; try { localStorage.removeItem('sona_home'); } catch (_) {} ask(en('ch_mycity'), c.textContent); }
        else ask(cq, c.textContent);
        return;
      }
      var s = e.target.closest('[data-sn="subscribe"]');
      if (s) { close(); if (window.GR_OPEN_SUBPOP) window.GR_OPEN_SUBPOP(); else location.href = '/inquiry'; track('subscribe'); return; }
      var sy = e.target.closest('.sn-say');
      if (sy) { var m = sy.closest('.sn-m'); speak(m._say, m._sl, m); track('replay'); return; }
      var f = e.target.closest('.sn-fb button');
      if (f && !f.parentNode.getAttribute('data-done')) {
        f.classList.add('on'); f.parentNode.setAttribute('data-done', '1');
        var id = f.parentNode.getAttribute('data-id');
        if (id) rpc('bot_feedback', { p_id: +id, p_sid: window.GR_SID || '', p_helpful: f.getAttribute('data-v') === '1' });
      }
    });
    labels();
  }
  // Every fixed label in the chosen language.
  function labels() {
    RL = LANG;
    $('#sonaSub', panel).textContent = t('ui_sub');
    $('#sonaFoot', panel).textContent = t('ui_foot');
    if (!listening) input.placeholder = t('ui_ph');
    input.dir = rtl(LANG) ? 'rtl' : 'auto';
    // the language the mic listens in, on the mic (change it with the language menu)
    if (mic) { mic.setAttribute('aria-label', t('ui_mic') + ' (' + langName(micLang()) + ')'); mic.title = t('ui_mic') + ' - ' + langName(micLang());
      var ml = $('#sonaMl', panel); if (ml) ml.textContent = short(micLang()); }
    if (spk) { spk.innerHTML = ttsOn ? ICON.on : ICON.off; spk.classList.toggle('on', ttsOn); spk.setAttribute('aria-pressed', ttsOn ? 'true' : 'false'); spk.setAttribute('aria-label', t('ui_speak')); spk.title = ttsOn ? t('ui_mute') : t('ui_speak'); }
    if (LG) {
      var lp = $('#sonaLang', panel); lp.textContent = (PICK ? short(PICK) : 'Auto') + ' ▾';
      lp.setAttribute('aria-label', t('ui_lang') + ': ' + (PICK ? langName(PICK) : t('ui_auto')));
      $('.sn-auto', lmenu).textContent = t('ui_auto');
      [].forEach.call(lmenu.querySelectorAll('button'), function (b) { b.classList.toggle('on', b.getAttribute('data-lang') === (PICK || 'auto')); });
    }
  }
  function setLang(c) {
    if (c === 'auto') {
      PICK = ''; HEARD = '';
      try { localStorage.removeItem('sona_pick'); localStorage.removeItem('sona_heard'); } catch (_) {}
    } else if (STR[c]) {
      PICK = c; try { localStorage.setItem('sona_pick', c); } catch (_) {}
    } else return;
    LANG = uiLang();
    if (lmenu) lmenu.classList.remove('on');
    hush(); labels(); track('lang_' + c);
    // Only the welcome so far: say it again in the new language.
    var ms = body.querySelectorAll('.sn-m');
    if (ms.length === 1 && ms[0].getAttribute('data-greet')) { ms[0].remove(); greet(); }
    else setChips(suggest());
  }
  function greet() {
    RL = LANG;
    var m = bubble('<p>' + t('greet1') + '</p><p>' + t('greet2') + '</p>' + (LG ? '<p class="sn-dim">' + t('lang_hint') + '</p><div class="sn-lchips">' +
      LG.LANGS.map(function (l) { return '<button type="button" data-lang="' + l.c + '">' + l.n + '</button>'; }).join('') + '</div>' : ''));
    m.setAttribute('data-greet', '1');
    setChips(suggest());
  }
  function setChips(list) {
    chipBox.innerHTML = (list || []).map(function (c) {
      c = typeof c === 'string' ? { l: c, q: c } : c;
      return '<button class="sn-chip" type="button" dir="auto" data-q="' + esc(c.q) + '">' + esc(c.l) + '</button>';
    }).join('');
  }
  function bubble(html, me, talking) {
    var m = document.createElement('div'); m.className = 'sn-m' + (me ? ' me' : ' bot') + (talking ? ' sona-talk' : '');
    m.innerHTML = (me ? '' : '<div class="sn-mav">' + avatar() + '</div>') + '<div class="sn-b" dir="' + (me ? 'auto' : rtl(RL) ? 'rtl' : 'ltr') + '">' + html + '</div>';
    body.appendChild(m);
    body.scrollTop = body.scrollHeight; return m;
  }
  function note(text) { bubble('<p class="sn-dim">' + esc(text) + '</p>'); }
  // While Sona writes or reads out a reply she talks: in her message and in the header.
  function talking(on) { var h = panel && $('#sonaHeadAv', panel); if (h) h.classList.toggle('sona-talk', on); }

  // ------------------------------------------------- voice (the browser's own)
  function bcp(c) { var l = (LG ? LG.LANGS : []).filter(function (x) { return x.c === c; })[0]; return l ? l.bcp : 'en-IN'; }
  function voiceFor(c) {
    var vs = (TTS && TTS.getVoices()) || [], want = bcp(c).toLowerCase();
    var lg = function (v) { return String(v.lang || '').replace('_', '-').toLowerCase(); };
    return vs.filter(function (v) { return lg(v) === want; })[0] ||
      vs.filter(function (v) { return lg(v) === c || lg(v).indexOf(c + '-') === 0; })[0] || null;
  }
  var toldNoVoice = {};
  function speak(text, lang, m) {
    if (!TTS || !text) return;
    lang = lang || 'en';
    var go = function () {
      var v = voiceFor(lang);
      if (!v && lang !== 'en') {
        if (!toldNoVoice[lang]) { toldNoVoice[lang] = 1; RL = lang; note(t('no_voice', { l: langName(lang) })); }
        return;
      }
      try { TTS.cancel(); } catch (_) {}
      var u = new SpeechSynthesisUtterance(String(text).replace(/₹/g, ''));
      if (v) u.voice = v;
      u.lang = v ? v.lang : bcp(lang); u.rate = 1; u.pitch = 1.05;
      u.onstart = function () { talking(true); if (m) m.classList.add('sona-talk'); };
      u.onend = u.onerror = function () { talking(false); if (m) m.classList.remove('sona-talk'); };
      TTS.speak(u);
    };
    if ((TTS.getVoices() || []).length) go();
    else {                                     // voices load late on some browsers
      var done = false, once = function () { if (!done) { done = true; go(); } };
      try { TTS.addEventListener('voiceschanged', once); } catch (_) {}
      setTimeout(once, 1200);
    }
  }
  function hush() { if (TTS) try { TTS.cancel(); } catch (_) {} talking(false); }
  function setListening(on) {
    listening = on;
    if (mic) mic.classList.toggle('on', on);
    RL = LANG; input.placeholder = on ? t('ui_listen') : t('ui_ph');
  }
  // The language the mic is listening for (for the fallback below).
  var micUsed = '';
  function listen(fallback) {
    if (!SR) return;
    if (listening && !fallback) { try { rec.stop(); } catch (_) {} var r0 = rec; setTimeout(function () { if (rec === r0 && listening) { try { r0.abort(); } catch (_) {} if (r0.onend) r0.onend(); } }, 1200); return; }
    hush();
    micUsed = micLang();
    rec = new SR(); rec.lang = fallback || bcp(micUsed); rec.interimResults = true; rec.maxAlternatives = 1; rec.continuous = false;
    var heard = '', done = false, quiet = null, cap = null, me = rec;
    // iPhone Safari does not stop by itself when the visitor stops talking
    // (Android does): stop after a short silence, or if nothing is said, or
    // after a hard limit - and finish even if Safari never sends "end".
    function finish() {
      if (done) return; done = true;
      clearTimeout(quiet); clearTimeout(cap);
      if (rec === me) setListening(false);
      if (heard.trim()) { voiceQ = true; ask(heard); }
    }
    function stop(ms) {
      clearTimeout(quiet);
      quiet = setTimeout(function () {
        try { me.stop(); } catch (_) {}
        setTimeout(function () { try { me.abort(); } catch (_) {} finish(); }, 1200);
      }, ms);
    }
    rec.onresult = function (e) {
      var now = '', fin = false;
      for (var i = 0; i < e.results.length; i++) { now += e.results[i][0].transcript; fin = e.results[i].isFinal; }
      heard = now; input.value = now;
      stop(fin ? 400 : 1500);                     // 1.5 s of silence ends the question
    };
    rec.onerror = function (e) {
      RL = LANG;
      // no recogniser for this language on the phone: listen with Hindi's
      // (it knows Marathi and other Indian words best), reply in the chosen one
      if (e.error === 'language-not-supported' && !fallback && micUsed !== 'hi') {
        done = true; clearTimeout(quiet); clearTimeout(cap);
        var want = micUsed;
        setTimeout(function () { listen('hi-IN'); micUsed = want; }, 50);
        return;
      }
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') note(t('mic_denied'));
      else if (e.error === 'no-speech') note(t('mic_none'));
    };
    rec.onend = finish;
    try {
      rec.start(); setListening(true); track('voice');
      stop(8000);                                 // nothing said at all
      cap = setTimeout(function () { stop(0); }, 20000);
    } catch (_) { setListening(false); }
  }
  // FAQ answers are written in English; where the browser can translate on
  // the device (free, nothing sent anywhere), Sona answers in the reply
  // language, otherwise in English with a note.
  function translateTo(text, lang) {
    try {
      if (!('Translator' in window)) return Promise.resolve(null);
      var o = { sourceLanguage: 'en', targetLanguage: lang };
      var go = window.Translator.availability(o).then(function (a) {
        return a === 'unavailable' ? null : window.Translator.create(o).then(function (tr) { return tr.translate(text); });
      }).catch(function () { return null; });
      return Promise.race([go, new Promise(function (r) { setTimeout(function () { r(null); }, 4000); })]);
    } catch (_) { return Promise.resolve(null); }
  }

  function ask(q, label) {
    q = String(q || '').trim(); if (!q) return;
    var spoken = voiceQ; voiceQ = false;
    hush();
    input.value = ''; bubble(esc(label || q), true); setChips([]);
    var typing = bubble('<span class="sn-typing"><span></span><span></span><span></span></span>', false, true);
    talking(true);
    loadKB().then(function () {
      var a = null;
      try { a = reply(q, !!label, spoken).a; } catch (e) { a = null; }
      var ok = !!a, rl = RL;
      if (!a) a = { intent: 'unknown', html: '<p>' + t('unknown') + '</p>' + gLink(q), say: t('unknown'), chips: suggest() };
      var tr = a.en && rl !== 'en' ? translateTo(a.en, rl) : Promise.resolve(null);
      tr.then(function (txt) {
        RL = rl;
        if (a.en && rl !== 'en') {
          if (txt) { a.html = '<p>' + esc(txt) + '</p>' + a.html.replace(/^<p>[\s\S]*?<\/p>/, '') + '<div class="sn-src">' + t('translated') + '</div>'; a.say = txt; }
          else { a.html = '<p class="sn-dim">' + t('en_only') + '</p>' + a.html; a.sayLang = 'en'; }
        }
        setTimeout(function () {
          typing.remove(); talking(false);
          var m = bubble(a.html + '<div class="sn-fb"><button type="button" data-v="1" aria-label="Helpful">👍</button><button type="button" data-v="0" aria-label="Not helpful">👎</button>' +
            (TTS && a.say ? '<button type="button" class="sn-say" aria-label="' + esc(t('ui_speak')) + '">🔊</button>' : '') + '</div>');
          m._say = a.say; m._sl = a.sayLang || rl;
          setChips(a.chips || suggest());
          var tag = (rl !== 'en' ? rl : '') + (spoken ? (rl !== 'en' ? ' ' : '') + 'voice' : '');
          rpc('log_bot_question', { p_q: (tag ? '[' + tag + '] ' : '') + redact(q), p_intent: a.intent, p_answered: ok, p_page: location.pathname, p_sid: window.GR_SID || '' })
            .then(function (id) { if (id) $('.sn-fb', m).setAttribute('data-id', id); });
          track(ok ? 'answered' : 'unanswered');
          if (spoken || ttsOn) speak(a.say, m._sl, m);
        }, 350 + Math.min(600, a.html.length / 6));
      });
    }).catch(function () { typing.remove(); talking(false); RL = LANG; bubble('<p>' + t('nodata') + '</p>'); });
  }
  // "Use my location": the browser asks the visitor first; the position is
  // only compared with the city centres here and is never sent anywhere.
  function locate() {
    RL = LANG; setChips([]);
    var wait = bubble('<p class="sn-dim">' + t('loc_wait') + '</p>');
    var fail = function () {
      wait.remove(); RL = LANG;
      loadKB().then(function () { var a = askCity('loc_fail'); bubble(a.html); setChips(a.chips); });
    };
    try {
      navigator.geolocation.getCurrentPosition(function (p) {
        loadKB().then(function () {
          var c = nearest(p.coords.latitude, p.coords.longitude);
          if (!c) return fail();
          wait.remove(); setHome(c); ask(c.n, '📍 ' + c.n);
        }).catch(fail);
      }, fail, { timeout: 10000, maximumAge: 600000 });
    } catch (_) { fail(); }
  }
  function open(q) {
    ui();
    if (!opened) {
      opened = true; document.documentElement.classList.add('sona-open');
      if (!body.childNodes.length) greet();
      track('open'); loadKB();
      if (window.innerWidth > 560) setTimeout(function () { try { input.focus(); } catch (_) {} }, 200);
    }
    if (q) ask(q);
  }
  function close() {
    opened = false; document.documentElement.classList.remove('sona-open');
    hush(); if (listening && rec) try { rec.stop(); } catch (_) {}
  }
  window.GR_ASK = open;

  if (TEST) {                                   // tests drive the engine without a page
    window.__SONA_TEST = {
      setKB: function (d) { KB = d; prep(d); },
      setLang: function (c) { PICK = c === 'auto' ? '' : c; HEARD = ''; LANG = uiLang(); RL = LANG; },
      micLang: function () { return micLang(); },
      nearest: function (la, lo) { return nearest(la, lo); },
      ask: function (q, chip, spoken) { if (spoken) micUsed = micLang(); var r = reply(q, chip, spoken); return { text: r.tx, lang: RL, a: r.a }; }
    };
    return;
  }

  // ---------------------------------------------------- launcher & banner
  function mount() {
    if (document.querySelector('.bnav')) document.documentElement.classList.add('sona-bnav');
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    var fab = document.createElement('button');
    fab.className = 'sn-fab'; fab.id = 'sonaFab'; fab.type = 'button'; fab.setAttribute('aria-label', 'Ask Sona, the jewellery assistant');
    fab.innerHTML = '<span class="sn-orb">' + avatar() + '</span><span class="sn-lbl">Ask Sona</span>' + (SR ? '<span class="sn-fmic">' + ICON.mic + '</span>' : '') + '<span class="sn-ping"></span>';
    fab.onclick = function () { open(); };
    document.body.appendChild(fab);
    var seen = null; try { seen = localStorage.getItem('sona_ban2'); } catch (_) {}
    if (!seen) {
      var b = document.createElement('div'); b.className = 'sn-ban'; b.id = 'sonaBanner';
      b.innerHTML = '<span class="sn-banav">' + avatar() + '</span><span class="nw">NEW</span><span>Now <b>talk to Sona</b> about gold rates — in English, हिन्दी, اردو, मराठी, ગુજરાતી, தமிழ், తెలుగు, ಕನ್ನಡ, മലയാളം, বাংলা, ਪੰਜਾਬੀ, ଓଡ଼ିଆ or অসমীয়া. <u>Try it</u></span><button class="bx" type="button" aria-label="Dismiss">×</button>';
      b.onclick = function (e) {
        if (e.target.closest('.bx')) { b.remove(); try { localStorage.setItem('sona_ban2', '1'); } catch (_) {} return; }
        open(); track('banner');
      };
      document.body.insertBefore(b, document.body.firstChild);
    }
    if (/[?&]ask=1\b/.test(location.search) || location.hash === '#ask') setTimeout(function () { open(); }, 400);
    // Feature cards carry an empty .sn-adav: Sona herself goes there.
    [].forEach.call(document.querySelectorAll('.sn-adav'), function (el) { el.innerHTML = avatar(true); });
    // Feature cards on the pages: <button data-ask="question"> opens Sona with it.
    document.addEventListener('click', function (e) {
      var el = e.target.closest && e.target.closest('[data-ask]');
      if (!el) return;
      e.preventDefault(); track('card'); open(el.getAttribute('data-ask') || '');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
