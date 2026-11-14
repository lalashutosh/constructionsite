"""IFC without a sibling image: a plan view of one storey, drawn from the model's own meshes (exact, no vision).

Storey = the one with the most walls directly contained in it (the same containment rule as engine.vector.ifc counts).
Each element's footprint = union of its mesh triangles projected onto the floor plane (ifcopenshell.geom, world
coordinates, metres). Walls (+ columns) become the 3D walls; IfcSpace footprints are the rooms; doors, windows and
sanitary terminals are their projected outlines.

`render(path, out, max_px)` writes the PNG; `geometry(path, max_px)` returns engine.geometry3d.model()-shaped data in
that pixel space, labelled `ifc-render` (proof evidence is not pinned onto it).
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from engine.vector import ifc as I

PAD = 24
WALL_CLASSES = ("IfcWall", "IfcColumn", "IfcCurtainWall")
FIXTURE_CLASSES = ("IfcSanitaryTerminal", "IfcFlowTerminal", "IfcFurnishingElement")


def _footprint(idx: "I.IfcIndex", el):
    mm = idx.mesh(el)
    if mm is None:
        return None
    v, f = mm
    if len(f) == 0:
        return None
    tri = v[f][:, :, :2]                                          # (M, 3, 2) projected triangles
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    area2 = np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))
    keep = tri[area2 > 1e-8]                                      # vertical faces project to slivers
    if len(keep) == 0:
        return None
    g = unary_union([Polygon(t) for t in keep]).buffer(0)
    return g if not g.is_empty else None


def _hull(idx: "I.IfcIndex", el):
    """Cheap footprint for MEP parts (pipes, fittings): convex hull of the projected vertices."""
    mm = idx.mesh(el)
    if mm is None or len(mm[0]) < 3:
        return None
    from shapely.geometry import MultiPoint
    g = MultiPoint([tuple(p) for p in mm[0][:, :2]]).convex_hull
    return g if g.geom_type == "Polygon" else g.buffer(0.02)


def _storey(idx: "I.IfcIndex"):
    def n_walls(s):
        return sum(1 for e in idx.direct.get(s.id(), []) if e.is_a("IfcWall"))
    ranked = sorted(idx.storeys, key=lambda s: (n_walls(s), len(idx.spaces.get(s.id(), [])),
                                                len(idx.direct.get(s.id(), []))), reverse=True)
    return ranked[0] if ranked else None


MEP_CAP = 600    # pipes/fittings drawn per storey at most (meshing ~20 ms each); the note says when it is capped


@lru_cache(maxsize=4)
def plan(path: str) -> dict:
    """Footprints (metres, model XY) for the chosen storey. Cached per file: meshing is the slow part."""
    idx = I.load(path)
    st = _storey(idx)
    if st is None or not (idx.direct.get(st.id()) or idx.spaces.get(st.id())):
        kinds = sorted({p.is_a() for p in idx.m.by_type("IfcProduct")})
        raise ValueError(f"this IFC model has no building elements to draw (it only contains {', '.join(kinds)})")
    direct = idx.direct.get(st.id(), [])
    pick = lambda classes: [e for e in direct if any(e.is_a(c) for c in classes)  # noqa: E731
                            and not getattr(e, "Decomposes", None)]
    out = {"storey": st.Name or st.LongName or f"#{st.id()}",
           "storeys": [s.Name or s.LongName or f"#{s.id()}" for s in idx.storeys]}
    for key, els in (("walls", pick(WALL_CLASSES)), ("doors", pick(("IfcDoor",))),
                     ("windows", pick(("IfcWindow",))), ("fixtures", pick(FIXTURE_CLASSES)),
                     ("rooms", list(idx.spaces.get(st.id(), [])))):
        items = []
        for e in els:
            g = _footprint(idx, e)
            if g is not None and g.area > 0:
                items.append((e, g))
        out[key] = items
    out["mode"] = "building"
    if not out["walls"] and not out["rooms"]:      # services-only model (plumbing, HVAC): draw its parts as outlines
        parts = [e for e in direct if not getattr(e, "Decomposes", None)]
        out["mode"] = f"services model: {len(parts)} parts" + (f", first {MEP_CAP} drawn" if len(parts) > MEP_CAP else "")
        out["fixtures"] = [(e, g) for e in parts[:MEP_CAP] for g in [_hull(idx, e)] if g is not None and g.area > 0]
    return out


def _frame(p: dict, max_px: int):
    geoms = [g for k in ("walls", "rooms", "doors", "windows", "fixtures") for _, g in p[k]]
    if not geoms:
        raise ValueError(f"storey '{p['storey']}' has no elements with geometry to draw")
    minx, miny, maxx, maxy = unary_union(geoms).bounds
    span = max(maxx - minx, maxy - miny) or 1.0
    k = (max_px - 2 * PAD) / span                                    # pixels per metre
    w, h = int(np.ceil((maxx - minx) * k)) + 2 * PAD, int(np.ceil((maxy - miny) * k)) + 2 * PAD

    def px(coords):
        return [[round((x - minx) * k + PAD, 2), round((maxy - y) * k + PAD, 2)] for x, y in coords]
    return k, w, h, px


def _polys(g):
    return list(g.geoms) if isinstance(g, MultiPolygon) else [g] if g.geom_type == "Polygon" else []


def render(path: str, out: str, max_px: int = 2000) -> None:
    p = plan(path)
    k, w, h, px = _frame(p, max_px)
    img = np.full((h, w, 3), 255, np.uint8)
    lw = max(1, int(round(w / 900)))
    arr = lambda c: np.array(px(c), np.int32)  # noqa: E731
    for _, g in p["rooms"]:
        for q in _polys(g):
            cv2.fillPoly(img, [arr(q.exterior.coords)], (246, 243, 236))
            cv2.polylines(img, [arr(q.exterior.coords)], True, (190, 190, 190), lw, cv2.LINE_AA)
    for _, g in p["walls"]:
        for q in _polys(g):
            cv2.fillPoly(img, [arr(q.exterior.coords)], (45, 45, 45), cv2.LINE_AA)
            for hole in q.interiors:
                cv2.fillPoly(img, [arr(hole.coords)], (255, 255, 255), cv2.LINE_AA)
    for key, col in (("windows", (200, 120, 40)), ("doors", (30, 30, 30)), ("fixtures", (90, 90, 90))):
        for _, g in p[key]:
            for q in _polys(g):
                cv2.polylines(img, [arr(q.exterior.coords)], True, col, lw, cv2.LINE_AA)
    fs = max(0.35, w / 3200)
    from engine.vector.dxf_render import ascii_label
    for e, g in p["rooms"]:
        c = g.representative_point()
        (x, y), = px([(c.x, c.y)])
        cv2.putText(img, ascii_label(e.LongName or e.Name or "")[:24], (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, fs,
                    (70, 70, 70), 1, cv2.LINE_AA)
    cv2.imwrite(out, img)


def geometry(path: str, max_px: int = 2000) -> dict:
    p = plan(path)
    k, w, h, px = _frame(p, max_px)
    wu = unary_union([g for _, g in p["walls"]]) if p["walls"] else None
    walls = [{"outer": px(q.simplify(0.005).exterior.coords[:-1]),
              "holes": [px(hh.coords[:-1]) for hh in q.simplify(0.005).interiors]}
             for q in (_polys(wu) if wu is not None else [])]

    def els(key, kind):
        out = []
        for e, g in p[key]:
            q = max(_polys(g), key=lambda x: x.area)
            out.append({"id": f"ifc:{e.GlobalId}", "kind": kind, "subtype": e.is_a(),
                        "label": (e.LongName or e.Name) if kind == "room" else e.Name,
                        "polygon": px(q.exterior.coords[:-1])})
        return out
    return {"width": w, "height": h, "walls": walls, "rooms": els("rooms", "room"), "doors": els("doors", "door"),
            "windows": els("windows", "window"), "fixtures": els("fixtures", "fixture"), "elements_aligned": True,
            "px_per_m": round(k, 4), "storey": p["storey"], "storeys": p["storeys"],
            "wall_note": (f"storey '{p['storey']}': " + (
                f"{len(p['walls'])} walls/columns from the model's own meshes, merged into {len(walls)} pieces"
                if p["mode"] == "building" else f"no walls ({p['mode']})")
                + f"; other storeys: {', '.join(s for s in p['storeys'] if s != p['storey']) or 'none'}")}
