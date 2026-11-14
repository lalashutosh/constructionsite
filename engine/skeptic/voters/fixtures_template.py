"""fixtures_template: multi-scale, 4-rotation normalised cross-correlation for toilet and sink symbols.

Templates are cropped from ONE DEV image (cubicasa5k/high_quality_architectural-672.png), see
engine/skeptic/templates/ and docs/handoff/skeptic.md. No shower/bath template: no reliable symbol, so this
voter is NOT registered for showers_baths.
"""
from __future__ import annotations

import functools
import pathlib

import cv2
import numpy as np

from engine.skeptic.prep import prep

NAME = "fixtures_template"
NOTE = ("template NCC from a single crop per fixture; weak on plans with different symbol styles and on "
        "rotated/skewed scans. Only registered for toilets and sinks.")
TPL_DIR = pathlib.Path(__file__).resolve().parents[1] / "templates"
CFG = {"toilets": dict(files=["toilet_a"], thr=0.62), "sinks": dict(files=["sink_a"], thr=0.66)}
SCALES = (0.5, 0.65, 0.8, 1.0, 1.25, 1.55)


@functools.lru_cache(maxsize=8)
def _tpl(name: str):
    t = cv2.imread(str(TPL_DIR / f"{name}.png"), 0)
    return t


def detect(path: str, intent: str):
    p = prep(path)
    if p is None or intent not in CFG:
        return None, []
    cfg = CFG[intent]
    g = p.gray
    # plan scale proxy: processing-px relative to the 914 px reference plan the templates came from
    ref = 914.0 / 1000.0
    hits = []
    for name in cfg["files"]:
        t0 = _tpl(name)
        for s in SCALES:
            t = cv2.resize(t0, None, fx=s * ref, fy=s * ref, interpolation=cv2.INTER_AREA)
            if min(t.shape) < 8 or t.shape[0] >= g.shape[0] or t.shape[1] >= g.shape[1]:
                continue
            for k in range(4):
                tt = np.rot90(t, k).copy()
                res = cv2.matchTemplate(g, tt, cv2.TM_CCOEFF_NORMED)
                ys, xs = np.nonzero(res >= cfg["thr"])
                for y, x in zip(ys, xs):
                    hits.append((float(res[y, x]), int(x), int(y), tt.shape[1], tt.shape[0]))
    hits.sort(reverse=True)
    keep = []
    for sc, x, y, w, h in hits:
        cx, cy = x + w / 2, y + h / 2
        if all(abs(cx - (kx + kw / 2)) > 0.6 * max(w, kw) or abs(cy - (ky + kh / 2)) > 0.6 * max(h, kh)
               for _, kx, ky, kw, kh in keep):
            keep.append((sc, x, y, w, h))
    return len(keep), keep


def count_for(path: str, intent: str):
    if intent not in CFG:
        return None
    n, _ = detect(path, intent)
    return n


def run(ctx):
    from contracts.proof import Element, Voter
    from engine.registry import VoterResult

    if ctx.intent not in CFG:
        return None
    p = prep(ctx.abs_path)
    n, keep = detect(ctx.abs_path, ctx.intent)
    if n is None:
        return None
    ev, ids = [], []
    sub = {"toilets": "toilet", "sinks": "sink"}[ctx.intent]
    for i, (sc, x, y, w, h) in enumerate(keep):
        eid = f"fix_{sub}_{i}"
        ids.append(eid)
        ev.append(Element(id=eid, kind="fixture", subtype=sub,
                          polygon=p.to_orig([(x, y), (x + w, y), (x + w, y + h), (x, y + h)]),
                          conf=float(min(1.0, max(0.0, sc))), attrs={"ncc": sc, "method": "template"}))
    return VoterResult(Voter(name=NAME, value=n, element_ids=ids, runs=[n], note=NOTE), ev)
