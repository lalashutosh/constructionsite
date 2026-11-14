"""Stress sheets (cache/stress/, skipped when absent): the solved scale must match the hand-derived truth."""
import hashlib
import json
import pathlib

import pytest

from engine.scale import checks as C
from engine.scale import sheet_scale as SS

ST = pathlib.Path(__file__).resolve().parents[1] / "cache" / "stress"
TRUTH = ST / "truth.json"
pytestmark = pytest.mark.skipif(not TRUTH.exists(), reason="stress set missing")


def _state(name):
    f = ST / name
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    return SS.sheet_state(str(f), sha), str(f), sha


def _truth(name):
    return json.loads(TRUTH.read_text())[name]["px_per_m"]


@pytest.mark.parametrize("name,tol", [("usace_p13_150dpi.png", 0.03), ("usace_p14_150dpi.png", 0.03),
                                      ("usace_p13.pdf", 0.03), ("usace_p14.pdf", 0.03), ("stoa3.png", 0.08)])
def test_scale_matches_truth(name, tol):
    st, _, _ = _state(name)
    w = st["cons"]["winner"]
    assert w is not None
    assert w["ppm"] == pytest.approx(_truth(name), rel=tol)


@pytest.mark.parametrize("name", ["usace_p13_150dpi.png", "usace_p14_150dpi.png", "usace_p13.pdf", "usace_p14.pdf"])
def test_big_sheets_auto_confident(name):
    st, f, sha = _state(name)
    it = C.get_checks(f, sha, name)["items"][0]
    assert it["status"] == "auto" and it["confidence"] >= 0.8 and it["question"] is None


@pytest.mark.parametrize("name", ["usace_p1_150dpi.png", "usace_p33_150dpi.png"])
def test_no_scale_sheets_ask(name):
    st, f, sha = _state(name)
    assert st["cons"]["winner"] is None
    it = C.get_checks(f, sha, name)["items"][0]
    assert it["status"] == "open" and it["question"] and it["value"]["px_per_m"] is None


def test_thumbnail_asks_instead_of_guessing():
    st, f, sha = _state("stoa3.png")
    it = C.get_checks(f, sha, "stoa3.png")["items"][0]
    assert it["status"] == "open" and it["question"].startswith("Is ") and "m)?" in it["question"]


def test_unreadable_thumbnail_is_not_confident():
    st, f, sha = _state("stoa2.png")
    assert C.get_checks(f, sha, "stoa2.png")["items"][0]["status"] != "auto"


def test_false_610_is_gone():
    """printed_dims used to give 610.7 px/m 'specified' on the p13 render (truth 246.06)."""
    from contracts.proof import SheetFacts
    from engine.scale import printed_dims
    f = ST / "usace_p13_150dpi.png"
    facts = SheetFacts(provenance={"file": str(f)}, width_px=5100, height_px=3300)
    assert printed_dims.anchor(facts, str(f), "x") is None


def test_yes_and_no_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(SS, "CHECKS", tmp_path)
    monkeypatch.setattr(C, "invalidate", lambda sha: None)
    st, f, sha = _state("stoa3.png")
    first = C.get_checks(f, sha, "p")["items"][0]
    out = C.answer(f, sha, "p", first["id"], "yes")["items"][0]
    assert out["status"] == "confirmed" and out["confidence"] >= 0.95 and out["value"]["tag"] == "chosen"
    (tmp_path / f"{sha}.json").unlink()
    after_no = C.answer(f, sha, "p", first["id"], "no")["items"][0]
    assert after_no["id"] != first["id"] or after_no["status"] == "open"
    anchors, _ = SS.anchors_for(f, sha)
    assert all(first["id"] not in (a.note or "") for a in anchors)
