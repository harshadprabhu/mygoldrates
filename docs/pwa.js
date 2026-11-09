(function () {
  var VAPID = 'BHx69Cj7xRy04bxYCe6oft_CEXsL_i25a7r7PG0NFoJdV-tV3Tga3FAoGEKjeMcKJRrKMFLEZKhTAsKzajgOuOo', API = 'https://mygoldrates-jd-api.harshads-priority.workers.dev';
  var nav = navigator, ua = nav.userAgent || '';
  if ('serviceWorker' in nav) nav.serviceWorker.register('/sw.js').catch(function () {});
  var ios = /iPhone|iPad|iPod/.test(ua) || (nav.platform === 'MacIntel' && nav.maxTouchPoints > 1);
  var standalone = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || nav.standalone === true;
  var inApp = /Instagram|FBAN|FBAV|FB_IAB|WhatsApp|Line\/|Snapchat/.test(ua);
  var installEvt = null, busy = false;
  function track(n) { try { if (window.GR_TRACK) window.GR_TRACK('click_events', { page: location.pathname, target: 'pwa:' + n, session_id: window.GR_SID || '' }); } catch (_) {} }
  window.addEventListener('beforeinstallprompt', function (e) { e.preventDefault(); installEvt = e; paint(); });
  window.addEventListener('appinstalled', function () { installEvt = null; track('app_installed'); paint(); });
  function pushOK() { return VAPID.length > 40 && 'serviceWorker' in nav && 'PushManager' in window && 'Notification' in window; }
  function key(s) {
    var p = '='.repeat((4 - s.length % 4) % 4), b = atob((s + p).replace(/-/g, '+').replace(/_/g, '/'));
    var a = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return a;
  }
  function city() {
    try { return localStorage.getItem('mgr_city') || localStorage.getItem('sona_home') || ''; } catch (_) { return ''; }
  }
  function state(cb) {
    if (!pushOK()) return cb('none');
    if (Notification.permission === 'denied') return cb('denied');
    nav.serviceWorker.ready.then(function (r) { return r.pushManager.getSubscription(); })
      .then(function (s) { cb(s ? 'on' : 'off'); }).catch(function () { cb('off'); });
  }
  function post(path, body) {
    return fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { if (!r.ok) throw new Error('save ' + r.status); return r; });
  }
  function on() {
    busy = true; paint();
    Notification.requestPermission().then(function (p) {
      if (p !== 'granted') throw new Error('perm');
      return nav.serviceWorker.ready;
    }).then(function (r) {
      return r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key(VAPID) }).then(function (s) {
        return post('/push/subscribe', { sub: s.toJSON(), city: city() }).then(function () {
          track('push_on');
          return r.showNotification('You are set', { body: 'Every morning: today’s gold rate and the cheapest jeweller' +
            (city() ? ' in ' + city() : '') + '.', icon: '/icon-192.png', tag: 'morning-rate' });
        });
      });
    }).catch(function (e) { track(e && e.message === 'perm' ? 'push_refused' : 'push_failed'); })
      .then(function () { busy = false; paint(); });
  }
  function off() {
    busy = true; paint();
    nav.serviceWorker.ready.then(function (r) { return r.pushManager.getSubscription(); }).then(function (s) {
      if (!s) return;
      var ep = s.endpoint;
      return s.unsubscribe().then(function () { return post('/push/unsubscribe', { endpoint: ep }).catch(function () {}); });
    }).catch(function () {}).then(function () { track('push_off'); busy = false; paint(); });
  }
  var B = 'display:inline-flex;align-items:center;gap:8px;padding:11px 18px;border-radius:999px;border:1px solid rgba(212,175,55,.45);' +
          'background:linear-gradient(135deg,#e8c766,#c9a23c);color:#16130d;font:600 14px/1.2 system-ui,sans-serif;cursor:pointer;margin:4px 6px 4px 0';
  var B2 = B.replace(/background:[^;]+;color:#16130d/, 'background:transparent;color:inherit');
  var T = 'font:13.5px/1.5 system-ui,sans-serif;opacity:.85;margin:6px 0';
  function paint() {
    var boxes = document.querySelectorAll('.mgr-push');
    if (!boxes.length) return;
    state(function (st) {
      var h = '';
      if (inApp) h = '<p style="' + T + '">🔔 To get the gold rate on your phone every morning, open <b>mygoldrates.com</b> in Chrome or Safari.</p>';
      else if (ios && !standalone && !pushOK()) {
        h = '<p style="' + T + '">🔔 <b>Morning gold rate on your iPhone:</b> tap <b>Share</b> ⬆︎ then <b>Add to Home Screen</b>, ' +
            'open MyGoldRates from your home screen and tap the bell there.</p>';
      } else {
        if (st === 'off') h += '<button type="button" data-a="on" style="' + B + '">🔔 ' + (busy ? 'One moment…' : 'Get today’s gold rate every morning') + '</button>';
        if (st === 'on') h += '<p style="' + T + '">✅ Morning gold rate is on for this ' + (ios ? 'iPhone' : 'device') +
          '. <button type="button" data-a="off" style="background:none;border:0;color:inherit;text-decoration:underline;cursor:pointer;font:inherit">Turn off</button></p>';
        if (st === 'denied') h += '<p style="' + T + '">Notifications are blocked for mygoldrates.com in your browser settings - allow them there to get the morning rate.</p>';
        if (installEvt && !standalone) h += '<button type="button" data-a="install" style="' + B2 + '">📲 Install the MyGoldRates app</button>';
      }
      for (var i = 0; i < boxes.length; i++) boxes[i].innerHTML = h;
    });
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.mgr-push [data-a]');
    if (!b || busy) return;
    var a = b.getAttribute('data-a');
    if (a === 'on') on(); else if (a === 'off') off();
    else if (a === 'install' && installEvt) { installEvt.prompt(); installEvt.userChoice.then(function () { installEvt = null; paint(); }); }
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', paint); else paint();
})();
