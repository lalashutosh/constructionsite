"""Vision label reader: an LLM TRANSCRIBES the room labels printed on a plan; code maps them through the glossary and
counts. The model reads text (a better OCR for faint / rotated / hand-lettered labels); it never produces the count.

    read_labels(image_bgr, llm, sha) -> [{"text", "room_type", "x", "y"}]   (cached per sha256 in cache/labels/)
    count(labels, intent) -> (n, [label texts]) or None when the intent is not label-defined

Used as an independent voter for label-defined counts (bedrooms = MH labels, saunas = S, wc_rooms = WC, ...).
"""
from __future__ import annotations

import json
import pathlib
import re
from functools import lru_cache
from typing import Optional

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "labels"


@lru_cache(maxsize=1)
def glossary() -> dict:
    return yaml.safe_load((ROOT / "engine" / "glossary.yaml").read_text(encoding="utf-8"))


def glossary_text(max_items: int = 60) -> str:
    """Compact 'ABBR=type' list for prompts (planner, reviewers, label reader)."""
    items = list(glossary()["room_labels"].items())[:max_items]
    return ", ".join(f"{k}={v}" for k, v in items)


def norm_label(text: str) -> str:
    t = (text or "").strip().upper()
    t = re.sub(r"[\d.\-_/]+$", "", t).strip()          # "MH 2", "MH.1", "MH2" -> "MH"
    t = re.sub(r"\s+\d+$", "", t).strip()
    return t


def room_type(text: str) -> Optional[str]:
    return glossary()["room_labels"].get(norm_label(text))


SYSTEM = (
    "You transcribe a floor plan. List EVERY room label printed inside the rooms exactly as written (keep numbers: "
    "'MH 1', 'MH 2'), including faint, rotated or hand-lettered ones; ignore dimensions, sheet titles, legends and "
    "furniture text. Common Nordic abbreviations for reference: {gloss}. Reply with JSON only: "
    '{{"labels": [{{"text": "<as printed>", "x": <0-100 % from left>, "y": <0-100 % from top>}}]}}'
)


def read_labels(image_bgr, llm, sha: str) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sha}.json"
    if f.exists():
        return json.loads(f.read_text())
    import cv2
    h, w = image_bgr.shape[:2]
    s = min(1.0, 1400 / max(h, w))
    img = cv2.resize(image_bgr, (int(w * s), int(h * s))) if s < 1 else image_bgr
    png = cv2.imencode(".png", img)[1].tobytes()
    r = llm.complete_vision(SYSTEM.format(gloss=glossary_text()), "Transcribe the room labels.", png, max_tokens=900)
    m = re.search(r"\{.*\}", r.text or "", re.S)
    labels = []
    if m:
        try:
            for it in json.loads(m.group(0)).get("labels", []):
                t = str(it.get("text", "")).strip()
                if t:
                    labels.append({"text": t, "room_type": room_type(t), "x": it.get("x"), "y": it.get("y")})
        except json.JSONDecodeError:
            pass
    f.write_text(json.dumps(labels))
    return labels


def count(labels: list[dict], intent: str) -> Optional[tuple[int, list[str]]]:
    types = glossary()["intent_room_types"].get(intent)
    if not types:
        return None
    hits = [l["text"] for l in labels if l.get("room_type") in types]
    return len(hits), hits


# glossary room type -> the engine's room subtype words (engine/query/run.py matches these + ROOM_SYNONYMS)
_SUBTYPE = {"living_room": "living", "bathroom": "bathroom", "wc": "wc", "bedroom": "bedroom", "kitchen": "kitchen",
            "sauna": "sauna", "hallway": "hallway", "storage": "storage", "utility": "utility", "wardrobe": "wardrobe",
            "balcony": "balcony", "terrace": "terrace", "dining": "dining", "office": "office", "garage": "garage"}


def name_rooms(facts, labels: list[dict], w: int, h: int, floors: list[dict] | None = None):
    """Copy of facts where each room takes the printed label the vision reader found inside it (and that label's room
    type), plus the floor it is on when the sheet holds several floor plans. Code decides membership (label point inside
    the room polygon); the model only read the text."""
    from shapely.geometry import Point, Polygon
    pts = [(Point(l["x"] / 100 * w, l["y"] / 100 * h), l) for l in labels
           if isinstance(l.get("x"), (int, float)) and isinstance(l.get("y"), (int, float))]
    out = facts.model_copy(deep=True)
    used: set = set()
    for e in out.elements:
        if e.kind != "room" or len(e.polygon) < 3:
            continue
        try:
            poly = Polygon(e.polygon)
        except Exception:  # noqa: BLE001
            continue
        inside = [l for p, l in pts if poly.contains(p)]
        typed = [l for l in inside if l.get("room_type") and id(l) not in used
                 and _smallest_holder(l, out, w, h) is e]
        if typed:
            l = typed[0]
            used.add(id(l))
            e.attrs["label_before"] = e.label
            e.attrs["subtype_before"] = e.subtype
            e.label, e.subtype = l["text"], _SUBTYPE.get(l["room_type"], l["room_type"])
            e.attrs["named_by"] = "vision label reader"
        if floors:
            c = poly.centroid
            for f in floors:
                b = f["box"]
                if b[0] <= c.x <= b[2] and b[1] <= c.y <= b[3]:
                    e.attrs["storey"] = f.get("label") or ""
                    break
    return out


def _smallest_holder(l: dict, facts, w: int, h: int):
    """The smallest room polygon containing label l (overlapping outlines must not all take the same name)."""
    from shapely.geometry import Point, Polygon
    pt = Point(l["x"] / 100 * w, l["y"] / 100 * h)
    best, ba = None, None
    for e in facts.elements:
        if e.kind != "room" or len(e.polygon) < 3:
            continue
        try:
            P = Polygon(e.polygon)
        except Exception:  # noqa: BLE001
            continue
        if P.is_valid and P.contains(pt) and (ba is None or P.area < ba):
            best, ba = e, P.area
    return best
