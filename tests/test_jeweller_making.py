import jeweller_making as jm

MC = {"updated": "2026-10-28", "brands": [
    {"brand": "PN Gadgil", "categories": [{"category": "Ring", "items": 57, "making_pct_median": 16.4, "confidence": "high"}]},
    {"brand": "Malabar Gold", "categories": [{"category": "Earrings", "items": 9, "making_pct_median": 16.9,
                                               "confidence": "jeweller", "source": "jeweller"}]}]}


def test_a_jewellers_own_figure_fills_gaps_and_measured_figures_win():
    items = [{"brand": "PN Gadgil", "category": "Ring", "pct": 9.0, "date": "2026-10-28"},       # measured: ignored
             {"brand": "PN Gadgil", "category": "Chain", "pct": 12.0, "date": "2026-10-28"},     # gap: added
             {"brand": "Ranka Jewellers", "category": "Bangle", "pct": 14.5, "date": "2026-10-28"}]  # new brand
    out = jm.merge(MC, items)
    by = {b["brand"]: {c["category"]: c for c in b["categories"]} for b in out["brands"]}
    assert by["PN Gadgil"]["Ring"]["making_pct_median"] == 16.4 and by["PN Gadgil"]["Ring"]["confidence"] == "high"
    assert by["PN Gadgil"]["Chain"]["making_pct_median"] == 12.0 and by["PN Gadgil"]["Chain"]["source"] == "jeweller"
    assert by["Ranka Jewellers"]["Bangle"]["confidence"] == "jeweller"
    assert "Malabar Gold" not in by                     # a figure no longer sent is dropped


def test_the_form_and_the_label_are_on_the_site():
    src = open("generate_site.py", encoding="utf-8").read()
    assert "submit_making_charges" in src and 'id="making"' in src
    assert "Supplied by the jeweller" in src
    sql = open("sql/jeweller_making.sql", encoding="utf-8").read()
    assert "pct between 3 and 60" in sql and "security definer" in sql and "revoke all" in sql
