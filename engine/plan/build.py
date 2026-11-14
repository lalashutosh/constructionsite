"""Build plan for one drawing: what building is this, what do we need to get, and in which order do we build.

    plan(facts, vibe="standard", scale=None, needs=None) -> dict   (shape documented in api/main.py GET /api/plan)

Every quantity is (basis from the drawing) x (rate from the chosen style or a fixed rule), with its formula in words
and a Tag: drawn (counted/measured on the drawing), defaulted (a style assumption entered the number), open (an input
is missing, e.g. no scale or no IT load: the UI asks for it). Nothing is invented: a missing basis gives qty None.
"""
from __future__ import annotations

import math
import pathlib
import re
from functools import lru_cache
from typing import Any, Optional

import yaml

from contracts.proof import SheetFacts
from engine.decide.vibe import VIBE_NAMES, load_vibe
from engine.takeoff import materials as M

HERE = pathlib.Path(__file__).resolve().parent
VIBE_BLURB = {"budget": "Code minimums, fewest coats, economy finishes",
              "standard": "Typical new-build spec",
              "premium": "Generous lighting, more sockets, larger tiles, oak floors",
              "nordic": "Bright, warm, durable natural materials"}
WET = {"bathroom", "bath", "wc", "sauna", "shower", "toilet"}
OPENING_M2 = {"door": 0.9 * 2.1, "window": 1.2 * 1.2}


@lru_cache(maxsize=1)
def _spec() -> dict:
    return yaml.safe_load((HERE / "types.yaml").read_text(encoding="utf-8"))


def _vv(vibe: dict, key: str, default=None):
    v = vibe.get(key)
    return v.get("value", default) if isinstance(v, dict) else (v if v is not None else default)


def _poly(e):
    from shapely.geometry import Polygon
    try:
        p = Polygon(e.polygon)
        return p if p.is_valid and p.area > 0 else p.buffer(0)
    except Exception:  # noqa: BLE001
        return None


def basis(facts: SheetFacts, vibe: dict, px_per_m: Optional[float], scale_tag: str, needs: dict) -> dict:
    els = facts.elements
    rooms = [e for e in els if e.kind == "room" and not e.attrs.get("outdoor") and (e.subtype or "") != "outdoor"]
    kinds: dict[str, int] = {}
    for e in els:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    B: dict[str, dict] = {}

    def put(k, v, unit, tag, src):
        B[k] = {"value": v, "unit": unit, "tag": tag if v is not None else "open", "source": src}

    sub = lambda e: (e.subtype or "").lower()
    lab = lambda e: (e.label or "").lower()
    put("rooms", len(rooms), "count", "drawn", "room polygons found on the drawing")
    put("kitchens", sum(1 for e in rooms if sub(e) == "kitchen" or "kitchen" in lab(e)), "count", "drawn",
        "rooms read as kitchen")
    put("doors", kinds.get("door", 0), "count", "drawn", "door elements")
    put("windows", kinds.get("window", 0), "count", "drawn", "window elements")
    put("toilets", kinds.get("toilet", 0), "count", "drawn", "toilet symbols")
    put("sinks", kinds.get("sink", 0), "count", "drawn", "basin/sink symbols")
    put("showers", kinds.get("shower", 0) + kinds.get("bathtub", 0), "count", "drawn", "shower and bath symbols")
    apts = {e.attrs.get("apartment") for e in rooms if e.attrs.get("apartment")}
    put("apartments", len(apts) if apts else 1, "count", "drawn" if apts else "defaulted",
        "apartment outlines on the drawing" if apts else "no apartment outlines: assumed one unit")

    # areas: metres from exact files, pixels through a scale for scans, else open
    def area_m2(e):
        if "area_m2" in e.attrs:
            return float(e.attrs["area_m2"]), "drawn"
        p = _poly(e)
        if p is None or not px_per_m:
            return None, "open"
        return p.area / px_per_m ** 2, scale_tag

    def perim_m(e):
        p = _poly(e)
        if p is None:
            return None
        if "area_m2" in e.attrs:
            return p.length            # DXF units are metres
        return p.length / px_per_m if px_per_m else None

    areas = [area_m2(e) for e in rooms]
    tag_area = "drawn" if areas and all(t == "drawn" for _, t in areas) else (scale_tag if px_per_m else "open")
    floor = sum(a for a, _ in areas if a is not None) if areas and all(a is not None for a, _ in areas) else None
    src_area = "sum of room areas" + ("" if tag_area == "drawn" else {
        "specified": " (scale from measurements printed on the drawing)", "chosen": " (scale from your measurement)",
        "defaulted": " (scale estimated from a typical 0.9 m door)"}.get(scale_tag, " (scale: " + scale_tag + ")"))
    put("floor_area_m2", round(floor, 2) if floor is not None else None, "m2", tag_area,
        src_area if floor is not None else "needs a scale: tap a door or type a dimension")
    wet = sum(a for (a, _), e in zip(areas, rooms) if a is not None and (sub(e) in WET or any(w in lab(e) for w in WET)))
    put("wet_area_m2", round(wet, 2) if floor is not None else None, "m2", tag_area, "bathroom/WC/sauna rooms")
    put("dry_area_m2", round(floor - wet, 2) if floor is not None else None, "m2", tag_area, "floor area minus wet rooms")
    perims = [perim_m(e) for e in rooms]
    per_sum = sum(perims) if perims and all(p is not None for p in perims) else None
    foot = None
    if floor is not None:
        from shapely.ops import unary_union
        polys = [p for p in (_poly(e) for e in rooms) if p is not None]
        u = unary_union([p.buffer(0.15 if "area_m2" in (rooms[0].attrs if rooms else {}) else
                                  0.15 * (px_per_m or 1)) for p in polys]) if polys else None
        if u is not None:
            k2 = 1.0 if (rooms and "area_m2" in rooms[0].attrs) else (1 / px_per_m ** 2)
            foot = u.area * k2
            k1 = 1.0 if (rooms and "area_m2" in rooms[0].attrs) else (1 / px_per_m)
            put("footprint_perimeter_m", round(u.length * k1, 2), "m", tag_area, "outline of all rooms + wall allowance")
    put("footprint_m2", round(foot, 2) if foot is not None else None, "m2", tag_area,
        "outline of all rooms incl. 0.15 m wall allowance")
    h = float(_vv(vibe, "ceiling_height_m", 2.5))
    put("ceiling_height_m", h, "m", "defaulted", "from the chosen style")
    if per_sum is not None and B.get("footprint_perimeter_m"):
        wall_len = (per_sum + B["footprint_perimeter_m"]["value"]) / 2
        put("wall_length_m", round(wall_len, 2), "m", tag_area, "(room perimeters + outline) / 2")
        put("wall_area_m2", round(wall_len * h, 2), "m2", "defaulted", "wall length x ceiling height")
        put("room_wall_area_m2", round(per_sum * h, 2), "m2", "defaulted", "room perimeters x ceiling height")
        openings = B["doors"]["value"] * OPENING_M2["door"] * 2 + B["windows"]["value"] * OPENING_M2["window"]
        try:
            pl = M.paint_litres(per_sum, h, openings, int(_vv(vibe, "paint_coats", 2)),
                                float(_vv(vibe, "paint_coverage_m2_per_l", 10)))
            put("paint_l", round(pl, 1), "l", "defaulted", "coats x (room perimeters x height - openings) / coverage")
        except ValueError:
            put("paint_l", None, "l", "open", "openings exceed wall area: check scale")
    else:
        for k in ("wall_length_m", "wall_area_m2", "room_wall_area_m2", "paint_l"):
            put(k, None, "m", "open", "needs a scale")
    if floor is not None:
        put("lights", M.lights_count(floor, float(_vv(vibe, "lux_target", 300)), float(_vv(vibe, "lumens_per_fitting", 1500)),
                                     float(_vv(vibe, "utilisation_factor", 0.6))), "count", "defaulted",
            "lux x area / (lumens x utilisation)")
        ts = _vv(vibe, "tile_size_m", [0.3, 0.3])
        put("wet_tiles", M.tiles_count(wet, float(_vv(vibe, "tile_waste_frac", 0.1)), float(ts[0]) * float(ts[1]))
            if wet else 0, "count", "defaulted", f"wet area x (1+waste) / {ts[0]}x{ts[1]} m tile")
    else:
        put("lights", None, "count", "open", "needs a scale")
        put("wet_tiles", None, "count", "open", "needs a scale")
    put("it_load_kw", float(needs["it_load_kw"]) if needs.get("it_load_kw") else None, "kW",
        "chosen" if needs.get("it_load_kw") else "open", "your input" if needs.get("it_load_kw") else "needs your input")
    return B


def classify(facts: SheetFacts, B: dict) -> dict:
    text = " ".join(f"{e.label or ''} {e.subtype or ''}" for e in facts.elements if e.kind in ("room", "label")).lower()
    S = _spec()["types"]
    ev: list[str] = []
    for tid in ("data_centre", "office"):
        hits = [w for w in S[tid]["signals"]["labels"] if re.search(rf"\b{re.escape(w)}", text)]
        if hits:
            ev.append(f"room labels mention {', '.join(hits[:3])}")
            return {"type": tid, "label": S[tid]["label"], "confidence": "high" if len(hits) > 1 else "medium",
                    "evidence": ev}
    apts = B["apartments"]
    if apts["tag"] == "drawn" and apts["value"] >= 2:
        ev.append(f"{apts['value']} apartment outlines on this floor")
        if B["kitchens"]["value"]:
            ev.append(f"{B['kitchens']['value']} kitchens")
        return {"type": "apartment_building", "label": S["apartment_building"]["label"],
                "confidence": "high" if B["kitchens"]["value"] >= 2 else "medium", "evidence": ev}
    resid = [k for k in ("kitchens", "toilets", "showers") if B[k]["value"]]
    if B["kitchens"]["value"] >= 3:          # 2 can be one kitchen split by a scan reader; outlines decide above
        return {"type": "apartment_building", "label": S["apartment_building"]["label"], "confidence": "medium",
                "evidence": [f"{B['kitchens']['value']} kitchens on one floor, no apartment outlines drawn"]}
    if resid or re.search(r"\b(bedroom|sauna|living|makuuhuone|oh|mh)\b", text):
        ev = [f"{B[k]['value']} {k}" for k in resid] or ["residential room names"]
        return {"type": "dwelling", "label": S["dwelling"]["label"],
                "confidence": "high" if len(resid) >= 2 else "medium", "evidence": ev}
    return {"type": "unknown", "label": "Unknown building type", "confidence": "low",
            "evidence": ["no kitchens, wet rooms or telling room names were found"]}


def plan(facts: SheetFacts, vibe: str = "standard", px_per_m: Optional[float] = None, scale_tag: str = "open",
         needs: Optional[dict] = None, counts: Optional[dict] = None) -> dict:
    """counts: {basis_key: (value, tag, source)} from the exact answers (the same numbers the Findings show)."""
    vibe = vibe if vibe in VIBE_NAMES else "standard"
    V = load_vibe(vibe)
    B = basis(facts, V, px_per_m, scale_tag, needs or {})
    for k, (v, t, src) in (counts or {}).items():
        if v is not None:
            B[k] = {"value": v, "unit": "count", "tag": t, "source": src}
    bt = classify(facts, B)
    S = _spec()
    lists = list(S["checklist"]["common"])
    if bt["type"] in ("apartment_building", "dwelling", "unknown"):
        lists += S["checklist"]["residential"]
    elif bt["type"] == "data_centre":
        lists += S["checklist"]["data_centre"]
    step_ids = S["types"].get(bt["type"], S["types"]["dwelling"])["steps"]
    checklist = []
    for c in lists:
        if c["step"] not in step_ids:
            continue
        b = B.get(c["per"], {"value": None, "tag": "open"})
        rate = c["rate"][vibe] if isinstance(c["rate"], dict) else c["rate"]
        qty, tag = None, "open"
        if b["value"] is not None:
            q = float(b["value"]) * float(rate)
            qty = int(math.ceil(q - 1e-9)) if c["unit"] in ("pcs", "sets") else round(q, 1)
            pure_count = (not isinstance(c["rate"], dict)) and float(rate) == 1.0
            tag = b["tag"] if (pure_count or b["tag"] == "open") else "defaulted"
        checklist.append({"id": c["id"], "group": c["group"], "item": c["item"], "qty": qty, "unit": c["unit"],
                          "tag": tag, "basis": c["basis"] + (f" (rate {rate} for {vibe})" if isinstance(c["rate"], dict) else ""),
                          "step": c["step"], "per": c["per"]})
    steps = []
    for n, sid in enumerate(step_ids, 1):
        d = S["steps"][sid]
        steps.append({"n": n, "id": sid, "title": d["title"], "why": d["why"], "phase": d["phase"],
                      "needs": [x for x in d.get("needs", []) if x in step_ids],
                      "items": [c["id"] for c in checklist if c["step"] == sid]})
    return {"building": bt, "vibe": vibe,
            "vibes": [{"id": v, "label": v.capitalize(), "blurb": VIBE_BLURB.get(v, "")} for v in VIBE_NAMES],
            "basis": B, "checklist": checklist, "steps": steps,
            "open_inputs": sorted({c["per"] for c in checklist if c["qty"] is None})}
