"""DXF without a sibling image: draw it ourselves and build the 3D data straight from its entities (exact, no vision).

`frame(path, max_px)`   -> Frame: drawing units -> image pixels (uniform scale, y flipped, padded)
`render(path, out, max_px)` writes a PNG of the plan in that pixel space (walls filled, doors with swing arcs, windows,
                         fixtures, room outlines and labels).
`geometry(path, max_px)` -> dict in the SAME pixel space, same shape as engine.geometry3d.model():
                         walls = union of the closed WALL polylines (pieces that touch merge, rooms stay open as holes),
                         rooms = ROOM_OUTLINE polygons with their names, doors = 5-point DOOR frames,
                         windows = 4-point WINDOW polylines, fixtures = FIXTURE clusters (bounding boxes).
Coordinates are labelled `dxf-render`: they are not the pixel space of the readers' evidence polygons (those stay in
drawing units), so the UI must not pin proof evidence onto this image.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import ezdxf
import numpy as np
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from engine.vector import dxf as D

PAD = 24
LAYERS = ("WALL", "ROOM_OUTLINE", "DOOR", "WINDOW", "FIXTURE", "UNIT_OUTLINE")


@dataclass(frozen=True)
class Frame:
    minx: float
    maxy: float
    k: float            # pixels per drawing unit
    width: int
    height: int
    m_per_unit: float   # drawing unit -> metres (from $INSUNITS / printed areas, engine.vector.dxf)

    def px(self, pts) -> list[list[float]]:
        return [[round((x - self.minx) * self.k + PAD, 2), round((self.maxy - y) * self.k + PAD, 2)] for x, y in pts]

    @property
    def px_per_m(self) -> float:
        return self.k / self.m_per_unit if self.m_per_unit else 0.0


_TRANS = str.maketrans({"ß": "ss", "²": "2", "³": "3", "æ": "ae", "Æ": "AE", "ø": "o", "Ø": "O"})


def ascii_label(s: str) -> str:
    """OpenCV's Hershey fonts are ASCII only: 'Küche 7.54 m²' -> 'Kuche 7.54 m2', 'KÖÖK' -> 'KOOK' (no '??')."""
    import unicodedata
    s = s.translate(_TRANS)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _ents(path: str) -> dict[str, list]:
    msp = ezdxf.readfile(path).modelspace()
    L: dict[str, list] = {}
    for e in msp:
        L.setdefault(e.dxf.layer, []).append(e)
    return L


def _points(e) -> list[tuple[float, float]]:
    t = e.dxftype()
    if t == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y in e.get_points("xy")]
    if t == "LINE":
        return [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    if t in ("CIRCLE", "ARC"):
        c, r = e.dxf.center, e.dxf.radius
        return [(c.x - r, c.y - r), (c.x + r, c.y + r)]
    if t == "TEXT":
        return [(e.dxf.insert.x, e.dxf.insert.y)]
    return []


def frame(path: str, max_px: int = 2000) -> Frame:
    L = _ents(path)
    pts = [p for lay in LAYERS for e in L.get(lay, []) for p in _points(e)]
    if not pts:                                  # unknown layer scheme: use every entity we can place
        pts = [p for es in L.values() for e in es for p in _points(e)]
    if not pts:
        raise ValueError("DXF has no drawable entities")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    span = max(maxx - minx, maxy - miny) or 1.0
    k = (max_px - 2 * PAD) / span
    w = int(math.ceil((maxx - minx) * k)) + 2 * PAD
    h = int(math.ceil((maxy - miny) * k)) + 2 * PAD
    plan = D.load(path)
    return Frame(minx=minx, maxy=maxy, k=k, width=w, height=h, m_per_unit=plan.scale or 1.0)


def _wall_polys(L: dict) -> list[Polygon]:
    out = []
    for e in L.get("WALL", []):
        if e.dxftype() == "LWPOLYLINE" and e.closed:
            pts = _points(e)
            if len(pts) >= 3:
                p = Polygon(pts)
                p = p if p.is_valid else p.buffer(0)
                if not p.is_empty and p.area > 0:
                    out.append(p)
    return out


def _fixture_boxes(L: dict) -> list[Polygon]:
    items = []
    for e in L.get("FIXTURE", []):
        if e.dxftype() == "CIRCLE":
            items.append(Point(e.dxf.center.x, e.dxf.center.y).buffer(e.dxf.radius))
        elif e.dxftype() == "LWPOLYLINE":
            pts = _points(e)
            if len(pts) >= 3:
                p = Polygon(pts)
                items.append(p if p.is_valid else p.buffer(0))
    if not items:
        return []
    merged = unary_union([g.buffer(0.02) for g in items])        # same clustering tolerance as engine.vector.dxf
    geoms = merged.geoms if isinstance(merged, MultiPolygon) else [merged]
    return [g.minimum_rotated_rectangle for g in geoms if not g.is_empty]


def render(path: str, out: str, max_px: int = 2000) -> Frame:
    fr = frame(path, max_px)
    L = _ents(path)
    img = np.full((fr.height, fr.width, 3), 255, np.uint8)
    lw = max(1, int(round(fr.width / 900)))

    def poly(pts, closed=True, color=(0, 0, 0), t=lw):
        if len(pts) >= 2:
            cv2.polylines(img, [np.array(fr.px(pts), np.int32)], closed, color, t, cv2.LINE_AA)

    for e in L.get("ROOM_OUTLINE", []):
        if e.dxftype() == "LWPOLYLINE":
            poly(_points(e), e.closed, (190, 190, 190))
    for p in _wall_polys(L):
        cv2.fillPoly(img, [np.array(fr.px(p.exterior.coords), np.int32)], (45, 45, 45), cv2.LINE_AA)
        for hole in p.interiors:
            cv2.fillPoly(img, [np.array(fr.px(hole.coords), np.int32)], (255, 255, 255), cv2.LINE_AA)
    for e in L.get("WALL", []):                  # open wall polylines (no area) still drawn as strokes
        if e.dxftype() == "LWPOLYLINE" and not e.closed:
            poly(_points(e), False, (45, 45, 45), lw * 2)
    for e in L.get("WINDOW", []):
        if e.dxftype() == "LWPOLYLINE":
            poly(_points(e), e.closed, (200, 120, 40))
    for e in L.get("DOOR", []):
        if e.dxftype() == "LWPOLYLINE":
            poly(_points(e), e.closed, (30, 30, 30))
        elif e.dxftype() == "ARC":
            (cx, cy), = fr.px([(e.dxf.center.x, e.dxf.center.y)])
            r = e.dxf.radius * fr.k
            # y is flipped, so a counter-clockwise DXF arc a0..a1 becomes -a1..-a0 in image angles
            cv2.ellipse(img, (int(cx), int(cy)), (int(r), int(r)), 0, -e.dxf.end_angle, -e.dxf.start_angle,
                        (120, 120, 120), lw, cv2.LINE_AA)
    for e in L.get("FIXTURE", []):
        if e.dxftype() == "LWPOLYLINE":
            poly(_points(e), e.closed, (90, 90, 90))
        elif e.dxftype() == "CIRCLE":
            (cx, cy), = fr.px([(e.dxf.center.x, e.dxf.center.y)])
            cv2.circle(img, (int(cx), int(cy)), max(1, int(e.dxf.radius * fr.k)), (90, 90, 90), lw, cv2.LINE_AA)
    fs = max(0.35, fr.width / 3200)
    for e in L.get("ROOM_TEXT", []):
        (x, y), = fr.px([(e.dxf.insert.x, e.dxf.insert.y)])
        cv2.putText(img, ascii_label(str(e.dxf.text))[:24], (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, fs, (70, 70, 70), 1,
                    cv2.LINE_AA)
    cv2.imwrite(out, img)
    return fr


def geometry(path: str, max_px: int = 2000) -> dict:
    fr = frame(path, max_px)
    L = _ents(path)
    plan = D.load(path)
    walls = []
    wp = _wall_polys(L)
    if wp:
        u = unary_union(wp)
        for g in (u.geoms if isinstance(u, MultiPolygon) else [u]):
            if g.is_empty or g.geom_type != "Polygon":
                continue
            g = g.simplify(0.005, preserve_topology=True)
            walls.append({"outer": fr.px(g.exterior.coords[:-1]),
                          "holes": [fr.px(h.coords[:-1]) for h in g.interiors]})
    rooms = []
    for r in plan.rooms:
        g = r.poly if r.poly.geom_type == "Polygon" else max(r.poly.geoms, key=lambda q: q.area)
        rooms.append({"id": r.eid, "kind": "room", "subtype": "outdoor" if r.outdoor else "room",
                      "label": " ".join(x for x in (r.name, r.id) if x) or r.id,
                      "polygon": fr.px(g.exterior.coords[:-1])})
    doors = [{"id": f"dxf:DOOR#{i}", "kind": "door", "subtype": None, "label": None, "polygon": fr.px(p)}
             for i, p in enumerate(plan.door_frames)]
    windows = [{"id": f"dxf:WINDOW#{i}", "kind": "window", "subtype": None, "label": None, "polygon": fr.px(p)}
               for i, p in enumerate(plan.window_polys)]
    fixtures = [{"id": f"dxf:FIXTURE#{i}", "kind": "fixture", "subtype": None, "label": None,
                 "polygon": fr.px(b.exterior.coords[:-1])} for i, b in enumerate(_fixture_boxes(L))]
    note = (f"walls = {len(wp)} closed WALL polylines from the DXF itself, merged into {len(walls)} pieces"
            if wp else "no closed WALL polylines in this DXF")
    return {"width": fr.width, "height": fr.height, "walls": walls, "wall_note": note, "rooms": rooms,
            "doors": doors, "windows": windows, "fixtures": fixtures, "elements_aligned": True,
            "px_per_m": round(fr.px_per_m, 4), "units_note": plan.units_note}
