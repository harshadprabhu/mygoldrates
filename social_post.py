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


def card(d, path):
    """A 1080x1350 (4:5) JPEG in the site's dark-gold look."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = 1080, 1350
    f = lambda w, s: ImageFont.truetype(os.path.join(FONTS, f"Poppins-{w}.ttf"), s)
    img = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    ImageDraw.Draw(glow).ellipse((-200, -380, W + 200, 560), fill=(92, 64, 18))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(160)), 1.0)
    g = ImageDraw.Draw(img)
    try:
        logo = Image.open("docs/icon-192.png").convert("RGBA").resize((84, 84))
        img.paste(logo, (72, 70), logo)
    except OSError:
        pass
    g.text((176, 76), "MyGoldRates", font=f("Bold", 40), fill=GOLD)
    g.text((176, 124), "mygoldrates.com", font=f("Medium", 26), fill=MUTED)
    g.text((72, 230), "Gold rate today", font=f("ExtraBold", 78), fill=CREAM)
    g.text((74, 330), d["date"], font=f("SemiBold", 36), fill=GOLD)
    # three tiles: the market middle
    for i, k in enumerate(("24K", "22K", "18K")):
        x = 72 + i * 318
        g.rounded_rectangle((x, 420, x + 294, 590), 28, fill=(40, 30, 14), outline=(120, 92, 40) if k != "22K" else GOLD, width=3)
        g.text((x + 28, 438), k, font=f("Bold", 30), fill=GOLD)
        g.text((x + 28, 484), inr(d["med"][k]), font=f("ExtraBold", 50), fill=CREAM)
        g.text((x + 28, 548), "per gram", font=f("Medium", 22), fill=MUTED)
    g.text((72, 608), f"Middle of {d['n']} jewellers' published rates, before GST", font=f("Medium", 24), fill=MUTED)
    # cheapest 22K
    g.text((72, 680), "Cheapest 22K today", font=f("Bold", 40), fill=CREAM)
    y = 748
    for r, (n, p) in enumerate(d["top"], 1):
        hi = r == 1
        g.rounded_rectangle((72, y, W - 72, y + 70), 22, fill=(58, 44, 16) if hi else (32, 24, 11))
        g.ellipse((96, y + 14, 138, y + 56), fill=GOLD if hi else (70, 54, 24))
        g.text((117, y + 35), str(r), font=f("Bold", 26), fill=BG if hi else CREAM, anchor="mm")
        g.text((162, y + 35), n, font=f("SemiBold", 31), fill=CREAM, anchor="lm")
        g.text((W - 100, y + 35), inr(p) + "/g", font=f("Bold", 33), fill=GOLD if hi else CREAM, anchor="rm")
        y += 80
    g.text((72, y + 6), f"Same 10 g of 22K: up to {inr(d['gap'])} apart.", font=f("SemiBold", 33), fill=GOLD)
    g.rounded_rectangle((72, H - 132, W - 72, H - 52), 40, fill=GOLD)
    g.text((W // 2, H - 92), "Your city's cheapest · mygoldrates.com", font=f("Bold", 34), fill=BG, anchor="mm")
    img.save(path, "JPEG", quality=92, optimize=True)


def build():
    kb = json.load(open(KB, encoding="utf-8"))
    d = today(kb)
    stamp = datetime.now(IST).strftime("%Y-%m-%d")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"rates-{stamp}.jpg")
    card(d, path)
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
