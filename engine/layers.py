"""Layers of a drawing, like the systems of a body: envelope (skin), walls (skeleton), furniture/fixtures (organs),
piping (veins), electrical (nerves). Each layer is geometry in ORIGINAL image px for the viewer to toggle and colour.

- envelope: the verified building outline (engine/outline.py / legend-zone union);
- walls: the 3D model's wall rings;
- furniture: the deep-read symbol nodes (engine/symbols.py cache) when that read has run;
- piping / electrical: on an MEP sheet (sheet id M-/P-/FP- = piping, E- = electrical) the discipline's black linework
  drawn over the screened (grey) building, inside the outline, text removed, as simplified polylines.
A layer that a sheet does not carry is returned empty with a reason, never invented."""
from __future__ import annotations

import json
import re
from typing import Any

import cv2
import numpy as np

SHEET_ID = re.compile(r"^(FP|[A-Z])-?\d{2,3}[A-Z]?$")


def discipline(words: list[dict]) -> str | None:
    """'M-101A' in the title block -> 'M'. The largest such id wins (the sheet number is printed big)."""
    if not words:
        return None
    W = max(w["box"][2] for w in words)
    H = max(w["box"][3] for w in words)
    best = None
    for w in words:
        t = w["text"].strip().upper()
        m = SHEET_ID.match(t)
        if not m or w.get("angle", 0) != 0:
            continue
        in_tb = w["box"][0] > 0.8 * W or w["box"][1] > 0.88 * H      # the title block: right strip / bottom band
        sc = (w["box"][3] - w["box"][1]) * (3 if in_tb else 1)
        if best is None or sc > best[0]:
            best = (sc, m.group(1))
    return best[1] if best else None


def _linework(abs_path: str, facts, words: list[dict], max_lines: int = 2500) -> list[list[list[float]]]:
    g = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
    fp = next((e for e in facts.elements if e.kind == "footprint" and e.attrs.get("source") == "outline"), None)
    if g is None or fp is None:
        return []
    mask = np.zeros(g.shape, np.uint8)
    cv2.fillPoly(mask, [np.array(fp.polygon, np.int32)], 1)
    mask = cv2.dilate(mask, np.ones((25, 25), np.uint8))              # pipes leave through the walls
    dark = ((g < 110) & (mask > 0)).astype(np.uint8)
    for w in words:
        a, b, c, d = [int(v) for v in w["box"]]
        dark[max(0, b - 2):d + 3, max(0, a - 2):c + 3] = 0
    s = min(1.0, 3000 / max(g.shape))
    small = (cv2.resize(dark * 255, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) > 60).astype(np.uint8)
    lines = cv2.morphologyEx(small, cv2.MORPH_OPEN, np.ones((1, 9), np.uint8)) | \
        cv2.morphologyEx(small, cv2.MORPH_OPEN, np.ones((9, 1), np.uint8))       # straight runs, not symbols
    cs, _ = cv2.findContours(lines, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in sorted(cs, key=lambda c: -cv2.arcLength(c, False))[:max_lines]:
        if cv2.arcLength(c, False) < 20:
            continue
        ap = cv2.approxPolyDP(c, 1.5, False).reshape(-1, 2)
        out.append([[float(x / s), float(y / s)] for x, y in ap])
    return out


WET = ("sink", "toilet", "shower", "bathtub", "washer", "kitchen counter")
# European rules the estimate follows (values to verify against the national annex; this is an estimate, not a design)
LU_EN806 = {"sink": 1, "toilet": 1, "shower": 2, "bathtub": 4, "washer": 2, "kitchen counter": 2}     # EN 806-3 loading units
DU_EN12056 = {"sink": 0.5, "toilet": 2.0, "shower": 0.6, "bathtub": 0.8, "washer": 0.8, "kitchen counter": 0.8}  # l/s, System I
LUX_EN12464 = [(r"hall|corridor|circulation|stair", 100), (r"bath|wc|toilet|shower", 200), (r"gym|fitness|sport", 300),
               (r"office|common|lounge|study|class|meeting", 500), (r"kitchen", 300)]   # maintained illuminance, lx
LUMENS, UF, MF = 1500.0, 0.6, 0.8       # LED fitting, utilisation factor, maintenance factor (lumen method)


def _mst(pts: list[tuple[float, float]]) -> list[tuple[int, int]]:
    """Minimum spanning tree (Prim) over points: the shortest network joining them all."""
    if len(pts) < 2:
        return []
    import math
    inside, edges = {0}, []
    while len(inside) < len(pts):
        best = None
        for i in inside:
            for j in range(len(pts)):
                if j in inside:
                    continue
                d = math.dist(pts[i], pts[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        edges.append((best[1], best[2]))
        inside.add(best[2])
    return edges


def estimate_services(facts, ck: dict | None, ppm: float) -> dict[str, Any]:
    """ESTIMATED services for a sheet that has no MEP drawing (tag: defaulted). Pipes: every wet fixture of the deep read
    branches to its wing's main; mains join the wings (minimum spanning tree), +30% routing allowance. Electrical: per
    room 1 light / 10 m2 and 1 socket / 4 m of wall; circuits run room to room (minimum spanning tree) from the room
    nearest the building centre (panel). Geometry in image px; quantities in metres / pieces."""
    import math
    from shapely.geometry import Point, Polygon
    out: dict[str, Any] = {"piping": [], "electrical": [], "quantities": {}}
    els = (ck or {}).get("elements", [])
    zones = [(Polygon(z["polygon"]).buffer(0), z["name"]) for z in (ck or {}).get("zones", []) if len(z.get("polygon", [])) >= 3]
    wet = []
    for e in els:
        if e["kind"] in WET:
            xs = [q[0] for q in e["polygon"]]; ys = [q[1] for q in e["polygon"]]
            wet.append((sum(xs) / len(xs), sum(ys) / len(ys)))
    if wet:
        groups: dict[str, list] = {}
        for c in wet:
            z = next((nm for zp, nm in zones if zp.contains(Point(c))), "building")
            groups.setdefault(z, []).append(c)
        mains = []
        total = 0.0
        for nm, pts in groups.items():
            cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
            mains.append((cx, cy))
            for p in pts:                                   # branch: fixture -> wing main (L-shaped run)
                out["piping"].append([[p[0], p[1]], [p[0], cy], [cx, cy]])
                total += abs(p[1] - cy) + abs(p[0] - cx)
        for i, j in _mst(mains):
            a, b = mains[i], mains[j]
            out["piping"].append([[a[0], a[1]], [b[0], a[1]], [b[0], b[1]]])
            total += abs(a[0] - b[0]) + abs(a[1] - b[1])
        out["quantities"]["pipe_m"] = {"value": round(total / ppm * 1.3, 1), "unit": "m", "tag": "defaulted",
                                       "basis": f"{len(wet)} wet fixtures from the deep read, branches to {len(mains)} wing mains, "
                                                "orthogonal runs + 30% routing allowance (estimate, no plumbing sheet)"}
        out["quantities"]["wet_points"] = {"value": len(wet), "unit": "pcs", "tag": "drawn", "basis": "wet fixtures counted"}
        kinds = [e["kind"] for e in els if e["kind"] in WET]
        lu = sum(LU_EN806.get(k, 1) for k in kinds)
        du = sum(DU_EN12056.get(k, 0.5) for k in kinds)
        K = 0.7                              # EN 12056-2 frequency factor: frequent use (dormitory, hotel, school)
        q = K * math.sqrt(du)
        out["quantities"]["loading_units"] = {"value": lu, "unit": "LU", "tag": "defaulted",
                                              "basis": "EN 806-3 loading units: washbasin 1, WC cistern 1, shower 2, bath 4, "
                                                       "kitchen sink 2 (supply pipe sizing starts from this total)"}
        out["quantities"]["waste_flow_ls"] = {"value": round(q, 2), "unit": "l/s", "tag": "defaulted",
                                              "basis": f"EN 12056-2: Qww = K x sqrt(sum DU) = 0.7 x sqrt({du:.1f}) "
                                                       "(discharge units: WC 2.0, washbasin 0.5, shower 0.6, bath 0.8; "
                                                       "K = 0.7 frequent use)"}
    rooms = [e for e in facts.elements if e.kind == "room" and len(e.polygon) >= 3]
    if rooms:
        import re as _re
        cents, lights, sockets = [], 0, 0
        for r in rooms:
            pg = Polygon(r.polygon).buffer(0)
            a = float(r.attrs.get("area_m2") or pg.area / ppm ** 2)
            per = pg.exterior.length / ppm
            name = f"{r.label or ''} {r.subtype or ''}".lower()
            E = next((lx for rx, lx in LUX_EN12464 if _re.search(rx, name)), 200)
            lights += max(1, math.ceil(E * a / (LUMENS * UF * MF)))           # lumen method
            sockets += 2 if a <= 8 else 3 if a <= 12 else 4 if a <= 20 else 5 + int((a - 20) // 10)
            c = pg.representative_point()
            cents.append((c.x, c.y))
        bc = (sum(c[0] for c in cents) / len(cents), sum(c[1] for c in cents) / len(cents))
        panel = min(range(len(cents)), key=lambda i: math.dist(cents[i], bc))
        order = [panel] + [i for i in range(len(cents)) if i != panel]
        pts = [cents[i] for i in order]
        cable = 0.0
        for i, j in _mst(pts):
            a, b = pts[i], pts[j]
            out["electrical"].append([[a[0], a[1]], [b[0], a[1]], [b[0], b[1]]])
            cable += abs(a[0] - b[0]) + abs(a[1] - b[1])
        out["quantities"].update({
            "cable_m": {"value": round(cable / ppm * 1.3, 1), "unit": "m", "tag": "defaulted",
                        "basis": f"room-to-room circuit tree from a panel near the building centre over {len(rooms)} rooms, "
                                 "+30% routing (circuits per HD 60364 / IEC 60364; cross-sections not sized here)"},
            "lights": {"value": lights, "unit": "pcs", "tag": "defaulted",
                       "basis": "lumen method N = E x A / (lumens x UF x MF) per room, E from EN 12464-1 by room type "
                                "(corridors 100 lx, rooms / bathrooms 200, gym 300, common / study 500), 1500 lm LED, "
                                "UF 0.6, MF 0.8"},
            "sockets": {"value": sockets, "unit": "pcs", "tag": "defaulted",
                        "basis": "planning rule in the style of DIN 18015-2 (room <= 8 m2: 2, <= 12: 3, <= 20: 4, "
                                 "then +1 per 10 m2); check the national standard"}})
    return out


def layers(abs_path: str, facts, geo: dict) -> dict[str, Any]:
    from engine.scale import sheet_text as T
    sha = facts.provenance.sha256
    words = T.words(abs_path, sha) if sha else []
    out: dict[str, Any] = {"envelope": [], "walls": [w["outer"] for w in geo.get("walls", [])], "furniture": [],
                           "piping": [], "electrical": [], "notes": {}}
    fp = next((e for e in facts.elements if e.kind == "footprint" and e.attrs.get("source") == "outline"), None)
    if fp is not None:
        out["envelope"] = [[list(map(float, p)) for p in fp.polygon]]
    try:                                                  # furniture nodes from a finished deep read (cached)
        from engine import symbols
        for f in sorted(symbols.CACHE.glob(f"{sha}-{symbols.VERSION}*.json")):
            ck = json.loads(f.read_text())
            out["furniture"] = [{"id": e["id"], "kind": e["kind"], "label": e.get("label"), "polygon": e["polygon"]}
                                for e in ck.get("elements", [])]
            break
        if not out["furniture"]:
            out["notes"]["furniture"] = "run the deep read (checklist) to place every furniture symbol"
    except Exception:  # noqa: BLE001
        pass
    disc = discipline(words)
    out["discipline"] = disc
    if disc in ("M", "P", "FP"):
        out["piping"] = _linework(abs_path, facts, words)
        out["notes"]["electrical"] = "no electrical sheet in this set (this is a piping / mechanical sheet)"
    elif disc == "E":
        out["electrical"] = _linework(abs_path, facts, words)
        out["notes"]["piping"] = "no piping sheet in this set (this is an electrical sheet)"
    else:                     # no MEP sheet: ESTIMATED services from the deep read + rooms (clearly marked)
        ck = None
        try:
            from engine import symbols
            ck = symbols.cached(sha)
        except Exception:  # noqa: BLE001
            pass
        ppm = float(fp.attrs.get("px_per_m")) if fp is not None and fp.attrs.get("px_per_m") else None
        if ppm:
            est = estimate_services(facts, ck, ppm)
            out["piping"], out["electrical"] = est["piping"], est["electrical"]
            out["estimated"] = True
            out["quantities"] = est["quantities"]
            out["notes"]["piping"] = "ESTIMATED from the wet fixtures (no plumbing sheet in this set)"
            out["notes"]["electrical"] = "ESTIMATED from the rooms (no electrical sheet in this set)"
        else:
            msg = f"not on this sheet ({'sheet ' + disc + '-' if disc else 'an architectural / structural sheet'}); upload the MEP sheet of the same floor"
            out["notes"]["piping"] = msg
            out["notes"]["electrical"] = msg
    return out
