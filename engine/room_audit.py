"""Final check of the BUILT model by vision reviewers: "why is this like this?"

The machine readers produce rooms; two vision LLMs then look at the drawing with every room outlined and numbered and
answer a fixed form per room (real room, or sitting on text / legend / title block / empty paper outside the building),
list printed room labels that no room covers (a missing balcony), and say where a sheet holds several floor plans side
by side. Code acts only on what it can verify:

- a room is removed when BOTH reviewers say it is not a room (one reviewer is never enough);
- a missing labelled room is added only when the label is a known room word (engine/glossary.yaml) and a closed region
  of paper exists at that point (flood fill bounded by the drawn lines), of plausible size;
- a split between plans is applied only when engine.scancheck.verify_cut finds a line there that no wall crosses.

No reviewer produces a count or a measurement. Every action is listed in audit["actions"] for the proof.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import cv2
import numpy as np

SYSTEM = (
    "You audit a machine reading of an architectural floor plan. Coloured numbered shapes are the ROOMS the machine "
    "found. Reply with JSON only: "
    '{{"rooms": [{{"n": <number>, "real": true|false, "why": "<= 8 words"}}], '
    '"missing": [{{"label": "<room label printed on the plan that NO numbered shape covers>", "x": <0-100 % from left>, '
    '"y": <0-100 % from top>}}], '
    '"plans": <how many separate floor plans are drawn on this sheet>, '
    '"cuts": [{{"axis": "x"|"y", "at": <0-100 %, the empty strip between two plans>}}], '
    '"plan_labels": ["<floor title of each plan in left-to-right / top-to-bottom order, e.g. 1. kerros>"], '
    '"issues": ["<= 12 words each: anything clearly wrong with the shapes>"]}}. '
    "real=false ONLY when the shape sits on text, a title block, legend, logo, scale bar, dimension lines or empty "
    "paper outside the building. Balconies and terraces (PARVEKE, TERASSI) are real. Room labels may be Nordic "
    "abbreviations: {gloss}. Never count or measure anything."
)


def _overlay(img: np.ndarray, rooms: list[dict]) -> tuple[bytes, float]:
    h, w = img.shape[:2]
    s = min(1.0, 1400.0 / max(h, w))
    canvas = cv2.resize(img, (int(w * s), int(h * s))) if s < 1 else img.copy()
    over = canvas.copy()
    rng = np.random.default_rng(7)
    for i, r in enumerate(rooms, 1):
        pts = np.array([[x * s, y * s] for x, y in r["polygon"]], np.int32)
        col = tuple(int(c) for c in rng.integers(60, 230, 3))
        cv2.fillPoly(over, [pts], col)
        cv2.polylines(canvas, [pts], True, col, 2)
    canvas = cv2.addWeighted(over, 0.35, canvas, 0.65, 0)
    for i, r in enumerate(rooms, 1):
        P = np.array(r["polygon"]) * s
        cx, cy = int(P[:, 0].mean()), int(P[:, 1].mean())
        cv2.putText(canvas, str(i), (cx - 10, cy + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 5)
        cv2.putText(canvas, str(i), (cx - 10, cy + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 180), 2)
    return cv2.imencode(".png", canvas)[1].tobytes(), s


def _parse(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) else None


def _flood_region(img: np.ndarray, x: float, y: float) -> Optional[list[list[float]]]:
    """Closed region of one colour around (x, y): the label's background (white paper or a grey balcony fill),
    grown while the colour stays the same; drawn lines stop it. The label's own letters are filled back in."""
    h, w = img.shape[:2]
    src = cv2.medianBlur(img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), 3)
    r = max(12, int(0.03 * max(h, w)))
    x0, y0 = max(0, int(x) - r), max(0, int(y) - r)
    win = src[y0:int(y) + r, x0:int(x) + r].reshape(-1, 3).astype(int)
    if not len(win):
        return None
    q = (win // 12)                                   # the window's most common colour = the label's background
    keys, counts = np.unique(q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2], return_counts=True)
    bg = keys[np.argmax(counts)]
    hit = np.nonzero(q[:, 0] * 10000 + q[:, 1] * 100 + q[:, 2] == bg)[0]
    ww = min(int(x) + r, w) - x0
    pts = [(int(k % ww) + x0, int(k // ww) + y0) for k in hit]
    sx, sy = min(pts, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(src.copy(), mask, (sx, sy), (0, 0, 0), (14, 14, 14), (14, 14, 14),
                  flags=4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE)
    region = mask[1:-1, 1:-1]
    area = int((region > 0).sum())
    if not (0.002 * h * w <= area <= 0.25 * h * w):
        return None
    ys, xs = np.nonzero(region)
    if xs.min() <= 1 or ys.min() <= 1 or xs.max() >= w - 2 or ys.max() >= h - 2:
        return None                                     # leaked to the sheet edge: not a closed room
    k = max(3, int(0.006 * max(h, w)))
    region = cv2.morphologyEx(region, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))   # letters back in
    cs, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cs, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.6 * cv2.contourArea(cv2.convexHull(c)):
        return None                                     # ragged leak, not a room shape
    c = cv2.approxPolyDP(c, 0.004 * max(h, w), True)
    return [[float(p[0][0]), float(p[0][1])] for p in c] if len(c) >= 3 else None


def audit(img: np.ndarray, rooms: list[dict], llms: list) -> dict:
    """Returns {"used", "cost_usd", "drop": [room ids], "add": [room dicts], "cuts": [{axis, at(0-1)}],
    "plan_labels", "issues", "actions"}. `rooms` are geometry room dicts (id, subtype, label, polygon)."""
    from engine import label_reader as LR
    out = {"used": False, "cost_usd": 0.0, "drop": [], "add": [], "cuts": [], "plan_labels": [], "issues": [],
           "actions": [], "answered": 0}
    llms = [L for L in (llms or []) if L is not None and hasattr(L, "complete_vision")]
    if not llms:
        return out
    rooms = [r for r in rooms if len(r.get("polygon") or []) >= 3]
    png, _ = _overlay(img, rooms)
    sys = SYSTEM.format(gloss=LR.glossary_text(40))
    got = []
    for L in llms:
        try:
            r = L.complete_vision(sys, f"{len(rooms)} numbered rooms.", png, max_tokens=1800)
            out["cost_usd"] += r.usd
            out["used"] = True
            p = _parse(r.text)
            if p:
                got.append(p)
        except Exception:  # noqa: BLE001  (the audit is optional)
            pass
    out["answered"] = len(got)
    out["cost_usd"] = round(out["cost_usd"], 5)
    if not got:
        return out
    h, w = img.shape[:2]
    # 1. rooms both reviewers call not-a-room
    if len(got) >= 2:
        verdicts = [{int(x.get("n", -1)): x for x in (g.get("rooms") or []) if isinstance(x, dict)} for g in got]
        for i, r in enumerate(rooms, 1):
            vs = [v.get(i) for v in verdicts]
            if all(v is not None and v.get("real") is False for v in vs):
                why = "; ".join(str(v.get("why", "")) for v in vs if v.get("why"))
                out["drop"].append(r["id"])
                out["actions"].append(f"removed room {i} ({r.get('subtype') or 'room'}): both reviewers: {why}")
    # 2. printed labels that no room covers -> a closed region at that point, if the label is a room word
    from shapely.geometry import Point, Polygon
    polys = []
    for r in rooms:
        try:
            polys.append(Polygon(r["polygon"]))
        except Exception:  # noqa: BLE001
            pass
    seen = set()
    for g in got:
        for m in g.get("missing") or []:
            if not isinstance(m, dict) or not isinstance(m.get("x"), (int, float)) or not isinstance(m.get("y"), (int, float)):
                continue
            t = LR.room_type(str(m.get("label", "")))
            if not t or LR.norm_label(m["label"]) in seen:
                continue
            x, y = m["x"] / 100 * w, m["y"] / 100 * h
            if any(p.is_valid and p.contains(Point(x, y)) for p in polys):
                continue
            poly = _flood_region(img, x, y)
            if poly is None:
                continue
            seen.add(LR.norm_label(m["label"]))
            sub = {"living_room": "living", "balcony": "balcony", "terrace": "terrace"}.get(t, t)
            out["add"].append({"id": f"room_audit_{len(out['add'])}", "kind": "room", "subtype": sub,
                               "label": str(m["label"]), "polygon": poly})
            out["actions"].append(f"added {m['label']} ({t}): printed label with no room; closed region found there")
    # 3. plan splits (verified by the caller with scancheck.verify_cut) and plan titles
    for g in reversed(got):                       # any reviewer may propose a cut: verify_cut is the check
        for c in g.get("cuts") or []:
            if isinstance(c, dict) and c.get("axis") in ("x", "y") and isinstance(c.get("at"), (int, float)):
                cut = {"axis": c["axis"], "at": float(c["at"]) / 100}
                if not any(x["axis"] == cut["axis"] and abs(x["at"] - cut["at"]) < 0.05 for x in out["cuts"]):
                    out["cuts"].append(cut)
        if not out["plan_labels"]:
            out["plan_labels"] = [str(x) for x in (g.get("plan_labels") or []) if x][:6]
    out["issues"] = [str(x) for g in got for x in (g.get("issues") or []) if x][:6]
    return out
