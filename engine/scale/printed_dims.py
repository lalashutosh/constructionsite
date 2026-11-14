"""Scale from measurements PRINTED on the drawing (tag `specified`), so sizes come from the source, not from a guess.

Finnish/Nordic plans print opening sizes next to windows and doors as W x H in centimetres ("248x149", "9x21" in
modules is not used here). Each such label is matched to the nearest detected window/door; that element's long side in
pixels / W metres is one scale estimate. A scale is accepted only when >= 2 labels agree within 6% (one misread digit
cannot move the result), and the anchor's note says which labels were used.
OCR runs at 0/90/180/270 degrees (scans are often rotated) and is cached per image sha256.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import statistics
from typing import Optional

import cv2
import numpy as np

from contracts.proof import ScaleAnchor, SheetFacts, Tag

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "scale_dims"
WXH = re.compile(r"^[^\d]*(\d{2,4})\s*[xX×*]\s*(\d{2,4})[^\d]*$")
AGREE = 0.06


def _tokens(img_bgr: np.ndarray) -> list[dict]:
    import pytesseract
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    h, w = g.shape
    up = 2.0 if max(h, w) < 1600 else 1.0           # small text needs 2x; timeout raised to 60 s for it
    G = cv2.resize(g, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    H, W = G.shape
    out = []
    for code in (None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE):
        im = G if code is None else cv2.rotate(G, code)
        try:
            d = pytesseract.image_to_data(im, config="--psm 11", output_type=pytesseract.Output.DICT, timeout=60)
        except Exception:  # noqa: BLE001
            continue
        for t, x, y, bw, bh, c in zip(d["text"], d["left"], d["top"], d["width"], d["height"], d["conf"]):
            tt = (t or "").strip()
            m = WXH.match(tt)
            if not m:
                if re.fullmatch(r"\d{3,5}", tt) and float(c) >= 70 and 600 <= int(tt) <= 30000:
                    out.append({"text": tt, "plain_mm": int(tt)})      # a dimension line value in millimetres
                continue
            if float(c) < 60:
                continue
            cx, cy = x + bw / 2, y + bh / 2
            if code is None:
                ox, oy = cx, cy
            elif code == cv2.ROTATE_90_CLOCKWISE:          # rotated (x', y') -> original (y', H-1-x')
                ox, oy = cy, H - 1 - cx
            elif code == cv2.ROTATE_180:
                ox, oy = W - 1 - cx, H - 1 - cy
            else:                                          # 90 ccw: (x', y') -> (W-1-y', x')
                ox, oy = W - 1 - cy, cx
            wv, hv = int(m.group(1)), int(m.group(2))
            unit = 0.01 if wv < 400 else 0.001               # 248x149 = cm, 1200x1500 = mm
            out.append({"text": t.strip(), "w_m": wv * unit, "x": ox / up, "y": oy / up, "conf": float(c)})
    return out


def _long_side_px(poly) -> float:
    pts = np.array(poly, np.float32)
    if len(pts) < 2:
        return 0.0
    (_, _), (a, b), _ = cv2.minAreaRect(pts)
    return float(max(a, b))


def anchor(facts: SheetFacts, abs_path: str, sha: str) -> Optional[ScaleAnchor]:
    """One `dimension` anchor (tag specified) or None."""
    # BIG SHEETS: opening labels / plain mm values are a small-plan (Finnish floor plan) cue. On a 34x22 in sheet the
    # OCR'd numbers (room numbers, elevations) matched random room outlines and gave 610.7 px/m 'specified' on a sheet
    # whose note says 1/2" = 1'-0" (246.06). Scale on big sheets comes from engine.scale.sheet_scale instead.
    if max(facts.width_px or 0, facts.height_px or 0) >= 2400:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sha}-v2.json"
    if f.exists():
        toks = json.loads(f.read_text())
    else:
        img = cv2.imread(abs_path, cv2.IMREAD_COLOR)
        toks = _tokens(img) if img is not None else []
        f.write_text(json.dumps(toks))
    plain = _plain_anchor([t for t in toks if "plain_mm" in t], facts)
    toks = [t for t in toks if "w_m" in t]
    openings = [e for e in facts.elements if e.kind in ("window", "door") and len(e.polygon) >= 2]
    if not toks or not openings:
        return plain
    size = max(facts.width_px or 0, facts.height_px or 0) or 1000
    cands = []
    for t in toks:
        best, bd = None, 1e9
        for e in openings:
            xs, ys = [p[0] for p in e.polygon], [p[1] for p in e.polygon]
            d = math.hypot((min(xs) + max(xs)) / 2 - t["x"], (min(ys) + max(ys)) / 2 - t["y"])
            if d < bd:
                best, bd = e, d
        if best is None or bd > 0.12 * size or not (0.4 <= t["w_m"] <= 4.0):
            continue
        L = _long_side_px(best.polygon)
        if L > 2:
            cands.append({"px_per_m": L / t["w_m"], "text": t["text"], "id": best.id})
    if len(cands) < 2:
        return None
    vals = sorted(c["px_per_m"] for c in cands)
    best_group = []
    for v in vals:                                          # largest group within +-AGREE of a member
        grp = [c for c in cands if abs(c["px_per_m"] / v - 1) <= AGREE]
        if len(grp) > len(best_group):
            best_group = grp
    if len(best_group) < 2:
        return plain
    pv = statistics.median(c["px_per_m"] for c in best_group)
    spread = (max(c["px_per_m"] for c in best_group) / min(c["px_per_m"] for c in best_group)) - 1
    labels = ", ".join(sorted({c["text"] for c in best_group}))
    return ScaleAnchor(kind="dimension", px_per_m=pv, rel_sigma=max(0.02, spread / 2), tag=Tag.specified,
                       note=f"printed opening sizes ({labels}) matched to {len(best_group)} openings that agree "
                            f"within {spread:.0%}; {len(cands) - len(best_group)} other labels disagreed",
                       element_ids=[c["id"] for c in best_group])


def _plain_anchor(toks: list[dict], facts: SheetFacts) -> Optional[ScaleAnchor]:
    """Plain dimension values (mm) matched to real lengths on the plan: room sides and the extents of each building
    outline. Accepted only when >= 2 DIFFERENT printed values agree on one px/m within 3% (chance agreement is rare)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    nums = sorted({t["plain_mm"] for t in toks})
    rooms = []
    for e in facts.elements:
        if e.kind == "room" and len(e.polygon) >= 3:
            try:
                rooms.append(Polygon(e.polygon))
            except Exception:  # noqa: BLE001
                pass
    if len(nums) < 2 or not rooms:
        return None
    L = []
    for r in rooms:
        x0, y0, x1, y1 = r.bounds
        L += [x1 - x0, y1 - y0]
    u = unary_union([r.buffer(2) for r in rooms])
    for g in getattr(u, "geoms", [u]):
        x0, y0, x1, y1 = g.bounds
        L += [x1 - x0, y1 - y0]
    L = [l for l in L if l > 20]
    cands = [(l / (n / 1000.0), n) for n in nums for l in L]
    best, sup = None, set()
    for r, _ in cands:
        s_ = {n for rr, n in cands if abs(rr / r - 1) <= 0.03}
        if len(s_) > len(sup):
            best, sup = r, s_
    if best is None or len(sup) < 2:
        return None
    vals = [rr for rr, n in cands if abs(rr / best - 1) <= 0.03]
    pv = statistics.median(vals)
    return ScaleAnchor(kind="dimension", px_per_m=pv, rel_sigma=0.03, tag=Tag.specified,
                       note=f"printed dimensions ({', '.join(str(n) for n in sorted(sup))} mm) match plan lengths "
                            f"at one scale within 3%")
