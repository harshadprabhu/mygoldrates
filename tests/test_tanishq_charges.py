import collect_charges as cc
import assistant_kb
import tanishq_charges as tq

# trimmed from Tanishq's own product data (the "Price Breakup" response)
PLAIN = ('{"product": {"karatage": "22", "metal": "Gold", "diamondWeight": 0, "stoneWeight": 0, '
         '"pricingGroupType": "PLAINGOLD", "customDataFeed": {"priceInfo": {"dtt": "F2", "dtp": "15", "vpg": "", '
         '"dttText": "<DISCOUNT_PERCENTAGE>% off on making charges"}}, '
         '"priceInfo": {"MGR": "3287.08", "GDV": "14609.24", "UTP": "17896.32"}}}')


def test_plain_22k_gives_making_pct_and_its_offer():
    r = tq.parse(PLAIN)
    assert r["pct"] == 22.5 and r["offer"] == {"pct": 15.0}


def test_other_karats_stones_and_missing_breakups_are_skipped():
    assert tq.parse(PLAIN.replace('"karatage": "22"', '"karatage": "14"')) is None
    assert tq.parse(PLAIN.replace('"stoneWeight": 0', '"stoneWeight": 0.41')) is None
    assert tq.parse(PLAIN.replace("PLAINGOLD", "GOLDSTUDDED")) is None
    assert tq.parse(PLAIN.replace('"GDV": "14609.24"', '"GDV": ""')) is None
    assert tq.parse("<html>Access Blocked</html>") is None


def test_per_gram_offer_and_html_escaped_data():
    t = PLAIN.replace('"dtp": "15", "vpg": ""', '"dtp": "", "vpg": "301"').replace('"', "&quot;")
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
