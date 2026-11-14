"""Skeptic tests on a synthetic plan (no dataset needed)."""
import cv2
import numpy as np
import pytest

from engine import registry
from engine.registry import Ctx
from engine.skeptic import calibrate
from engine.skeptic.voters import doors_arc, windows_lines
from engine.triage import rules


def _plan(path, door=True, window=True):
    im = np.full((700, 700, 3), 255, np.uint8)
    t = 12
    cv2.rectangle(im, (100, 100), (600, 600), (0, 0, 0), t)
    cv2.line(im, (350, 100), (350, 600), (0, 0, 0), 8)
    if window:  # gap in top wall with two thin parallel lines
        cv2.rectangle(im, (180, 92), (260, 110), (255, 255, 255), -1)
        cv2.line(im, (180, 98), (260, 98), (0, 0, 0), 1)
        cv2.line(im, (180, 104), (260, 104), (0, 0, 0), 1)
    if door:  # hinge on the vertical partition, leaf along it, quarter arc
        cv2.rectangle(im, (344, 300), (356, 340), (255, 255, 255), -1)
        cv2.line(im, (350, 300), (350, 335), (0, 0, 0), 2)
        cv2.ellipse(im, (350, 300), (35, 35), 0, 0, 90, (0, 0, 0), 2)
    cv2.imwrite(str(path), im)
    return str(path)


def test_doors_and_windows_on_synthetic(tmp_path):
    p = _plan(tmp_path / "plan.png")
    n_d, arcs, _ = doors_arc.count(p)
    assert n_d >= 1
    n_w, ws, _ = windows_lines.count(p)
    assert n_w is None or n_w >= 1


def test_voter_result_contract(tmp_path):
    p = _plan(tmp_path / "plan.png")
    vr = doors_arc.run(Ctx(path="x.png", abs_path=p, question="", intent="doors"))
    assert vr.voter.name == "doors_arc" and vr.voter.note
    assert len(vr.evidence) == len(vr.voter.element_ids) == vr.voter.value
    for el in vr.evidence:
        assert all(0 <= x <= 700 and 0 <= y <= 700 for x, y in el.polygon)


def test_plugin_registers_and_abstains_off_intent(tmp_path):
    registry.reset()
    registry.autodiscover(("engine.skeptic.plugin",))
    names = [n for n, _ in registry.voters_for("count")]
    assert "doors_arc" in names
    fn = dict(registry.voters_for("count"))["doors_arc"]
    p = _plan(tmp_path / "plan.png")
    assert fn(Ctx(path="x.png", abs_path=p, question="", intent="toilets")) is None     # not enabled for this intent
    assert fn(Ctx(path="x.pdf", abs_path=p + ".pdf", question="", intent="doors")) is None  # pdf goes to vector route
    registry.reset()


def test_triage_refuses_thumbnail(tmp_path):
    im = np.full((90, 125, 3), 255, np.uint8)
    cv2.rectangle(im, (10, 10), (100, 70), (0, 0, 0), 3)
    p = str(tmp_path / "thumb.png")
    cv2.imwrite(p, im)
    r = rules.classify(p, use_ocr=False)
    assert r["refuse"] and "150 px" in r["refuse"] and not r["legible"]


def test_triage_does_not_refuse_synthetic_plan(tmp_path):
    r = rules.classify(_plan(tmp_path / "plan.png"), use_ocr=False)
    assert r["refuse"] is None and r["sheet_type"] == "floor_plan"


def test_calibrator_featurize_defaulted_counts_zero_voters():
    po = {"intent": "doors", "voters": [{"name": "prior", "value": 5, "runs": []}], "evidence": []}
    f = calibrate.featurize(po, 500, "floor_plan")
    assert len(f) == len(calibrate.FEATURES) and f[-1] == 1.0   # a defaulted voter is flagged, never counted as evidence
    po2 = {"intent": "doors", "voters": [{"name": "a", "value": 3, "runs": [3, 4]}, {"name": "b", "value": 5}], "evidence": []}
    f2 = calibrate.featurize(po2, 500)
    assert f2[1] == 2.0 and f2[2] == 1.0


def test_reliability_bins_cover_all_rows():
    p = np.linspace(0, 1, 101)
    y = (p > 0.5).astype(int)
    assert sum(b["n"] for b in calibrate.reliability(p, y)) == 101
