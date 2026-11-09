"""Manubhai making charges from its product prices (owner, 9 Nov 2026)."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import manubhai_making as mm  # noqa: E402

TICKER = ('<a href="/gold-rate/">Gold Rate as on 08/11/2026 | 22KT - &#8377; 13,027 Per Gram</a>'
          '<a href="/gold-rate/">Gold Rate as on 08/11/2026 | 18KT - &#8377; 10,654 Per Gram</a>')


def page(pur="22KT", dia="-", net="15.9g", gross="15.9g", price="2,29,837"):
    cell = ('<td><span class="woocommerce-Price-amount amount"><bdi><span class="woocommerce-Price-currencySymbol">'
            f'&#8377;</span>{price}</bdi></span></td>') if price else "<td>-</td>"
    return (TICKER + '<h3>Price Breakup</h3><table class="price-breakup-table"><thead><tr><th>Purity</th>'
            '<th>Diamond Wt</th><th>Net Wt (g)</th><th>Gross Wt (g)</th><th>Price</th></tr></thead><tbody><tr>'
            f"<td>{pur}</td><td>{dia}</td><td>{net}</td><td>{gross}</td>{cell}</tr></tbody></table>"
            # a related product further down must not be read as this one's price
            '<li><span>&#8377;</span>7,36,546</li>')


def parse(cases):
    js = ("import('./cf-worker-jd/worker.js').then(m => console.log(JSON.stringify(%s.map(([h, c]) => m.mbParse(h, c)))))"
          % json.dumps(cases))
    out = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_worker_reads_the_pieces_own_breakup():
    r = parse([[page(), "Chain"]])[0]
    # 229837 / 1.03 / (15.9 x 13027) - 1 = 7.7%
    assert r == {"pur": "22", "net": 15.9, "price": 229837, "rate": 13027, "pct": 7.7}


def test_worker_uses_the_rate_for_the_pieces_purity():
    r = parse([[page(pur="18KT", net="4.32g", gross="4.32g", price="49,540"), "Earrings"]])[0]
    assert r["rate"] == 10654


def test_worker_skips_what_is_not_a_plain_priced_gold_piece():
    got = parse([[page(price=None), "Chain"],                          # made to order
                 [page(dia="0.25ct"), "Ring"],                          # diamonds
                 [page(net="10g", gross="10.6g"), "Necklace"],          # stones
                 ["<p>nothing here</p>", "Ring"]])
    assert [g.get("skip") for g in got] == ["no price", "diamonds", "stones", "no breakup"]


def test_mangalsutra_beads_are_allowed():
    r = parse([[page(net="13.03g", gross="13.78g", price="1,99,748"), "Mangalsutra"]])[0]
    assert "pct" in r


def test_rows_need_five_pieces_and_drop_implausible_readings():
    rd = {f"https://manubhai.in/product/r{i}/": {"cat": "Ring", "pct": p}
          for i, p in enumerate([14.3, 16.4, 16.4, 19.3, 25.3, 85.0, -3.0])}
    rd.update({f"https://manubhai.in/product/c{i}/": {"cat": "Chain", "pct": 15.0} for i in range(4)})
    rows = mm.rows_from_readings(rd)
    assert set(rows) == {"Ring"}                     # Chain has only 4
    r = rows["Ring"]
    assert r["items"] == 5 and r["making_pct_median"] == 16.4
    assert r["making_pct_max"] == 25.3 and r["source"] == "price"
    assert r["examples"][0]["url"].startswith("https://manubhai.in/")    # matches by site too


def test_merge_never_replaces_a_charge_measured_from_a_breakup():
    mc = {"brands": [{"brand": mm.BRAND, "categories": [{"category": "Ring", "making_pct_median": 12, "source": "breakup"}]},
                     {"brand": "Tanishq", "categories": []}]}
    rows = {"Ring": {"category": "Ring", "making_pct_median": 16.4, "source": "price"},
            "Chain": {"category": "Chain", "making_pct_median": 15.4, "source": "price"}}
    out = mm.merge(mc, rows)
    b = next(x for x in out["brands"] if x["brand"] == mm.BRAND)
    assert {c["category"]: c["making_pct_median"] for c in b["categories"]} == {"Chain": 15.4, "Ring": 12}
    assert any(x["brand"] == "Tanishq" for x in out["brands"])


def test_worker_keeps_within_its_request_budget():
    src = open("cf-worker-jd/worker.js", encoding="utf-8").read()
    assert "MB_PER_RUN = 20" in src and "_fields=permalink" in src
    assert "snapshotPages(env).then(() => mbMaking(env))" in src
