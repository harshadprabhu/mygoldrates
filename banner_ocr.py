"""Read offer text from jewellers' banner images, free (Tesseract OCR).

Many jewellers publish their offers only as pictures - CaratLane's "FLAT 20%
off on all diamond jewellery / 5% instant discount on credit cards" is a
homepage banner with no text on the page. offers.py calls this to:

  1. find the banner images on a page (named in the plain page, or the large
     wide images of the rendered page);
  2. read each banner the way a person does, not line by line:
       - three readings of the picture - plain, inverted (light text on
         dark) and a gold-lettering mask (stylised gold figures such as PN
         Gadgil & Sons' "50%Off" only come out in that one) - merged by
         position, keeping only words Tesseract is confident about;
       - the headline figures (the big "50%" / "100%") each start a panel;
         the small text under a figure, within its own width, belongs to it;
         a line that runs under several panels ("Offer valid till 15 Nov
         2026 | T&C apply") belongs to all of them;
       - the tiny rotated "UPTO" printed beside a figure is read from that
         strip, turned upright;
  3. hand back one block of text per panel, for the same offer rules as
     page text.

A banner without headline figures is read as lines, as before. Offers read
this way are marked on the site ("read from their banner").
"""
from __future__ import annotations

import io
import re

MIN_CONF = 70           # Tesseract word confidence (0-100) to keep a word
MAX_IMAGES = 8          # per page
MIN_W, MIN_H = 500, 180

BANNER_HINT = re.compile(r"banner|slider|carousel|hero|offer|sale|promo|festive|diwali|"
                         r"dhanteras|campaign|home|web|desktop|deal|wysiwyg|cms", re.I)
NOT_BANNER = re.compile(r"logo|icon|sprite|avatar|favicon|\.svg|\.gif|thumb|swatch|"
                        r"payment|social|whatsapp|badge|/product|/catalog/product|_\d{2,3}x\d{2,3}", re.I)


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


# ------------------------------------------------------------ reading
def _fix(w: str) -> str:
    """Stylised figures: "lOO" is 100, "5O%" is 50%, "%rr" (a "%Off" glyph)
    is "%"."""
    w = re.sub(r"^[lI1][oO0][oO0](?=%|$|[^A-Za-z])", "100", w)
    w = re.sub(r"^([1-9])[oO](?=%|$|[^A-Za-z])", r"\g<1>0", w)
    if re.fullmatch(r"%[A-Za-z:;.]{0,3}", w):
        w = "%"
    return w


def _words(img, min_conf=MIN_CONF, psm=11):
    """Confident words with their boxes."""
    import pytesseract
    d = pytesseract.image_to_data(img, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    out = []
    for i, w in enumerate(d["text"]):
        w = w.strip()
        try:
            c = float(d["conf"][i])
        except ValueError:
            continue
        if not w or c < min_conf or not re.search(r"[A-Za-z0-9₹%]", w):
            continue
        out.append({"w": _fix(w), "c": c, "x": d["left"][i], "y": d["top"][i],
                    "wd": d["width"][i], "h": d["height"][i]})
    return out


def _gold_mask(im):
    """Warm, bright pixels (gold lettering) as black on white."""
    from PIL import Image
    try:
        import numpy as np
        a = im.convert("RGB")
        arr = np.asarray(a).astype(int)
        m = (arr[:, :, 0] > 150) & (arr[:, :, 1] > 110) & ((arr[:, :, 1] - arr[:, :, 2]) > 25)
        return Image.fromarray(np.where(m, 0, 255).astype("uint8"))
    except ImportError:
        src = im.convert("RGB")
        px = src.load()
        out = Image.new("L", src.size, 255)
        o = out.load()
        for y in range(src.size[1]):
            for x in range(src.size[0]):
                r, g, b = px[x, y]
                if r > 150 and g > 110 and g - b > 25:
                    o[x, y] = 0
        return out


def _merge(groups):
    """Words from several readings of the same picture: where two overlap,
    keep the one with digits, then the more confident."""
    keep = []
    for w in [w for g in groups for w in g]:
        clash = None
        for k in keep:
            ox = min(w["x"] + w["wd"], k["x"] + k["wd"]) - max(w["x"], k["x"])
            oy = min(w["y"] + w["h"], k["y"] + k["h"]) - max(w["y"], k["y"])
            if ox > 0 and oy > 0 and ox * oy > 0.35 * min(w["wd"] * w["h"], k["wd"] * k["h"]):
                clash = k
                break
        if clash is None:
            keep.append(w)
        elif (bool(re.search(r"\d", w["w"])), w["c"]) > (bool(re.search(r"\d", clash["w"])), clash["c"]):
            keep[keep.index(clash)] = w
    return keep


def _lines_of(words):
    """Words into lines (by vertical centre), each left to right."""
    words = sorted(words, key=lambda w: (w["y"] + w["h"] / 2, w["x"]))
    lines, cur, cy, ch = [], [], None, None
    for w in words:
        y = w["y"] + w["h"] / 2
        if cy is None or abs(y - cy) > max(min(w["h"], ch), 10) * 0.6:
            if cur:
                lines.append(sorted(cur, key=lambda v: v["x"]))
            cur, cy, ch = [w], y, w["h"]
        else:
            cur.append(w)
    if cur:
        lines.append(sorted(cur, key=lambda v: v["x"]))
    return lines


def _upto_beside(im, fig) -> bool:
    """The small rotated "UPTO" printed in the strip just left of a figure."""
    import pytesseract
    h = fig["h"]
    # The full strip beside the figure, then a tighter one: a tall figure
    # box (PN Gadgil & Sons' "100") can reach the line of text below it.
    boxes = [(max(0, fig["x"] - max(16, int(h * 0.5))), max(0, fig["y"] - h // 4), fig["x"] + 4,
              min(im.height, fig["y"] + h + h // 4)),
             (max(0, fig["x"] - max(16, int(h * 0.3))), max(0, fig["y"] - h // 10), fig["x"] - 2,
              min(im.height, fig["y"] + int(h * 0.8)))]
    for box in boxes:
        if box[2] - box[0] < 6:
            continue
        strip = im.crop(box).convert("L")
        strip = strip.resize((strip.width * 3, strip.height * 3))
        # Printed reading upwards, so turned 270 degrees it reads "U P T O"
        # (the O often comes out as a degree sign, the thin T as a "u":
        # "U Pp u ce)" beside PN Gadgil & Sons' 100%).
        for angle in (270, 90):
            for img in (strip, _invert(strip)):
                for psm in (6, 7):
                    t = pytesseract.image_to_string(img.rotate(angle, expand=True), config=f"--psm {psm}")
                    if re.search(r"\bu\s*p+\s*[tu]\s*[o0°c(]?", t, re.I):
                        return True
    return False


def _invert(img):
    from PIL import ImageOps
    return ImageOps.invert(img.convert("L"))


def _panels(im, words) -> list[str] | None:
    """One block of text per headline figure; None if the banner has none."""
    if not words:
        return None
    hs = sorted(w["h"] for w in words)
    small = hs[len(hs) // 2]
    figs = [w for w in words if re.fullmatch(r"\d{1,3}%?", w["w"]) and w["h"] >= 2.2 * small]
    if not figs:
        return None
    figs.sort(key=lambda f: f["x"])
    # A figure's "%" may be a separate word just right of it.
    for f in figs:
        if not f["w"].endswith("%"):
            if any(w["w"].startswith("%") and 0 <= w["x"] - (f["x"] + f["wd"]) < f["h"]
                   and abs(w["y"] - f["y"]) < f["h"] * 0.5 for w in words):
                f["w"] += "%"
    # Panel edges: midway between neighbouring figures. A panel takes only
    # text within its own figure's reach, so text beside a single headline
    # (CaratLane's bank-card offer next to its "20%") stays out of it.
    centres = [f["x"] + f["wd"] / 2 for f in figs]
    edges = [-1e9] + [(centres[i] + centres[i + 1]) / 2 for i in range(len(figs) - 1)] + [1e9]
    bands = []
    for i, f in enumerate(figs):
        lo = max(edges[i], f["x"] - 0.6 * f["wd"] - f["h"])
        hi = min(edges[i + 1], f["x"] + 1.6 * f["wd"] + f["h"])
        bands.append((lo, hi))
    rest = [w for w in words if w not in figs and not (w["w"] == "%" and w["h"] >= 2.2 * small)]
    # Words on the figure's own line, right next to it: "FLAT 20% OFF".
    beside = [([], []) for _ in figs]
    for i, f in enumerate(figs):
        for w in sorted(rest, key=lambda v: v["x"]):
            cy = w["y"] + w["h"] / 2
            # headline-sized, close, and inside this figure's own panel
            if (not (f["y"] <= cy <= f["y"] + f["h"]) or len(w["w"]) > 12 or w["h"] < 0.45 * f["h"]
                    or w["x"] < bands[i][0] or w["x"] + w["wd"] > bands[i][1]):
                continue
            if 0 <= f["x"] - (w["x"] + w["wd"]) < 0.8 * f["h"]:
                beside[i][0].append(w)
            elif 0 <= w["x"] - (f["x"] + f["wd"]) < 0.8 * f["h"]:
                beside[i][1].append(w)
    used = [w for b in beside for side in b for w in side]
    rest = [w for w in rest if w not in used]
    panel_lines = [[] for _ in figs]
    shared, other = [], []
    top = min(f["y"] for f in figs)
    for ln in _lines_of(rest):
        # split a line where a wide gap means another column
        segs, seg = [], [ln[0]]
        for w in ln[1:]:
            if w["x"] - (seg[-1]["x"] + seg[-1]["wd"]) > im.width * 0.03:
                segs.append(seg)
                seg = [w]
            else:
                seg.append(w)
        segs.append(seg)
        for sg in segs:
            x0 = min(w["x"] for w in sg)
            x1 = max(w["x"] + w["wd"] for w in sg)
            y = min(w["y"] for w in sg)
            text = " ".join(w["w"] for w in sg)
            inside = [i for i, (lo, hi) in enumerate(bands) if x0 < hi and x1 > lo]
            # a word just above a figure, within its reach ("FLAT" over
            # CaratLane's "20%", "UPTO" over others), leads that panel
            above = [i for i, f in enumerate(figs)
                     if f["y"] - 1.3 * f["h"] <= y < f["y"] and x0 >= bands[i][0] and x1 <= bands[i][1]]
            if above and len(text) <= 12 and re.fullmatch(
                    r"(?:flat|up\s*to|upto|extra|get|save|enjoy|special|min\.?|max\.?)\W*", text, re.I):
                panel_lines[above[0]].append((-1, text))
            elif y <= top - small:
                other.append(text)
            elif len(inside) == 1 and x0 >= bands[inside[0]][0] - small and x1 <= bands[inside[0]][1] + small:
                panel_lines[inside[0]].append((y, text))
            elif len(inside) > 1 and len(figs) > 1:
                shared.append(text)            # validity, T&C under every panel
            else:
                other.append(text)
    out = []
    for i, (f, lines) in enumerate(zip(figs, panel_lines)):
        pre = " ".join([t for y, t in lines if y == -1] + [w["w"] for w in beside[i][0]])
        post = " ".join(w["w"] for w in beside[i][1])
        lead = "Up to " if (not re.search(r"up\s*to|flat", pre, re.I) and _upto_beside(im, f)) else ""
        # Under the headline: its own lines, then maybe a second, smaller
        # offer ("5% INSTANT DISCOUNT / ON CREDIT CARDS") and the validity
        # line, which belongs to every offer on the banner.
        blocks, valid = [[f"{pre} {lead}{f['w']} {post}".strip()]], list(shared)
        for y, t in sorted(lines):
            if y == -1:
                continue
            if re.search(r"\bvalid|t\s*&\s*c|\b20\d\d\b", t, re.I):
                valid.append(t)
            elif re.match(r"(?:flat\s+|up\s*to\s+)?\d{1,3}\s*%", t, re.I):
                blocks.append([t])
            else:
                blocks[-1].append(t)
        out += [" ".join(b + valid) for b in blocks]
    return out + other


def _lines(words) -> list[str]:
    """Plain reading: lines left to right, split where a big gap means
    another column."""
    out = []
    for ln in _lines_of(words):
        seg, prev = [], None
        for w in ln:
            if prev is not None and w["x"] - prev > 400:
                out.append(" ".join(seg))
                seg = []
            seg.append(w["w"])
            prev = w["x"] + w["wd"]
        if seg:
            out.append(" ".join(seg))
    return out


def read_image(data: bytes) -> str:
    """Confident text from one banner: one block per offer panel, or lines.
    "" if unreadable."""
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return ""
    if im.width < MIN_W or im.height < MIN_H:
        return ""                               # a thumbnail, not a banner
    im = im.convert("RGB")
    if im.width < 1600 or im.width > 2400:
        f = (1600 if im.width < 1600 else 2400) / im.width
        im = im.resize((int(im.width * f), int(im.height * f)))
    try:
        g = im.convert("L")
        words = _merge([_words(g), _words(ImageOps.invert(g)),
                        _words(_gold_mask(im), min_conf=50)])
    except Exception:
        return ""
    panels = _panels(im, words)
    lines = panels if panels else _lines(words)
    seen, out = set(), []
    for ln in lines:
        # a small raised "st" read as "%": "31% Oct 2026" is 31 October
        ln = re.sub(r"\b(\d{1,2})\s*(?:%|st|nd|rd|th)(?=\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))",
                    r"\1", ln, flags=re.I)
        k = ln.lower()
        if k not in seen and len(ln) >= 3:
            seen.add(k)
            out.append(ln)
    return "\n".join(out)
