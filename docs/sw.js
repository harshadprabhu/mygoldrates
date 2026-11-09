/* MyGoldRates service worker (pwa.py). No caching: rates are always fetched fresh. */
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
var OFFLINE = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<title>Offline - MyGoldRates</title><body style="margin:0;padding:28px 20px;font:16px/1.5 system-ui,sans-serif;background:#0b0a08;color:#efe4c8">' +
  '<h1 style="font-size:22px">You are offline</h1><p>Gold rates change through the day, so MyGoldRates needs a connection to show ' +
  'today\'s figures. Connect and try again.</p><button onclick="location.reload()" style="padding:10px 18px;border-radius:999px;' +
  'border:0;background:#d4af37;color:#16130d;font-weight:600">Try again</button>';
self.addEventListener('fetch', function (e) {
  if (e.request.mode !== 'navigate') return;
  e.respondWith(fetch(e.request).catch(function () {
    return new Response(OFFLINE, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
  }));
});
self.addEventListener('push', function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { title: 'Gold rate today', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'Gold rate today', {
    body: d.body || '', icon: '/icon-192.png', badge: '/icon-96.png', tag: d.tag || 'morning-rate',
    renotify: true, data: { url: d.url || '/?src=push' } }));
});
self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (ws) {
    for (var i = 0; i < ws.length; i++) if ('focus' in ws[i]) { ws[i].navigate(url); return ws[i].focus(); }
    return self.clients.openWindow(url);
  }));
});
