#!/usr/bin/env python3
"""The two daily story posts around the rate card, from the site's own news.

    python news_post.py build news|pulse         # card + caption -> docs/social/<kind>-YYYY-MM-DD.*
    python news_post.py publish news|pulse <url> # post them to Instagram

  news   morning: "Today's Gold News" - the day's main gold story, three
         points and the market's view, attributed.
  pulse  afternoon: "India's Gold Pulse" - what Indian buyers and the
         Indian market are doing (demand, festivals, imports, jewellers),
         plus our own figures: the 22K middle today, its move over a week,
         and the gap between jewellers.

The headlines are the ones the site shows (generate_site.fetch_news - the
same links). Gemini's free text model writes the summary in our own words
from those headlines only, and it is checked before anything is posted,
because a wrong figure is worse than no post:
  - every number must appear in the headlines or in our own data;
  - a view about what comes next must be attributed (analysts, a brokerage,
    traders...), never our own prediction; the card says it is not
    investment advice;
  - no "guarantee", no "scrap".
If anything fails, that post is skipped for the day. Every card carries the
logo header (social_post.header), like the rate card.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

import social_post as sp

MODELS = [m for m in [os.environ.get("GEMINI_TEXT_MODEL"), "gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"] if m]
HOURS = 36
BANNED = ("guarantee", "scrap", "sure-shot", "assured")
INDIA = re.compile(r"\b(india|indian|rupee|rs\.?|₹|jewell?er|jewell?ery|festive|festival|diwali|dhanteras|wedding|"
                   r"akshaya|import|rbi|demand|buyers?|consumers?|mcx|ibja|retail|mumbai|delhi|chennai|kolkata|"
                   r"bengaluru|hyderabad|kerala|sales|footfall|etf|sgb|households?)\b", re.I)

KINDS = {
    "news": {
        "title": ("Today’s", "Gold News"), "box": "MARKET VIEW",
        "brief": "the day's main gold story for Indian gold buyers: price moves and why (dollar, US rates, "
                 "central banks, geopolitics) and what it means for buyers in India",
        "view": "one sentence on what analysts, brokerages or traders in the headlines expect next, naming who "
                "says it (e.g. \"Kotak Securities expects...\"); if no headline has a view, say what traders are watching",
        "tag": "Gold news today", "emoji": "\U0001f4f0",
        "hash": "#goldnews #goldprice #goldrate #goldratetoday #gold #mygoldrates",
    },
    "pulse": {
        "title": ("India’s", "Gold Pulse"), "box": "MOOD",
        "brief": "the mood among Indian gold buyers and the Indian market today: demand at jewellers, festivals "
                 "and weddings, imports, ETFs, how buyers react to prices",
        "view": "one sentence on the mood of Indian buyers or the trade as the headlines describe it, naming who "
                "reports it (e.g. \"Jewellers quoted by Economic Times report...\")",
        "tag": "India's gold pulse", "emoji": "\U0001f1ee\U0001f1f3",
        "hash": "#goldindia #goldbuying #goldjewellery #goldrate #indiangold #mygoldrates",
    },
}

PROMPT = """You write a short Instagram post for MyGoldRates.com, an Indian site that compares \
jewellers' gold rates. Topic: %s.

Below are today's gold headlines (with the publisher) and OUR DATA. Write JSON only:
{"headline": "...", "points": ["...", "...", "..."], "view": "...", "sources": ["..."]}

Rules:
- Use ONLY facts stated in the headlines or OUR DATA. Copy any number exactly as written \
there; never calculate, round or invent one.
- "headline": at most 60 characters, in your own words.
- "points": exactly 3 points, at most 110 characters each, your own words, not copied.
- "view": %s. At most 150 characters. Never your own prediction, never advice to buy or sell.
- "sources": the publisher names you used, exactly as given.

OUR DATA
%s

HEADLINES
%s
"""


def ours(kb=None):
    """Our own figures for the pulse post, from the site's knowledge file."""
    kb = kb or json.load(open(sp.KB, encoding="utf-8"))
    d = sp.today(kb)
    h = [p for _, p in kb.get("hist", [])]
    now = d["med"]["22K"]
    wk = (h[-1] - h[-8]) * 22 / 24 if len(h) >= 8 else None
    lines = [f"22K market middle today: {sp.inr(now)}/g (middle of {d['n']} jewellers' rates, before GST)",
             f"Same 10 g of 22K differs by up to {sp.inr(d['gap'])} between jewellers today"]
    if wk is not None:
        lines.append(f"22K over the last 7 days: {'up' if wk >= 0 else 'down'} {sp.inr(abs(wk))}/g")
    return d, wk, lines


def fetch(kind):
    """The site's gold headlines from the last HOURS hours: [(source, title)]."""
    import generate_site as gs
    cut = datetime.utcnow() - timedelta(hours=HOURS)
    out = [(n["source"] or "Google News", n["title"]) for n in gs.fetch_news(limit=40)
           if n.get("dt") is None or n["dt"] >= cut]
    if kind == "pulse":
        india = [x for x in out if INDIA.search(x[1])]
        out = india if len(india) >= 3 else out
    return out[:25]


def _nums(t):
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t)}


def check(s, items, data=()):
    """The summary if it passes every check, else (None, why)."""
    try:
        head, pts, view, src = s["headline"].strip(), [p.strip() for p in s["points"]], s["view"].strip(), s["sources"]
    except (KeyError, TypeError, AttributeError):
        return None, "bad shape"
    if len(pts) != 3 or not head or not view or not isinstance(src, list):
        return None, "bad shape"
    text = " ".join([head, view] + pts)
    known = _nums(" ".join(t for _, t in items) + " " + " ".join(data))
    if _nums(text) - known:
        return None, f"numbers not in the news: {len(_nums(text) - known)}"
    if any(w in text.lower() for w in BANNED):
        return None, "banned word"
    if not re.search(r"analyst|expert|brokerage|securities|trader|market|says|expects|according|watch|report|"
                     r"jewell?er|buyer|quoted|survey|council", view, re.I):
        return None, "view not attributed"
    names = {p for p, _ in items}
    src = [p for p in src if p in names] or sorted(names)[:4]
    return {"headline": head[:70], "points": [p[:130] for p in pts], "view": view[:180], "sources": src[:5]}, ""


def summarise(kind, items, key, data=()):
    import requests
    k = KINDS[kind]
    prompt = PROMPT % (k["brief"], k["view"], "\n".join(data) or "(none)", "\n".join(f"- [{p}] {t}" for p, t in items))
    for m in MODELS:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}},
                              timeout=180)
        except requests.RequestException as e:
            sp._say(f"{kind}: {m} no answer ({type(e).__name__})"); continue
        if not r.ok:
            sp._say(f"{kind}: {m} HTTP {r.status_code}"); continue
        try:
            s = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, ValueError):
            sp._say(f"{kind}: {m} gave no usable JSON"); continue
        ok, why = check(s, items, data)
        if ok:
            return ok
        sp._say(f"{kind}: {m} draft failed the checks ({why})")
    return None


def _wrap(g, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if g.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + ([cur] if cur else [])


def card(kind, n, date, path, figures=None):
    """1080x1350 story card: logo header, title, headline, three points, the
    view (attributed), our figures for the pulse, sources, not-advice note."""
    from PIL import Image, ImageDraw, ImageFilter
    W, H = 1080, 1350
    k = KINDS[kind]
    f = sp.fonts()
    img = Image.new("RGB", (W, H))
    bg = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        bg.line([(0, y), (W, y)], fill=(round(255 - 4 * t), round(248 - 18 * t), round(232 - 40 * t)))
    glow = Image.new("RGBA", (W, H), (255, 214, 130, 0))
    ImageDraw.Draw(glow).ellipse((560, -300, 1400, 520), fill=(255, 214, 130, 150))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(110)))
    g = ImageDraw.Draw(img)
    sp.header(g, f)
    g.text((56, 150), k["title"][0], font=f("Serif-Bold", 84), fill=sp.INK)
    g.text((52, 236), k["title"][1], font=f("Serif-Black", 116), fill=(150, 98, 14))
    g.text((60, 372), date, font=f("Medium", 28), fill=sp.SOFT)
    sp._ball(g, 950, 150, 70, glint=False)
    g.text((950, 152), "₹", font=f("Bold", 70), fill=(150, 98, 14), anchor="mm")
    y = 436
    for ln in _wrap(g, n["headline"], f("Bold", 40), 960)[:2]:
        g.text((56, y), ln, font=f("Bold", 40), fill=sp.INK); y += 52
    y += 14
    for i, p in enumerate(n["points"]):
        lines = _wrap(g, p, f("Medium", 28), 880)[:3]
        h = 30 + 38 * len(lines)
        g.rounded_rectangle((44, y, 1036, y + h), 24, fill=(255, 251, 242), outline=(226, 186, 104), width=2)
        sp._ball(g, 92, y + h / 2, 25, glint=False)
        g.text((92, y + h / 2), str(i + 1), font=f("Bold", 25), fill=sp.INK, anchor="mm")
        for j, ln in enumerate(lines):
            g.text((140, y + 15 + 38 * j), ln, font=f("Medium", 28), fill=sp.INK)
        y += h + 14
    lines = _wrap(g, n["view"], f("Medium", 27), 900)[:3]
    h = 70 + 36 * len(lines)
    g.rounded_rectangle((44, y + 2, 1036, y + 2 + h), 26, fill=sp.INK)
    g.text((80, y + 20), k["box"], font=f("Bold", 23), fill=(227, 191, 99))
    for j, ln in enumerate(lines):
        g.text((80, y + 56 + 36 * j), ln, font=f("Medium", 27), fill=(245, 238, 220))
    y += h + 16
    if figures:                                       # our own numbers, drawn by code
        g.rounded_rectangle((44, y, 1036, y + 70), 22, fill=(252, 238, 200), outline=(206, 150, 44), width=2)
        cols = [(200, figures[0]), (540, figures[1]), (880, figures[2])]
        for cx, (lab, val) in cols:
            g.text((cx, y + 22), lab, font=f("Medium", 19), fill=sp.SOFT, anchor="mm")
            g.text((cx, y + 49), val, font=f("Bold", 25), fill=sp.INK, anchor="mm")
        y += 84
    g.text((50, y), "Sources: " + ", ".join(n["sources"]) + ".  News summary, not investment advice.",
           font=f("Medium", 19), fill=sp.SOFT)
    g.rounded_rectangle((44, H - 124, 1036, H - 40), 42, fill=sp.INK)
    g.text((96, H - 82), "Today’s jeweller rates on ", font=f("Bold", 32), fill=(227, 191, 99), anchor="lm")
    xx = 96 + g.textlength("Today’s jeweller rates on ", font=f("Bold", 32))
    g.text((xx, H - 82), "MyGoldRates.com", font=f("Bold", 32), fill=(245, 238, 220), anchor="lm")
    ax, ay = 976, H - 82
    sp._ball(g, ax, ay, 31, glint=False)
    g.line([(ax - 14, ay), (ax + 13, ay)], fill=sp.INK, width=5)
    g.line([(ax + 2, ay - 11), (ax + 14, ay), (ax + 2, ay + 11)], fill=sp.INK, width=5)
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def caption(kind, n, date, figures=None):
    k = KINDS[kind]
    lab = "\U0001f52e Market view" if kind == "news" else "\U0001f4ac Mood"
    figs = ("\n\U0001f4ca Our data: " + " · ".join(f"{a} {b}" for a, b in figures) + "\n") if figures else ""
    return (
        f"{k['tag']}, {date} {k['emoji']}\n\n{n['headline']}\n\n"
        + "".join(f"• {p}\n" for p in n["points"])
        + f"\n{lab}: {n['view']}\n{figs}\n"
        f"Sources: {', '.join(n['sources'])}. News summary, not investment advice.\n\n"
        "\U0001f449 Today's rates at 30+ jewellers, making charges and offers: mygoldrates.com (link in bio)\n"
        "\U0001f514 Follow for gold news every morning, the rate card at 11 and India's gold pulse in the afternoon.\n\n"
        + k["hash"]
    )


def build(kind):
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        sp._say(f"{kind}: no GEMINI_API_KEY - nothing built"); return None
    items = fetch(kind)
    sp._say(f"{kind}: {len(items)} headlines from the site's news")
    if len(items) < 3:
        return None
    data, figures = (), None
    if kind == "pulse":
        d, wk, data = ours()
        figures = [("22K today", sp.inr(d["med"]["22K"]) + "/g"),
                   ("7-day move", ("▲ " if (wk or 0) >= 0 else "▼ ") + sp.inr(abs(wk or 0)) + "/g" if wk is not None else "—"),
                   ("Gap on 10 g", sp.inr(d["gap"]))]
    n = summarise(kind, items, key, data)
    if not n:
        sp._say(f"{kind}: no summary passed the checks - nothing posted"); return None
    now = datetime.now(sp.IST)
    date, stamp = f"{now.day} {now:%B %Y}", now.strftime("%Y-%m-%d")
    os.makedirs(sp.OUT, exist_ok=True)
    path = os.path.join(sp.OUT, f"{kind}-{stamp}.jpg")
    card(kind, n, date, path, figures)
    with open(os.path.join(sp.OUT, f"{kind}-{stamp}.txt"), "w", encoding="utf-8") as fh:
        fh.write(caption(kind, n, date, figures))
    sp._say(f"{kind}: card built ({n['headline']})")
    return path


def publish(kind, url):
    stamp = datetime.now(sp.IST).strftime("%Y-%m-%d")
    key = f"{kind}-{stamp}"
    try:
        log = json.load(open(sp.LOG, encoding="utf-8"))
    except (OSError, ValueError):
        log = {}
    if key in log:
        print("already posted today"); return
    txt = os.path.join(sp.OUT, f"{key}.txt")
    if not os.path.exists(txt):
        print(f"no {kind} card today - nothing to post"); return
    mid = sp.publish(url, open(txt, encoding="utf-8").read())
    if mid:
        log[key] = mid
        with open(sp.LOG, "w", encoding="utf-8") as fh:
            json.dump(log, fh, indent=1, sort_keys=True)
        print("posted", mid)


def main():
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "build" and a[1] in KINDS:
        build(a[1])
    elif len(a) >= 3 and a[0] == "publish" and a[1] in KINDS:
        publish(a[1], a[2])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
