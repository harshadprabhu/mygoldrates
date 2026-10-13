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
    for path in ("privacy", "about", "contact", "terms",
                 "calculators", "news", "making-charges-comparison"):
        assert re.search(rf'href="(?:https://mygoldrates\.com)?/{path}"', h), (
            f"homepage does not link /{path}")


@built
def test_phone_view_carries_the_links_too():
    """Phones get the app view; the desktop layout and its footer are
    display:none below 900px, and Google indexes the phone version."""
    h = _read(f"{DOCS}/index.html")
    app = h[h.index('id="v-rates"'):h.index("<!-- /v-rates -->")]
    assert "/privacy" in app and "/about" in app and "/calculators" in app


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
    # /compare is gone (it redirects to /); the homepage carries the FAQ
    # and its markup now.
    assert not os.path.exists(f"{DOCS}/compare.html")
    assert '"FAQPage"' in _read(f"{DOCS}/index.html")


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


# ─── city pages use the new design ──────────────────────────────────────

@built
@pytest.mark.parametrize("slug,place", [("chennai", "Chennai"), ("agra", "Agra"),
                                        ("maharashtra", "Maharashtra")])
def test_city_pages_are_the_new_design_with_their_own_identity(slug, place):
    """City pages were rendered from the old comparison-page template, so a
    visitor arriving from search for a place saw an older site than the
    homepage. They are built from the homepage now."""
    h = _read(f"{DOCS}/gold-rate-today-in-{slug}.html")
    assert 'id="v-rates"' in h, "not the new design"
    assert 'class="board-rates"' not in h, "still the old template"
    assert f"<title>Gold Rate Today in {place} (" in h
    assert f'rel="canonical" href="https://mygoldrates.com/gold-rate-today-in-{slug}"' in h
    assert f'og:url" content="https://mygoldrates.com/gold-rate-today-in-{slug}"' in h
    # visible on phones, not screen-reader only
    assert re.search(rf'<h1 style="[^"]+">Gold Rate Today in {place}<span', h)
    assert 'class="sr-only">Gold Rate Today in India' not in h
    assert "Gold Rate Today in India" not in re.search(r"<title>[^<]*", h).group(0)
    # the details popup ships on every city page
    assert 'id="subPop"' in h
    # local section in both layouts
    assert h.count('class="seo local-board"') == 2


@built
def test_city_page_structured_data_describes_the_city_not_the_homepage():
    h = _read(f"{DOCS}/gold-rate-today-in-chennai.html")
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)
    assert len(blocks) == 1
    items = json.loads(blocks[0])
    page = next(x for x in items if x["@type"] == "WebPage")
    assert page["url"].endswith("/gold-rate-today-in-chennai")
    assert {x["@type"] for x in items} == {"WebSite", "Organization", "WebPage",
                                          "BreadcrumbList"}


def test_city_section_text_is_coloured_for_the_dark_design():
    """The new design sets text colour per element, so the local section's
    write-up rendered dark-on-dark until it was given a colour."""
    src = _read("generate_site.py")
    assert ".city-local,.city-local h2,.city-local h3,.city-local p," in src



# ─── no old design anywhere ─────────────────────────────────────────────

@built
def test_no_public_page_is_in_the_old_design():
    """Every page is either the app (home + city pages) or the new-design
    page shell. The only exception is the private analytics dashboard,
    which no visitor reaches."""
    old_markers = ('<header class="top">', 'id="navdrawer"', 'class="navtog"',
                   "family=Marcellus", 'class="board-rates"', 'class="brand-tag"')
    bad = []
    for root, _, files in os.walk(DOCS):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(root, f)
            if path == f"{DOCS}/analytics.html":
                continue
            h = _read(path)
            new = 'id="v-rates"' in h or 'class="nd-nav"' in h
            if not new or any(m in h for m in old_markers):
                bad.append(path)
    assert not bad, f"{len(bad)} page(s) in the old design, e.g. {bad[:5]}"


def test_there_is_no_old_design_fallback():
    """The old design used to come back whenever pulse_app.html was missing,
    which is how an old page reaches production unnoticed."""
    src = _read("generate_site.py")
    assert "TEMPLATE = Template(" not in src.replace("PAGE_TEMPLATE", "").replace(
        "CONTENT_TEMPLATE", "").replace("INQUIRY_TEMPLATE", "").replace("UNSUB_TEMPLATE", "")
    assert "write_classic_city_pages" not in src
    assert "refusing to build the" in src and "without the new design" in src
    assert "NAV = f" not in src


@built
def test_compare_redirects_to_the_homepage():
    rules = _read(f"{DOCS}/_redirects")
    for src in ("/compare", "/compare/", "/compare.html"):
        assert re.search(rf"^{re.escape(src)}\s+/\s+301$", rules, re.M), src


@built
@pytest.mark.parametrize("page", ["index.html", "gold-rate-today-in-chennai.html",
                                  "about.html", "calculators.html",
                                  "jewellers-digest.html", "404.html"])
def test_logo_mark_is_in_the_header(page):
    """The gold bars-and-arrow mark was in the old header and was lost when
    pages moved to the new design's wordmark-only header."""
    h = _read(f"{DOCS}/{page}")
    assert 'class="brand-mark"' in h
