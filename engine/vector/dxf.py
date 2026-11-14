"""Swiss Dwellings DXF reader (exact). Wraps vendor/planlab for name->type tables and extends it with the counting
rules derived from the data (see docs/handoff/vector.md):

  doors      = number of 5-point open polylines on layer DOOR (one frame per opening; a double door shares one frame;
               stacked duplicate ARC/leaf entities and the second arc of a double door are NOT counted).
  windows    = number of 4-point polylines on layer WINDOW (the 2-point ones are sill/reveal lines).
  apartments = UNIT_OUTLINE polygons whose ROOM_TEXT contains an apartment label ('App. A', 'Whg. A', ...);
               units without that label are commercial space / balcony units.
  rooms      = closed ROOM_OUTLINE polylines carrying a number text ('5.11'); name/area label from the other texts.
Units: $INSUNITS is read (6 = metres); coordinates are converted to metres and verified against the printed room
area labels ('13.6 m²') when present.
"""
from __future__ import annotations

import math
import re
import sys
import pathlib
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import ezdxf
from shapely.geometry import Point, Polygon

_VENDOR = pathlib.Path(__file__).resolve().parents[2] / "vendor" / "planlab"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))
try:  # reuse the prototype's multilingual name table
    from planlab import NAME_TYPES  # type: ignore
except Exception:  # pragma: no cover
    NAME_TYPES = {}

INSUNITS_M = {0: None, 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 7: 1000.0}
OUTDOOR = {"balcon", "balcone", "balkon", "loggia", "terrasse", "terrazza", "terrace", "veranda", "giardino", "jardin", "garten"}
APT_LABEL = re.compile(r"^(?:app|appt|whg|apt|wohnung|appartement|apartment)\.?\s+([A-Za-z]{1,2})$", re.I)
NUM_RE = re.compile(r"^[A-Z]{0,2}\d+\.\d+$")


def _pts(e):
    return [(float(x), float(y)) for x, y in e.get_points("xy")]


@dataclass
class Room:
    id: str
    name: Optional[str]
    poly: Polygon
    area_label: Optional[float]
    unit: Optional[int] = None
    eid: str = ""

    @property
    def outdoor(self) -> bool:
        return (self.name or "").strip().casefold() in OUTDOOR

    @property
    def area(self) -> float:
        return self.poly.area


@dataclass
class Unit:
    poly: Polygon
    label: Optional[str]       # apartment letter ('A') or None
    raw_label: Optional[str] = None
    eid: str = ""


@dataclass
class DxfPlan:
    path: str
    scale: float                # drawing units -> metres
    units_note: str
    rooms: list[Room]
    units: list[Unit]
    door_frames: list           # 5-pt polylines (list of points)
    door_arcs: list             # (center, radius, a0, a1)
    window_polys: list
    fixtures: list[dict]
    title: str = ""
    layers: dict = field(default_factory=dict)
    texts: list = field(default_factory=list)


@lru_cache(maxsize=8)
def load(path: str) -> DxfPlan:
    d = ezdxf.readfile(path)
    ins = d.header.get("$INSUNITS", 0)
    scale = INSUNITS_M.get(ins)
    note = f"$INSUNITS={ins}"
    msp = list(d.modelspace())
    L: dict[str, list] = {}
    for e in msp:
        L.setdefault(e.dxf.layer, []).append(e)
    # --- rooms
    texts = [(e.dxf.text, e.dxf.insert.x, e.dxf.insert.y) for e in L.get("ROOM_TEXT", [])]
    rooms: list[Room] = []
    outlines: list[tuple[int, Polygon]] = []
    for i, e in enumerate(L.get("ROOM_OUTLINE", [])):
        if e.dxftype() != "LWPOLYLINE" or not e.closed:
            continue
        pts = _pts(e)
        if len(pts) < 3:
            continue
        p = Polygon(pts)
        if not p.is_valid or p.area <= 0:
            continue
        outlines.append((i, p))
    # A text belongs to the INNERMOST outline that contains it. An outline that contains other outlines (lift core
    # around a shaft, ...) is the ring around them: its net area is polygon minus the nested outlines. This is what
    # the printed 'm²' labels and the answer key use (verified on duplicate-numbered rooms such as 5.11/5.12).
    owner: dict[int, list] = {i: [] for i, _ in outlines}
    for t in texts:
        pt = Point(t[1], t[2])
        cont = [(p.area, i) for i, p in outlines if p.contains(pt)]
        if cont:
            owner[min(cont)[1]].append(t)
    for i, p in outlines:
        inside = sorted(owner[i], key=lambda t: -t[2])
        nested = [q for j, q in outlines if j != i and q.area < p.area and p.contains(q)]
        if nested:
            from shapely.ops import unary_union
            p = p.difference(unary_union(nested))
            if p.is_empty or p.area <= 0:
                continue
        name = num = area = None
        for t, _, _ in inside:
            if NUM_RE.match(t):
                num = t
            elif "m²" in t:
                try:
                    area = float(re.sub(r"[^0-9.]", "", t))
                except ValueError:
                    pass
            elif name is None and not APT_LABEL.match(t.strip()):
                name = t
        if num:
            rooms.append(Room(id=num, name=name, poly=p, area_label=area, eid=f"dxf:ROOM_OUTLINE#{i}"))
    # unit of a room
    units: list[Unit] = []
    for i, e in enumerate(L.get("UNIT_OUTLINE", [])):
        pts = _pts(e)
        if len(pts) < 3:
            continue
        p = Polygon(pts)
        if not p.is_valid:
            p = p.buffer(0)
        lab = raw = None
        for t, x, y in texts:
            m = APT_LABEL.match(t.strip())
            if m and p.contains(Point(x, y)):
                lab, raw = m.group(1).upper(), t
                break
        units.append(Unit(poly=p, label=lab, raw_label=raw, eid=f"dxf:UNIT_OUTLINE#{i}"))
    for r in rooms:
        c = r.poly.representative_point()
        cont = [(u.poly.area, ui) for ui, u in enumerate(units) if u.poly.area > 0 and u.poly.contains(c)]
        if cont:  # innermost unit polygon (units can be nested)
            r.unit = min(cont)[1]
    door_frames, door_arcs = [], []
    for e in L.get("DOOR", []):
        if e.dxftype() == "LWPOLYLINE" and len(e) == 5:
            door_frames.append(_pts(e))
        elif e.dxftype() == "ARC":
            door_arcs.append(((e.dxf.center.x, e.dxf.center.y), e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle))
    wins = [_pts(e) for e in L.get("WINDOW", []) if e.dxftype() == "LWPOLYLINE" and len(e) == 4]
    fixtures = _fixture_clusters(L.get("FIXTURE", []))
    title = next((e.dxf.text for e in L.get("ANNOTATION", [])), "")
    plan = DxfPlan(path=path, scale=scale if scale else 1.0, units_note=note, rooms=rooms, units=units,
                   door_frames=door_frames, door_arcs=door_arcs, window_polys=wins, fixtures=fixtures, title=title,
                   layers={k: len(v) for k, v in L.items()}, texts=texts)
    # unit sanity: printed area labels vs polygon area (verifies the scale; never assume metres)
    ratios = [r.area_label / r.area for r in rooms if r.area_label and r.area > 0]
    if ratios:
        ratios.sort()
        med = ratios[len(ratios) // 2]
        plan.units_note += f"; printed-area/polygon-area median {med:.3f}"
        if scale is None or abs(med - 1) > 0.1:
            # calibrate: polygon area * k^2 = label area  -> k
            plan.scale = math.sqrt(med) if med > 0 else 1.0
            plan.units_note += " (scale calibrated from printed areas)"
    return plan


def _fixture_clusters(ents) -> list[dict]:
    """Union-find clusters of FIXTURE circles/polylines (planlab/fixtures.py idea)."""
    from shapely.ops import unary_union
    items = []
    for e in ents:
        if e.dxftype() == "CIRCLE":
            items.append(("C", Point(e.dxf.center.x, e.dxf.center.y).buffer(e.dxf.radius)))
        elif e.dxftype() == "LWPOLYLINE":
            pts = _pts(e)
            if len(pts) >= 3:
                pg = Polygon(pts)
                if pg.is_valid:
                    items.append(("P", pg))
    n = len(items)
    parent = list(range(n))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if items[i][1].buffer(0.02).intersects(items[j][1]):
                parent[f(i)] = f(j)
    cl: dict[int, list[int]] = {}
    for i in range(n):
        cl.setdefault(f(i), []).append(i)
    out = []
    for v in cl.values():
        u = unary_union([items[i][1] for i in v])
        b = u.bounds
        out.append(dict(nC=sum(items[i][0] == "C" for i in v), nP=sum(items[i][0] == "P" for i in v),
                        L=max(b[2] - b[0], b[3] - b[1]), S=min(b[2] - b[0], b[3] - b[1]),
                        c=u.centroid.coords[0], area=u.area))
    return out
