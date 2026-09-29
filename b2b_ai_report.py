#!/usr/bin/env python3
"""AI-written commentary for the B2B report, over pre-computed facts only.

MODEL AND COST
  claude-opus-5-5, adaptive thinking, effort high. One report per day serves
  every subscriber - the analysis is the same for all of them - so the cost
  is per DAY, not per subscriber. At roughly 3K input and 2K output tokens
  including thinking, that is about $0.05 a day, near Rs 130/month TOTAL
  regardless of how many jewellers subscribe. Worth knowing against a
  Rs 50/month price: the AI commentary pays for itself at about three
  subscribers, and costs no more at three hundred.

THE CONSTRAINT THAT SHAPES THIS FILE

The model is never shown raw data and asked to analyse it. It is shown
FACTS ALREADY COMPUTED by b2b_analysis - which is pure, deterministic and
separately tested - and asked to write them up. A language model asked to
find patterns in 72 days of prices will find some, state them fluently, and
be wrong in a way a jeweller cannot check.

Then the output is VALIDATED before anyone sees it: every rupee figure in
the generated text must be traceable to the facts it was given. Anything
else is an invented number, and the report is withheld rather than shipped.
This is the same discipline as the rest of this codebase - a fabricated rate
read off a 404 page got published for weeks because it looked plausible.
Fluent prose is better at looking plausible than a scraper ever was.
"""
import json
import os
import re
import sys

MODEL = "claude-opus-5-5"

SYSTEM = """You write a short daily market note for Indian jewellery retailers, \
published as part of a paid analysis product.

You are given FACTS as JSON. They were computed from scraped data by code. \
You are writing them up - you are not analysing raw data and not estimating \
anything.

Rules, in order of importance:

1. Use ONLY numbers present in the FACTS. Never introduce a figure that is \
not there, and never round one into a different number. If you want to say \
something the facts do not support, say instead that the data does not show \
it.
2. The facts describe a specific window. Do not imply a longer history, a \
seasonal pattern, or a forecast. There is no bullion benchmark in this data, \
so never describe any premium as being "over bullion" or "over spot" - the \
premiums given are against the median of the other jewellers that day.
3. Write for someone deciding today's counter price. Lead with what changed \
and what it means for their margin, not with a description of the dataset.
4. Be plain. No hype, no "significant"/"remarkable" unless the number earns \
it. If the market barely moved, say so.
5. 200-300 words, in short paragraphs. No headings, no bullet lists, no \
markdown. Plain prose that will be pasted into a spreadsheet cell.
6. Close with one sentence naming the single most useful thing in the facts \
for a jeweller today."""


def facts_from(ctx, limit_brands=8):
    """Compact, already-computed facts. Nothing raw, nothing inferred.

    Trimmed to the brands at each end of the range: the full 21-brand table
    is in the workbook, and sending all of it spends input tokens on rows
    the note will never mention.
    """
    t, stats = ctx["trend"], ctx["stats"]
    cheap = stats[:limit_brands // 2]
    dear = stats[-(limit_brands // 2):]
    latest = ctx["market"][-1]
    prev = ctx["market"][-2] if len(ctx["market"]) > 1 else None
    return {
        "window": {"from": t["from"], "to": t["to"], "days": t["days"],
                   "jewellers": len(stats)},
        "market": {
            "median_first_day": t["open"], "median_last_day": t["close"],
            "change": t["change"], "change_pct": t["change_pct"],
            "high": t["high"], "low": t["low"], "range_pct": t["range_pct"],
            "avg_spread": t["avg_spread"], "widest_spread": t["widest_spread"],
            "widest_spread_date": str(t["widest_spread_date"]),
        },
        "today": {
            "date": str(latest["date"]), "jewellers": latest["brands"],
            "cheapest": latest["low"], "median": latest["median"],
            "dearest": latest["high"], "spread": latest["spread"],
        },
        "yesterday": ({"median": prev["median"], "spread": prev["spread"],
                       "median_change": round(latest["median"] - prev["median"], 2)}
                      if prev else None),
        "cheapest_jewellers": [
            {"brand": s["slug"], "latest": s["latest"],
             "avg_premium_vs_market_pct": s["premium_vs_median_pct"],
             "pct_days_cheapest": s["pct_days_cheapest"]} for s in cheap],
        "dearest_jewellers": [
            {"brand": s["slug"], "latest": s["latest"],
             "avg_premium_vs_market_pct": s["premium_vs_median_pct"]}
            for s in dear],
        "not_in_this_data": [
            "any bullion or spot benchmark, so no premium-over-bullion",
            "any period before " + str(t["from"]),
            "making charges beyond the separate sheet",
        ],
    }


# Rupee-scale figures: a per-gram gold rate or a spread. These are the
# numbers a jeweller would act on, so these are the ones that must be
# traceable. Percentages and small integers are routinely and legitimately
# derived in prose ("about a third of days"), so they are not policed here.
# The lookbehind must exclude a comma as well as a digit: without it,
# "14,889" matches the fragment "889", which is not a figure anyone wrote and
# would be checked against the facts as if it were. The first comma group is
# 1-3 digits so both Western (14,889) and Indian (1,04,889) grouping parse.
_RUPEE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:,\d{2,3})+|\d{3,7})(?:\.(\d{1,2}))?(?![\d,%])")


def _numbers_in(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers_in(v, out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.add(round(float(obj), 2))
    return out


def untraceable_figures(text, facts, tol=1.0):
    """Rupee-scale numbers in the note that are not in the facts.

    Tolerance of 1 rupee absorbs honest rounding ("about 14,890"). A match
    against the integer part is also accepted, so "Rs 14,889" matches
    14889.0 and "480" matches 479.89.
    """
    known = _numbers_in(facts)
    known_int = {int(k) for k in known}
    bad = []
    for m in _RUPEE.finditer(text):
        raw = m.group(0).replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        if v < 100:            # counts, day numbers, small ordinals
            continue
        if any(abs(v - k) <= tol for k in known):
            continue
        if int(v) in known_int:
            continue
        bad.append(m.group(0))
    return bad


def write_note(facts, api_key=None):
    """-> (text, usage). Raises if the SDK or key is unavailable."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        # Explicit: Opus 5.5 defaults to medium, and this is the one part of
        # the product a subscriber reads as judgement rather than data.
        output_config={"effort": "high"},
        messages=[{"role": "user",
                   "content": "FACTS:\n" + json.dumps(facts, indent=1, default=str)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, resp.usage


def generate(ctx, api_key=None):
    """-> dict with the note, or with a refusal and why.

    Never returns unvalidated prose. If a figure cannot be traced back to the
    computed facts, the note is withheld: a paid report that quotes a made-up
    rate is worse than one with no commentary.
    """
    facts = facts_from(ctx)
    try:
        text, usage = write_note(facts, api_key)
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {str(e)[:200]}",
                "note": None}
    bad = untraceable_figures(text, facts)
    if bad:
        return {"ok": False, "reason": "untraceable figures in generated note: "
                + ", ".join(bad[:6]), "note": None, "draft": text}
    return {"ok": True, "note": text, "facts": facts,
            "usage": {"input": getattr(usage, "input_tokens", None),
                      "output": getattr(usage, "output_tokens", None)}}
