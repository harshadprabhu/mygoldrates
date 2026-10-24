"""Reading jeweller offers, and what the offers page says about them."""
import offers as O
import offers_page as P


def _one(text, kind):
    return [o for o in O.extract_offers(text, "https://x.in/") if o["kind"] == kind]


def test_reads_making_charge_discounts_in_their_usual_wordings():
    for t in ("Upto 20% off on Gold jewellery making charges",
              "Flat 20% OFF on Value Addition (VA)",
              "Making charges flat 25% off this Diwali"):
        hits = _one(t, "making_off")
        assert hits and hits[0]["pct"] in (20.0, 25.0), t
    assert _one("Upto 20% off on Gold jewellery making charges", "making_off")[0]["upto"]
    assert _one("Up To 100% Off On Making Charges", "making_off")[0]["pct"] == 100.0


def test_customer_reviews_and_other_markets_are_not_offers():
    assert not O.extract_offers("They gave 10% discount on our purchase value. We really happy", "u")
    assert not O.extract_offers("Flash Sale 70% OFF STARTING AT $ 199", "u")


def test_diamond_and_scheme_offers_are_not_read_as_making_discounts():
    assert not _one("15% OFF on Diamond Value", "making_off")
    assert _one("15% OFF on Diamond Value", "diamond_off")
    hits = O.extract_offers("12 month plan 50% discount on Value Addition", "u")
    assert hits and all(h["kind"] == "scheme" for h in hits)


def test_fine_print_and_coverage_are_kept():
    raw = (O.extract_offers("Enjoy 0% deduction on old gold exchange & buyback facility for Senco jewellery", "u")
           + O.extract_offers("Gold Rate Protection are valid only if final billing is completed within 30 days", "u")
           + O.extract_offers("Double Gold Rate Protection offer", "u"))
    s = {o["kind"]: o for o in O.summarise(raw)}
    assert "only jewellery bought from them" in s["exchange"]["applies_to"]
    assert s["rate_protect"]["text"] == "Double Gold Rate Protection offer"
    assert s["rate_protect"]["conditions"]


def test_product_repeats_fold_into_one_range():
    raw = sum((O.extract_offers(f"Ring {i} {p}% off on making charges", "u")
               for i, p in enumerate((5, 10, 15, 15))), [])
    s = O.summarise(raw)
    assert len(s) == 1 and (s[0]["pct_min"], s[0]["pct_max"]) == (5.0, 15.0)
    assert s[0]["selected"]


def test_ring_price_ranks_after_offers_and_keeps_up_to_as_best_case():
    data = {"brands": [
        {"slug": "a", "name": "A", "offers": [
            {"kind": "making_off", "pct_min": 20.0, "pct_max": 20.0, "upto": False,
             "selected": False, "applies_to": []}]},
        {"slug": "b", "name": "B", "offers": [
            {"kind": "making_off", "pct_min": 50.0, "pct_max": 50.0, "upto": True,
             "selected": False, "applies_to": []}]}]}
    mc = {"brands": [{"brand": "A", "categories": [{"category": "Ring", "making_pct_median": 18.0}]},
                     {"brand": "B", "categories": [{"category": "Ring", "making_pct_median": 12.0}]}]}
    rows = P.ring_prices(data, mc, {"a": 12000.0, "b": 12000.0})
    a, b = {r["slug"]: r for r in rows}["a"], {r["slug"]: r for r in rows}["b"]
    # A: 18% making, 20% off -> 14.4%; B: 12%, its "up to" is not counted.
    assert round(a["after"]) == round(120000 * 1.144 * 1.03)
    assert round(b["after"]) == round(120000 * 1.12 * 1.03)
    assert b["best_case"] and b["best_case"] < b["after"]
    assert rows[0]["slug"] == "b"           # lower making beats a bigger discount


def test_the_page_never_uses_the_word_scraping():
    body, faq, _ = P.build_body({"brands": [{"slug": "a", "name": "A", "status": "ok",
        "offers": [{"kind": "exchange", "pct_min": None, "pct_max": None, "upto": False,
                    "selected": False, "applies_to": [], "conditions": [],
                    "text": "0% deduction", "url": "https://a.in/"}]}]},
        {}, {}, 13000, "24 October 2026", "https://mygoldrates.com", "")
    assert "scrap" not in (body + str(faq)).lower()


def test_making_charge_is_matched_by_website_not_by_similar_name():
    mc = {"brands": [{"brand": "PN Gadgil", "categories": [{"category": "Ring",
          "making_pct_median": 16.4, "examples": [{"url": "https://www.pngjewellers.com/p/x"}]}]}]}
    assert P.making_for(mc, "PN Gadgil", "www.pngjewellers.com") == 16.4
    assert P.making_for(mc, "PN Gadgil & Sons", "pngadgilandsons.com") is None


def test_a_customer_review_is_never_an_offer():
    """CaratLane, 24 Oct 2026: a review was published as a 100% offer."""
    assert not O.extract_offers(
        "Beautiful necklace, got 100% discount on making charges making it worth it", "u")


def test_an_implausible_flat_discount_never_enters_the_ranking():
    data = {"brands": [{"slug": "a", "name": "A", "offers": [
        {"kind": "making_off", "pct_min": 100.0, "pct_max": 100.0, "upto": False,
         "selected": False, "applies_to": []}]}]}
    mc = {"brands": [{"brand": "A", "categories": [{"category": "Ring", "making_pct_median": 20.0}]}]}
    r = P.ring_prices(data, mc, {"a": 12000.0})[0]
    assert r["flat_pct"] == 0 and r["after"] == r["before"]
    assert r["best_case"]                      # shown only as a best case
