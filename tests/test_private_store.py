import json
import os
import subprocess

import private_store as ps

MC = {"updated": "2026-10-28T19:00:00+05:30", "note": "x", "brands": [
    {"brand": "Tanishq", "offer": {"making_pct_off": 10.0, "share": 0.26},
     "categories": [{"category": "Ring", "items": 5, "making_pct_median": 19.5, "making_pct_min": 18.0,
                     "making_pct_max": 22.5, "confidence": "low", "rejected_outliers": 1,
                     "examples": [{"url": "https://www.tanishq.co.in/product/x.html", "pct": 19.5}]}]},
    {"brand": "Indriya", "categories": [{"category": "Bangle", "items": 25, "making_pct_median": 22.9,
                                         "confidence": "high", "source": "price"}]}]}


def test_making_charges_survive_the_trip_through_the_table():
    rows = ps.making_rows(MC)
    assert {r["brand"] for r in rows} == {"Tanishq", "Indriya"} and all(r["run_at"] == MC["updated"] for r in rows)
    back = ps.making_from_rows(rows, "x")
    by = {b["brand"]: b for b in back["brands"]}
    assert by["Tanishq"]["offer"] == MC["brands"][0]["offer"]
    assert by["Tanishq"]["categories"][0] == MC["brands"][0]["categories"][0]
    assert by["Indriya"]["categories"][0]["source"] == "price"


def test_collected_data_is_not_in_git_or_on_the_site():
    assert "private/" in open(".gitignore").read()
    assert ps.MC.startswith("private/") and ps.OFFERS.startswith("private/")
    for wf in (".github/workflows/charges.yml", ".github/workflows/offers.yml"):
        y = open(wf).read()
        assert "git add docs/making-charges.json" not in y and "git add docs/offers.json" not in y
        assert "private_store.py push-" in y
    tracked = subprocess.run(["git", "ls-files", "private"], capture_output=True, text=True).stdout
    assert tracked == ""


def test_without_supabase_nothing_is_pushed(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setattr(ps, "_sb", None)
    assert ps.push_making(MC) == 0 and ps.push_offers({"brands": [{"slug": "a"}]}) == 0
