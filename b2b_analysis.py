#!/usr/bin/env python3
"""Analysis over the scraped jeweller rate history, for the B2B report.

Pure computation: takes rows, returns numbers. No Supabase, no Excel, no
network - so every figure in the paid report can be tested directly against
known input, which matters when someone is paying for it.

WHAT THE DATA SUPPORTS, AND WHAT IT DOES NOT

Everything here is derived from `rates` - one published 24K pre-GST figure
per brand per day, scraped from each jeweller's own site. As of 2026-09-29
that is 72 consecutive days with no missing dates, median 21 brands/day.

That supports: per-brand levels and dispersion, rank and how often a brand
is cheapest, the spread across the market, and each brand's premium over
the CROSS-BRAND MEDIAN.

It does NOT support premium over bullion. IBJA is fetched at build time and
rendered, never stored, so there is no daily benchmark series to compare
against and it cannot be backfilled from anything we hold. Any claim of the
form "X% over bullion" would be invented, so this module does not compute
one. That series starts accruing the day something begins storing it.

Nor does it support seasonality or year-on-year: ten weeks is ten samples
per weekday, which is enough to describe the window and not enough to call
a pattern. describe_confidence() exists so the report can say so in its own
voice rather than leaving the reader to assume.
"""
import statistics
from collections import defaultdict
from datetime import date


def _d(s):
    return s if isinstance(s, date) else date.fromisoformat(s)


def build_matrix(rows, brands, active_only=True):
    """-> (dates, {slug: {date: rate}}, excluded) from published rate rows.

    active_only drops brands that are no longer on the board, and it defaults
    to True because this feeds a PAID report.

    The case that forced it: `whp` carries 50 days of published history at
    around 15,664, and that number is not a gold rate. It was read off a 404
    page whose shell happened to contain product prices, which is why the
    brand was deactivated. It sat only +0.83% off the median, so no drift gate
    ever flagged it, and nothing in the stored row marks it as wrong - the
    only record that it is wrong is the fact that the brand was switched off.

    Selling that inside an analysis product would be selling a known-bad
    number. Seven other brands are inactive for the ordinary reason that no
    scrapeable rate could be found; their history is fine but stale, and a
    reader comparing jewellers they can actually buy from is not helped by a
    brand that stopped reporting weeks ago.

    Excluded brands are returned rather than silently dropped, so the report
    can name them and say why the count differs from the live board.
    """
    by_brand = defaultdict(dict)
    names = {b["id"]: b["slug"] for b in brands}
    live = {b["slug"] for b in brands if b.get("active")}
    excluded = set()
    for r in rows:
        if r.get("status") != "published":
            continue
        slug = names.get(r["brand_id"])
        v = r.get("canonical_24k_pre_gst")
        if not slug or v is None:
            continue
        if active_only and slug not in live:
            excluded.add(slug)
            continue
        by_brand[slug][r["rate_date"]] = float(v)
    dates = sorted({d for m in by_brand.values() for d in m})
    return dates, dict(by_brand), sorted(excluded)


def daily_market(dates, matrix):
    """Per day: how many brands, and the min/median/max/spread across them."""
    out = []
    for d in dates:
        vals = [m[d] for m in matrix.values() if d in m]
        if not vals:
            continue
        lo, hi = min(vals), max(vals)
        out.append({
            "date": d, "brands": len(vals),
            "low": lo, "median": statistics.median(vals), "high": hi,
            "spread": round(hi - lo, 2),
            "spread_pct": round((hi - lo) / lo * 100, 3) if lo else 0.0,
        })
    return out


def brand_stats(dates, matrix, market):
    """Per brand over the window, including how often it was cheapest.

    `premium_vs_median_pct` is the mean of the DAILY premium, not the premium
    of the means. Those differ whenever a brand is missing on days when the
    market moved, and the daily mean is the one that answers "what do I
    typically pay here versus the market".
    """
    med = {m["date"]: m["median"] for m in market}
    low = {m["date"]: m["low"] for m in market}
    high = {m["date"]: m["high"] for m in market}
    out = []
    for slug, series in matrix.items():
        ds = sorted(series)
        vals = [series[d] for d in ds]
        if not vals:
            continue
        prem = [(series[d] / med[d] - 1) * 100 for d in ds if med.get(d)]
        cheapest = sum(1 for d in ds if low.get(d) is not None
                       and abs(series[d] - low[d]) < 0.005)
        dearest = sum(1 for d in ds if high.get(d) is not None
                      and abs(series[d] - high[d]) < 0.005)
        # Day-to-day move, as a proxy for how often this jeweller revises.
        moves = [abs(vals[i] - vals[i - 1]) for i in range(1, len(vals))]
        out.append({
            "slug": slug,
            "days": len(ds),
            "coverage_pct": round(len(ds) / len(dates) * 100, 1) if dates else 0,
            "first": ds[0], "last": ds[-1],
            "latest": vals[-1],
            "mean": round(statistics.mean(vals), 2),
            "median": round(statistics.median(vals), 2),
            "min": min(vals), "max": max(vals),
            "stdev": round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,
            "premium_vs_median_pct": round(statistics.mean(prem), 3) if prem else None,
            "days_cheapest": cheapest,
            "pct_days_cheapest": round(cheapest / len(ds) * 100, 1),
            "days_dearest": dearest,
            "pct_days_dearest": round(dearest / len(ds) * 100, 1),
            "avg_daily_move": round(statistics.mean(moves), 2) if moves else 0.0,
            "days_unchanged": sum(1 for m in moves if m < 0.005),
        })
    out.sort(key=lambda r: (r["premium_vs_median_pct"] is None,
                            r["premium_vs_median_pct"]))
    return out


def weekday_pattern(market):
    """Mean market median by weekday.

    Reported with the sample count attached because with ten weeks of data
    each weekday has about ten observations - enough to describe the window,
    not enough to support "Tuesdays are cheaper". The report prints n so the
    reader can judge that for themselves.
    """
    buckets = defaultdict(list)
    for m in market:
        buckets[_d(m["date"]).weekday()].append(m["median"])
    names = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]
    return [{"weekday": names[i], "n": len(buckets[i]),
             "mean_median": round(statistics.mean(buckets[i]), 2),
             "min": min(buckets[i]), "max": max(buckets[i])}
            for i in range(7) if buckets[i]]


def market_trend(market):
    """First/last/high/low of the market median across the window."""
    if not market:
        return {}
    meds = [m["median"] for m in market]
    first, last = meds[0], meds[-1]
    return {
        "from": market[0]["date"], "to": market[-1]["date"],
        "days": len(market),
        "open": first, "close": last,
        "change": round(last - first, 2),
        "change_pct": round((last / first - 1) * 100, 2) if first else 0.0,
        "high": max(meds), "low": min(meds),
        "range_pct": round((max(meds) - min(meds)) / min(meds) * 100, 2),
        "avg_spread": round(statistics.mean(m["spread"] for m in market), 2),
        "widest_spread": max(m["spread"] for m in market),
        "widest_spread_date": max(market, key=lambda m: m["spread"])["date"],
    }


def describe_confidence(dates, matrix, market):
    """Plain statements about what this particular window can and cannot show.

    Printed verbatim into the report. A paid analysis should state its own
    limits rather than let a reader infer depth that is not there.
    """
    n = len(dates)
    notes = [
        f"Window: {dates[0]} to {dates[-1]} ({n} days, no missing dates)."
        if dates else "No data in window.",
        f"Brands per day: median {statistics.median([m['brands'] for m in market])}"
        f", minimum {min(m['brands'] for m in market)}." if market else "",
        "All rates are 24K, pre-GST, per gram, as published by each jeweller "
        "on its own website and scraped daily.",
        "Premium figures compare each jeweller to the median of the other "
        "jewellers on the same day, NOT to a bullion benchmark: no daily "
        "IBJA/spot series is stored, so a premium-over-bullion figure cannot "
        "be computed for past dates and is deliberately absent.",
        f"Weekday averages rest on about {n // 7} observations per weekday. "
        "Treat them as a description of this window, not a seasonal pattern.",
        "A brand absent on a given day was not scrapeable that day (blocked, "
        "site change, or quarantined for failing a sanity check); it is "
        "excluded from that day rather than carried forward.",
        "Only jewellers currently on the live board are included. Brands "
        "since removed are left out even where history exists - one of them "
        "was removed precisely because the figure it published was not a "
        "gold rate.",
    ]
    return [x for x in notes if x]
