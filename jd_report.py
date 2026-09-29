#!/usr/bin/env python3
"""Build the Jewellers Digest analysis workbook from scraped history.

Reads `rates` + `brands` from Supabase, runs jd_analysis, and writes an
.xlsx with the raw export a jeweller can pivot themselves plus the derived
analysis. Formatting lives here; every number comes from jd_analysis, which
is pure and separately tested.

Sheets
  Summary          window overview and today's board, cheapest first
  Daily Rates      date x brand matrix - the raw export, nothing derived
  Brand Analysis   per brand: level, dispersion, premium, how often cheapest
  Market Daily     per day: low / median / high / spread
  Weekday          mean by weekday, with n attached
  Making Charges   median making % by brand and category, with confidence
  Methodology      what this window supports, and what it does not

The Methodology sheet is not filler. Someone is paying for these numbers,
so the workbook states its own limits in its own voice - the window, the
missing bullion benchmark, the weekday sample size, and which brands were
excluded and why.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import jd_analysis as A

SB = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
# NOT under docs/. Everything in docs/ is published to mygoldrates.com by
# Cloudflare Pages, so writing the paid workbook there would hand it to
# anyone who guessed the filename. It is written to a build-local path and
# uploaded to a PRIVATE Supabase Storage bucket; entitled subscribers get a
# short-lived signed URL from the JD worker, never a public path.
OUT = os.environ.get("JD_REPORT_OUT", "build/jewellers-digest.xlsx")
BUCKET = os.environ.get("JD_REPORT_BUCKET", "jd-reports")
MC_URL = "https://mygoldrates.com/making-charges.json"

GOLD = "D4A63C"
INK = "1B1712"
HEAD = PatternFill("solid", fgColor=GOLD)
SUBHEAD = PatternFill("solid", fgColor="F2EDE3")
BOLD = Font(bold=True, color=INK)
WHITEB = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="D9D2C5")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def get(path):
    rows, off = [], 0
    while True:
        req = urllib.request.Request(
            f"{SB}/rest/v1/{path}&limit=1000&offset={off}",
            headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            b = json.loads(r.read())
        rows += b
        if len(b) < 1000:
            return rows
        off += 1000


def fetch_making_charges():
    try:
        req = urllib.request.Request(MC_URL, headers={"User-Agent": "mygoldrates-jd"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  making charges unavailable ({type(e).__name__}) - sheet skipped")
        return None


def _hrow(ws, row, headers, width=None):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.fill = HEAD
        c.font = WHITEB
        c.border = BOX
        c.alignment = Alignment(horizontal="center", vertical="center",
                                wrap_text=True)
    ws.freeze_panes = ws.cell(row=row + 1, column=1)
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = \
            (width or {}).get(h, max(11, min(26, len(str(h)) + 4)))


def sheet_summary(wb, trend, stats, dates, excluded, generated):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Jewellers Digest - MyGoldRates jeweller rate analysis"
    ws["A1"].font = Font(bold=True, size=15, color=INK)
    ws["A2"] = f"Generated {generated} - all rates 24K, pre-GST, per gram"
    ws["A2"].font = Font(italic=True, color="6B6357")
    ws.column_dimensions["A"].width = 34
    for col in "BCDEF":
        ws.column_dimensions[col].width = 15

    r = 4
    ws.cell(row=r, column=1, value="WINDOW").font = BOLD
    ws.cell(row=r, column=1).fill = SUBHEAD
    r += 1
    for label, key, fmt in [
        ("Period", None, None),
        ("Trading days", "days", "0"),
        ("Jewellers covered", None, None),
        ("Market median, first day", "open", "#,##0.00"),
        ("Market median, last day", "close", "#,##0.00"),
        ("Change over window", "change", "+#,##0.00;-#,##0.00"),
        ("Change %", "change_pct", "+0.00\\%;-0.00\\%"),
        ("Highest median", "high", "#,##0.00"),
        ("Lowest median", "low", "#,##0.00"),
        ("Peak-to-trough range %", "range_pct", "0.00\\%"),
        ("Average cheapest-to-dearest spread", "avg_spread", "#,##0.00"),
        ("Widest spread", "widest_spread", "#,##0.00"),
    ]:
        ws.cell(row=r, column=1, value=label)
        if label == "Period":
            ws.cell(row=r, column=2, value=f"{trend['from']} to {trend['to']}")
        elif label == "Jewellers covered":
            ws.cell(row=r, column=2, value=len(stats))
        else:
            c = ws.cell(row=r, column=2, value=trend.get(key))
            if fmt:
                c.number_format = fmt
        r += 1
    ws.cell(row=r, column=1, value="Widest spread occurred")
    ws.cell(row=r, column=2, value=str(trend.get("widest_spread_date", "")))
    r += 2

    ws.cell(row=r, column=1, value="TODAY'S BOARD - CHEAPEST FIRST").font = BOLD
    ws.cell(row=r, column=1).fill = SUBHEAD
    r += 1
    _hrow(ws, r, ["Jeweller", "Latest 24K", "Avg premium vs market %",
                  "Days cheapest %", "Days covered"])
    ws.freeze_panes = "A4"
    r += 1
    for s in sorted(stats, key=lambda x: x["latest"]):
        ws.cell(row=r, column=1, value=s["slug"])
        ws.cell(row=r, column=2, value=s["latest"]).number_format = "#,##0.00"
        c = ws.cell(row=r, column=3, value=s["premium_vs_median_pct"])
        c.number_format = "+0.00;-0.00"
        ws.cell(row=r, column=4, value=s["pct_days_cheapest"]).number_format = "0.0"
        ws.cell(row=r, column=5, value=s["days"])
        r += 1
    if excluded:
        r += 1
        ws.cell(row=r, column=1,
                value=f"Excluded (no longer on the board): {', '.join(excluded)}"
                ).font = Font(italic=True, color="A33E32")
    return ws


def sheet_daily_rates(wb, dates, matrix):
    ws = wb.create_sheet("Daily Rates")
    slugs = sorted(matrix)
    _hrow(ws, 1, ["Date"] + slugs)
    for i, d in enumerate(dates, 2):
        ws.cell(row=i, column=1, value=str(d))
        for j, s in enumerate(slugs, 2):
            v = matrix[s].get(d)
            if v is not None:
                ws.cell(row=i, column=j, value=v).number_format = "#,##0.00"
    return ws


def sheet_brand_analysis(wb, stats):
    ws = wb.create_sheet("Brand Analysis")
    cols = [("Jeweller", "slug", None), ("Days", "days", "0"),
            ("Coverage %", "coverage_pct", "0.0"),
            ("Latest", "latest", "#,##0.00"), ("Mean", "mean", "#,##0.00"),
            ("Median", "median", "#,##0.00"), ("Min", "min", "#,##0.00"),
            ("Max", "max", "#,##0.00"),
            ("Volatility (sd)", "stdev", "#,##0.00"),
            ("Avg premium vs market %", "premium_vs_median_pct", "+0.000;-0.000"),
            ("Days cheapest", "days_cheapest", "0"),
            ("% days cheapest", "pct_days_cheapest", "0.0"),
            ("Days dearest", "days_dearest", "0"),
            ("Avg daily move", "avg_daily_move", "#,##0.00"),
            ("Days unchanged", "days_unchanged", "0")]
    _hrow(ws, 1, [c[0] for c in cols])
    for i, s in enumerate(stats, 2):
        for j, (_, k, fmt) in enumerate(cols, 1):
            c = ws.cell(row=i, column=j, value=s.get(k))
            if fmt:
                c.number_format = fmt
    return ws


def sheet_market_daily(wb, market):
    ws = wb.create_sheet("Market Daily")
    _hrow(ws, 1, ["Date", "Jewellers", "Cheapest", "Median", "Dearest",
                  "Spread", "Spread %"])
    for i, m in enumerate(market, 2):
        ws.cell(row=i, column=1, value=str(m["date"]))
        ws.cell(row=i, column=2, value=m["brands"])
        for j, k in enumerate(["low", "median", "high", "spread"], 3):
            ws.cell(row=i, column=j, value=m[k]).number_format = "#,##0.00"
        ws.cell(row=i, column=7, value=m["spread_pct"]).number_format = "0.000"
    return ws


def sheet_weekday(wb, rows):
    ws = wb.create_sheet("Weekday")
    ws["A1"] = ("Mean of the daily market median, by weekday. n is the number "
                "of observations - with ten weeks of data this describes the "
                "window and is not enough to call a seasonal pattern.")
    ws["A1"].font = Font(italic=True, color="6B6357")
    ws.merge_cells("A1:E1")
    _hrow(ws, 3, ["Weekday", "n", "Mean median", "Min", "Max"])
    for i, w in enumerate(rows, 4):
        ws.cell(row=i, column=1, value=w["weekday"])
        ws.cell(row=i, column=2, value=w["n"])
        for j, k in enumerate(["mean_median", "min", "max"], 3):
            ws.cell(row=i, column=j, value=w[k]).number_format = "#,##0.00"
    return ws


def sheet_making_charges(wb, mc):
    ws = wb.create_sheet("Making Charges")
    ws["A1"] = (mc.get("note") or "Making charge as a % of gold value, from "
                "each jeweller's own listed product breakups.")[:300]
    ws["A1"].font = Font(italic=True, color="6B6357")
    ws.merge_cells("A1:G1")
    ws["A2"] = f"Source updated {mc.get('updated', 'unknown')}"
    ws["A2"].font = Font(italic=True, color="6B6357")
    _hrow(ws, 4, ["Jeweller", "Category", "Items sampled", "Median making %",
                  "Min %", "Max %", "Confidence"])
    r = 5
    for b in mc.get("brands", []):
        for cat in b.get("categories", []):
            ws.cell(row=r, column=1, value=b.get("brand"))
            ws.cell(row=r, column=2, value=cat.get("category"))
            ws.cell(row=r, column=3, value=cat.get("items"))
            for j, k in enumerate(["making_pct_median", "making_pct_min",
                                   "making_pct_max"], 4):
                c = ws.cell(row=r, column=j, value=cat.get(k))
                c.number_format = "0.0"
            conf = cat.get("confidence", "")
            c = ws.cell(row=r, column=7, value=conf)
            if conf == "low":
                c.font = Font(color="A33E32")
            r += 1
    return ws


def sheet_market_note(wb, ai, generated):
    """The AI-written daily note - or an honest blank where it would have been.

    When the note fails validation the sheet says so instead of quietly
    disappearing. A subscriber who paid for commentary should be told it was
    withheld and why, not left wondering whether they missed a tab.
    """
    ws = wb.create_sheet("Market Note")
    ws.column_dimensions["A"].width = 110
    ws["A1"] = "Daily market note"
    ws["A1"].font = Font(bold=True, size=14, color=INK)
    ws["A2"] = (f"Written {generated} by Claude from the figures in this "
                f"workbook. Every rupee figure below is checked against those "
                f"figures before publication.")
    ws["A2"].font = Font(italic=True, color="6B6357")
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 30

    if ai and ai.get("ok"):
        r = 4
        for para in [p for p in ai["note"].split("\n") if p.strip()]:
            c = ws.cell(row=r, column=1, value=para.strip())
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[r].height = max(30, 15 * (len(para) // 95 + 1))
            r += 1
        return ws

    ws["A4"] = "No note today."
    ws["A4"].font = BOLD
    ws["A5"] = ("It was withheld rather than published: "
                + (ai or {}).get("reason", "the generator was not configured")
                + ". The figures in the other sheets are unaffected - they are "
                  "computed by code, not written.")
    ws["A5"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[5].height = 45
    return ws


def sheet_methodology(wb, notes, excluded, trend, generated):
    ws = wb.create_sheet("Methodology")
    ws.column_dimensions["A"].width = 120
    ws["A1"] = "How to read this report"
    ws["A1"].font = Font(bold=True, size=14, color=INK)
    r = 3
    for n in notes:
        ws.cell(row=r, column=1, value="- " + n).alignment = \
            Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 30
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="Definitions").font = BOLD
    r += 1
    for d in [
        "Market median - the median of all jewellers publishing on that day. "
        "It is a cross-section of this board, not an official benchmark.",
        "Avg premium vs market % - the mean of the daily percentage gap "
        "between a jeweller and that day's market median. Averaging the daily "
        "gaps, rather than comparing averages, keeps the figure meaningful "
        "when a jeweller is missing on days the market moved.",
        "Volatility (sd) - population standard deviation of that jeweller's "
        "own rate over the window, in rupees per gram.",
        "Spread - cheapest to dearest on the same day. This is the number "
        "that bounds what a buyer could save by shopping around that day.",
        "Days unchanged - days where the jeweller's published rate did not "
        "move from the previous scraped day.",
    ]:
        ws.cell(row=r, column=1, value="- " + d).alignment = \
            Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 30
        r += 1
    r += 1
    if excluded:
        ws.cell(row=r, column=1,
                value="Excluded brands: " + ", ".join(excluded) +
                " - no longer on the live board. One was removed because the "
                "figure it published was a product price read from an error "
                "page, not a gold rate; its history is therefore not sold "
                "here.").alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 45
        r += 2
    ws.cell(row=r, column=1,
            value=f"Generated {generated} from mygoldrates.com scraped data. "
                  f"Window {trend.get('from')} to {trend.get('to')}.")
    return ws


def build(rates, brands, mc, generated):
    dates, matrix, excluded = A.build_matrix(rates, brands)
    if not dates:
        raise SystemExit("no published rate history - nothing to report")
    market = A.daily_market(dates, matrix)
    stats = A.brand_stats(dates, matrix, market)
    trend = A.market_trend(market)
    notes = A.describe_confidence(dates, matrix, market)

    wb = Workbook()
    wb.remove(wb.active)
    sheet_summary(wb, trend, stats, dates, excluded, generated)
    sheet_daily_rates(wb, dates, matrix)
    sheet_brand_analysis(wb, stats)
    sheet_market_daily(wb, market)
    sheet_weekday(wb, A.weekday_pattern(market))
    ai = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import jd_ai_report as AI
        ai = AI.generate({"trend": trend, "stats": stats, "market": market})
        sheet_market_note(wb, ai, generated)
    else:
        print("  ai note  skipped (ANTHROPIC_API_KEY not set)")
    if mc:
        sheet_making_charges(wb, mc)
    sheet_methodology(wb, notes, excluded, trend, generated)
    return wb, {"dates": dates, "matrix": matrix, "market": market,
                "stats": stats, "trend": trend, "excluded": excluded}


def upload(path, trend):
    """Upload to a PRIVATE Supabase Storage bucket, keyed by window end date.

    Needs the service key - the anon key cannot write here, and the bucket
    must not be public: the whole point is that only the JD worker can mint
    a signed URL for a subscriber whose entitlement is current.

    Dated object names keep every day's workbook rather than overwriting, so
    a subscriber who paid last week can still be given what they paid for,
    and a figure someone queries can be traced to the exact file that carried
    it.
    """
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        return "skipped (no service key - report written locally only)"
    name = f"jewellers-digest-{trend.get('to')}.xlsx"
    url = f"{SB}/storage/v1/object/{BUCKET}/{name}"
    with open(path, "rb") as f:
        body = f.read()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet",
        "x-upsert": "true",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            if r.status in (200, 201):
                return f"uploaded {BUCKET}/{name} ({len(body)/1024:.0f} KB)"
            return f"unexpected status {r.status}"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:160]
        if e.code == 404:
            return (f"FAILED - bucket '{BUCKET}' does not exist. Create it as "
                    f"a PRIVATE bucket in Supabase Storage. ({detail})")
        return f"FAILED HTTP {e.code}: {detail}"
    except Exception as e:
        return f"FAILED {type(e).__name__}: {str(e)[:120]}"


def main():
    if not SB or not KEY:
        print("jd_report: SUPABASE_URL / key not set")
        return 1
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rates = get("rates?select=rate_date,brand_id,canonical_24k_pre_gst,status"
                "&order=rate_date.asc")
    brands = get("brands?select=id,slug,name,active&order=id.asc")
    wb, ctx = build(rates, brands, fetch_making_charges(), generated)

    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    wb.save(OUT)
    t = ctx["trend"]
    print(f"jd_report: {OUT}")
    print(f"  window   {t['from']} -> {t['to']} ({t['days']} days)")
    print(f"  brands   {len(ctx['stats'])} included"
          + (f", excluded {ctx['excluded']}" if ctx["excluded"] else ""))
    print(f"  median   {t['open']:,.0f} -> {t['close']:,.0f} "
          f"({t['change_pct']:+.2f}%)")
    print(f"  spread   avg Rs {t['avg_spread']:,.0f}/g, "
          f"widest Rs {t['widest_spread']:,.0f}")
    print(f"  sheets   {', '.join(wb.sheetnames)}")
    up = upload(OUT, t)
    print(f"  storage  {up}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
