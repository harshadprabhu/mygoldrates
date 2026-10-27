#!/usr/bin/env python3
"""Daily Instagram post: today's gold news, in our own words.

    python news_post.py build              # card + caption -> docs/social/news-YYYY-MM-DD.*
    python news_post.py publish <image_url> # post them to Instagram

The news comes from the publishers' own RSS feeds (headlines and their short
descriptions, as published for feed readers). Gemini's free text model turns
the last day's gold stories into a short summary - three points and the
market's view, attributed - using only what the feeds say. Checks before
anything is posted, because a wrong figure is worse than no post:
  - every number in the summary must appear in the feed text it came from;
  - the market view must be attributed (analysts, a brokerage, traders...),
    never our own prediction, and the card says it is not investment advice;
  - no "guarantee", no "scrap";
  - the sources are named on the card and in the caption.
If anything fails, nothing is posted that day. The card carries the logo
header like every post (social_post.header).
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import social_post as sp

FEEDS = {
    "Economic Times": "https://economictimes.indiatimes.com/markets/commodities/rssfeeds/1808152121.cms",
    "BusinessLine": "https://www.thehindubusinessline.com/markets/gold/feeder/default.rss",
    "Moneycontrol": "https://www.moneycontrol.com/rss/commodities.xml",
    "Mint": "https://www.livemint.com/rss/markets",
    "Business Standard": "https://www.business-standard.com/rss/markets-106.rss",
}
MODELS = [m for m in [os.environ.get("GEMINI_TEXT_MODEL"), "gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"] if m]
HOURS = 30
BANNED = ("guarantee", "scrap", "sure-shot", "assured")

PROMPT = """You write a short daily gold-news post for MyGoldRates.com, an Indian site that \
compares jewellers' gold rates. Below are today's gold news items from Indian business \
publications (title and summary as each publisher wrote it).

Write JSON only:
{"headline": "...", "points": ["...", "...", "..."], "outlook": "...", "sources": ["..."]}

Rules:
- Use ONLY facts stated in the items. Copy any number exactly as written there; never \
calculate, round or invent a number.
- "headline": the day's main gold story, at most 60 characters, in your own words.
- "points": exactly 3 short points (at most 110 characters each) for Indian gold buyers: \
price moves, why (dollar, Fed, demand, festivals, imports), what it means. Your own words, \
not copied sentences.
- "outlook": one sentence (at most 150 characters) on what analysts, brokerages or traders \
in the items expect next, naming who says it (e.g. "Kotak Securities expects..."). Never \
your own prediction, never advice to buy or sell. If no item has a view, say what traders \
are watching.
- "sources": the publisher names you used, from: %s.

ITEMS
%s
"""


def fetch(now=None):
    """The last HOURS hours of gold stories: [(publisher, title, summary)]."""
    import requests
    import xml.etree.ElementTree as ET
    now = now or datetime.now(timezone.utc)
    out, seen = [], set()
    for pub, url in FEEDS.items():
        try:
            x = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (MyGoldRates news reader)"}, timeout=30).content
            items = ET.fromstring(x).findall(".//item")
        except Exception as e:
            sp._say(f"news: {pub} feed unavailable ({type(e).__name__})"); continue
        for it in items:
            t = re.sub(r"\s+", " ", it.findtext("title") or "").strip()
            dsc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
            dsc = re.sub(r"\s+", " ", dsc).strip()[:400]
            if not re.search(r"\bgold\b", t + " " + dsc, re.I) or t.lower() in seen:
                continue
            try:
                when = parsedate_to_datetime(it.findtext("pubDate") or "")
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                if now - when > timedelta(hours=HOURS):
                    continue
            except (TypeError, ValueError):
                continue
            seen.add(t.lower())
            out.append((pub, t, dsc))
    return out[:30]


def _nums(t):
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t)}


def check(s, items):
    """The summary if it passes every check, else None (and why)."""
    try:
        head, pts, view, src = s["headline"].strip(), [p.strip() for p in s["points"]], s["outlook"].strip(), s["sources"]
    except (KeyError, TypeError, AttributeError):
        return None, "bad shape"
    if len(pts) != 3 or not head or not view or not isinstance(src, list):
        return None, "bad shape"
    text = " ".join([head, view] + pts)
    known = _nums(" ".join(t + " " + d for _, t, d in items))
    extra = _nums(text) - known
    if extra:
        return None, f"numbers not in the news: {len(extra)}"
    if any(w in text.lower() for w in BANNED):
        return None, "banned word"
    if not re.search(r"analyst|expert|brokerage|securities|trader|market|says|expects|according|watch", view, re.I):
        return None, "outlook not attributed"
    src = [p for p in src if p in FEEDS] or sorted({p for p, _, _ in items})
    return {"headline": head[:70], "points": [p[:130] for p in pts], "outlook": view[:180], "sources": src}, ""


def summarise(items, key):
    import requests
    prompt = PROMPT % (", ".join(FEEDS), "\n".join(f"- [{p}] {t}. {d}" for p, t, d in items))
    for m in MODELS:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}},
                              timeout=180)
        except requests.RequestException as e:
            sp._say(f"news: {m} no answer ({type(e).__name__})"); continue
        if not r.ok:
            sp._say(f"news: {m} HTTP {r.status_code}"); continue
        try:
            s = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, ValueError):
            sp._say(f"news: {m} gave no usable JSON"); continue
        ok, why = check(s, items)
        if ok:
            return ok
        sp._say(f"news: {m} draft failed the checks ({why})")
    return None


def _wrap(g, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if g.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + ([cur] if cur else [])


def card(n, date, path):
    """1080x1350 news card: logo header, title, headline, three points, the
    market's view, sources and a not-advice note."""
    from PIL import Image, ImageDraw, ImageFilter
    W, H = 1080, 1350
    f = sp.fonts()
    img = Image.new("RGB", (W, H))
    bg = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        bg.line([(0, y), (W, y)], fill=(round(255 - 4 * k), round(248 - 18 * k), round(232 - 40 * k)))
    glow = Image.new("RGBA", (W, H), (255, 214, 130, 0))
    ImageDraw.Draw(glow).ellipse((560, -300, 1400, 520), fill=(255, 214, 130, 150))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(110)))
    g = ImageDraw.Draw(img)
    sp.header(g, f)
    g.text((56, 150), "Today’s", font=f("Serif-Bold", 84), fill=sp.INK)
    g.text((52, 236), "Gold News", font=f("Serif-Black", 116), fill=(150, 98, 14))
    g.text((60, 372), date, font=f("Medium", 28), fill=sp.SOFT)
    sp._ball(g, 950, 150, 70, glint=False)                  # a gold coin, top right
    g.text((950, 152), "₹", font=f("Bold", 70), fill=(150, 98, 14), anchor="mm")
    # headline
    y = 440
    for ln in _wrap(g, n["headline"], f("Bold", 42), 960)[:2]:
        g.text((56, y), ln, font=f("Bold", 42), fill=sp.INK); y += 54
    y += 18
    # three points
    for i, p in enumerate(n["points"]):
        lines = _wrap(g, p, f("Medium", 29), 880)[:3]
        h = 34 + 40 * len(lines)
        g.rounded_rectangle((44, y, 1036, y + h), 24, fill=(255, 251, 242), outline=(226, 186, 104), width=2)
        sp._ball(g, 92, y + h / 2, 26, glint=False)
        g.text((92, y + h / 2), str(i + 1), font=f("Bold", 26), fill=sp.INK, anchor="mm")
        for j, ln in enumerate(lines):
            g.text((140, y + 17 + 40 * j), ln, font=f("Medium", 29), fill=sp.INK)
        y += h + 16
    # the market's view, attributed
    lines = _wrap(g, n["outlook"], f("Medium", 28), 900)[:3]
    h = 76 + 38 * len(lines)
    g.rounded_rectangle((44, y + 4, 1036, y + 4 + h), 26, fill=sp.INK)
    g.text((80, y + 24), "MARKET VIEW", font=f("Bold", 24), fill=(227, 191, 99))
    for j, ln in enumerate(lines):
        g.text((80, y + 62 + 38 * j), ln, font=f("Medium", 28), fill=(245, 238, 220))
    y += h + 22
    g.text((50, y), "Sources: " + ", ".join(n["sources"]) + ".  News summary, not investment advice.",
           font=f("Medium", 20), fill=sp.SOFT)
    # call to action
    g.rounded_rectangle((44, H - 128, 1036, H - 40), 44, fill=sp.INK)
    g.text((96, H - 84), "Today’s jeweller rates on ", font=f("Bold", 32), fill=(227, 191, 99), anchor="lm")
    xx = 96 + g.textlength("Today’s jeweller rates on ", font=f("Bold", 32))
    g.text((xx, H - 84), "MyGoldRates.com", font=f("Bold", 32), fill=(245, 238, 220), anchor="lm")
    ax, ay = 976, H - 84
    sp._ball(g, ax, ay, 32, glint=False)
    g.line([(ax - 14, ay), (ax + 13, ay)], fill=sp.INK, width=5)
    g.line([(ax + 2, ay - 11), (ax + 14, ay), (ax + 2, ay + 11)], fill=sp.INK, width=5)
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def caption(n, date):
    return (
        f"Gold news today, {date} \U0001f4f0\n\n{n['headline']}\n\n"
        + "".join(f"• {p}\n" for p in n["points"])
        + f"\n\U0001f52e Market view: {n['outlook']}\n\n"
        f"Sources: {', '.join(n['sources'])}. News summary, not investment advice.\n\n"
        "\U0001f449 Today's rates at 30+ jewellers, making charges and offers: mygoldrates.com (link in bio)\n"
        "\U0001f514 Follow for the daily gold rate card and gold news.\n\n"
        "#goldnews #goldprice #goldrate #goldratetoday #gold #mygoldrates"
    )


def build():
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        sp._say("news: no GEMINI_API_KEY - nothing built"); return None
    items = fetch()
    sp._say(f"news: {len(items)} gold stories in the last {HOURS} hours")
    if len(items) < 3:
        return None
    n = summarise(items, key)
    if not n:
        sp._say("news: no summary passed the checks - nothing posted today"); return None
    now = datetime.now(sp.IST)
    date, stamp = f"{now.day} {now:%B %Y}", now.strftime("%Y-%m-%d")
    os.makedirs(sp.OUT, exist_ok=True)
    path = os.path.join(sp.OUT, f"news-{stamp}.jpg")
    card(n, date, path)
    with open(os.path.join(sp.OUT, f"news-{stamp}.txt"), "w", encoding="utf-8") as fh:
        fh.write(caption(n, date))
    sp._say(f"news: card built ({n['headline']})")
    return path


def main():
    if sys.argv[1:2] == ["build"]:
        build()
    elif sys.argv[1:2] == ["publish"] and len(sys.argv) > 2:
        stamp = datetime.now(sp.IST).strftime("%Y-%m-%d")
        key = f"news-{stamp}"
        try:
            log = json.load(open(sp.LOG, encoding="utf-8"))
        except (OSError, ValueError):
            log = {}
        if key in log:
            print("already posted today"); return
        txt = os.path.join(sp.OUT, f"{key}.txt")
        if not os.path.exists(txt):
            print("no news card today - nothing to post"); return
        mid = sp.publish(sys.argv[2], open(txt, encoding="utf-8").read())
        if mid:
            log[key] = mid
            with open(sp.LOG, "w", encoding="utf-8") as fh:
                json.dump(log, fh, indent=1, sort_keys=True)
            print("posted", mid)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
