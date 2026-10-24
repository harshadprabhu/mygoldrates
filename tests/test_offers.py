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


def test_a_site_showing_us_its_international_version_is_skipped():
    html = "".join(f'<img src="/media/bsimages/collection-{i}-web-intl.jpg">' for i in range(4))
    assert O.international(html)
    assert O.international("<p>Get a FREE pendant on purchases of $300, $500 and $1000 and $2000</p>")
    assert not O.international("<p>₹13,050 per gram, ₹1,30,500 for 10 g</p>")
    # everyday addresses are not country markers
    assert not O.international('<script src="/js/intl-tel-input.min.js"></script>' * 4)
    assert not O.international('<a href="/contact-us/">x</a><a href="/about-us.html">y</a>'
                               '<a href="/pages/us-policy">z</a><a href="/why-us/">w</a>')


def test_banner_text_from_ocr_reads_like_page_text():
    """CaratLane's banner (24 Oct 2026), as Tesseract reads it: the '%' after
    'FLAT 20' is stylised and comes back missing."""
    txt = "FLAT\n20 Off\nOn All Diamond Jewellery\n5% INSTANT DISCOUNT ON CREDIT CARDS\nValid till 31st Oct 2026. T&C Apply"
    got = {o["kind"]: o for o in O.extract_offers(txt, "https://x.in/", image="https://x.in/b.jpg")}
    assert got["diamond_off"]["pct"] == 20.0 and got["diamond_off"]["image"]
    assert got["cashback"]["pct"] == 5.0


def test_a_big_figure_from_a_banner_is_left_out_and_buy_more_is_named():
    """Jewel One's banner, 24 Oct 2026."""
    txt = ("BUY 1 DIAMOND\nJEWELLERY\nGOLD JEWELLERY\nGET YOUR 2ND AT 15% OFF\n100% OFF\nON DIAMOND")
    got = O.extract_offers(txt, "u", image="i")
    assert not any((o["pct"] or 0) >= 50 for o in got)
    assert any(o["kind"] == "combo" for o in got)


def test_stylised_banner_figures_are_read_right():
    """PN Gadgil & Sons' banner (24 Oct 2026): "lOO ON MAKING CHARGES OF
    CERTIFIED NATURAL DIAMOND JEWELLERY ... Offer Valid Till 15 Nov 2026"."""
    txt = "lOO\nON MAKING CHARGES OF CERTIFIED\nNATURAL DIAMOND JEWELLERY\nOffer Valid Till 15 Nov 2026 *T&C Apply"
    assert "100% ON MAKING" in O._ocr_prepare(txt)


def test_rate_lock_wording_is_rate_protection():
    """Khimji's banner: lock your gold rate / get it at the booked rate."""
    assert _one("LOCK YOUR GOLD RATE AT JEWELLERY ADVANCE", "rate_protect")
    assert _one("PRICE HIKED? GET YOUR GOLD JEWELLERY AT THE BOOKED RATE", "rate_protect")


def test_a_redirect_abroad_is_followed_back_to_the_indian_store():
    class R:
        def __init__(self, url, text): self.url, self.text, self.status_code = url, text, 200
    class S:
        def get(self, u, timeout=0): return R("https://x.com/in/pan-india/en/", "<p>₹13,000</p>")
    html = '<a href="https://x.com/in/">India</a><a href="https://x.com/uk/">UK</a>'
    assert O.india_url(S(), "https://x.com/", "https://x.com/us/", html) == "https://x.com/in/pan-india/en/"
    assert O.india_url(S(), "https://x.com/", "https://x.com/", "<p>₹1</p>") is None


def _w(w, x, y, wd, h, c=95):
    return {"w": w, "c": c, "x": x, "y": y, "wd": wd, "h": h}


def test_a_two_offer_banner_is_read_panel_by_panel(monkeypatch):
    """PN Gadgil & Sons, 24 Oct 2026: two offers side by side with a shared
    validity line - each figure keeps its own words."""
    import banner_ocr as B
    monkeypatch.setattr(B, "_upto_beside", lambda im, f: True)
    im = type("Im", (), {"width": 1920, "height": 850})()
    words = [_w("50%", 942, 430, 319, 112), _w("100", 1403, 426, 251, 170),
             *[_w(t, x, 584, 120, 23) for t, x in (("ON", 906), ("MAKING", 966), ("CHARGES", 1104))],
             *[_w(t, x, 619, 120, 22) for t, x in (("OF", 911), ("GOLD", 964), ("JEWELLERY", 1063))],
             *[_w(t, x, 595, 110, 18) for t, x in (("ON", 1360), ("MAKING", 1410), ("CHARGES", 1522), ("OF", 1655), ("CERTIFIED", 1699))],
             *[_w(t, x, 623, 120, 18) for t, x in (("NATURAL", 1387), ("DIAMOND", 1517), ("JEWELLERY", 1654))],
             *[_w(t, x, 701, 60, 22) for t, x in (("Offer", 1077), ("Valid", 1160), ("Till", 1242), ("15", 1291), ("Nov", 1330), ("2026", 1395))]]
    p = B._panels(im, words)
    assert p[0].startswith("Up to 50% ON MAKING CHARGES OF GOLD JEWELLERY")
    assert "NATURAL DIAMOND JEWELLERY" in p[1] and "GOLD" not in p[1]
    assert all("15 Nov 2026" in x for x in p[:2])
    got = O.summarise(O.extract_offers("\n".join(p), "u", image="i"))
    pct = sorted(o["pct_max"] for o in got if o["kind"] == "making_off")
    assert pct == [50.0, 100.0]


def test_figures_inside_a_buy_two_deal_stay_in_the_deal():
    txt = "BUY 1 DIAMOND JEWELLERY\nGET YOUR 2ND AT\n100% OFF 15% OFF\nON DIAMOND VALUE"
    got = O.extract_offers(txt, "u", image="i")
    assert [o["kind"] for o in got] == ["combo"]
