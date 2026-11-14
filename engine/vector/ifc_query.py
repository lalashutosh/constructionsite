"""Intent -> numbers on an IFC model. Returns a list of `IfcAnswer` (one per independent voter)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import ifc as I

INTENTS = {
    "room_net_area", "total_net_area_storey", "walls_length_storey", "walls_volume_storey", "walls_side_area_storey",
    "slabs_volume_storey", "doors_on_storey", "count_on_storey", "count_in_model",
}
_PROP_AREA_KEYS = ("120_Pindala", "Area", "Floor Area", "Pindala")


@dataclass
class IfcAnswer:
    voter: str                     # ifc_exact | ifc_geometry | ifc_property
    value: float
    unit: str
    note: str
    element_ids: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)


def _eid(e) -> str:
    return f"ifc#{e.id()}"


def _space_keys(sp) -> set[str]:
    n, ln = I.norm(sp.Name), I.norm(sp.LongName)
    keys = {n, ln}
    if ln and n:
        keys.add(f"{ln} ({n})")
        keys.add(f"{n} ({ln})")
        keys.add(f"{n} {ln}")
    return {k for k in keys if k}


def _prop_area(idx: "I.IfcIndex", sp) -> Optional[float]:
    """A printed area property (e.g. AR_Ruum.120_Pindala '63,8'); rounded by the author, so only a cross-check."""
    try:
        import ifcopenshell.util.element as E
        for _, props in E.get_psets(sp).items():
            for k, v in props.items():
                if k in _PROP_AREA_KEYS and v not in (None, ""):
                    if isinstance(v, str):
                        v = float(v.replace(",", "."))
                    return float(v)
    except Exception:
        return None
    return None


def _find_space(idx, storey, room: str):
    key = I.norm(room)
    cands = [sp for sp in idx.spaces.get(storey.id(), []) if key in _space_keys(sp)]
    if cands:
        return cands
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", room)
    if m:  # 'LONGNAME (Name)' where the order differs
        a, b = I.norm(m.group(1)), I.norm(m.group(2))
        cands = [sp for sp in idx.spaces.get(storey.id(), []) if I.norm(sp.Name) == b or I.norm(sp.LongName) == a]
        cands = [sp for sp in cands if I.norm(sp.Name) == b] or cands
    return cands


def answer(path: str, intent: str, question: str, params: Optional[dict] = None) -> list[IfcAnswer]:
    if not I.HAVE_IFC:
        return []
    params = params or {}
    idx = I.load(path)
    names = I.quoted_names(question)
    out: list[IfcAnswer] = []

    if intent == "count_in_model":
        cls = I.element_class_from_text(question, params.get("element"))
        if not cls:
            return []
        els = idx.model_elements(cls)
        return [IfcAnswer("ifc_exact", float(len(els)), "count",
                          f"count of {cls} in the model (top-level, aggregated parts excluded); exact source, single voter",
                          [_eid(e) for e in els[:200]])]

    storey_name = params.get("storey") or (names[-1] if names else None)
    if intent == "room_net_area":
        room = params.get("room") or (names[0] if names else None)
        storey_name = params.get("storey") or (names[1] if len(names) > 1 else storey_name)
    st = idx.storey(storey_name) if storey_name else None
    if st is None:
        return []

    if intent in ("count_on_storey", "doors_on_storey"):
        cls = "IfcDoor" if intent == "doors_on_storey" else I.element_class_from_text(question, params.get("element"))
        if not cls:
            return []
        els = idx.elements(st, cls)
        return [IfcAnswer("ifc_exact", float(len(els)), "count",
                          f"{cls} directly contained in storey '{st.Name}' (IfcRelContainedInSpatialStructure)",
                          [_eid(e) for e in els])]

    if intent in ("room_net_area", "total_net_area_storey"):
        if intent == "room_net_area":
            sps = _find_space(idx, st, room)[:1]
            if not sps:
                return []
        else:
            sps = idx.elements(st, "IfcSpace")
        qv = [idx.quantity(s, "NetFloorArea") for s in sps]
        gv = None
        if all(v is not None for v in qv) and sps:
            out.append(IfcAnswer("ifc_exact", sum(qv), "m2",
                                 f"model quantity NetFloorArea of {len(sps)} IfcSpace on '{st.Name}'",
                                 [_eid(s) for s in sps]))
        gl = [idx.geom_floor_area(s) for s in sps]
        if sps and all(v is not None for v in gl):
            gv = sum(gl)
            out.append(IfcAnswer("ifc_geometry" if out else "ifc_exact", gv, "m2",
                                 f"geometry: footprint of {len(sps)} IfcSpace body on '{st.Name}' (no Qto in the model)"
                                 if not out else f"geometry: footprint of {len(sps)} IfcSpace bodies",
                                 [_eid(s) for s in sps]))
        pv = [_prop_area(idx, s) for s in sps]
        if sps and all(v is not None for v in pv):
            out.append(IfcAnswer("ifc_property", sum(pv), "m2",
                                 "author's printed area property (rounded)", [_eid(s) for s in sps]))
        return out

    if intent in ("walls_length_storey", "walls_volume_storey", "walls_side_area_storey", "slabs_volume_storey"):
        cls = "IfcSlab" if intent.startswith("slabs") else "IfcWall"
        qn = {"walls_length_storey": "Length", "walls_volume_storey": "NetVolume",
              "walls_side_area_storey": "NetSideArea", "slabs_volume_storey": "NetVolume"}[intent]
        unit = {"walls_length_storey": "m", "walls_side_area_storey": "m2"}.get(intent, "m3")
        els = idx.elements(st, cls)
        if not els:
            return []
        qv = [idx.quantity(e, qn) for e in els]
        if all(v is not None for v in qv):
            out.append(IfcAnswer("ifc_exact", sum(qv), unit,
                                 f"model quantity {qn} summed over {len(els)} {cls} on '{st.Name}'",
                                 [_eid(e) for e in els]))
        if qn == "NetVolume":
            gl = [idx.geom_volume(e) for e in els]
            if all(v is not None for v in gl):
                out.append(IfcAnswer("ifc_geometry" if out else "ifc_exact", sum(gl), unit,
                                     "geometry: mesh volume (openings not subtracted unless in the body)",
                                     [_eid(e) for e in els]))
        return out
    return out
