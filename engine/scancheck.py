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
    '"better": "A|B|neither", "walls_missing": true|false, "false_walls": true|false, '
    '"level": <floor number printed or implied for a floor plan: 0 ground/1st floor, 1 the floor above, -1 basement; '
    'null if unclear>, "level_label": "<floor name as printed, e.g. 1. KERROS, or empty>"}], '
    '"text_mirrored": true|false, "notes": "<= 20 words"}. '
    "Room labels may be Nordic abbreviations (MH=bedroom, OH=living room, K=kitchen, KH/PH=bathroom, WC=toilet room, "
    "S=sauna, ET=hall, VH=wardrobe, PARVEKE=balcony): text like that means a floor plan. "
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


def _thick_ink(img: np.ndarray) -> np.ndarray:
    """Thick dark strokes only (walls): thin lines, text, hatching and coloured frames are removed by an opening."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    dark = (g < 90).astype(np.uint8)
    k = max(3, int(round(0.0055 * max(g.shape[:2]))))
    return cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))


def verify_cut(img: np.ndarray, box, axis: str, at: float) -> Optional[int]:
    """A reviewer proposed 'two plans side by side, split at <at> (fraction of the image)'. Accept only if, within
    +-6% of the box around that line, there is a line no wall crosses with real wall mass on both sides. Returns the
    cut coordinate in image pixels, or None. (Inside one plan every line crosses the outer walls.)"""
    x0, y0, x1, y1 = [int(v) for v in box]
    h, w = img.shape[:2]
    sub = _thick_ink(img[y0:y1, x0:x1])
    if sub.size == 0 or sub.sum() == 0:
        return None
    ax = 0 if axis == "x" else 1
    prof = sub.sum(axis=ax).astype(float)
    n = len(prof)
    c = int(at * (w if axis == "x" else h)) - (x0 if axis == "x" else y0)
    if not (0.15 * n < c < 0.85 * n):
        return None
    r = max(3, int(0.06 * n))
    lo, hi = max(1, c - r), min(n - 1, c + r)
    k = lo + int(np.argmin(prof[lo:hi]))
    tot = prof.sum()
    if prof[k] > 0.01 * prof.max() or min(prof[:k].sum(), prof[k:].sum()) < 0.15 * tot:
        return None
    crop = img[y0:y1, x0:x1]
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    thin = (g < 110).sum(axis=ax) / max(1, g.shape[ax])        # a gutter is paper: almost no ink of any kind
    zero = np.nonzero(prof <= 0.01 * prof.max())[0]
    band = zero[np.abs(zero - k) <= r]
    if thin[k] > 0.012 or len(band) < max(3, 0.01 * n):
        return None
    best = band[np.argmin(thin[band])]
    return int(best) + (x0 if axis == "x" else y0)


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


def _review_image(img, vs, wa, wb, px: float = 1800.0) -> bytes:
    h, w = img.shape[:2]
    s = min(1.0, float(px) / max(h, w))
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


def apply_cuts(img: np.ndarray, vs: list[dict], cuts: Optional[list]) -> tuple[list[dict], list[str]]:
    """Split views where a reviewer said 'two plans side by side' AND verify_cut finds a wall-free gutter there."""
    if not cuts:
        return vs, []
    h, w = img.shape[:2]
    out, done = [], []
    for v in vs:
        parts = [list(v["box"])]
        for c in cuts:
            nxt = []
            for b in parts:
                k = verify_cut(img, b, c["axis"], c["at"])
                if k is None:
                    nxt.append(b)
                    continue
                done.append(f"split at {'x' if c['axis'] == 'x' else 'y'}={k}px (reviewer proposed, gutter verified)")
                nxt += ([[b[0], b[1], k, b[3]], [k, b[1], b[2], b[3]]] if c["axis"] == "x"
                        else [[b[0], b[1], b[2], k], [b[0], k, b[2], b[3]]])
            parts = nxt
        out += [{"box": b, "area_frac": round((b[2] - b[0]) * (b[3] - b[1]) / (w * h), 3)} for b in parts]
    for i, v in enumerate(out, 1):
        v["n"] = i
    return out, done


def check(img: np.ndarray, walls_cnn: Optional[list], walls_trace: list, rooms_cnn: Optional[np.ndarray] = None,
          llm=None, cuts: Optional[list] = None, plan_labels: Optional[list] = None, budget: Optional[dict] = None) -> dict:
    """Returns {views:[{n, box, type, type_source, reader, agreement, flags}], walls:[...chosen...], warnings,
    reviewer: {used, cost_usd, notes}}."""
    vs, cut_notes = apply_cuts(img, views(img), cuts)
    wa, wb = walls_cnn or [], walls_trace or []
    tol = max(5, int(0.006 * max(img.shape[:2])))
    ma, mb = _mask(wa, img.shape), _mask(wb, img.shape)
    review, cost, used, names = None, 0.0, False, []
    llms = [x for x in (llm if isinstance(llm, (list, tuple)) else [llm]) if x is not None and hasattr(x, "complete_vision")]
    reviews = []
    if llms:
        bud = budget or {}                       # chosen from the sheet profile (engine/profile.review_budget)
        png = _review_image(img, vs, wa, wb, bud.get("image_px", 1800))
        from concurrent.futures import ThreadPoolExecutor

        def ask(L):
            import copy
            Q = copy.copy(L)
            think = int(bud.get("think_tokens", 0))
            Q.no_think = think == 0 or getattr(L, "kind", "") == "fast"   # simple plan: no thinking; dense sheet: strong thinks
            try:
                return L, Q.complete_vision(REVIEW_SYSTEM, f"There are {len(vs)} numbered views.", png,
                                            max_tokens=700 + (min(think, 6000) if not Q.no_think else 0))
            except Exception:  # noqa: BLE001  (reviewers are optional; CV rules still decide)
                return L, None
        with ThreadPoolExecutor(max_workers=len(llms)) as ex:      # independent reviewers, in parallel
            done = list(ex.map(ask, llms))
        for L, r in done:                    # same order as llms: strongest last
            if r is None:
                continue
            cost += r.usd
            used = True
            p = _parse(r.text)
            if p is not None:
                reviews.append(p)
                names.append(getattr(L, "kind", "reviewer"))
    disputed: set[int] = set()
    if reviews:
        two = len(reviews) >= 2                         # a consensus needs at least two reviewers' answers
        review = {"views": {}, "text_mirrored": two and all(r["text_mirrored"] for r in reviews),
                  "notes": " | ".join(r["notes"] for r in reviews if r["notes"])}
        for n in {k for r in reviews for k in r["views"]}:
            got = [r["views"][n] for r in reviews if n in r["views"]]
            types = {g["type"] for g in got}
            merged = dict(got[-1])                       # last = strongest reviewer
            if len(types) > 1:
                disputed.add(n)
            bet = {g.get("better") for g in got}
            merged["better"] = got[-1].get("better") if len(bet) > 1 else next(iter(bet))
            full = two and len(got) == len(reviews)
            merged["walls_missing"] = full and all(g.get("walls_missing") for g in got)
            merged["false_walls"] = full and all(g.get("false_walls") for g in got)
            merged["agree"] = len(types) == 1 and len(got) == len(reviews)
            lv = [g.get("level") for g in got if isinstance(g.get("level"), int)]
            merged["level"] = lv[-1] if lv else None            # strongest reviewer's reading
            merged["level_label"] = next((str(g.get("level_label")) for g in reversed(got) if g.get("level_label")), "")
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
        if rv:
            v["level"], v["level_label"] = rv.get("level"), rv.get("level_label", "")
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
        warnings.append("Text on the sheet reads upside down or mirrored: the scan is rotated or flipped (counts are unaffected)")
    # several floor plans on ONE sheet = several floors: list them in level order (unknown: top-to-bottom, left-to-right)
    plans = [v for v in vs if v.get("type") == "floor_plan"]
    floors = []
    for k, v in enumerate(sorted(plans, key=lambda v: (v.get("level") if isinstance(v.get("level"), int) else 50,
                                                       v["box"][1] // 200, v["box"][0]))):
        idx = [i for i, wl in enumerate(chosen) if _in_box(wl, v["box"])]
        lv = v.get("level")
        if not v.get("level_label") and plan_labels and len(plan_labels) == len(plans) and cut_notes:
            v["level_label"] = plan_labels[k]
        floors.append({"view": v["n"], "box": v["box"], "level": lv, "level_label": v.get("level_label") or "",
                       "label": v.get("level_label") or (f"Level {lv}" if isinstance(lv, int) else f"Floor {k + 1}"),
                       "wall_indices": idx, "level_source": "read by AI reviewers" if isinstance(lv, int) else "position on sheet"})
    if len(floors) > 1:
        warnings.append(f"{len(floors)} floor plans on one sheet: shown as {len(floors)} floors")
    warnings += [f"Views: {c}" for c in cut_notes]
    return {"views": vs, "walls": chosen, "warnings": warnings, "floors": floors,
            "reviewer": {"used": used, "models": names, "answered": len(reviews), "asked": len(llms),
                         "cost_usd": round(cost, 5), "notes": (review or {}).get("notes", "")}}
