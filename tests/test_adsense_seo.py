"""What AdSense review and Google search need from the site.

Each test pins a problem that was measured on the live site in October 2026,
not a best practice in the abstract. The docstrings say what was found.
"""
import json
import os
import re

import pytest

import generate_site as gs

DOCS = "docs"
built = pytest.mark.skipif(not os.path.isdir(DOCS), reason="site not built")


def _read(path):
    return open(path, encoding="utf-8").read()


# ─── homepage navigation ────────────────────────────────────────────────

@built
def test_homepage_links_to_policy_and_main_pages():
    """The homepage linked 14 city pages and nothing else: no Privacy Policy,
    About, Contact or Terms, and no route to /compare, /calculators or /news
    - Search Console reported /calculators and /news as unknown to Google.
    AdSense reviewers look for policy pages and navigation from here."""
    h = _read(f"{DOCS}/index.html")
    for path in ("privacy", "about", "contact", "terms", "compare",
                 "calculators", "news", "making-charges-comparison"):
        assert re.search(rf'href="(?:https://mygoldrates\.com)?/{path}"', h), (
            f"homepage does not link /{path}")


@built
def test_phone_view_carries_the_links_too():
    """Phones get the app view; the desktop layout and its footer are
    display:none below 900px, and Google indexes the phone version."""
    h = _read(f"{DOCS}/index.html")
    app = h[h.index('id="v-rates"'):h.index("<!-- /v-rates -->")]
    assert "/privacy" in app and "/about" in app and "/compare" in app


def test_homepage_template_markers_present():
    src = _read("pulse_app.html")
    assert "<!--SITE_LINKS_APP-->" in src and "<!--SITE_LINKS_SITE-->" in src


# ─── intrusive popup ────────────────────────────────────────────────────

def test_subscribe_popup_waits_for_engagement():
    """It opened within a second of landing and covered 100% of a phone
    screen at 1, 3, 6, 10 and 15 seconds on the live city pages - Google's
    intrusive-interstitial pattern, on the pages people arrive at from
    search."""
    src = _read("generate_site.py")
    i = src.index("function maybeShowSubscribePopup(){")
    body = src[i:i + 3000]
    assert "whenEngaged(function(){" in body
    assert "window.scrollY/max>=0.5" in src


# ─── city pages are about their place ───────────────────────────────────

def test_every_place_has_a_state():
    missing = [p for p in gs.LOCATIONS if p not in gs.PLACE_STATE]
    assert not missing, missing


@built
def test_city_pages_lead_with_local_jewellers():
    """City pages were /compare with the name swapped: 97-100% identical."""
    h = _read(f"{DOCS}/gold-rate-today-in-pune.html")
    assert 'class="seo local-board"' in h
    assert "Maharashtra" in h
    # a Maharashtra regional chain is listed for Pune...
    board = re.search(r'local-board.*?</section>', h, re.S).group(0)
    assert re.search(r"Regional", board)


@built
def test_city_pages_do_not_repeat_the_national_faq_or_its_markup():
    """Google forbids FAQPage markup for questions not on the page, and the
    India FAQ is national content - it stays on /compare."""
    h = _read(f"{DOCS}/gold-rate-today-in-pune.html")
    assert 'id="faqh"' not in h
    types = []
    for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        d = json.loads(blk)
        items = d if isinstance(d, list) else d.get("@graph", [d])
        types += [x.get("@type") for x in items]
    assert "FAQPage" not in types and "Dataset" not in types
    assert "BreadcrumbList" in types
    c = _read(f"{DOCS}/compare.html")
    assert 'id="faqh"' in c and '"FAQPage"' in c


@built
def test_local_board_does_not_overclaim():
    """A national chain listed here is not a claim it has a shop in this
    city, and a quiet day is not "no regional chains here"."""
    h = _read(f"{DOCS}/gold-rate-today-in-kerala.html")
    board = re.search(r'local-board.*?</section>', h, re.S).group(0)
    assert "Lowest 22K among these jewellers today" in board
    assert "We do not track a regional chain in Kerala" not in board


# ─── page weight and mobile ─────────────────────────────────────────────

def test_homepage_background_is_not_the_two_megabyte_png():
    """bg.png was 2.1MB, ~80% of the homepage's own download."""
    src = _read("pulse_app.html")
    assert "url('bg.png')" not in src and "url('/bg.png')" not in src
    assert "/bg.webp" in src
    assert os.path.getsize(f"{DOCS}/bg.webp") < 300_000


def test_pinch_zoom_is_allowed():
    src = _read("pulse_app.html")
    assert "user-scalable=no" not in src and "maximum-scale=1" not in src


# ─── titles ─────────────────────────────────────────────────────────────

def test_daily_reports_do_not_reuse_the_city_page_title():
    """Up to five pages per city shared one title and competed for one
    search."""
    src = _read("generate_site.py")
    i = src.index("    def gen_daily(place, place_slug):")
    body = src[i:i + 4000]
    assert "Daily Report" in body
    assert 'f"Gold Rate Today {where_in} ({display_date})' not in body
