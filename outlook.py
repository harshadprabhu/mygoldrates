#!/usr/bin/env python3
"""Market outlook for the Indian gold board: direction, levels, and size.

WHAT THIS IS, AND WHAT IT IS NOT

This is a description of current market structure for people who buy metal
for a living - trend, momentum, where price has repeatedly turned, and how
far it typically travels in a week. It is not investment advice and it is
not a forecast anyone should trade on. Every number here is computed from
observed prices and carries its own sample size, so a reader can see how
much weight it deserves.

THE TWO SERIES, AND WHY BOTH ARE NEEDED

The Indian retail board is not the international price. Over the window we
hold, the board sits about 15% above international parity (duty plus a
domestic premium) and, more importantly, it MOVES DIFFERENTLY: it is sticky.
Measured on our own rate history, the same-day correlation between the
board and international parity is only about 0.35, but at a ONE-DAY LAG it
is about 0.71. Over ten-day windows it reaches 0.95, with roughly 80% of an
international move eventually arriving.

So the technical work runs on the international series - which has years of
real OHLC and sets the direction - and the result is translated onto the
board through a measured ratio and a measured pass-through, both reported
with their own dispersion. Running technicals on 72 days of sticky retail
quotes would produce confident nonsense.

EVERYTHING DEGRADES RATHER THAN GUESSES

If a feed is down, the section that needed it is omitted and says so. An
outlook with a missing piece is honest; an outlook with an invented piece
is worse than none, because it looks the same as a real one.
"""
import bisect
import json
import math
import os
import statistics as st
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

OZ_GRAMS = 31.1034768

MARKET_API = os.environ.get(
    "MARKET_API_BASE",
    "https://mygoldrates-market-api.harshads-priority.workers.dev")
FX_API = "https://api.frankfurter.dev/v1"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# NOT under docs/. Everything in docs/ is published to mygoldrates.com, and
# this analysis is a paid Jewellers Digest deliverable, not public copy. It
# is written to a build-local path and consumed by jd_report.py.
OUT = os.environ.get("OUTLOOK_OUT", "build/outlook.json")


# ─── plumbing ────────────────────────────────────────────────────────────

def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        # The market Worker only answers cross-origin for known sites; it
        # answers a server-side call either way, but sending the Origin it
        # expects keeps this path identical to the browser's.
        "Origin": "https://mygoldrates.com",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# ─── indicators ──────────────────────────────────────────────────────────
# Each takes a plain list of floats, oldest first, and returns a list the
# same length with None where there is not yet enough history. Keeping the
# length aligned means an index into the price series is an index into every
# indicator, and an off-by-one cannot silently shift a signal by a day.

def sma(xs, n):
    out, run = [], 0.0
    for i, v in enumerate(xs):
        run += v
        if i >= n:
            run -= xs[i - n]
        out.append(run / n if i >= n - 1 else None)
    return out


def ema(xs, n):
    if not xs:
        return []
    k = 2.0 / (n + 1)
    out = [None] * len(xs)
    if len(xs) < n:
        return out
    seed = sum(xs[:n]) / n
    out[n - 1] = seed
    prev = seed
    for i in range(n, len(xs)):
        prev = xs[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _rsi_from(ag, al):
    """RSI from average gain and average loss.

    Both zero means the price did not move at all over the window, which
    carries no directional information - so 50, the midpoint. The obvious
    `100 if al == 0` shortcut gets this exactly backwards and reads a
    stalled feed repeating one price as maximum bullish, which is the worst
    possible answer to give about a feed that has stopped.
    """
    if al == 0:
        return 50.0 if ag == 0 else 100.0
    return 100 - 100 / (1 + ag / al)


def rsi(xs, n=14):
    """Wilder's RSI. Not the naive rolling-mean version - the smoothing is
    the whole definition, and the two disagree by several points."""
    out = [None] * len(xs)
    if len(xs) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = xs[i] - xs[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / n, losses / n
    out[n] = _rsi_from(ag, al)
    for i in range(n + 1, len(xs)):
        d = xs[i] - xs[i - 1]
        ag = (ag * (n - 1) + max(d, 0.0)) / n
        al = (al * (n - 1) + max(-d, 0.0)) / n
        out[i] = _rsi_from(ag, al)
    return out


def macd(xs, fast=12, slow=26, sig=9):
    ef, es = ema(xs, fast), ema(xs, slow)
    line = [None if (a is None or b is None) else a - b for a, b in zip(ef, es)]
    solid = [v for v in line if v is not None]
    off = len(line) - len(solid)
    sl = ema(solid, sig)
    signal = [None] * off + sl
    hist = [None if (a is None or b is None) else a - b
            for a, b in zip(line, signal)]
    return line, signal, hist


def true_range(bars):
    out = [None]
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
        out.append(max(h - l, abs(h - pc), abs(l - pc)))
    return out


def atr(bars, n=14):
    tr = true_range(bars)
    out = [None] * len(bars)
    if len(bars) <= n:
        return out
    seed = sum(tr[1:n + 1]) / n
    out[n] = seed
    prev = seed
    for i in range(n + 1, len(bars)):
        prev = (prev * (n - 1) + tr[i]) / n
        out[i] = prev
    return out


# ─── support and resistance ──────────────────────────────────────────────

def swing_points(bars, k=5):
    """Fractal swing highs and lows: a bar whose high is the highest, or low
    the lowest, of the 2k+1 bars centred on it.

    k=5 means a level has to survive a week either side to count, which is
    what keeps this from marking every wiggle as a level."""
    highs, lows = [], []
    for i in range(k, len(bars) - k):
        w = bars[i - k:i + k + 1]
        if bars[i]["h"] >= max(b["h"] for b in w):
            highs.append((i, bars[i]["h"]))
        if bars[i]["l"] <= min(b["l"] for b in w):
            lows.append((i, bars[i]["l"]))
    return highs, lows


def cluster_levels(points, tol, bars):
    """Collapse nearby swing points into zones.

    A level that price turned at four separate times is worth more than one
    it touched once, and that only shows up if near-identical pivots are
    counted as the same level rather than four. `tol` is an absolute price
    width - pass a fraction of ATR so the tolerance scales with how much the
    market is actually moving.
    """
    if not points:
        return []
    zones = []
    for idx, price in sorted(points, key=lambda p: p[1]):
        if zones and price - zones[-1]["prices"][-1] <= tol:
            zones[-1]["prices"].append(price)
            zones[-1]["idx"].append(idx)
        else:
            zones.append({"prices": [price], "idx": [idx]})
    out = []
    last_i = len(bars) - 1
    for z in zones:
        newest = max(z["idx"])
        out.append({
            "price": round(st.mean(z["prices"]), 2),
            "touches": len(z["prices"]),
            "last_touch": bars[newest]["d"],
            "bars_ago": last_i - newest,
        })
    return out


def levels_around(bars, price, atr_now, k=5, tol_atr=0.75, want=3,
                  lookback=260):
    """The nearest few zones below and above, strongest first.

    Only the last `lookback` bars are searched. This is not an optimisation:
    gold traded near Rs 4,800/g in 2021, and a cluster of seventy pivots
    down there is not support for a market at Rs 12,800 - it is a different
    price regime. Searching five years and ranking by touch count surfaces
    exactly that kind of archaeology, confidently labelled. A year of
    history is the most that can still be called a level.

    Within the window, ranking is by distance first, with a CAPPED bonus for
    how often price actually turned there and a small penalty for staleness.
    The cap matters: without it one heavily-tested zone outranks everything
    nearer simply by having been touched more times.
    """
    if not bars or not atr_now:
        return [], []
    window = bars[-lookback:] if len(bars) > lookback else bars
    highs, lows = swing_points(window, k)
    tol = atr_now * tol_atr
    zones = cluster_levels(highs + lows, tol, window)
    below = [z for z in zones if z["price"] < price]
    above = [z for z in zones if z["price"] > price]
    span = max(len(window), 1)

    def rank(z, dist):
        return (dist / max(atr_now, 1e-9)
                - 0.5 * min(z["touches"], 4)
                + z["bars_ago"] / span)

    below.sort(key=lambda z: rank(z, price - z["price"]))
    above.sort(key=lambda z: rank(z, z["price"] - price))
    for z in below:
        z["distance_pct"] = round((price - z["price"]) / price * -100, 2)
    for z in above:
        z["distance_pct"] = round((z["price"] - price) / price * 100, 2)
    return below[:want], above[:want]


def pivot_points(bars, n=21):
    """Classic floor-trader pivots off the last n bars, as a cross-check.

    Swing pivots say where price actually turned; floor pivots say where a
    lot of desks will be watching. When the two agree on a level, it is
    worth more than either alone.
    """
    if len(bars) < n:
        return None
    w = bars[-n:]
    h, l, c = max(b["h"] for b in w), min(b["l"] for b in w), w[-1]["c"]
    p = (h + l + c) / 3
    return {
        "pivot": round(p, 2),
        "r1": round(2 * p - l, 2), "s1": round(2 * p - h, 2),
        "r2": round(p + (h - l), 2), "s2": round(p - (h - l), 2),
        "window_bars": n,
    }


# ─── magnitude ───────────────────────────────────────────────────────────

def expected_range(closes, atr_now, price, horizons=(1, 5, 21)):
    """How far price typically travels, from how far it actually has.

    Two independent estimates per horizon, because they fail differently:
    sigma scaled by root-time assumes moves are independent (they are not,
    quite), while the empirical quantile of past moves over that exact
    horizon assumes the future resembles the sample. Where they disagree,
    the reader can see it rather than being handed one number.
    """
    out = []
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    if len(rets) < 30:
        return out
    daily_sd = st.pstdev(rets[-120:] if len(rets) >= 120 else rets)
    for h in horizons:
        moves = [abs(closes[i] / closes[i - h] - 1)
                 for i in range(h, len(closes))]
        moves = moves[-250:] if len(moves) >= 250 else moves
        if len(moves) < 20:
            continue
        moves_sorted = sorted(moves)
        typical = moves_sorted[int(len(moves_sorted) * 0.68)]
        sigma = daily_sd * math.sqrt(h)
        out.append({
            "days": h,
            "sigma_pct": round(sigma * 100, 2),
            "sigma_rupees": round(price * sigma, 0),
            "observed_68_pct": round(typical * 100, 2),
            "observed_68_rupees": round(price * typical, 0),
            "n": len(moves),
        })
    if atr_now:
        out.append({
            "days": 1, "label": "atr",
            "atr_rupees": round(atr_now, 0),
            "atr_pct": round(atr_now / price * 100, 2),
        })
    return out


# ─── seasonality ─────────────────────────────────────────────────────────

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def month_seasonality(bars, month):
    """Mean return for one calendar month across the years we hold.

    India's festival and wedding buying peaks from Navratri through Diwali,
    and jewellers ask about it constantly. Five years is five observations,
    which is not enough to call a seasonal pattern - so the sample size and
    the spread ship WITH the number, and the reader can discount it. The
    alternative, asserting a festival effect because it is common knowledge,
    is how a product ends up confidently wrong.
    """
    by_year = {}
    for b in bars:
        y, m = int(b["d"][:4]), int(b["d"][5:7])
        if m == month:
            by_year.setdefault(y, []).append(b)
    rets = []
    for y, bs in sorted(by_year.items()):
        if len(bs) < 10:      # a stub of a month is not a month
            continue
        rets.append({"year": y,
                     "return_pct": round((bs[-1]["c"] / bs[0]["c"] - 1) * 100, 2)})
    if len(rets) < 3:
        return {"month": MONTHS[month - 1], "n": len(rets),
                "note": "too few years to say anything"}
    vals = [r["return_pct"] for r in rets]
    return {
        "month": MONTHS[month - 1],
        "n": len(vals),
        "mean_pct": round(st.mean(vals), 2),
        "median_pct": round(st.median(vals), 2),
        "stdev_pct": round(st.pstdev(vals), 2),
        "positive_years": sum(1 for v in vals if v > 0),
        "years": rets,
    }


# ─── board pass-through ──────────────────────────────────────────────────

def _corr(a, b):
    if len(a) < 8:
        return None
    ma, mb = st.mean(a), st.mean(b)
    sa, sb = st.pstdev(a), st.pstdev(b)
    if not sa or not sb:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / len(a) / (sa * sb)


def _beta(y, x):
    if len(x) < 8:
        return None
    mx, my = st.mean(x), st.mean(y)
    vx = sum((v - mx) ** 2 for v in x)
    if not vx:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / vx


def passthrough(board, parity, max_lag=4):
    """How an international move reaches the Indian retail board.

    `board` and `parity` are aligned lists of (date, level). The answer that
    matters is which LAG fits best: if the board follows with a one-day lag,
    then today's international close is already information about tomorrow's
    board, and that is a forecast with a coefficient rather than a hunch.
    """
    if len(board) < 20 or len(board) != len(parity):
        return None
    db = [board[i][1] / board[i - 1][1] - 1 for i in range(1, len(board))]
    dp = [parity[i][1] / parity[i - 1][1] - 1 for i in range(1, len(parity))]
    lags = []
    for lag in range(max_lag + 1):
        y = db[lag:]
        x = dp[:len(dp) - lag] if lag else dp
        n = min(len(y), len(x))
        c, bt = _corr(y[:n], x[:n]), _beta(y[:n], x[:n])
        if c is None or bt is None:
            continue
        lags.append({"lag_days": lag, "corr": round(c, 3),
                     "beta": round(bt, 3), "n": n})
    windows = []
    for k in (5, 10):
        if len(board) <= k + 8:
            continue
        y = [board[i][1] / board[i - k][1] - 1 for i in range(k, len(board))]
        x = [parity[i][1] / parity[i - k][1] - 1 for i in range(k, len(parity))]
        c, bt = _corr(y, x), _beta(y, x)
        if c is not None and bt is not None:
            windows.append({"window_days": k, "corr": round(c, 3),
                            "beta": round(bt, 3), "n": len(y)})
    ratios = [b[1] / p[1] for b, p in zip(board, parity) if p[1]]
    # The premium is reported even when no correlation can be computed. A
    # stretch where one series does not move leaves the regression
    # undefined, but the gap between the two is still perfectly measurable,
    # and throwing it away because a different number was undefined would
    # blank the translation that every level on the page depends on.
    return {
        "lags": lags,
        "best_lag": max(lags, key=lambda r: r["corr"]) if lags else None,
        "windows": windows,
        "board_over_parity": {
            "median": round(st.median(ratios), 4),
            "stdev": round(st.pstdev(ratios), 4),
            "min": round(min(ratios), 4),
            "max": round(max(ratios), 4),
            "n": len(ratios),
        } if ratios else None,
    }


# ─── stance ──────────────────────────────────────────────────────────────
# Every component is scored to [-1, +1] and carries its own weight, and the
# components ship with the verdict. A single "BULLISH" with nothing behind
# it is a horoscope; the same word with six numbers under it is a claim a
# reader can check and disagree with.

def _clamp(v, lo=-1.0, hi=1.0):
    return max(lo, min(hi, v))


def stance(bars, fx_closes=None):
    closes = [b["c"] for b in bars]
    if len(closes) < 210:
        return None
    price = closes[-1]
    s50, s200 = sma(closes, 50), sma(closes, 200)
    a = atr(bars, 14)
    atr_now = a[-1]
    r = rsi(closes, 14)[-1]
    _, _, hist = macd(closes)
    comps = []

    # 1. Where price sits relative to its 50-day mean, measured in ATR so a
    #    quiet market and a violent one are not scored on the same scale.
    if s50[-1] and atr_now:
        z = (price - s50[-1]) / atr_now
        comps.append({"name": "Price vs 50-day", "weight": 0.22,
                      "score": round(_clamp(z / 2.5), 3),
                      "detail": f"{(price / s50[-1] - 1) * 100:+.2f}% "
                                f"({z:+.2f} ATR)"})

    # 2. The 50/200 relationship - the slowest signal here, and the one that
    #    stays right longest when it is right.
    if s50[-1] and s200[-1]:
        gap = (s50[-1] / s200[-1] - 1)
        comps.append({"name": "50-day vs 200-day", "weight": 0.20,
                      "score": round(_clamp(gap / 0.06), 3),
                      "detail": f"{gap * 100:+.2f}% apart"})

    # 3. RSI as DIRECTION only, from the 50 line. An RSI of 78 is not four
    #    times as bullish as 57; it is a stretched market that mean-reverts
    #    as often as it runs. The stretch is handled as conviction below,
    #    not as extra bullishness here.
    if r is not None:
        comps.append({"name": "RSI (14)", "weight": 0.15,
                      "score": round(_clamp((r - 50) / 20), 3),
                      "detail": f"{r:.1f}"})

    # 4. MACD histogram: sign for direction, slope for whether it is
    #    building or fading.
    h = [v for v in hist if v is not None]
    if len(h) >= 5 and atr_now:
        rising = h[-1] > h[-4]
        comps.append({"name": "MACD momentum", "weight": 0.15,
                      "score": round(_clamp(h[-1] / (atr_now * 0.8)), 3),
                      "detail": ("histogram " + ("rising" if rising else "fading")
                                 + f" at {h[-1]:+.1f}")})

    # 5. Twenty-day rate of change, normalised by this market's own vol.
    if len(closes) > 21:
        rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        sd = st.pstdev(rets[-120:]) or 1e-9
        roc = closes[-1] / closes[-21] - 1
        comps.append({"name": "20-day change", "weight": 0.13,
                      "score": round(_clamp(roc / (sd * math.sqrt(21) * 1.5)), 3),
                      "detail": f"{roc * 100:+.2f}%"})

    # 6. The rupee. Gold can be flat in dollars and still rise on an Indian
    #    board because the rupee slipped - this is the driver a purely
    #    international read misses, and it is half the answer some weeks.
    if fx_closes and len(fx_closes) >= 60:
        f50 = sma(fx_closes, 50)[-1]
        if f50:
            gap = fx_closes[-1] / f50 - 1
            comps.append({"name": "Rupee (USD/INR)", "weight": 0.15,
                          "score": round(_clamp(gap / 0.02), 3),
                          "detail": (f"{fx_closes[-1]:.2f}, {gap * 100:+.2f}% "
                                     f"vs 50-day")})

    if not comps:
        return None
    tw = sum(c["weight"] for c in comps)
    score = sum(c["score"] * c["weight"] for c in comps) / tw * 100

    if score >= 40:
        label, short = "Bullish", "up"
    elif score >= 15:
        label, short = "Mildly bullish", "up"
    elif score > -15:
        label, short = "Neutral", "flat"
    elif score > -40:
        label, short = "Mildly bearish", "down"
    else:
        label, short = "Bearish", "down"

    # Conviction, kept as its parts rather than one opaque number.
    #
    # Agreement is how aligned the components are: six signals pointing the
    # same way is a more robust read than three each way. Penalties are
    # separate and multiplicative, because they say something different -
    # the call may be well-supported AND still likely to snap back.
    #
    # These are not collapsed into a single figure alone, because a strong
    # trend maximises agreement, so a lone conviction number would be
    # highest in exactly the melt-up where a reversal hurts most. Showing
    # the penalty beside the agreement lets a reader see both.
    scores = [c["score"] for c in comps]
    agreement = _clamp(1 - (st.pstdev(scores) if len(scores) > 1 else 0), 0.0, 1.0)
    penalties, caveats = [], []
    if r is not None and r >= 70:
        penalties.append({"factor": 0.75, "reason": "stretched"})
        caveats.append(f"RSI at {r:.0f} is stretched; strength this far above "
                       "the 50 line has historically faded as often as it ran")
    if r is not None and r <= 30:
        penalties.append({"factor": 0.75, "reason": "washed out"})
        caveats.append(f"RSI at {r:.0f} is washed out; a bounce from here is "
                       "as common as a continuation")
    if atr_now:
        apct = [x / c * 100 for x, c in zip(a[-250:], closes[-250:]) if x]
        if apct and atr_now / price * 100 > st.median(apct) * 1.3:
            penalties.append({"factor": 0.8, "reason": "unusually wide range"})
            caveats.append("daily range is well above its own recent norm, so "
                           "levels are being cut through rather than respected")
    conviction = agreement
    for pen in penalties:
        conviction *= pen["factor"]
    return {
        "label": label, "direction": short,
        "score": round(score, 1),
        "conviction": round(conviction, 2),
        "agreement": round(agreement, 2),
        "penalties": penalties,
        "components": comps,
        "caveats": caveats,
    }


# ─── what moved it: gold, or the rupee ───────────────────────────────────

def decompose(usd_closes, fx_closes, days=20):
    """Split the INR move into its dollar-gold part and its rupee part.

    A jeweller who knows the board rose 3% still does not know whether to
    expect more: 3% from the dollar price is a gold story, 3% from the rupee
    is an FX story, and they turn for different reasons. The two legs are
    multiplicative, so they are decomposed in log space and the residual is
    the cross term, which is tiny and folded into the total.
    """
    if len(usd_closes) <= days or len(fx_closes) <= days:
        return None
    gu = usd_closes[-1] / usd_closes[-1 - days] - 1
    gf = fx_closes[-1] / fx_closes[-1 - days] - 1
    total = (1 + gu) * (1 + gf) - 1
    lu, lf = math.log1p(gu), math.log1p(gf)
    tot_l = lu + lf
    share = abs(lu) / (abs(lu) + abs(lf)) if (lu or lf) else 0.5
    return {
        "days": days,
        "total_pct": round(total * 100, 2),
        "gold_usd_pct": round(gu * 100, 2),
        "rupee_pct": round(gf * 100, 2),
        "gold_share_of_move": round(share, 2),
        "driver": ("gold" if share >= 0.65 else
                   "rupee" if share <= 0.35 else "both"),
        "_log_total": round(tot_l, 6),
    }


# ─── scheduled event risk ────────────────────────────────────────────────

HIGH_IMPACT = (
    "fomc", "federal funds", "interest rate", "rate decision", "cpi",
    "inflation", "non-farm", "nonfarm", "payroll", "unemployment",
    "employment", "jobless", "gdp", "ppi", "pce", "ism", "jolts",
)
# "FOMC Member Someone Speaks" fires several times a week, moves nothing,
# and would crowd out the releases that do. Matched on the word, not the
# impact rating, because the feed rates some of them Medium.
EVENT_NOISE = ("speaks", "speech", "member")


def _event_date(raw):
    """The calendar feed dates as MM-DD-YYYY; other sources use ISO.

    Accept both. Silently dropping every event because of a date format is
    exactly the kind of failure that looks like "a quiet week" instead of
    like a bug - this had already swallowed a payrolls print once.
    """
    raw = (raw or "").strip()[:10]
    for parse in (
        lambda r: date.fromisoformat(r),
        lambda r: date(int(r[6:10]), int(r[0:2]), int(r[3:5])),
    ):
        try:
            return parse(raw)
        except (ValueError, IndexError):
            continue
    return None


def event_risk(calendar, within_days=7, today=None):
    """Scheduled releases that reliably move gold.

    This does not forecast the releases - nobody here knows what payrolls
    will print. It flags WHEN the market is due to be repriced, which is the
    part a buyer can act on: a level that held all week means less the
    morning of an inflation print or a jobs report.

    High-impact entries are always kept. Medium ones only when the title
    names something that actually moves metal, which in practice is the
    employment and inflation series.
    """
    if not calendar:
        return []
    today = today or date.today()
    horizon = today + timedelta(days=within_days)
    out = []
    for ev in calendar:
        d = _event_date(ev.get("date") or ev.get("day"))
        if not d or not (today <= d <= horizon):
            continue
        title = (ev.get("title") or ev.get("event") or "").strip()
        low = title.lower()
        if any(k in low for k in EVENT_NOISE):
            continue
        impact = (ev.get("impact") or "").strip().lower()
        keyword = any(k in low for k in HIGH_IMPACT)
        if not (impact == "high" or (impact == "medium" and keyword)
                or (not impact and keyword)):
            continue
        out.append({
            "date": d.isoformat(),
            "title": title,
            "impact": impact or "unrated",
            "country": ev.get("country") or ev.get("ccy") or "",
            "time": ev.get("time") or "",
            "days_away": (d - today).days,
        })
    # Keep every high-impact release in the window first, then fill the
    # remaining slots with the medium ones by date. Sorting by date alone
    # and truncating would drop Friday's payrolls to make room for
    # Tuesday's job openings, which is the wrong way round.
    out.sort(key=lambda e: (e["date"], e["title"]))
    high = [e for e in out if e["impact"] == "high"]
    rest = [e for e in out if e["impact"] != "high"]
    keep = high + rest[:max(0, 10 - len(high))]
    keep.sort(key=lambda e: (e["date"], e["impact"] != "high", e["title"]))
    return keep


# ─── feeds ───────────────────────────────────────────────────────────────

def fetch_gold(range_="5y"):
    """Daily gold bars in USD/oz, through our own market Worker.

    Not straight from Yahoo: the Worker already caches this, is the same
    source the live page reads (so the page and this file cannot disagree
    about what the price is), and Yahoo rate-limits shared egress IPs that
    a CI runner very much has.
    """
    j = _get(f"{MARKET_API}/chart?sym=XAU&interval=1d&range={range_}")
    bars = []
    for c in j.get("candles", []):
        if not c.get("c"):
            continue
        d = datetime.fromtimestamp(c["t"], timezone.utc).date().isoformat()
        bars.append({"d": d, "o": c["o"] or c["c"], "h": c["h"] or c["c"],
                     "l": c["l"] or c["c"], "c": c["c"]})
    bars.sort(key=lambda b: b["d"])
    return bars


def fetch_fx(start, end):
    """USD/INR daily from the ECB series (Frankfurter). No key, no quota."""
    j = _get(f"{FX_API}/{start}..{end}?base=USD&symbols=INR")
    return {d: v["INR"] for d, v in (j.get("rates") or {}).items() if v.get("INR")}


def fetch_calendar():
    """This week's US releases.

    generate_site already fetches these at build time and is the source of
    truth for the calendar strip on the page, so reuse it: the Worker's
    /calendar cannot reach the feed at all (Cloudflare refuses the
    worker-to-worker-zone hop) and answers "upstream unavailable" every
    time. The Worker stays as a fallback only so this file still works if
    it is ever run outside a build checkout.
    """
    try:
        import generate_site
        ev = generate_site.fetch_calendar()
        if ev:
            return ev
    except Exception:
        pass
    try:
        j = _get(f"{MARKET_API}/calendar", timeout=20)
    except Exception:
        return []
    if isinstance(j, dict):
        for k in ("events", "calendar", "items"):
            if isinstance(j.get(k), list):
                return j[k]
        return []
    return j if isinstance(j, list) else []


def fetch_board():
    """Our own retail board history: the daily median across jewellers."""
    sb = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_ANON_KEY"))
    if not sb or not key:
        return []
    import jd_analysis as A
    rows, off = [], 0
    while True:
        url = (f"{sb}/rest/v1/rates?select=rate_date,brand_id,"
               f"canonical_24k_pre_gst,status&order=rate_date.asc"
               f"&offset={off}&limit=1000")
        req = urllib.request.Request(url, headers={
            "apikey": key, "Authorization": f"Bearer {key}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.loads(r.read().decode())
        rows += page
        if len(page) < 1000:
            break
        off += 1000
    req = urllib.request.Request(
        f"{sb}/rest/v1/brands?select=id,slug,name,active&order=id.asc",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        brands = json.loads(r.read().decode())
    dates, matrix, _ = A.build_matrix(rows, brands)
    return [(str(m["date"]), m["median"]) for m in A.daily_market(dates, matrix)]


def to_inr_per_gram(bars, fx):
    """International parity in rupees per gram of 999 gold.

    This is the landed-free international price, NOT the Indian board: duty
    and the domestic premium sit on top and are measured separately rather
    than assumed, because both move and neither is ours to guess.
    """
    fdates = sorted(fx)
    out = []
    for b in bars:
        i = bisect.bisect_right(fdates, b["d"]) - 1
        if i < 0:
            continue
        rate = fx[fdates[i]] / OZ_GRAMS
        out.append({"d": b["d"], "o": b["o"] * rate, "h": b["h"] * rate,
                    "l": b["l"] * rate, "c": b["c"] * rate,
                    "usd": b["c"], "fx": fx[fdates[i]]})
    return out


# ─── assembly ────────────────────────────────────────────────────────────

def build(inr_bars, board=None, calendar=None, today=None):
    """Assemble the outlook. Pure: every feed has already been fetched.

    Keeping this free of I/O is what makes the whole thing testable - a
    synthetic series with a known answer goes in, and the verdict can be
    checked against it.
    """
    closes = [b["c"] for b in inr_bars]
    fx_closes = [b["fx"] for b in inr_bars if b.get("fx")]
    usd_closes = [b["usd"] for b in inr_bars if b.get("usd")]
    price = closes[-1]
    a = atr(inr_bars, 14)
    atr_now = a[-1]
    today = today or date.fromisoformat(inr_bars[-1]["d"])

    sup, res = levels_around(inr_bars, price, atr_now)
    st_ = stance(inr_bars, fx_closes)
    ctx = build_context(inr_bars, fx_closes)
    horizons = [h for h in (horizon_view(ctx, k, price, today)
                            for k in ("week", "month", "quarter")) if h]
    pt = passthrough(board, _align(board, inr_bars)) if board else None

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": inr_bars[-1]["d"],
        "basis": {
            "what": "International gold parity, rupees per gram of 999 gold",
            "how": "XAU/USD daily close x USD/INR, divided by 31.1035",
            "price": round(price, 2),
            "usd_oz": round(usd_closes[-1], 2) if usd_closes else None,
            "usd_inr": round(fx_closes[-1], 4) if fx_closes else None,
            "history_days": len(inr_bars),
            "note": ("This is the international price in rupee terms. The "
                     "Indian retail board sits above it by duty plus a "
                     "domestic premium; that gap is measured below rather "
                     "than assumed."),
        },
        "stance": st_,
        "horizons": horizons,
        "levels": {
            "support": sup,
            "resistance": res,
            "floor_pivots": pivot_points(inr_bars),
            "atr_14": round(atr_now, 2) if atr_now else None,
            "method": ("Swing pivots: a bar whose high or low is the extreme "
                       "of the 11 bars centred on it, with near-identical "
                       "pivots merged into one zone. Touches is how many "
                       "separate times price turned there."),
        },
        "expected_move": expected_range(closes, atr_now, price),
        "seasonality": month_seasonality(inr_bars, today.month),
        "drivers": decompose(usd_closes, fx_closes),
        "events": event_risk(calendar, today=today),
        "board": pt,
        "disclaimer": ("Computed from observed prices. This describes market "
                       "structure for people buying metal to stock; it is "
                       "not investment advice and nothing here is a "
                       "guarantee of where price goes next."),
    }
    if pt:
        out["board_forecast"] = board_forecast(board, inr_bars, pt)
        ratio = pt.get("board_over_parity")
        out["board_levels"] = {
            "support": to_board(sup, ratio),
            "resistance": to_board(res, ratio),
            "current": round(board[-1][1], 0) if board else None,
            "premium_over_parity_pct": (
                round((ratio["median"] - 1) * 100, 2) if ratio else None),
            "method": ("Parity levels multiplied by the board's own measured "
                       "premium over parity. The band is that premium's "
                       "dispersion over the same window, not a rounding."),
        }
    return out


def _align(board, inr_bars):
    """Line the international series up with the board's own dates.

    The board has a rate every calendar day; COMEX does not trade weekends.
    Carrying the last international close forward onto a board date is
    right, not a fudge: that IS the price the board was reacting to.
    """
    idx = {b["d"]: b["c"] for b in inr_bars}
    dates = sorted(idx)
    out = []
    for d, _ in board:
        i = bisect.bisect_right(dates, d) - 1
        out.append((d, idx[dates[i]] if i >= 0 else None))
    keep = [(b, p) for b, p in zip(board, out) if p[1]]
    if len(keep) != len(board):
        # Drop from BOTH sides together or the two series silently shift
        # against each other and every correlation below is garbage.
        board[:] = [b for b, _ in keep]
    return [p for _, p in keep]


def to_board(levels, ratio):
    """Restate parity levels in the units a jeweller actually quotes.

    The technicals run on international parity because that is where the
    history and the direction are. Nobody buys at parity: the board sits
    above it by duty plus a domestic premium. That gap is MEASURED over our
    own measured window, not assumed from a duty schedule, because the duty
    schedule changes and the premium moves with local demand.

    The band comes from the gap's own dispersion, so a level is quoted as a
    range rather than a false decimal. If the premium ever stops being
    stable, the band widens on its own and says so.
    """
    if not ratio or not ratio.get("median"):
        return []
    med, sd = ratio["median"], ratio.get("stdev") or 0.0
    out = []
    for z in levels:
        mid = z["price"] * med
        out.append({
            "price": round(mid, 0),
            "low": round(z["price"] * (med - sd), 0),
            "high": round(z["price"] * (med + sd), 0),
            "touches": z["touches"],
            "parity_price": z["price"],
            "distance_pct": z["distance_pct"],
            "last_touch": z["last_touch"],
        })
    return out


def board_forecast(board, inr_bars, pt):
    """Today's international close, carried onto the board at the measured
    lag and coefficient.

    This is the one genuinely forward-looking number here, and it is honest
    because it is mechanical: the board has been following the international
    series with a measurable lag, so today's international move is already
    information about the board's next move. It is reported with the
    correlation and sample size that earned it, and it is worth nothing if
    that relationship breaks.
    """
    best = pt.get("best_lag")
    if not best:
        return {"usable": False,
                "why": ("Neither series moved enough over the shared window "
                        "to measure a relationship between them.")}
    if best["lag_days"] < 1 or best["corr"] < 0.35:
        return {"usable": False,
                "why": ("The board is not currently tracking the "
                        "international price closely enough at any lag for "
                        "this to mean anything "
                        f"(best correlation {best['corr']:+.2f} at "
                        f"{best['lag_days']}-day lag).")}
    idx = {b["d"]: b["c"] for b in inr_bars}
    dates = sorted(idx)
    if len(dates) < 2:
        return {"usable": False, "why": "not enough international history"}
    intl_move = idx[dates[-1]] / idx[dates[-2]] - 1
    implied = intl_move * best["beta"]
    last_board = board[-1][1]
    resid = math.sqrt(max(0.0, 1 - best["corr"] ** 2))
    return {
        "usable": True,
        "lag_days": best["lag_days"],
        "beta": best["beta"],
        "corr": best["corr"],
        "n": best["n"],
        "international_move_pct": round(intl_move * 100, 2),
        "implied_board_move_pct": round(implied * 100, 2),
        "implied_board_rupees": round(last_board * implied, 0),
        "from_board": round(last_board, 0),
        "to_board": round(last_board * (1 + implied), 0),
        "unexplained_share": round(resid, 2),
        "how": (f"The board has followed international parity with a "
                f"{best['lag_days']}-day lag at {best['beta']:.2f}x "
                f"(correlation {best['corr']:+.2f} over {best['n']} days). "
                f"Applying that to today's international move gives the "
                f"figure above. About {resid * 100:.0f}% of the board's "
                f"day-to-day movement is not explained by this at all."),
    }


def main():
    try:
        bars = fetch_gold()
    except Exception as e:
        print(f"outlook: gold feed failed ({type(e).__name__}: {e}) - "
              f"nothing written, the old file stands")
        return 1
    if len(bars) < 250:
        print(f"outlook: only {len(bars)} gold bars, need 250+ - nothing written")
        return 1
    try:
        fx = fetch_fx(bars[0]["d"], bars[-1]["d"])
    except Exception as e:
        print(f"outlook: FX feed failed ({type(e).__name__}: {e}) - "
              f"nothing written, the old file stands")
        return 1
    inr = to_inr_per_gram(bars, fx)
    if len(inr) < 250:
        print(f"outlook: only {len(inr)} aligned days - nothing written")
        return 1

    board = []
    try:
        board = fetch_board()
    except Exception as e:
        print(f"outlook: board history unavailable ({type(e).__name__}) - "
              f"outlook will omit the board translation")
    calendar = fetch_calendar()

    data = build(inr, board=board or None, calendar=calendar)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    s = data.get("stance") or {}
    print(f"outlook: {OUT}")
    print(f"  as of    {data['as_of']}  parity Rs {data['basis']['price']:,.0f}/g "
          f"(${data['basis']['usd_oz']:,.0f}/oz @ {data['basis']['usd_inr']})")
    print(f"  stance   {s.get('label', 'n/a')}  score {s.get('score')} "
          f"conviction {s.get('conviction')}")
    sup = data["levels"]["support"]
    res = data["levels"]["resistance"]
    def _lvl(zs):
        return ", ".join(f"{z['price']:,.0f} ({z['touches']}x)"
                         for z in zs) or "none in range"
    print(f"  support  {_lvl(sup)}")
    print(f"  resist   {_lvl(res)}")
    bf = data.get("board_forecast") or {}
    if bf.get("usable"):
        print(f"  board    next move {bf['implied_board_move_pct']:+.2f}% "
              f"-> Rs {bf['to_board']:,.0f}/g "
              f"(lag {bf['lag_days']}d, r={bf['corr']:+.2f}, n={bf['n']})")
    print(f"  events   {len(data['events'])} high-impact in the next 7 days")
    return 0



# ─── horizons ────────────────────────────────────────────────────────────
# A single verdict is the wrong shape for the question a jeweller actually
# asks. "Do I buy this week" and "where is this in a quarter" are different
# questions with different answers, and they are driven by different things:
# a week is momentum and where price sits against its 20-day mean, a quarter
# is the 50/200 relationship and the slope of the 200-day. Scoring the same
# six signals three times and relabelling the output would be dishonest.
#
# Each horizon therefore gets its own signal set and weights. What keeps
# that from being three opinions is `skill()` below, which measures whether
# each one has ever predicted anything.

HORIZONS = {
    "week":    {"days": 5,  "label": "Next week"},
    "month":   {"days": 21, "label": "Next month"},
    "quarter": {"days": 63, "label": "Next quarter"},
}


def _rolling_sd(rets, window=120):
    """Trailing standard deviation at each point, using only prior returns.

    Computed as an array rather than from the tail of the series, because
    the backtest scores historical days and must not normalise them by
    volatility that had not happened yet. Using the whole series' stdev
    would leak the future into every past score and turn a worthless signal
    into a convincing one.
    """
    out = [None] * len(rets)
    for i in range(len(rets)):
        lo = max(0, i - window + 1)
        w = rets[lo:i + 1]
        out[i] = st.pstdev(w) if len(w) >= 20 else None
    return out


def build_context(bars, fx_closes=None):
    """Every indicator series, computed once, all causal.

    Every array here is indexed by bar, and the value at i uses only bars up
    to i. That is what makes the same function usable for today's verdict
    and for scoring a day two years ago.
    """
    closes = [b["c"] for b in bars]
    rets = [None] + [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    _, _, hist = macd(closes)
    ctx = {
        "bars": bars, "closes": closes,
        "sma20": sma(closes, 20), "sma50": sma(closes, 50),
        "sma200": sma(closes, 200),
        "rsi": rsi(closes, 14), "atr": atr(bars, 14), "macd_hist": hist,
        "sd": [None] + _rolling_sd([r for r in rets[1:]]),
        "fx": fx_closes or [],
        "fx_sma50": sma(fx_closes, 50) if fx_closes else [],
    }
    return ctx


def _roc(closes, i, n):
    if i - n < 0 or not closes[i - n]:
        return None
    return closes[i] / closes[i - n] - 1


def horizon_components(ctx, i, horizon):
    """The signals for one horizon at one point in time.

    Returns [] when the history at i is too short - an empty component list
    means no verdict, which is the right answer rather than a verdict built
    from three of the six signals.
    """
    c, a, sd = ctx["closes"], ctx["atr"], ctx["sd"]
    price, atr_now = c[i], a[i]
    sd_now = sd[i] if i < len(sd) else None
    if atr_now is None or sd_now is None:
        return []
    out = []

    def norm(num, den):
        """Normalised score, with the degenerate case handled honestly.

        A price series that has not moved gives a zero numerator AND a zero
        denominator. That is not a missing reading and it is not a strong
        signal - it is a market doing nothing, which scores zero. Guarding
        with a plain falsiness check instead made the whole horizon return
        no verdict, and a stalled feed repeating one price would hit it.
        """
        if not den:
            return 0.0 if not num else math.copysign(1.0, num)
        return num / den

    def add(name, weight, score, detail):
        out.append({"name": name, "weight": weight,
                    "score": round(_clamp(score), 3), "detail": detail})

    if horizon == "week":
        m20 = ctx["sma20"][i]
        if not m20:
            return []
        add("Price vs 20-day", 0.30, norm(price - m20, atr_now * 2.0),
            f"{(price / m20 - 1) * 100:+.2f}%")
        r5 = _roc(c, i, 5)
        if r5 is None:
            return []
        add("5-day change", 0.25, norm(r5, sd_now * math.sqrt(5) * 1.5),
            f"{r5 * 100:+.2f}%")
        if ctx["rsi"][i] is None:
            return []
        add("RSI (14)", 0.20, (ctx["rsi"][i] - 50) / 20, f"{ctx['rsi'][i]:.1f}")
        h = ctx["macd_hist"][i]
        if h is None:
            return []
        add("MACD momentum", 0.15, norm(h, atr_now * 0.8), f"{h:+.1f}")
        _add_rupee(ctx, i, out, 0.10)

    elif horizon == "month":
        m50, m200 = ctx["sma50"][i], ctx["sma200"][i]
        if not m50 or not m200:
            return []
        add("Price vs 50-day", 0.25, norm(price - m50, atr_now * 2.5),
            f"{(price / m50 - 1) * 100:+.2f}%")
        add("50-day vs 200-day", 0.15, (m50 / m200 - 1) / 0.06,
            f"{(m50 / m200 - 1) * 100:+.2f}% apart")
        if ctx["rsi"][i] is None:
            return []
        add("RSI (14)", 0.15, (ctx["rsi"][i] - 50) / 20, f"{ctx['rsi'][i]:.1f}")
        h = ctx["macd_hist"][i]
        if h is None:
            return []
        add("MACD momentum", 0.15, norm(h, atr_now * 0.8), f"{h:+.1f}")
        r20 = _roc(c, i, 21)
        if r20 is None:
            return []
        add("20-day change", 0.15, norm(r20, sd_now * math.sqrt(21) * 1.5),
            f"{r20 * 100:+.2f}%")
        _add_rupee(ctx, i, out, 0.15)

    elif horizon == "quarter":
        m50, m200 = ctx["sma50"][i], ctx["sma200"][i]
        if not m50 or not m200:
            return []
        add("50-day vs 200-day", 0.30, (m50 / m200 - 1) / 0.06,
            f"{(m50 / m200 - 1) * 100:+.2f}% apart")
        add("Price vs 200-day", 0.25, (price / m200 - 1) / 0.12,
            f"{(price / m200 - 1) * 100:+.2f}%")
        r63 = _roc(c, i, 63)
        if r63 is None:
            return []
        add("Quarter change", 0.20, norm(r63, sd_now * math.sqrt(63) * 1.5),
            f"{r63 * 100:+.2f}%")
        # The 200-day's own slope: a market above a FALLING long average is
        # a different animal from one above a rising average, and only the
        # slope tells them apart.
        prev200 = ctx["sma200"][i - 21] if i >= 21 else None
        if prev200:
            slope = m200 / prev200 - 1
            add("200-day slope", 0.15, slope / 0.04,
                f"{slope * 100:+.2f}% over 21 days")
        _add_rupee(ctx, i, out, 0.10)

    return out


def _add_rupee(ctx, i, out, weight):
    fx, f50 = ctx["fx"], ctx["fx_sma50"]
    if i >= len(fx) or i >= len(f50) or not f50[i]:
        return
    gap = fx[i] / f50[i] - 1
    out.append({"name": "Rupee (USD/INR)", "weight": weight,
                "score": round(_clamp(gap / 0.02), 3),
                "detail": f"{fx[i]:.2f}, {gap * 100:+.2f}% vs 50-day"})


def _label(score):
    if score >= 40:
        return "Bullish", "up"
    if score >= 15:
        return "Mildly bullish", "up"
    if score > -15:
        return "Neutral", "flat"
    if score > -40:
        return "Mildly bearish", "down"
    return "Bearish", "down"


def score_at(ctx, i, horizon):
    comps = horizon_components(ctx, i, horizon)
    if not comps:
        return None
    tw = sum(c["weight"] for c in comps)
    return sum(c["score"] * c["weight"] for c in comps) / tw * 100


def skill(ctx, horizon, min_n=60):
    """Has this horizon's score ever predicted anything?

    Every past day is scored with the indicators as they stood ON that day,
    then compared against what price actually did over the following
    horizon. Three numbers come out:

      ic        correlation between score and the forward return. This is
                the honest measure. Anything above +0.10 is respectable for
                a price signal; near zero means the verdict is decoration.
      hit_rate  how often the SIGN was right, counting only days the score
                was decisive enough to be a call at all.
      edge      mean forward return on bullish days minus bearish days.

    Reporting this is the point. Three confident verdicts with no measure of
    whether any of them work is the thing the rest of this codebase exists
    to avoid - and if a horizon scores zero, that is what the product should
    say about it rather than quietly printing the verdict anyway.
    """
    days = HORIZONS[horizon]["days"]
    c = ctx["closes"]
    scores, fwd = [], []
    for i in range(len(c) - days):
        s = score_at(ctx, i, horizon)
        if s is None:
            continue
        scores.append(s)
        fwd.append(c[i + days] / c[i] - 1)
    if len(scores) < min_n:
        return {"n": len(scores), "usable": False,
                "why": "not enough scored history to measure"}
    ic = _corr(scores, fwd)
    decisive = [(sc, f) for sc, f in zip(scores, fwd) if abs(sc) >= 15]
    hits = sum(1 for sc, f in decisive if (sc > 0) == (f > 0))
    hit_rate = hits / len(decisive) * 100 if decisive else None
    # The baseline this MUST be read against: over a window where gold rose
    # most quarters, a signal that says "bullish" every day scores a high
    # hit rate while knowing nothing. Reporting 79% without saying that 78%
    # of quarters were up regardless is how a useless model looks skilled.
    base_rate = sum(1 for f in fwd if f > 0) / len(fwd) * 100
    base_mean = st.mean(fwd) * 100
    bull = [f for sc, f in zip(scores, fwd) if sc >= 15]
    bear = [f for sc, f in zip(scores, fwd) if sc <= -15]
    edge = (st.mean(bull) - st.mean(bear)) * 100 if (bull and bear) else None
    return {
        "usable": True,
        "n": len(scores),
        "ic": round(ic, 3) if ic is not None else None,
        "decisive_n": len(decisive),
        "hit_rate": round(hit_rate, 1) if hit_rate is not None else None,
        "base_rate": round(base_rate, 1),
        "base_mean_pct": round(base_mean, 2),
        "beats_baseline": (round(hit_rate - base_rate, 1)
                           if hit_rate is not None else None),
        "edge_pct": round(edge, 2) if edge is not None else None,
        "verdict": _skill_verdict(ic, len(decisive)),
        "window": f"{ctx['bars'][0]['d']} to {ctx['bars'][-1]['d']}",
        "caveat": (
            f"Measured over one regime: gold moved "
            f"{(ctx['closes'][-1] / ctx['closes'][0] - 1) * 100:+.0f}% across "
            f"this window, and {base_rate:.0f}% of {days}-day periods in it "
            f"were up regardless of any signal. A hit rate below that "
            f"baseline means the score did worse than assuming the market "
            f"rises."),
    }


def _skill_verdict(ic, n):
    """Plain words for what the measurement means, so nobody has to know
    what an information coefficient is to read the report.

    Deliberately blunt at the bottom of the scale. A product that hedges
    "no measurable value" into "directionally indicative" is worse than one
    that omits the section, because the reader cannot tell the difference
    between this and a signal that works.
    """
    if ic is None or n < 30:
        return "too little history to judge"
    if ic >= 0.20:
        return "has predicted direction well on this history"
    if ic >= 0.10:
        return "has some predictive value on this history"
    if ic >= 0.03:
        return "weak - barely better than a coin toss"
    if ic > -0.03:
        return "no measurable predictive value on this history"
    return "has pointed the WRONG way on this history"


def horizon_view(ctx, horizon, price, today=None):
    """One horizon: the verdict, the signals, the range, and the skill."""
    i = len(ctx["closes"]) - 1
    comps = horizon_components(ctx, i, horizon)
    if not comps:
        return None
    days = HORIZONS[horizon]["days"]
    s = score_at(ctx, i, horizon)
    label, direction = _label(s)
    scores = [c["score"] for c in comps]
    agreement = _clamp(1 - (st.pstdev(scores) if len(scores) > 1 else 0), 0.0, 1.0)

    # Projected band from what moves of this length have actually been.
    c = ctx["closes"]
    moves = [abs(c[k] / c[k - days] - 1) for k in range(days, len(c))]
    moves = moves[-500:] if len(moves) > 500 else moves
    band = sorted(moves)[int(len(moves) * 0.68)] if len(moves) >= 20 else None

    out = {
        "horizon": horizon,
        "label": HORIZONS[horizon]["label"],
        "days": days,
        "verdict": label,
        "direction": direction,
        "score": round(s, 1),
        "agreement": round(agreement, 2),
        "components": comps,
        "skill": skill(ctx, horizon),
    }
    if band:
        out["range"] = {
            "pct": round(band * 100, 2),
            "rupees": round(price * band, 0),
            "low": round(price * (1 - band), 0),
            "high": round(price * (1 + band), 0),
            "n": len(moves),
        }
    if today:
        out["seasonality"] = _season_ahead(ctx["bars"], today, days)
    return out


def _season_ahead(bars, today, days):
    """What the calendar months this horizon covers have done before.

    A week does not have a season, so anything under a month returns
    nothing rather than a number dressed up as one.
    """
    if days < 21:
        return None
    months = 1 if days <= 31 else 3
    out = []
    m = today.month
    for k in range(months):
        mm = (m - 1 + k) % 12 + 1
        se = month_seasonality(bars, mm)
        if se.get("mean_pct") is not None:
            out.append(se)
    if not out:
        return None
    return {
        "months": [x["month"] for x in out],
        "mean_pct": round(sum(x["mean_pct"] for x in out), 2),
        "n": min(x["n"] for x in out),
        "detail": out,
    }


if __name__ == "__main__":
    raise SystemExit(main())
