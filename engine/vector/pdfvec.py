"""Vector floor-plan PDFs via PyMuPDF `page.get_drawings()` (no sibling needed).

Implemented sheet family: IfcConvert-style plan sheets (the dataset's ifc_models PDFs): IfcSpace = light-blue filled
paths (0.89, 0.93, 0.97), walls = dark-grey filled paths (0.29); room labels = a name word line + a number word line.
Scale = printed '1:N' text on the page (1 pt = 25.4/72 mm of paper). Anything else returns [] (pixel route takes it).
Evidence polygons are in PDF user units of page 1 (render at 150 dpi => multiply by 150/72).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

import pymupdf
from shapely.geometry import Polygon

from . import ifc as I
from . import ifc_query as Q

SPACE_FILL = (0.89, 0.93, 0.97)
WALL_FILL = (0.29, 0.29, 0.29)


def _close(a, b, tol=0.015):
    return a is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def _path_poly(d) -> Optional[Polygon]:
    pts = []
    for it in d["items"]:
        if it[0] == "l":
            if not pts:
                pts.append((it[1].x, it[1].y))
            pts.append((it[2].x, it[2].y))
        elif it[0] == "re":
            r = it[1]
            pts += [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
        elif it[0] == "qu":
            q = it[1]
            pts += [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
        elif it[0] == "c":
            if not pts:
                pts.append((it[1].x, it[1].y))
            pts.append((it[4].x, it[4].y))
    if len(pts) < 3:
        return None
    pg = Polygon(pts)
    if not pg.is_valid:
        pg = pg.buffer(0)
    return pg if not pg.is_empty else None


@lru_cache(maxsize=8)
def load(path: str):
    doc = pymupdf.open(path)
    pg = doc[0]
    words = pg.get_text("words")
    ratio = None
    for w in words:
        m = re.fullmatch(r"1:(\d{2,4})", w[4])
        if m:
            ratio = float(m.group(1))
            break
    spaces, walls = [], []
    for d in pg.get_drawings():
        f = d.get("fill")
        if f is None:
            continue
        if _close(f, SPACE_FILL):
            p = _path_poly(d)
            if p is not None and p.area > 1:
                spaces.append(p)
        elif _close(f, WALL_FILL):
            walls.append(d)
    # labels: group words into lines
    lines: dict[tuple, list] = {}
    for x0, y0, x1, y1, w, b, l, n in words:
        lines.setdefault((b, l), []).append((x0, y0, x1, y1, w))
    labels = []
    for k, ws in lines.items():
        ws.sort()
        txt = " ".join(w[4] for w in ws)
        labels.append((txt, (ws[0][0] + ws[-1][2]) / 2, (ws[0][1] + ws[0][3]) / 2))
    return dict(ratio=ratio, spaces=spaces, walls=walls, labels=labels, rect=tuple(pg.rect))


def _m2(ratio, area_pt2):
    return area_pt2 * (25.4 / 72.0 * ratio / 1000.0) ** 2


def answer(path: str, intent: str, question: str, params: Optional[dict] = None) -> list[Q.IfcAnswer]:
    params = params or {}
    sh = load(path)
    if not sh["spaces"] or not sh["ratio"]:
        return []
    note = f"pdf vector paths (PyMuPDF get_drawings), printed scale 1:{int(sh['ratio'])}"
    if intent == "total_net_area_storey":
        return [Q.IfcAnswer("pdf_vector", sum(_m2(sh["ratio"], p.area) for p in sh["spaces"]), "m2",
                            f"{note}: sum of {len(sh['spaces'])} IfcSpace fills; exact source, single voter")]
    if intent == "count_on_storey":
        cls = I.element_class_from_text(question, params.get("element"))
        if cls == "IfcSpace":
            return [Q.IfcAnswer("pdf_vector", float(len(sh["spaces"])), "count", f"{note}: space fills; exact source, single voter")]
        if cls == "IfcWall":
            return [Q.IfcAnswer("pdf_vector", float(len(sh["walls"])), "count", f"{note}: wall fills; exact source, single voter")]
        return []
    if intent == "room_net_area":
        names = I.quoted_names(question)
        room = params.get("room") or (names[0] if names else "")
        m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", room)
        long_, num = (m.group(1), m.group(2)) if m else ("", room)
        hits = [(t, x, y) for t, x, y in sh["labels"] if I.norm(t) == I.norm(num)]
        cands = []
        for t, x, y in hits:
            for p in sh["spaces"]:
                if p.contains(__import__("shapely.geometry", fromlist=["Point"]).Point(x, y)):
                    cands.append(p)
                    break
        if not cands:
            return []
        p = cands[0]
        return [Q.IfcAnswer("pdf_vector", _m2(sh["ratio"], p.area), "m2",
                            f"{note}: area of the IfcSpace fill containing label '{num}'; exact source, single voter")]
    return []
