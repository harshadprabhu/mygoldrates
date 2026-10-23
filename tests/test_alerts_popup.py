"""The daily-alerts popup (homepage/city pages and every other page)."""
import generate_site as gs

APP = open("pulse_app.html", encoding="utf-8").read()
POP = gs.ALERTS_POP_JS


def test_subscribers_are_never_asked():
    """Asking someone who already subscribed only pulls them off the page."""
    assert "if(lsGet(SP_SUB)==='1')return false;" in APP
    assert "g('gr_sub')==='1'" in POP


def test_email_links_mark_the_reader_as_a_subscriber():
    """Everyone who clicks through from the daily email is a subscriber."""
    src = open("send_alerts.py", encoding="utf-8").read()
    assert 'href="{SITE_URL}/"' not in src
    assert src.count('{SITE_URL}/?from=alert') >= 2
    for code in (APP, POP):
        assert "get('from')==='alert'" in code and "replaceState" in code


def test_already_subscribed_link_remembers_it():
    assert "lsSet(SP_SUB,'1');closeSubPop(true)" in APP
    assert "s('gr_sub','1');close();" in POP


def test_only_the_small_x_closes_it():
    """No tap-outside close and no "Maybe later" button; the x stays."""
    assert "e.target===subPop" not in APP and 'id="spLater"' not in APP
    assert "e.target===el" not in POP and "Maybe later</button>" not in POP
    assert 'id="spClose"' in APP and 'class="x"' in POP


def test_desktop_homepage_can_see_the_popup():
    """Its markup sits inside the phone layout, hidden at 900px and up."""
    assert "document.body.appendChild(subPop)" in APP
