"""doors_arc: door swing arcs found by RANSAC circle fitting on thin curved ink components.

Pipeline: ink mask minus thick walls -> connected components -> RANSAC circle on component pixels ->
accept when radius is plausible for the wall thickness, the angular span is a quarter-ish arc (50-125 deg)
and a straight door leaf (dark line) joins the circle centre to one arc end. Open doorways (no arc) are
not counted, matching the answer key rule.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from engine.skeptic.prep import Prep, prep

CFG = dict(leaf=0.75, dom=0.3, cov=0.75, fill=0.75, hinge=False, gap2=4)  # tuned on 60 DEV images (devcheck)
NAME = "doors_arc"
NOTE = ("geometry only (circle fit + leaf line). Weak on hand-drawn/scanned plans and when arcs are dashed "
        "or broken by text; no wall-gap test, so a swing arc without leaf is not counted.")


def _fit3(p):
    (x1, y1), (x2, y2), (x3, y3) = p
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-6:
        return None
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    return ux, uy, math.hypot(x1 - ux, y1 - uy)


def _leaf_score(dark, c, e, band=1):
    n = int(max(abs(e[0] - c[0]), abs(e[1] - c[1])))
    if n < 3:
        return 0.0
    xs = np.linspace(c[0], e[0], n).round().astype(int)
    ys = np.linspace(c[1], e[1], n).round().astype(int)
    h, w = dark.shape
    hit = 0
    for dx in (-band, 0, band):
        for dy in (-band, 0, band):
            pass
    xs = np.clip(xs, 0, w - 1)
    ys = np.clip(ys, 0, h - 1)
    d = cv2.dilate(dark, np.ones((3, 3), np.uint8))
    return float((d[ys, xs] > 0).mean())


def find_arcs(p: Prep, rng_seed: int = 7):
    # lines is needed inside the loop
    ys_, xs_ = np.nonzero(p.walls)
    span_ = max(np.ptp(xs_), np.ptp(ys_)) if len(xs_) > 50 else max(p.gray.shape)
    span_ = max(span_, 0.3 * max(p.gray.shape))
    r_lo, r_hi = max(6.0, 0.022 * span_), max(14.0, 0.075 * span_)
    L = int(max(15, 1.25 * r_hi * 0.75))
    hl = cv2.morphologyEx(p.ink, cv2.MORPH_OPEN, np.ones((1, L), np.uint8))
    vl = cv2.morphologyEx(p.ink, cv2.MORPH_OPEN, np.ones((L, 1), np.uint8))
    lines = cv2.dilate(cv2.bitwise_or(hl, vl), np.ones((3, 3), np.uint8))
    thin = cv2.bitwise_and(p.ink, cv2.bitwise_not(lines))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(thin, connectivity=8)
    rng = np.random.default_rng(rng_seed)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < r_lo * 1.2 or max(w, h) < r_lo * 0.9 or max(w, h) > r_hi * 3.0:
            continue
        ys, xs = np.nonzero(lab[y:y + h, x:x + w] == i)
        pts = np.stack([xs + x, ys + y], 1).astype(np.float64)
        if len(pts) > 1500:
            pts = pts[rng.choice(len(pts), 1500, replace=False)]
        best = None
        for _ in range(120):
            s = pts[rng.choice(len(pts), 3, replace=False)]
            f = _fit3(s)
            if f is None or not (r_lo <= f[2] <= r_hi):
                continue
            d = np.abs(np.hypot(pts[:, 0] - f[0], pts[:, 1] - f[1]) - f[2])
            inl = d < 1.6
            k = int(inl.sum())
            if best is None or k > best[0]:
                best = (k, f, inl)
        if best is None:
            continue
        k, (cx, cy, r), inl = best
        if k < 0.8 * r_lo:
            continue
        ip = pts[inl]
        ang = np.degrees(np.arctan2(ip[:, 1] - cy, ip[:, 0] - cx)) % 360
        hist = np.zeros(72, bool)
        hist[(ang // 5).astype(int) % 72] = True
        # span = 360 - largest empty circular gap
        idx = np.nonzero(hist)[0]
        if len(idx) < 6:
            continue
        gaps = np.diff(np.r_[idx, idx[0] + 72])
        span = (72 - gaps.max() + 1) * 5
        if not (45 <= span <= 130):
            continue
        # arc length must be mostly present (not a sparse set of points)
        if hist.sum() * 5 < CFG['cov'] * span:
            continue
        gs = np.sort(gaps)[::-1]
        if len(gs) > 1 and gs[1] > CFG['gap2']:      # a second hole in the angular coverage: not one clean arc
            continue
        full = int(len(pts))
        if k < CFG['dom'] * full:                # arc must dominate its connected component (leaf + arc only)
            continue
        if k < CFG['fill'] * r * math.radians(span):
            continue
        # arc ends
        start = idx[np.argmax(gaps) + 1 - len(idx)] if False else None
        j = int(np.argmax(gaps))
        a0 = idx[(j + 1) % len(idx)] * 5.0
        a1 = idx[j] * 5.0 + 5.0
        ends = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in (a0, a1)]
        leaf = max(_leaf_score(p.ink, (cx, cy), e) for e in ends)
        if leaf < CFG['leaf']:
            continue
        ci = (int(round(cx)), int(round(cy)))
        h_, w_ = lines.shape
        y0, y1, x0, x1 = max(ci[1] - 3, 0), min(ci[1] + 4, h_), max(ci[0] - 3, 0), min(ci[0] + 4, w_)
        if CFG['hinge'] and (y1 <= y0 or x1 <= x0 or not lines[y0:y1, x0:x1].any()):
            continue                        # hinge must sit on a wall/jamb line
        out.append({"c": (cx, cy), "r": r, "span": span, "leaf": leaf, "ends": ends, "inl": k})
    # de-duplicate concentric / near-identical fits
    out.sort(key=lambda a: -a["inl"])
    keep = []
    for a in out:
        if all(math.hypot(a["c"][0] - b["c"][0], a["c"][1] - b["c"][1]) > 0.5 * min(a["r"], b["r"]) for b in keep):
            keep.append(a)
    return keep


def count(path: str):
    p = prep(path)
    if p is None:
        return None, [], None
    arcs = find_arcs(p)
    return len(arcs), arcs, p


def run(ctx):
    from contracts.proof import Element, Voter
    from engine.registry import VoterResult

    n, arcs, p = count(ctx.abs_path)
    if n is None:
        return None
    ev, ids = [], []
    for i, a in enumerate(arcs):
        cx, cy = a["c"]
        pts = [(cx, cy), a["ends"][0], a["ends"][1]]
        eid = f"door_arc_{i}"
        ids.append(eid)
        ev.append(Element(id=eid, kind="door", polygon=p.to_orig(pts), conf=float(min(1.0, a["leaf"])),
                          attrs={"radius_px": a["r"] / p.scale, "span_deg": a["span"], "method": "arc_fit"}))
    return VoterResult(Voter(name=NAME, value=n, element_ids=ids, runs=[n], note=NOTE), ev)
