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
VERSION = "v12"
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
    ink = ((g < 160) & (mask > 0)).astype(np.uint8)       # (local-contrast ink tried: pulls floor-fill edges in; worse)
    for w in words:
        a, b, c, d = [int(v) for v in w["box"]]
        ink[max(0, b - 1):d + 2, max(0, a - 1):c + 2] = 0
    thick = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    L = max(15, int(1.2 * ppm))                          # walls are LONG heavy strokes; a treadmill's heavy outline is short
    walls = cv2.morphologyEx(thick, cv2.MORPH_OPEN, np.ones((1, L), np.uint8)) | \
        cv2.morphologyEx(thick, cv2.MORPH_OPEN, np.ones((L, 1), np.uint8))
    walls = cv2.dilate(walls, np.ones((7, 7), np.uint8))
    thin = ink & (1 - cv2.dilate(thick, np.ones((3, 3), np.uint8)))
    thin = thin | (thick & (1 - walls))                  # heavy, short strokes are symbol outlines too
    n, lab, st, _ = cv2.connectedComponentsWithStats(thin, 8)
    lo, hi = max(8, int(0.25 * ppm)), int(3.0 * ppm)
    keep = [i for i in range(1, n) if lo <= max(st[i][2], st[i][3]) <= hi and min(st[i][2], st[i][3]) >= 0.12 * ppm
            and st[i][4] >= 20]
    return lab, st, keep, thin


def _desc(lab, st, i, S: int = 24, ink=None):
    x, y, w, h = st[i][:4]
    m = (lab[y:y + h, x:x + w] == i)
    if ink is not None:
        m = m & (ink[y:y + h, x:x + w] > 0)
    m = m.astype(np.uint8) * 255
    side = max(w, h)
    pad = np.zeros((side, side), np.uint8)
    pad[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = m
    d = cv2.resize(pad, (S, S), interpolation=cv2.INTER_AREA) > 40
    return cv2.dilate(d.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0, (max(w, h), min(w, h))


def _v8(d):
    return [np.rot90(d, k) for k in range(4)] + [np.rot90(np.fliplr(d), k) for k in range(4)]


def _cluster(lab, st, keep, ink=None, cap: int = 36) -> list[dict]:
    reps: list[dict] = []
    for i in keep:
        d, dims = _desc(lab, st, i, ink=ink)
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
            reps.append({"d": d, "dims": dims, "members": [i], "st": st})
    reps = [r for r in reps if len(r["members"]) >= 3]   # gym machines, sofas: a few per sheet
    reps.sort(key=lambda r: -len(r["members"]))
    return reps[:cap]


def _whole_symbols(thin: np.ndarray, lab_raw: np.ndarray, ppm: float) -> list[dict]:
    """Second discovery level: strokes within a few px grouped into ONE symbol (a treadmill, an elliptical, a bench and
    a lounge set are drawn from several separate strokes). Only groups made of >= 2 strokes; clustered like strokes."""
    grp = cv2.dilate(thin, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(grp, 8)
    lo, hi = int(0.4 * ppm), int(3.0 * ppm)
    keep = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if not (lo <= max(w, h) <= hi and min(w, h) >= 0.25 * ppm):
            continue
        sub = lab_raw[y:y + h, x:x + w][(lab[y:y + h, x:x + w] == i)]
        if len(np.unique(sub[sub > 0])) >= 2:
            keep.append(i)
    reps = _cluster(lab, st, keep, ink=thin, cap=14)
    for r in reps:
        r["grouped"] = True
    return reps


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


def _thumb(g: np.ndarray, box: list[float], size: int = 72) -> str:
    """Small picture of one symbol (the exemplar the count is built on), data URL for the checklist row."""
    import base64
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    m = int(0.25 * max(x1 - x0, y1 - y0)) + 2
    H, W = g.shape
    c = g[max(0, y0 - m):min(H, y1 + m), max(0, x0 - m):min(W, x1 + m)]
    if c.size == 0:
        return ""
    side = max(c.shape)
    sq = np.full((side, side), 255, np.uint8)
    sq[(side - c.shape[0]) // 2:(side - c.shape[0]) // 2 + c.shape[0], (side - c.shape[1]) // 2:(side - c.shape[1]) // 2 + c.shape[1]] = c
    sq = cv2.resize(sq, (size, size), interpolation=cv2.INTER_AREA)
    return "data:image/png;base64," + base64.b64encode(cv2.imencode(".png", sq)[1].tobytes()).decode()


def _add_printed(out: dict, words: list[dict], g: np.ndarray) -> None:
    """Tagged equipment (FP-1..5, CV-1..4 ...) and what the sheet prints (tables, slab types, pipe sizes)."""
    # tagged equipment (FP-1..5, CV-1..4 ...) and what the sheet prints (tables, slab types, pipe sizes)
    try:
        from engine import sheet_findings as SF
        from engine import sheet_lookup as SL
        defs = SL._sheet_defs(SL.rows(words))
        printed = SF.findings(words)
        out["printed"] = [{"title": f["title"], "text": f["text"], "kind": f["kind"]} for f in printed if f["kind"] != "note"]
        for f in printed:
            if f["kind"] != "equipment":
                continue
            for it in f["items"]:
                series = it["label"]
                m = re.match(r"(\d+)", str(it["value"]))
                if not m or not it.get("boxes"):
                    continue
                meaning, why = SL.expand(series, defs, numbered=True)
                label = (f"{meaning.capitalize()}s ({series})" if meaning and not meaning.endswith("s") else
                         f"{meaning.capitalize()} ({series})" if meaning else f"{series} tags")
                ids = []
                for j, b in enumerate(it["boxes"]):
                    eid = f"tag_{series}_{j}"
                    out["elements"].append({"id": eid, "kind": f"tag {series}", "label": f"{series} tag",
                                            "polygon": [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]], "room_id": None})
                    ids.append(eid)
                out["totals"].append({"kind": f"tag {series}", "label": label, "count": int(m.group(1)), "ids": ids,
                                      "tier": "amber", "note": f"equipment tags {it['value']} read on the sheet"
                                      + (f"; {why}" if why else ""), "thumb": _thumb(g, it["boxes"][0])})
    except Exception as e:  # noqa: BLE001
        out["printed_error"] = f"{type(e).__name__}: {e}"


def _contact_sheet(g: np.ndarray, st, reps: list[dict], ppm: float) -> bytes:
    """One cell per symbol type: the exemplar IN CONTEXT (3x its size) with a red box, and its real size in metres."""
    cells = []
    H, W = g.shape
    for k, r in enumerate(reps):
        x, y, w, h = [int(v) for v in r["st"][r["members"][0]][:4]]
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
    lab, st, keep, thin = _components(g, mask, words, ppm)
    reps = _cluster(lab, st, keep)
    reps += _whole_symbols(thin, lab, ppm)            # multi-stroke symbols: gym machines, lounge sets, sofas
    names, usd, agree_n = (_name_types(_contact_sheet(g, st, reps, ppm), len(reps), llm) if reps else ({}, 0.0, {}))
    out["naming"] = {str(k): v for k, v in agree_n.items()}
    unnamed = [k for k in range(len(reps)) if not names.get(k + 1)][:8]
    if unnamed and llm is not None:                   # second pass: each unnamed type alone, with more context
        strong = llm[-1] if isinstance(llm, (list, tuple)) else llm
        think0 = getattr(strong, "no_think", True)
        strong.no_think = True                       # one symbol: answer directly (thinking took minutes per call)
        for k in unnamed:
            png1 = _contact_sheet(g, st, [reps[k]], ppm)
            got, u1 = _ask_names(png1, 1, strong)
            usd += u1
            if got.get(1):
                names[k + 1] = got[1]
                agree_n[k + 1] = "named alone (second pass)"
        strong.no_think = think0
    rejected = []
    for k, r in enumerate(reps):                    # code verifies each name against the measured size
        nm = names.get(k + 1)
        if nm:
            x, y, w, h = [int(v) for v in r["st"][r["members"][0]][:4]]
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
        x, y, w, h = [int(v) for v in r["st"][r["members"][0]][:4]]
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
            S_ = best["rep"]["st"]
            boxes = [[float(S_[i][0]), float(S_[i][1]), float(S_[i][0] + S_[i][2]), float(S_[i][1] + S_[i][3])]
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
                              "count": len(ids), "ids": ids, "tier": "green" if agree else "amber", "note": note,
                              "thumb": _thumb(g, boxes[0]) if boxes else ""})
    _add_printed(out, words, g)
    # stair flights: the tread detector inside the outline (downscaled so a 10k px sheet stays fast)
    try:
        from engine.raster import stairs as ST
        k = min(1.0, 3000 / max(g.shape))
        col = cv2.imread(abs_path, cv2.IMREAD_COLOR)
        small = cv2.resize(col, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else col
        msk = cv2.resize(mask, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
        flights = [f for f in ST.detect(small)
                   if msk[int(np.clip(np.mean([q[1] for q in f["polygon"]]), 0, msk.shape[0] - 1)),
                          int(np.clip(np.mean([q[0] for q in f["polygon"]]), 0, msk.shape[1] - 1))]]
        ids = []
        for j, f in enumerate(flights):
            poly = [[q[0] / k, q[1] / k] for q in f["polygon"]]
            eid = f"stairs_{j}"
            out["elements"].append({"id": eid, "kind": "stair", "label": f"stair flight ({f['attrs']['treads']} treads)",
                                    "polygon": poly, "room_id": None})
            ids.append(eid)
        if ids:
            xs = [q[0] for q in out["elements"][-len(ids)]["polygon"]]; ys = [q[1] for q in out["elements"][-len(ids)]["polygon"]]
            out["totals"].append({"kind": "stair", "label": "Stair flights", "count": len(ids), "ids": ids, "tier": "amber",
                                  "note": "tread-line detector (evenly spaced treads) inside the building outline",
                                  "thumb": _thumb(g, [min(xs), min(ys), max(xs), max(ys)])})
    except Exception as e:  # noqa: BLE001
        out["stairs_error"] = f"{type(e).__name__}: {e}"
    out["totals"].sort(key=lambda t: -t["count"])
    # per wing / zone (legend colour zones are the wings of a colour-coded plan): where each element is
    zl = []
    if colour:
        W2, H2 = g.shape[1], g.shape[0]
        for z in colour:
            if len(z.polygon) < 3 or not z.label:
                continue
            zp = Polygon(z.polygon).buffer(0)
            if zp.area < 0.03 * Polygon(fp.polygon).buffer(0).area:
                continue
            c = zp.centroid
            where = ("top" if c.y < H2 * 0.4 else "bottom" if c.y > H2 * 0.6 else "middle")
            where += "" if where == "middle" else (" left" if c.x < W2 * 0.42 else " right" if c.x > W2 * 0.58 else "")
            cnt: dict[str, int] = {}
            for e in out["elements"]:
                xs = [q[0] for q in e["polygon"]]; ys = [q[1] for q in e["polygon"]]
                if zp.contains(Point(sum(xs) / len(xs), sum(ys) / len(ys))):
                    cnt[e["kind"]] = cnt.get(e["kind"], 0) + 1
            nice = " ".join(w if w[:1].isdigit() else w.capitalize() for w in z.label.strip().split())
            zl.append({"name": f"{nice} ({where})", "polygon": [list(q) for q in z.polygon], "counts": cnt})
    out["zones"] = zl
    out["summary"] = _summary(abs_path, sha, facts, words, fp, out)
    for r in rooms:
        out["rooms"].append({"id": r.id, "name": rnames.get(r.id, r.id), "kind": r.subtype or "room",
                             "area_m2": r.attrs.get("area_m2"), "polygon": [list(p) for p in r.polygon],
                             "counts": per_room.get(r.id, {})})
    out["rooms"].sort(key=lambda r: r["name"])
    out["cost"] = {"usd": round(usd, 5), "ms": int((time.perf_counter() - t0) * 1000),
                   "llm_calls": len(llm) if isinstance(llm, (list, tuple)) else (1 if llm is not None else 0)}
    return out


def door_swings(abs_path: str, g: np.ndarray, mask: np.ndarray, ppm: float) -> list[list[float]]:
    """Door swing arcs on a big sheet: the arc voter (engine/skeptic/voters/doors_arc.py) sizes doors relative to the
    drawing span, so it runs on ~30 m tiles of the building (door radius then in its range); results mapped back and
    de-duplicated (< 0.5 m apart). Boxes in original px."""
    import tempfile
    from engine.skeptic.voters import doors_arc as DA
    ys, xs = np.where(mask > 0)
    if not len(xs):
        return []
    X0, X1, Y0, Y1 = xs.min(), xs.max(), ys.min(), ys.max()
    T = int(30 * ppm)
    step = int(T * 0.85)
    out: list[list[float]] = []
    with tempfile.TemporaryDirectory() as td:
        for y0 in range(Y0, max(Y0 + 1, Y1 - int(0.15 * T)) + 1, step):
            for x0 in range(X0, max(X0 + 1, X1 - int(0.15 * T)) + 1, step):
                tile = g[y0:min(Y1, y0 + T), x0:min(X1, x0 + T)]
                if tile.size == 0 or (mask[y0:y0 + T, x0:x0 + T] > 0).mean() < 0.05:
                    continue
                f = f"{td}/t.png"
                cv2.imwrite(f, tile)
                try:
                    n, arcs, pp = DA.count(f)
                except Exception:  # noqa: BLE001
                    continue
                for a in arcs or []:
                    pts = pp.to_orig([tuple(a["c"]), tuple(a["ends"][0]), tuple(a["ends"][1])])
                    xs_ = [q[0] + x0 for q in pts]; ys_ = [q[1] + y0 for q in pts]
                    cx, cy = sum(xs_) / 3, sum(ys_) / 3
                    if not (0 <= int(cy) < mask.shape[0] and 0 <= int(cx) < mask.shape[1]) or not mask[int(cy), int(cx)]:
                        continue
                    if all((cx - (b[0] + b[2]) / 2) ** 2 + (cy - (b[1] + b[3]) / 2) ** 2 > (0.5 * ppm) ** 2 for b in out):
                        out.append([min(xs_), min(ys_), max(xs_), max(ys_)])
    return out


DISCIPLINE = {"A": "architectural", "S": "structural", "M": "mechanical / piping", "P": "plumbing", "FP": "fire protection",
              "E": "electrical", "C": "civil", "G": "general", "L": "landscape"}


TITLE_WORDS = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "GROUND", "BASEMENT", "FLOOR", "PLAN", "ROOF", "FOUNDATION",
               "SLAB", "PIPING", "ELECTRICAL", "MECHANICAL", "PLUMBING", "LEVEL", "SITE", "LIGHTING", "POWER", "ELEVATION", "SECTION"]


def _title_word(t: str) -> str:
    import difflib
    m = difflib.get_close_matches(t.upper(), TITLE_WORDS, n=1, cutoff=0.75)
    return m[0] if m else t


def _summary(abs_path: str, sha: str, facts, words: list[dict], fp, ck: dict) -> list[str]:
    """What this sheet is and what is on it, in plain sentences (all from code: title block, scale, outline, counts)."""
    from engine import layers as LY
    from engine.scale import sheet_scale as S2
    out = []
    titles = []
    for r in __import__("engine.sheet_lookup", fromlist=["rows"]).rows(words):
        t = r["text"].strip()
        if r.get("angle") == 90:                      # vertical title-block text: read in whichever order makes a title
            ws_ = sorted(r["words"], key=lambda w: -(w["box"][3] - w["box"][1]))
            kept = []
            for w in ws_:                             # OCR duplicates overlapping along the line: keep the longer word
                if all(min(w["box"][3], k["box"][3]) - max(w["box"][1], k["box"][1]) < 0.5 * (w["box"][3] - w["box"][1]) for k in kept):
                    kept.append(w)
            kept.sort(key=lambda w: w["box"][1])
            rev = " ".join(_title_word(w["text"]) for w in reversed(kept)).strip()
            if re.search(r"\b(PLAN|ELEVATION|SECTION|DETAILS?|SCHEDULE)\b\W*$", rev.upper()):
                t = rev
        if re.search(r"\bPLAN\b|\bELEVATION\b|\bSECTION\b|\bDETAILS?\b|\bSCHEDULE\b", t.upper()) and 2 <= len(t.split()) <= 7 \
                and "=" not in t and not re.search(r"\bSEE\b|\bNOTE\b", t.upper()):
            titles.append((r["h"], t))
    titles.sort(key=lambda x: (-bool(re.search(r"\b(PLAN|ELEVATION|SECTION)\W*$", x[1].upper())), -x[0]))
    title = titles[0][1].title() if titles else None
    if title:                                       # an OCR fragment first ('Ond Floor Plan'): the floor the sheet names
        from engine import sheet_lookup as _SL
        first = title.split()[0]
        if not _SL._english(first) and first.upper() not in TITLE_WORDS:
            fl = _SL.this_floor(_SL.rows(words))
            words_ = {0: "Basement", 1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}
            title = " ".join(([words_[fl]] if fl in words_ else []) + title.split()[1:])
    disc = LY.discipline(words)
    Wx = max((w["box"][2] for w in words), default=1)
    Hy = max((w["box"][3] for w in words), default=1)
    sid = next((w["text"] for w in sorted(words, key=lambda w: -((w["box"][3] - w["box"][1]) *
                (3 if w["box"][0] > 0.8 * Wx or w["box"][1] > 0.88 * Hy else 1)))
                if LY.SHEET_ID.match(w["text"].strip().upper()) and w.get("angle", 0) == 0), None)
    first = (title or "A drawing") + (f" (sheet {sid}" + (f", {DISCIPLINE.get(disc, disc)}" if disc else "") + ")" if sid else "")
    out.append(first + ".")
    try:
        st = S2.sheet_state(abs_path, sha)
        w = st["cons"]["winner"]
        if w:
            lab = next((c["label"] for c in w["items"] if c["family"] == "ratio"), None)
            out.append(f"Scale {lab + ' = ' if lab else ''}{w['ppm']:.1f} px/m, read from {', '.join(w['families'])} "
                       f"({int(st['conf'] * 100)}% sure).")
    except Exception:  # noqa: BLE001
        pass
    if fp is not None and fp.attrs.get("bbox_m"):
        out.append(f"Building about {fp.attrs['bbox_m'][0]:.1f} x {fp.attrs['bbox_m'][1]:.1f} m, "
                   f"{fp.attrs.get('area_m2', 0):.0f} m² inside its outline; {len(ck.get('rooms', []))} enclosed spaces.")
    top = [t for t in ck.get("totals", []) if not t["label"].startswith("Symbol Type")][:6]
    if top:
        out.append("On it: " + ", ".join(f"{t['count']} {t['label'].lower()}" for t in top) + ".")
    for f in ck.get("printed", [])[:2]:
        out.append(f"{f['title']}: {f['text'][:160]}")
    return out


# ---------------------------------------------------------------- the chatbot reads the stored deep read
SYN = {"washbasin": "sink", "basin": "sink", "lavatory": "sink", "wc": "toilet", "loo": "toilet", "nightstand": "side table",
       "bedside": "side table", "wardrobe": "closet", "cupboard": "closet", "couch": "sofa", "armchair": "lounge chair",
       "television": "tv", "staircase": "stair", "stairway": "stair", "flight": "stair", "step": "stair", "treadmill": "gym equipment",
       "gym": "gym equipment", "refrigerator": "fridge", "tub": "bathtub", "bath": "bathtub"}


def cached(sha: str) -> Optional[dict]:
    fs = sorted(CACHE.glob(f"{sha}-{VERSION}*.json"), key=lambda f: -f.stat().st_mtime)
    for f in fs:
        try:
            return json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            continue
    return None


def answer(sha: str, question: str):
    """'how many beds / sinks / stairs ...' from the deep read of this drawing (each count with its boxes)."""
    m = re.search(r"\bhow\s+many\s+(.+?)(?:\s+(?:are|is|do|does|in|on|there|here|shown|drawn)\b|\?|$)|\bnumber\s+of\s+(.+?)(?:\?|$)",
                  question, re.I)
    if not m:
        return None
    ck = cached(sha)
    if not ck or not ck.get("totals"):
        return None
    noun = (m.group(1) or m.group(2) or "").lower().strip()
    words = [w.rstrip("s") if len(w) > 3 else w for w in re.findall(r"[a-z]+", noun)]
    want = None
    for w in words[::-1]:
        w = SYN.get(w, w)
        hits = []
        for t in ck["totals"]:
            k = t["kind"]
            lw = [x.rstrip("s") for x in re.findall(r"[a-z]+", t["label"].lower())]
            if k == w or k.split()[-1] == w or (len(w) >= 4 and (k.startswith(w) or w.startswith(k))) or w in lw:
                hits.append(t)
        if hits:
            exact = [t for t in hits if " ".join(words) in t["label"].lower()]
            hits = exact or hits
            if len(hits) == 1:
                want = hits[0]
            else:                                    # a class word ('valves'): every matching type, summed
                want = {"kind": w, "label": f"{w}s", "count": sum(t["count"] for t in hits), "parts": True,
                        "ids": [i for t in hits for i in t["ids"]], "tier": "amber",
                        "note": "; ".join(f"{t['count']} {t['label'].lower()}" for t in hits)}
            break
    if want is None and re.search(r"\brooms?\b", noun) and ck.get("rooms"):
        return {"value": len(ck["rooms"]), "label": "rooms", "ids": [r["id"] for r in ck["rooms"]], "tier": "amber",
                "note": "enclosed spaces inside the building outline, each named", "polys": [r["polygon"] for r in ck["rooms"]]}
    if want is None:
        return None
    by = {e["id"]: e for e in ck.get("elements", [])}
    per_zone = {z["name"]: z["counts"].get(want["kind"], 0) for z in ck.get("zones", []) if z["counts"].get(want["kind"])}
    return {"value": want["count"], "label": want["label"].lower(), "ids": want["ids"], "tier": want["tier"], "parts": want.get("parts", False),
            "note": want.get("note", ""), "polys": [by[i]["polygon"] for i in want["ids"] if i in by], "zones": per_zone}


def missing_note(sha: str, question: str) -> Optional[str]:
    """When the deep read exists but holds nothing of the asked kind, say so (instead of a detector disclaimer)."""
    ck = cached(sha)
    m = re.search(r"\bhow\s+many\s+([a-z]+)", question, re.I)
    if not ck or not m:
        return None
    kinds = ", ".join(t["label"].lower() for t in ck.get("totals", [])[:6]) or "no repeated symbols"
    return (f"the deep read of this sheet found no {m.group(1).lower()} symbols (it found: {kinds}); "
            "if they are drawn on another sheet of the set, upload that sheet")


def enrich(abs_path: str, sha: str, facts, ck: dict) -> dict:
    """Add equipment tags, printed tables and the sheet summary to an existing deep read (no symbol re-discovery)."""
    from engine.scale import sheet_text as T
    g = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
    words = T.words(abs_path, sha)
    if not any(t["kind"].startswith("tag ") for t in ck.get("totals", [])):
        _add_printed(ck, words, g)
        ck["totals"].sort(key=lambda t: -t["count"])
    fp = next((e for e in facts.elements if e.kind == "footprint" and e.attrs.get("px_per_m")), None)
    rooms = [e for e in facts.elements if e.kind == "room" and len(e.polygon) >= 3]
    if rooms and not ck.get("rooms"):                 # the read started before the rooms were there: rebuild the list
        from shapely.geometry import Point, Polygon
        rn = _room_names(rooms, [e for e in facts.elements if e.kind == "zone"])
        polys = [(r, Polygon(r.polygon).buffer(0)) for r in rooms]
        counts: dict[str, dict[str, int]] = {r.id: {} for r in rooms}
        for e in ck.get("elements", []):
            xs = [q[0] for q in e["polygon"]]; ys = [q[1] for q in e["polygon"]]
            c = Point(sum(xs) / len(xs), sum(ys) / len(ys))
            rid = next((r.id for r, pp in polys if pp.contains(c)), None)
            if rid:
                e["room_id"] = rid
                counts[rid][e["kind"]] = counts[rid].get(e["kind"], 0) + 1
        ck["rooms"] = sorted([{"id": r.id, "name": rn.get(r.id, r.id), "kind": r.subtype or "room",
                               "area_m2": r.attrs.get("area_m2"), "polygon": [list(q) for q in r.polygon],
                               "counts": counts[r.id]} for r in rooms], key=lambda r: r["name"])
    ck["summary"] = _summary(abs_path, sha, facts, words, fp, ck)
    return ck
