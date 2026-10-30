#!/usr/bin/env python3
"""Instagram: today's best deals, a swipe post (7 slides, 1080x1350).

    python deals_post.py build              # docs/social/deals-<date>-N.jpg + .txt caption
    python deals_post.py publish <base_url> # post them (base: the folder's public URL)

Slides: cover, today's rates (the middle of every jeweller and the five
lowest 22K), one slide per jewel - ring, earrings, bangle, mangalsutra -
ranking jewellers by what 10 g of 22K costs after today's making-charge
offer and 3% GST (the same sum as Sona's "best offer": gold + making charge
after a flat offer; an "up to" offer is shown as a best case, never ranked
on), then today's offers. Every number comes from the knowledge file
(docs/assistant.json). Each jeweller's logo is its own site's favicon, the
same one the comparison table shows.
"""
import io
import json
import os
import sys
from datetime import datetime

import social_post as sp

W, H = 1080, 1350
CATS = [("Ring", "Ring"), ("Earrings", "Earrings"), ("Bangle", "Bangle"), ("Mangalsutra", "Mangalsutra")]
BG_TOP, BG_BOT = (44, 31, 12), (14, 10, 4)
GOLD, CREAM, MUTED, INK = (227, 191, 99), (246, 236, 214), (190, 172, 138), sp.INK
RED = (232, 96, 80)
_logos = {}


def initial(name, size):
    """A gold tile with the jeweller's initial, for a site without a favicon."""
    from PIL import Image, ImageDraw
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    g = ImageDraw.Draw(tile)
    g.rounded_rectangle((0, 0, size - 1, size - 1), size // 5, fill=GOLD)
    g.text((size / 2, size / 2), (name or "?")[:1].upper(), font=sp.fonts()("Bold", int(size * .55)), fill=INK, anchor="mm")
    return tile


def logo(domain, size, name=""):
    """The jeweller's site favicon on a white rounded tile (its initial if it has none)."""
    if not domain:
        return initial(name, size)
    if domain not in _logos:
        im = None
        try:
            import requests
            from PIL import Image
            r = requests.get(f"https://www.google.com/s2/favicons?domain={domain}&sz=128", timeout=20)
            if r.ok and len(r.content) > 200:
                im = Image.open(io.BytesIO(r.content)).convert("RGBA")
                if im.size[0] < 24:            # Google's grey globe for a site without an icon
                    im = None
        except Exception:
            im = None
        _logos[domain] = im
    im = _logos[domain]
    if im is None:
        return initial(name, size)
    from PIL import Image, ImageDraw
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, size - 1, size - 1), size // 5, fill=(255, 255, 255, 255))
    inner = int(size * 0.74)
    tile.alpha_composite(im.resize((inner, inner), Image.LANCZOS), ((size - inner) // 2, (size - inner) // 2))
    return tile


def deals(kb, cat, grams=10):
    """Sona's best-offer sum for one jewel: [{n, d, mk, f, u, after, tot, best}] cheapest first."""
    rows = []
    for b in kb["brands"]:
        mk = (b.get("mk") or {}).get(cat)
        if mk is None or not b.get("r24"):
            continue
        gold = b["r24"] * 22 / 24 * grams
        mo = b.get("mo") or {}
        f, u = mo.get("f") or 0, mo.get("u") or 0
        after = mk * (1 - f / 100)
        rows.append({"n": b["n"], "d": b.get("d"), "mk": mk, "f": f, "u": u, "after": after,
                     "tot": (gold + gold * after / 100) * 1.03,
                     "best": (gold + gold * mk * (1 - u / 100) / 100) * 1.03 if u > f else None})
    return sorted(rows, key=lambda r: r["tot"])


def pct(v):
    return f"{round(v, 1):g}%"


def _canvas():
    from PIL import Image
    img = Image.new("RGB", (W, H))
    top, bot = BG_TOP, BG_BOT
    for y in range(H):
        t = y / H
        img.paste(tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)), (0, y, W, y + 1))
    return img.convert("RGBA")


def _frame(img, f, n, total, title, sub):
    from PIL import ImageDraw
    g = ImageDraw.Draw(img)
    sp.header(g, f)
    g.text((W - 60, 82), f"{n}/{total}", font=f("SemiBold", 28), fill=MUTED, anchor="rm")
    g.text((60, 178), title, font=f("Serif-Black", 74), fill=GOLD)
    if sub:
        g.text((62, 272), sub, font=f("Medium", 28), fill=CREAM)
    # footer
    g.line([(60, H - 150), (W - 60, H - 150)], fill=(90, 70, 30), width=2)
    g.text((60, H - 128), "Offer % is tentative; confirm with the jeweller. Logos belong to their owners; no affiliation.",
           font=f("Medium", 19), fill=MUTED)
    g.rounded_rectangle((60, H - 92, 620, H - 30), 31, fill=GOLD)
    g.text((340, H - 61), "Compare free: mygoldrates.com", font=f("Bold", 28), fill=INK, anchor="mm")
    g.text((W - 60, H - 61), "Swipe »" if n < total else "", font=f("SemiBold", 28), fill=GOLD, anchor="rm")
    return g


def _row(img, g, f, y, rank, r, top, h=132):
    from PIL import ImageDraw
    x0, x1 = 60, W - 60
    g.rounded_rectangle((x0, y, x1, y + h - 14), 26, fill=(64, 46, 16) if top else (34, 25, 10),
                        outline=GOLD if top else (80, 62, 28), width=3 if top else 2)
    g.text((x0 + 36, y + (h - 14) / 2), str(rank), font=f("Bold", 40), fill=GOLD, anchor="mm")
    lg = logo(r.get("d"), 72, r["n"])
    tx = x0 + 74
    if lg:
        img.alpha_composite(lg, (tx, int(y + (h - 14 - 72) / 2)))
        tx += 90
    g = ImageDraw.Draw(img)
    g.text((tx, y + 20), r["n"], font=f("Bold", 34), fill=CREAM)
    if top:
        g.text((tx + g.textlength(r["n"], font=f("Bold", 34)) + 16, y + 30), "BEST DEAL", font=f("Bold", 20), fill=RED)
    return g, tx


def slide_cover(kb, path, total, d):
    img = _canvas()
    f = sp.fonts()
    g = _frame(img, f, 1, total, "Best deals today", f"{kb['date']}  ·  10 g of 22K, after making-charge offers + 3% GST")
    y = 360
    g.text((60, y), "The jeweller that works out cheapest", font=f("SemiBold", 34), fill=CREAM)
    y += 70
    for cat, label in CATS:
        rs = d[cat]
        if not rs:
            continue
        r = rs[0]
        g.rounded_rectangle((60, y, W - 60, y + 150), 28, fill=(40, 29, 11), outline=(90, 70, 30), width=2)
        lg = logo(r["d"], 84, r["n"])
        if lg:
            img.alpha_composite(lg, (90, y + 33))
        from PIL import ImageDraw
        g = ImageDraw.Draw(img)
        g.text((200, y + 26), label.upper(), font=f("Bold", 24), fill=GOLD)
        g.text((200, y + 62), r["n"], font=f("Bold", 38), fill=CREAM)
        g.text((W - 90, y + 75), sp.inr(r["tot"]), font=f("Bold", 44), fill=GOLD, anchor="rm")
        y += 172
    g.text((60, y + 10), "Swipe for the full list, today's rates and offers »", font=f("SemiBold", 30), fill=MUTED)
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def slide_rates(kb, path, n, total):
    img = _canvas()
    f = sp.fonts()
    g = _frame(img, f, n, total, "Gold rate today", f"{kb['date']}  ·  per gram, before GST")
    med = kb["med"]
    y = 350
    for i, k in enumerate(("24K", "22K", "18K")):
        x = 60 + i * 326
        g.rounded_rectangle((x, y, x + 306, y + 170), 28, fill=(40, 29, 11), outline=(90, 70, 30), width=2)
        g.text((x + 153, y + 44), k, font=f("Bold", 34), fill=GOLD, anchor="mm")
        g.text((x + 153, y + 108), sp.inr(med[k]), font=f("Bold", 46), fill=CREAM, anchor="mm")
    g.text((60, y + 196), f"The middle of {len(kb['brands'])} jewellers' published rates", font=f("Medium", 26), fill=MUTED)
    y += 270
    g.text((60, y), "Lowest 22K today", font=f("Serif-Bold", 48), fill=GOLD)
    y += 80
    low = sorted((b for b in kb["brands"] if b.get("r24")), key=lambda b: b["r24"])[:5]
    for i, b in enumerate(low, 1):
        g, tx = _row(img, g, f, y, i, {"n": b["n"], "d": b.get("d")}, False, h=104)
        g.text((W - 100, y + 45), sp.inr(b["r24"] * 22 / 24) + "/g", font=f("Bold", 38), fill=GOLD if i == 1 else CREAM, anchor="rm")
        if b.get("st"):
            g.text((tx, y + 58), "Local: " + ", ".join(b["st"]), font=f("Medium", 22), fill=MUTED)
        y += 104
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def slide_cat(kb, rows, cat, label, path, n, total):
    img = _canvas()
    f = sp.fonts()
    g = _frame(img, f, n, total, f"{label}: best deal", "10 g of 22K · gold + making after offer + 3% GST")
    y = 340
    for i, r in enumerate(rows[:5], 1):
        g, tx = _row(img, g, f, y, i, r, i == 1, h=150)
        mk = f"Making {pct(r['mk'])}" + (f" » {pct(r['after'])}  (−{pct(r['f'])} offer)" if r["f"] else "")
        g.text((tx, y + 66), mk, font=f("Medium", 25), fill=CREAM)
        if r["best"]:
            g.text((tx, y + 98), f"Up to −{pct(r['u'])} on some designs » {sp.inr(r['best'])}", font=f("Medium", 23), fill=MUTED)
        g.text((W - 96, y + 52), sp.inr(r["tot"]), font=f("Bold", 42), fill=GOLD if i == 1 else CREAM, anchor="rm")
        y += 150
    if len(rows) > 5:
        g.text((60, y + 6), f"+ {len(rows) - 5} more jewellers on mygoldrates.com", font=f("SemiBold", 28), fill=MUTED)
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def slide_offers(kb, path, n, total):
    img = _canvas()
    f = sp.fonts()
    g = _frame(img, f, n, total, "Today's offers", "As published on each jeweller's own website")
    y = 340
    withoff = sorted((b for b in kb["brands"] if b.get("off")), key=lambda b: b["n"])[:7]
    for b in withoff:
        g, tx = _row(img, g, f, y, "•", {"n": b["n"], "d": b.get("d")}, False, h=118)
        heads = " · ".join(o["h"] for o in b["off"][:2])
        g.text((tx, y + 62), heads[:58] + ("…" if len(heads) > 58 else ""), font=f("Medium", 24), fill=CREAM)
        y += 118
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


# Gold around the world: 24K per gram in each currency and in rupees, from
# the knowledge file's spot price and live exchange rates (as on the site).
WORLD = [("Dubai (UAE)", "AED", "AED "), ("Saudi Arabia", "SAR", "SAR "), ("USA", "USD", "$"),
         ("Russia", "RUB", "RUB "), ("Kazakhstan", "KZT", "KZT "), ("Cambodia", "KHR", "KHR ")]


def world(kb):
    """[(country, local price text, rupees)] or [] without today's exchange rates."""
    I = kb.get("intl") or {}
    fx, usd_g = I.get("fx") or {}, I.get("usd_g")
    if not usd_g or not fx.get("INR"):
        return []
    out = []
    for name, cur, sym in WORLD:
        rate = 1.0 if cur == "USD" else fx.get(cur)
        if rate:
            v = usd_g * rate
            out.append((name, sym + (f"{v:,.0f}" if v >= 1000 else f"{v:,.2f}"), usd_g * fx["INR"]))
    return out


def slide_world(kb, rows, path, n, total):
    img = _canvas()
    f = sp.fonts()
    g = _frame(img, f, n, total, "Gold around the world", f"{kb['date']}  ·  24K per gram, in rupees at live exchange rates")
    india = kb["med"]["24K"]
    y = 335
    g.rounded_rectangle((60, y, W - 60, y + 100), 26, fill=(64, 46, 16), outline=GOLD, width=3)
    g.text((96, y + 50), "India", font=f("Bold", 38), fill=CREAM, anchor="lm")
    g.text((W - 96, y + 50), sp.inr(india), font=f("Bold", 42), fill=GOLD, anchor="rm")
    y += 114
    for name, local, rs in rows:
        g.rounded_rectangle((60, y, W - 60, y + 90), 22, fill=(34, 25, 10), outline=(80, 62, 28), width=2)
        g.text((96, y + 28), name, font=f("Bold", 30), fill=CREAM, anchor="lm")
        g.text((96, y + 63), local, font=f("Medium", 23), fill=MUTED, anchor="lm")
        g.text((W - 96, y + 45), sp.inr(rs), font=f("Bold", 36), fill=CREAM, anchor="rm")
        y += 100
    gap = (india / rows[0][2] - 1) * 100
    g.text((60, y + 4), f"India is about {abs(gap):.0f}% {'dearer' if gap > 0 else 'cheaper'}: mostly import duty.",
           font=f("SemiBold", 28), fill=GOLD)
    g.text((60, y + 46), "India: middle of jewellers' rates before GST. Others: spot before local taxes.",
           font=f("Medium", 22), fill=MUTED)
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def caption(kb, d):
    lines = []
    for cat, label in CATS:
        if d[cat]:
            lines.append(f"💍 {label}: {d[cat][0]['n']}, {sp.inr(d[cat][0]['tot'])}")
    return (
        f"Best gold deals today, {kb['date']} 🪔 Dhanteras & Diwali shopping, sorted.\n\n"
        "Which jeweller is cheapest for 10 g of 22K after today's making-charge offers + 3% GST:\n"
        + "\n".join(lines) + "\n\n"
        f"Swipe for the top 5 in each, today's gold rate (22K {sp.inr(kb['med']['22K'])}/g, the middle of "
        f"{len(kb['brands'])} jewellers) and the offers on every jeweller's site.\n\n"
        + (f"🌍 Gold around the world: 24K is about {sp.inr(world(kb)[0][2])}/g in Dubai vs "
           f"{sp.inr(kb['med']['24K'])}/g in India. Saudi, USA, Russia and more on the world slide "
           "and at mygoldrates.com/gold-rate-around-the-world\n\n" if world(kb) else "")
        + "👉 Your exact piece and weight: ask Sona, free, on mygoldrates.com (link in bio)\n"
        "📌 Save this for Dhanteras (6 Nov) and share it with whoever is buying gold.\n\n"
        "Offer % is tentative; confirm with the jeweller. Logos belong to their owners; no affiliation.\n\n"
        "#goldrate #dhanteras #diwali #makingcharges #goldjewellery #dubaigold #goldrateindia"
    )


def build():
    kb = json.load(open(sp.KB, encoding="utf-8"))
    d = {cat: deals(kb, cat) for cat, _ in CATS}
    stamp = datetime.now(sp.IST).strftime("%Y-%m-%d")
    os.makedirs(sp.OUT, exist_ok=True)
    cats = [(c, l) for c, l in CATS if len(d[c]) >= 2]
    w = world(kb)
    total = 3 + len(cats) + (1 if w else 0)
    files = []

    def name(i):
        files.append(f"deals-{stamp}-{i}.jpg")
        return os.path.join(sp.OUT, files[-1])
    slide_cover(kb, name(1), total, d)
    slide_rates(kb, name(2), 2, total)
    for i, (c, l) in enumerate(cats, 3):
        slide_cat(kb, d[c], c, l, name(i), i, total)
    if w:
        slide_world(kb, w, name(total - 1), total - 1, total)
    slide_offers(kb, name(total), total, total)
    with open(os.path.join(sp.OUT, f"deals-{stamp}.txt"), "w", encoding="utf-8") as fh:
        fh.write(caption(kb, d))
    with open(os.path.join(sp.OUT, f"deals-{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump({"slides": files}, fh)
    print("deals:", files)
    return files


def publish(base):
    stamp = datetime.now(sp.IST).strftime("%Y-%m-%d")
    key = f"deals-{stamp}"
    try:
        log = json.load(open(sp.LOG, encoding="utf-8"))
    except (OSError, ValueError):
        log = {}
    if key in log:
        print("already posted today"); return
    try:
        man = json.load(open(os.path.join(sp.OUT, f"{key}.json"), encoding="utf-8"))
    except (OSError, ValueError):
        print("no deals post today - nothing to post"); return
    text = open(os.path.join(sp.OUT, f"{key}.txt"), encoding="utf-8").read()
    mid = sp.publish_carousel([f"{base.rstrip('/')}/{n}" for n in man["slides"]], text)
    if mid:
        log[key] = mid
        with open(sp.LOG, "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=1, sort_keys=True)
        print("posted", mid)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["build"]:
        build()
    elif a[:1] == ["publish"] and len(a) > 1:
        publish(a[1])
    else:
        print(__doc__)
        sys.exit(2)
