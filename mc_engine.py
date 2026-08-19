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
    # Plausibility gate. Upper bound: above ~120% we are almost certainly
    # reading a total or a stone value by mistake. Lower bound: no jeweller
    # crafts for under ~2% - a tiny ratio means a unit mismatch (e.g. reading a
    # percentage as a rupee amount), which previously published "Ring 0.1%".
    if not (0.02 <= ratio <= 1.2):
        return ExtractionResult(strategy, None, 0.0, fields,
                                f"implausible ratio {ratio:.4f}")

    # Any real stone/diamond content excludes a piece, not just a dominant
    # one. Making charge as %-of-GOLD-value only means "what a plain gold
    # piece in this category costs to make" when the piece actually IS plain
    # gold - several brands apply steep (sometimes near-total) making-charge
    # discounts on studded jewellery, since the stone markup already covers
    # labour, so even a modest accent stone quietly understates what a real
    # gold-only purchase costs to make. The threshold (3% of gold value, floor
    # ₹200) exists only to tolerate float/rounding noise on genuinely plain
    # items that carry a stray stone_value: 0 field, not to admit real stones.
    stone = fields.get("stone_value")
    if stone and stone > max(0.03 * gold, 200):
        return ExtractionResult(strategy, None, 0.0, fields,
                                f"studded/diamond (stone {stone:.0f}), excluded")

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

def s_json_typed_percent(html: str) -> ExtractionResult:
    """Brands that publish the making charge as a PERCENTAGE in JSON.

    Senco ships {"making_charge_type":"percentage","making_charge":27} - the 27
    is already a percent, not rupees. Treating it as an amount and dividing by
    gold value yields nonsense (27/50000 = 0.05%), which is exactly the
    regression this strategy exists to prevent. Must run before the flat-key
    strategy so the typed case wins.
    """
    tm = re.search(r'"(?:making_charge_type|making_charges_type|mc_type)"\s*:\s*'
                   r'"([a-z%]+)"', html, re.I)
    if not tm or "percent" not in tm.group(1).lower():
        return ExtractionResult("json_typed_percent", None, 0.0, {})
    vm = re.search(r'"(?:making_charge|making_charges|mc_value)"\s*:\s*"?'
                   r'([\d.]+)"?', html, re.I)
    pct = _num(vm.group(1)) if vm else None
    if pct is None or not (0 < pct <= 60):
        return ExtractionResult("json_typed_percent", None, 0.0, {},
                                "typed percent out of range")
    return ExtractionResult("json_typed_percent", round(pct, 1), 0.9,
                            {"making_pct_direct": pct})


def s_json_flat_keys(html: str) -> ExtractionResult:
    """JSON key/value pairs anywhere in the page state.

    Matches e.g.  "making_charges":1200 , "gold_value":"14729"
    Keys are fuzzy-matched, so a brand inventing "labourCost" still resolves.
    """
    # If the page declares the making charge as a percentage, the numeric
    # value is NOT a rupee amount - defer to s_json_typed_percent.
    tm = re.search(r'"(?:making_charge_type|making_charges_type|mc_type)"\s*:\s*'
                   r'"([a-z%]+)"', html, re.I)
    if tm and "percent" in tm.group(1).lower():
        return ExtractionResult("json_flat_keys", None, 0.0, {},
                                "deferred: typed percentage")
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


def s_js_object_literal(html: str) -> ExtractionResult:
    """Unquoted JS object-literal keys: `metal_price: 20605.0, making_charges: 2375.0`.

    Some Shopify themes emit a plain JS object (not JSON-quoted) for the
    per-variant price breakup, e.g.
        const variantsData = {"123": {metal_price: 20605.0,
        making_charges: 2375.0, price: 2825400, ...}};
    json_flat_keys requires quoted `"key":` and misses this shape entirely -
    seen on PN Gadgil, where it previously yielded zero items even though
    the exact rupee breakup is sitting in the page.

    Pairing is done by PROXIMITY, not "first occurrence per concept" (what
    json_flat_keys does): a large real page has plenty of unrelated
    label-like-token-followed-by-number pairs (e.g. a CSS custom property
    `--colors-price: 255, 255, 255;` fuzzy-matches the "gold_value" concept
    via the bare word "price"). Taking the document-wide first match per
    concept let that CSS value win the "gold_value" slot ahead of the real,
    co-located variant block further down the page, silently producing no
    result (the ratio against the real making charge was implausible and
    got rejected) even though the correct pair was sitting right there.
    Requiring the two labels to be near each other - the way they actually
    appear together inside one variant object - fixes that.
    """
    tm = re.search(r'\b(?:making_charge_type|making_charges_type|mc_type)\s*:\s*'
                   r'[\'"]([a-z%]+)[\'"]', html, re.I)
    if tm and "percent" in tm.group(1).lower():
        return ExtractionResult("js_object_literal", None, 0.0, {},
                                "deferred: typed percentage")
    matches: list[tuple[int, str, float]] = []
    for m in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]{2,40})\s*:\s*'
                         r'(?:[\'"]\s*)?(?:₹|Rs\.?|INR)?\s*(-?[\d,]+(?:\.\d{1,4})?)\b',
                         html):
        concept, score = match_concept(m.group(1))
        if not concept or score < 0.9:
            continue
        val = _num(m.group(2))
        if val is None or val <= 0:
            continue
        matches.append((m.start(), concept, val))

    window = 400
    for pos, concept, val in matches:
        if concept != "making_charge":
            continue
        # Try every nearby gold_value candidate, closest first, instead of
        # committing to the single nearest one - a generic label like bare
        # "price" fuzzy-matches gold_value too (it's a whole word inside
        # "gold price"/"metal price") and can sit closer than the real
        # "metal_price" field while pairing with an implausible ratio (e.g.
        # the sibling total-price-in-paise field). Falling through to the
        # next candidate on an implausible ratio recovers the real pairing.
        candidates = sorted(
            (abs(pos2 - pos), val2)
            for pos2, concept2, val2 in matches
            if concept2 == "gold_value" and abs(pos2 - pos) <= window)
        for _, gold_val in candidates:
            fields = {"gold_value": gold_val, "making_charge": val}
            for pos2, concept2, val2 in matches:
                if concept2 in ("stone_value", "gst", "total") and abs(pos2 - pos) <= window:
                    fields.setdefault(concept2, val2)
            res = _finish("js_object_literal", fields)
            if res.ok:
                return res
    return ExtractionResult("js_object_literal", None, 0.0, {}, "no nearby pair")


def s_weight_rate_join(html: str) -> ExtractionResult:
    """Join a per-karat gold RATE table with a variant's weight + flat making charge.

    Some brands publish these as two separate static objects instead of a
    precomputed gold value, because the final price is meant to be assembled
    client-side: a per-karat ₹/gram table (e.g. WHP's `metalPriceConfig =
    {"gold_price_18k":12161,...}`) plus a variant's `metal_weight` (grams),
    `purity` (karat) and flat `making_charges` (₹). Both pieces are present in
    static HTML - the only thing missing is the multiplication, which we do
    here instead of needing a browser to run the page's own JS.
    """
    rm = re.search(r'metalPriceConfig\s*=\s*(\{.*?\})\s*(?:\|\|\s*\{\})?;', html, re.S)
    if not rm:
        return ExtractionResult("weight_rate_join", None, 0.0, {}, "no rate table")
    try:
        rates = json.loads(rm.group(1))
    except (json.JSONDecodeError, ValueError):
        return ExtractionResult("weight_rate_join", None, 0.0, {}, "bad rate JSON")

    vm = re.search(
        r'"metal_type"\s*:\s*"gold"\s*,\s*"purity"\s*:\s*"(\d+)K?"\s*,\s*'
        r'"metal_weight"\s*:\s*([\d.]+)\s*,\s*"diamond_charges"\s*:\s*(null|[\d.]+)'
        r'.{0,400}?"making_charges"\s*:\s*([\d.]+)(.{0,300}?)(?:\}|$)',
        html, re.I | re.S)
    if not vm:
        return ExtractionResult("weight_rate_join", None, 0.0, {}, "no variant match")
    # Not every variant means "making_charges" as a flat rupee amount - a
    # sibling "remarks" field says so explicitly ("fixed" vs "percentage").
    # Seen on a WHP plain-gold kada: making_charges:200 with remarks:
    # "percentage" is NOT ₹200, and blindly dividing it by gold value like
    # the normal (rupee) case produced a nonsense >100% "rate". Rather than
    # guess the right scale for the percentage variant, skip it - the
    # regular (fixed-rupee) variants cover most of the catalogue anyway.
    tail = vm.group(5)
    rm2 = re.search(r'"remarks"\s*:\s*"(fixed|percentage)"', tail, re.I)
    if rm2 and rm2.group(1).lower() == "percentage":
        return ExtractionResult("weight_rate_join", None, 0.0, {},
                                "making_charges is percentage-typed, not rupees")
    purity, weight = vm.group(1), _num(vm.group(2))
    diamond, making = _num(vm.group(3)), _num(vm.group(4))
    rate = rates.get(f"gold_price_{purity}k")
    if not rate or not weight or not making:
        return ExtractionResult("weight_rate_join", None, 0.0, {}, "missing join fields")
    gold_value = rate * weight
    fields = {"gold_value": round(gold_value, 2), "making_charge": making}
    if diamond:
        fields["stone_value"] = diamond
    return _finish("weight_rate_join", fields)


def s_escaped_json_block(html: str) -> ExtractionResult:
    """A named JSON object embedded as an ESCAPED STRING inside a larger payload.

    e.g. GRT: \\"product_price_details\\":{\\"metal_value\\":20952.425,
    \\"making_charge\\":4442.755,\\"making_charge_with_discount\\":3554.204,
    \\"gst_with_discount\\":735.199,...} - a whole nested JSON object
    re-serialized as a string (backslash before every quote), sitting inside
    the page's own bootstrap JSON. None of the other strategies' `"key":`
    patterns can match this at all - it isn't a different data shape, the
    escaping just breaks literal quote-matching. Locate the named block by
    brace-balancing (values are flat, so no nested braces to worry about),
    unescape, and parse it directly instead of re-deriving field positions.

    A product page repeats this block once per size/variant, and the FIRST
    occurrence is typically an unselected placeholder (metal_value: null,
    making_charge: 0) rather than real data - skip those and take the first
    block with an actual gold value.

    making_charge_with_discount (post-discount) is preferred over the flat
    making_charge field, matching every other brand seen so far where the
    discounted figure is what a customer actually pays.
    """
    for m in re.finditer(r'\\"product_price_details\\"\s*:\s*\{', html):
        start = m.end() - 1
        depth, end = 0, None
        for i in range(start, min(start + 2000, len(html))):
            c = html[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            obj = json.loads(html[start:end].replace('\\"', '"'))
        except (json.JSONDecodeError, ValueError):
            continue
        gold = obj.get("metal_value") or obj.get("final_metal_value")
        making = obj.get("making_charge_with_discount") or obj.get("making_charge")
        if not gold or not making:
            continue          # placeholder block - keep scanning
        fields = {"gold_value": gold, "making_charge": making}
        if obj.get("stone_amount"):
            fields["stone_value"] = obj["stone_amount"]
        gst = obj.get("gst_with_discount") or obj.get("gst_without_discount")
        if gst:
            fields["gst"] = gst
        total = obj.get("grand_total_with_discount") or obj.get("total_with_discount")
        if total:
            fields["total"] = total
        return _finish("escaped_json_block", fields)
    return ExtractionResult("escaped_json_block", None, 0.0, {}, "no valid product_price_details block")


def s_rsc_price_breakup(html: str) -> ExtractionResult:
    """Next.js App Router RSC streaming payload with priceType-tagged line items.

    e.g. Kisna: `self.__next_f.push([1,"...f6:{\\"price\\":13062,
    \\"weight\\":2.27,\\"priceType\\":\\"metalPrice\\",\\"metalType\\":
    \\"gold\\",...}\\nf7:{\\"price\\":8127,\\"priceType\\":\\"makingCharge\\",
    \\"extraChargeType\\":\\"Making Charges\\",...}..."])`. This looked like a
    brand with genuinely zero static pricing on first pass - the price
    panel's initial DOM is an empty skeleton, and there's no `__NEXT_DATA__`
    tag (App Router doesn't use one). The real numbers are there, just
    streamed as escaped JSON fragments keyed by a distinct `priceType`
    rather than nested under one named object - each line item is found by
    its own tag instead of brace-balancing a single block.
    """
    gm = re.search(r'\\"price\\"\s*:\s*([\d.]+)\s*,\s*\\"weight\\"\s*:\s*[\d.]+\s*,\s*'
                   r'\\"priceType\\"\s*:\s*\\"metalPrice\\"', html)
    mm = re.search(r'\\"price\\"\s*:\s*([\d.]+)\s*,\s*\\"priceType\\"\s*:\s*\\"makingCharge\\"', html)
    if not gm or not mm:
        return ExtractionResult("rsc_price_breakup", None, 0.0, {}, "no metalPrice/makingCharge pair")
    fields = {"gold_value": _num(gm.group(1)), "making_charge": _num(mm.group(1))}
    sm = re.search(r'\\"price\\"\s*:\s*([\d.]+)\s*,\s*\\"weight\\"\s*:\s*[\d.]+\s*,\s*'
                   r'\\"priceType\\"\s*:\s*\\"stonePrice\\"', html)
    if sm:
        fields["stone_value"] = _num(sm.group(1))
    return _finish("rsc_price_breakup", fields)


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
    signal = re.compile(r"making\s*charge|value\s*addition", re.I)
    block = None
    for pat in (r'<section[^>]*id="[^"]*price-?breakup[^"]*".*?</section>',
                r'<div[^>]*(?:id|class)="[^"]*price-?break-?up[^"]*".*?</div>\s*</div>',
                r'<table[^>]*>(?:(?!</table>).){0,4000}?'
                r'(?:making\s*charge|value\s*addition)'
                r'(?:(?!</table>).){0,4000}?</table>'):
        m = re.search(pat, html, re.I | re.S)
        # A match alone isn't enough to accept the block: the div pattern's
        # ".*?</div></div>" is a lazy, arbitrary stopping point on deeply
        # nested markup - it can "successfully" match a wrong, truncated
        # chunk (e.g. an unrelated cart widget) that closes two divs before
        # the real breakup content ever appears. Without a content check,
        # that wrong match short-circuits the loop before it ever tries the
        # table pattern below, which would have matched correctly - verified
        # live on C Krishniah Chetty, whose real breakup table sits right
        # after a "price-breakup" div wrapper deep enough to fool the div
        # pattern. Require the same making-charge/value-addition signal
        # inside the match before accepting it, same bar every candidate
        # pattern already has to clear on its own.
        if m and signal.search(m.group(0)):
            block = m.group(0)
            break
    if not block:
        return ExtractionResult("dom_breakup_section", None, 0.0, {}, "no breakup block")
    return _labelled_text_scan(block, "dom_breakup_section")


def s_table_row_columns(html: str) -> ExtractionResult:
    """A price-breakup table with extra columns between label and value.

    _labelled_text_scan requires the currency amount right after the label
    (only a colon/dash and whitespace in between) - correct for a plain
    "Making Charges: Rs.1,234" row, but it breaks on a table that has a
    weight/quantity column in the middle, e.g. C Krishniah Chetty's
    Component | Approx. Weight | Value | Final Value rows ("18Kt Gold |
    3.078 Grams | Rs.36,390.18 | Rs.36,390.18") - "3.078 Grams" between the
    label and the amount stops the label-adjacent-amount pattern from
    matching at all, so gold_value never gets picked up even though making_
    charge (whose row has no weight column) does. Read row by row instead:
    first <td> is the label, the LAST <td> containing a currency amount in
    that row is its value (the final/total column, not an interim weight).
    """
    fields: dict[str, float] = {}
    for row_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_m.group(1), re.I | re.S)
        if len(cells) < 2:
            continue
        label = re.sub(r"<[^>]+>", " ", cells[0])
        label = re.sub(r"\s+", " ", label).strip()
        if not label or _NEGATIVE_CONTEXT.search(label):
            continue
        concept, score = match_concept(label)
        if not concept or score < 0.9:
            continue
        amount = None
        for cell in cells[1:]:
            text = re.sub(r"<[^>]+>", " ", cell)
            m = re.search(_CUR + r"\s*" + _AMT, text)
            if m:
                amount = _num(m.group(1))
        if amount and amount > 0:
            fields.setdefault(concept, amount)
    return _finish("table_row_columns", fields)


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
    """Brands that publish the making charge as a percentage outright.

    The gap between label and "%" is deliberately short and excludes other
    line-item words (gst/tax/discount/...) - a wide gap previously let e.g.
    "Making Charges Discount GST (3%)" bind the GST row's percentage to the
    making-charge label (seen on WHP: shipped 3.0% via this row when the
    real figure, computable from the page's own weight+rate data, is 22.9%).
    """
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    for m in re.finditer(r"(making\s*charges?|value\s*addition|wastage)"
                         r"(?![^%\d]*?\b(?:gst|tax|cgst|sgst|discount|off|save[ds]?)\b)"
                         r"[^%\d]{0,20}?(\d{1,2}(?:\.\d)?)\s*%", text, re.I):
        window = text[max(0, m.start() - 60):m.start()]
        if _NEGATIVE_CONTEXT.search(window):
            continue
        pct = _num(m.group(2))
        if pct and 0 < pct <= 60:
            return ExtractionResult("direct_percent", round(pct, 1), 0.7,
                                    {"making_pct_direct": pct})
    return ExtractionResult("direct_percent", None, 0.0, {})


STRATEGIES: list[tuple[str, Callable[[str], ExtractionResult]]] = [
    ("json_typed_percent", s_json_typed_percent),   # must precede flat_keys
    ("weight_rate_join", s_weight_rate_join),       # specific join, try early
    ("escaped_json_block", s_escaped_json_block),
    ("rsc_price_breakup", s_rsc_price_breakup),
    ("json_breakup_arrays", s_json_breakup_arrays),
    ("json_flat_keys", s_json_flat_keys),
    ("js_object_literal", s_js_object_literal),
    ("dom_breakup_section", s_dom_breakup_section),
    ("table_row_columns", s_table_row_columns),
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

    # REGRESSION GUARD (Senco): making_charge is a PERCENTAGE, not rupees.
    # Reading 27 as an amount and dividing by gold value shipped "Ring 0.1%"
    # to production. The typed-percent strategy must win here.
    ("SencoTyped", """{"variant":{"gold_value":"52000","making_charge_type":
     "percentage","making_charge":27,"gst":1560}}""",
     27.0, "json_typed_percent"),
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

    print("\n== plausibility floor (unit-mismatch guard) ==")
    # gold 50000 + making 27 -> 0.054%, physically impossible; must be rejected
    r = _finish("test", {"gold_value": 50000.0, "making_charge": 27.0})
    ok = not r.ok
    print(f"  {'PASS' if ok else 'FAIL'}  0.05% rejected -> {r.making_pct} ({r.notes})")
    failures += 0 if ok else 1
    r = _finish("test", {"gold_value": 50000.0, "making_charge": 15000.0})
    ok = r.ok and abs(r.making_pct - 30.0) < 0.1
    print(f"  {'PASS' if ok else 'FAIL'}  30% accepted -> {r.making_pct}")
    failures += 0 if ok else 1

    print("\n== studded/diamond exclusion (plain gold only) ==")
    # Stone value >= gold value: a diamond-dominated piece where the making
    # charge isn't representative of a plain gold item - must be rejected
    # even though the ratio itself (10%) is perfectly plausible on its own.
    r = _finish("test", {"gold_value": 5000.0, "making_charge": 500.0,
                          "stone_value": 45000.0})
    ok = not r.ok and "studded" in r.notes
    print(f"  {'PASS' if ok else 'FAIL'}  diamond-dominated rejected -> "
          f"{r.making_pct} ({r.notes})")
    failures += 0 if ok else 1
    # A modest accent stone, well under the gold value, is still a real
    # stone - the comparison is plain-gold-only, so it must be rejected too.
    r = _finish("test", {"gold_value": 50000.0, "making_charge": 10000.0,
                          "stone_value": 8000.0})
    ok = not r.ok and "studded" in r.notes
    print(f"  {'PASS' if ok else 'FAIL'}  modest accent stone rejected -> "
          f"{r.making_pct} ({r.notes})")
    failures += 0 if ok else 1
    # A negligible/rounding-noise stone_value (well under the tolerance
    # floor) must not disqualify an otherwise plain gold item.
    r = _finish("test", {"gold_value": 50000.0, "making_charge": 10000.0,
                          "stone_value": 50.0})
    ok = r.ok and abs(r.making_pct - 20.0) < 0.1
    print(f"  {'PASS' if ok else 'FAIL'}  negligible stone accepted -> {r.making_pct}")
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
