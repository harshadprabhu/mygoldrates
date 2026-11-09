"""Install as an app and the morning notification (owner, 9 Nov 2026)."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import push_send as P  # noqa: E402
import pwa  # noqa: E402

KB = {"med": {"24K": 14461.0, "22K": 13255.92}, "hist": [["2026-11-08", 14356.36], ["2026-11-09", 14460.0]],
      "cities": [{"n": "Pune", "st": "Maharashtra", "u": "/gold-rate-today-in-pune"}],
      "brands": [{"n": "Kalyan Jewellers", "r24": 14400.0, "nat": True},
                 {"n": "Mahesh Jewellers", "r24": 14280.0, "nat": False, "st": ["Maharashtra"]},
                 {"n": "GRT Jewellers", "r24": 14100.0, "nat": False, "st": ["Tamil Nadu"]}]}


def test_message_names_the_cheapest_jeweller_that_serves_the_city():
    m = P.message(KB, "Pune")
    assert m["title"] == "Gold rate today: 22K ₹13,256/g ▲ ₹95"
    assert m["body"].startswith("Cheapest in Pune: Mahesh Jewellers ₹13,090/g")
    assert m["url"] == "https://mygoldrates.com/gold-rate-today-in-pune?src=push"


def test_message_without_a_city_uses_national_chains_only():
    m = P.message(KB, "")
    assert "Kalyan Jewellers" in m["body"] and "GRT" not in m["body"]
    assert m["url"] == "https://mygoldrates.com/?src=push"


def test_signing_key_is_made_once_and_kept_private():
    src = open("push_send.py", encoding="utf-8").read()
    assert 'KEY = "webpush_vapid"' in src and "cache_put(KEY" in src
    assert "Vapid02" in src                      # RFC 8292 header, which Apple requires
    assert "(404, 410)" in src                   # expired subscriptions are removed


def test_service_worker_never_caches_rates():
    assert "caches." not in pwa.SW_JS            # latest data only (owner)
    assert "showNotification" in pwa.SW_JS and "openWindow" in pwa.SW_JS
    assert pwa.MANIFEST["display"] == "standalone" and pwa.MANIFEST["start_url"].startswith("/")
    assert {i["sizes"] for i in pwa.MANIFEST["icons"]} == {"192x192", "512x512"}


def test_permission_is_asked_only_on_a_tap():
    js = pwa.CLIENT_JS
    i = js.index("Notification.requestPermission")
    assert js.rfind("function on()", 0, i) > -1            # inside the click handler only
    assert js.count("Notification.requestPermission") == 1
    assert "Add to Home Screen" in js and "Chrome or Safari" in js


def test_pages_carry_the_manifest_and_script():
    app = open("pulse_app.html", encoding="utf-8").read()
    assert '<link rel="manifest" href="/manifest.webmanifest">' in app and '<script src="/pwa.js" defer>' in app
    assert app.count('class="mgr-push"') == 2
    gs = open("generate_site.py", encoding="utf-8").read()
    assert gs.count('<script src="$site_url/pwa.js" defer></script>') >= 2


def test_worker_accepts_only_real_push_services():
    js = """import('./cf-worker-jd/worker.js').then(m => console.log(JSON.stringify([
      m.pushCheck({sub: {endpoint: 'https://fcm.googleapis.com/fcm/send/x'}}),
      m.pushCheck({sub: {endpoint: 'https://web.push.apple.com/QA'}}),
      m.pushCheck({sub: {endpoint: 'https://updates.push.services.mozilla.com/wpush/v2/x'}}),
      m.pushCheck({sub: {endpoint: 'https://evil.example/x'}}),
      m.pushCheck({sub: {endpoint: 'http://fcm.googleapis.com/x'}})])))"""
    out = json.loads(subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True,
                                    text=True, check=True).stdout)
    assert out[:3] == ["https://fcm.googleapis.com/fcm/send/x", "https://web.push.apple.com/QA",
                       "https://updates.push.services.mozilla.com/wpush/v2/x"]
    assert out[3:] == [None, None]
