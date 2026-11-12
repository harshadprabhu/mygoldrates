"""Pinky & Gappu ad maker (owner, 12 Nov 2026)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ad_maker as A  # noqa: E402


def test_ad_spec_is_complete():
    spec = json.load(open("brand/ads/goldrate-confusion.json", encoding="utf-8"))
    assert len(spec["scenes"]) == 3
    for sc in spec["scenes"]:
        assert 3 <= float(sc["duration"].rstrip("s")) <= 15          # Omni's limits
        assert "Gappu" in sc["prompt"] or "Pinky" in sc["prompt"]
    assert "plain dark screen" in spec["scenes"][0]["prompt"]      # the AI never draws the site
    assert "no logos" in spec["style"] and "No subtitles" in spec["style"]
    assert os.path.exists(spec["end_card"]["image"]) and os.path.exists(spec["logo"])


def test_reference_images_are_at_most_three_per_character(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "MASCOTS", str(tmp_path))
    for n in ("pinky", "gappu"):
        for i, t in enumerate(("front", "side", "face", "extra"), 1):
            (tmp_path / f"{n}-{i}-{t}.png").write_bytes(b"x")
    (tmp_path / "pinky-gappu.png").write_bytes(b"x")              # the couple picture is not a reference
    r = A.refs()
    assert len(r) == 6 and all("pinky-gappu" not in p for p in r)


def test_outputs_reads_the_interaction_response():
    import base64
    d = {"steps": [{"type": "model_output", "content": [
        {"type": "text", "text": "ok"}, {"type": "video", "mime_type": "video/mp4",
                                         "data": base64.b64encode(b"MP4").decode()}]}]}
    assert A.outputs(d, "video") == [(b"MP4", "video/mp4")]


def test_key_comes_only_from_the_environment():
    src = open("ad_maker.py", encoding="utf-8").read()
    assert 'os.environ.get("GEMINI_API_KEY"' in src and "print(_key" not in src
    wf = open(".github/workflows/ad-maker.yml", encoding="utf-8").read()
    assert "secrets.GEMINI_API_KEY" in wf
