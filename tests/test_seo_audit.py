"""Findings of the SEO crawl of 9 Nov 2026, kept fixed."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SRC = open("generate_site.py", encoding="utf-8").read()


def _fn(name, nxt):
    ns = {}
    exec(SRC[SRC.index("TITLE_MAX, DESC_MAX"):SRC.index(nxt)], ns)
    return ns[name]


def test_titles_fit_search_results():
    fit = _fn("fit_title", "def inr(v, dec=0):")
    long = "Gold Making Charges Compared: 19 Jewellers by Ring, Bangle, Earrings | MyGoldRates"
    assert fit(long) == "Gold Making Charges Compared: 19 Jewellers by Ring, Bangle, Earrings"
    short = "Gold Rate Today in Pune (9 Nov): 24K, 22K, 18K | MyGoldRates"
    assert fit(short) == short


def test_descriptions_fit_search_results():
    fit = _fn("fit_desc", "def inr(v, dec=0):")
    d = ("Gold rate today, 9 November 2026: 24K Rs 14,389/g. Each of 36 jewellers' own rate - Tanishq, "
         "Kalyan, Malabar and more - with the change from yesterday and the cheapest today.")
    out = fit(d)
    assert len(out) <= 160 and (out.endswith(".") or out.endswith("\u2026"))
    assert fit("short one.") == "short one."


def test_no_half_built_addresses_in_page_scripts():
    """Crawlers read '/gold-rate-today-in-'+w.u+' in a script as an address
    and report it as a 404."""
    for f in ("pulse_app.html", "assistant.js", "outreach_pages.py"):
        s = open(f, encoding="utf-8").read()
        # a literal path glued to a variable (the variable holding a whole
        # address is fine)
        assert not re.search(r"""href=\\?["']/[a-z0-9/-]+['"]\s*\+""", s), f
        assert not re.search(r"""['"]/[a-z0-9-]+-['"]\s*\+""", s), f


def test_coin_page_has_one_h1():
    import coin_section as cs
    rows = [{"brand": "A", "pct": 3.0, "n": 4, "from_price": False, "gf": 1.0, "rate": 14000.0,
             "per_g": 14900.0, "prices": {1: 14900, 5: 74500, 10: 149000}, "premium": 0.06}]
    assert cs.coin_html(rows, "2026-11-09", "https://mygoldrates.com").count("<h1>") == 1


def test_email_addresses_are_kept_from_cloudflare_obfuscation():
    import outreach_pages
    src = open(outreach_pages.__file__, encoding="utf-8").read()
    assert "<!--email_off--><a href=\"mailto:" in src


def test_homepage_city_lists_come_from_the_indexed_cities():
    assert "if p in INDEXED_PLACES and is_city(p))" in SRC
    i = SRC.index("<h3>Gold rate by state</h3>")
    assert "if p in INDEXED_PLACES" in SRC[i:i + 300]
    assert "/jeweller-badge" in SRC[SRC.index("def site_links_html"):SRC.index("def nd_header_html")]


def test_sitemap_dates_ignore_volatile_bits():
    import re as _re
    i = SRC.index("    _VOLATILE = re.compile(")
    j = SRC.index(", re.S)", i) + len(", re.S)")
    ns = {"re": _re}
    exec(SRC[i:j].strip(), ns)
    v = ns["_VOLATILE"]
    a = 'rate for 37 major\n jewellers <script src="a.js?v=9fec98e2">'
    b = 'rate for 36 major\n jewellers <script src="a.js?v=37a0abcf">'
    assert v.sub("", a) == v.sub("", b)
