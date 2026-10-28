#!/usr/bin/env python3
"""Gold awareness carousels for Instagram: purity, hallmarking, HUID.

    python awareness.py build                 # today's topic -> docs/social/awareness-<date>-N.jpg + .txt + .json
    python awareness.py build <topic>         # a chosen topic (purity | hallmark | huid)
    python awareness.py publish <base_url>    # post today's carousel (base_url holds the files)

Each topic is a six-slide swipe post (cover, the facts, how to check, a call
to action) in the site's gold-and-ivory look with the logo header on every
slide and gold ornaments in the background. The facts follow the site's own
guides (/learn/22k-vs-24k-gold and /learn/gold-hallmarking), which follow BIS
guidance. No rates appear on these cards - they never go stale - and no
slide quotes anything that changes. The topic rotates (purity, hallmark,
HUID, purity...) with each post, so the series repeats every three posts.
A slide whose text does not fit raises an error instead of being cut off.
"""
import json
import os
import sys
from datetime import datetime

import social_post as sp
from news_post import _wrap

W, H, S = 1080, 1350, 2
GOLD, DEEP, TEXT = (227, 191, 99), (150, 98, 14), (66, 44, 20)
TOPICS = ["purity", "hallmark", "huid"]

CONTENT = {
    "purity": {
        "series": "Gold purity", "learn": "/learn/22k-vs-24k-gold",
        "hash": "#goldpurity #karat #22kgold #24kgold #916gold #goldknowledge #goldbuying #mygoldrates",
        "intro": "What does 22K or 916 really mean? Swipe to learn how gold purity works - and what to check before you buy.",
        "slides": [
            ("cover", {"kicker": "GOLD KNOW-HOW", "title": "What is gold purity?", "sub": "Karat, fineness and what you really pay for"}),
            ("page", [("title", "K stands for karat"),
                      ("p", "Karat tells you how much of the metal is pure gold."),
                      ("cards", [("24K = 24 parts gold", "Pure gold: 24 out of 24 parts."),
                                 ("22K = 22 + 2", "22 parts gold and 2 parts other metals, such as copper and silver."),
                                 ("Fineness", "The same purity per 1000: 22K is 916, meaning 916 parts gold in 1000.")])]),
            ("page", [("title", "The purity guide"),
                      ("table", ["Karat", "Fineness", "Gold", "Best for"],
                       [["24K", "999", "99.9%", "Coins, bars"], ["22K", "916", "91.6%", "Jewellery"],
                        ["18K", "750", "75%", "Diamond sets"], ["14K", "585", "58.5%", "Fashion"]]),
                      ("note", "The bigger the number, the more pure gold - and the softer the metal.")]),
            ("page", [("title", "How is purity made?"),
                      ("cards", [("1  Refine", "Gold is refined until it is 99.9% pure or better."),
                                 ("2  Alloy", "For jewellery it is mixed with copper, silver or zinc. 22 parts gold + 2 parts alloy = 22K."),
                                 ("3  Test", "Purity is checked with an XRF machine or a lab fire assay."),
                                 ("4  Hallmark", "The tested purity is laser-marked on the piece, like 22K916.")])]),
            ("page", [("title", "Why not wear 24K?"),
                      ("p", "Pure gold is very soft - about as hard as a fingernail."),
                      ("note", "A plain 24K bangle bends and scratches in daily wear. Mixing in other metals makes 22K strong enough for jewellery, and 18K strong enough for diamond settings.")]),
            ("cta", [("title", "Check before you buy"),
                     ("cards", [("Read the stamp", "22K916 or 18K750 - it must match your bill."),
                                ("Find the BIS hallmark", "It makes the purity official."),
                                ("Compare the rate", "Same purity, different price at every jeweller.")]),
                     ("note", "Today's jeweller rates: MyGoldRates.com")]),
        ],
    },
    "hallmark": {
        "series": "Gold hallmarking", "learn": "/learn/gold-hallmarking",
        "hash": "#goldhallmark #bishallmark #hallmarking #huid #goldknowledge #goldbuying #realgold #mygoldrates",
        "intro": "That tiny stamp on your jewellery is the proof of purity. Swipe to see what it means and how to check it before you pay.",
        "slides": [
            ("cover", {"kicker": "GOLD KNOW-HOW", "title": "Gold hallmarking", "sub": "The official stamp that proves purity"}),
            ("page", [("title", "What is a hallmark?"),
                      ("p", "A hallmark is the Bureau of Indian Standards (BIS) certificate of purity, laser-marked on the jewellery itself."),
                      ("note", "Purity is checked by an independent, BIS-recognised centre, not decided by the jeweller.")]),
            ("page", [("title", "The 3 marks to look for"),
                      ("cards", [("1  BIS logo", "The triangle mark of the Bureau of Indian Standards."),
                                 ("2  Purity grade", "Karat and fineness, such as 22K916."),
                                 ("3  HUID", "A 6-character code unique to that piece.")])]),
            ("page", [("title", "How a piece gets hallmarked"),
                      ("cards", [("1  Sent for testing", "The jeweller sends it to a BIS-recognised Assaying and Hallmarking Centre."),
                                 ("2  Purity tested", "With XRF and lab assay methods."),
                                 ("3  Marks engraved", "BIS logo, purity grade and the unique HUID, by laser."),
                                 ("4  Back to the shop", "With the hallmark on every piece.")])]),
            ("page", [("title", "4 quick checks at the shop"),
                      ("cards", [("See all 3 marks", "Ask for the jeweller's magnifier."),
                                 ("Match the purity", "The stamp must match what your bill says."),
                                 ("Verify the HUID", "Use the BIS Care app before you pay."),
                                 ("Ask about the fee", "Hallmarking costs a small fee per piece.")])]),
            ("cta", [("title", "Hallmark = purity, not price"),
                     ("p", "A hallmark proves what the gold is. It does not tell you if the rate or the making charge is fair."),
                     ("cards", [("Compare today's rate", "It differs between jewellers."),
                                ("Compare making charges", "Often the most negotiable part.")]),
                     ("note", "Compare jewellers free: MyGoldRates.com")]),
        ],
    },
    "huid": {
        "series": "HUID explained", "learn": "/learn/gold-hallmarking",
        "hash": "#huid #hallmark #bishallmark #biscare #goldknowledge #goldbuying #realgold #mygoldrates",
        "intro": "Every hallmarked piece carries its own ID. Swipe to learn what HUID is and how to verify it in under a minute.",
        "slides": [
            ("cover", {"kicker": "GOLD KNOW-HOW", "title": "What is HUID?", "sub": "The 6-character ID that tells the story of your gold"}),
            ("page", [("title", "HUID in one line"),
                      ("p", "HUID means Hallmark Unique ID: a 6-character code of letters and numbers, laser-engraved on every hallmarked piece."),
                      ("huid", "A7B9C3"),
                      ("small", "Example of the format only - not a real HUID.")]),
            ("page", [("title", "Why it matters"),
                      ("cards", [("One code, one piece", "No two pieces share a HUID."),
                                 ("Fully traceable", "It links to the jeweller, the hallmarking centre and the date."),
                                 ("Easy to check", "Anyone can verify it, before paying.")])]),
            ("page", [("title", "Verify it in 4 steps"),
                      ("cards", [("1  Open BIS Care", "The government's app, on Android and iPhone."),
                                 ("2  Tap Verify HUID", "From the app's home screen."),
                                 ("3  Enter the code", "The 6 characters engraved on your piece."),
                                 ("4  Read the details", "Jeweller, hallmarking centre, date and certified purity.")])]),
            ("page", [("title", "Good to know"),
                      ("cards", [("No HUID on the piece?", "Ask the jeweller why before you buy."),
                                 ("Old jewellery", "It can usually be tested and hallmarked at a centre."),
                                 ("Details don't match?", "Don't pay. Ask the jeweller, or contact BIS.")])]),
            ("cta", [("title", "Before you pay, verify"),
                     ("cards", [("Find the HUID", "Under magnification, on the piece."),
                                ("Check it in BIS Care", "It takes under a minute."),
                                ("Then compare the rate", "Hallmark proves purity, not price.")]),
                     ("note", "Compare jeweller rates: MyGoldRates.com")]),
        ],
    },
}

CARD_BG, CARD_LINE = (255, 251, 242), (226, 186, 104)


def _canvas():
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("RGB", (W, H))
    bg = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        bg.line([(0, y), (W, y)], fill=(round(255 - 4 * k), round(248 - 18 * k), round(232 - 40 * k)))
    glow = Image.new("RGBA", (W, H), (255, 214, 130, 0))
    gl = ImageDraw.Draw(glow)
    gl.ellipse((520, -300, 1400, 520), fill=(255, 214, 130, 150))
    gl.ellipse((-300, 1000, 500, 1700), fill=(255, 226, 160, 90))
    return Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(110)))


def _ornaments(img, kind, f):
    """Gold jewellery drawn at 2x. cover: full strength; others ghosted in a
    corner so the text stays the star."""
    from PIL import Image, ImageDraw, ImageFilter
    orn = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    o = ImageDraw.Draw(orn)
    fs = lambda w, s: f(w, s * S)
    if kind == "cover":
        sp._bangle(o, 880 * S, 250 * S, 150 * S, 112 * S, 30 * S)
        sp._bangle(o, 995 * S, 340 * S, 135 * S, 100 * S, 28 * S)
        for y in (1260, 1236, 1212):
            sp._flat_coin(o, 965 * S, y * S, 70 * S)
        sp._coin(o, fs, 850 * S, 1215 * S, 52 * S)
    elif kind == "a":
        sp._bangle(o, 1050 * S, 700 * S, 150 * S, 112 * S, 30 * S)
        for y in (1210, 1186):
            sp._flat_coin(o, 100 * S, y * S, 70 * S)
    else:
        sp._bangle(o, 40 * S, 640 * S, 140 * S, 105 * S, 28 * S)
        for y in (1210, 1186, 1162):
            sp._flat_coin(o, 975 * S, y * S, 66 * S)
    orn = orn.resize((W, H), Image.LANCZOS)
    if kind != "cover":
        orn.putalpha(orn.getchannel("A").point(lambda a: int(a * 0.5)))
    sh = Image.new("RGBA", (W, H), (120, 72, 10, 0))
    sh.paste((120, 72, 10, 70 if kind == "cover" else 34), (6, 10), orn)
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
    return Image.alpha_composite(img, orn)


def _frame(g, n, total, last):
    g.rounded_rectangle((22, 22, W - 22, H - 22), 36, outline=(226, 186, 104), width=3)
    g.rounded_rectangle((34, 34, W - 34, H - 34), 28, outline=(240, 214, 150), width=1)


def _arrow(g, x, y, c):
    g.line([(x, y), (x + 34, y)], fill=c, width=5)
    g.line([(x + 20, y - 12), (x + 34, y), (x + 20, y + 12)], fill=c, width=5)


def _footer(g, f, n, total, last):
    g.text((70, H - 74), "mygoldrates.com", font=f("SemiBold", 24), fill=DEEP, anchor="lm")
    g.text((W - 70, H - 74), f"{n} / {total}", font=f("SemiBold", 24), fill=DEEP, anchor="rm")
    if not last:
        g.text((W // 2 - 14, H - 74), "Swipe", font=f("Bold", 26), fill=sp.INK, anchor="rm")
        _arrow(g, W // 2 - 4, H - 74, sp.INK)


# ------------------------------------------------------------------ layout
X0, X1 = 80, W - 80          # content column
TOP, BOTTOM = 190, H - 120   # content area


def _measure_draw(g, f, items, y, draw):
    """Lay items out from y; draw them if `draw`. Returns the bottom y."""
    for it in items:
        kind = it[0]
        if kind == "title":
            font = f("Serif-Black", 84)
            for ln in _wrap(g, it[1], font, X1 - X0):
                if draw:
                    g.text((X0, y), ln, font=font, fill=sp.INK)
                y += 98
            y += 28
        elif kind == "p":
            font = f("Medium", 40)
            for ln in _wrap(g, it[1], font, X1 - X0):
                if draw:
                    g.text((X0, y), ln, font=font, fill=TEXT)
                y += 58
            y += 28
        elif kind == "small":
            font = f("Medium", 26)
            for ln in _wrap(g, it[1], font, X1 - X0):
                if draw:
                    g.text((X0, y), ln, font=font, fill=sp.SOFT)
                y += 36
            y += 14
        elif kind == "cards":
            hf, bf = f("Bold", 38), f("Medium", 33)
            for head, body in it[1]:
                lines = _wrap(g, body, bf, X1 - X0 - 120)
                h = 40 + 54 + 45 * len(lines)
                if draw:
                    g.rounded_rectangle((X0, y, X1, y + h), 26, fill=CARD_BG, outline=CARD_LINE, width=2)
                    sp._ball(g, X0 + 46, y + 48, 26, glint=False)
                    g.text((X0 + 46, y + 48), "•", font=f("Bold", 28), fill=sp.INK, anchor="mm")
                    g.text((X0 + 94, y + 28), head, font=hf, fill=sp.INK)
                    for j, ln in enumerate(lines):
                        g.text((X0 + 94, y + 28 + 54 + 45 * j), ln, font=bf, fill=TEXT)
                y += h + 20
        elif kind == "table":
            hdr, rows = it[1], it[2]
            cols = [X0 + 30, X0 + 250, X0 + 450, X0 + 660]
            if draw:
                g.rounded_rectangle((X0, y, X1, y + 76), 22, fill=sp.INK)
                g.rectangle((X0, y + 34, X1, y + 76), fill=sp.INK)
                for cx, t in zip(cols, hdr):
                    g.text((cx, y + 38), t, font=f("SemiBold", 32), fill=(240, 220, 170), anchor="lm")
            y += 76
            for i, r in enumerate(rows):
                if draw:
                    g.rectangle((X0, y, X1, y + 92), fill=(252, 238, 200) if i == 1 else (CARD_BG if i % 2 == 0 else (248, 241, 226)))
                    for j, (cx, t) in enumerate(zip(cols, r)):
                        g.text((cx, y + 46), t, font=f("Bold" if j == 0 else "SemiBold", 36), fill=DEEP if (j == 0 and i == 1) else sp.INK, anchor="lm")
                y += 92
            if draw:
                g.line([(X0, y), (X1, y)], fill=(214, 180, 110), width=2)
            y += 28
        elif kind == "note":
            font = f("Medium", 36)
            lines = _wrap(g, it[1], font, X1 - X0 - 70)
            h = 56 + 50 * len(lines)
            if draw:
                g.rounded_rectangle((X0, y, X1, y + h), 28, fill=sp.INK)
                for j, ln in enumerate(lines):
                    g.text((X0 + 35, y + 28 + 50 * j), ln, font=font, fill=(245, 238, 220))
            y += h + 20
        elif kind == "huid":
            box, gap = 120, 14
            total = 6 * box + 5 * gap
            x = (W - total) // 2
            if draw:
                for ch in it[1]:
                    sp._ball(g, x + box / 2, y + box / 2, box / 2, glint=False)
                    g.rounded_rectangle((x + 10, y + 10, x + box - 10, y + box - 10), 24, outline=(150, 98, 14), width=2)
                    g.text((x + box / 2, y + box / 2 + 2), ch, font=f("Bold", 66), fill=sp.INK, anchor="mm")
                    x += box + gap
            y += box + 24
    return y


def render(slide, n, total, path):
    from PIL import ImageDraw
    f = sp.fonts()
    kind, body = slide
    last = n == total
    img = _ornaments(_canvas(), "cover" if kind == "cover" else ("a" if n % 2 == 0 else "b"), f)
    g = ImageDraw.Draw(img)
    _frame(g, n, total, last)
    sp.header(g, f)
    if kind == "cover":
        tf, sf = f("Serif-Black", 136), f("Medium", 42)
        tl, sl = _wrap(g, body["title"], tf, 660)[:4], _wrap(g, body["sub"], sf, 660)[:3]
        block = 50 + len(tl) * 150 + 30 + len(sl) * 58
        y = 190 + max(0, (H - 190 - 250 - block) // 2)
        g.text((X0, y), body["kicker"], font=f("Bold", 32), fill=DEEP)
        y += 50
        for i, ln in enumerate(tl):
            g.text((X0 - 4, y), ln, font=tf, fill=sp.INK if i == 0 else DEEP); y += 150
        y += 30
        for ln in sl:
            g.text((X0, y), ln, font=sf, fill=TEXT); y += 58
        if y > 1100:
            raise ValueError(f"cover too tall: {body['title']}")
        g.text((X0, H - 150), "Swipe", font=f("Bold", 34), fill=sp.INK, anchor="lm")
        _arrow(g, X0 + 108, H - 150, sp.INK)
        g.text((X0, H - 74), "mygoldrates.com", font=f("SemiBold", 24), fill=DEEP, anchor="lm")
    else:
        h = _measure_draw(g, f, body, 0, False)
        top = TOP + max(0, (BOTTOM - TOP - h) // 2)
        if top + h > BOTTOM:
            raise ValueError(f"slide {n} text does not fit ({top + h} > {BOTTOM})")
        _measure_draw(g, f, body, top, True)
        _footer(g, f, n, total, last)
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def caption(topic):
    c = CONTENT[topic]
    return (
        f"{c['series']} \U0001f4a1\n\n{c['intro']}\n\n"
        "\U0001f4cc Save this post for when you shop for gold.\n"
        "\U0001f501 Share it with someone buying gold this season.\n\n"
        f"More: mygoldrates.com{c['learn']} (link in bio)\n"
        "General information based on BIS guidelines, not investment advice.\n\n"
        f"{c['hash']}"
    )


def next_topic(log):
    done = sum(1 for k in log if k.startswith("awareness-"))
    return TOPICS[done % len(TOPICS)]


def build(topic=None):
    try:
        log = json.load(open(sp.LOG, encoding="utf-8"))
    except (OSError, ValueError):
        log = {}
    topic = topic or next_topic(log)
    c = CONTENT[topic]
    stamp = datetime.now(sp.IST).strftime("%Y-%m-%d")
    os.makedirs(sp.OUT, exist_ok=True)
    files = []
    for i, slide in enumerate(c["slides"], 1):
        name = f"awareness-{stamp}-{i}.jpg"
        render(slide, i, len(c["slides"]), os.path.join(sp.OUT, name))
        files.append(name)
    with open(os.path.join(sp.OUT, f"awareness-{stamp}.txt"), "w", encoding="utf-8") as fh:
        fh.write(caption(topic))
    with open(os.path.join(sp.OUT, f"awareness-{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump({"topic": topic, "slides": files}, fh)
    sp._say(f"awareness: built '{c['series']}' ({len(files)} slides)")
    return topic


def publish(base):
    stamp = datetime.now(sp.IST).strftime("%Y-%m-%d")
    key = f"awareness-{stamp}"
    try:
        log = json.load(open(sp.LOG, encoding="utf-8"))
    except (OSError, ValueError):
        log = {}
    if key in log:
        print("already posted today"); return
    try:
        man = json.load(open(os.path.join(sp.OUT, f"{key}.json"), encoding="utf-8"))
    except (OSError, ValueError):
        print("no awareness carousel today - nothing to post"); return
    text = open(os.path.join(sp.OUT, f"{key}.txt"), encoding="utf-8").read()
    mid = sp.publish_carousel([f"{base.rstrip('/')}/{n}" for n in man["slides"]], text)
    if mid:
        log[key] = mid
        with open(sp.LOG, "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=1, sort_keys=True)
        print("posted", mid)


def main():
    a = sys.argv[1:]
    if a[:1] == ["build"]:
        build(a[1] if len(a) > 1 else None)
    elif a[:1] == ["publish"] and len(a) > 1:
        publish(a[1])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
