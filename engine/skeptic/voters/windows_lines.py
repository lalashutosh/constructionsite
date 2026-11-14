"""windows_lines: windows as thin parallel line groups bridging a gap in a thick wall.

Pipeline: thick-wall mask (opening by wall thickness) -> bridge collinear wall pieces (closing along x / y) ->
the bridged-but-not-wall regions are wall gaps -> a gap whose cross-section holds >= 2 continuous thin lines
(parallel line pair/triple) is a window; a gap with no lines is an open doorway or door and is NOT counted.
"""
from __future__ import annotations

import cv2
import numpy as np

from engine.skeptic.prep import Prep, prep

NAME = "windows_lines"
NOTE = ("geometry only. Weak for plans drawn with a coloured/solid window symbol or without thick walls; "
        "windows in thin-walled hand drawings are missed. Merges adjacent windows separated by <1 wall thickness.")
CFG = dict(min_wall_px=7, min_len=1.2, max_len=14.0, min_lines=2, cover=0.75)


def _gaps_axis(p: Prep, horizontal: bool):
    t = max(3, int(round(p.thick)))
    walls = p.walls if p.walls.any() else p.dark
    span = max(p.gray.shape)
    Lg = int(max(6 * t, 0.12 * span))
    ker = (1, Lg) if horizontal else (Lg, 1)
    closed = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, np.ones(ker, np.uint8))
    gaps = cv2.bitwise_and(closed, cv2.bitwise_not(cv2.dilate(walls, np.ones((3, 3), np.uint8))))
    return gaps, t


def find_windows(p: Prep):
    out = []
    ink = p.ink
    for horizontal in (True, False):
        gaps, t = _gaps_axis(p, horizontal)
        n, lab, st, _ = cv2.connectedComponentsWithStats(gaps, connectivity=4)
        for i in range(1, n):
            x, y, w, h, a = st[i]
            length, thick = (w, h) if horizontal else (h, w)
            if length < CFG["min_len"] * t or length > CFG["max_len"] * t:
                continue
            if thick < 0.5 * t or thick > 2.2 * t:
                continue
            sub = ink[y:y + h, x:x + w] > 0
            msk = lab[y:y + h, x:x + w] == i
            prof_axis = 1 if horizontal else 0           # sum along the wall direction
            cov = (sub & msk).sum(axis=prof_axis) / np.maximum(msk.sum(axis=prof_axis), 1)
            line = cov >= CFG["cover"]
            # count separated line runs (adjacent rows form one thick line)
            runs = int(((np.diff(np.r_[0, line.astype(int)]) == 1)).sum())
            if runs >= CFG["min_lines"]:
                out.append({"box": (int(x), int(y), int(w), int(h)), "lines": runs, "horizontal": horizontal})
    return out


def count(path: str):
    p = prep(path)
    if p is None:
        return None, [], None
    if p.thick < CFG["min_wall_px"] or p.walls.mean() / 255.0 < 0.004:
        return None, [], p          # abstain: no readable thick walls (hand drawing / thin CAD lines)
    ws = find_windows(p)
    return len(ws), ws, p


def run(ctx):
    from contracts.proof import Element, Voter
    from engine.registry import VoterResult

    n, ws, p = count(ctx.abs_path)
    if n is None:
        return None  # abstain
    ev, ids = [], []
    for i, w in enumerate(ws):
        x, y, bw, bh = w["box"]
        eid = f"win_lines_{i}"
        ids.append(eid)
        ev.append(Element(id=eid, kind="window", polygon=p.to_orig([(x, y), (x + bw, y), (x + bw, y + bh), (x, y + bh)]),
                          conf=min(1.0, 0.5 + 0.2 * w["lines"]), attrs={"lines": w["lines"], "method": "wall_gap_lines"}))
    return VoterResult(Voter(name=NAME, value=n, element_ids=ids, runs=[n], note=NOTE), ev)
