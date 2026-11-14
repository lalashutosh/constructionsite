"""SheetFacts.elements from an exact DXF (Swiss Dwellings layers), so the query engine / planner can answer questions
no fixed intent covers ("which room is the largest?", "total bathroom area in apartment B?").
Coordinates are DXF units (metres here); every room carries attrs.area_m2, attrs.apartment, attrs.outdoor."""
from __future__ import annotations

import re

from contracts.proof import Element

# room names in the drawings (de/fr/it) -> one room type vocabulary shared with the raster reader
ROOM_TYPE = [
    (r"bain|bad\b|bagno|douche|dusche|doccia|wc|toilet", "bathroom"),
    (r"cuisine|küche|kueche|cucina", "kitchen"),
    (r"couloir|flur|korridor|gang|corridoio|disimpegno|entrée|entree|eingang|ingresso|vestibule", "hallway"),
    (r"escalier|treppe|scala", "stairs"),
    (r"chambre|schlafen|camera", "bedroom"),
    (r"séjour|sejour|salon|wohnen|soggiorno|living", "living_room"),
    (r"réduit|reduit|abstell|ripostiglio|cave|keller|storage|dépôt|depot", "storage"),
    (r"balcon|balkon|loggia|terrasse|terrazza|terrace|veranda|jardin|garten|giardino", "outdoor"),
    (r"pièce|piece|zimmer|stanza|locale|room", "room"),
]


def room_type(name):
    n = (name or "").casefold()
    for rx, t in ROOM_TYPE:
        if re.search(rx, n):
            return t
    return "unnamed" if not n else "room"


def from_dxf(abs_path: str) -> list[Element]:
    from engine.vector import dxf
    from engine.vector.dxf_query import classify_fixture

    pl = dxf.load(abs_path)
    k = float(pl.scale or 1.0)
    letters = {i: u.label for i, u in enumerate(pl.units)}
    out: list[Element] = []
    for r in pl.rooms:
        g = r.poly if r.poly.geom_type == "Polygon" else max(r.poly.geoms, key=lambda q: q.area)
        out.append(Element(id=f"room_{r.id}", kind="room", subtype=room_type(r.name),
                           polygon=[(float(x), float(y)) for x, y in list(g.exterior.coords)[:-1]],
                           label=r.name or r.id,
                           attrs={"number": r.id, "area_m2": round(r.area * k * k, 4), "outdoor": r.outdoor,
                                  "apartment": letters.get(r.unit) if r.unit is not None else None,
                                  "printed_area_m2": r.area_label}))
    for i, pts in enumerate(pl.door_frames):
        out.append(Element(id=f"door_{i}", kind="door", polygon=[(float(x), float(y)) for x, y in pts]))
    for i, pts in enumerate(pl.window_polys):
        pp = list(pts.exterior.coords) if hasattr(pts, "exterior") else pts
        out.append(Element(id=f"window_{i}", kind="window", polygon=[(float(x), float(y)) for x, y in pp]))
    single = {"toilets": "toilet", "washbasins": "sink", "bathtubs": "bathtub", "showers": "shower"}
    for i, c in enumerate(pl.fixtures):
        kind = single.get(classify_fixture(c) or "", "fixture")
        cx, cy = c["c"]
        out.append(Element(id=f"fixture_{i}", kind=kind, polygon=[(cx - .2, cy - .2), (cx + .2, cy - .2),
                                                                   (cx + .2, cy + .2), (cx - .2, cy + .2)]))
    return out
