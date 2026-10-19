#!/usr/bin/env python3
"""The day's Jewellers Digest issue as JSON, for the members-only web page.

The workbook and this JSON carry the same analysis; the JSON is what
/jd-today renders. Pure: no I/O here. jd_report.py builds it alongside the
workbook and uploads it to the same PRIVATE bucket, and the JD Worker hands
it only to a signed-in account whose access is current.
"""
import statistics


def board(dates, matrix, names):
    """Latest day's rate per jeweller, cheapest first, with its premium over
    that day's median."""
    if not dates:
        return []
    last = dates[-1]
    today = {s: m[last] for s, m in matrix.items() if last in m}
    if not today:
        return []
    med = statistics.median(today.values())
    rows = [{"n": names.get(s, s), "v": round(v, 2),
             "p": round((v / med - 1) * 100, 2) if med else 0.0}
            for s, v in today.items()]
    return sorted(rows, key=lambda r: r["v"])


def build(dates, matrix, market, stats, trend, notes, weekday, outlook,
          ai, making, names, excluded, generated, disclaimer):
    """Everything the issue page shows, in one plain dict."""
    return {
        "generated": generated,
        "last": dates[-1] if dates else None,
        "trend": trend,
        "excluded": [names.get(s, s) for s in excluded],
        "series": [{"d": m["date"], "lo": round(m["low"], 1),
                    "md": round(m["median"], 1), "hi": round(m["high"], 1)}
                   for m in market],
        "board": board(dates, matrix, names),
        "stats": [{"n": names.get(s["slug"], s["slug"]),
                   "cov": s["coverage_pct"], "med": s["median"],
                   "prem": s["premium_vs_median_pct"],
                   "cheap": s["pct_days_cheapest"],
                   "move": s["avg_daily_move"], "sd": s["stdev"]}
                  for s in sorted(stats, key=lambda s: (
                      s["premium_vs_median_pct"] is None,
                      s["premium_vs_median_pct"] or 0))],
        "weekday": weekday,
        "confidence": [n for n in notes if n],
        "outlook": outlook,
        "note": ai["note"] if ai and ai.get("ok") else None,
        "making": making,
        "disclaimer": disclaimer,
    }
