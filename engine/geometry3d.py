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


def _wall_like(c) -> bool:
    """Walls are long and thin (any angle, also curved); furniture, fixtures and filled boxes are compact.
    Thickness ~ 2*area/perimeter; a wall piece is at least ~3x longer than it is thick."""
    area = cv2.contourArea(c)
    per = cv2.arcLength(c, True)
    if area <= 0 or per <= 0:
        return False
    thick = 2 * area / per
    length = per / 2
    return length >= 3.0 * thick


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
        if not holes and not _wall_like(c):
            continue                                    # compact solid blob = furniture/fixture/hatching, not a wall
        out.append({"outer": outer, "holes": holes})
    return out


def _walls(img: np.ndarray) -> tuple[list, str]:
    """Line-drawing wall reader (any angle, curves too). Archival plans draw walls as two thin parallel lines:
    adaptive threshold (faint scans) -> close by the wall gap (double lines become one solid band) -> open (single
    thin lines, hatching and dimension lines vanish) -> keep only the connected wall network (text and labels float
    free) -> drop anything touching the sheet border -> keep long thin pieces only."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = g.shape
    ink = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 12)
    gap = max(3, int(round(max(h, w) / 230)))
    solid = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (gap, gap)))
    o = max(3, gap // 2 + 1)
    solid = cv2.morphologyEx(solid, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (o, o)))
    # the wall network: components (after bridging door gaps) that are a sizeable part of the biggest one
    bridge = cv2.dilate(solid, np.ones((gap * 3, gap * 3), np.uint8))     # bridges door openings
    n, lab, st, _ = cv2.connectedComponentsWithStats(bridge, connectivity=8)
    keep = np.zeros_like(solid)
    if n > 1:
        m = 2 * gap
        inner = [i for i in range(1, n)
                 if not (st[i][0] <= m or st[i][1] <= m or st[i][0] + st[i][2] >= w - m or st[i][1] + st[i][3] >= h - m)]
        if inner:
            big = max(st[i][4] for i in inner)
            for i in inner:
                if st[i][4] >= 0.10 * big:
                    keep[lab == i] = 255
    solid = cv2.bitwise_and(solid, keep)
    walls = _trace(solid, max((w * h) * 0.00004, gap * gap * 2), max(1.0, gap * 0.25))
    L = max(h, w) * 0.025
    walls = [wl for wl in walls
             if wl["holes"] or cv2.arcLength(np.array(wl["outer"], np.float32).reshape(-1, 1, 2), True) / 2 >= L]
    return walls, f"walls traced as line pairs (gap {gap}px), connected network only, {len(walls)} pieces"


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
    if coords == "pixels":
        try:                                   # stair flights from tread lines; never breaks the 3D
            from engine.raster import stairs as _stairs
            for k, f in enumerate(_stairs.detect(img, walls=None)):
                out["fixtures"].append({"id": f"stairs-{k}", "kind": "stairs", "subtype": None,
                                        "label": f"stairs ({f['attrs']['treads']} treads)",
                                        "polygon": f["polygon"], "conf": f["conf"], "attrs": f["attrs"]})
        except Exception:
            pass
    return out


def _drop_stairs_in_walls(out: dict, shape) -> None:
    """Hatching inside thick walls looks like treads: a 'flight' that lies mostly inside the chosen walls is not one."""
    st = [f for f in out["fixtures"] if f.get("kind") == "stairs"]
    if not st or not out.get("walls"):
        return
    m = np.zeros(shape[:2], np.uint8)
    for wl in out["walls"]:                 # outer ring minus holes (the rooms) = the wall itself
        cv2.fillPoly(m, [np.array(wl["outer"], np.int32)] + [np.array(h, np.int32) for h in wl.get("holes", [])], 1)
    keep_ids = set()
    for f in st:
        b = np.zeros(shape[:2], np.uint8)
        cv2.fillPoly(b, [np.array(f["polygon"], np.int32)], 1)
        area = int(b.sum())
        if area and (b & m).sum() / area < 0.4:
            keep_ids.add(f["id"])
    out["fixtures"] = [f for f in out["fixtures"] if f.get("kind") != "stairs" or f["id"] in keep_ids]


def _trace_full(img: np.ndarray) -> tuple[list, str]:
    h, w = img.shape[:2]
    s = min(1.0, MAX_SIDE / max(h, w))
    work = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
    walls, note = _walls(work)
    if s < 1:
        sc = lambda P: [[x / s, y / s] for x, y in P]
        walls = [{"outer": sc(wl["outer"]), "holes": [sc(hh) for hh in wl["holes"]]} for wl in walls]
    return walls, note


def _cad_model(img, facts, coords) -> Optional[dict]:
    """Construction sheet (title block, border, several views): walls from LINE GEOMETRY of the main plan view only
    (engine/bigsheet.py). No CubiCasa CNN, no vision reviewer: the sheet profile already says what each region is."""
    prof = (facts.extras.get("profile") if facts is not None else None) or {}
    if prof.get("sheet_type") != "cad_sheet" or facts.extras.get("route") != "cad" or coords != "pixels":
        return None
    from engine import bigsheet, profile as P
    from engine.pipeline import _abs
    h, w = img.shape[:2]
    try:
        words = P.words_for(_abs(facts.provenance.file), facts.provenance.sha256, img)
    except Exception:  # noqa: BLE001
        words = []
    walls = bigsheet.walls(img, {**prof, "width_px": w, "height_px": h}, words)
    out = {"width": w, "height": h, "walls": walls, "rooms": [], "doors": [], "windows": [], "fixtures": [],
           "elements_aligned": True,
           "wall_note": f"construction sheet: walls read from line geometry of the main plan view ({len(walls)} pieces); "
                        "title block, notes, schedules and dimension chains excluded"}
    for e in facts.elements:
        if e.kind == "room" and len(e.polygon) >= 3:
            out["rooms"].append(_el(e))
    views = []
    for v in prof.get("views", []):
        views.append({"n": v["n"], "box": v["box"], "type": "floor_plan" if v["kind"] == "plan" else
                      {"notes": "other", "schedule": "legend", "legend": "legend", "key_plan": "other", "detail": "other"}.get(v["kind"], "other"),
                      "type_source": "sheet profile", "reader": "line geometry" if v["kind"] == "plan" else None,
                      "flags": [], "title": v.get("title"), "kind": v["kind"]})
    warns = [f"Construction sheet: {len(views)} regions found; walls read only inside the main plan view"]
    if prof.get("title_block"):
        warns.append("Title block excluded from the model")
    out["check"] = {"views": views, "walls": walls, "warnings": warns, "floors": [], "profile": {
        k: prof.get(k) for k in ("sheet_type", "route", "complexity", "main_view", "title_block", "border")},
        "reviewer": {"used": False, "models": [], "answered": 0, "asked": 0, "cost_usd": 0.0,
                     "notes": "the sheet profile decided; no vision reviewer was needed"}}
    return out


def _checked(img, facts, coords, use_cnn, llm) -> dict:
    """Both wall readers + engine.scancheck (views, agreement, optional vision reviewer) decide the walls."""
    cad = _cad_model(img, facts, coords)
    if cad is not None:
        return cad
    from engine import scancheck
    global _LAST_ROOMS
    _LAST_ROOMS = None
    got = cnn_walls(img) if use_cnn else None
    wa = got[0] if got else []
    wb, _ = _trace_full(img)
    out = model(img, facts, coords, use_cnn=False)          # elements + shape; walls replaced below
    aud = None
    try:                                                    # AI audit of the built rooms; code verifies each action
        from engine import room_audit
        aud = room_audit.audit(img, out["rooms"], llm if isinstance(llm, (list, tuple)) else [llm],
                               stairs=[f for f in out["fixtures"] if f.get("kind") == "stairs"])
        if aud["drop"] or aud["add"]:
            out["rooms"] = [r for r in out["rooms"] if r["id"] not in set(aud["drop"])] + aud["add"]
    except Exception:  # noqa: BLE001  (the audit is optional)
        aud = None
    bud = ((facts.extras.get("profile") or {}).get("review") if facts is not None else None) or None
    chk = scancheck.check(img, wa, wb, _LAST_ROOMS, llm, cuts=(aud or {}).get("cuts"),
                          plan_labels=(aud or {}).get("plan_labels"), budget=bud)
    if aud:
        chk["audit"] = {k: aud[k] for k in ("used", "answered", "cost_usd", "drop", "actions", "issues", "drop_stairs")}
        chk["audit"]["added"] = [r["id"] for r in aud["add"]]
        chk["warnings"] += [f"AI audit: {a}" for a in aud["actions"]]
    out["walls"] = chk.pop("walls")
    _drop_stairs_in_walls(out, img.shape)
    if aud and aud.get("drop_stairs"):
        out["fixtures"] = [f for f in out["fixtures"] if f.get("id") not in set(aud["drop_stairs"])]
    out["wall_note"] = "walls chosen per view by the scan check (two readers + reviewer)"
    out["check"] = chk
    return out
