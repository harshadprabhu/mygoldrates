"""Re-measure the beacon against the live site.

Not a unit test - it drives a real browser against production and
writes real rows. Run it by hand when the tracker changes:

    python3 tests/beacon_bounce.py <spki-list-file> /some-path

It reports, for a visitor who leaves after N milliseconds, whether the
pageview was sent at all and whether it completed. The numbers quoted
in tests/test_analytics_beacon.py came from this.
"""
import sys
from playwright.sync_api import sync_playwright

spki = open(sys.argv[1]).read().strip()
BASE = "https://mygoldrates.com"
PAGE = sys.argv[2]
# How long the "visitor" stays before navigating away.
DWELLS = [0, 50, 100, 200, 400, 800, 1600, 3000]

with sync_playwright() as p:
    b = p.chromium.launch(
        executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
        args=["--ignore-certificate-errors-spki-list=" + spki])
    print(f'{"dwell ms":>9}  {"beacon sent":>11}  {"completed":>9}  result')
    for ms in DWELLS:
        ctx = b.new_context()
        # Throttle nothing; this is a fast datacentre link. A real Indian
        # mobile connection makes every number here worse, not better.
        pg = ctx.new_page()
        sent, done = [], []
        pg.on("request", lambda r: sent.append(r.url)
              if "/rest/v1/page_views" in r.url else None)
        pg.on("response", lambda r: done.append(r.status)
              if "/rest/v1/page_views" in r.url else None)
        pg.on("requestfailed", lambda r: done.append("ABORTED")
              if "/rest/v1/page_views" in r.url else None)
        try:
            pg.goto(BASE + PAGE,
                    wait_until="commit", timeout=45000)
            pg.wait_for_timeout(ms)
            pg.goto("about:blank", timeout=20000)   # visitor leaves
            pg.wait_for_timeout(1200)
        except Exception as e:
            pass
        ok = [d for d in done if d == 201]
        verdict = ("counted" if ok else
                   "LOST" if sent else "never even fired")
        print(f'{ms:>9}  {len(sent):>11}  {str(done):>9}  {verdict}')
        ctx.close()
    b.close()
