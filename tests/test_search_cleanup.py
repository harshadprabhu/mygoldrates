"""The 2026-10-20 search clean-up (agreed with the owner).

City and state pages: 28 places with content of their own are indexed and in
the sitemaps; the rest stay live with noindex and out of the sitemaps.
Daily and recap pages: one national daily page a day, indexed for 3 days;
per-city daily copies and per-day recaps are retired, every retired address
301s to its replacement, and a month-by-month history replaces the recaps.
"""
import ast
import json
import os
import re

import pytest

DOCS = "docs"
SRC = open("generate_site.py", encoding="utf-8").read()
built = pytest.mark.skipif(not os.path.isdir(f"{DOCS}/gold-rate-history"),
                           reason="site not built with the clean-up yet")


def _const(name):
    i = SRC.index(f"{name} = ")
    j = SRC.index("\n}\n" if SRC[i:].split("=", 1)[1].lstrip().startswith("{") else "]\n", i)
    return ast.literal_eval(SRC[i + len(name) + 3:j + 2].strip())


def test_indexed_places_are_real_places():
    places, locs = _const("INDEXED_PLACES"), _const("LOCATIONS")
    assert len(places) == 28
    assert places <= set(locs)


def _locs(path):
    return re.findall(r"<loc>([^<]+)</loc>", open(path, encoding="utf-8").read())


@built
def test_city_pages_indexed_or_noindexed_as_agreed():
    places, locs = _const("INDEXED_PLACES"), _const("LOCATIONS")
    for nm in locs:
        sl = re.sub(r"[^a-z0-9]+", "-", nm.lower()).strip("-")
        h = open(f"{DOCS}/gold-rate-today-in-{sl}.html", encoding="utf-8").read()
        noindex = 'name="robots" content="noindex' in h
        assert noindex == (nm not in places), nm


@built
def test_no_noindexed_or_missing_page_is_in_a_sitemap():
    for sm in ("sitemap.xml", "sitemap_main.xml", "sitemap_cities.xml",
               "sitemap_daily.xml", "sitemap_news.xml"):
        for u in _locs(f"{DOCS}/{sm}"):
            path = u.replace("https://mygoldrates.com", "").rstrip("/") or "/index"
            f = f"{DOCS}{path}.html"
            assert os.path.exists(f), f"{sm} lists {u}, which has no page"
            assert 'content="noindex' not in open(f, encoding="utf-8").read(), \
                f"{sm} lists {u}, which is noindex"


@built
def test_city_sitemap_holds_exactly_the_indexed_places():
    assert len(_locs(f"{DOCS}/sitemap_cities.xml")) == len(_const("INDEXED_PLACES"))


@built
def test_retired_pages_are_gone_and_redirect_to_real_pages():
    r = json.load(open(f"{DOCS}/retired-urls.json"))["redirects"]
    assert len(r) >= 440
    for src, dst in r.items():
        assert not os.path.exists(f"{DOCS}{src}.html"), f"{src} still on disk"
        assert dst == "/" or os.path.exists(f"{DOCS}{dst}.html"), f"{src} -> missing {dst}"
    red = open(f"{DOCS}/_redirects").read()
    for src, dst in list(r.items())[:50]:
        assert f"{src}    {dst}    301" in red


@built
def test_only_national_daily_pages_remain_and_no_recaps():
    daily = os.listdir(f"{DOCS}/news/daily")
    assert daily and all(f.startswith("gold-rate-india-") for f in daily)
    assert len(daily) <= 5
    assert not os.path.isdir(f"{DOCS}/news/recap") or not os.listdir(f"{DOCS}/news/recap")


@built
def test_redirect_rules_stay_under_the_cloudflare_limit():
    rules = [l for l in open(f"{DOCS}/_redirects").read().splitlines()
             if l.strip() and not l.startswith("#")]
    assert len(rules) < 1800, "close to Cloudflare Pages' 2,000 static redirect limit"


@built
def test_history_pages_cover_every_month_and_are_listed():
    months = os.listdir(f"{DOCS}/gold-rate-history")
    assert "october-2026.html" in months and "july-2026.html" in months
    main = " ".join(_locs(f"{DOCS}/sitemap_main.xml"))
    for m in months:
        assert f"/gold-rate-history/{m[:-5]}" in main
    h = open(f"{DOCS}/gold-rate-history/october-2026.html", encoding="utf-8").read()
    assert '"@type": "Dataset"' in h and "<table" in h
