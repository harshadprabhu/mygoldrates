"""Every internal link in the built site must point at something that exists.

This test exists because of a bug that ran for weeks in plain sight. The
homepage linked its city pages as href="city/pune/" - relative, and a path
that was never built. Cloudflare Pages, with no 404.html in the project,
answered unmatched paths with index.html and a 200, so the click looked like
it had done nothing rather than failing. The visitor clicked the next city,
the browser resolved the same relative href against the bad path, and the
analytics filled up with chains:

    /city/jaipur/city/pune/city/visakhapatnam/city/coimbatore/...

Every one of those was a real person who wanted a city page and never got
one. Nothing was red: the deploy was green, the pages were there, and the
server said 200 to everything.

The checker below is the thing that would have caught it in one run, so it
runs on every build now. It also found favicon-32.png, referenced by two
pages and never generated, which the same fallback had been answering with
HTML labelled as a PNG.
"""
import os
import re
from urllib.parse import urlsplit, urljoin

import pytest

DOCS = "docs"
SITE = "mygoldrates.com"

# Hrefs assembled by JavaScript at runtime: href="/'+it.url+'". There is
# nothing to resolve at build time and nothing to check.
DYNAMIC = re.compile(r"""\+|\$\{|\{\{""")


def _built_paths():
    out = set()
    for root, _, files in os.walk(DOCS):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), DOCS)
            out.add("/" + rel.replace(os.sep, "/"))
    return out


def _resolves(target, paths):
    """Cloudflare Pages serves /foo from foo.html and /foo/ from foo/index.html."""
    return (target in paths
            or target + ".html" in paths
            or target.rstrip("/") + "/index.html" in paths
            or (target.endswith("/") and target + "index.html" in paths))


def _internal_targets():
    """(source page, href, resolved absolute path) for every internal link."""
    for root, _, files in os.walk(DOCS):
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            page = os.path.join(root, f)
            rel = "/" + os.path.relpath(page, DOCS).replace(os.sep, "/")
            base = (rel[:-len("index.html")] if rel.endswith("/index.html")
                    else rel)
            html = open(page, encoding="utf-8", errors="replace").read()
            for m in re.finditer(r'(?:href|src)="([^"]+)"', html):
                h = m.group(1).strip()
                if not h or DYNAMIC.search(h):
                    continue
                if h.startswith(("mailto:", "tel:", "javascript:", "#",
                                 "data:", "//")):
                    continue
                sp = urlsplit(h)
                if sp.scheme in ("http", "https"):
                    if sp.netloc.replace("www.", "") != SITE:
                        continue
                    target = sp.path or "/"
                elif sp.netloc or sp.scheme:
                    continue
                elif not sp.path:
                    continue
                else:
                    target = urljoin(base, sp.path)
                if not target.startswith("/"):
                    target = "/" + target
                yield rel, h, target


@pytest.mark.skipif(not os.path.isdir(DOCS), reason="site not built")
def test_no_internal_link_points_at_a_page_that_was_never_built():
    paths = _built_paths()
    broken = {}
    for src, href, target in _internal_targets():
        if target == "/":
            continue
        if not _resolves(target, paths):
            broken.setdefault((href, target), set()).add(src)
    if broken:
        lines = [f'  href="{h}" -> {t}   from {len(s)} page(s), '
                 f'e.g. {sorted(s)[0]}' for (h, t), s in sorted(broken.items())]
        raise AssertionError(
            f"{len(broken)} internal link(s) point at nothing:\n"
            + "\n".join(lines))


@pytest.mark.skipif(not os.path.isdir(DOCS), reason="site not built")
def test_links_to_other_pages_are_not_relative_directory_paths():
    """A relative href ending in / is what let the chain grow one segment per
    click. Root-absolute or extensionless-sibling links cannot compound."""
    offenders = []
    for src, href, _ in _internal_targets():
        if href.startswith(("/", "http")):
            continue
        if href.endswith("/") and "." not in href.split("/")[0]:
            offenders.append(f'{src}: href="{href}"')
    assert not offenders, (
        "relative directory-style links compound when the page they are on "
        "is itself a bad path:\n  " + "\n  ".join(sorted(set(offenders))))


@pytest.mark.skipif(not os.path.isdir(DOCS), reason="site not built")
def test_the_site_has_a_404_page():
    """Without docs/404.html, Pages answers every unmatched path with
    index.html and a 200. That is what hid the broken city links, and it
    invites Google to index unbounded duplicate homepages."""
    assert os.path.exists(f"{DOCS}/404.html"), "docs/404.html is missing"
    html = open(f"{DOCS}/404.html", encoding="utf-8").read()
    assert "noindex" in html, "the 404 page must not be indexable"
