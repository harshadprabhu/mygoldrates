#!/usr/bin/env python3
"""Instagram: a one-off campaign carousel (1080x1350), built ahead and posted
by the social job's "campaign" post.

    python campaign_post.py build dip "28 Oct:Bearish:0.70,29 Oct:Bearish:0.68"
    python campaign_post.py publish <base_url>

"dip": gold has fallen. Slides: the fall (today vs yesterday and vs the
recent peak, from the knowledge file's rate history), the chart, what the
Jewellers Digest outlook said before it (the stances are passed in as read
from that day's Digest run - never invented), and what it means for a buyer.
The outlook is described as what it is: a reading of market signals, not a
promise, and nothing here is investment advice.
"""
import json
import os
import sys
from datetime import datetime

import social_post as sp
from deals_post import W, H, GOLD, CREAM, MUTED, INK, RED, _canvas

GREEN = (110, 200, 140)


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d").strftime("%-d %b")


def facts(kb):
    h = [(d, v) for d, v in kb["hist"] if v]
    (d1, now), (d0, prev) = h[-1], h[-2]
    recent = [x for x in h if x[0] >= "2026-08-01"]
    pk_d, pk = max(recent, key=lambda x: x[1])
    return {"now": now, "prev": prev, "d1": d1, "d0": d0, "day": now - prev, "day_pct": (now / prev - 1) * 100,
            "pk": pk, "pk_d": pk_d, "off": pk - now, "off_pct": (1 - now / pk) * 100,
            "now22": now * 22 / 24, "off22_10g": (pk - now) * 22 / 24 * 10, "hist": recent}


def _frame(img, f, n, total):
    from PIL import ImageDraw
    g = ImageDraw.Draw(img)
    sp.header(g, f)
    g.text((W - 60, 82), f"{n}/{total}", font=f("SemiBold", 28), fill=MUTED, anchor="rm")
    g.line([(60, H - 150), (W - 60, H - 150)], fill=(90, 70, 30), width=2)
    g.text((60, H - 128), "Market outlook, not investment advice. Prices can move either way.",
           font=f("Medium", 20), fill=MUTED)
    g.rounded_rectangle((60, H - 92, 620, H - 30), 31, fill=GOLD)
    g.text((340, H - 61), "Compare free: mygoldrates.com", font=f("Bold", 28), fill=INK, anchor="mm")
    g.text((W - 60, H - 61), "Swipe »" if n < total else "", font=f("SemiBold", 28), fill=GOLD, anchor="rm")
    return g


def _save(img, path):
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def slide_fall(F, path, total):
    img, f = _canvas(), sp.fonts()
    g = _frame(img, f, 1, total)
    g.text((60, 190), "Gold just got", font=f("Serif-Black", 92), fill=CREAM)
    g.text((60, 300), "cheaper.", font=f("Serif-Black", 120), fill=GOLD)
    y = 500
    g.rounded_rectangle((60, y, W - 60, y + 250), 32, fill=(64, 46, 16), outline=GOLD, width=3)
    g.text((100, y + 40), f"24K today, {_d(F['d1'])}", font=f("SemiBold", 32), fill=MUTED)
    g.text((100, y + 92), sp.inr(F["now"]) + "/g", font=f("Bold", 96), fill=CREAM)
    g.text((W - 100, y + 140), f"down {sp.inr(abs(F['day']))}", font=f("Bold", 44), fill=GREEN, anchor="rm")
    g.text((W - 100, y + 196), f"{abs(F['day_pct']):.1f}% since {_d(F['d0'])}", font=f("Medium", 26), fill=MUTED, anchor="rm")
    y += 290
    for label, val in ((f"Below the {_d(F['pk_d'])} peak", f"{sp.inr(F['off'])}/g  ({F['off_pct']:.0f}%)"),
                       ("22K today", f"{sp.inr(F['now22'])}/g"),
                       ("Saving on 10 g of 22K vs the peak", sp.inr(F["off22_10g"]))):
        g.text((60, y), label, font=f("Medium", 32), fill=CREAM)
        g.text((W - 60, y), val, font=f("Bold", 36), fill=GOLD, anchor="ra")
        y += 76
    g.text((60, y + 20), "The middle of Indian jewellers' published rates, before GST.", font=f("Medium", 24), fill=MUTED)
    _save(img, path)


def slide_chart(F, path, total):
    from PIL import ImageDraw
    img, f = _canvas(), sp.fonts()
    g = _frame(img, f, 2, total)
    g.text((60, 180), "Off the peak", font=f("Serif-Black", 80), fill=GOLD)
    g.text((62, 280), "24K per gram, 1 Aug to today", font=f("Medium", 30), fill=CREAM)
    h = F["hist"]
    x0, x1, y0, y1 = 110, W - 90, 380, 1020
    lo, hi = min(v for _, v in h), max(v for _, v in h)
    lo, hi = lo - (hi - lo) * 0.08, hi + (hi - lo) * 0.08
    px = lambda i: x0 + (x1 - x0) * i / (len(h) - 1)
    py = lambda v: y1 - (y1 - y0) * (v - lo) / (hi - lo)
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        g.line([(x0, py(v)), (x1, py(v))], fill=(70, 54, 24), width=1)
        g.text((x0 - 12, py(v)), f"{v / 1000:.1f}k", font=f("Medium", 20), fill=MUTED, anchor="rm")
    pts = [(px(i), py(v)) for i, (_, v) in enumerate(h)]
    g.line(pts, fill=GOLD, width=5, joint="curve")
    ip = max(range(len(h)), key=lambda i: h[i][1])
    for (x, y), lab, col, anc in ((pts[ip], f"Peak {sp.inr(F['pk'])}  {_d(F['pk_d'])}", CREAM, "ms"),
                                  (pts[-1], f"Today {sp.inr(F['now'])}", GREEN, "rs")):
        g.ellipse((x - 11, y - 11, x + 11, y + 11), fill=col, outline=INK, width=3)
        g.text((x if anc == "ms" else x + 8, y - (22 if anc == "ms" else 70)), lab, font=f("Bold", 28), fill=col, anchor=anc)
    g.text((x0, y1 + 24), _d(h[0][0]), font=f("Medium", 22), fill=MUTED)
    g.text((x1, y1 + 24), _d(h[-1][0]), font=f("Medium", 22), fill=MUTED, anchor="ra")
    g.text((60, y1 + 80), f"Down {F['off_pct']:.0f}% from the high: {sp.inr(F['off'])} less per gram of 24K.",
           font=f("SemiBold", 30), fill=CREAM)
    _save(img, path)


def slide_digest(F, stances, path, total):
    img, f = _canvas(), sp.fonts()
    g = _frame(img, f, 3, total)
    g.text((60, 180), "We flagged it", font=f("Serif-Black", 86), fill=GOLD)
    g.text((62, 290), "Jewellers Digest market outlook, before the fall", font=f("Medium", 30), fill=CREAM)
    y = 380
    for day, stance, conv in stances:
        g.rounded_rectangle((60, y, W - 60, y + 130), 28, fill=(40, 29, 11), outline=(90, 70, 30), width=2)
        g.text((100, y + 65), day, font=f("Bold", 40), fill=CREAM, anchor="lm")
        g.text((W - 100, y + 46), stance.upper(), font=f("Bold", 42), fill=RED, anchor="rm")
        g.text((W - 100, y + 96), f"conviction {float(conv) * 100:.0f}%", font=f("Medium", 24), fill=MUTED, anchor="rm")
        y += 150
    g.rounded_rectangle((60, y, W - 60, y + 130), 28, fill=(64, 46, 16), outline=GOLD, width=3)
    g.text((100, y + 65), _d(F["d1"]), font=f("Bold", 40), fill=CREAM, anchor="lm")
    g.text((W - 100, y + 46), f"down {sp.inr(abs(F['day']))}/g", font=f("Bold", 42), fill=GREEN, anchor="rm")
    g.text((W - 100, y + 96), f"{sp.inr(F['prev'])} » {sp.inr(F['now'])}", font=f("Medium", 24), fill=MUTED, anchor="rm")
    y += 170
    for line in ("The Digest reads trend, momentum and the levels",
                 "where gold keeps turning - every day, for jewellers",
                 "and serious buyers. A signal, never a guarantee."):
        g.text((60, y), line, font=f("Medium", 29), fill=CREAM)
        y += 44
    _save(img, path)


def slide_buyer(F, path, total):
    img, f = _canvas(), sp.fonts()
    g = _frame(img, f, 4, total)
    g.text((60, 180), "A golden window", font=f("Serif-Black", 80), fill=GOLD)
    g.text((62, 280), "for Dhanteras (6 Nov) buyers", font=f("Medium", 34), fill=CREAM)
    y = 380
    for head, sub in ((f"{sp.inr(F['off22_10g'])} less", "on 10 g of 22K than at the August peak"),
                      ("Compare before you buy", "the same gold costs different amounts at different jewellers"),
                      ("Check the making charge", "after the offer - it can be the bigger number"),
                      ("Buy in parts", "spreading purchases evens out the swings")):
        g.rounded_rectangle((60, y, W - 60, y + 132), 28, fill=(40, 29, 11), outline=(90, 70, 30), width=2)
        g.text((100, y + 30), head, font=f("Bold", 38), fill=GOLD)
        g.text((100, y + 82), sub, font=f("Medium", 26), fill=CREAM)
        y += 150
    g.rounded_rectangle((60, y + 10, W - 60, y + 150), 28, fill=(64, 46, 16), outline=GOLD, width=3)
    g.text((W / 2, y + 56), "Get the daily outlook: Jewellers Digest", font=f("Bold", 34), fill=CREAM, anchor="mm")
    g.text((W / 2, y + 108), "mygoldrates.com/jewellers-digest", font=f("SemiBold", 30), fill=GOLD, anchor="mm")
    _save(img, path)


def caption(F, stances):
    said = " and ".join(d for d, _, _ in stances)
    return (
        f"Gold just got cheaper 📉✨ 24K is {sp.inr(F['now'])}/g today, down {sp.inr(abs(F['day']))} "
        f"({abs(F['day_pct']):.1f}%) in a day and {sp.inr(F['off'])} ({F['off_pct']:.0f}%) below the "
        f"{_d(F['pk_d'])} peak.\n\n"
        f"Our Jewellers Digest market outlook read BEARISH on {said}, before the fall. "
        "It tracks trend, momentum and the levels where gold keeps turning, every day.\n\n"
        f"🪔 For Dhanteras buyers: 10 g of 22K costs about {sp.inr(F['off22_10g'])} less than at the August "
        "peak. Compare jewellers and their making charges before you buy, and consider buying in parts.\n\n"
        "👉 Today's rates from every jeweller we track, free: mygoldrates.com (link in bio)\n"
        "📊 The daily outlook: mygoldrates.com/jewellers-digest\n\n"
        "A market outlook, not investment advice; gold can move either way.\n\n"
        "#goldrate #goldprice #dhanteras #diwali #goldinvestment #goldrateindia #buygold #gold"
    )


def build(kind, stances_arg):
    assert kind == "dip", "only the 'dip' campaign exists"
    kb = json.load(open(sp.KB, encoding="utf-8"))
    F = facts(kb)
    if F["day"] >= 0:
        sys.exit(f"gold did not fall today ({F['prev']} -> {F['now']}); nothing built")
    stances = [tuple(x.split(":")) for x in stances_arg.split(",")]
    stamp = datetime.now(sp.IST).strftime("%Y-%m-%d")
    os.makedirs(sp.OUT, exist_ok=True)
    files = []

    def name(i):
        files.append(f"campaign-{stamp}-{i}.jpg")
        return os.path.join(sp.OUT, files[-1])
    slide_fall(F, name(1), 4)
    slide_chart(F, name(2), 4)
    slide_digest(F, stances, name(3), 4)
    slide_buyer(F, name(4), 4)
    with open(os.path.join(sp.OUT, f"campaign-{stamp}.txt"), "w", encoding="utf-8") as fh:
        fh.write(caption(F, stances))
    with open(os.path.join(sp.OUT, f"campaign-{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump({"slides": files}, fh)
    print("campaign:", files)
    return files


def publish(base):
    stamp = datetime.now(sp.IST).strftime("%Y-%m-%d")
    key = f"campaign-{stamp}"
    try:
        log = json.load(open(sp.LOG, encoding="utf-8"))
    except (OSError, ValueError):
        log = {}
    if key in log:
        print("already posted today"); return
    try:
        man = json.load(open(os.path.join(sp.OUT, f"{key}.json"), encoding="utf-8"))
    except (OSError, ValueError):
        print("no campaign today - nothing to post"); return
    text = open(os.path.join(sp.OUT, f"{key}.txt"), encoding="utf-8").read()
    mid = sp.publish_carousel([f"{base.rstrip('/')}/{n}" for n in man["slides"]], text)
    if mid:
        log[key] = mid
        with open(sp.LOG, "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=1, sort_keys=True)
        print("posted", mid)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["build"] and len(a) > 2:
        build(a[1], a[2])
    elif a[:1] == ["publish"] and len(a) > 1:
        publish(a[1])
    else:
        print(__doc__)
        sys.exit(2)
