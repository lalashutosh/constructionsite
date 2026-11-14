"""Fixed query specs: the known intents re-expressed as data. `spec_for(intent, params)` -> spec | None."""
from __future__ import annotations

from typing import Optional

_RL = ["room", "label"]

# the 12 cubicasa intents (mirror engine.count.rules; tests/test_query.py checks equality on cached facts)
CUBICASA: dict = {
    "windows": {"select": "window", "aggregate": "count"},
    "doors": {"select": "door", "aggregate": "count"},  # raster door icons are leaf-only already
    "toilets": {"select": "toilet", "aggregate": "count"},
    "sinks": {"select": "sink", "aggregate": "count"},
    "showers_baths": {"select": "bath", "aggregate": "count", "rules": ["prior_fallback_1"]},
    "saunas": {"select": _RL, "where": {"subtype": "sauna"}, "aggregate": "count", "rules": ["cluster_instances"]},
    "kitchens": {"select": _RL, "where": {"subtype": "kitchen"}, "aggregate": "count",
                 "rules": ["cluster_instances", "kitchenettes_count", "prior_fallback_not1"]},
    "bedrooms": {"select": _RL, "where": {"subtype": "bedroom"}, "aggregate": "count", "rules": ["cluster_instances"]},
    "wc_rooms": {"select": _RL, "where": {"subtype": "wc"}, "aggregate": "count", "rules": ["cluster_instances"]},
    "bathrooms": {"select": _RL, "where": {"subtype": "bathroom"}, "aggregate": "count",
                  "rules": ["cluster_instances", "separate_wc_not_bathroom", "prior_fallback_not1"]},
    "balconies": {"select": _RL, "where": {"subtype": "balcony"}, "aggregate": "count",
                  "rules": ["cluster_instances", "glazed_balconies_count"]},
    "floors": {"select": "floor_blob", "aggregate": "count", "rules": ["min_one"]},
}

_ELEMENT_KIND = {"spaces": "room", "(spaces)": "room", "storeys": "storey", "stairs": "stair"}


def element_kind(name: str) -> str:
    n = name.strip().lower().replace("ifc", "").strip()
    n = n.replace(" (spaces)", "")
    if n in _ELEMENT_KIND:
        return _ELEMENT_KIND[n]
    return n[:-1] if n.endswith("s") and not n.endswith("ss") else n


def spec_for(intent: str, params: Optional[dict] = None, source: Optional[str] = None) -> Optional[dict]:
    p = {k: v for k, v in (params or {}).items() if v}
    if intent in CUBICASA and source in (None, "cubicasa5k"):
        return dict(CUBICASA[intent])
    fixtures = {"toilets": "toilet", "washbasins": "washbasin", "bathtubs": "bathtub", "showers": "shower"}
    if intent in fixtures:
        return {"select": [fixtures[intent], "fixture"], "where": {"subtype": fixtures[intent]}, "aggregate": "count"}
    if intent == "room_labelled" and p.get("label"):
        return {"select": "room", "where": {"label": p["label"]}, "aggregate": "count"}
    if intent == "room_area_labelled" and p.get("label"):
        return {"select": "room", "where": {"label": p["label"]}, "aggregate": "sum_area"}
    if intent == "total_net_area":
        return {"select": "room", "aggregate": "sum_area", "rules": ["exclude_outdoor"]}
    if intent == "apartment_net_area" and p.get("letter"):
        return {"select": "room", "where": {"apartment": p["letter"]}, "aggregate": "sum_area",
                "rules": ["exclude_outdoor"]}
    if intent == "room_area" and (p.get("room") or p.get("label")):
        w = {k: v for k, v in (("id", p.get("room")), ("label", p.get("label"))) if v}
        return {"select": "room", "where": w, "aggregate": "sum_area"}
    if intent == "room_net_area" and p.get("room"):
        w = {"label": p["room"]}
        if p.get("storey"):
            w["storey"] = p["storey"]
        return {"select": "room", "where": w, "aggregate": "sum_area"}
    if intent == "total_net_area_storey" and p.get("storey"):
        return {"select": "room", "where": {"storey": p["storey"]}, "aggregate": "sum_area"}
    if intent == "walls_side_area_storey" and p.get("storey"):
        return {"select": "wall", "where": {"storey": p["storey"]}, "aggregate": "sum_attr", "attr": "side_area_m2"}
    if intent == "walls_length_storey" and p.get("storey"):
        return {"select": "wall", "where": {"storey": p["storey"]}, "aggregate": "sum_length"}
    if intent == "walls_volume_storey" and p.get("storey"):
        return {"select": "wall", "where": {"storey": p["storey"]}, "aggregate": "sum_attr", "attr": "volume_m3"}
    if intent == "slabs_volume_storey" and p.get("storey"):
        return {"select": "slab", "where": {"storey": p["storey"]}, "aggregate": "sum_attr", "attr": "volume_m3"}
    if intent == "doors_on_storey" and p.get("storey"):
        return {"select": "door", "where": {"storey": p["storey"]}, "aggregate": "count"}
    if intent == "count_on_storey" and p.get("element") and p.get("storey"):
        return {"select": element_kind(p["element"]), "where": {"storey": p["storey"]}, "aggregate": "count"}
    if intent == "count_in_model" and p.get("element"):
        return {"select": element_kind(p["element"]), "aggregate": "count"}
    if intent in ("doors", "windows"):
        return {"select": intent[:-1], "aggregate": "count", "rules": ["door_requires_leaf"] if intent == "doors" else []}
    return None
