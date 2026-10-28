import collect_charges as cc
import assistant_kb
import tanishq_charges as tq

# trimmed from Tanishq's own product data (the "Price Breakup" response)
PLAIN = ('{"product": {"karatage": "22", "metal": "Gold", "diamondWeight": 0, "stoneWeight": 0, '
         '"pricingGroupType": "PLAINGOLD", "customDataFeed": {"priceInfo": {"dtt": "F2", "dtp": "15", "vpg": "", '
         '"dttText": "<DISCOUNT_PERCENTAGE>% off on making charges"}}, '
         '"priceInfo": {"MGR": "14065", "GDV": "48735.23", "WTV": "10965.43", "AF1": "0", "F2": "0", "UTP": "61491.67", '
         '"TXV": "1791.02", "WTP": "22.5"}}}')


def test_plain_22k_gives_making_pct_and_its_offer():
    r = tq.parse(PLAIN)
    assert r["pct"] == 22.5 and r["offer"] == {"pct": 15.0}


def test_other_karats_stones_and_missing_breakups_are_skipped():
    assert tq.parse(PLAIN.replace('"karatage": "22"', '"karatage": "14"')) is None
    assert tq.parse(PLAIN.replace('"stoneWeight": 0', '"stoneWeight": 0.41')) is None
    assert tq.parse(PLAIN.replace("PLAINGOLD", "GOLDSTUDDED")) is None
    assert tq.parse(PLAIN.replace('"GDV": "48735.23"', '"GDV": ""')) is None
    assert tq.parse("<html>Access Blocked</html>") is None
    assert tq.parse(PLAIN.replace('"UTP": "61491.67"', '"UTP": "80000"')) is None    # parts must add up


def test_a_master_product_points_to_a_variant_that_has_the_price():
    master = ('{"productType": "master", "karatage": "22", "url": '
              '"https://www.tanishq.co.in/on/demandware.store/Sites-Tanishq-Site/en_IN/Product-Variation?'
              'dwvar_51t815fbraa00_grossWeight=4.2&amp;pid=51t815fbraa00&amp;quantity=1"}')
    assert tq.variant_url(master).endswith("grossWeight=4.2&pid=51t815fbraa00&quantity=1")


def test_per_gram_offer_and_html_escaped_data():
    t = PLAIN.replace('"dtp": "15", "vpg": ""', '"dtp": "0", "vpg": "301"').replace('"', "&quot;")
    assert tq.parse(t)["offer"] == {"per_gram": 301.0}


def test_offer_summary_and_how_sona_reads_it():
    off = {"Ring": {"seen": 4, "pct": [15, 15, 20], "per_gram": []}}
    s = tq.offer_summary(off)
    assert s == {"making_pct_off": 15, "max_pct_off": 20, "share": 0.75}
    assert assistant_kb._product_offer(s) == (0.0, 20.0)          # not on every piece: "up to"
    assert assistant_kb._product_offer(dict(s, share=1.0)) == (15.0, 20.0)


def test_only_tanishq_spends_proxy_credits(monkeypatch):
    calls = []

    class S:
        def get(self, u, **k):
            calls.append(u)
            raise OSError
    monkeypatch.setenv("SCRAPERAPI_KEY", "x")
    cc.fetch(S(), "https://www.waman-hari-pethe.com/x")
    assert len(calls) == 1                                  # direct only
    cc.fetch(S(), "https://www.tanishq.co.in/x")
    assert len(calls) == 3 and "scraperapi" in calls[-1]


def test_offers_read_tanishq_through_the_proxies_and_others_stay_blocked(monkeypatch):
    import offers
    page = ("<html><body><h2>Diwali offer</h2><p>Flat 20% off on making charges on gold jewellery. "
            "Valid till 5 November.</p></body></html>") * 3
    seen = []
    monkeypatch.setattr(cc, "fetch", lambda sess, u, **k: (seen.append(u) or page, "zenrows"))
    monkeypatch.setattr(offers, "read_banners", lambda *a, **k: [])
    rec = offers.read_via_proxy(None, {"pages": [], "offers": [], "status": "ok"}, "https://www.tanishq.co.in/")
    assert rec["via"] == "proxy" and any(o["kind"] == "making_off" for o in rec["offers"])
    assert len(seen) <= offers.PROXY_PAGES
    other = offers.read_via_proxy(None, {"pages": [], "offers": [], "status": "ok"}, "https://www.joyalukkas.in/")
    assert other["status"].startswith("not readable")
