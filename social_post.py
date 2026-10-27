#!/usr/bin/env python3
"""Daily Instagram post: today's gold rate card, made from the site's own data.

    python social_post.py build              # card + caption -> docs/social/
    python social_post.py publish <image_url> # post them to Instagram

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


def card(d, path, art=None):
    """A bright 1080x1350 (4:5) JPEG. art: Gemini's photo for the background;
    without it the card is ivory and champagne, framed with drawn jewellery."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H, S = 1080, 1350, 2
    f = lambda w, s: ImageFont.truetype(os.path.join(FONTS, f"Poppins-{w}.ttf"), s)
    if art is not None:
        img = _cover(art, W, H).convert("RGBA")
        veil = Image.new("RGBA", (W, H), (255, 250, 240, 0))       # a soft ivory veil keeps the text readable
        v = ImageDraw.Draw(veil)
        v.rounded_rectangle((40, 40, 700, 450), 36, fill=(255, 250, 240, 175))
        v.rounded_rectangle((40, 452, 1040, 1312), 36, fill=(255, 250, 240, 165))
        img = Image.alpha_composite(img, veil.filter(ImageFilter.GaussianBlur(6)))
        return _texts(img, d, f, W, H, path)
    # background: warm ivory to champagne, with a soft glow
    img = Image.new("RGB", (W, H))
    bg = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        bg.line([(0, y), (W, y)], fill=(round(255 - 6 * k), round(250 - 22 * k), round(238 - 48 * k)))
    glow = Image.new("RGBA", (W, H), (255, 222, 140, 0))       # warm even where clear, so the blur adds no grey
    ImageDraw.Draw(glow).ellipse((420, -260, 1360, 520), fill=(255, 222, 140, 120))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(120)))
    # jewellery, drawn at 2x for smooth edges
    orn = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    o = ImageDraw.Draw(orn)
    fs = lambda w, s: f(w, s * S)
    _necklace(o, 560 * S, 1130 * S, -30 * S, 220 * S)
    for i, (x, y) in enumerate([(905, 392), (905, 368), (905, 344), (905, 320)]):
        _flat_coin(o, x * S, y * S, 92 * S)
    _coin(o, fs, 1000 * S, 300 * S, 62 * S)
    _bangle(o, 960 * S, 1265 * S, 150 * S, 112 * S, 30 * S)
    _bangle(o, 1045 * S, 1170 * S, 120 * S, 90 * S, 26 * S)
    for x, y, r in [(70, 1330, 54), (175, 1342, 40), (36, 1240, 34)]:
        _coin(o, fs, x * S, y * S, r * S)
    orn = orn.resize((W, H), Image.LANCZOS)
    sh = Image.new("RGBA", (W, H), (120, 72, 10, 0))
    sh.paste((120, 72, 10, 90), (6, 10), orn)
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
    img = Image.alpha_composite(img, orn)
    g = ImageDraw.Draw(img)
    for x, y, s in [(760, 120, 16), (1040, 470, 12), (640, 360, 10), (1010, 1060, 14), (250, 1290, 10)]:
        _sparkle(g, x, y, s)
    return _texts(img, d, f, W, H, path)


def _texts(img, d, f, W, H, path):
    """Every word and number on the card - always drawn here, never by the AI."""
    from PIL import Image, ImageDraw
    g = ImageDraw.Draw(img)
    # header and title
    try:
        logo = Image.open("docs/icon-192.png").convert("RGBA").resize((84, 84))
        img.paste(logo, (72, 64), logo)
    except OSError:
        pass
    g.text((176, 70), "MyGoldRates", font=f("Bold", 40), fill=GOLD_DK)
    g.text((176, 118), "mygoldrates.com", font=f("Medium", 26), fill=SOFT)
    g.text((70, 196), "Gold Rate", font=f("ExtraBold", 84), fill=BROWN)
    g.text((70, 288), "Today", font=f("ExtraBold", 84), fill=GOLD_DK)
    g.text((74, 392), d["date"], font=f("SemiBold", 34), fill=BROWN)
    # three tiles: the market middle
    for i, k in enumerate(("24K", "22K", "18K")):
        x, hi = 72 + i * 318, k == "22K"
        g.rounded_rectangle((x + 4, 474, x + 298, 644), 28, fill=(214, 170, 90))
        g.rounded_rectangle((x, 466, x + 294, 636), 28, fill=(255, 236, 178) if hi else (255, 253, 247), outline=(206, 150, 44), width=3)
        g.text((x + 28, 482), k, font=f("Bold", 30), fill=GOLD_DK)
        g.text((x + 28, 526), inr(d["med"][k]), font=f("ExtraBold", 50), fill=BROWN)
        g.text((x + 28, 592), "per gram", font=f("Medium", 22), fill=SOFT)
    g.text((72, 654), f"Middle of {d['n']} jewellers' published rates, before GST", font=f("Medium", 24), fill=SOFT)
    # cheapest 22K
    g.text((72, 712), "Cheapest 22K today", font=f("Bold", 40), fill=BROWN)
    y = 776
    for r, (n, p) in enumerate(d["top"], 1):
        hi = r == 1
        g.rounded_rectangle((72, y, 900, y + 64), 22, fill=(255, 236, 178) if hi else (255, 252, 244), outline=(226, 186, 104), width=2)
        g.ellipse((92, y + 12, 132, y + 52), fill=(206, 150, 44) if hi else (245, 226, 180))
        g.text((112, y + 32), str(r), font=f("Bold", 24), fill=(255, 255, 255) if hi else BROWN, anchor="mm")
        g.text((150, y + 32), n, font=f("SemiBold", 29), fill=BROWN, anchor="lm")
        g.text((878, y + 32), inr(p) + "/g", font=f("Bold", 31), fill=GOLD_DK if hi else BROWN, anchor="rm")
        y += 74
    g.text((72, y + 8), f"Same 10 g of 22K: up to {inr(d['gap'])} apart!", font=f("Bold", 31), fill=(176, 36, 36))
    g.rounded_rectangle((250, H - 138, 820, H - 62), 38, fill=(200, 140, 30))
    g.text((535, H - 100), "Your city's cheapest → mygoldrates.com".replace("→", "·"), font=f("Bold", 26), fill=(255, 255, 255), anchor="mm")
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def build():
    kb = json.load(open(KB, encoding="utf-8"))
    d = today(kb)
    stamp = datetime.now(IST).strftime("%Y-%m-%d")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"rates-{stamp}.jpg")
    card(d, path, library_art() or ai_art())
    with open(os.path.join(OUT, f"rates-{stamp}.txt"), "w", encoding="utf-8") as fh:
        fh.write(caption(d))
    print(path)
    return path


# ------------------------------------------------------------------ Instagram
def _token():
    """The freshest token: the saved one if any, refreshed and saved back."""
    import requests
    sb, tok = None, os.environ.get("IG_ACCESS_TOKEN", "")
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"):
        try:
            from supabase import create_client
            sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
            rows = sb.table("app_tokens").select("value").eq("name", "instagram").execute().data
            if rows:
                tok = rows[0]["value"]
        except Exception as e:                     # table not created yet: use the secret
            print("token store unavailable:", type(e).__name__)
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
    else:
        print("token refresh skipped:", r.status_code)
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


def posted_today():
    try:
        log = json.load(open(LOG, encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return datetime.now(IST).strftime("%Y-%m-%d") in log


def main():
    if sys.argv[1:2] == ["build"]:
        build()
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
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
