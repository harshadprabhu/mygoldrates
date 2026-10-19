#!/usr/bin/env python3
"""The Jewellers Digest morning note, written by rules from the day's figures.

No model and no network: the interpretation is fixed here, once, and runs
every morning on whatever the analysis produced. Every number in the note is
read straight from the issue (jd_issue.build), so the note cannot state a
figure the page does not show. Sections whose inputs are missing or stale are
left out rather than guessed.

How each metric is read is written next to the code that reads it.
"""
from datetime import date


def _inr(n):
    """Indian digit grouping, whole rupees: 1,63,205."""
    n = int(round(n))
    s, neg = str(abs(n)), n < 0
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if neg else "") + "₹" + s


def _pct(x, d=1):
    return f"{x:+.{d}f}%"


def _signed_inr(n):
    return ("+" if n >= 0 else "−") + _inr(abs(n))


def _day(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} " + ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                           "Aug", "Sep", "Oct", "Nov", "Dec"][int(m) - 1]


# How much a signal's track record earns it. Same thresholds as the page's
# skill tags (information coefficient = correlation of score with what
# actually happened next), so the note and the page never disagree.
def _trust(skill):
    if not skill or not skill.get("usable"):
        return "its track record cannot be measured yet"
    ic = skill.get("ic") or 0
    if ic >= 0.10:
        return "a signal with some measured predictive value"
    if ic >= 0.03:
        return "a weak signal, only slightly better than chance"
    if ic > -0.03:
        return "a signal with no measured predictive value, so treat it as context only"
    return "a signal that has pointed the wrong way more often than not, so give it little weight"


def market_today(issue):
    """Where the board is, against the last session and a week ago.

    Series values repeat on days no jeweller changed its rate (weekends,
    holidays); comparing against the previous *different* value would hide
    that, so the comparison is against the previous session as recorded."""
    s = issue.get("series") or []
    if len(s) < 2:
        return None
    now, prev = s[-1], s[-2]
    wk = s[-6] if len(s) >= 6 else s[0]
    d1, d5 = now["md"] - prev["md"], now["md"] - wk["md"]
    move = ("unchanged on the day" if abs(d1) < 1 else
            f"{'up' if d1 > 0 else 'down'} {_inr(abs(d1))} on the day")
    week = ("flat over the last five sessions" if abs(d5) < 1 else
            f"{'up' if d5 > 0 else 'down'} {_inr(abs(d5))} over the last five sessions")
    return (f"The board median is {_inr(now['md'])}/g (24K, pre-GST) on "
            f"{_day(now['d'])}, {move} and {week}.")


def spread_today(issue):
    """Cheapest-to-dearest gap today against its window average. A wide gap
    is when shopping around pays most."""
    s, t = issue.get("series") or [], issue.get("trend") or {}
    if not s or not t.get("avg_spread"):
        return None
    gap, avg = s[-1]["hi"] - s[-1]["lo"], t["avg_spread"]
    ratio = gap / avg if avg else 1
    if ratio >= 1.25:
        read = "well above the usual, so comparing jewellers pays more than normal today"
    elif ratio <= 0.8:
        read = "narrower than usual, so jewellers are quoting close together"
    else:
        read = "about the usual"
    return (f"Cheapest to dearest is {_inr(gap)}/g today against a "
            f"{_inr(avg)} average: {read}.")


def cheapest(issue):
    """Who is cheapest today, and whether that is habit or a one-off."""
    b, stats = issue.get("board") or [], issue.get("stats") or []
    if not b:
        return None
    top = b[0]
    habit = {x["n"]: x.get("cheap") or 0 for x in stats}
    regular = max(stats, key=lambda x: x.get("cheap") or 0) if stats else None
    line = (f"{top['n']} is cheapest at {_inr(top['v'])}/g, "
            f"{abs(top['p']):.2f}% under the median")
    share = habit.get(top["n"])
    if share is not None:
        line += f"; it has been the cheapest on {share:.0f}% of days in the window"
    if regular and regular["n"] != top["n"] and (regular.get("cheap") or 0) >= 20:
        line += (f". {regular['n']} is the most frequent cheapest "
                 f"({regular['cheap']:.0f}% of days)")
    return line + "."


def _fresh(issue, max_days=3):
    """The outlook is computed by a separate step that can fail; an old one
    is not described as today's."""
    o, last = issue.get("outlook") or {}, issue.get("last")
    try:
        age = (date.fromisoformat(last) - date.fromisoformat(o["as_of"][:10])).days
    except (KeyError, TypeError, ValueError):
        return False
    return age <= max_days


def outlook(issue):
    """Direction by horizon, each with how much its record deserves."""
    if not _fresh(issue):
        return None
    hs = (issue["outlook"].get("horizons") or [])
    if not hs:
        return None
    parts = []
    for h in hs:
        r = h.get("range") or {}
        rng = f", typical range ±{r['pct']:.1f}%" if r.get("pct") else ""
        parts.append(f"{h['label'].lower()} {h['verdict']}{rng} ({_trust(h.get('skill'))})")
    return "Signals read: " + "; ".join(parts) + "."


def levels(issue):
    """The nearest turning points on the board above and below."""
    if not _fresh(issue):
        return None
    bl = issue["outlook"].get("board_levels") or {}
    res = [z for z in bl.get("resistance") or [] if z.get("distance_pct", 0) > 0]
    sup = [z for z in bl.get("support") or [] if z.get("distance_pct", 0) < 0]
    bits = []
    if res:
        z = min(res, key=lambda z: z["distance_pct"])
        bits.append(f"resistance near {_inr(z['price'])} ({_pct(z['distance_pct'])}, "
                    f"turned there {z['touches']} time{'s' if z['touches'] != 1 else ''})")
    if sup:
        z = max(sup, key=lambda z: z["distance_pct"])
        bits.append(f"support near {_inr(z['price'])} ({_pct(z['distance_pct'])}, "
                    f"{z['touches']} time{'s' if z['touches'] != 1 else ''})")
    return ("On the board: " + " and ".join(bits) + ".") if bits else None


def tomorrow(issue):
    """The one genuinely forward-looking figure: the board follows the
    international price with a one-day lag. Always stated with how much of
    daily movement it leaves unexplained."""
    if not _fresh(issue):
        return None
    f = issue["outlook"].get("board_forecast") or {}
    if not f.get("usable"):
        return None
    return (f"The international move implies about "
            f"{_pct(f['implied_board_move_pct'], 2)} ({_signed_inr(f['implied_board_rupees'])}) "
            f"on the board next session, though about "
            f"{round(f['unexplained_share'] * 100)}% of daily movement is not "
            f"explained by this.")


def typical_move(issue):
    """How far a normal day travels, so a big move can be recognised."""
    if not _fresh(issue):
        return None
    em = [r for r in issue["outlook"].get("expected_move") or []
          if r.get("days") == 1 and r.get("sigma_rupees")]
    if not em:
        return None
    return f"A typical day moves about ±{_inr(em[0]['sigma_rupees'])}/g."


def events(issue):
    """High-impact releases still ahead this week."""
    if not _fresh(issue):
        return None
    ev = [e for e in issue["outlook"].get("events") or []
          if e.get("impact") == "high" and (e.get("days_away") or 0) >= 0]
    if not ev:
        return None
    names = []
    for e in ev:
        if e["title"] not in names:
            names.append(e["title"])
    head = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
    return (f"High-impact US releases due this week: {head}. Expect larger moves "
            f"around them; their direction is not knowable in advance.")


SECTIONS = [market_today, spread_today, cheapest, outlook, levels,
            tomorrow, typical_move, events]


def compose(issue):
    """The note: one short paragraph per section that has what it needs."""
    out = []
    for fn in SECTIONS:
        try:
            line = fn(issue)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            line = None                 # a malformed input drops its section only
        if line:
            out.append(line)
    if not _fresh(issue) and issue.get("outlook"):
        out.append("The outlook was not refreshed today, so direction, levels "
                   "and event risk are left out of this note.")
    return "\n".join(out)
