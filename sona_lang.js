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
  function detect(q, cur) {
    if (AR.test(q)) return 'ur';
    var m = String(q).match(/[ऀ-ൿ]/);
    if (!m) return null;
    var b = scriptOf(m[0].charCodeAt(0));
    if (b[1] === 'deva') return cur === 'mr' || MR.test(q) ? 'mr' : 'hi';
    if (b[1] === 'beng') return cur === 'as' || AS.test(q) ? 'as' : 'bn';
    return SCRIPT_LANG[b[1]];
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

  root.SONA_LANG = { LANGS: LANGS, romWord: romWord, key: key, detect: detect, understand: understand,
    vocabOf: vocabOf, isIndic: isIndic, LEX: LEX };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.SONA_LANG;
})(typeof window !== 'undefined' ? window : globalThis);
