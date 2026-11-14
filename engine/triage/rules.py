"""Rule-based sheet triage. Thresholds were set by hand on 361 labelled images (see docs/handoff/skeptic.md);
the numbers are resubstitution estimates and therefore optimistic.

Order: cheap legibility rules first, then shape rules; OCR (slow) runs only when a shape rule already fired
(plan-label words veto a refusal).
"""
from __future__ import annotations

from engine.triage import features
from engine.triage.features_extra import compute_extra

MIN_DIM = 150
BLUR_MIN = 0.08

REASONS = {
    "too_small": "image is {w} px wide and {h} px high: below the readable minimum of 150 px",
    "blurry": "image is too blurry to read walls and symbols",
    "photo": "this looks like a photograph, not a drawing: floor-plan questions do not apply",
    "elevation": "this looks like an elevation or section (mirror-symmetric facade, no enclosed rooms, no room labels): "
                 "floor-plan questions do not apply",
    "not_a_plan": "no right-angle wall structure and no room labels were found: this does not look like a floor plan",
}


def _windows_proxy(path: str) -> int:
    try:
        from engine.skeptic.voters import windows_lines
        n, _, _ = windows_lines.count(path)
        return -1 if n is None else int(n)
    except Exception:  # noqa: BLE001
        return -1


def classify(path: str, use_ocr: bool = True) -> dict:
    """Returns {sheet_type, legible, refuse (reason or None), rule, feats}."""
    f = features.compute(path, use_ocr=False)
    if not f.get("ok"):
        return dict(sheet_type="not_a_plan", legible=False, refuse="file could not be read as an image", rule="unreadable",
                    feats=f)
    out = dict(sheet_type="floor_plan", legible=True, refuse=None, rule=None, feats=f)
    if f["min_dim"] < MIN_DIM:
        out.update(sheet_type="not_a_plan", legible=False, rule="too_small",
                   refuse=REASONS["too_small"].format(w=f["w"], h=f["h"]))
        return out
    if f["blur"] < BLUR_MIN:
        out.update(legible=False, rule="blurry", refuse=REASONS["blurry"])
        return out
    if f["sat"] > 0.05 and f["bg_frac"] < 0.6:
        out.update(sheet_type="not_a_plan", rule="photo", refuse=REASONS["photo"])
        return out
    f.update(compute_extra(path))
    f["wins"] = _windows_proxy(path)
    cand = None
    if f["sym"] > 0.5 and f["n_mid"] <= 3 and f["wins"] <= 0:
        cand = ("elevation", "elevation")
    elif f["ortho"] < 0.8 and f["n_mid"] <= 3:
        cand = ("not_a_plan", "not_a_plan")
    if cand is not None:
        if use_ocr:
            t = features.ocr_text(features.read_gray(path))
            f["kw_plan"] = len(features.KW_PLAN.findall(t))
        else:
            f["kw_plan"] = 0
        if f["kw_plan"] == 0:
            out.update(sheet_type=cand[0], rule=cand[1], refuse=REASONS[cand[1]])
    return out
