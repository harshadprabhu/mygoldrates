import price_making as pm

# trimmed from Indriya's own product data (product.pdp.json)
RING = {"formattedPrice": "₹54,016.00", "masterAttrMap": {"master_group": "Gold", "purity": "22 karat"},
        "productAccordions": [{"label": "Metals", "tableValue": [
            {"key": "Gold Weight", "value": "3.488000 g"}, {"key": "Purity (Karatage)", "value": "22K"}]}]}


def test_making_is_price_less_gold_at_the_jewellers_own_rate():
    # 3.488 g x 13195 = 46,024; 54,016 - 46,024 = 7,992 -> 17.36%
    assert pm.Indriya.parse(RING, 13195) == 17.36
    assert pm.making_pct(100, 1, 120) is None          # below the gold value: not plausible
    assert pm.making_pct(200, 1, 100) is None          # 100%: not plausible


def test_stones_other_karats_and_other_metals_are_skipped():
    stones = dict(RING, productAccordions=RING["productAccordions"] + [
        {"label": "Stones", "tableValue": [{"key": "Gemstone Weight", "value": "0.27"}]}])
    assert pm.Indriya.parse(stones, 13195) is None
    k18 = {**RING, "productAccordions": [{"tableValue": [{"key": "Gold Weight", "value": "3 g"},
                                                         {"key": "Purity (Karatage)", "value": "18K"}]}]}
    assert pm.Indriya.parse(k18, 13195) is None
    assert pm.Indriya.parse(dict(RING, masterAttrMap={"master_group": "Silver"}), 13195) is None


def test_the_site_labels_figures_worked_out_from_the_price():
    src = open("generate_site.py", encoding="utf-8").read()
    assert "Worked out from the price" in src and '"src": c.get("source", "")' in src


TM = ('<div>Price Breakup</div><div>22KT GOLD</div><span>₹293,721.00</span> + <div>MC</div><span>₹49,933.00</span>'
      ' + <div>HMC</div><span>₹150.00</span> + <div>GST(3.00%)</div><span>₹10,314.00</span>'
      '<table><tr><th>Metal Purity</th><td>22K</td></tr><tr><th>Making Charge</th><td>17</td></tr></table>')


def test_thangamayil_reads_its_own_breakup():
    assert pm.Thangamayil.parse(TM) == 17.0
    assert pm.Thangamayil.parse(TM.replace("<div>HMC</div>", "<div>STONE</div>")) is None
    assert pm.Thangamayil.parse(TM.replace(">22K<", ">18K<")) is None
    assert pm.Thangamayil.source is None and pm.Indriya.source == "price"
