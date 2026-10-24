"""Read offer text from jewellers' banner images, free (Tesseract OCR).

Many jewellers publish their offers only as pictures - CaratLane's "FLAT 20%
off on all diamond jewellery / 5% instant discount on credit cards" is a
homepage banner with no text on the page. offers.py calls this to:

  1. find the banner images on a page (rendered in headless Chromium, the
     large wide images near the top: carousels, hero banners);
  2. read them with Tesseract - plain and inverted (light text on dark),
     upscaled - keeping only words Tesseract is confident about, rebuilt
     into lines from their positions so two-column banners do not mix;
  3. hand the text back for the same offer rules as page text.

Offers read this way are marked as such on the site ("read from their
banner"), and the stricter checks in offers.py apply to them.
"""
from __future__ import annotations

import io
import re

MIN_CONF = 70           # Tesseract word confidence (0-100) to keep a word
MAX_IMAGES = 8          # per page
MIN_W, MIN_H = 500, 180


def banner_urls(page) -> list[str]:
    """Large images on an already-rendered Playwright page, biggest first."""
    try:
        found = page.evaluate("""() => {
          const out = [];
          for (const im of document.images) {
            const w = im.naturalWidth, h = im.naturalHeight, src = im.currentSrc || im.src;
            if (!src || src.startsWith('data:') || w < %d || h < %d) continue;
            const r = im.getBoundingClientRect();
            out.push({src, area: w * h, top: r.top + window.scrollY});
          }
          return out;
        }""" % (MIN_W, MIN_H))
    except Exception:
        return []
    seen, urls = set(), []
    for f in sorted(found, key=lambda f: (f["top"] > 2500, -f["area"])):
        key = re.sub(r"[?#].*$", "", f["src"])
        if key in seen or re.search(r"logo|icon|sprite|avatar|\.svg", key, re.I):
            continue
        seen.add(key)
        urls.append(f["src"])
        if len(urls) >= MAX_IMAGES:
            break
    return urls


BANNER_HINT = re.compile(r"banner|slider|carousel|hero|offer|sale|promo|festive|diwali|"
                         r"dhanteras|campaign|home|web|desktop|deal|wysiwyg|cms", re.I)
NOT_BANNER = re.compile(r"logo|icon|sprite|avatar|favicon|\.svg|\.gif|thumb|swatch|"
                        r"payment|social|whatsapp|badge|/product|/catalog/product|_\d{2,3}x\d{2,3}", re.I)


def banner_urls_from_html(html: str, base: str) -> list[str]:
    """Banner image addresses written in the page's own HTML (src, data-src,
    srcset), for sites whose browser version changes by country: the plain
    page is the one served for India."""
    from urllib.parse import urljoin
    cands = []
    for m in re.finditer(r'(?:src|data-src|data-lazy|data-original|srcset|data-srcset)\s*=\s*["\']([^"\']+)["\']', html, re.I):
        for part in m.group(1).split(","):
            u = part.strip().split(" ")[0]
            if not re.search(r"\.(?:jpe?g|png|webp)(?:[?#]|$)", u, re.I):
                continue
            if NOT_BANNER.search(u) or not BANNER_HINT.search(u):
                continue
            u = urljoin(base, u)
            if u not in cands:
                cands.append(u)
    return cands[:MAX_IMAGES]


def _lines(img) -> list[str]:
    import pytesseract
    d = pytesseract.image_to_data(img, config="--psm 11", output_type=pytesseract.Output.DICT)
    words = []
    for i, w in enumerate(d["text"]):
        w = w.strip()
        try:
            c = float(d["conf"][i])
        except ValueError:
            continue
        if not w or c < MIN_CONF or not re.search(r"[A-Za-z0-9₹%]", w):
            continue
        words.append((d["top"][i], d["left"][i], d["height"][i], w))
    # Rebuild lines: words whose vertical centres are close, left to right.
    # Words far apart horizontally (another column) start a new line.
    words.sort(key=lambda x: (x[0] + x[2] / 2, x[1]))
    lines, cur, cy, last_x = [], [], None, None
    for top, left, h, w in words:
        y = top + h / 2
        if cy is None or abs(y - cy) > max(h, 12) * 0.6:
            if cur:
                lines.append(cur)
            cur, cy = [(left, w)], y
        else:
            cur.append((left, w))
    if cur:
        lines.append(cur)
    out = []
    for ln in lines:
        ln.sort()
        seg, prev = [], None
        for left, w in ln:
            if prev is not None and left - prev > 400:      # a different column
                out.append(" ".join(seg))
                seg = []
            seg.append(w)
            prev = left + 12 * len(w)
        if seg:
            out.append(" ".join(seg))
    return out


def read_image(data: bytes) -> str:
    """Confident text from one banner, as lines. "" if unreadable."""
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return ""
    if im.width < MIN_W or im.height < MIN_H:
        return ""                               # a thumbnail, not a banner
    im = im.convert("L")
    if im.width < 1600:
        f = 1600 / im.width
        im = im.resize((int(im.width * f), int(im.height * f)))
    try:
        a, b = _lines(im), _lines(ImageOps.invert(im))
    except Exception:
        return ""
    # Keep both readings: light-on-dark and dark-on-light text each read
    # well in only one of them.
    seen, out = set(), []
    for ln in a + b:
        k = ln.lower()
        if k not in seen and len(ln) >= 3:
            seen.add(k)
            out.append(ln)
    return "\n".join(out)
