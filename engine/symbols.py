"""Deep read of a big, detailed plan: every furniture / fixture SYMBOL counted, every room named, one checklist.

CAD sheets draw furniture as exact copies of a few symbols (bed, desk, chair, wardrobe, toilet, sink, door swing ...).
So symbols are DISCOVERED BY REPETITION, by code:
  1. inside the building outline, heavy wall strokes are removed; thin-line ink splits into components;
  2. components are clustered by shape (rotation 0/90/180/270 + mirror invariant, size within 12-15%);
  3. a cluster that repeats (>= 4) is a symbol TYPE; its members are its instances (each one a node with a box);
  4. second voter: the type's exemplar is template-matched (normalised cross-correlation, 8 orientations, at half
     resolution) over the plan; only for exemplars with real 2D structure (thin line fragments match everywhere);
  5. a vision model NAMES each type ONCE from a numbered contact sheet (rule 8a: classify each distinct template once).
     It never counts. Without an LLM types stay "symbol type k" and are still counted.
Rooms: engine/outline.subrooms (enclosed spaces) named "Hallway n" (long thin), "<legend name> n" (legend colour zone),
a printed space word, or "Room n". Each symbol instance is assigned to the room that contains its centre.

  checklist(abs_path, sha, facts, llm=None) -> {deep, rooms, totals, elements, types, cost}
Cached at cache/symbols/<sha>-<VERSION>.json (paid once per drawing)."""
from __future__ import annotations

import json
import pathlib
import re
import time
from typing import Any, Optional

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "symbols"
VERSION = "v6"
NAMES = ["bed", "side table", "desk", "chair", "sofa", "lounge chair", "table", "closet", "wardrobe", "toilet", "sink",
         "shower", "bathtub", "door", "window", "stair", "tv", "kitchen counter", "fridge", "gym equipment", "washer",
         "plant", "column", "other"]
# physical size check (long side, short side, metres) - code verifies the vision model's name at the solved scale
SIZE_M = {"bed": (1.7, 2.4, 0.8, 2.1), "side table": (0.3, 0.8, 0.25, 0.8), "desk": (0.8, 2.2, 0.4, 1.0),
          "chair": (0.35, 0.9, 0.3, 0.9), "sofa": (1.2, 3.2, 0.6, 1.2), "lounge chair": (0.6, 1.2, 0.5, 1.1),
          "table": (0.5, 3.0, 0.4, 1.6), "closet": (0.5, 3.0, 0.3, 0.9), "wardrobe": (0.5, 3.0, 0.3, 0.9),
          "toilet": (0.4, 0.9, 0.3, 0.7), "sink": (0.3, 1.2, 0.25, 0.7), "shower": (0.7, 1.8, 0.7, 1.4),
          "bathtub": (1.4, 2.0, 0.6, 1.0), "door": (0.6, 1.9, 0.5, 1.9), "window": (0.5, 4.0, 0.05, 0.5),
          "stair": (2.0, 9.0, 0.8, 4.0), "tv": (0.6, 2.0, 0.05, 0.5), "kitchen counter": (1.0, 6.0, 0.5, 0.9),
          "fridge": (0.5, 1.0, 0.5, 0.9), "gym equipment": (0.6, 2.5, 0.4, 1.5), "washer": (0.5, 0.8, 0.5, 0.8),
          "plant": (0.2, 1.2, 0.2, 1.2), "column": (0.2, 1.2, 0.2, 1.2)}


def plausible(name: str, long_m: float, short_m: float) -> bool:
    r = SIZE_M.get(name)
    if r is None:
        return True
    return r[0] * 0.8 <= long_m <= r[1] * 1.25 and r[2] * 0.8 <= short_m <= r[3] * 1.25


LABEL = {"side table": "Side tables", "closet": "Closets", "wardrobe": "Closets", "tv": "TVs", "gym equipment": "Gym equipment",
         "lounge chair": "Lounge chairs", "stair": "Stair flights", "kitchen counter": "Kitchen counters"}
SYSTEM = ("You name furniture and fixture SYMBOLS from an architectural floor plan. The image is a grid of numbered "
          "cells; each cell shows ONE symbol type outlined in RED (with its surroundings for context) and its real size "
          "in metres in the caption - use the size: a bed is about 2 x 1 m, a side table about 0.5 x 0.5 m (a bed, desk, chair, sofa, lounge chair, side table, table, closet/wardrobe, "
          "toilet, sink, shower, bathtub, door swing, window, stair, TV, kitchen counter, fridge, gym equipment, washer, "
          "plant, column) or a fragment of linework (other). Reply JSON only: {\"types\": [{\"n\": <cell number>, "
          "\"name\": \"<one of: " + ", ".join(NAMES) + ">\"}]}. Never count anything.")


def deep_info(prof: dict, n_rooms: int = 0) -> dict:
    """Is this sheet complex enough for the deep read? (and how long it will take, said up front)"""
    w, h = prof.get("width_px") or 0, prof.get("height_px") or 0
    mpx = w * h / 1e6
    cx = float(prof.get("complexity") or 0)
    on = mpx >= 20 and (cx >= 0.55 or n_rooms >= 20)
    eta = int(30 + 2.5 * mpx + 0.6 * n_rooms) if on else 0
    why = (f"{w}x{h} px ({mpx:.0f} megapixels), complexity {cx:.2f}, {n_rooms} enclosed spaces: every symbol is "
           "discovered, counted and named, which takes longer" if on else "regular read")
    return {"on": bool(on), "reason": why, "eta_s": eta}


def _components(g: np.ndarray, mask: np.ndarray, words: list[dict], ppm: float):
    ink = ((g < 160) & (mask > 0)).astype(np.uint8)
    for w in words:
        a, b, c, d = [int(v) for v in w["box"]]
        ink[max(0, b - 1):d + 2, max(0, a - 1):c + 2] = 0
    thick = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    thin = ink & (1 - cv2.dilate(thick, np.ones((3, 3), np.uint8)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(thin, 8)
    lo, hi = max(8, int(0.25 * ppm)), int(3.0 * ppm)
    keep = [i for i in range(1, n) if lo <= max(st[i][2], st[i][3]) <= hi and min(st[i][2], st[i][3]) >= 0.12 * ppm
            and st[i][4] >= 20]
    return lab, st, keep


def _desc(lab, st, i, S: int = 24):
    x, y, w, h = st[i][:4]
    m = (lab[y:y + h, x:x + w] == i).astype(np.uint8) * 255
    side = max(w, h)
    pad = np.zeros((side, side), np.uint8)
    pad[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = m
    d = cv2.resize(pad, (S, S), interpolation=cv2.INTER_AREA) > 40
    return cv2.dilate(d.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0, (max(w, h), min(w, h))


def _v8(d):
    return [np.rot90(d, k) for k in range(4)] + [np.rot90(np.fliplr(d), k) for k in range(4)]


def _cluster(lab, st, keep) -> list[dict]:
    reps: list[dict] = []
    for i in keep:
        d, dims = _desc(lab, st, i)
        best = None
        for r in reps:
            if abs(r["dims"][0] - dims[0]) > 0.12 * dims[0] + 2 or abs(r["dims"][1] - dims[1]) > 0.15 * dims[1] + 2:
                continue
            iou = max(float((v & r["d"]).sum()) / max(1, float((v | r["d"]).sum())) for v in _v8(d))
            if iou >= 0.6 and (best is None or iou > best[0]):
                best = (iou, r)
        if best:
            best[1]["members"].append(i)
        else:
            reps.append({"d": d, "dims": dims, "members": [i]})
    reps = [r for r in reps if len(r["members"]) >= 4]
    reps.sort(key=lambda r: -len(r["members"]))
    return reps[:30]


def _ncc_hits(g: np.ndarray, mask: np.ndarray, box: list[int]) -> Optional[list[tuple[float, float]]]:
    """Second voter: template-match the exemplar (8 orientations) at half resolution inside the outline."""
    x, y, w, h = box
    if min(w, h) < 16:
        return None                                      # a thin fragment matches every line on the sheet
    ys, xs = np.where(mask > 0)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    inv = (255 - g[y0:y1, x0:x1]).astype(np.float32)
    inv[mask[y0:y1, x0:x1] == 0] = 0
    s = 0.5
    img = cv2.resize(inv, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    tpl = cv2.resize((255 - g[y:y + h, x:x + w]).astype(np.float32), None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    if tpl.std() < 1 or (tpl > 60).mean() < 0.05:
        return None
    hits = []
    for v in _v8(tpl):
        v = np.ascontiguousarray(v)
        if v.shape[0] >= img.shape[0] or v.shape[1] >= img.shape[1]:
            continue
        m = cv2.matchTemplate(img, v, cv2.TM_CCOEFF_NORMED)
        yy, xx = np.where(m >= 0.78)
        hits += [(float(m[a, b]), b + v.shape[1] / 2, a + v.shape[0] / 2) for a, b in zip(yy, xx)]
    hits.sort(key=lambda t: -t[0])
    keep: list[tuple] = []
    rad2 = (0.45 * min(tpl.shape)) ** 2
    for sc, cx, cy in hits:
        if all((cx - a) ** 2 + (cy - b) ** 2 > rad2 for _, a, b in keep):
            keep.append((sc, cx, cy))
        if len(keep) > 2000:
            return None
    return [(x0 + cx / s, y0 + cy / s) for _, cx, cy in keep]


def _same_shape(g: np.ndarray, mask: np.ndarray, d_ref, c: tuple[float, float], w: int, h: int) -> bool:
    cx, cy = c
    best = 0.0
    for ww, hh in ((w, h), (h, w)):
        x0, y0 = int(cx - ww / 2), int(cy - hh / 2)
        if x0 < 0 or y0 < 0 or x0 + ww > g.shape[1] or y0 + hh > g.shape[0]:
            continue
        m = ((g[y0:y0 + hh, x0:x0 + ww] < 160) & (mask[y0:y0 + hh, x0:x0 + ww] > 0)).astype(np.uint8) * 255
        side = max(ww, hh)
        pad = np.zeros((side, side), np.uint8)
        pad[(side - hh) // 2:(side - hh) // 2 + hh, (side - ww) // 2:(side - ww) // 2 + ww] = m
        d = cv2.resize(pad, (24, 24), interpolation=cv2.INTER_AREA) > 40
        d = cv2.dilate(d.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
        best = max(best, max(float((v & d_ref).sum()) / max(1, float((v | d_ref).sum())) for v in _v8(d)))
    return best >= 0.45


def _contact_sheet(g: np.ndarray, st, reps: list[dict], ppm: float) -> bytes:
    """One cell per symbol type: the exemplar IN CONTEXT (3x its size) with a red box, and its real size in metres."""
    cells = []
    H, W = g.shape
    for k, r in enumerate(reps):
        x, y, w, h = [int(v) for v in st[r["members"][0]][:4]]
        m = int(1.2 * max(w, h))
        a, b, c, d = max(0, x - m), max(0, y - m), min(W, x + w + m), min(H, y + h + m)
        crop = cv2.cvtColor(g[b:d, a:c], cv2.COLOR_GRAY2BGR)
        cv2.rectangle(crop, (x - a - 2, y - b - 2), (x - a + w + 2, y - b + h + 2), (0, 0, 255), max(2, int(0.04 * max(w, h))))
        side = max(crop.shape[:2])
        sq = np.full((side, side, 3), 255, np.uint8)
        sq[(side - crop.shape[0]) // 2:(side - crop.shape[0]) // 2 + crop.shape[0],
           (side - crop.shape[1]) // 2:(side - crop.shape[1]) // 2 + crop.shape[1]] = crop
        sq = cv2.resize(sq, (240, 240), interpolation=cv2.INTER_AREA)
        cv2.rectangle(sq, (0, 0), (240, 26), (255, 255, 255), -1)
        cv2.putText(sq, f"{k + 1}: {max(w, h) / ppm:.1f}x{min(w, h) / ppm:.1f} m", (4, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 200), 2)
        cells.append(cv2.copyMakeBorder(sq, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(160, 160, 160)))
    while len(cells) % 5:
        cells.append(np.full_like(cells[0], 255))
    grid = np.vstack([np.hstack(cells[j:j + 5]) for j in range(0, len(cells), 5)])
    return cv2.imencode(".png", grid)[1].tobytes()


def _ask_names(png: bytes, n: int, llm) -> tuple[dict[int, str], float]:
    try:
        rep = llm.complete_vision(SYSTEM, f"{n} numbered cells.", png,
                                  max_tokens=2500 if getattr(llm, "no_think", True) else 9000)
    except Exception:  # noqa: BLE001
        return {}, 0.0
    m = re.search(r"\{.*\}", rep.text or "", re.S)
    out: dict[int, str] = {}
    try:
        for t in json.loads(m.group(0)).get("types", []) if m else []:
            nm = str(t.get("name", "")).lower().strip()
            if nm in NAMES:
                out[int(t["n"])] = nm
    except Exception:  # noqa: BLE001
        pass
    return out, float(getattr(rep, "usd", 0.0) or 0.0)


def _name_types(png: bytes, n: int, llm) -> tuple[dict[int, str], float, dict[int, str]]:
    """Two reviewers name the types independently (parallel). Returns (names, usd, agreement per type)."""
    llms = [L for L in (llm if isinstance(llm, (list, tuple)) else [llm]) if L is not None and hasattr(L, "complete_vision")]
    if not llms:
        return {}, 0.0, {}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(len(llms)) as ex:
        got = list(ex.map(lambda L: _ask_names(png, n, L), llms))
    usd = sum(u for _, u in got)
    names: dict[int, str] = {}
    agree: dict[int, str] = {}
    for k in range(1, n + 1):
        votes = [g[0].get(k) for g in got if g[0].get(k)]
        if not votes:
            continue
        names[k] = votes[-1]                      # the last reviewer is the strong one
        agree[k] = "both reviewers" if len(votes) >= 2 and len(set(votes)) == 1 else (
            "reviewers differ: " + " / ".join(votes) if len(votes) >= 2 else "one reviewer")
    return names, usd, agree


def _room_names(rooms: list, colour: list) -> dict[str, str]:
    """Hallway n (long, thin), '<Legend> n' (inside a legend colour zone), printed name, else Room n."""
    from shapely.geometry import Point, Polygon
    zones = [(Polygon(z.polygon).buffer(0), (z.label or "").strip().title()) for z in colour if len(z.polygon) >= 3 and z.label]
    count: dict[str, int] = {}
    out = {}
    for r in sorted(rooms, key=lambda e: (min(p[1] for p in e.polygon), min(p[0] for p in e.polygon))):
        poly = Polygon(r.polygon).buffer(0)
        mrr = poly.minimum_rotated_rectangle
        xs, ys = mrr.exterior.coords.xy
        sides = sorted({round(((xs[i + 1] - xs[i]) ** 2 + (ys[i + 1] - ys[i]) ** 2) ** 0.5, 1) for i in range(4)})
        aspect = sides[-1] / max(sides[0], 1e-6)
        base = None
        if r.label and r.label.upper() not in ("DORMITORY",) and not re.match(r"^\d", r.label):
            base = r.label.strip().title()
        if aspect >= 4.0 or (poly.area / max(mrr.area, 1) < 0.45):
            base = "Hallway"
        if base is None:
            c = poly.representative_point()
            base = next((nm for z, nm in zones if z.contains(c)), None)
        if base is None and r.label:
            base = r.label.strip().title()
        base = base or "Room"
        count[base] = count.get(base, 0) + 1
        out[r.id] = f"{base} {count[base]}"
    return out


def checklist(abs_path: str, sha: str, facts, llm=None, force: bool = False) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sha}-{VERSION}{'-named' if llm is not None else ''}.json"
    if f.exists() and not force:
        try:
            return json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            pass
    res = _checklist(abs_path, sha, facts, llm)
    f.write_text(json.dumps(res))
    return res


def _checklist(abs_path: str, sha: str, facts, llm) -> dict:
    from shapely.geometry import Point, Polygon
    from engine.scale import sheet_text as T
    t0 = time.perf_counter()
    prof = facts.extras.get("profile") or {}
    rooms = [e for e in facts.elements if e.kind == "room" and len(e.polygon) >= 3]
    colour = [e for e in facts.elements if e.kind == "zone"]
    deep = deep_info(prof, len(rooms))
    fp = next((e for e in facts.elements if e.kind == "footprint" and e.attrs.get("px_per_m")), None)
    out: dict[str, Any] = {"deep": deep, "rooms": [], "totals": [], "elements": [], "types": [], "cost": {"usd": 0.0, "ms": 0}}
    if fp is None:
        out["note"] = "no verified building outline at a known scale on this sheet"
        return out
    ppm = float(fp.attrs["px_per_m"])
    g = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
    if g is None:
        return out
    mask = np.zeros(g.shape, np.uint8)
    cv2.fillPoly(mask, [np.array(fp.polygon, np.int32)], 1)
    words = T.words(abs_path, sha)
    lab, st, keep = _components(g, mask, words, ppm)
    reps = _cluster(lab, st, keep)
    names, usd, agree_n = (_name_types(_contact_sheet(g, st, reps, ppm), len(reps), llm) if reps else ({}, 0.0, {}))
    out["naming"] = {str(k): v for k, v in agree_n.items()}
    rejected = []
    for k, r in enumerate(reps):                    # code verifies each name against the measured size
        nm = names.get(k + 1)
        if nm:
            x, y, w, h = [int(v) for v in st[r["members"][0]][:4]]
            if not plausible(nm, max(w, h) / ppm, min(w, h) / ppm) or agree_n.get(k + 1, "").startswith("reviewers differ") and \
                    not plausible(nm, max(w, h) / ppm, min(w, h) / ppm):
                rejected.append(f"type {k + 1} named '{nm}' but measures {max(w, h) / ppm:.1f}x{min(w, h) / ppm:.1f} m")
                names[k + 1] = f"symbol type {k + 1}"
    out["rejected_names"] = rejected
    room_polys = [(r, Polygon(r.polygon).buffer(0)) for r in rooms]
    rnames = _room_names(rooms, colour)
    per_room: dict[str, dict[str, int]] = {r.id: {} for r in rooms}
    by_name: dict[str, list[dict]] = {}
    for k, r in enumerate(reps):
        nm = names.get(k + 1) or f"symbol type {k + 1}"
        if nm == "other":
            continue
        x, y, w, h = [int(v) for v in st[r["members"][0]][:4]]
        hits = _ncc_hits(g, mask, [x, y, w, h])
        if hits:                                     # every template hit must ALSO have the exemplar's shape
            hits = [hc for hc in hits if _same_shape(g, mask, r["d"], hc, w, h)]
        n = len(r["members"])
        ncc = len(hits) if hits is not None else None
        ncc_ok = ncc is not None and n <= ncc <= 3.5 * n
        out["types"].append({"n": k + 1, "name": nm, "count": n, "ncc": ncc, "size_m": [round(w / ppm, 2), round(h / ppm, 2)]})
        by_name.setdefault(nm, []).append({"k": k, "rep": r, "w": w, "h": h, "n": n, "hits": hits if ncc_ok else None})
    for nm, cands in by_name.items():
        # the count of a symbol = all copies of its best exemplar (template matching finds copies touching walls that
        # the stroke clusters miss); clusters are the fallback; 2 exemplars agreeing within 10% -> green
        good = sorted([c for c in cands if c["hits"]], key=lambda c: -len(c["hits"]))
        if good:
            best = good[0]
            pts = best["hits"]
            agree = len(good) >= 2 and abs(len(good[1]["hits"]) - len(pts)) <= max(1, 0.1 * len(pts))
            w, h = best["w"], best["h"]
            boxes = [[cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2] for cx, cy in pts]
            note = (f"{len(pts)} copies of the exemplar found by template matching (8 orientations)"
                    + (f"; a second exemplar finds {len(good[1]['hits'])}" if len(good) >= 2 else "; one exemplar only"))
        else:
            best = max(cands, key=lambda c: c["n"])
            agree = False
            boxes = [[float(st[i][0]), float(st[i][1]), float(st[i][0] + st[i][2]), float(st[i][1] + st[i][3])]
                     for i in best["rep"]["members"]]
            note = f"{len(boxes)} identical shapes found by clustering (template matching not usable for this symbol)"
        ids = []
        for j, (bx0, by0, bx1, by1) in enumerate(boxes):
            eid = f"sym_{nm.replace(' ', '_')}_{j}"
            c = Point((bx0 + bx1) / 2, (by0 + by1) / 2)
            rid = next((rr.id for rr, pp in room_polys if pp.contains(c)), None)
            if rid:
                per_room[rid][nm] = per_room[rid].get(nm, 0) + 1
            out["elements"].append({"id": eid, "kind": nm, "label": f"{nm} ({rnames.get(rid, 'outside rooms')})",
                                    "polygon": [[bx0, by0], [bx1, by0], [bx1, by1], [bx0, by1]], "room_id": rid})
            ids.append(eid)
        out["totals"].append({"kind": nm, "label": LABEL.get(nm, nm.title() + ("s" if not nm.endswith("s") else "")),
                              "count": len(ids), "ids": ids, "tier": "green" if agree else "amber", "note": note})
    out["totals"].sort(key=lambda t: -t["count"])
    for r in rooms:
        out["rooms"].append({"id": r.id, "name": rnames.get(r.id, r.id), "kind": r.subtype or "room",
                             "area_m2": r.attrs.get("area_m2"), "polygon": [list(p) for p in r.polygon],
                             "counts": per_room.get(r.id, {})})
    out["rooms"].sort(key=lambda r: r["name"])
    out["cost"] = {"usd": round(usd, 5), "ms": int((time.perf_counter() - t0) * 1000),
                   "llm_calls": len(llm) if isinstance(llm, (list, tuple)) else (1 if llm is not None else 0)}
    return out
