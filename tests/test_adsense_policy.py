"""AdSense policy (owner, 18 Nov 2026): no ad script on pages without
publisher content (404, forms) or on noindexed near-copy pages."""
import os
import re

SRC = open(os.path.join(os.path.dirname(__file__), "..", "generate_site.py"), encoding="utf-8").read()


def test_ads_are_stripped_from_pages_policy_forbids():
    i = SRC.index("def strip_ads_where_not_allowed():")
    body = SRC[i:i + 2500]
    for p in ("docs/404.html", "docs/inquiry.html", "docs/contact.html"):
        assert p in body
    assert 'content="noindex' in body
    assert "strip_ads_where_not_allowed()" in SRC[i + 100:]


def test_the_loader_pattern_matches_the_real_tag():
    i = SRC.index("loader = re.compile(r'"); j = SRC.index("')", i)
    pat = re.compile(SRC[i + len("loader = re.compile(r'"):j])
    tag = ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
           '?client=ca-pub-1893036481180379" crossorigin="anonymous"></script>\n')
    assert pat.sub("", "<head>" + tag + "</head>") == "<head></head>"
