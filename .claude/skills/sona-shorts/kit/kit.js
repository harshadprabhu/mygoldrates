/* Stage kit for Sona Shorts: everything a scene draws, each a pure function
 * of time t (seconds), so a frame can be rendered in any order.
 *
 * The stage is 540x960 CSS px (rendered at 2x = 1080x1920). An episode page
 * sets window.EP = {dur, music, sfx, chat, poster, scene(t)} and calls
 * K.boot(); render.py then calls window.render(t) once per frame.
 */
(function (root) {
  'use strict';
  var K = {};
  var clamp = K.clamp = function (x, a, b) { return Math.max(a === undefined ? 0 : a, Math.min(b === undefined ? 1 : b, x)); };
  K.lerp = function (a, b, p) { return a + (b - a) * p; };
  K.eo = function (x) { x = clamp(x); return 1 - Math.pow(1 - x, 3); };
  K.eio = function (x) { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  K.back = function (x) { x = clamp(x); var c = 1.70158, c3 = c + 1; return 1 + c3 * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
  // 0 -> 1 -> 0: in over i seconds from a, out over o seconds before b
  K.env = function (t, a, b, i, o) { i = i || .3; o = o || .22; return Math.min(K.eo((t - a) / i), 1 - K.eio((t - (b - o)) / o)); };
  K.on = function (t, a, b) { return t >= a && t < b; };
  function rnd(seed) { var x = Math.sin(seed * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
  K.rnd = rnd;

  // ------------------------------------------------------------ backdrops
  // A Diwali living room: garland, a window with fireworks, diya, rug.
  K.room = function (t) {
    var s = '<defs><linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe9c7"/><stop offset="1" stop-color="#ffd59a"/></linearGradient>' +
      '<radialGradient id="glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffcf5a" stop-opacity=".9"/><stop offset="1" stop-color="#ffcf5a" stop-opacity="0"/></radialGradient></defs>' +
      '<rect width="540" height="960" fill="url(#wall)"/>' +
      '<rect x="300" y="150" width="190" height="230" rx="14" fill="#2a2350" stroke="#b9783a" stroke-width="10"/><path d="M395 150v230M300 265h190" stroke="#b9783a" stroke-width="6"/>' +
      '<circle cx="455" cy="190" r="16" fill="#fff4c2"/>';
    for (var f = 0; f < 3; f++) {                                  // fireworks in the window
      var p = ((t + f * 1.1) % 3.3) / 3.3, cx = 330 + f * 55, cy = 230 + (f % 2) * 70;
      if (p < .6) for (var k = 0; k < 10; k++) {
        var a = k / 10 * 6.283, r = 6 + p * 46;
        s += '<circle cx="' + (cx + Math.cos(a) * r) + '" cy="' + (cy + Math.sin(a) * r) + '" r="' + (3 - p * 3) + '" fill="' + ['#ffd35a', '#ff5d95', '#7cf2ff'][f] + '" opacity="' + (1 - p / .6) + '"/>';
      }
    }
    s += '<path d="M-10 70 Q270 150 550 70" stroke="#3c7a2a" stroke-width="5" fill="none"/>';
    for (var i = 0; i <= 18; i++) {                                // marigold garland + lights
      var x = -10 + i * 31.1, y = 70 + Math.sin(i / 18 * Math.PI) * 58;
      s += '<circle cx="' + x + '" cy="' + y + '" r="11" fill="' + (i % 2 ? '#ff9d1c' : '#ffc61a') + '"/>';
      if (i % 3 === 1) s += '<path d="M' + x + ' ' + (y + 10) + ' v26" stroke="#3c7a2a" stroke-width="3"/><circle cx="' + x + '" cy="' + (y + 40) + '" r="7" fill="#ff9d1c"/>';
      if (i % 2 === 0) s += '<circle cx="' + x + '" cy="' + (y - 14) + '" r="4" fill="#fff6b0" opacity="' + (.5 + .5 * Math.sin(t * 6 + i)) + '"/>';
    }
    s += '<rect y="740" width="540" height="220" fill="#d29a62"/><path d="M0 740h540" stroke="#a8713d" stroke-width="6"/>' +
      '<ellipse cx="270" cy="815" rx="250" ry="58" fill="#c0263a"/><ellipse cx="270" cy="815" rx="215" ry="44" fill="none" stroke="#ffd35a" stroke-width="5" stroke-dasharray="14 10"/>' +
      '<ellipse cx="270" cy="815" rx="90" ry="20" fill="none" stroke="#ff9d1c" stroke-width="5"/>' +
      '<rect x="22" y="600" width="70" height="140" rx="8" fill="#9a5b2a"/><ellipse cx="57" cy="598" rx="44" ry="9" fill="#b06a32"/>' +
      '<circle cx="57" cy="560" r="60" fill="url(#glow)" opacity="' + (.6 + .15 * Math.sin(t * 9)) + '"/>' +
      '<path d="M32 590 Q57 612 82 590 Z" fill="#c9650e"/><path d="M57 588 q-10 -18 0 -34 q10 16 0 34Z" fill="#ffb81c" transform="rotate(' + (Math.sin(t * 11) * 6) + ' 57 588)"/>' +
      '<path d="M57 586 q-5 -10 0 -19 q5 9 0 19Z" fill="#fff3b0"/>';
    return s;
  };
  // A jewellery shop: maroon wall, glowing shelves, glass counter.
  K.shop = function (t) {
    var s = '<defs><linearGradient id="shopw" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5a1424"/><stop offset="1" stop-color="#3a0c17"/></linearGradient>' +
      '<linearGradient id="glass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#bfe6ff" stop-opacity=".55"/><stop offset="1" stop-color="#8fc9ee" stop-opacity=".25"/></linearGradient></defs>' +
      '<rect width="540" height="960" fill="url(#shopw)"/>' +
      '<rect x="120" y="60" width="300" height="64" rx="12" fill="#2a0810" stroke="#e3b44f" stroke-width="4"/>' +
      '<text x="270" y="104" text-anchor="middle" font-family="Baloo 2, sans-serif" font-weight="800" font-size="30" fill="#ffd35a">✨ JEWELLERY ✨</text>';
    for (var r = 0; r < 2; r++) {
      var y = 200 + r * 150;
      s += '<rect x="30" y="' + (y + 80) + '" width="480" height="12" rx="4" fill="#e3b44f"/>';
      for (var i = 0; i < 4; i++) {
        var x = 85 + i * 123;
        s += '<circle cx="' + x + '" cy="' + (y + 40) + '" r="46" fill="#ffd35a" opacity="' + (.08 + .06 * Math.sin(t * 3 + i + r)) + '"/>' +
          (i % 2 ? '<path d="M' + (x - 34) + ' ' + (y + 10) + ' Q' + x + ' ' + (y + 70) + ' ' + (x + 34) + ' ' + (y + 10) + '" stroke="#ffd35a" stroke-width="7" fill="none"/><circle cx="' + x + '" cy="' + (y + 52) + '" r="9" fill="#ff3b6b"/>'
            : '<circle cx="' + x + '" cy="' + (y + 40) + '" r="24" fill="none" stroke="#ffd35a" stroke-width="8"/><circle cx="' + x + '" cy="' + (y + 40) + '" r="14" fill="none" stroke="#f6d77d" stroke-width="4"/>');
      }
    }
    s += '<rect y="690" width="540" height="270" fill="#2a0810"/>' +
      '<rect x="10" y="650" width="520" height="300" rx="14" fill="url(#glass)" stroke="#e3b44f" stroke-width="5"/>' +
      '<path d="M40 700 l60 -40M120 700 l60 -40" stroke="#fff" stroke-width="5" opacity=".35"/>';
    return s;
  };

  // --------------------------------------------------------------- overlays
  function esc(x) { return String(x).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  K.esc = esc;
  // Speech bubble pointing at (x, y): tail 'bl' (bottom-left) or 'br'.
  K.bubble = function (o) {
    if (o.p <= 0.001) return '';
    var w = o.w || 300, sc = K.back(o.p), left = o.tail === 'br' ? o.x - w + 40 : o.x - 40;
    left = clamp(left, 14, 540 - w - 14);
    var tx = o.x - left;
    return '<div class="bub" style="left:' + left + 'px;bottom:' + (960 - o.y + 22) + 'px;width:' + w + 'px;transform-origin:' + tx + 'px 120%;transform:scale(' + sc + ');opacity:' + clamp(o.p * 2) + ';' + (o.bg ? 'background:' + o.bg + ';' : '') + (o.size ? 'font-size:' + o.size + 'px;' : '') + '">' +
      o.text + '<i style="left:' + (tx - 14) + 'px;' + (o.bg ? 'border-top-color:' + o.bg : '') + '"></i></div>';
  };
  K.caption = function (text, p, y, size) {
    if (p <= 0.001) return '';
    return '<div class="cap" style="top:' + (y || 120) + 'px;font-size:' + (size || 40) + 'px;transform:translateY(' + ((1 - K.eo(p)) * -30) + 'px) scale(' + (.85 + .15 * K.back(p)) + ');opacity:' + clamp(p * 1.6) + '">' + text + '</div>';
  };

  // -------------------------------------------------------------- particles
  K.hearts = function (t, t0, cx, cy, n, spread) {
    var s = '', u = t - t0;
    if (u < 0 || u > 2.6) return '';
    for (var i = 0; i < n; i++) {
      var a = -Math.PI / 2 + (rnd(i) - .5) * (spread || 2.4), sp = 120 + rnd(i + 9) * 160, d = u - rnd(i + 3) * .3;
      if (d < 0) continue;
      var x = cx + Math.cos(a) * sp * d, y = cy + Math.sin(a) * sp * d + 40 * d * d, r = 9 + rnd(i + 5) * 12;
      s += '<g opacity="' + clamp(1.6 - d * .75) + '">' + root.CHAR.heart(x, y, r * K.back(d * 4), ['#ff3b6b', '#ff7aa6', '#ff2457'][i % 3]) + '</g>';
    }
    return s;
  };
  K.coins = function (t, t0, n) {
    var s = '', u = t - t0;
    if (u < 0 || u > 3.2) return '';
    for (var i = 0; i < n; i++) {
      var d = u - rnd(i + 1) * 1.2;
      if (d < 0) continue;
      var x = 30 + rnd(i + 2) * 480, y = -40 + d * (420 + rnd(i) * 260), sw = Math.abs(Math.cos(d * 7 + i));
      s += '<g transform="translate(' + x + ' ' + y + ') scale(' + (.25 + .75 * sw) + ' 1)"><circle r="17" fill="#ffd35a" stroke="#b07e12" stroke-width="3"/><text y="7" text-anchor="middle" font-size="20" font-weight="800" fill="#b07e12" font-family="Baloo 2, sans-serif">₹</text></g>';
    }
    return s;
  };
  K.sparkles = function (t, cx, cy, rad, n) {
    var s = '';
    for (var i = 0; i < n; i++) {
      var ph = (t * 1.3 + rnd(i)) % 1, a = rnd(i + 4) * 6.283, r = rad * (.4 + rnd(i + 7) * .6);
      var x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r, k = Math.sin(ph * Math.PI) * 11;
      s += '<path d="M' + x + ' ' + (y - k) + ' Q' + x + ' ' + y + ' ' + (x + k) + ' ' + y + ' Q' + x + ' ' + y + ' ' + x + ' ' + (y + k) + ' Q' + x + ' ' + y + ' ' + (x - k) + ' ' + y + ' Q' + x + ' ' + y + ' ' + x + ' ' + (y - k) + 'Z" fill="#fff6c2"/>';
    }
    return s;
  };
  K.moth = function (t, t0, x0, y0) {                                // flies out of an empty wallet
    var u = t - t0;
    if (u < 0 || u > 2.4) return '';
    var x = x0 + Math.sin(u * 5) * 30 + u * 110, y = y0 - u * 210 - u * u * 40, f = .25 + .75 * Math.abs(Math.sin(u * 26));
    return '<g transform="translate(' + x + ' ' + y + ') scale(1.3)"><g transform="scale(' + f + ' 1)"><path d="M0 0 C-30 -34 -44 -6 -30 10 C-22 18 -8 12 0 4Z" fill="#a59d90" stroke="#6b645a" stroke-width="2"/>' +
      '<path d="M0 0 C30 -34 44 -6 30 10 C22 18 8 12 0 4Z" fill="#bdb5a8" stroke="#6b645a" stroke-width="2"/></g><ellipse rx="4.5" ry="13" fill="#5a534a"/><path d="M-2 -12 q-6 -10 -12 -12M2 -12 q6 -10 12 -12" stroke="#5a534a" stroke-width="2" fill="none"/></g>';
  };

  // -------------------------------------------------------- the real Sona
  // The phone shows the live site's chat (an iframe of /?c=1). render.py asks
  // the questions once before recording; here each message is shown, typed
  // and scrolled by time, so frames stay a pure function of t.
  // spec: {typeAt, sendAt, answerAt, q}
  K.chat = function (t, spec) {
    var f = document.getElementById('chat');
    var d = f && f.contentDocument;
    if (!d) return;
    var ms = d.querySelectorAll('#sonaPanel .sn-body > .sn-m:not(#fakeTyping)'), body = d.querySelector('#sonaPanel .sn-body'), inp = d.getElementById('sonaInput');
    if (!ms.length || !body) return;
    var dots = d.getElementById('fakeTyping');
    if (!dots) {
      dots = d.createElement('div'); dots.id = 'fakeTyping'; dots.className = 'sn-m bot';
      dots.innerHTML = ms[ms.length - 1].querySelector('.sn-mav').outerHTML + '<div class="sn-b"><span class="sn-typing"><span></span><span></span><span></span></span></div>';
      body.appendChild(dots);
    }
    var q = ms[ms.length - 2], a = ms[ms.length - 1];
    for (var i = 0; i < ms.length - 2; i++) ms[i].style.display = 'none';
    var typed = clamp((t - spec.typeAt) / Math.max(.1, spec.sendAt - spec.typeAt));
    inp.value = t < spec.sendAt ? spec.q.slice(0, Math.round(typed * spec.q.length)) : '';
    q.style.display = t >= spec.sendAt ? '' : 'none';
    dots.style.display = t >= spec.sendAt + .25 && t < spec.answerAt ? '' : 'none';
    a.style.display = t >= spec.answerAt ? '' : 'none';
    a.style.opacity = clamp((t - spec.answerAt) / .25);
    var chips = d.querySelector('#sonaPanel .sn-chips');
    if (chips) chips.style.visibility = t >= spec.answerAt + .4 ? 'visible' : 'hidden';
    var mx = Math.max(0, body.scrollHeight - body.clientHeight);          // scroll to the end of the answer
    body.scrollTop = t >= spec.answerAt ? K.eio((t - spec.answerAt - (spec.hold || .8)) / 1.4) * Math.min(mx, spec.scroll || mx) : 0;
  };

  // --------------------------------------------------------------- outro
  K.outro = function (p, t, line) {
    if (p <= 0.001) return '';
    var av = root.GR_SONA_AVATAR ? root.GR_SONA_AVATAR(true) : '';
    return '<div class="outro" style="opacity:' + clamp(p * 1.5) + '">' +
      '<div class="o-sona" style="transform:translateY(' + ((1 - K.back(p)) * -260 + Math.sin(t * 3) * 6) + 'px)">' + av + '</div>' +
      '<div class="o-line" style="transform:scale(' + (.8 + .2 * K.back(clamp((p - .15) * 1.4))) + ')">' + line + '</div>' +
      '<div class="o-site"><img src="/icon-192.png" alt="">mygoldrates.com</div>' +
      '<div class="o-sub">Free · no app · 13 languages</div></div>';
  };

  // ------------------------------------------------------------- dialogue
  // Lines are laid end to end from the voices' real lengths (window.VO, from
  // voice.py): tl.say(id, gap) -> {a, b}, the seconds the line plays;
  // tl.cut(gap) moves on to the next music beat for a scene change.
  K.timeline = function (VO, beat, first) {
    var c = 0, tl = { voice: [] };
    tl.now = function () { return c; };
    tl.wait = function (d) { c += d; return c; };
    tl.say = function (id, gap) {
      c += gap || 0;
      var r = { a: c, b: c + ((VO && VO[id]) || 2) };
      tl.voice.push([id, c, 0]); c = r.b; return r;
    };
    tl.cut = function (gap) {
      c += gap || 0;
      if (beat) c = first + Math.ceil((c - first) / beat - 1e-6) * beat;
      return c;
    };
    return tl;
  };
  // A speech bubble that stays up while its line is spoken (the subtitle).
  K.line = function (t, r, o) {
    o.p = K.env(t, r.a - .12, r.b + .45, .22, .2);
    return K.bubble(o);
  };
  K.talking = function (t, r) { return t >= r.a && t < r.b - .05; };

  // ----------------------------------------------------------------- boot
  K.boot = function () {
    var EP = root.EP;
    root.T_END = EP.dur;
    root.render = function (t) {
      var out = EP.scene(t) || {};
      document.getElementById('bg').innerHTML = out.bg || '';
      document.getElementById('cast').innerHTML = out.cast || '';
      document.getElementById('fx').innerHTML = out.fx || '';
      document.getElementById('ui').innerHTML = out.ui || '';
      var ph = document.getElementById('phone');
      if (out.phone) { ph.style.display = 'block'; ph.style.transform = out.phone; } else ph.style.display = 'none';
      if (EP.chat && out.phone) K.chat(t, EP.chat);
      document.getElementById('flash').style.opacity = out.flash || 0;
    };
  };
  root.K = K;
})(typeof window !== 'undefined' ? window : globalThis);
