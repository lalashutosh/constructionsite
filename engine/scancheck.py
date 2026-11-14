"""Scan check: several readers + a vision-LLM reviewer before anything is built in 3D.

1. views:   split the sheet into separate drawings (ink clusters): floor plan, site plan, title block ...
2. readers: two independent wall readers per view (CubiCasa CNN wall class, stroke tracing); agreement = IoU of
            their (dilated) wall masks, like two voters agreeing on a count
3. review:  (LLM on) a vision model sees the sheet with numbered view boxes and the two overlays, and answers a
            FIXED JSON form: view type, text mirrored?, which overlay matches the real walls. It judges; it never
            produces a number or geometry
4. decide:  code keeps walls only in floor-plan views, picks the reader per view (agreement first, reviewer when they
            disagree), and returns plain-language warnings. LLM off -> CV rules only (CNN rooms inside a view = plan).
"""
from __future__ import annotations

import json
import re
from typing import Optional

import cv2
import numpy as np

VIEW_TYPES = ("floor_plan", "site_plan", "elevation", "section", "title_block", "legend", "photo", "other")
REVIEW_SYSTEM = (
    "You review machine readings of an architectural drawing. Reply with JSON only, no prose, exactly this shape: "
    '{"views": [{"n": <view number>, "type": "floor_plan|site_plan|elevation|section|title_block|legend|photo|other", '
    '"better": "A|B|neither", "walls_missing": true|false, "false_walls": true|false}], '
    '"text_mirrored": true|false, "notes": "<= 20 words"}. '
    "Overlay A (blue) and overlay B (orange) are two different wall readers. 'better' = which one follows the real "
    "walls of that view more closely. Never invent counts or measurements."
)


def views(img: np.ndarray) -> list[dict]:
    """Separate drawings on one sheet: big ink clusters at a coarse scale. Boxes in original pixels."""
    h, w = img.shape[:2]
    s = 600.0 / max(h, w)
    small = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
    ink = (g < 170).astype(np.uint8)
    k = max(3, int(0.03 * max(small.shape[:2])))
    blob = cv2.dilate(ink, np.ones((k, k), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(blob, connectivity=8)
    total = small.shape[0] * small.shape[1]
    out = []
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if bw * bh < 0.03 * total:
            continue
        out.append({"box": [int(x / s), int(y / s), int((x + bw) / s), int((y + bh) / s)], "area_frac": round(bw * bh / total, 3)})
    out.sort(key=lambda v: -v["area_frac"])
    merged: list[dict] = []                     # one drawing = one view: drop boxes mostly inside a bigger one
    for v in out:
        x0, y0, x1, y1 = v["box"]
        inside = False
        for m in merged:
            a0, b0, a1, b1 = m["box"]
            ix = max(0, min(x1, a1) - max(x0, a0)) * max(0, min(y1, b1) - max(y0, b0))
            if ix >= 0.5 * (x1 - x0) * (y1 - y0):
                m["box"] = [min(x0, a0), min(y0, b0), max(x1, a1), max(y1, b1)]
                inside = True
                break
        if not inside:
            merged.append(v)
    out = merged
    if not out:
        out = [{"box": [0, 0, w, h], "area_frac": 1.0}]
    for i, v in enumerate(out, 1):
        v["n"] = i
    return out[:6]


def _mask(walls: list[dict], shape) -> np.ndarray:
    m = np.zeros(shape[:2], np.uint8)
    for wl in walls:
        cv2.fillPoly(m, [np.array(wl["outer"], np.int32)] + [np.array(h, np.int32) for h in wl["holes"]], 255)
    return m


def _iou(a: np.ndarray, b: np.ndarray, tol: int) -> Optional[float]:
    k = np.ones((tol, tol), np.uint8)
    a, b = cv2.dilate(a, k) > 0, cv2.dilate(b, k) > 0
    u = (a | b).sum()
    return None if u == 0 else float((a & b).sum() / u)


def _in_box(wl: dict, box) -> bool:
    xs = [p[0] for p in wl["outer"]]
    ys = [p[1] for p in wl["outer"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def _review_image(img, vs, wa, wb) -> bytes:
    h, w = img.shape[:2]
    s = min(1.0, 1400.0 / max(h, w))
    canvas = cv2.resize(img, (int(w * s), int(h * s))) if s < 1 else img.copy()
    over = canvas.copy()
    for walls, col in ((wa, (230, 120, 30)), (wb, (30, 140, 255))):        # A blue, B orange (BGR)
        for wl in walls:
            pts = [np.array([[x * s, y * s] for x, y in wl["outer"]], np.int32)]
            cv2.polylines(over, pts, True, col, 2)
    canvas = cv2.addWeighted(over, 0.85, canvas, 0.15, 0)
    for v in vs:
        x0, y0, x1, y1 = [int(c * s) for c in v["box"]]
        cv2.rectangle(canvas, (x0, y0), (x1, y1), (40, 40, 40), 2)
        cv2.putText(canvas, str(v["n"]), (x0 + 8, y0 + 34), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    return cv2.imencode(".png", canvas)[1].tobytes()


def _parse(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    vs = [v for v in d.get("views", []) if isinstance(v, dict) and v.get("type") in VIEW_TYPES]
    return {"views": {int(v.get("n", 0)): v for v in vs}, "text_mirrored": bool(d.get("text_mirrored")),
            "notes": str(d.get("notes", ""))[:200]}


def check(img: np.ndarray, walls_cnn: Optional[list], walls_trace: list, rooms_cnn: Optional[np.ndarray] = None,
          llm=None) -> dict:
    """Returns {views:[{n, box, type, type_source, reader, agreement, flags}], walls:[...chosen...], warnings,
    reviewer: {used, cost_usd, notes}}."""
    vs = views(img)
    wa, wb = walls_cnn or [], walls_trace or []
    tol = max(5, int(0.006 * max(img.shape[:2])))
    ma, mb = _mask(wa, img.shape), _mask(wb, img.shape)
    review, cost, used, names = None, 0.0, False, []
    llms = [x for x in (llm if isinstance(llm, (list, tuple)) else [llm]) if x is not None and hasattr(x, "complete_vision")]
    reviews = []
    if llms:
        png = _review_image(img, vs, wa, wb)
        for L in llms:                       # independent reviewers, same picture, same fixed form
            try:
                r = L.complete_vision(REVIEW_SYSTEM, f"There are {len(vs)} numbered views.", png, max_tokens=700)
                cost += r.usd
                used = True
                p = _parse(r.text)
                if p is not None:
                    reviews.append(p)
                    names.append(getattr(L, "kind", "reviewer"))
            except Exception:  # noqa: BLE001  (reviewers are optional; CV rules still decide)
                pass
    disputed: set[int] = set()
    if reviews:
        review = {"views": {}, "text_mirrored": all(r["text_mirrored"] for r in reviews),   # consensus only
                  "notes": " | ".join(r["notes"] for r in reviews if r["notes"])}
        for n in {k for r in reviews for k in r["views"]}:
            got = [r["views"][n] for r in reviews if n in r["views"]]
            types = {g["type"] for g in got}
            merged = dict(got[-1])                       # last = strongest reviewer
            if len(types) > 1:
                disputed.add(n)
            bet = {g.get("better") for g in got}
            merged["better"] = got[-1].get("better") if len(bet) > 1 else next(iter(bet))
            full = len(got) == len(reviews)
            merged["walls_missing"] = full and all(g.get("walls_missing") for g in got)
            merged["false_walls"] = full and all(g.get("false_walls") for g in got)
            merged["agree"] = len(types) == 1 and len(got) == len(reviews)
            review["views"][n] = merged
    chosen, warnings = [], []
    for v in vs:
        x0, y0, x1, y1 = v["box"]
        sub_a, sub_b = ma[y0:y1, x0:x1], mb[y0:y1, x0:x1]
        agree = _iou(sub_a, sub_b, tol)
        v["agreement"] = None if agree is None else round(agree, 2)
        rv = (review or {}).get("views", {}).get(v["n"]) if review else None
        if rv:
            v["type"] = rv["type"]
            v["type_source"] = (f"{len(reviews)} vision reviewers agree" if rv.get("agree") and len(reviews) > 1
                                else "vision reviewer" if len(reviews) == 1 else "vision reviewers disagree: strongest kept")
            if v["n"] in disputed:
                warnings.append(f"View {v['n']}: reviewers disagree on what it is; check it")
        else:
            rooms_here = rooms_cnn is not None and float(rooms_cnn[y0:y1, x0:x1].mean()) > 0.08
            v["type"] = "floor_plan" if (rooms_here or sub_a.any()) else "other"
            v["type_source"] = "CV rule (CNN rooms inside the view)" if rooms_here else "CV rule"
        flags = []
        if v["type"] != "floor_plan":
            v["reader"] = None
            if (sub_a.any() or sub_b.any()):
                warnings.append(f"View {v['n']} looks like a {v['type'].replace('_', ' ')}: no walls built there")
            v["flags"] = flags
            continue
        a_here = [wl for wl in wa if _in_box(wl, v["box"])]
        b_here = [wl for wl in wb if _in_box(wl, v["box"])]
        if agree is not None and agree >= 0.5:
            pick, why = ("A" if a_here else "B"), f"readers agree ({agree:.0%} overlap)"
        elif rv and rv.get("better") in ("A", "B"):
            pick, why = rv["better"], f"readers disagree ({(agree or 0):.0%} overlap); reviewer picked {rv['better']}"
        else:
            pick = "A" if a_here else "B"
            why = f"readers disagree ({(agree or 0):.0%} overlap); default reader"
            flags.append("walls uncertain")
        v["reader"] = {"A": "CNN wall class", "B": "stroke tracing"}[pick]
        v["why"] = why
        if rv and rv.get("walls_missing"):
            flags.append("some walls missing")
        if rv and rv.get("false_walls"):
            flags.append("some walls may be wrong")
        v["flags"] = flags
        chosen += a_here if pick == "A" else b_here
        for f in flags:
            warnings.append(f"View {v['n']} (floor plan): {f}")
    if review and review.get("text_mirrored"):
        warnings.append("Text on the sheet reads mirrored: the scan itself may be flipped")
    return {"views": vs, "walls": chosen, "warnings": warnings,
            "reviewer": {"used": used, "models": names, "cost_usd": round(cost, 5), "notes": (review or {}).get("notes", "")}}
