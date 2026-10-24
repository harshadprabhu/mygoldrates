// Runs Sona's answer engine (no page) on questions given as JSON on stdin;
// prints [{q, text, lang, intent, html, say}] - used by tests/test_assistant.py.
global.window = globalThis;
window.__SONA_TEST = 1;
global.location = { pathname: '/', search: '', hash: '' };
global.navigator = { languages: ['en-IN'] };
global.localStorage = { getItem: function () { return null; }, setItem: function () {} };
var path = require('path'), fs = require('fs'), root = path.join(__dirname, '..');
require(path.join(root, 'sona_i18n.js'));
require(path.join(root, 'sona_lang.js'));
require(path.join(root, 'assistant.js'));
var S = window.__SONA_TEST, input = JSON.parse(fs.readFileSync(0, 'utf8'));
S.setKB(JSON.parse(fs.readFileSync(input.kb, 'utf8')));
console.log(JSON.stringify(input.qs.map(function (x) {
  S.setLang(x.lang || 'en');
  var r = S.ask(x.q), a = r.a || {};
  return { q: x.q, text: r.text, lang: r.lang, intent: a.intent || null, html: a.html || '', say: a.say || '' };
})));
