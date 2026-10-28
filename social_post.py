#!/usr/bin/env python3
"""Daily Instagram post: today's gold rate card, made from the site's own data.

    python social_post.py build              # card + caption -> docs/social/
    python social_post.py publish <image_url> # post them to Instagram
    python social_post.py reel <video_url>    # post docs/social/reel-<date>.mp4 as a Reel
    python social_post.py check              # is Instagram connected? (posts nothing)

The card is drawn from docs/assistant.json (the file Sona answers from, so
every number matches the site): the market middle for 24K/22K/18K, the five
cheapest national jewellers for 22K and the gap between cheapest and dearest
on 10 g. social.yml commits the card to the public repo and hands Instagram
its raw.githubusercontent.com address - Instagram fetches the image from a
public URL, and GitHub is never behind the site's bot protection.

Posting uses Meta's free Instagram API (Instagram Login): create a media
container from the image URL, wait until Instagram has processed it, then
publish it. The access token lives in the IG_ACCESS_TOKEN secret; tokens
expire after 60 days, so each run refreshes it and keeps the fresh one in
the private app_tokens table (service key only). It is never printed.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

OUT = "docs/social"
LOG = os.path.join(OUT, "posted.json")
KB = "docs/assistant.json"
FONTS = "assets/fonts"
ART_DIR = "assets/social-art"     # jewellery photos made in Gemini/Flow; one a day, in turn
GRAPH = "https://graph.instagram.com/v21.0"
IST = timezone(timedelta(hours=5, minutes=30))
GOLD, CREAM, MUTED, BG = (240, 196, 92), (246, 236, 214), (190, 172, 138), (18, 13, 6)


def inr(v):
    """12958.2 -> '₹12,958' (Indian grouping)."""
    n = str(round(v)); h, t = n[:-3], n[-3:]
    g = []
    while len(h) > 2:
        g.insert(0, h[-2:]); h = h[:-2]
    if h:
        g.insert(0, h)
    return "₹" + (",".join(g) + "," if g else "") + t


def today(kb):
    """The figures a post may quote, all from the knowledge file."""
    nat = sorted((b for b in kb["brands"] if b.get("nat")), key=lambda b: b["r24"])
    r22 = lambda b: b["r24"] * 22 / 24
    return {
        "date": kb["date"], "n": len(kb["brands"]), "med": kb["med"],
        "top": [(b["n"], r22(b)) for b in nat[:5]],
        "gap": (r22(nat[-1]) - r22(nat[0])) * 10,
        # the card's table: cheapest first; making = median on rings, if measured
        "rows": [(b["n"], b["r24"] * 18 / 24, r22(b), (b.get("mk") or {}).get("Ring")) for b in nat],
    }


def caption(d):
    lo_n, lo_p = d["top"][0]
    return (
        f"Gold rate today, {d['date']} 🪙\n\n"
        f"24K {inr(d['med']['24K'])}/g · 22K {inr(d['med']['22K'])}/g · 18K {inr(d['med']['18K'])}/g\n"
        f"(the middle of {d['n']} jewellers' published rates, before GST)\n\n"
        f"Cheapest 22K among national jewellers today: {lo_n}, {inr(lo_p)}/g.\n"
        f"Same 10 g of 22K is up to {inr(d['gap'])} apart between jewellers - worth checking before you buy.\n\n"
        "👉 Your city's cheapest jeweller, making charges and offers: mygoldrates.com (link in bio)\n"
        "💬 Or ask Sona, our free assistant, in your own language.\n\n"
        "#goldrate #goldratetoday #goldprice #22kgold #24kgold #goldjewellery #mygoldrates"
    )


BROWN, GOLD_DK, SOFT = (74, 40, 8), (168, 112, 18), (128, 98, 58)


def _gold(t):
    """Metallic gold from shadow (0) to highlight (1)."""
    stops = [(0, (138, 86, 14)), (.4, (206, 150, 44)), (.72, (244, 202, 104)), (1, (255, 246, 206))]
    t = max(0.0, min(1.0, t))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            k = (t - a) / (b - a)
            return tuple(round(x + (y - x) * k) for x, y in zip(ca, cb)) + (255,)
    return stops[-1][1] + (255,)


def _ball(g, cx, cy, rx, ry=None, glint=True):
    """A shaded gold disc/bead, lit from the top left."""
    ry = ry or rx
    n = max(8, int(rx))
    for i in range(n):
        k = i / n
        ox, oy = -rx * .3 * k, -ry * .3 * k
        g.ellipse((cx + ox - rx * (1 - k), cy + oy - ry * (1 - k), cx + ox + rx * (1 - k), cy + oy + ry * (1 - k)), fill=_gold(.15 + .85 * k))
    if glint:
        g.ellipse((cx - rx * .5, cy - ry * .55, cx - rx * .2, cy - ry * .3), fill=(255, 255, 240, 200))


def _coin(g, f, cx, cy, r):
    """A ₹ gold coin, face on."""
    _ball(g, cx, cy, r, glint=False)
    g.ellipse((cx - r, cy - r, cx + r, cy + r), outline=_gold(.1), width=max(2, int(r * .07)))
    g.ellipse((cx - r * .78, cy - r * .78, cx + r * .78, cy + r * .78), outline=_gold(.3), width=max(2, int(r * .04)))
    g.text((cx + 2, cy + 3), "₹", font=f("Bold", int(r * 1.0)), fill=_gold(.15), anchor="mm")
    g.text((cx, cy), "₹", font=f("Bold", int(r * 1.0)), fill=_gold(.95), anchor="mm")


def _flat_coin(g, cx, cy, r):
    """A coin lying flat (for stacks): rim band, then the top face."""
    h = r * .34
    g.rectangle((cx - r, cy, cx + r, cy + r * .14), fill=_gold(.25))
    g.ellipse((cx - r, cy + r * .14 - h, cx + r, cy + r * .14 + h), fill=_gold(.2))
    _ball(g, cx, cy, r, h, glint=False)
    g.ellipse((cx - r * .75, cy - h * .75, cx + r * .75, cy + h * .75), outline=_gold(.35), width=3)


def _bangle(g, cx, cy, rx, ry, w):
    """A round gold bangle: a shaded tube, with small red stones."""
    import math
    for j in range(w):
        t = j / max(1, w - 1)
        g.ellipse((cx - rx + j, cy - ry + j, cx + rx - j, cy + ry - j), outline=_gold(.2 + .8 * math.sin(math.pi * t)), width=2)
    g.arc((cx - rx + w * .3, cy - ry + w * .3, cx + rx - w * .3, cy + ry - w * .3), 200, 290, fill=(255, 250, 225, 230), width=max(2, w // 6))
    for a in range(0, 360, 45):
        x = cx + (rx - w / 2) * math.cos(math.radians(a)); y = cy + (ry - w / 2) * math.sin(math.radians(a))
        g.ellipse((x - w * .16, y - w * .16, x + w * .16, y + w * .16), fill=(200, 24, 52, 255), outline=_gold(.9), width=2)


def _necklace(g, x0, x1, top, sag):
    """Gold beads hanging between two points, with a pendant and a ruby."""
    import math
    n = 20
    pts = [(x0 + (x1 - x0) * i / n, top + sag * math.sin(math.pi * i / n)) for i in range(n + 1)]
    for i, (x, y) in enumerate(pts):
        r = 18 + 9 * math.sin(math.pi * i / n)
        _ball(g, x, y, r)
    mx, my = pts[n // 2]
    g.polygon([(mx - 38, my + 18), (mx + 38, my + 18), (mx, my + 118)], fill=_gold(.55))
    _ball(g, mx, my + 40, 38)
    g.ellipse((mx - 18, my + 22, mx + 18, my + 62), fill=(196, 18, 48, 255), outline=_gold(.95), width=4)
    g.ellipse((mx - 9, my + 28, mx - 1, my + 38), fill=(255, 190, 200, 220))
    _ball(g, mx, my + 104, 15)


def _sparkle(g, x, y, s):
    g.polygon([(x, y - s), (x + s * .22, y - s * .22), (x + s, y), (x + s * .22, y + s * .22), (x, y + s), (x - s * .22, y + s * .22), (x - s, y), (x - s * .22, y - s * .22)],
              fill=(255, 255, 255, 235))


# ------------------------------------------------------------- AI artwork
# Gemini paints the day's jewellery photo; the numbers are always drawn by
# card() on top, never by the model (image models garble figures). Any
# failure - no key, quota spent, a refusal - falls back to the drawn card.
THEMES = [
    "an elegant gold temple-style necklace with a small ruby pendant and a few gold coins on soft ivory silk",
    "a neat stack of shiny gold coins and two gold bangles on cream marble",
    "gold jhumka earrings and a delicate gold chain on champagne satin",
    "a gold kada bracelet, two gold rings and scattered gold coins on warm beige velvet",
    "a layered gold necklace and matching earrings on a pale gold silk drape with soft bokeh lights",
    "gold coins spilling from a small ivory pouch beside a gold bangle on light marble",
    "a gold mangalsutra-style chain and a pair of gold bangles on cream linen with marigold petals",
]
ART_PROMPT = ("Award-winning luxury jewellery advertising photograph, the kind used for a premium festive campaign. "
              "{theme}. Polished 22 karat yellow gold with rich, warm reflections and crisp fine detail, catching "
              "soft golden-hour window light; gentle sparkle highlights and dreamy warm bokeh in the background. "
              "Bright, airy and high-key: ivory, cream, champagne and soft blush tones, never dark, no black. "
              "Shot on a 100mm macro lens, shallow depth of field, photorealistic, editorial magazine quality. "
              "Composition: the jewellery sits only along the edges of the frame - mainly the top-right corner and "
              "the bottom - leaving the centre and the left side as clean, softly lit, empty space for text. "
              "No text, no letters, no numbers, no logos, no watermark, no people, no hands. Vertical 4:5.")


def _say(msg):
    """A line in the run's summary on GitHub (a notice), plain print elsewhere."""
    print(("::notice title=gemini::" if os.environ.get("GITHUB_ACTIONS") else "") + msg)


def ai_art(day=None):
    """Today's background photo from the Gemini API (GEMINI_API_KEY), or None."""
    import base64, io
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        _say("no GEMINI_API_KEY - drawn card")
        return None
    import requests
    from PIL import Image
    day = day or datetime.now(IST)
    prompt = ART_PROMPT.format(theme=THEMES[day.timetuple().tm_yday % len(THEMES)])
    models = [m for m in [os.environ.get("GEMINI_IMAGE_MODEL"), "gemini-2.5-flash-image", "gemini-3.1-flash-image"] if m]
    for m in models:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              headers={"x-goog-api-key": key},             # the key never goes in a URL or a log
                              json={"contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:5"}}},
                              timeout=120)
        except requests.RequestException as e:
            _say(f"{m}: no answer - {type(e).__name__}"); continue
        if not r.ok:
            _say(f"{m}: HTTP {r.status_code} " + (r.json().get("error", {}).get("message", "") if r.headers.get("content-type", "").startswith("application/json") else "")[:200])
            continue
        for part in (r.json().get("candidates") or [{}])[0].get("content", {}).get("parts", []):
            data = (part.get("inlineData") or part.get("inline_data") or {}).get("data")
            if data:
                _say(f"artwork from {m}")
                return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
        _say(f"{m}: returned no image")
    return None


def flow_art(day=None):
    """Today's background from Google Flow via useapi.net (USEAPI_TOKEN), or None.
    Flow's Nano Banana model; the photo carries no text - card() draws it all."""
    import base64, io
    key = os.environ.get("USEAPI_TOKEN", "")
    if not key:
        return None
    import requests
    from PIL import Image
    day = day or datetime.now(IST)
    prompt = ART_PROMPT.format(theme=THEMES[day.timetuple().tm_yday % len(THEMES)])
    for model in [os.environ.get("FLOW_IMAGE_MODEL") or "nano-banana-2", "nano-banana-2-lite"]:
        try:
            r = requests.post("https://api.useapi.net/v1/google-flow/images",
                              headers={"Authorization": f"Bearer {key}"},   # never in a URL or a log
                              json={"prompt": prompt, "model": model, "aspectRatio": "3:4", "count": 1}, timeout=300)
        except requests.RequestException as e:
            _say(f"flow {model}: no answer - {type(e).__name__}"); continue
        if not r.ok:
            msg = r.json().get("error", "") if "json" in r.headers.get("content-type", "") else ""
            _say(f"flow {model}: HTTP {r.status_code} {str(msg)[:160]}"); continue
        for m in r.json().get("media") or []:
            gi = (m.get("image") or {}).get("generatedImage") or {}
            try:
                if gi.get("fifeUrl"):
                    raw = requests.get(gi["fifeUrl"], timeout=120).content
                elif gi.get("encodedImage"):
                    raw = base64.b64decode(gi["encodedImage"])
                else:
                    continue
                _say(f"artwork from Google Flow ({model})")
                return Image.open(io.BytesIO(raw)).convert("RGB")
            except Exception as e:
                _say(f"flow {model}: image unreadable - {type(e).__name__}")
        _say(f"flow {model}: returned no image")
    return None


def library_art(day=None):
    """Today's photo from ART_DIR (taken in turn by day of the year), or None."""
    from PIL import Image
    try:
        files = sorted(f for f in os.listdir(ART_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    except FileNotFoundError:
        return None
    if not files:
        return None
    day = day or datetime.now(IST)
    name = files[day.timetuple().tm_yday % len(files)]
    _say(f"artwork from the library: {name}")
    return Image.open(os.path.join(ART_DIR, name)).convert("RGB")


def _cover(im, W, H):
    """Scale and centre-crop an image to fill W x H."""
    from PIL import Image
    k = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


SERIF = "PlayfairDisplay.ttf"                     # OFL, variable weight
INK, CREAM_ROW, GOLD_ROW = (24, 16, 6), (255, 251, 242), (252, 238, 200)


def card(d, path, art=None):
    """A bright 1080x1350 (4:5) JPEG in the style of a jewellery ad: big
    "Today's Gold Rates" title, every national jeweller's 18K and 22K rate
    in a table (cheapest first), gold jewellery around it. art: a photo for
    the background (our library or Gemini); without one the jewellery is drawn."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H, S = 1080, 1350, 2
    f = fonts()

    if art is not None:
        img = _cover(art, W, H).convert("RGBA")
        veil = Image.new("RGBA", (W, H), (255, 250, 240, 0))       # an ivory veil keeps the text readable
        v = ImageDraw.Draw(veil)
        v.rounded_rectangle((20, 140, 700, 400), 40, fill=(255, 250, 240, 190))
        v.rounded_rectangle((36, 404, 1044, 1180), 30, fill=(255, 250, 240, 210))
        img = Image.alpha_composite(img, veil.filter(ImageFilter.GaussianBlur(8)))
    else:
        img = Image.new("RGB", (W, H))
        bg = ImageDraw.Draw(img)
        for y in range(H):
            k = y / H
            bg.line([(0, y), (W, y)], fill=(round(255 - 4 * k), round(248 - 18 * k), round(232 - 40 * k)))
        glow = Image.new("RGBA", (W, H), (255, 214, 130, 0))
        gl = ImageDraw.Draw(glow)
        gl.ellipse((560, -300, 1400, 520), fill=(255, 214, 130, 150))
        gl.ellipse((-300, 1050, 500, 1700), fill=(255, 226, 160, 90))
        img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(110)))
        orn = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        o = ImageDraw.Draw(orn)
        fs = lambda w, s: f(w, s * S)
        _bangle(o, 870 * S, 150 * S, 150 * S, 112 * S, 30 * S)              # two bangles, top right
        _bangle(o, 985 * S, 235 * S, 135 * S, 100 * S, 28 * S)
        for x, y in [(1000, 1300), (1000, 1276), (1000, 1252)]:          # coins, bottom right
            _flat_coin(o, x * S, y * S, 70 * S)
        _coin(o, fs, 905 * S, 1250 * S, 52 * S)
        _coin(o, fs, 40 * S, 1325 * S, 46 * S)
        orn = orn.resize((W, H), Image.LANCZOS)
        sh = Image.new("RGBA", (W, H), (120, 72, 10, 0))
        sh.paste((120, 72, 10, 90), (6, 10), orn)
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
        img = Image.alpha_composite(img, orn)
        g = ImageDraw.Draw(img)
        for x, y, s in [(740, 70, 14), (1050, 380, 12), (700, 330, 9), (860, 1180, 12)]:
            _sparkle(g, x, y, s)
    return _texts(img, d, f, W, H, path)


def _mark(g, x, y, s, fill):
    """The site's mark - two bars and a rising arrow - in an s x s box."""
    g.rounded_rectangle((x, y + s * .52, x + s * .3, y + s), int(s * .06), fill=fill)
    g.rounded_rectangle((x + s * .4, y + s * .28, x + s * .7, y + s), int(s * .06), fill=fill)
    g.line([(x + s * .05, y + s * .55), (x + s * .55, y + s * .22), (x + s * .92, y + s * .02)], fill=fill, width=max(3, int(s * .1)))
    g.polygon([(x + s, y - s * .04), (x + s * .72, y + s * .02), (x + s * .96, y + s * .26)], fill=fill)


def fonts():
    """f("Bold", 30) for Poppins, f("Serif-Black", 110) for Playfair Display."""
    from PIL import ImageFont

    def f(w, s):
        if w.startswith("Serif"):
            ft = ImageFont.truetype(os.path.join(FONTS, SERIF), s)
            ft.set_variation_by_name(w.split("-")[1])
            return ft
        return ImageFont.truetype(os.path.join(FONTS, f"Poppins-{w}.ttf"), s)
    return f


def header(g, f):
    """The logo pill at the top of every post: mark, name, tagline."""
    g.rounded_rectangle((-40, 26, 600, 136), 55, fill=INK)
    _mark(g, 52, 50, 58, (227, 191, 99))
    x = 130
    for t, c in (("My", (245, 238, 220)), ("Gold", (227, 191, 99)), ("Rates", (245, 238, 220)), (".com", (190, 176, 140))):
        g.text((x, 40), t, font=f("Bold", 42), fill=c); x += g.textlength(t, font=f("Bold", 42))
    g.text((132, 94), "Compare.  Track.  Save.", font=f("Medium", 22), fill=(230, 220, 196))


def _texts(img, d, f, W, H, path):
    """Every word and number on the card - always drawn here, never by the AI."""
    from PIL import ImageDraw
    g = ImageDraw.Draw(img)
    header(g, f)
    # title
    g.text((56, 150), "Today\u2019s", font=f("Serif-Bold", 84), fill=INK)
    g.text((52, 236), "Gold Rates", font=f("Serif-Black", 116), fill=(150, 98, 14))
    g.text((60, 372), f"{d['date']}  \u00b7  per gram, before GST", font=f("Medium", 28), fill=SOFT)
    # seal, right of the title
    cx, cy, r = 935, 420, 92
    for i in range(24):
        a = __import__("math").radians(i * 15)
        g.ellipse((cx + (r + 4) * __import__("math").cos(a) - 14, cy + (r + 4) * __import__("math").sin(a) - 14,
                   cx + (r + 4) * __import__("math").cos(a) + 14, cy + (r + 4) * __import__("math").sin(a) + 14), fill=(206, 150, 44))
    _ball(g, cx, cy, r, glint=False)
    g.ellipse((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10), outline=(150, 98, 14), width=2)
    for i, t in enumerate(("SAME", "GOLD.", "BETTER", "CHOICES.")):
        g.text((cx, cy - 48 + i * 32), t, font=f("Bold", 25), fill=INK, anchor="mm")
    # table
    rows = d["rows"][:12]
    x0, x1, y = 44, 1036, 520
    cols = [(x0 + 28, "Jeweller", "lm"), (560, "18K  \u20b9/g", "mm"), (750, "22K  \u20b9/g", "mm"), (936, "Making*", "mm")]
    g.rounded_rectangle((x0, y, x1, y + 62), 22, fill=INK)
    g.rectangle((x0, y + 30, x1, y + 62), fill=INK)
    for cx_, t, an in cols:
        g.text((cx_, y + 31), t, font=f("SemiBold", 26), fill=(240, 220, 170), anchor=an)
    y += 62
    rh = 45
    for i, (n, r18, r22, mk) in enumerate(rows):
        hi = i == 0
        g.rectangle((x0, y, x1, y + rh), fill=GOLD_ROW if hi else (CREAM_ROW if i % 2 == 0 else (248, 241, 226)))
        g.text((x0 + 28, y + rh / 2), f"{i + 1}.  {n}", font=f("Bold" if hi else "SemiBold", 27), fill=INK, anchor="lm")
        if hi:
            g.text((x0 + 36 + g.textlength(f"{i + 1}.  {n}", font=f("Bold", 27)), y + rh / 2), "  CHEAPEST", font=f("Bold", 17), fill=(176, 36, 36), anchor="lm")
        g.text((560, y + rh / 2), inr(r18), font=f("SemiBold", 27), fill=INK, anchor="mm")
        g.text((750, y + rh / 2), inr(r22), font=f("Bold", 28), fill=(150, 98, 14) if hi else INK, anchor="mm")
        g.text((936, y + rh / 2), f"{mk:g}%" if mk else "\u2014", font=f("SemiBold", 26), fill=INK if mk else SOFT, anchor="mm")
        y += rh
    g.line([(x0, y), (x1, y)], fill=(214, 180, 110), width=2)
    g.text((x0 + 6, y + 14), "*Making charges: median on rings, from real products.  \u2014 = not measured yet.", font=f("Medium", 19), fill=SOFT)
    g.text((x0 + 6, y + 46), f"Same 10 g of 22K: up to {inr(d['gap'])} apart between jewellers!", font=f("Bold", 27), fill=(176, 36, 36))
    # call to action
    g.rounded_rectangle((44, H - 128, 800, H - 40), 44, fill=INK)
    g.text((96, H - 84), "Compare on ", font=f("Bold", 34), fill=(227, 191, 99), anchor="lm")
    xx = 96 + g.textlength("Compare on ", font=f("Bold", 34))
    g.text((xx, H - 84), "MyGoldRates.com", font=f("Bold", 34), fill=(245, 238, 220), anchor="lm")
    ax, ay = 740, H - 84
    _ball(g, ax, ay, 34, glint=False)
    g.line([(ax - 15, ay), (ax + 14, ay)], fill=INK, width=5)
    g.line([(ax + 3, ay - 12), (ax + 15, ay), (ax + 3, ay + 12)], fill=INK, width=5)
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def build():
    kb = json.load(open(KB, encoding="utf-8"))
    d = today(kb)
    stamp = datetime.now(IST).strftime("%Y-%m-%d")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"rates-{stamp}.jpg")
    card(d, path, library_art() or flow_art() or ai_art())
    with open(os.path.join(OUT, f"rates-{stamp}.txt"), "w", encoding="utf-8") as fh:
        fh.write(caption(d))
    print(path)
    return path


# ------------------------------------------------------------------ Instagram
def _sb():
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY")):
        return None
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _token():
    """The freshest token: the one saved in the private app_tokens table if
    any (else the IG_ACCESS_TOKEN secret), refreshed and saved back.
    Instagram tokens last 60 days; refreshing every run keeps them alive."""
    import requests
    tok, sb = os.environ.get("IG_ACCESS_TOKEN", ""), None
    try:
        sb = _sb()
        rows = sb.table("app_tokens").select("value").eq("name", "instagram").execute().data if sb else []
        if rows and rows[0]["value"]:
            tok = rows[0]["value"]
    except Exception as e:
        print(f"::warning title=instagram::token table unavailable ({type(e).__name__}) - using the secret")
        sb = None
    if not tok:
        return ""
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=30)
    if r.ok and r.json().get("access_token"):
        tok = r.json()["access_token"]
        if sb:
            sb.table("app_tokens").upsert({"name": "instagram", "value": tok,
                                           "updated_at": datetime.now(timezone.utc).isoformat()}).execute()
            print("::notice title=instagram::token renewed and saved")
    else:
        print(f"::notice title=instagram::token refresh skipped ({r.status_code})")
    return tok


def publish(image_url, text):
    import requests
    tok = _token()
    if not tok:
        print("::notice::No Instagram token yet (IG_ACCESS_TOKEN) - card built, nothing posted.")
        return None
    me = os.environ.get("IG_USER_ID") or "me"
    r = requests.post(f"{GRAPH}/{me}/media", data={"image_url": image_url, "caption": text, "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"Instagram refused the image: {r.status_code} {r.json().get('error', {}).get('message', '')}")
    cid = r.json()["id"]
    for _ in range(30):                            # Instagram fetches and processes the image
        s = requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise SystemExit("Instagram could not process the image")
        time.sleep(5)
    r = requests.post(f"{GRAPH}/{me}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"Instagram refused to publish: {r.status_code} {r.json().get('error', {}).get('message', '')}")
    return r.json()["id"]


def publish_reel(video_url, text):
    """A Reel from a public .mp4 (1080x1920, H.264/AAC): container with
    media_type REELS, wait while Instagram processes the video, publish."""
    import requests
    tok = _token()
    if not tok:
        print("::notice::No Instagram token yet (IG_ACCESS_TOKEN) - nothing posted.")
        return None
    me = os.environ.get("IG_USER_ID") or "me"
    r = requests.post(f"{GRAPH}/{me}/media", data={"media_type": "REELS", "video_url": video_url, "caption": text,
                                                   "share_to_feed": "true", "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"Instagram refused the video: {r.status_code} {r.json().get('error', {}).get('message', '')}")
    cid = r.json()["id"]
    for _ in range(60):                            # video processing takes a minute or two
        st = requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise SystemExit(f"Instagram could not process the video: {st.get('status', '')}")
        time.sleep(6)
    else:
        raise SystemExit("Instagram took too long to process the video")
    r = requests.post(f"{GRAPH}/{me}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"Instagram refused to publish: {r.status_code} {r.json().get('error', {}).get('message', '')}")
    return r.json()["id"]


def _wait(cid, tok):
    """Wait until Instagram has fetched and processed a container."""
    import requests
    for _ in range(40):
        s = requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            return
        if s.get("status_code") == "ERROR":
            raise SystemExit("Instagram could not process an image")
        time.sleep(4)
    raise SystemExit("Instagram took too long to process the images")


def publish_carousel(image_urls, text):
    """A swipe post of 2-10 images: one container per image, one for the
    carousel, then publish. Returns the media id."""
    import requests
    tok = _token()
    if not tok:
        print("::notice::No Instagram token yet (IG_ACCESS_TOKEN) - cards built, nothing posted.")
        return None
    me = os.environ.get("IG_USER_ID") or "me"
    kids = []
    for u in image_urls:
        r = requests.post(f"{GRAPH}/{me}/media", data={"image_url": u, "is_carousel_item": "true", "access_token": tok}, timeout=60)
        if not r.ok:
            raise SystemExit(f"Instagram refused a slide: {r.status_code} {r.json().get('error', {}).get('message', '')}")
        kids.append(r.json()["id"])
    for k in kids:
        _wait(k, tok)
    r = requests.post(f"{GRAPH}/{me}/media", data={"media_type": "CAROUSEL", "children": ",".join(kids),
                                                 "caption": text, "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"Instagram refused the carousel: {r.status_code} {r.json().get('error', {}).get('message', '')}")
    cid = r.json()["id"]
    _wait(cid, tok)
    r = requests.post(f"{GRAPH}/{me}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    if not r.ok:
        raise SystemExit(f"Instagram refused to publish: {r.status_code} {r.json().get('error', {}).get('message', '')}")
    return r.json()["id"]


def check():
    """Is Instagram connected? Prints the account's username, posts nothing."""
    import requests
    tok = _token()
    if not tok:
        print("::warning::No Instagram token yet (IG_ACCESS_TOKEN secret)."); return
    r = requests.get(f"{GRAPH}/me", params={"fields": "username,account_type", "access_token": tok}, timeout=30)
    if r.ok:
        j = r.json()
        print(f"::notice title=instagram::Connected to @{j.get('username')} ({j.get('account_type', '?')}) - ready to post.")
    else:
        msg = r.json().get("error", {}).get("message", "") if "json" in r.headers.get("content-type", "") else ""
        print(f"::warning title=instagram::Token refused: {r.status_code} {msg[:160]}")


def posted_today():
    try:
        log = json.load(open(LOG, encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return datetime.now(IST).strftime("%Y-%m-%d") in log


def main():
    if sys.argv[1:2] == ["build"]:
        build()
    elif sys.argv[1:2] == ["check"]:
        check()
    elif sys.argv[1:2] == ["publish"] and len(sys.argv) > 2:
        if posted_today():
            print("already posted today")
            return
        path = sys.argv[2]
        stamp = datetime.now(IST).strftime("%Y-%m-%d")
        text = open(os.path.join(OUT, f"rates-{stamp}.txt"), encoding="utf-8").read()
        mid = publish(path, text)
        if mid:
            try:
                log = json.load(open(LOG, encoding="utf-8"))
            except (OSError, ValueError):
                log = {}
            log[stamp] = mid
            with open(LOG, "w", encoding="utf-8") as fh:
                json.dump(log, fh, indent=1, sort_keys=True)
            print("posted", mid)
    elif sys.argv[1:2] == ["reel"] and len(sys.argv) > 2:
        # a Reel made ahead (docs/social/reel-<date>.mp4 + .txt caption), posted once
        stamp = datetime.now(IST).strftime("%Y-%m-%d")
        try:
            log = json.load(open(LOG, encoding="utf-8"))
        except (OSError, ValueError):
            log = {}
        if log.get(f"reel-{stamp}"):
            print("reel already posted today")
            return
        text = open(os.path.join(OUT, f"reel-{stamp}.txt"), encoding="utf-8").read()
        mid = publish_reel(sys.argv[2], text)
        if mid:
            log[f"reel-{stamp}"] = mid
            with open(LOG, "w", encoding="utf-8") as fh:
                json.dump(log, fh, indent=1, sort_keys=True)
            print("posted reel", mid)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
