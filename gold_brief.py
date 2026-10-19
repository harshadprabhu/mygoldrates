#!/usr/bin/env python3
"""The daily gold market brief: what moved gold, and why, in plain words.

Runs inside every site build. Reads the day's numbers (international gold,
the rupee, the Indian jeweller board) and the gold headlines from around the
world, sorts the headlines into the forces that move gold, and writes a short
analysis for /gold-market-today. No model and no API key: how each force is
read is written down here once, and every number in the brief is one the
build measured. Headlines are quoted as titles with a link to the publisher,
never reproduced.

One page, always current, rather than a new page a day: a fresh dated page
every morning is the thin-content pattern the 2026-10-20 clean-up removed.
Each day's brief is kept in docs/market-brief.json; the page shows the last
week, and the monthly gold rate history pages carry one line per day.
"""
import html
import json
import re
from datetime import date, datetime, timedelta

import requests

UA = "Mozilla/5.0 (compatible; MyGoldRatesBot/1.0; +https://mygoldrates.com)"
STATE = "docs/market-brief.json"
KEEP_DAYS = 400

# The forces that move gold, how each is recognised in a headline, and the
# one-line reading of it. Order matters only for ties.
THEMES = [
    ("rates", "US interest rates",
     r"\b(fed|fomc|federal reserve|powell|rate cut|rate hike|rate-cut|"
     r"interest rate|treasury yield|bond yield|yields)\b",
     "Gold pays no interest, so expectations of lower US rates tend to "
     "support it and higher rates tend to weigh on it."),
    ("dollar", "The US dollar",
     r"\b(dollar|greenback|dxy|dollar index)\b",
     "Gold is priced in dollars: a stronger dollar usually pushes it down, a "
     "weaker one lifts it."),
    ("inflation", "Inflation",
     r"\b(inflation|cpi|pce|ppi|consumer prices)\b",
     "Gold is held as an inflation hedge, though hot inflation can also mean "
     "higher rates, which cuts the other way."),
    ("safe_haven", "Geopolitics and safe-haven buying",
     r"\b(war|conflict|tension|tensions|ceasefire|sanction|sanctions|missile|"
     r"attack|geopolitic\w*|middle east|ukraine|russia|israel|iran|gaza|"
     r"tariff|tariffs|trade war|safe[- ]haven|uncertainty|crisis)\b",
     "Uncertainty sends investors to gold as a store of value."),
    ("central_banks", "Central bank buying",
     r"\b(central bank|central banks|reserves|pboc|people's bank|rbi gold)\b",
     "Central banks have been steady buyers of gold, a large and patient "
     "source of demand."),
    ("investment", "Investment flows (ETFs)",
     r"\b(etf|etfs|holdings|inflows|outflows|spdr)\b",
     "Money moving into or out of gold funds shows what investors are doing "
     "with their own cash."),
    ("india_demand", "Indian demand",
     r"\b(dhanteras|diwali|akshaya|wedding|festive|festival|jewell?ers?|"
     r"jewell?ery demand|import duty|customs duty|gold imports?)\b",
     "Festival and wedding buying, and import costs, move local premiums "
     "and the price on the jeweller board."),
    ("rupee", "The rupee",
     r"\b(rupee|inr|usd/inr)\b",
     "A weaker rupee makes imported gold dearer in India even when the "
     "world price is flat."),
    ("momentum", "Records and profit-taking",
     r"\b(record|all[- ]time high|lifetime high|profit[- ]taking|"
     r"correction|slump|plunge|rally|surge)\b",
     "Big moves feed on themselves for a while, and sharp rallies attract "
     "profit-taking."),
]


def fetch_global_news(limit=40):
    """Gold-market headlines from around the world, last day (Google News
    RSS, English, global edition). Titles and links only."""
    url = ("https://news.google.com/rss/search?q="
           + requests.utils.quote('"gold price" OR "gold prices" OR bullion when:1d')
           + "&hl=en-US&gl=US&ceid=US:en")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    except Exception as e:
        print("brief: global news failed:", type(e).__name__)
        return []
    out, seen = [], set()
    for it in re.findall(r"<item>(.*?)</item>", r.text, re.S):
        def f(tag):
            m = re.search(r"<" + tag + r"[^>]*>(.*?)</" + tag + ">", it, re.S)
            return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
        title, link, src = f("title"), f("link"), f("source")
        if src and title.endswith(" - " + src):
            title = title[:-(len(src) + 3)].strip()
        k = title.lower()
        if title and link and k not in seen and len(title) > 20:
            seen.add(k)
            out.append({"title": title, "link": link, "source": src})
        if len(out) >= limit:
            break
    return out


def classify(headlines):
    """{theme_key: [headline, ...]} for every theme with at least one."""
    out = {}
    for h in headlines:
        t = h["title"].lower()
        for key, _, pat, _ in THEMES:
            if re.search(pat, t):
                out.setdefault(key, []).append(h)
    return out


def _pct(a, b):
    return (a / b - 1) * 100 if a and b else None


def _inr(n):
    digits = str(abs(int(round(n))))
    s = digits
    if len(digits) > 3:
        h, t = digits[:-3], digits[-3:]
        parts = []
        while len(h) > 2:
            parts.insert(0, h[-2:])
            h = h[:-2]
        if h:
            parts.insert(0, h)
        s = ",".join(parts) + "," + t
    return ("-" if n < 0 else "") + "₹" + s


def compose(day, snap, prev, themed, events, spread=None):
    """The brief for `day` as a dict: a one-line summary and paragraphs.

    snap / prev: {"gold_usd", "usdinr", "board24"} for today and the last
    recorded day before it (prev may be None). themed: classify() output.
    events: this week's US calendar entries. spread: today's cheapest-to-
    dearest gap on the board, rupees per gram."""
    paras, summary = [], []

    # 1. The numbers, and where the rupee move came from.
    g, fx, b = snap.get("gold_usd"), snap.get("usdinr"), snap.get("board24")
    pg = prev or {}
    gp, fp, bp = _pct(g, pg.get("gold_usd")), _pct(fx, pg.get("usdinr")), _pct(b, pg.get("board24"))
    bits = []
    if g:
        bits.append(f"International gold is at ${g:,.0f} an ounce"
                    + (f" ({gp:+.2f}% since {pg['date_disp']})" if gp is not None else ""))
    if fx:
        bits.append(f"the rupee at ₹{fx:.2f} to the dollar"
                    + ("" if fp is None or abs(fp) < 0.005 else
                       f" ({'weaker' if fp > 0 else 'stronger'} by {abs(fp):.2f}%)"))
    if b:
        bits.append(f"and the Indian jeweller board median at {_inr(b)}/g for 24K"
                    + (f" ({bp:+.2f}%)" if bp is not None else ""))
    if bits:
        line = ", ".join(bits) + "."
        if gp is not None and fp is not None and (abs(gp) + abs(fp)) > 0.05:
            # In rupees, gold's move is roughly the dollar move plus the
            # rupee's move against the dollar; whichever is larger drove it.
            src = ("the world gold price" if abs(gp) >= abs(fp) else "the rupee")
            line += (f" In rupee terms the move came mostly from {src} "
                     f"({gp:+.2f}% gold, {fp:+.2f}% USD/INR).")
        paras.append(line)
        if gp is not None:
            summary.append(f"gold {gp:+.1f}%")

    # 2. The forces in today's headlines, strongest first.
    ranked = sorted(themed.items(), key=lambda kv: (-len(kv[1]),
                    [t[0] for t in THEMES].index(kv[0])))
    meta = {k: (name, why) for k, name, _, why in THEMES}
    if ranked:
        names = [meta[k][0].lower() for k, _ in ranked[:3]]
        paras.append(
            "What the world's gold news is about today: "
            + ", ".join(f"{meta[k][0]} ({len(v)} headline{'s' if len(v) != 1 else ''})"
                        for k, v in ranked[:4]) + ".")
        for k, hs in ranked[:3]:
            name, why = meta[k]
            cites = "; ".join(
                f'<a href="{html.escape(h["link"])}" rel="nofollow noopener" '
                f'target="_blank">{html.escape(h["title"])}</a>'
                + (f" ({html.escape(h['source'])})" if h.get("source") else "")
                for h in hs[:2])
            paras.append(f"<strong>{html.escape(name)}.</strong> {html.escape(why)} "
                         f"In the news: {cites}.")
        summary.append("news led by " + names[0])
    else:
        paras.append("No clear theme in today's gold headlines.")

    # 3. What is scheduled.
    hi = [e for e in events or [] if (e.get("impact") or "").lower() == "high"]
    if hi:
        names = []
        for e in hi:
            if e["title"] not in names:
                names.append(e["title"])
        paras.append("High-impact US data due this week: "
                     + html.escape(", ".join(names[:4]))
                     + (f" and {len(names) - 4} more" if len(names) > 4 else "")
                     + ". Gold often moves sharply around these releases; "
                       "which way is not knowable in advance.")

    # 4. For someone buying in India today.
    if spread:
        paras.append(
            f"For buyers: the gap between the cheapest and dearest jeweller "
            f"on our board is {_inr(spread)}/g today, and making charges "
            f"usually differ by more than a day's price move. Compare the "
            f'<a href="https://mygoldrates.com/">live rates</a> and the '
            f'<a href="https://mygoldrates.com/making-charges-comparison">making '
            f"charges</a> before you buy.")

    return {"date": day.isoformat(), "summary": ", ".join(summary),
            "paragraphs": paras,
            "themes": {k: len(v) for k, v in themed.items()},
            "snap": snap}


def load(path=STATE):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"days": {}}


def save(state, path=STATE):
    days = state.get("days", {})
    cutoff = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
    state["days"] = {k: v for k, v in days.items() if k >= cutoff}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False, sort_keys=True)


def previous(state, day):
    """The latest recorded day strictly before `day`, as a snapshot with a
    display date."""
    earlier = sorted(k for k in state.get("days", {}) if k < day.isoformat())
    if not earlier:
        return None
    k = earlier[-1]
    snap = dict(state["days"][k].get("snap") or {})
    snap["date_disp"] = datetime.fromisoformat(k).strftime("%d %b")
    return snap
