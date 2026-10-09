"""The pageview beacon: what it must do, and why.

The numbers in these docstrings were measured against the live site with a
real headless browser, not estimated. The harness is kept in
tests/beacon_bounce.py so they can be re-measured.

The short version of what was wrong: a visitor who landed and left inside
about 1.6 seconds was never counted. On a site whose whole purpose is
"what is the gold rate today", that is the single commonest visit there is.
Two independent causes, both fixed here:

  * the beacon used a plain fetch(), which the browser cancels on unload;
  * on every page except the homepage it rode in a deferred 11.6KB bundle,
    so it could not fire until an extra round trip had finished.
"""
import re

import generate_site as gs


def snippet():
    return gs.analytics_snippet("https://x.supabase.co", "anon-key-123")


# ─── the two measured fixes ─────────────────────────────────────────────

def test_the_beacon_survives_the_page_being_closed():
    """Six identical fast-bounce loads, same conditions: a plain fetch landed
    3 of 6 rows, keepalive landed 6 of 6. Without this flag the browser
    cancels the request when the document unloads, which is exactly when a
    rate-checker leaves."""
    assert "keepalive:true" in snippet()


def test_the_beacon_is_inline_and_not_in_the_deferred_bundle():
    """Measured on a live city page: with the beacon in deferred signup.js,
    a visitor who left within 800ms sent nothing at all. The homepage, whose
    copy was already inline, managed 200ms."""
    assert "page_views" not in gs.SIGNUP_JS
    assert "page_views" not in gs.CLICK_JS
    assert 'post("page_views"' not in open("generate_site.py").read(), (
        "a second hand-written copy of the beacon has reappeared")


def test_every_page_template_carries_the_beacon_in_its_head():
    src = open("generate_site.py").read()
    for name in ("TEMPLATE", "INQUIRY_TEMPLATE", "PAGE_TEMPLATE",
                 "CONTENT_TEMPLATE"):
        m = re.search(rf'^{name} = Template\("""', src, re.M)
        assert m, f"{name} not found"
        head = src[m.end():src.index("</head>", m.end()) + 7]
        assert "$analytics_js</head>" in head, (
            f"{name} does not inject the beacon before </head>")


# ─── it must fire exactly once ──────────────────────────────────────────

def test_the_beacon_fires_exactly_once_per_page():
    """Two copies on one page doubles every number on the dashboard. The
    head snippet owns the pageview; signup.js and the app bundle own only
    clicks, and read the sender back off window rather than rebuilding it."""
    assert snippet().count('send("page_views"') == 1
    assert "window.GR_TRACK=send" in snippet()
    assert "window.GR_TRACK" in gs.CLICK_JS
    assert "window.GR_SID" in gs.CLICK_JS


def test_the_click_bundle_does_not_build_its_own_session_id():
    """A second session-id generator would split one visitor into two."""
    assert "crypto.randomUUID" not in gs.CLICK_JS
    assert "gr_sid" not in gs.CLICK_JS


def test_the_app_does_not_get_the_signup_bundle():
    """pulse_app runs its own Google Identity Services flow; the signup
    bundle's gate/modal/OTP code collides with it. It needs CLICK_JS only."""
    src = open("generate_site.py").read()
    i = src.index("analytics_js = (")
    block = src[i:i + 900]
    assert "CLICK_JS" in block
    assert "+ SIGNUP_JS +" not in block


# ─── failure modes that hid the problem ─────────────────────────────────

def test_a_failed_insert_cannot_throw_away_the_row_silently():
    """A column the live DB has not been migrated for yet comes back as an
    HTTP error, not a thrown one, so fetch() resolves and a bare .catch()
    would drop the row without a trace. Retry once without the newer field."""
    s = snippet()
    assert "!r.ok&&!retried" in s
    assert 'row.host!==undefined' in s


def test_the_beacon_never_breaks_the_page():
    """It runs in the document head, before anything is rendered. If it
    throws there, the page dies with it."""
    s = snippet()
    assert s.count("try{") >= 2 and "catch(e){}" in s
    assert "if(!SB||!KEY)return;" in s


def test_the_jd_page_is_tracked_too():
    """It shipped with no beacon at all, so every visit to the page that is
    supposed to sell the subscription went unrecorded."""
    import jd_page
    assert hasattr(jd_page, "_analytics")
    assert "{analytics}" in open("jd_page.py").read()
