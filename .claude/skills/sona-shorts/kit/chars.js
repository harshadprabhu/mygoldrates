/* Chiku & Piku - MyGoldRates' own cartoon couple (original designs, ours
 * to use anywhere). Chiku: a chubby golden puppy in an orange kurta.
 * Piku: a white kitten in a pink saree, with a bow and a bindi.
 *
 * Each is drawn as SVG from a state, so a scene is a pure function of time:
 *   CHAR.chiku({x, y, s, flip, rot, sq, mood, talk, t, pose, prop, kneel})
 * x, y   feet position on the 540x960 stage; s scale (1 = about 300px tall)
 * flip   -1 mirrors; rot degrees; sq squash (+ wider/shorter, - taller)
 * mood   normal | happy | love | sweat | shock | faint | laugh | sly | kiss | cry
 * talk   true moves the mouth; t is the time, for blinks and wobbles
 * pose   idle | wave | phone | phone2 | hold | cheer | hug | shrug | cheeks | fan | point
 * prop   phone | ring | wallet | jhumka | bill | none (held in the right hand)
 */
(function (root) {
  'use strict';
  var PAL = {
    chiku: { fur: '#e6a966', furDk: '#bf7d3d', ear: '#7b4a22', muzzle: '#fde9cf', cloth: '#f2841f', clothDk: '#c9650e', trim: '#ffd35a', line: '#5a3413' },
    piku: { fur: '#fffaf5', furDk: '#eadbcf', ear: '#ffb3c8', muzzle: '#ffffff', cloth: '#ff5d95', clothDk: '#d93f76', trim: '#ffd35a', line: '#6b4b45' }
  };
  var HANDS = {               // [left hand, right hand], character-local
    idle: [[-78, -60], [78, -60]], wave: [[-78, -60], [96, -205]], phone: [[-78, -60], [34, -168]],
    phone2: [[-26, -128], [26, -128]], hold: [[-30, -104], [30, -104]], cheer: [[-92, -215], [92, -215]],
    hug: [[-118, -138], [118, -138]], shrug: [[-104, -150], [104, -150]], cheeks: [[-52, -178], [52, -178]],
    fan: [[-78, -60], [86, -150]], point: [[-78, -60], [120, -150]]
  };

  function blinkAt(t, seed) {          // a short blink every few seconds
    var p = (t + seed) % 3.7;
    return p > 3.55;
  }
  function heart(x, y, r, fill) {
    return '<path d="M' + x + ' ' + (y + r * .9) + ' C' + (x - r * 1.6) + ' ' + (y - r * .2) + ' ' + (x - r * .9) + ' ' + (y - r * 1.25) + ' ' + x + ' ' + (y - r * .45) +
      ' C' + (x + r * .9) + ' ' + (y - r * 1.25) + ' ' + (x + r * 1.6) + ' ' + (y - r * .2) + ' ' + x + ' ' + (y + r * .9) + 'Z" fill="' + fill + '"/>';
  }
  function eyes(mood, t, ex, ey, lash, seed) {
    var o = '', i, x;
    for (i = -1; i <= 1; i += 2) {
      x = i * ex;
      if (mood === 'love') o += heart(x, ey, 13 + Math.sin(t * 9) * 1.5, '#ff3b6b');
      else if (mood === 'shock') o += '<circle cx="' + x + '" cy="' + ey + '" r="15" fill="#fff" stroke="#2b1a10" stroke-width="3"/><circle cx="' + x + '" cy="' + ey + '" r="4.5" fill="#2b1a10"/>';
      else if (mood === 'faint') o += '<path d="M' + (x - 9) + ' ' + (ey - 9) + 'l18 18M' + (x + 9) + ' ' + (ey - 9) + 'l-18 18" stroke="#2b1a10" stroke-width="5" stroke-linecap="round"/>';
      else if (mood === 'happy' || mood === 'laugh' || mood === 'kiss') o += '<path d="M' + (x - 10) + ' ' + (ey + 3) + ' Q' + x + ' ' + (ey - 11) + ' ' + (x + 10) + ' ' + (ey + 3) + '" stroke="#2b1a10" stroke-width="5" fill="none" stroke-linecap="round"/>';
      else if (mood === 'cry') o += '<path d="M' + (x - 10) + ' ' + (ey - 2) + ' Q' + x + ' ' + (ey + 8) + ' ' + (x + 10) + ' ' + (ey - 2) + '" stroke="#2b1a10" stroke-width="5" fill="none" stroke-linecap="round"/>' +
        '<path d="M' + (x + i * 4) + ' ' + (ey + 8) + ' q' + (i * 3) + ' 16 0 ' + (22 + (t * 40) % 14) + '" stroke="#7cc8ff" stroke-width="6" fill="none" stroke-linecap="round" opacity=".85"/>';
      else if (blinkAt(t, seed)) o += '<path d="M' + (x - 9) + ' ' + ey + 'h18" stroke="#2b1a10" stroke-width="5" stroke-linecap="round"/>';
      else {
        var lid = mood === 'sly' ? '<path d="M' + (x - 11) + ' ' + (ey - 5) + 'h22" stroke="#2b1a10" stroke-width="5" stroke-linecap="round"/>' : '';
        o += '<ellipse cx="' + x + '" cy="' + ey + '" rx="8.5" ry="11.5" fill="#2b1a10"/><circle cx="' + (x + 3) + '" cy="' + (ey - 4) + '" r="3.4" fill="#fff"/>' + lid;
      }
      if (lash && mood !== 'faint' && mood !== 'love')
        o += '<path d="M' + (x + i * 8) + ' ' + (ey - 9) + 'l' + (i * 7) + ' -6M' + (x + i * 10) + ' ' + (ey - 3) + 'l' + (i * 8) + ' -2" stroke="#2b1a10" stroke-width="3" stroke-linecap="round"/>';
    }
    return o;
  }
  function mouth(mood, talk, t, my, w) {
    var open = talk ? (Math.sin(t * 22) + 1) / 2 : 0;
    if (mood === 'shock') return '<ellipse cx="0" cy="' + (my + 6) + '" rx="' + (w * .45) + '" ry="' + (w * .6) + '" fill="#5a1f1f"/>';
    if (mood === 'laugh') return '<path d="M' + (-w) + ' ' + my + ' Q0 ' + (my + w * 1.9) + ' ' + w + ' ' + my + 'Z" fill="#5a1f1f"/><ellipse cx="0" cy="' + (my + w * .95) + '" rx="' + (w * .5) + '" ry="' + (w * .32) + '" fill="#ff7d8e"/>';
    if (mood === 'sweat') return '<path d="M' + (-w) + ' ' + (my + 4) + ' q' + (w / 4) + ' -6 ' + (w / 2) + ' 0 t' + (w / 2) + ' 0 t' + (w / 2) + ' 0 t' + (w / 2) + ' 0" stroke="#2b1a10" stroke-width="4" fill="none" stroke-linecap="round"/>';
    if (mood === 'faint') return '<path d="M' + (-w * .7) + ' ' + (my + 4) + ' q' + (w * .35) + ' -6 ' + (w * .7) + ' 0 t' + (w * .7) + ' 0" stroke="#2b1a10" stroke-width="4" fill="none"/><ellipse cx="' + (w * .3) + '" cy="' + (my + 12) + '" rx="7" ry="9" fill="#ff7d8e"/>';
    if (mood === 'kiss') return heart(0, my + 6, 7, '#ff3b6b');
    if (mood === 'cry') return '<path d="M' + (-w * .8) + ' ' + (my + 10) + ' Q0 ' + (my - 2) + ' ' + (w * .8) + ' ' + (my + 10) + '" stroke="#2b1a10" stroke-width="4.5" fill="none" stroke-linecap="round"/>';
    if (open > .25) return '<ellipse cx="0" cy="' + (my + 5) + '" rx="' + (w * .55) + '" ry="' + (3 + open * w * .55) + '" fill="#5a1f1f"/>';
    return '<path d="M' + (-w * .8) + ' ' + my + ' Q0 ' + (my + w * .9) + ' ' + (w * .8) + ' ' + my + '" stroke="#2b1a10" stroke-width="4.5" fill="none" stroke-linecap="round"/>';
  }
  function arm(sx, sy, hx, hy, c, cd) {
    var mx = (sx + hx) / 2 + (hy < sy ? 0 : (hx > 0 ? 8 : -8)), my = (sy + hy) / 2 + 6;
    return '<path d="M' + sx + ' ' + sy + ' Q' + mx + ' ' + my + ' ' + hx + ' ' + hy + '" stroke="' + cd + '" stroke-width="30" fill="none" stroke-linecap="round"/>' +
      '<path d="M' + sx + ' ' + sy + ' Q' + mx + ' ' + my + ' ' + hx + ' ' + hy + '" stroke="' + c + '" stroke-width="24" fill="none" stroke-linecap="round"/>' +
      '<circle cx="' + hx + '" cy="' + hy + '" r="15" fill="' + c + '" stroke="' + cd + '" stroke-width="3"/>';
  }
  function prop(kind, x, y, t) {
    var g = '<g transform="translate(' + x + ' ' + y + ')">';
    if (kind === 'phone') return g + '<rect x="-17" y="-34" width="34" height="62" rx="8" fill="#1b1b22" stroke="#d6b25e" stroke-width="2.5"/><rect x="-13" y="-28" width="26" height="48" rx="4" fill="#ffd77a"/><circle cx="0" cy="-10" r="7" fill="#fff8e1"/><rect x="-9" y="2" width="18" height="3" rx="1.5" fill="#b07e12"/><rect x="-9" y="8" width="13" height="3" rx="1.5" fill="#b07e12"/></g>';
    if (kind === 'ring') return g + '<rect x="-24" y="-8" width="48" height="30" rx="7" fill="#c8102e" stroke="#7a0a1c" stroke-width="3"/><path d="M-24 -6 Q0 -40 24 -6Z" fill="#a50d26" stroke="#7a0a1c" stroke-width="3"/>' +
      '<rect x="-18" y="-4" width="36" height="9" rx="4" fill="#4a0612"/><circle cx="0" cy="-6" r="9" fill="none" stroke="#ffd35a" stroke-width="4.5"/><path d="M0 -24 l5 7 -5 6 -5 -6Z" fill="#dff6ff" stroke="#9fd8ff" stroke-width="1.5"/>' +
      '<path d="M14 -30 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2Z" fill="#fff" opacity="' + (.5 + .5 * Math.sin(t * 8)) + '"/></g>';
    if (kind === 'wallet') return g + '<rect x="-30" y="-20" width="60" height="40" rx="7" fill="#7b4a22" stroke="#4e2c10" stroke-width="3"/><path d="M-30 -20 Q0 6 30 -20" fill="#8f5a2c" stroke="#4e2c10" stroke-width="3"/><circle cx="20" cy="2" r="4" fill="#ffd35a"/></g>';
    if (kind === 'jhumka') return g + '<path d="M0 -26 v10" stroke="#e3b44f" stroke-width="3"/><circle cx="0" cy="-28" r="5" fill="#ffd35a"/><path d="M-18 -8 Q0 -26 18 -8 L14 4 H-14Z" fill="#ffd35a" stroke="#b07e12" stroke-width="2.5"/>' +
      '<path d="M-14 4 Q0 14 14 4" fill="none" stroke="#b07e12" stroke-width="2.5"/><circle cx="-10" cy="10" r="3" fill="#ff3b6b"/><circle cx="0" cy="13" r="3" fill="#ff3b6b"/><circle cx="10" cy="10" r="3" fill="#ff3b6b"/></g>';
    if (kind === 'bill') return g + '<rect x="-28" y="-40" width="56" height="74" rx="4" fill="#fff" stroke="#c9b9a8" stroke-width="2"/><path d="M-18 -26h36M-18 -14h28M-18 -2h36M-18 10h20" stroke="#bbb" stroke-width="3"/><path d="M-18 22h36" stroke="#e23" stroke-width="4"/></g>';
    return '';
  }

  function draw(who, o) {
    var C = PAL[who], t = o.t || 0, mood = o.mood || 'normal', pose = o.pose || 'idle';
    var bob = mood === 'faint' ? 0 : Math.sin(t * 3.1 + (who === 'chiku' ? 0 : 1.7)) * 3;
    var sq = (o.sq || 0), hands = HANDS[pose] || HANDS.idle;
    var lh = hands[0].slice(), rh = hands[1].slice();
    if (pose === 'wave') rh[0] += Math.sin(t * 14) * 12;
    if (pose === 'fan') { rh[0] += Math.sin(t * 20) * 16; rh[1] += Math.cos(t * 20) * 6; }
    if (pose === 'cheer') { lh[1] += Math.sin(t * 16) * 6; rh[1] -= Math.sin(t * 16) * 6; }
    var tr = 'translate(' + o.x + ' ' + o.y + ') rotate(' + (o.rot || 0) + ') scale(' + ((o.s || 1) * (o.flip || 1) * (1 + sq)) + ' ' + ((o.s || 1) * (1 - sq)) + ')';
    var g = '<g transform="' + tr + '">';
    g += '<ellipse cx="0" cy="2" rx="' + (who === 'chiku' ? 74 : 64) + '" ry="12" fill="#000" opacity=".16"/>';
    g += '<g transform="translate(0 ' + bob + ')">';
    var kneel = o.kneel ? 26 : 0;
    if (who === 'piku') {                                                  // tail, behind
      var tw = Math.sin(t * 2.6) * 10;
      g += '<path d="M48 -40 Q' + (108 + tw) + ' -70 ' + (86 + tw) + ' -142" stroke="' + C.furDk + '" stroke-width="22" fill="none" stroke-linecap="round"/>' +
        '<path d="M48 -40 Q' + (108 + tw) + ' -70 ' + (86 + tw) + ' -142" stroke="' + C.fur + '" stroke-width="16" fill="none" stroke-linecap="round"/>';
    } else {
      var wg = Math.sin(t * 12) * 12;
      g += '<path d="M54 -46 q30 -6 ' + (36 + wg / 3) + ' ' + (-34 + wg) + '" stroke="' + C.furDk + '" stroke-width="18" fill="none" stroke-linecap="round"/>';
    }
    if (!kneel) g += '<ellipse cx="-30" cy="-12" rx="24" ry="16" fill="' + C.furDk + '"/><ellipse cx="30" cy="-12" rx="24" ry="16" fill="' + C.furDk + '"/>' +
      '<ellipse cx="-30" cy="-14" rx="20" ry="12" fill="' + C.fur + '"/><ellipse cx="30" cy="-14" rx="20" ry="12" fill="' + C.fur + '"/>';
    g += '<g transform="translate(0 ' + kneel + ')">';
    // body + clothes
    if (who === 'chiku') {
      g += '<ellipse cx="0" cy="-82" rx="70" ry="70" fill="' + C.clothDk + '"/><ellipse cx="0" cy="-84" rx="66" ry="66" fill="' + C.cloth + '"/>' +
        '<path d="M0 -146 v100" stroke="' + C.clothDk + '" stroke-width="3"/><circle cx="0" cy="-124" r="5" fill="' + C.trim + '"/><circle cx="0" cy="-104" r="5" fill="' + C.trim + '"/><circle cx="0" cy="-84" r="5" fill="' + C.trim + '"/>' +
        '<path d="M-30 -146 Q0 -128 30 -146" stroke="' + C.trim + '" stroke-width="6" fill="none" stroke-linecap="round"/>';
    } else {
      g += '<ellipse cx="0" cy="-78" rx="62" ry="64" fill="' + C.furDk + '"/><ellipse cx="0" cy="-80" rx="59" ry="61" fill="' + C.fur + '"/>' +
        '<path d="M-58 -70 Q-10 -60 30 -20 L52 -40 Q20 -100 -40 -132 Z" fill="' + C.cloth + '"/><path d="M-40 -132 Q20 -100 52 -40" stroke="' + C.trim + '" stroke-width="6" fill="none" stroke-linecap="round"/>' +
        '<path d="M-58 -38 Q0 -22 58 -38 L56 -26 Q0 -6 -56 -26Z" fill="' + C.clothDk + '"/>';
    }
    var shY = who === 'chiku' ? -118 : -110, shX = who === 'chiku' ? 54 : 48;
    var behind = pose === 'hug';
    var armsSvg = arm(-shX, shY, lh[0], lh[1], C.fur, C.furDk) + arm(shX, shY, rh[0], rh[1], C.fur, C.furDk);
    if (behind) g += armsSvg;
    // head
    var hy = who === 'chiku' ? -214 : -200, hr = who === 'chiku' ? 88 : 82;
    var tilt = o.tilt || 0;
    g += '<g transform="rotate(' + tilt + ' 0 ' + (hy + 60) + ')">';
    if (who === 'chiku') {
      var ef = Math.sin(t * 3.1) * 4 + (o.earFlap ? Math.sin(t * 30) * 14 : 0);
      g += '<ellipse cx="-80" cy="' + (hy + 6) + '" rx="30" ry="56" fill="' + C.ear + '" transform="rotate(' + (18 + ef) + ' -80 ' + (hy - 30) + ')"/>' +
        '<ellipse cx="80" cy="' + (hy + 6) + '" rx="30" ry="56" fill="' + C.ear + '" transform="rotate(' + (-18 - ef) + ' 80 ' + (hy - 30) + ')"/>';
      g += '<circle cx="0" cy="' + hy + '" r="' + (hr + 3) + '" fill="' + C.furDk + '"/><circle cx="0" cy="' + hy + '" r="' + hr + '" fill="' + C.fur + '"/>' +
        '<path d="M-14 ' + (hy - hr + 6) + ' q8 -22 22 -6 q6 -16 16 0" fill="' + C.fur + '" stroke="' + C.furDk + '" stroke-width="3"/>' +
        '<ellipse cx="0" cy="' + (hy + 34) + '" rx="46" ry="32" fill="' + C.muzzle + '"/>' +
        eyes(mood, t, 33, hy - 6, false, 0) +
        '<ellipse cx="0" cy="' + (hy + 18) + '" rx="14" ry="9.5" fill="#2b1a10"/><ellipse cx="-4" cy="' + (hy + 15) + '" rx="4" ry="2.5" fill="#fff" opacity=".7"/>' +
        '<g transform="translate(0 ' + (hy + 34) + ')">' + mouth(mood, o.talk, t, 0, 14) + '</g>';
    } else {
      var ew = Math.sin(t * 2.2) * 3;
      g += '<path d="M-66 ' + (hy - 30) + ' L-52 ' + (hy - 104 + ew) + ' L-12 ' + (hy - 70) + 'Z" fill="' + C.furDk + '"/><path d="M-60 ' + (hy - 38) + ' L-51 ' + (hy - 92 + ew) + ' L-22 ' + (hy - 68) + 'Z" fill="' + C.ear + '"/>' +
        '<path d="M66 ' + (hy - 30) + ' L52 ' + (hy - 104 - ew) + ' L12 ' + (hy - 70) + 'Z" fill="' + C.furDk + '"/><path d="M60 ' + (hy - 38) + ' L51 ' + (hy - 92 - ew) + ' L22 ' + (hy - 68) + 'Z" fill="' + C.ear + '"/>';
      g += '<circle cx="0" cy="' + hy + '" r="' + (hr + 3) + '" fill="' + C.furDk + '"/><circle cx="0" cy="' + hy + '" r="' + hr + '" fill="' + C.fur + '"/>' +
        '<g transform="translate(46 ' + (hy - 70) + ') rotate(18)"><ellipse cx="-16" cy="0" rx="18" ry="12" fill="#ff3d7f"/><ellipse cx="16" cy="0" rx="18" ry="12" fill="#ff3d7f"/><circle r="8" fill="#e01f63"/></g>' +
        '<circle cx="0" cy="' + (hy - 40) + '" r="6" fill="#e0202f"/>' +
        eyes(mood, t, 30, hy - 2, true, 1.3) +
        '<path d="M-7 ' + (hy + 18) + ' h14 l-7 8Z" fill="#ff8fab"/>' +
        '<g transform="translate(0 ' + (hy + 28) + ')">' + (mood === 'normal' && !o.talk ? '<path d="M-12 0 q6 8 12 0 q6 8 12 0" stroke="#2b1a10" stroke-width="3.5" fill="none" stroke-linecap="round"/>' : mouth(mood, o.talk, t, 0, 12)) + '</g>' +
        '<path d="M-38 ' + (hy + 16) + ' h-36M-38 ' + (hy + 26) + ' l-34 8M38 ' + (hy + 16) + ' h36M38 ' + (hy + 26) + ' l34 8" stroke="#c9b6aa" stroke-width="2.5" stroke-linecap="round"/>';
    }
    var bl = (mood === 'love' || mood === 'kiss' || o.blush) ? .75 : .38;
    g += '<ellipse cx="-52" cy="' + (hy + 24) + '" rx="15" ry="9" fill="#ff7d8e" opacity="' + bl + '"/><ellipse cx="52" cy="' + (hy + 24) + '" rx="15" ry="9" fill="#ff7d8e" opacity="' + bl + '"/>';
    if (mood === 'sweat') {
      var d = (t * 1.6) % 1;
      g += '<path d="M' + (hr - 6) + ' ' + (hy - 40 + d * 40) + ' q10 16 0 22 q-10 -6 0 -22Z" fill="#7cc8ff" opacity="' + (1 - d * .6) + '"/>' +
        '<path d="M' + (-hr + 10) + ' ' + (hy - 50 + ((d + .5) % 1) * 40) + ' q8 13 0 18 q-8 -5 0 -18Z" fill="#7cc8ff" opacity=".8"/>';
    }
    if (mood === 'faint') {                                                  // stars circling
      for (var k = 0; k < 3; k++) {
        var a = t * 5 + k * 2.09, sx = Math.cos(a) * 70, sy = hy - hr - 10 + Math.sin(a) * 14;
        g += '<path d="M' + sx + ' ' + (sy - 10) + ' l3 7 7 1 -5 5 1.5 7 -6.5 -3.5 -6.5 3.5 1.5 -7 -5 -5 7 -1Z" fill="#ffd35a"/>';
      }
    }
    g += '</g>';                                                            // head
    if (!behind) g += armsSvg;
    if (o.prop && o.prop !== 'none') g += prop(o.prop, rh[0], rh[1] - 18, t);
    g += '</g></g></g>';
    return g;
  }

  root.CHAR = {
    chiku: function (o) { return draw('chiku', o); },
    piku: function (o) { return draw('piku', o); },
    heart: heart, prop: prop
  };
})(typeof window !== 'undefined' ? window : globalThis);
