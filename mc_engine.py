#!/usr/bin/env python3
"""Adaptive making-charge extraction engine.

WHY THIS EXISTS
---------------
Hand-writing one regex per jeweller does not scale: every brand encodes its
price breakup differently (nested JSON, DOM tables, plain text), and any site
redesign silently breaks a hardcoded pattern - the failure mode is "0 items
extracted", which looks identical to "brand has no data".

Instead of guessing per brand, this module runs a BATTERY of candidate
strategies against a page, scores each result, keeps the best, and REMEMBERS
which strategy won (a per-brand "profile"). Next run the learned strategy is
tried first (fast path); if it stops working the engine automatically falls
back to a full re-probe and re-learns. That is the self-healing property.

WHY NOT A TRAINED MODEL
-----------------------
A supervised model would need a labelled corpus of jeweller pages we do not
have, would need retraining per site redesign, and would still have to be
validated against arithmetic ground truth (making/gold ratios). The hard part
here is not classification, it is (a) locating the right numbers among many
rupee amounts on a page and (b) knowing when the answer is wrong. So the
"learning" here is:

  * fuzzy semantic label matching  -> handles unseen phrasings
    ("Making Charges" / "Making Charge" / "Value Addition" / "VA" / "Labour")
  * automatic strategy selection   -> no per-brand code needed
  * learned per-brand profiles     -> speed + drift detection
  * robust statistics (MAD)        -> rejects garbage before it poisons a median

All dependency-light (stdlib + bs4, both already used by this repo) so it runs
inside the existing GitHub Actions budget.

USAGE
-----
    from mc_engine import Engine, ExtractionResult

    eng = Engine.load("mc_profiles.json")
    res = eng.extract(html, brand="BlueStone")     # -> ExtractionResult
    if res.ok:
        print(res.making_pct, res.strategy, res.confidence)
    eng.save("mc_profiles.json")                   # persist what it learned

    # Probe an unknown brand / debug a broken one:
    for cand in eng.probe(html):
        print(cand.strategy, cand.making_pct, cand.confidence, cand.fields)

Self-test (no network):  python mc_engine.py --selftest
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from typing import Callable, Iterable

IST = timezone(timedelta(hours=5, minutes=30))

# --------------------------------------------------------------------------
# Semantic vocabulary
# --------------------------------------------------------------------------
# Each concept maps to phrasings seen in the wild. Matching is fuzzy, so close
# variants ("Making Charge", "MakingCharges", "Making  Chrg") still resolve.
# Order within a list does not matter; longer phrases are preferred at match
# time so "gold value" beats a bare "gold" when both are present.
CONCEPTS: dict[str, list[str]] = {
    "gold_value": [
        "gold", "gold value", "gold price", "gold amount", "gold cost",
        "gold total", "total gold value", "metal", "metal value",
        "metal price", "metal cost", "gold rate value",
    ],
    "making_charge": [
        "making charge", "making charges", "making", "making cost",
        "value addition", "va charges", "labour", "labour charges",
        "labor charges", "wastage", "wastage charges", "craftsmanship",
    ],
    "stone_value": [
        "stone", "stone value", "diamond", "diamond value", "diamond price",
        "colored stone", "coloured stone", "gemstone", "solitaire",
        "pre set solitaire", "precious stone",
    ],
    "gst": ["gst", "tax", "taxes", "cgst", "sgst", "igst"],
    "total": [
        "total", "grand total", "total price", "final price", "you pay",
        "net payable", "total amount",
    ],
    "weight": [
        "net weight", "gold weight", "metal weight", "gross weight", "weight",
    ],
}

# Concepts that must NOT be confused with making charge when scanning text.
_NEGATIVE_CONTEXT = re.compile(
    r"(?:%\s*off|off\s+on|discount|coupon|use\s+[A-Z0-9]{4,}|offer|save\s+)",
    re.I)

_CUR = r"(?:₹|Rs\.?|INR|\\u20b9)"
_AMT = r"([\d,]+(?:\.\d{1,2})?)"


def _num(s: str | None) -> float | None:
    if not s:
        return None
    try:
        v = float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _norm_label(s: str) -> str:
    """Lowercase, strip punctuation/underscores, collapse whitespace."""
    s = re.sub(r"[_\-]+", " ", str(s or "").lower())
    s = re.sub(r"[^a-z0-9%\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def match_concept(label: str, min_ratio: float = 0.82) -> tuple[str | None, float]:
    """Map an arbitrary label to a known concept via fuzzy matching.

    Returns (concept, score). Exact/substring hits score 1.0; otherwise the
    best SequenceMatcher ratio across the vocabulary is used, which is what
    lets brand-new phrasings resolve without a code change.
    """
    lab = _norm_label(label)
    if not lab:
        return None, 0.0

    best: tuple[str | None, float] = (None, 0.0)
    for concept, phrases in CONCEPTS.items():
        # Prefer the longest phrase that matches, so "gold value" wins over "gold"
        for ph in sorted(phrases, key=len, reverse=True):
            if lab == ph:
                return concept, 1.0
            # whole-word containment either direction
            if re.search(rf"\b{re.escape(ph)}\b", lab) or \
               (len(lab) > 3 and re.search(rf"\b{re.escape(lab)}\b", ph)):
                score = 0.95 + 0.01 * min(len(ph), 5) / 5
                if score > best[1]:
                    best = (concept, min(score, 0.99))
            else:
                r = SequenceMatcher(None, lab, ph).ratio()
                if r >= min_ratio and r > best[1]:
                    best = (concept, r)
    return best


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
@dataclass
class ExtractionResult:
    strategy: str = ""
    making_pct: float | None = None
    confidence: float = 0.0
    fields: dict[str, float] = field(default_factory=dict)
    notes: str = ""

    @property
    def ok(self) -> bool:
        return self.making_pct is not None


def _finish(strategy: str, fields: dict[str, float], notes: str = "") -> ExtractionResult:
    """Turn located field values into a validated making-% result.

    Confidence rewards corroboration: a breakup whose parts reconcile against a
    stated total is far more trustworthy than two numbers found in isolation.
    """
    gold = fields.get("gold_value")
    making = fields.get("making_charge")
    if not gold or not making or gold <= 0:
        return ExtractionResult(strategy, None, 0.0, fields, notes or "missing gold/making")

    ratio = making / gold
    # Plausibility gate: making charge is a fraction of metal value. Above ~120%
    # we are almost certainly reading a total or a stone value by mistake.
    if not (0 < ratio <= 1.2):
        return ExtractionResult(strategy, None, 0.0, fields,
                                f"implausible ratio {ratio:.2f}")

    conf = 0.55
    if fields.get("total"):
        parts = sum(v for k, v in fields.items()
                    if k in ("gold_value", "making_charge", "stone_value", "gst"))
        if parts > 0:
            err = abs(parts - fields["total"]) / fields["total"]
            if err <= 0.02:
                conf = 0.98          # breakup reconciles with the stated total
            elif err <= 0.08:
                conf = 0.85
            else:
                conf = 0.6
    if fields.get("gst"):
        conf = min(0.99, conf + 0.03)
    if ratio > 0.9:                  # legal but unusual; flag it
        conf *= 0.85

    return ExtractionResult(strategy, round(ratio * 100, 1), round(conf, 2),
                            fields, notes)


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------
# Each strategy takes raw html and returns an ExtractionResult. They are tried
# in registry order; every one that succeeds is scored and the best wins.

def s_json_flat_keys(html: str) -> ExtractionResult:
    """JSON key/value pairs anywhere in the page state.

    Matches e.g.  "making_charges":1200 , "gold_value":"14729"
    Keys are fuzzy-matched, so a brand inventing "labourCost" still resolves.
    """
    fields: dict[str, float] = {}
    for m in re.finditer(r'"([A-Za-z_][A-Za-z0-9_ ]{2,40})"\s*:\s*"?'
                         r'(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)"?', html):
        concept, score = match_concept(m.group(1))
        if not concept or score < 0.9:
            continue
        val = _num(m.group(2))
        if val is None or val <= 0:
            continue
        # keep the first plausible hit per concept (page state usually leads
        # with the canonical block; later repeats are per-variant duplicates)
        fields.setdefault(concept, val)
    return _finish("json_flat_keys", fields)


def s_json_breakup_arrays(html: str) -> ExtractionResult:
    """Nested breakup arrays: "making":[{... "value":"Rs. 884" ...}].

    This is CaratLane's shape. The label is the ARRAY key, the amount lives in
    a "value"/"final_value" member, and slashes may be unicode-escaped.
    """
    fields: dict[str, float] = {}
    for m in re.finditer(
            r'"([A-Za-z_][A-Za-z0-9_ ]{2,30})"\s*:\s*\[\s*\{(.{0,400}?)\}',
            html, re.S):
        concept, score = match_concept(m.group(1))
        if not concept or score < 0.9:
            continue
        body = m.group(2)
        vm = re.search(r'"(?:final_value|value)"\s*:\s*"' + _CUR + r'?\.?\s*'
                       + _AMT + r'"', body, re.I)
        if not vm:
            continue
        val = _num(vm.group(1))
        if val and val > 0:
            fields.setdefault(concept, val)
    return _finish("json_breakup_arrays", fields)


def s_dom_breakup_section(html: str) -> ExtractionResult:
    """A dedicated price-breakup DOM block, read as plain text.

    Handles BlueStone (<section id="section-price-breakup">) and any brand that
    renders labelled rows without stable element ids. Scoping to the breakup
    block first is what stops promo banners ("5% off on Making Charges") from
    being mistaken for the real line item.
    """
    block = None
    for pat in (r'<section[^>]*id="[^"]*price-?breakup[^"]*".*?</section>',
                r'<div[^>]*(?:id|class)="[^"]*price-?break-?up[^"]*".*?</div>\s*</div>',
                r'<table[^>]*>(?:(?!</table>).){0,4000}?'
                r'(?:making\s*charge|value\s*addition)'
                r'(?:(?!</table>).){0,4000}?</table>'):
        m = re.search(pat, html, re.I | re.S)
        if m:
            block = m.group(0)
            break
    if not block:
        return ExtractionResult("dom_breakup_section", None, 0.0, {}, "no breakup block")
    return _labelled_text_scan(block, "dom_breakup_section")


def s_labelled_text(html: str) -> ExtractionResult:
    """Last resort: scan the whole page text for labelled rupee amounts.

    Weakest strategy (a page has many rupee amounts), so it is scored lower and
    only wins when nothing structured is available.
    """
    res = _labelled_text_scan(html, "labelled_text")
    if res.ok:
        res.confidence = round(res.confidence * 0.75, 2)
    return res


def _labelled_text_scan(fragment: str, strategy: str) -> ExtractionResult:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = re.sub(r"\s+", " ", text)
    fields: dict[str, float] = {}
    # label ... amount, where the gap holds no other digits (prevents a label
    # binding to a number that belongs to the next row)
    for m in re.finditer(r"([A-Za-z][A-Za-z /&']{2,32}?)\s*[:\-]?\s*"
                         + _CUR + r"\s*" + _AMT, text):
        label, amt = m.group(1), m.group(2)
        window = text[max(0, m.start() - 60):m.start()]
        if _NEGATIVE_CONTEXT.search(window) or _NEGATIVE_CONTEXT.search(label):
            continue                      # promo/discount text, not a line item
        concept, score = match_concept(label)
        if not concept or score < 0.9:
            continue
        val = _num(amt)
        if val and val > 0:
            fields.setdefault(concept, val)
    return _finish(strategy, fields)


def s_direct_percent(html: str) -> ExtractionResult:
    """Brands that publish the making charge as a percentage outright."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    for m in re.finditer(r"(making\s*charges?|value\s*addition|wastage)"
                         r"[^%\d]{0,40}?(\d{1,2}(?:\.\d)?)\s*%", text, re.I):
        window = text[max(0, m.start() - 60):m.start()]
        if _NEGATIVE_CONTEXT.search(window):
            continue
        pct = _num(m.group(2))
        if pct and 0 < pct <= 60:
            return ExtractionResult("direct_percent", round(pct, 1), 0.7,
                                    {"making_pct_direct": pct})
    return ExtractionResult("direct_percent", None, 0.0, {})


STRATEGIES: list[tuple[str, Callable[[str], ExtractionResult]]] = [
    ("json_breakup_arrays", s_json_breakup_arrays),
    ("json_flat_keys", s_json_flat_keys),
    ("dom_breakup_section", s_dom_breakup_section),
    ("direct_percent", s_direct_percent),
    ("labelled_text", s_labelled_text),
]
_BY_NAME = dict(STRATEGIES)


# --------------------------------------------------------------------------
# Robust statistics
# --------------------------------------------------------------------------
def mad_filter(values: list[float], z: float = 3.5) -> tuple[list[float], list[float]]:
    """Median-absolute-deviation outlier rejection.

    Returns (kept, rejected). MAD is used instead of standard deviation because
    a couple of bad extractions would inflate the SD enough to hide themselves,
    whereas the median stays put.
    """
    vals = [v for v in values if v is not None]
    if len(vals) < 4:
        return vals, []
    med = statistics.median(vals)
    devs = [abs(v - med) for v in vals]
    mad = statistics.median(devs)
    if mad == 0:
        return vals, []
    kept, rej = [], []
    for v in vals:
        score = 0.6745 * (v - med) / mad          # modified z-score
        (kept if abs(score) <= z else rej).append(v)
    return kept, rej


def summarize(values: list[float]) -> dict:
    kept, rejected = mad_filter(values)
    if not kept:
        return {"items": 0, "median": None, "min": None, "max": None,
                "rejected": len(rejected), "confidence": "none"}
    n = len(kept)
    conf = "high" if n >= 12 else "medium" if n >= 5 else "low"
    return {
        "items": n,
        "median": round(statistics.median(kept), 1),
        "min": round(min(kept), 1),
        "max": round(max(kept), 1),
        "iqr": ([round(q, 1) for q in statistics.quantiles(kept, n=4)]
                if n >= 4 else None),
        "rejected": len(rejected),
        "confidence": conf,
    }


# --------------------------------------------------------------------------
# Engine (profile learning + drift detection)
# --------------------------------------------------------------------------
@dataclass
class BrandProfile:
    strategy: str = ""
    hits: int = 0
    misses: int = 0
    last_ok: str = ""
    typical: dict = field(default_factory=dict)   # category -> summary

    @property
    def hit_rate(self) -> float:
        t = self.hits + self.misses
        return self.hits / t if t else 0.0


class Engine:
    """Chooses, remembers and re-learns the right strategy per brand."""

    def __init__(self, profiles: dict[str, BrandProfile] | None = None):
        self.profiles: dict[str, BrandProfile] = profiles or {}

    # ---- persistence -----------------------------------------------------
    @classmethod
    def load(cls, path: str) -> "Engine":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls({b: BrandProfile(**p) for b, p in raw.get("brands", {}).items()})

    def save(self, path: str) -> None:
        payload = {
            "updated": datetime.now(IST).isoformat(),
            "note": "Learned extraction profiles. Auto-maintained by mc_engine.",
            "brands": {b: asdict(p) for b, p in sorted(self.profiles.items())},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    # ---- extraction ------------------------------------------------------
    def probe(self, html: str) -> list[ExtractionResult]:
        """Run every strategy; return successes best-first (for debugging)."""
        out = [fn(html) for _, fn in STRATEGIES]
        return sorted([r for r in out if r.ok],
                      key=lambda r: r.confidence, reverse=True)

    def extract(self, html: str, brand: str = "") -> ExtractionResult:
        """Learned strategy first, full probe as fallback; relearn on drift."""
        prof = self.profiles.get(brand)

        if prof and prof.strategy in _BY_NAME:
            res = _BY_NAME[prof.strategy](html)
            if res.ok:
                prof.hits += 1
                prof.last_ok = datetime.now(IST).isoformat()
                return res
            prof.misses += 1          # drift: fall through and re-probe

        ranked = self.probe(html)
        if not ranked:
            if brand:
                p = self.profiles.setdefault(brand, BrandProfile())
                p.misses += 1
            return ExtractionResult("none", None, 0.0, {}, "all strategies failed")

        best = ranked[0]
        if brand:
            p = self.profiles.setdefault(brand, BrandProfile())
            if p.strategy != best.strategy:
                p.strategy = best.strategy      # learn / relearn
            p.hits += 1
            p.last_ok = datetime.now(IST).isoformat()
        return best

    # ---- analysis --------------------------------------------------------
    def record(self, brand: str, category: str, values: list[float]) -> dict:
        """Store a category summary and report drift vs. the previous run."""
        s = summarize(values)
        p = self.profiles.setdefault(brand, BrandProfile())
        prev = p.typical.get(category)
        if prev and prev.get("median") and s.get("median"):
            delta = s["median"] - prev["median"]
            s["drift_vs_last"] = round(delta, 1)
            # A large jump usually means the page changed and we are now
            # reading a different number - worth surfacing, not silently using.
            s["drift_flag"] = abs(delta) > max(5.0, 0.35 * prev["median"])
        p.typical[category] = s
        return s

    def report(self) -> str:
        lines = ["brand                strategy                hit%   cats"]
        for b, p in sorted(self.profiles.items()):
            lines.append(f"{b:<20} {p.strategy or '-':<22} "
                         f"{p.hit_rate * 100:5.1f}  {len(p.typical)}")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Self-test (offline fixtures - no network, safe to run in CI)
# --------------------------------------------------------------------------
_FIXTURES = [
    # BlueStone: DOM section, plain-text rows, plus a promo trap above it
    ("BlueStone", """
     <div class="offers">5% off on Making Charges: Use RADIANCE5</div>
     <section id="section-price-breakup"><h2>Price Breakup</h2><table>
     <tr><td class="item-type-title">Gold</td><td><span>Rs.</span>
     <span id="goldCost_b">79,240</span></td></tr>
     <tr><td>Making Charges</td><td>Rs. 23,930</td></tr>
     <tr><td>GST</td><td>Rs. 3,096</td></tr>
     <tr><td>Total</td><td>Rs. 1,06,266</td></tr></table></section>""",
     30.2, "dom_breakup_section"),

    # CaratLane: nested JSON arrays with unicode-escaped currency
    ("CaratLane", """{"price_breakup":{"gold":[{"title":"995 Kt Yellow Gold",
     "rate":"Rs. 14729\\u002Fg","value":"Rs. 14729"}],
     "gold_total":[{"title":"Total Gold Value","value":"Rs. 14729"}],
     "making":[{"title":"Making Charge","value":"Rs. 884"}],
     "tax":[{"title":"GST","value":"Rs. 468"}],
     "total":[{"title":"Grand Total","value":"Rs. 16081"}]}}""",
     6.0, "json_breakup_arrays"),

    # WHP-style flat JSON keys, absolute making charge
    ("WHP", """{"sku":"X","making_charges":1200,"stone_charges":null,
     "gold_value":"48000","gst":1476,"total":"50676"}""",
     2.5, "json_flat_keys"),

    # Brand publishing a straight percentage
    ("PercentBrand", "<p>Making charges: 12% of gold value</p>", 12.0,
     "direct_percent"),

    # Unseen phrasing ("Value Addition" + "Metal Value") must still resolve
    ("NovelPhrasing", """<div class="price-breakup"><table>
     <tr><td>Metal Value</td><td>Rs. 50,000</td></tr>
     <tr><td>Value Addition</td><td>Rs. 10,000</td></tr>
     <tr><td>Total</td><td>Rs. 60,000</td></tr></table></div>""",
     20.0, None),
]


def _selftest() -> int:
    eng = Engine()
    failures = 0

    print("== extraction ==")
    for brand, html, expect_pct, expect_strategy in _FIXTURES:
        res = eng.extract(html, brand=brand)
        got = res.making_pct
        ok = got is not None and abs(got - expect_pct) <= 0.35
        if expect_strategy and res.strategy != expect_strategy:
            ok = False
        print(f"  {'PASS' if ok else 'FAIL'}  {brand:<14} "
              f"got={got} want={expect_pct} via={res.strategy} "
              f"conf={res.confidence} fields={res.fields}")
        failures += 0 if ok else 1

    print("\n== negative control (promo text must not yield a rate) ==")
    junk = "<div>Flat 20% off on Making Charges this weekend! Use CODE20</div>"
    r = eng.extract(junk, brand="JunkBrand")
    ok = not r.ok
    print(f"  {'PASS' if ok else 'FAIL'}  got={r.making_pct} ({r.notes})")
    failures += 0 if ok else 1

    print("\n== fuzzy concept matching ==")
    for label, want in [("Making Charge", "making_charge"),
                        ("making_charges", "making_charge"),
                        ("Value Addition", "making_charge"),
                        ("Metal Value", "gold_value"),
                        ("Total Gold Value", "gold_value"),
                        ("Grand Total", "total"),
                        ("Colored Stone", "stone_value"),
                        ("Delivery Address", None)]:
        got, score = match_concept(label)
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label:<20} -> {got} ({score:.2f})")
        failures += 0 if ok else 1

    print("\n== MAD outlier rejection ==")
    vals = [28.0, 29.5, 30.0, 30.2, 31.0, 29.0, 300.0]   # 300 is garbage
    kept, rej = mad_filter(vals)
    ok = 300.0 in rej and len(kept) == 6
    print(f"  {'PASS' if ok else 'FAIL'}  kept={kept} rejected={rej}")
    failures += 0 if ok else 1

    print("\n== summary + confidence ==")
    s = summarize([30.0, 31.0, 29.0, 30.5, 30.2])
    ok = s["items"] == 5 and s["confidence"] == "medium"
    print(f"  {'PASS' if ok else 'FAIL'}  {s}")
    failures += 0 if ok else 1

    print("\n== profile learning + drift ==")
    eng.record("BlueStone", "Bangle", [30.2, 31.0, 29.8, 30.1, 30.5])
    s2 = eng.record("BlueStone", "Bangle", [44.0, 45.0, 43.5, 44.2, 44.8])
    ok = s2.get("drift_flag") is True
    print(f"  {'PASS' if ok else 'FAIL'}  drift={s2.get('drift_vs_last')} "
          f"flag={s2.get('drift_flag')}")
    failures += 0 if ok else 1

    prof = eng.profiles.get("BlueStone")
    ok = prof is not None and prof.strategy == "dom_breakup_section"
    print(f"  {'PASS' if ok else 'FAIL'}  learned strategy = "
          f"{prof.strategy if prof else None}")
    failures += 0 if ok else 1

    print("\n== learned fast-path is reused ==")
    before = eng.profiles["BlueStone"].hits
    eng.extract(_FIXTURES[0][1], brand="BlueStone")
    ok = eng.profiles["BlueStone"].hits == before + 1
    print(f"  {'PASS' if ok else 'FAIL'}  hits {before} -> "
          f"{eng.profiles['BlueStone'].hits}")
    failures += 0 if ok else 1

    print("\n" + eng.report())
    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILURE(S)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print(__doc__)
