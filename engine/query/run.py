"""Query engine: `run(spec, facts, px_per_m=None) -> Result` over SheetFacts. No LLM, no network.

shapely handles containment / adjacency / area, networkx (graph.py) the apartment grouping.
Area units: attrs.area_m2 (vector sources in real units) wins; else polygon px area / px_per_m^2 (needs scale)."""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, Optional

from contracts.proof import Element, SheetFacts
from engine.query import rules as R

SCHEMA = json.loads((pathlib.Path(__file__).parent / "schema.json").read_text())
_TOP = set(SCHEMA["properties"])
_WHERE = set(SCHEMA["properties"]["where"]["properties"])
_AGG = set(SCHEMA["properties"]["aggregate"]["enum"])
_GROUP = set(SCHEMA["properties"]["group_by"]["enum"])


class SpecError(ValueError):
    pass


@dataclass
class Result:
    value: Optional[float | int] = None
    unit: str = "count"
    evidence_ids: list[str] = field(default_factory=list)
    rule_applied: list[str] = field(default_factory=list)
    needs_scale: bool = False
    groups: dict[str, Any] = field(default_factory=dict)
    runs: list = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    defaulted: Optional[str] = None  # reason when the value is a prior, not a measurement


def validate(spec: dict, known_kinds: Optional[set[str]] = None) -> dict:
    """Reject unknown keys / aggregates / rules (and unknown element kinds when `known_kinds` is given)."""
    if not isinstance(spec, dict):
        raise SpecError("spec must be an object")
    extra = set(spec) - _TOP
    if extra:
        raise SpecError(f"unknown spec keys: {sorted(extra)}")
    for k in ("select", "aggregate"):
        if k not in spec:
            raise SpecError(f"missing key {k}")
    if spec["aggregate"] not in _AGG:
        raise SpecError(f"unknown aggregate {spec['aggregate']!r}")
    if spec.get("group_by") not in _GROUP:
        raise SpecError(f"unknown group_by {spec.get('group_by')!r}")
    sel = spec["select"]
    sels = [sel] if isinstance(sel, str) else sel
    if not isinstance(sels, list) or not sels or not all(isinstance(s, str) for s in sels):
        raise SpecError("select must be a string or non-empty list of strings")
    if known_kinds is not None:
        bad = [s for s in sels if s != "*" and s not in known_kinds]
        if bad:
            raise SpecError(f"unknown element kinds {bad}; present: {sorted(known_kinds)}")
    where = spec.get("where") or {}
    if not isinstance(where, dict):
        raise SpecError("where must be an object")
    wx = set(where) - _WHERE
    if wx:
        raise SpecError(f"unknown where keys: {sorted(wx)}")
    for key, allowed in (("has", {"kind", "min"}), ("adjacent_to", {"room_type", "label"})):
        sub = where.get(key)
        if sub is not None and (not isinstance(sub, dict) or set(sub) - allowed):
            raise SpecError(f"bad where.{key}")
    if spec["aggregate"] == "sum_attr" and not isinstance(spec.get("attr"), str):
        raise SpecError("sum_attr needs attr")
    for r in spec.get("rules") or []:
        if r not in R.RULES:
            raise SpecError(f"unknown rule {r!r}; known: {sorted(R.RULES)}")
    return spec


def _poly(e: Element):
    from shapely.geometry import Polygon
    pts = list(e.polygon)
    if len(pts) < 3:
        return None
    try:
        p = Polygon(pts)
        return p if p.is_valid else p.buffer(0)
    except Exception:  # noqa: BLE001
        return None


def _eq(a: Optional[str], b: str) -> bool:
    return (a or "").strip().casefold() == b.strip().casefold()


# a room TYPE asked for in words -> the names readers give it (en/fi/de/fr/it) ...
ROOM_SYNONYMS = {
    "bathroom": {"bathroom", "bath", "wc", "toilet", "washroom", "restroom", "kh", "kph", "ph", "pesuh", "sh", "shower",
                 "bad", "bain", "bagno", "wet_room"},
    "bedroom": {"bedroom", "mh", "makuuhuone", "schlafzimmer", "chambre", "camera"},
    "kitchen": {"kitchen", "k", "kk", "keittiö", "küche", "cuisine", "cucina"},
}
ROOM_SYNONYMS["bathrooms"] = ROOM_SYNONYMS["bathroom"]
# ... and the fixtures that make a room that type even when no reader named it (a toilet = a bathroom/WC)
ROOM_BY_FIXTURE = {"bathroom": {"toilet", "shower", "bathtub"}, "bathrooms": {"toilet", "shower", "bathtub"}}


def _rooms_with(facts: SheetFacts, fixture_kinds: set) -> set:
    from shapely.geometry import Point
    pts = []
    for e in facts.elements:
        if e.kind in fixture_kinds and e.polygon:
            xs, ys = [p[0] for p in e.polygon], [p[1] for p in e.polygon]
            pts.append(Point((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
    out = set()
    for r in facts.elements:
        if r.kind != "room":
            continue
        g = _poly(r)
        if g is not None and any(g.contains(p) for p in pts):
            out.add(r.id)
    return out


def _subtype_ok(e: Element, want: str, rules: list[str], wet: Optional[set] = None) -> bool:
    st = (e.subtype or "").casefold()
    w = want.casefold()
    if w in ROOM_SYNONYMS and e.kind == "room":
        if st in ROOM_SYNONYMS[w] or (e.label or "").strip().casefold() in ROOM_SYNONYMS[w]:
            return True
        if wet is not None and e.id in wet:
            return True
    if w == "kitchen" and "kitchenettes_count" in rules:
        return st in R.KITCHEN_ALIASES
    if w == "balcony" and "glazed_balconies_count" in rules:
        return st in R.BALCONY_ALIASES
    return st == w or e.kind.casefold() == w


def select(spec: dict, facts: SheetFacts) -> list[Element]:
    sel = spec["select"]
    kinds = [sel] if isinstance(sel, str) else list(sel)
    rules = list(spec.get("rules") or [])
    where = spec.get("where") or {}
    els = [e for e in facts.elements if "*" in kinds or e.kind in kinds]
    for key in ("room_type", "subtype"):
        if where.get(key):
            want = where[key].casefold()
            wet = _rooms_with(facts, ROOM_BY_FIXTURE[want]) if want in ROOM_BY_FIXTURE else None
            els = [e for e in els if _subtype_ok(e, where[key], rules, wet)]
    if where.get("label"):
        els = [e for e in els if _eq(e.label, where["label"])]
    if where.get("id"):
        els = [e for e in els if e.id == where["id"] or _eq(str(e.attrs.get("number", "")), where["id"])]
    if where.get("storey"):
        els = [e for e in els if _eq(str(e.attrs.get("storey", "")), where["storey"])]
    if where.get("apartment"):
        from engine.query.graph import apartment_of
        amap = apartment_of(facts)
        els = [e for e in els if _eq(str(e.attrs.get("apartment") or amap.get(e.id, "")), where["apartment"])]
    if where.get("has"):
        els = _filter_has(els, where["has"], facts)
    if where.get("adjacent_to"):
        els = _filter_adjacent(els, where["adjacent_to"], facts)
    return els


def _filter_has(els, has, facts):
    from shapely.geometry import Point
    inner = [(e, _poly(e)) for e in facts.elements if e.kind == has["kind"]]
    need = int(has.get("min", 1))
    out = []
    for e in els:
        p = _poly(e)
        if p is None:
            continue
        p = p.buffer(0.08 * (p.area ** 0.5))      # windows/doors sit ON the room outline, not strictly inside
        n = 0
        for ie, ip in inner:
            c = ip.centroid if ip is not None else (Point(ie.polygon[0]) if ie.polygon else None)
            if c is not None and p.contains(c):
                n += 1
        if n >= need:
            out.append(e)
    return out


def _filter_adjacent(els, adj, facts, tol: float = 3.0):
    others = [e for e in facts.elements if e.kind == "room"
              and (not adj.get("room_type") or _eq(e.subtype, adj["room_type"]))
              and (not adj.get("label") or _eq(e.label, adj["label"]))]
    op = [(o, _poly(o)) for o in others]
    out = []
    for e in els:
        p = _poly(e)
        if p is None:
            continue
        if any(o.id != e.id and q is not None and p.distance(q) <= tol for o, q in op):
            out.append(e)
    return out


def _area_m2(e: Element, px_per_m: Optional[float]) -> Optional[float]:
    if "area_m2" in e.attrs:
        return float(e.attrs["area_m2"])
    p = _poly(e)
    if p is None or not px_per_m:
        return None
    return p.area / (px_per_m ** 2)


def _length_m(e: Element, px_per_m: Optional[float]) -> Optional[float]:
    if "length_m" in e.attrs:
        return float(e.attrs["length_m"])
    if "length_px" in e.attrs and px_per_m:
        return float(e.attrs["length_px"]) / px_per_m
    if len(e.polygon) >= 2 and px_per_m:
        from shapely.geometry import LineString
        return LineString(e.polygon).length / px_per_m
    return None


def _group_key(e: Element, key: str, amap) -> str:
    if key == "storey":
        return str(e.attrs.get("storey", ""))
    if key == "subtype":
        return e.subtype or ""
    if key == "label":
        return e.label or ""
    return str(e.attrs.get("apartment") or amap.get(e.id, ""))


def _agg(els: list[Element], spec: dict, facts: SheetFacts, px_per_m, res: Result):
    agg = spec["aggregate"]
    rules = list(spec.get("rules") or [])
    if agg == "count":
        if "cluster_instances" in rules:
            return R.cluster_count(els, facts)
        return len(els)
    if agg == "list":
        return [e.label or e.id for e in els]
    vals: list[float] = []
    for e in els:
        if agg in ("sum_area", "max_area", "avg_area"):
            v = _area_m2(e, px_per_m)
        elif agg == "sum_length":
            v = _length_m(e, px_per_m)
        else:
            raw = e.attrs.get(spec["attr"])
            v = float(raw) if isinstance(raw, (int, float)) else None
            if v is None:
                res.notes.append(f"'{spec['attr']}' is not known for {e.kind} elements")
        if v is None:
            res.needs_scale = True
            continue
        vals.append(v)
    if not vals and els:
        return None                     # elements exist but none had the measure: unknown, not zero
    if agg == "max_area":
        return max(vals) if vals else 0.0
    if agg == "avg_area":
        return float(sum(vals) / len(vals)) if vals else None
    return float(sum(vals))


def run(spec: dict, facts: SheetFacts, px_per_m: Optional[float] = None) -> Result:
    validate(spec)
    rules = list(spec.get("rules") or [])
    els = select(spec, facts)
    unit = {"sum_area": "m2", "max_area": "m2", "avg_area": "m2", "sum_length": "m",
            "argmax_area": "label", "argmin_area": "label"}.get(spec["aggregate"], "count")
    if spec["aggregate"] == "sum_attr":
        unit = next((u for suf, u in (("_m3", "m3"), ("_m2", "m2"), ("_m", "m")) if spec["attr"].endswith(suf)), "count")
    res = Result(unit=unit)
    for r in rules:
        els, note = R.RULES[r](els, facts)
        res.rule_applied.append(r)
        if note:
            res.notes.append(note)
    res.evidence_ids = [e.id for e in els]
    rt = ((spec.get("where") or {}).get("room_type") or "").casefold()
    if rt in ROOM_BY_FIXTURE and els:
        res.notes.append(f"{rt} = rooms named bath/WC/KH/PH/… or containing a toilet, shower or bathtub")
    if not els and spec["aggregate"] not in ("count", "list"):
        w = spec.get("where") or {}
        what = w.get("room_type") or w.get("subtype") or w.get("label") or spec.get("select")
        res.notes.append(f"no matching elements: no {what} recognised on this drawing")
        res.value = None                          # a sum over nothing is 'not found', not a confident 0
        return res
    if spec["aggregate"] in ("argmax_area", "argmin_area"):
        scored = [(a, e) for e in els if (a := _area_m2(e, px_per_m)) is not None]
        unit_word = "m2"
        if not scored:                     # no scale: comparing rooms of ONE drawing needs only relative areas
            scored = [(p.area, e) for e in els if (p := _poly(e)) is not None and p.area > 0]
            unit_word = "px2 (relative, no scale needed to compare)"
        if not scored:
            res.needs_scale = bool(els)
            return res
        a, e = (max if spec["aggregate"] == "argmax_area" else min)(scored, key=lambda t: t[0])
        num = e.attrs.get("number")
        name = e.label or (e.subtype or e.kind).replace("_", " ")
        same = [x for _, x in scored if (x.label or x.subtype) == (e.label or e.subtype)]
        if len(same) > 1 and not num:           # several rooms share the name: say which one (rank by area)
            order = sorted(same, key=lambda x: _area_m2(x, px_per_m) or (_poly(x).area if _poly(x) else 0))
            name = f"{name} #{order.index(e) + 1} of {len(same)} (by size)"
        size = f", {a:.1f} m²" if unit_word == "m2" else ""
        res.value = f"{name}" + (f" ({num})" if num and num != e.label else "") + size
        res.notes.append(f"{len(scored)} candidates compared by area; chosen {a:.2f} {unit_word}")
        res.groups = {"area": round(a, 2)}
        res.evidence_ids = [e.id]
        return res
    if spec.get("group_by"):
        from engine.query.graph import apartment_of
        amap = apartment_of(facts) if spec["group_by"] == "apartment" else {}
        buckets: dict[str, list[Element]] = {}
        for e in els:
            buckets.setdefault(_group_key(e, spec["group_by"], amap), []).append(e)
        res.groups = {k: _agg(v, spec, facts, px_per_m, res) for k, v in sorted(buckets.items())}
    res.value = _agg(els, spec, facts, px_per_m, res)
    if spec["aggregate"] == "count":
        if "min_one" in rules:
            res.value = max(1, int(res.value))
        if "prior_fallback_1" in rules and res.value == 0:
            res.value, res.defaulted = 1, "no detection; dev-median prior"
        if "prior_fallback_not1" in rules and res.value != 1:
            res.defaulted = f"detector said {res.value}; dev-median prior"
            res.value = 1
        res.value = int(res.value)
        res.runs = [res.value]
    if res.needs_scale and spec["aggregate"] in ("sum_area", "max_area", "avg_area", "sum_length") and not px_per_m:
        res.value = None
    return res
