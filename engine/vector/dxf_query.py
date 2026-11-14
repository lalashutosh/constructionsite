"""Intent -> numbers on a Swiss Dwellings DXF. Each function returns a list of DxfAnswer (one per voter).

Counting/area conventions are documented in dxf.py; fixture classification thresholds were fitted on the DEV split
only (see docs/handoff/vector.md) and are the only fitted part.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import LineString, Point, Polygon

from . import dxf as X

INTENTS = {"apartments", "doors", "windows", "toilets", "washbasins", "bathtubs", "showers", "room_labelled",
           "room_area_labelled", "total_net_area", "apartment_net_area", "room_area"}

# fixture classification thresholds (fit on DEV only; (nC circles, nP polygons, L long side m, S short side m))
FX = dict(wc_lo=0.4, wc_hi=1.0, wc_s_lo=0.2, wc_s_hi=0.7, tub_lo=1.4, tub_s_hi=1.0, sh_lo=0.75, sh_hi=1.5,
          sh_s_lo=0.75, basin_hi=1.1, mid_lo=1.15, mid_hi=1.4, mid_s=0.7, q4_basin_hi=1.3)


def classify_fixture(c: dict, p: dict = FX) -> Optional[str]:
    nC, nP, L, S = c["nC"], c["nP"], c["L"], c["S"]
    if nC == 0 and nP == 2 and p["wc_lo"] <= L <= p["wc_hi"] and p["wc_s_lo"] <= S <= p["wc_s_hi"]:
        return "toilets"
    if nC == 1 and nP == 2:
        mid = p["mid_lo"] <= L <= p["mid_hi"] and S <= p["mid_s"]
        if p["sh_lo"] <= L <= p["sh_hi"] and S >= p["sh_s_lo"]:
            return "showers"
        if L >= p["tub_lo"] and S <= p["tub_s_hi"] and not mid:
            return "bathtubs"
        if L <= p["basin_hi"] or mid:
            return "washbasins"
    if nP == 4 and nC in (1, 2):
        return "washbasins" if L <= p["q4_basin_hi"] else "bathtubs"
    return None


@dataclass
class DxfAnswer:
    voter: str                 # dxf_exact | dxf_alt
    value: float
    unit: str
    note: str
    elements: list = field(default_factory=list)   # (id, kind, polygon points, label, attrs)


def label_from_question(plan: X.DxfPlan, question: str, params: dict) -> Optional[str]:
    """Room label named in the question: prefer a name that actually occurs in the plan (longest match), because
    quote characters collide with apostrophes (Cage d'escalier)."""
    names = sorted({r.name for r in plan.rooms if r.name}, key=len, reverse=True)
    # the label sits between the first and the LAST quote mark (ASCII apostrophes occur inside names: Cage d'escalier)
    m = re.search(r"[«“„‘'\"]\s*(.+?)\s*[»”“’'\"]", question[::1], re.S)
    m2 = re.search(r"[«“„‘'\"]\s*(.+)\s*[»”“’'\"]", question, re.S)
    for cand in ([m2.group(1)] if m2 else []) + ([m.group(1)] if m else []):
        for n in names:
            if n.casefold() == cand.strip().casefold():
                return n
    q = question.casefold()
    for n in names:
        if re.search(r"(?<!\w)" + re.escape(n.casefold()) + r"(?!\w)", q):
            return n
    return params.get("label")


def _el(id_, kind, poly, label=None, **attrs):
    pts = [(float(x), float(y)) for x, y in (poly.exterior.coords if hasattr(poly, "exterior") else poly)]
    return (id_, kind, pts, label, attrs)


def answer(path: str, intent: str, question: str, params: Optional[dict] = None) -> list[DxfAnswer]:
    params = params or {}
    plan = X.load(path)
    k2 = plan.scale ** 2
    out: list[DxfAnswer] = []
    unit_note = plan.units_note

    if intent == "doors":
        frames = plan.door_frames
        out.append(DxfAnswer("dxf_exact", float(len(frames)), "count",
                             "5-point DOOR frames (1 per opening; stacked arcs / 2nd leaf of a double door not counted)",
                             [_el(f"dxf:door#{i}", "door", f) for i, f in enumerate(frames)]))
        # alt voter: frames that a swing arc (hinge or open end) actually touches (arc/leaf geometry)
        import math as _m
        pts_arc = []
        for (c, r, a0, a1) in plan.door_arcs:
            s, e = _m.radians(a0), _m.radians(a1)
            pts_arc += [c, (c[0] + r * _m.cos(s), c[1] + r * _m.sin(s)), (c[0] + r * _m.cos(e), c[1] + r * _m.sin(e))]
        touched = 0
        for f in plan.door_frames:
            if any(min(((x - px) ** 2 + (y - py) ** 2) ** .5 for x, y in f) < 0.03 for px, py in pts_arc):
                touched += 1
        out.append(DxfAnswer("dxf_alt", float(touched), "count", "5-point frames touched by a swing arc (arc geometry)"))
    elif intent == "windows":
        w = plan.window_polys
        out.append(DxfAnswer("dxf_exact", float(len(w)), "count", "4-point WINDOW polylines (2-point ones are reveal lines)",
                             [_el(f"dxf:window#{i}", "window", p) for i, p in enumerate(w)]))
        n_all = plan.layers.get("WINDOW", 0)
        if n_all:
            out.append(DxfAnswer("dxf_alt", float(round(n_all / 3)), "count", "all WINDOW entities / 3 (frame + 2 reveal lines)"))
    elif intent == "apartments":
        us = [u for u in plan.units if u.label]
        out.append(DxfAnswer("dxf_exact", float(len(us)), "count",
                             "UNIT_OUTLINE polygons carrying an apartment label (App./Whg. X)",
                             [_el(u.eid, "room", u.poly, u.raw_label, subtype="apartment") for u in us]))
        labels = {u.label for u in us}
        out.append(DxfAnswer("dxf_alt", float(len(labels)), "count", "distinct apartment letters in ROOM_TEXT"))
    elif intent in ("toilets", "washbasins", "bathtubs", "showers"):
        sel = [c for c in plan.fixtures if classify_fixture(c) == intent]
        out.append(DxfAnswer("dxf_exact", float(len(sel)), "count",
                             f"FIXTURE clusters classified by (circles, polygons, long/short side); thresholds fitted on DEV; "
                             "exact source, single voter",
                             [_el(f"dxf:fixture#{i}", "fixture", Point(c["c"]).buffer(max(c["S"], 0.2) / 2).exterior.coords, None,
                                  subtype=intent) for i, c in enumerate(sel)]))
    elif intent in ("room_labelled", "room_area_labelled"):
        lab = label_from_question(plan, question, params)
        if not lab:
            return []
        rs = [r for r in plan.rooms if (r.name or "") == lab]
        els = [_el(r.eid, "room", r.poly if not r.poly.geom_type == "MultiPolygon" else max(r.poly.geoms, key=lambda g: g.area),
                   f"{lab} {r.id}") for r in rs]
        if intent == "room_labelled":
            out.append(DxfAnswer("dxf_exact", float(len(rs)), "count", f"numbered ROOM_OUTLINE polygons named '{lab}'", els))
            out.append(DxfAnswer("dxf_alt", float(sum(1 for t, _, _ in plan.texts if t == lab)), "count",
                                 "ROOM_TEXT labels equal to the name"))
        else:
            out.append(DxfAnswer("dxf_exact", sum(r.area for r in rs) * k2, "m2",
                                 f"sum of polygon areas of rooms named '{lab}' ({unit_note})", els))
            lab_areas = [r.area_label for r in rs]
            if rs and all(a is not None for a in lab_areas):
                out.append(DxfAnswer("dxf_alt", float(sum(lab_areas)), "m2", "sum of printed area labels"))
    elif intent == "room_area":
        num = params.get("room")
        if not num:
            m = re.search(r"\b([A-Z]{0,2}\d+\.\d+)\b", question)
            num = m.group(1) if m else None
        rs = [r for r in plan.rooms if r.id == num]
        if not rs:
            return []
        # duplicate numbers: the ring/inner pair is resolved in dxf.load (innermost owns the text)
        r = rs[0]
        out.append(DxfAnswer("dxf_exact", r.area * k2, "m2", f"polygon area of room {num} ({unit_note})",
                             [_el(r.eid, "room", r.poly if r.poly.geom_type == "Polygon" else max(r.poly.geoms, key=lambda g: g.area), r.id)]))
        if r.area_label is not None:
            out.append(DxfAnswer("dxf_alt", float(r.area_label), "m2", "printed area label"))
    elif intent == "total_net_area":
        rs = [r for r in plan.rooms if not r.outdoor]
        out.append(DxfAnswer("dxf_exact", sum(r.area for r in rs) * k2, "m2",
                             f"sum of numbered rooms excluding balconies/loggias/terraces ({unit_note}); "
                             "unnamed shaft-like rooms are included (not detectable from the drawing)",
                             [_el(r.eid, "room", r.poly if r.poly.geom_type == "Polygon" else max(r.poly.geoms, key=lambda g: g.area), r.id)
                              for r in rs]))
        if rs and all(r.area_label is not None for r in rs):
            out.append(DxfAnswer("dxf_alt", float(sum(r.area_label for r in rs)), "m2", "sum of printed area labels"))
    elif intent == "apartment_net_area":
        let = (params.get("letter") or "").upper()
        if not let:
            m = re.search(r"(?:apartment|appartamento|appartement|wohnung|whg\.?|app\.?)\s+([A-Z])\b", question, re.I)
            let = m.group(1).upper() if m else ""
        ui = [i for i, u in enumerate(plan.units) if u.label == let]
        if not ui:
            return []
        rs = [r for r in plan.rooms if r.unit in ui and not r.outdoor]
        out.append(DxfAnswer("dxf_exact", sum(r.area for r in rs) * k2, "m2",
                             f"sum of rooms inside UNIT_OUTLINE of apartment {let}, outdoor rooms excluded ({unit_note})",
                             [_el(r.eid, "room", r.poly if r.poly.geom_type == "Polygon" else max(r.poly.geoms, key=lambda g: g.area), r.id)
                              for r in rs]))
        if rs and all(r.area_label is not None for r in rs):
            out.append(DxfAnswer("dxf_alt", float(sum(r.area_label for r in rs)), "m2", "sum of printed area labels"))
    return out
