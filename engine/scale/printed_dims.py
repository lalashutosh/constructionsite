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
    up = 2.0 if max(h, w) < 1600 else 1.0
    G = cv2.resize(g, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    H, W = G.shape
    out = []
    for code in (None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE):
        im = G if code is None else cv2.rotate(G, code)
        try:
            d = pytesseract.image_to_data(im, config="--psm 11", output_type=pytesseract.Output.DICT, timeout=20)
        except Exception:  # noqa: BLE001
            continue
        for t, x, y, bw, bh, c in zip(d["text"], d["left"], d["top"], d["width"], d["height"], d["conf"]):
            m = WXH.match((t or "").strip())
            if not m or float(c) < 60:
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
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sha}.json"
    if f.exists():
        toks = json.loads(f.read_text())
    else:
        img = cv2.imread(abs_path, cv2.IMREAD_COLOR)
        toks = _tokens(img) if img is not None else []
        f.write_text(json.dumps(toks))
    openings = [e for e in facts.elements if e.kind in ("window", "door") and len(e.polygon) >= 2]
    if not toks or not openings:
        return None
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
        return None
    pv = statistics.median(c["px_per_m"] for c in best_group)
    spread = (max(c["px_per_m"] for c in best_group) / min(c["px_per_m"] for c in best_group)) - 1
    labels = ", ".join(sorted({c["text"] for c in best_group}))
    return ScaleAnchor(kind="dimension", px_per_m=pv, rel_sigma=max(0.02, spread / 2), tag=Tag.specified,
                       note=f"printed opening sizes ({labels}) matched to {len(best_group)} openings that agree "
                            f"within {spread:.0%}; {len(cands) - len(best_group)} other labels disagreed",
                       element_ids=[c["id"] for c in best_group])
