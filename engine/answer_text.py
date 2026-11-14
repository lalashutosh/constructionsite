"""One plain sentence per answer, built by code from the computed value (no LLM, so the number in the sentence is
always the number that was computed). Examples:
  doors 6            -> "There are 6 doors."
  bedrooms 1         -> "There is 1 bedroom."
  sum_area bathroom  -> "The bathrooms cover 7.0 m² in total."
  argmax_area room   -> "The largest room is the kitchen."
  greater windows/doors -> "No: 6 windows vs 6 doors."
"""
from __future__ import annotations

import re
from typing import Optional

NOUN = {  # intent -> (singular, plural)
    "doors": ("door", "doors"), "windows": ("window", "windows"), "bedrooms": ("bedroom", "bedrooms"),
    "toilets": ("toilet", "toilets"), "sinks": ("sink or basin", "sinks and basins"), "kitchens": ("kitchen", "kitchens"),
    "bathrooms": ("bathroom", "bathrooms"), "saunas": ("sauna", "saunas"), "balconies": ("balcony", "balconies"),
    "wc_rooms": ("separate WC room", "separate WC rooms"), "showers_baths": ("shower or bath", "showers and baths"),
    "floors": ("floor", "floors"), "apartments": ("apartment", "apartments"), "washbasins": ("washbasin", "washbasins"),
    "bathtubs": ("bathtub", "bathtubs"), "showers": ("shower", "showers"), "doors_on_storey": ("door", "doors"),
    "room_labelled": ("room with that label", "rooms with that label"),
}
AREA_PHRASE = {"apartment_net_area": "The apartment's net floor area is", "total_net_area": "The total net floor area is",
               "room_area": "The room's area is", "room_area_labelled": "Those rooms cover", "room_net_area": "The room's net area is",
               "total_net_area_storey": "The storey's net floor area is"}
KIND_UNIT = {"m2": "m²", "m3": "m³", "m": "m"}


def _plural(word: str) -> str:
    if word.endswith("y") and not word.endswith(("ay", "ey", "oy")):
        return word[:-1] + "ies"
    return word if word.endswith("s") else word + "s"


def _what(spec: dict) -> tuple[str, str]:
    """(singular, plural) for what a query_spec selects: 'room' + room_type bathroom -> bathroom(s)."""
    sel = spec.get("select")
    sel = sel if isinstance(sel, str) else " and ".join(sel or [])
    w = spec.get("where") or {}
    base = (w.get("room_type") or w.get("subtype") or sel or "item").replace("_", " ")
    if sel == "room" and (w.get("room_type") or w.get("subtype")):
        base = base if base.endswith(("room", "kitchen", "hall", "sauna", "storage")) else base
    if w.get("label"):
        base = f"{sel} labelled '{w['label']}'"
    return base, _plural(base) if " and " not in base else base


def _num(v, unit: Optional[str]) -> str:
    u = KIND_UNIT.get(unit or "", unit or "")
    return f"{float(v):.1f} {u}".strip()


def sentence(po) -> Optional[str]:
    v, kind, intent, spec = po.value, po.kind, po.intent or "", po.query_spec
    if v is None:
        return f"I can't answer this from the drawing: {po.refusal}." if po.refusal else None
    if spec and "parts" in spec and isinstance(v, str) and v in ("Yes", "No"):
        parts = re.findall(r"part\d+=([^,]+)", " ".join(n for n in po.notes if n.startswith("query parts")))
        names = [_what(s)[1] for s in spec["parts"][:2]]
        if len(parts) >= 2 and len(names) == 2:
            return f"{v}: {parts[0].strip()} {names[0]} vs {parts[1].strip()} {names[1]}."
        return f"{v}."
    if spec and "parts" in spec and spec.get("combine") == "ratio" and isinstance(v, (int, float)):
        a, b = (_what(spec["parts"][0])[1], _what(spec["parts"][1])[1])
        return f"The {a} are {float(v) * 100:.1f}% of the {b}" + (" (by area)." if spec["parts"][0].get("aggregate") == "sum_area" else ".")
    if spec and "parts" in spec and spec.get("combine") == "difference" and isinstance(v, (int, float)):
        a, b = (_what(spec["parts"][0])[1], _what(spec["parts"][1])[1])
        n = abs(int(v)) if float(v).is_integer() else abs(v)
        if n == 0:
            return f"There are as many {a} as {b}."
        word = _what(spec["parts"][0])[0] if n == 1 else a
        return f"There {'is' if n == 1 else 'are'} {n} {'more' if v > 0 else 'fewer'} {word} than {b}."
    if spec and spec.get("aggregate") in ("argmax_area", "argmin_area"):
        sing, _ = _what(spec)
        which = "largest" if spec["aggregate"] == "argmax_area" else "smallest"
        name = str(v)
        if "#" in name or "(" in name:
            return f"The {which} {sing} is {name}."
        return f"The {which} {sing} is the {name.lower() if name.islower() or ' ' not in name else name}."
    if kind == "count":
        n = int(v)
        if spec and "aggregate" in spec:
            sing, plur = _what(spec)
        elif intent in NOUN:
            sing, plur = NOUN[intent]
        else:                                     # e.g. count_in_model: take the object from the question
            m = re.search(r"how many ([a-zäöüé]+)", po.question.lower())
            plur = m.group(1) if m else "items"
            sing = plur[:-1] if plur.endswith("s") else plur
            if "model" in intent:
                plur, sing = f"{plur} in the model", f"{sing} in the model"
        if n == 0:
            return f"No {plur} found on this drawing."
        return f"There is 1 {sing}." if n == 1 else f"There are {n} {plur}."
    if kind in ("area", "length", "volume") and isinstance(v, (int, float)):
        if spec and "aggregate" in spec:
            sing, plur = _what(spec)
            if spec["aggregate"] == "avg_area":
                return f"The average {sing} area is {_num(v, po.unit)}."
            return f"The {plur} cover {_num(v, po.unit)} in total." if kind == "area" else f"{_num(v, po.unit)} in total."
        lead = AREA_PHRASE.get(intent, "The answer is")
        return f"{lead} {_num(v, po.unit)}."
    return f"{v}."
