"""IFC exact reader (ifcopenshell). Intents on .ifc files:

room_net_area, total_net_area_storey, walls_length_storey, walls_volume_storey, walls_side_area_storey,
slabs_volume_storey, doors_on_storey, count_on_storey, count_in_model.

Two independent voters where possible:
  * ifc_quantity : the model's own IfcElementQuantity (Qto_*BaseQuantities / ArchiCAD "BaseQuantities")
  * ifc_geometry : ifcopenshell.geom meshes (footprint area / volume / length from the body)
Units are read from IfcUnitAssignment (LENGTHUNIT / AREAUNIT / VOLUMEUNIT); never assumed.

Counting rule (derived from the data): an element counts for a storey only when it is DIRECTLY contained in it
(IfcRelContainedInSpatialStructure). Parts that are aggregated under a parent (e.g. 564 of 579 IfcStair "RISER-n"
children in molio) are not counted. IfcSpace belongs to a storey through IfcRelAggregates.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any, Optional

try:  # keep the rest of the package importable without ifcopenshell
    import ifcopenshell
    import ifcopenshell.util.unit as _unit
    HAVE_IFC = True
except ImportError:  # pragma: no cover
    ifcopenshell = None
    HAVE_IFC = False


def norm(s: Any) -> str:
    """NFKC + casefold + whitespace squeeze (storey and room matching)."""
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"\s+", " ", s.casefold()).strip()


# element word -> IFC class (English + the question languages seen: et, da, de, fi, sv, fr, it)
ELEMENT_WORDS: dict[str, tuple[str, ...]] = {
    "IfcDoor": ("door", "doors", "ust", "døre", "dør", "türen", "tür", "portes", "porte", "porti", "ovea", "ovi",
                "dörrar", "puertas"),
    "IfcWindow": ("window", "windows", "akent", "aken", "vinduer", "vindue", "fenster", "fenêtres", "finestre",
                  "ikkunaa", "ikkuna", "fönster"),
    "IfcSpace": ("spaces", "space", "rooms", "room", "ruumi", "ruum", "rum", "räume", "raum", "pièces", "locali",
                 "tilaa", "huonetta", "rum"),
    "IfcWall": ("walls", "wall", "seina", "seinad", "vægge", "væg", "wände", "wand", "murs", "muri", "seinää",
                "väggar"),
    "IfcColumn": ("columns", "column", "posti", "post", "søjler", "søjle", "stützen", "stütze", "poteaux",
                  "pilastri", "pylvästä", "pelare"),
    "IfcBeam": ("beams", "beam", "tala", "talad", "bjælker", "bjælke", "träger", "poutres", "travi", "palkkia",
                "balkar"),
    "IfcStair": ("stairs", "stair", "treppi", "trepid", "trapper", "trappe", "treppen", "treppe", "escaliers",
                 "scale", "portaita", "trappor"),
    "IfcSlab": ("slabs", "slab", "plaati", "dæk", "decken", "dalles", "solai"),
    "IfcRailing": ("railings", "railing", "käsipuud", "gelænder", "geländer"),
    "IfcRoof": ("roofs", "roof", "katused", "tage", "dächer"),
    "IfcSanitaryTerminal": ("sanitary", "fixtures"),
    "IfcFurnishingElement": ("furniture",),
}
_WORD2CLASS = {w: c for c, ws in ELEMENT_WORDS.items() for w in ws}


def element_class_from_text(question: str, element: Optional[str] = None) -> Optional[str]:
    """Resolve the element class from the params.element text if present, else scan the question tokens."""
    if element:
        for tok in re.findall(r"[^\W\d_]+", norm(element)):
            if tok in _WORD2CLASS:
                if tok in ("fixtures", "sanitary"):
                    return "IfcSanitaryTerminal"
                return _WORD2CLASS[tok]
    qs = re.sub(r"['‘’“”«»„‚][^'‘’“”«»„‚]*['‘’“”«»„‚]", " ", question)  # drop the quoted names
    for tok in re.findall(r"[^\W\d_]+", norm(qs)):
        if tok in _WORD2CLASS and tok not in ("fixtures", "sanitary"):
            if _WORD2CLASS[tok] == "IfcSpace" and tok in ("space",):
                continue
            return _WORD2CLASS[tok]
    return None


def quoted_names(question: str) -> list[str]:
    """Names inside quotes of any style: 'x', "x", „x“, «x», ‘x’, “x”."""
    out = []
    for m in re.finditer(r"'([^']+)'|“([^”]+)”|„([^“”]+)[“”]|«\s*([^»]+?)\s*»|‘([^’]+)’|\"([^\"]+)\"", question):
        g = next((x for x in m.groups() if x), None)
        if g:
            out.append(g)
    return out


class IfcIndex:
    """Parsed model: storeys, direct contents, spaces by storey, unit scales. Cached per file."""

    def __init__(self, path: str):
        self.path = path
        self.m = ifcopenshell.open(path)
        self.schema = self.m.schema
        self.len_scale = self._scale("LENGTHUNIT")
        self.area_scale = self._scale("AREAUNIT")
        self.vol_scale = self._scale("VOLUMEUNIT")
        self.storeys = list(self.m.by_type("IfcBuildingStorey"))
        self.direct: dict[int, list] = {s.id(): [] for s in self.storeys}
        for rel in self.m.by_type("IfcRelContainedInSpatialStructure"):
            sid = rel.RelatingStructure.id()
            if sid in self.direct:
                self.direct[sid].extend(rel.RelatedElements)
        self.spaces: dict[int, list] = {s.id(): [] for s in self.storeys}
        for sp in self.m.by_type("IfcSpace"):
            st = self._space_storey(sp)
            if st is not None and st.id() in self.spaces:
                self.spaces[st.id()].append(sp)
        self._geom_cache: dict[int, Any] = {}

    def _scale(self, unit_type: str) -> float:
        try:
            return float(_unit.calculate_unit_scale(self.m, unit_type))
        except TypeError:
            return float(_unit.calculate_unit_scale(self.m))
        except Exception:
            return 1.0

    @staticmethod
    def _space_storey(sp):
        for rel in getattr(sp, "Decomposes", ()) or ():
            obj = rel.RelatingObject
            while obj is not None and not obj.is_a("IfcBuildingStorey"):
                dec = getattr(obj, "Decomposes", ()) or ()
                obj = dec[0].RelatingObject if dec else None
            if obj is not None:
                return obj
        for rel in getattr(sp, "ContainedInStructure", ()) or ():
            if rel.RelatingStructure.is_a("IfcBuildingStorey"):
                return rel.RelatingStructure
        return None

    def storey(self, name: str):
        n = norm(name)
        for s in self.storeys:
            if norm(s.Name) == n:
                return s
        for s in self.storeys:
            if norm(s.LongName or "") == n:
                return s
        return None

    def elements(self, storey, cls: str) -> list:
        if cls == "IfcSpace":
            return list(self.spaces.get(storey.id(), []))
        return [e for e in self.direct.get(storey.id(), []) if e.is_a(cls)]

    def model_elements(self, cls: str) -> list:
        if cls == "IfcSanitaryTerminal" and self.schema == "IFC2X3":
            cls = "IfcFlowTerminal"      # IFC2X3 has no IfcSanitaryTerminal; sanitary fixtures are IfcFlowTerminal
        els = self.m.by_type(cls)
        if cls in ("IfcStair", "IfcWall", "IfcBeam", "IfcColumn", "IfcSlab", "IfcDoor", "IfcWindow"):
            # same top-level rule as per-storey counts: drop aggregated children
            els = [e for e in els if not getattr(e, "Decomposes", None)]
        return els

    # ---- model's own quantities -------------------------------------------------------------------------------
    def quantity(self, el, qname: str) -> Optional[float]:
        """Value of quantity `qname` in SI (m, m2, m3), from the first IfcElementQuantity that holds it.
        Prefers Qto_* sets, then ArchiCAD 'BaseQuantities'."""
        sets = []
        for rel in getattr(el, "IsDefinedBy", ()) or ():
            if rel.is_a("IfcRelDefinesByProperties"):
                d = rel.RelatingPropertyDefinition
                if d is not None and d.is_a("IfcElementQuantity"):
                    sets.append(d)
        sets.sort(key=lambda d: 0 if (d.Name or "").startswith("Qto_") else 1 if d.Name == "BaseQuantities" else 2)
        for d in sets:
            for q in d.Quantities or ():
                if q.Name == qname:
                    v = q[3]
                    if v is None:
                        continue
                    if q.is_a("IfcQuantityLength"):
                        return float(v) * self.len_scale
                    if q.is_a("IfcQuantityArea"):
                        return float(v) * self.area_scale
                    if q.is_a("IfcQuantityVolume"):
                        return float(v) * self.vol_scale
                    return float(v)
        return None

    # ---- geometry -----------------------------------------------------------------------------------------------
    def mesh(self, el):
        """(verts Nx3, faces Mx3) in model length unit converted to metres, world coordinates."""
        import numpy as np
        import ifcopenshell.geom as geom
        if el.id() in self._geom_cache:
            return self._geom_cache[el.id()]
        st = geom.settings()
        st.set("use-world-coords", True)
        res = None
        try:
            sh = geom.create_shape(st, el)
            v = np.array(sh.geometry.verts, dtype=float).reshape(-1, 3)
            f = np.array(sh.geometry.faces, dtype=int).reshape(-1, 3)
            res = (v, f)
        except Exception:
            res = None
        self._geom_cache[el.id()] = res
        return res

    def geom_floor_area(self, sp) -> Optional[float]:
        """Footprint area (m2): sum of projected area of downward-facing triangles of the space body."""
        import numpy as np
        mm = self.mesh(sp)
        if mm is None:
            return None
        v, f = mm
        if len(f) == 0:
            return None
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        n = np.cross(b - a, c - a)
        nz = n[:, 2]
        # ifcopenshell.geom already returns metres (it applies the unit scale) for world coords
        down = nz < 0
        area = 0.5 * np.abs(nz[down]).sum()
        up = nz > 0
        area_up = 0.5 * np.abs(nz[up]).sum()
        return float(min(area, area_up) if area_up > 0 and area > 0 else max(area, area_up))

    def geom_volume(self, el) -> Optional[float]:
        mm = self.mesh(el)
        if mm is None:
            return None
        v, f = mm
        if len(f) == 0:
            return None
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        import numpy as np
        vol = np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0
        return float(abs(vol))


@lru_cache(maxsize=4)
def load(path: str) -> "IfcIndex":
    return IfcIndex(path)
