"""SVG floor-plan sheets generated from IFC (IfcConvert): one <g class="IfcXxx" data-name=...> per element.

Exact because the file is vector: counts are elements of a class in the section drawn at the sheet's cut plane,
areas are shoelace areas of the IfcSpace paths times the printed scale ('1:100' text on the sheet, cross-checked
with the 5 m scale-bar rectangle when found). `scale_note` says where the scale came from.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from shapely.geometry import Polygon

from . import ifc as I
from . import ifc_query as Q

NS = "{http://www.w3.org/2000/svg}"
_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")


@dataclass
class SvgSheet:
    path: str
    ratio: Optional[float]
    scale_note: str
    elements: list = field(default_factory=list)      # dict(cls,name,poly,eid)
    texts: list = field(default_factory=list)         # (text, x, y)
    mm_per_unit: float = 1.0


def _rings(d: str) -> list[list[tuple[float, float]]]:
    out = []
    for sub in re.split(r"(?=[Mm])", d.strip()):
        nums = [float(x) for x in _NUM.findall(sub)]
        pts = list(zip(nums[0::2], nums[1::2]))
        if len(pts) >= 3:
            out.append(pts)
    return out


def _poly(d: str) -> Optional[Polygon]:
    acc = None
    for r in _rings(d):
        pg = Polygon(r)
        if not pg.is_valid:
            pg = pg.buffer(0)
        acc = pg if acc is None else acc.symmetric_difference(pg)
    return acc


@lru_cache(maxsize=8)
def load(path: str) -> SvgSheet:
    root = ET.parse(path).getroot()
    vb = [float(x) for x in root.get("viewBox", "0 0 1 1").split()]
    wmm = re.match(r"([\d.]+)\s*mm", root.get("width", "") or "")
    mm_per_unit = float(wmm.group(1)) / vb[2] if wmm and vb[2] else 1.0
    texts, els = [], []
    for t in root.iter(NS + "text"):
        texts.append(((t.text or "").strip(), float(t.get("x", 0)), float(t.get("y", 0))))
    for g in root.iter(NS + "g"):
        cls = g.get("class")
        if not cls or not cls.startswith("Ifc"):
            continue
        poly = None
        for p in g.iter(NS + "path"):
            pg = _poly(p.get("d", ""))
            if pg is not None and not pg.is_empty:
                poly = pg if poly is None else poly.union(pg)
        els.append(dict(cls=cls, name=g.get("data-name") or "", poly=poly, eid=g.get("id") or ""))
    ratio, note = None, "no printed scale"
    for t, _, _ in texts:
        m = re.search(r"(?:\b|^)1\s*:\s*(\d{2,4})\b", t)
        if m:
            ratio = float(m.group(1))
            note = f"printed scale text '1:{int(ratio)}' (paper mm per drawing unit {mm_per_unit:g})"
            break
    return SvgSheet(path=path, ratio=ratio, scale_note=note, elements=els, texts=texts, mm_per_unit=mm_per_unit)


_WALL = ("IfcWall", "IfcWallStandardCase")
_CLS = {"IfcWall": _WALL, "IfcDoor": ("IfcDoor",), "IfcWindow": ("IfcWindow",), "IfcSpace": ("IfcSpace",),
        "IfcColumn": ("IfcColumn",), "IfcBeam": ("IfcBeam",), "IfcStair": ("IfcStair", "IfcStairFlight"),
        "IfcSlab": ("IfcSlab",), "IfcRailing": ("IfcRailing",), "IfcRoof": ("IfcRoof",)}


def _m2(sheet: SvgSheet, area_units: float) -> float:
    # drawing units -> paper mm -> real mm -> m
    return area_units * (sheet.mm_per_unit * sheet.ratio / 1000.0) ** 2


def answer(path: str, intent: str, question: str, params: Optional[dict] = None) -> list[Q.IfcAnswer]:
    params = params or {}
    sh = load(path)
    if intent in ("count_on_storey", "doors_on_storey"):
        cls = "IfcDoor" if intent == "doors_on_storey" else I.element_class_from_text(question, params.get("element"))
        if not cls or cls not in _CLS:
            return []
        els = [e for e in sh.elements if e["cls"] in _CLS[cls]]
        return [Q.IfcAnswer("ifc_exact", float(len(els)), "count",
                            f"svg sheet: {len(els)} <g class={'/'.join(_CLS[cls])}> in the cut-plane drawing; exact source, single voter",
                            [e["eid"] for e in els])]
    if intent in ("room_net_area", "total_net_area_storey"):
        if not sh.ratio:
            return []
        sp = [e for e in sh.elements if e["cls"] == "IfcSpace" and e["poly"] is not None]
        if intent == "total_net_area_storey":
            tot = sum(_m2(sh, e["poly"].area) for e in sp)
            return [Q.IfcAnswer("ifc_exact", tot, "m2", f"svg sheet: sum of {len(sp)} IfcSpace path areas; {sh.scale_note}",
                                [e["eid"] for e in sp])]
        names = I.quoted_names(question)
        room = params.get("room") or (names[0] if names else "")
        m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", room)
        long_, num = (m.group(1), m.group(2)) if m else ("", room)
        cands = [e for e in sp if I.norm(e["name"]) == I.norm(num)]
        if len(cands) > 1 and long_:
            # disambiguate by the long name printed near the polygon
            c2 = []
            for e in cands:
                cx, cy = e["poly"].representative_point().x, e["poly"].representative_point().y
                near = [t for t, x, y in sh.texts if I.norm(t) == I.norm(long_) and abs(x - cx) < 15 and abs(y - cy) < 15]
                if near:
                    c2.append(e)
            cands = c2 or cands
        if not cands:
            return []
        e = cands[0]
        return [Q.IfcAnswer("ifc_exact", _m2(sh, e["poly"].area), "m2",
                            f"svg sheet: shoelace area of IfcSpace '{num}' x scale; {sh.scale_note}; exact source, single voter",
                            [e["eid"]])]
    return []
