"""Doors the symbol detectors miss (hand-drawn / faint scans where a door is a gap with a short leaf, no swing arc).

Vision reviewers PROPOSE door positions (x, y in % of the image); code VERIFIES each one on the drawing: there must be a
wall opening there (heavy wall ink on both sides along one axis, little ink in the middle) of door width. Verified
proposals that no detected door already covers are added. The LLM never counts: code counts verified openings.
Runs only when the detectors clearly under-count (fewer doors than rooms - 1) or disagree, and an LLM is configured."""
from __future__ import annotations

import json
import re
from typing import Optional

import cv2
import numpy as np

SYSTEM = ("You look at an architectural floor plan scan. List EVERY door: a doorway in a wall fitted with a door leaf "
          "(a short line or swing arc in the opening; hand-drawn plans may show only the leaf line). Do not list open "
          "passages without a leaf, windows, or wardrobe doors. Reply JSON only: {\"doors\": [{\"x\": <0-100 % from left>, "
          "\"y\": <0-100 % from top>}]}. Mark the CENTRE of each door opening. Never count, just list positions.")


def needed(n_doors: int, n_rooms: int, arc: Optional[int]) -> bool:
    return n_doors < max(2, n_rooms - 1) or (arc is not None and arc >= n_doors + 3)


def _walls(img: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    bg = cv2.dilate(g, np.ones((9, 9), np.uint8))
    ink = ((bg.astype(np.int16) - g) > 40).astype(np.uint8)
    k = max(2, int(round(min(g.shape) / 300)))
    return cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((k + 1, k + 1), np.uint8))       # heavy strokes = walls


def opening_at(walls: np.ndarray, x: float, y: float, door_px: float) -> Optional[list[float]]:
    """Verified wall opening near (x, y): wall ink on both sides of a gap of ~door width. Returns its box or None."""
    h, w = walls.shape
    r = int(door_px)
    best = None
    for dy in range(-r // 2, r // 2 + 1, max(1, r // 8)):
        for dx in range(-r // 2, r // 2 + 1, max(1, r // 8)):
            cx, cy = int(x + dx), int(y + dy)
            if not (r <= cx < w - r and r <= cy < h - r):
                continue
            for horiz in (True, False):
                line = walls[cy, cx - r:cx + r] if horiz else walls[cy - r:cy + r, cx]
                band = walls[cy - 2:cy + 3, cx - r:cx + r].max(0) if horiz else walls[cy - r:cy + r, cx - 2:cx + 3].max(1)
                mid = band[int(0.3 * r):int(1.7 * r)]
                left, right = band[:int(0.3 * r)], band[int(1.7 * r):]
                if mid.mean() < 0.15 and left.mean() > 0.5 and right.mean() > 0.5:
                    sc = abs(dx) + abs(dy)
                    if best is None or sc < best[0]:
                        bx = [cx - r * 0.7, cy - 3, cx + r * 0.7, cy + 3] if horiz else [cx - 3, cy - r * 0.7, cx + 3, cy + r * 0.7]
                        best = (sc, bx)
    return best[1] if best else None


def openings(walls_geo: list[dict], floor: np.ndarray, shape: tuple, door_px: float) -> list[list[float]]:
    """Code-only door candidates: gaps of ~door width between collinear wall pieces of the 3D wall model, with FLOOR on
    both sides (a gap in the outer wall is a window or the entrance, not an interior door). Boxes in image px."""
    h, w = shape[:2]
    W = np.zeros((h, w), np.uint8)
    for wl in walls_geo:
        cv2.fillPoly(W, [np.array(wl["outer"], np.int32)], 1)
        for hole in wl.get("holes", []):
            cv2.fillPoly(W, [np.array(hole, np.int32)], 0)
    cands = []
    for horiz in (True, False):
        A = W if horiz else np.ascontiguousarray(W.T)
        k = max(9, int(0.4 * door_px))
        runs = cv2.morphologyEx(A, cv2.MORPH_OPEN, np.ones((1, k), np.uint8))
        for y in range(2, A.shape[0] - 2, 2):
            xs = np.flatnonzero(runs[y])
            if len(xs) < 2:
                continue
            segs = np.split(xs, np.where(np.diff(xs) > 1)[0] + 1)
            for a, b in zip(segs[:-1], segs[1:]):
                gap = b[0] - a[-1]
                if 0.45 * door_px <= gap <= 1.4 * door_px:
                    cx = (a[-1] + b[0]) / 2
                    cands.append(((cx, y) if horiz else (y, cx), gap, horiz))
    keep: list = []
    for (x, y), gap, horiz in cands:
        if any(np.hypot(x - kx, y - ky) <= 0.7 * door_px for (kx, ky), _, _ in keep):
            continue
        rows = sum(1 for (x2, y2), g2, h2 in cands if h2 == horiz and abs(g2 - gap) <= 0.25 * door_px
                   and (abs(x2 - x) <= 0.15 * door_px if horiz else abs(y2 - y) <= 0.15 * door_px)
                   and (abs(y2 - y) <= 0.5 * door_px if horiz else abs(x2 - x) <= 0.5 * door_px))
        if rows < 2:
            continue                                 # a real opening cuts through the whole wall thickness
        off = 0.6 * door_px                          # floor on both sides, perpendicular to the wall
        sides = [(x, y - off), (x, y + off)] if horiz else [(x - off, y), (x + off, y)]
        if all(0 <= int(sy) < h and 0 <= int(sx) < w and floor[int(sy), int(sx)] for sx, sy in sides):
            keep.append(((x, y), gap, horiz))
    return [[x - g / 2, y - 3, x + g / 2, y + 3] if hz else [x - 3, y - g / 2, x + 3, y + g / 2] for (x, y), g, hz in keep]


def audit(img: np.ndarray, door_boxes: list[list[float]], llms: list, door_px: float) -> dict:
    """Returns {"added": [box], "proposed": n, "verified": n, "cost_usd"}."""
    out = {"added": [], "proposed": 0, "verified": 0, "cost_usd": 0.0, "used": False}
    llms = [L for L in (llms or []) if L is not None and hasattr(L, "complete_vision")]
    if not llms:
        return out
    h, w = img.shape[:2]
    s = min(1.0, 1600 / max(h, w)) if max(h, w) > 1600 else max(1.0, 1100 / max(h, w))
    show = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA)
    png = cv2.imencode(".png", show)[1].tobytes()
    pts: list[tuple[float, float]] = []
    for L in llms:
        try:
            rep = L.complete_vision(SYSTEM, "Floor plan.", png, max_tokens=2500 if getattr(L, "no_think", True) else 8000)
        except Exception:  # noqa: BLE001
            continue
        out["used"] = True
        out["cost_usd"] += float(getattr(rep, "usd", 0.0) or 0.0)
        m = re.search(r"\{.*\}", rep.text or "", re.S)
        try:
            for d in json.loads(m.group(0)).get("doors", []) if m else []:
                pts.append((float(d["x"]) / 100 * w, float(d["y"]) / 100 * h))
        except Exception:  # noqa: BLE001
            pass
    out["proposed"] = len(pts)
    walls = _walls(img)
    have = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in door_boxes]
    for x, y in pts:
        bx = opening_at(walls, x, y, door_px)
        if bx is None:
            continue
        c = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
        if any(np.hypot(c[0] - a, c[1] - b) < door_px for a, b in have):
            continue
        out["verified"] += 1
        have.append(c)
        out["added"].append(bx)
    return out
