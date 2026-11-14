"""Geometry for the 3D view: walls traced from the drawing's own pixels + the elements the readers found.

`model(image_bgr, facts, coords)` -> dict in IMAGE PIXEL space (same space as GET /api/image):
  {width, height, walls: [{outer: [[x,y],...], holes: [[[x,y],...]]}], rooms: [{id, label, subtype, polygon}], doors: [...], windows: [...],
   fixtures: [...], wall_note}
Walls are thick dark strokes (morphological opening removes text, hatching and thin symbol lines), traced to
polygons and simplified. This works for any raster or rendered PDF, including uploads, without a model.
Elements from SheetFacts are included only when they share the image pixel space (raster files).
"""
from __future__ import annotations

from typing import Any, Optional

import cv2
import numpy as np

MAX_SIDE = 1400
CNN_MAX_SIDE = 1600


def _trace(mask: np.ndarray, min_area: float, eps: float, to_orig=None) -> list[dict]:
    """mask -> [{outer: [[x,y]..], holes: [[[x,y]..]..]}]; holes keep enclosed rooms open (no solid blocks)."""
    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return []
    hier = hier[0]
    conv = to_orig or (lambda pts: pts)

    def poly(c):
        a = cv2.approxPolyDP(c, eps, True)
        return [[float(x), float(y)] for x, y in conv([(float(p[0][0]), float(p[0][1])) for p in a])] if len(a) >= 3 else None

    out = []
    for i, c in enumerate(cnts):
        if hier[i][3] != -1 or cv2.contourArea(c) < min_area:
            continue                                    # holes are attached to their parent below
        outer = poly(c)
        if outer is None:
            continue
        holes, j = [], hier[i][2]
        while j != -1:
            if cv2.contourArea(cnts[j]) >= min_area:
                hp = poly(cnts[j])
                if hp:
                    holes.append(hp)
            j = hier[j][0]
        out.append({"outer": outer, "holes": holes})
    return out


def _walls(img: np.ndarray) -> tuple[list, str]:
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = g.shape
    _, dark = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # stroke width: walls are the thickest consistent strokes on a plan
    dist = cv2.distanceTransform(dark, cv2.DIST_L2, 3)
    vals = dist[dist > 0]
    if vals.size == 0:
        return [], "no dark strokes found"
    t = max(1.0, float(np.percentile(vals, 90)) * 0.6)
    k = max(2, int(round(t * 2)))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    thick = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
    thick = cv2.morphologyEx(thick, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    out = _trace(thick, max((w * h) * 0.00004, k * k * 2), max(1.0, k * 0.35))
    return out, f"walls traced from strokes >= {k}px thick (morphological opening), {len(out)} pieces"


_LAST_ROOMS = None


def _rooms_to_original(indoor: np.ndarray, v, w: int, h: int) -> np.ndarray:
    """Indoor-room mask from the CNN's rendered variant back to original pixels (via the variant's mapping)."""
    out = np.zeros((h, w), np.uint8)
    cnts, _ = cv2.findContours(indoor * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        pts = v.to_original([(float(p[0][0]), float(p[0][1])) for p in c])
        cv2.fillPoly(out, [np.array(pts, np.int32)], 1)
    return out


def cnn_walls(img_bgr: np.ndarray) -> Optional[tuple[list, str]]:
    """CubiCasa CNN wall class -> polygons in original pixels; None when the model is unavailable."""
    try:
        from engine.raster import model as cc_model, prep
        if not cc_model.available():
            return None
        h, w = img_bgr.shape[:2]
        # big scans: give the CNN more pixels (interior walls vanish at 800 px), capped for CPU time
        target = 800.0                     # 1400 px was tried: worse walls on both clean and archival scans
        v = prep.make_variants(w, h, cap=1, target_long_side=target)[0]
        rooms_p, _ = cc_model.infer(v.render(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))
        arg = np.argmax(rooms_p, axis=0)
        global _LAST_ROOMS
        indoor = np.isin(arg, [cc_model.ROOM_CLASSES.index(c) for c in cc_model.ROOM_CLASSES
                               if c not in ("background", "outdoor", "wall", "railing")]).astype(np.uint8)
        _LAST_ROOMS = _rooms_to_original(indoor, v, w, h)
        mask = (arg == cc_model.ROOM_CLASSES.index("wall")).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        out = _trace(mask, 40, 2.0, v.to_original)      # drop specks, straighter outlines (jagged 3D otherwise)
        return out, f"walls = CubiCasa CNN wall class, {len(out)} pieces"
    except Exception as e:  # noqa: BLE001
        return None


def _el(e) -> dict:
    return {"id": e.id, "kind": e.kind, "subtype": e.subtype, "label": e.label,
            "polygon": [[float(p[0]), float(p[1])] for p in e.polygon]}


def model(img: np.ndarray, facts: Optional[Any] = None, coords: str = "pixels", use_cnn: bool = False,
          scan_check: bool = False, llm=None) -> dict:
    h, w = img.shape[:2]
    if scan_check:
        return _checked(img, facts, coords, use_cnn, llm)
    # the wall CNN was trained on clean CubiCasa plans (240-1700 px); big archival scans get stroke tracing,
    # which finds fewer walls there but never invents them in site plans or title blocks
    got = cnn_walls(img) if (use_cnn and max(h, w) <= CNN_MAX_SIDE) else None
    if got is not None and got[0]:
        walls, note = got
    else:
        s = min(1.0, MAX_SIDE / max(h, w))
        work = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
        walls, note = _walls(work)
        if s < 1:
            sc = lambda P: [[x / s, y / s] for x, y in P]
            walls = [{"outer": sc(wl["outer"]), "holes": [sc(hh) for hh in wl["holes"]]} for wl in walls]
    out = {"width": w, "height": h, "walls": walls, "wall_note": note,
           "rooms": [], "doors": [], "windows": [], "fixtures": [], "elements_aligned": False}
    if facts is not None and coords == "pixels" and facts.elements:
        out["elements_aligned"] = True
        for e in facts.elements:
            if len(e.polygon) < 2:
                continue
            if e.kind == "room":
                out["rooms"].append(_el(e))
            elif e.kind == "door":
                out["doors"].append(_el(e))
            elif e.kind == "window":
                out["windows"].append(_el(e))
            elif e.kind not in ("label", "floor_blob"):
                out["fixtures"].append(_el(e))
    return out


def _trace_full(img: np.ndarray) -> tuple[list, str]:
    h, w = img.shape[:2]
    s = min(1.0, MAX_SIDE / max(h, w))
    work = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
    walls, note = _walls(work)
    if s < 1:
        sc = lambda P: [[x / s, y / s] for x, y in P]
        walls = [{"outer": sc(wl["outer"]), "holes": [sc(hh) for hh in wl["holes"]]} for wl in walls]
    return walls, note


def _checked(img, facts, coords, use_cnn, llm) -> dict:
    """Both wall readers + engine.scancheck (views, agreement, optional vision reviewer) decide the walls."""
    from engine import scancheck
    global _LAST_ROOMS
    _LAST_ROOMS = None
    got = cnn_walls(img) if use_cnn else None
    wa = got[0] if got else []
    wb, _ = _trace_full(img)
    chk = scancheck.check(img, wa, wb, _LAST_ROOMS, llm)
    out = model(img, facts, coords, use_cnn=False)          # elements + shape; walls replaced below
    out["walls"] = chk.pop("walls")
    out["wall_note"] = "walls chosen per view by the scan check (two readers + reviewer)"
    out["check"] = chk
    return out
