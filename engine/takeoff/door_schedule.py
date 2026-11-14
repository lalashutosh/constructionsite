"""Draft door schedule: one row per door. This is the hero export -- "draft
door schedule generated from the plan" -- CSV so it can go straight into a
spreadsheet or BIM import.
"""
from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from typing import Optional

from shapely.geometry import Polygon

from contracts.proof import Element, ScaleInfo, SheetFacts


@dataclass
class DoorRow:
    id: str
    from_room: Optional[str] = None
    to_room: Optional[str] = None
    width_m: Optional[float] = None
    width_error_m: Optional[float] = None
    width_px_relative: Optional[float] = None
    swing: Optional[str] = None
    element_ids: list[str] = field(default_factory=list)
    open_decisions: list[str] = field(default_factory=list)


def _closed(polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return polygon if polygon[0] == polygon[-1] else [*polygon, polygon[0]]


def _centroid(polygon: list[tuple[float, float]]):
    return Polygon(_closed(polygon)).centroid


def _distance_to_room(centroid, room: Element) -> float:
    return centroid.distance(Polygon(_closed(room.polygon)))


def _door_width_px(door: Element) -> float:
    if "width_px" in door.attrs:
        return float(door.attrs["width_px"])
    xs = [p[0] for p in door.polygon]
    ys = [p[1] for p in door.polygon]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def build(facts: SheetFacts, scale: Optional[ScaleInfo] = None) -> list[DoorRow]:
    """Build one DoorRow per door element. from/to room are the two nearest
    distinct room polygons to the door's centroid (0 distance = inside).
    Width is metres when `scale` has real (non-relative) px_per_m, otherwise
    only the raw pixel width is reported and an open decision is raised
    (never report a door width as measured when the scale itself came only
    from the door-width prior: that would be circular evidence).
    """
    doors = [e for e in facts.elements if e.kind == "door"]
    rooms = [e for e in facts.elements if e.kind == "room"]
    rows: list[DoorRow] = []

    for d in doors:
        c = _centroid(d.polygon)
        ranked = sorted(rooms, key=lambda r: (_distance_to_room(c, r), r.id))
        open_decisions: list[str] = []
        if len(ranked) == 0:
            from_room = to_room = None
            open_decisions.append("no room polygons on this sheet: from/to room unknown")
        elif len(ranked) == 1:
            from_room = ranked[0].id
            to_room = "exterior"
            open_decisions.append(
                f"only one room polygon ({ranked[0].id}) on sheet: {d.id} assumed exterior door, confirm"
            )
        else:
            from_room, to_room = ranked[0].id, ranked[1].id

        row = DoorRow(
            id=d.id,
            from_room=from_room,
            to_room=to_room,
            swing=d.attrs.get("swing"),
            element_ids=[d.id],
            open_decisions=open_decisions,
        )

        width_px = _door_width_px(d)
        if scale is not None and scale.px_per_m and not scale.widths_relative:
            row.width_m = round(width_px / scale.px_per_m, 3)
            if scale.rel_sigma:
                row.width_error_m = round(row.width_m * scale.rel_sigma, 3)
        else:
            row.width_px_relative = width_px
            row.open_decisions = [
                *row.open_decisions,
                "scale is relative only (door-width prior would be circular evidence): width given in px, not metres",
            ]
        rows.append(row)
    return rows


def to_csv(rows: list[DoorRow]) -> str:
    buf = io.StringIO()
    fieldnames = [
        "id", "from_room", "to_room", "width_m", "width_error_m",
        "width_px_relative", "swing", "element_ids", "open_decisions",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        d = asdict(r)
        d["element_ids"] = ";".join(d["element_ids"])
        d["open_decisions"] = ";".join(d["open_decisions"])
        writer.writerow(d)
    return buf.getvalue()
