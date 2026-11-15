"""Derived quantities: 'how many 3x3 m tiles do I need for the living room?' -> tiles, not square metres.

Code computes, the LLM never produces the number.
  parse(question)            regex (en, fi, de, fr, it) -> DeriveSpec | None
  from_obj(dict)             validate a `derive` object an LLM planner may emit, against the same schema
  compute(spec, base_value, base_proof) -> Derived   value + sentence + assumptions (+ open decisions)
  answer(engine, path, question, spec, ...)          the hook used by PipelineEngine.ask: run the base-quantity
                                                     question (floor area of the named room) through the normal
                                                     routing, then wrap the result.

Formulas live in engine/takeoff/materials.py (tiles N = ceil(A (1+w) / a_tile); paint V = n (P h - openings) / c;
lights N = ceil(E A / (F u)); carpet strips). Every constant not stated in the question is an Assumption tagged
`defaulted` with source 'code table v1'; a constant stated in the question is tagged `chosen`.
"""
from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from contracts.proof import Assumption, Decision, Interval, Option, Tag, Tier
from engine.takeoff import materials

Kind = Literal["tiles", "planks", "paint", "carpet", "lights", "skirting"]
SOURCE_TABLE = "code table v1"

# defaults when the question does not say (editable: they are listed as assumptions on every answer)
DEFAULTS = {"waste_frac": 0.10, "coats": 2, "coverage_m2_per_l": 8.0, "height_m": 2.5, "roll_width_m": 4.0,
            "lux": 300.0, "lumens": 1500.0, "utilisation": 0.60}
UNIT_M = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254, "ft": 0.3048}

# ---------------------------------------------------------------- vocabulary (en, fi, de, fr, it)
_W = {
    "tiles": r"tiles?|tiling|laatta\w*|fliese\w*|kachel\w*|carrea\w+|carrelage\w*|piastrell\w+|mattonell\w+",
    "planks": r"planks?|laminate\w*|parquet\w*|floorboards?|floor\s*boards?|lankku\w*|laminaat\w*|parkett\w*|dielen?|lames?|listoni|listelli",
    "paint": r"paint\w*|maali\w*|maalat\w*|farbe\w*|streichen|anstrich\w*|peinture\w*|peindre|vernic\w+|pittur\w+|tinteggi\w+|imbianc\w+",
    "carpet": r"carpet\w*|matto\w*|teppich\w*|moquette\w*|tapis|tappet\w+",
    "lights": r"lights?|light\s+fittings?|light\s+fixtures?|luminaires?|downlights?|lamps?|lighting|valaisim\w+|valo\w*|leuchte\w*|"
              r"beleuchtung|lumi[eè]res?|lampad\w+|lampe\w*|luci|illuminazione",
    "skirting": r"skirting\w*|baseboards?|jalkalist\w+|fu(?:ß|ss)leiste\w*|sockelleiste\w*|plinthes?|battiscopa|zoccolin\w+",
}
# first-person need phrases; plain counts of existing fixtures ('how many lights are there') are not derived
_FIRST_PERSON_NEED = (r"tarvitsen|tarvitaan|brauche|ben[oö]tige|j.ai\s+besoin|il\s+me\s+faut|il\s+faut|ho\s+bisogno|mi\s+servono|mi\s+occorrono|"
                      r"servono|occorrono")
_PURCHASE_CUE = (r"\b(?:for|need\w*|required?|buy|order|cover|fit|take|lay|tarvit\w*|tarvi\w*|riitt\w*|menee|kuluu|pour|f[uü]r|brauch\w*|"
                 r"ben[oö]tig\w*|besoin|per|servono|serve|occorr\w+|faut|bisogn\w+)\b")
_HOWMANY = (r"how\s+many|how\s+much|kuinka\s+monta|montako|kuinka\s+paljon|wie\s+viele?|wieviele?|combien|quant[ie]\b|quanto|quante")
_WALL = r"wall\w*|seinä\w*|seina\w*|wand|wände|waende|mur\w*|par[ei]t[ei]|pareti"
_CEIL = r"ceiling\w*|katto\w*|decke\w*|plafond\w*|soffitt\w*"

ROOMS: dict[str, str] = {   # canonical room_type -> pattern (singular/plural, local names, plan abbreviations)
    "living": r"living[\s-]*rooms?|lounges?|sitting[\s-]*rooms?|olohuone\w*|oh\b|wohnzimmer\w*|stube|salon\w*|s[eé]jour|soggiorn\w+",
    "bedroom": r"bed[\s-]*rooms?|makuuhuone\w*|mh\b|schlafzimmer\w*|chambres?|camer[ae]\s+da\s+letto|camer[ae]\b",
    "kitchen": r"kitchens?|keitti[oö]\w*|kk\b|k[uü]che\w*|cuisines?|cucin\w+",
    "bathroom": r"bath[\s-]*rooms?|baths?\b|wet[\s-]*rooms?|washrooms?|kylpyhuone\w*|kph\b|pesuhuone\w*|ph\b|badezimmer\w*|bad\b|"
                r"salles?\s+de\s+bains?|bagn[oi]",
    "wc": r"wc\b|toilets?|restrooms?|vessa\w*|toilette\w*|toilettes",
    "hallway": r"hall(?:way)?s?\b|corridors?|entry\s*hall|eteis\w+|k[aä]yt[aä]v\w+|flur\w*|diele\b|couloirs?|corridoi\w*|ingress\w+",
    "sauna": r"saunas?",
    "balcony": r"balcon\w+|parveke\w*|balkon\w*",
    "storage": r"storage(?:\s+rooms?)?|store[\s-]*rooms?|varasto\w*|vh\b|abstellraum\w*|d[eé]barras|ripostigli\w+",
    "entry": r"entrance\w*|entry\b|porch\w*|tuulikaap\w*|vindfang|eingang\w*|entr[eé]e\w*|ingresso",
    "dining": r"dining(?:\s+rooms?)?|ruokailu\w*|esszimmer\w*|salle\s+[aà]\s+manger|sala\s+da\s+pranzo",
}
ROOM_WORD = {"living": "living room", "bedroom": "bedroom", "kitchen": "kitchen", "bathroom": "bathroom", "wc": "WC",
             "hallway": "hallway", "sauna": "sauna", "balcony": "balcony", "storage": "storage room", "entry": "entrance",
             "dining": "dining room"}
_ALL_ROOMS = (r"whole\s+(?:flat|apartment|house|home|floor|place|unit)|entire\s+(?:flat|apartment|house|home|floor|unit)|all\s+(?:the\s+)?rooms|"
              r"every\s+room|(?:my|the)\s+(?:flat|apartment|house)\b|koko\s+asunto\w*|koko\s+kerros|ganze\w*\s+wohnung|gesamte\w*\s+wohnung|"
              r"tout\s+l.appartement|toute\s+la\s+maison|tutto\s+l.appartamento|intero\s+appartamento")

_UNIT = (r"millimet\w+|millim[eè]tr\w+|millimetr\w+|mm|centimet\w+|centim[eè]tr\w+|centimetr\w+|senttim\w+|sentti\w*|zentim\w+|cm|"
         r"inch(?:es)?|tuum\w+|zoll|pouces?|pollic\w+|in\b|[\"″”]|feet|foot|ft|"
         r"metres?|meters?|m[eè]tres?|metri\w*|metr[oi]|meter\w*|m")
_NUM = r"\d+(?:[.,]\d+)?"
_X = r"(?:x|×|\*|by|-by-|:)"
_SIZE_RE = re.compile(rf"({_NUM})\s*(?:({_UNIT})(?![a-z0-9²]))?\s*{_X}\s*({_NUM})\s*(?:({_UNIT})(?![a-z0-9²]))?", re.I)
_SINGLE_RE = re.compile(rf"({_NUM})\s*(cm|mm|centim\w+|millim\w+|senttim\w+|inch(?:es)?|zoll|pouces?|pollic\w+|tuum\w+|[\"″”]|m|metres?|meters?)"
                        rf"(?![a-z0-9²])(?:\s*(?:square|sq\.?|neliö\w*))?\s*(?:{_W['tiles']}|{_W['planks']})", re.I)
_AREA_UNIT = r"m2|m²|m\^2|sqm|sq\.?\s*m(?:etres?|eters?)?|square\s+m(?:etres?|eters?)|neli[oö]\w*|qm|mq"
_SINGLE_BEFORE_RE = re.compile(rf"(?:{_W['tiles']}|{_W['planks']})\s*(?:of|von|di|de|d'|à|sized?|measuring)?\s*({_NUM})\s*"
                               rf"(cm|mm|centim\w+|millim\w+|senttim\w+|inch(?:es)?|zoll|pouces?|pollic\w+|tuum\w+|[\"″”]|m|metres?|meters?)(?![a-z0-9²])", re.I)
_PER_PIECE_RE = re.compile(rf"({_NUM})\s*(?:{_AREA_UNIT})\s*(?:per|each|/|a|kohti|pro|je|par|ciascun\w*|ognuna?)\s*"
                           rf"(?:{_W['tiles']}|{_W['planks']}|piece|pcs)", re.I)
_PIECE_OF_RE = re.compile(rf"(?:{_W['tiles']}|{_W['planks']})\s*(?:of|at|are|is|sized?|à|von|di)\s*(?:about\s*)?({_NUM})\s*(?:{_AREA_UNIT})", re.I)
_WASTE_RE = re.compile(rf"({_NUM})\s*(?:%|percent|prosent\w*|prozent|pour\s*cent|per\s*cento)\s*(?:of\s*)?(?:waste|extra|spare|overage|"
                       rf"allowance|margin|hukka\w*|verschnitt|reserve|chutes?|perte\w*|scart\w*|sfrido)", re.I)
_NO_WASTE_RE = re.compile(r"\b(?:no|zero|without|ilman|ohne|sans|senza|0)\s+(?:waste|extra|spare|hukka\w*|verschnitt|chutes?|pertes?|scart\w*|sfrido)", re.I)
_WASTE_AFTER_RE = re.compile(rf"(?:waste|allowance|overage|hukka\w*|verschnitt|chutes?|pertes?|scarto|sfrido)\s*(?:of|at|:|=|on)?\s*({_NUM})\s*%", re.I)
_COATS_RE = re.compile(r"\b(\d+|one|two|three|four|yksi|kaksi|kolme|ein|zwei|drei|vier|une?|deux|trois|quatre|due|tre|quattro)\s*"
                       r"(?:coats?|layers?|kerro\w+|schichten?|anstriche?|couches?|mani\b|strati)", re.I)
_COATS_WORD = {"one": 1, "two": 2, "three": 3, "four": 4, "yksi": 1, "kaksi": 2, "kolme": 3, "ein": 1, "zwei": 2, "drei": 3, "vier": 4,
               "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "due": 2, "tre": 3, "quattro": 4}
_DOUBLE_COAT = re.compile(r"\bdouble\s+coat|\btwice\b|kahdesti|zweimal|deux\s+fois|due\s+volte", re.I)
_COVER_RE = re.compile(rf"({_NUM})\s*(?:{_AREA_UNIT})\s*(?:per|/|a|je|par)\s*(?:l\b|lit\w+|ltr)", re.I)
_HEIGHT_RE = re.compile(rf"({_NUM})\s*(m|metres?|meters?|cm)\s*(?:high|tall|ceiling|korke\w*|hoch|haut\w*|alt[oa])|"
                        rf"(?:ceiling|wall|room|ceiling\s+height|height|korkeus|korkeu\w*|h[oö]he|hauteur|altezza)\s*(?:height\s*)?(?:of|is|at|:|=|on)?\s*"
                        rf"({_NUM})\s*(m|metres?|meters?|cm)\b", re.I)
_ROLL_RE = re.compile(rf"({_NUM})\s*(m|metres?|meters?)\s*(?:wide\s*)?(?:roll|rolls|width|wide|leve\w*|breit\w*|large\w*|larg\w*)|"
                      rf"(?:roll|rolls|rulla\w*|rolle\w*|rouleau\w*|rotol\w*)\s*(?:width|leveys|breite|largeur|larghezza)?\s*(?:of|is|at|:|=|on)?\s*({_NUM})\s*(m|metres?|meters?)\b", re.I)
_LUX_RE = re.compile(rf"({_NUM})\s*(?:lux|lx)\b", re.I)
_LUMEN_RE = re.compile(rf"({_NUM})\s*(?:lumens?|lm)\b", re.I)


def _f(x: str) -> float:
    return float(x.replace(",", "."))


def _unit_key(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = u.lower()
    if u.startswith(("mm", "millim", "millimetr")):
        return "mm"
    if u.startswith(("cm", "centim", "sentti", "zentim")):
        return "cm"
    if u.startswith(("in", "tuum", "zoll", "pouce", "pollic")) or u in ('"', "″", "”"):
        return "in"
    if u.startswith(("ft", "feet", "foot")):
        return "ft"
    return "m"


class DeriveSpec(BaseModel):
    """What the user wants derived, with the parameters they stated (None = not stated -> default or ask)."""
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    room: Optional[str] = None             # canonical room_type (key of ROOMS); None = every room on the drawing
    room_phrase: Optional[str] = None      # what the user wrote
    target: Literal["floor", "walls", "ceiling"] = "floor"
    tile_w_m: Optional[float] = Field(None, gt=0, le=20)
    tile_h_m: Optional[float] = Field(None, gt=0, le=20)
    tile_area_m2: Optional[float] = Field(None, gt=0, le=400)
    size_unit: Optional[Literal["m", "cm", "mm", "in", "ft"]] = None   # the unit the user wrote the size in
    size_unit_guessed: bool = False
    waste_frac: Optional[float] = Field(None, ge=0, le=1)
    coats: Optional[int] = Field(None, ge=1, le=6)
    coverage_m2_per_l: Optional[float] = Field(None, gt=0, le=50)
    height_m: Optional[float] = Field(None, gt=0.5, le=15)
    roll_width_m: Optional[float] = Field(None, gt=0, le=10)
    lux: Optional[float] = Field(None, gt=0, le=5000)
    lumens: Optional[float] = Field(None, gt=0, le=100000)
    utilisation: Optional[float] = Field(None, gt=0, le=1)
    lang: Optional[str] = None

    @model_validator(mode="after")
    def _check(self):
        if self.room is not None and self.room not in ROOMS:
            raise ValueError(f"unknown room {self.room!r}; known: {sorted(ROOMS)}")
        if self.kind not in ("tiles", "planks") and (self.tile_w_m or self.tile_h_m or self.tile_area_m2):
            raise ValueError("tile size only applies to tiles/planks")
        if bool(self.tile_w_m) != bool(self.tile_h_m):
            raise ValueError("tile_w_m and tile_h_m go together")
        return self

    @property
    def piece_area_m2(self) -> Optional[float]:
        if self.tile_area_m2:
            return self.tile_area_m2
        if self.tile_w_m and self.tile_h_m:
            return self.tile_w_m * self.tile_h_m
        return None

    @property
    def missing(self) -> list[str]:
        return ["tile_size"] if self.kind in ("tiles", "planks") and self.piece_area_m2 is None else []

    @property
    def room_label(self) -> str:
        return ROOM_WORD.get(self.room or "", "") if self.room else "all rooms"

    def base_spec(self) -> dict:
        """The query_spec for the base quantity: floor area of the named rooms (perimeter is derived from their outline)."""
        s: dict[str, Any] = {"select": "room", "aggregate": "sum_area"}
        if self.room:
            s["where"] = {"room_type": self.room}
        return s

    def base_question(self) -> str:
        """Phrased so no fixed template matches ('dining room' / 'all room' hit sheet-level intents): the stub spec runs."""
        return ("derived quantity base: sum of floor areas of the " + ROOM_WORD[self.room]) if self.room \
            else "derived quantity base: sum of floor areas, no room filter"


def from_obj(obj: Any) -> DeriveSpec:
    """Validate a `derive` object an LLM planner emitted (same schema; unknown keys rejected). Raises ValueError."""
    if not isinstance(obj, dict):
        raise ValueError("derive must be an object")
    try:
        return DeriveSpec.model_validate(obj)
    except ValidationError as e:
        raise ValueError(f"bad derive object: {e.errors()[0]['msg']} ({'.'.join(map(str, e.errors()[0]['loc']))})") from e


# ---------------------------------------------------------------- parsing
def _first_kind(q: str) -> Optional[Kind]:
    best: Optional[tuple[int, str]] = None
    for k, pat in _W.items():
        m = re.search(rf"\b(?:{pat})", q, re.I)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), k)
    return best[1] if best else None  # type: ignore[return-value]


def _guess_unit(a: float, b: float) -> str:
    """No unit written: 600 -> mm, 30 -> cm, 3 -> m (a 3 x 3 cm tile is not a floor tile)."""
    v = max(a, b)
    return "mm" if v >= 100 else "cm" if v >= 8 else "m"


def _parse_size(q: str) -> dict:
    m = _SIZE_RE.search(q)
    if m:
        a, u1, b, u2 = _f(m.group(1)), _unit_key(m.group(2)), _f(m.group(3)), _unit_key(m.group(4))
        unit = u2 or u1
        guessed = unit is None
        unit = unit or _guess_unit(a, b)
        if not (u1 is None or u2 is None or u1 == u2):    # '1 m x 60 cm'
            return {"tile_w_m": a * UNIT_M[u1], "tile_h_m": b * UNIT_M[u2], "size_unit": u2}
        return {"tile_w_m": a * UNIT_M[unit], "tile_h_m": b * UNIT_M[unit], "size_unit": unit, "size_unit_guessed": guessed}
    m = _SINGLE_RE.search(q) or _SINGLE_BEFORE_RE.search(q)
    if m:
        u = _unit_key(m.group(2)) or "m"
        return {"tile_w_m": _f(m.group(1)) * UNIT_M[u], "tile_h_m": _f(m.group(1)) * UNIT_M[u], "size_unit": u}
    m = _PER_PIECE_RE.search(q) or _PIECE_OF_RE.search(q)
    if m:
        return {"tile_area_m2": _f(m.group(1))}
    return {}


def _parse_room(q: str) -> tuple[Optional[str], Optional[str], bool]:
    """(canonical room, phrase, named_something_unknown). The room that follows 'for/in/of ...' wins over a size word."""
    if re.search(_ALL_ROOMS, q, re.I):
        return None, None, False
    hits = []
    for rt, pat in ROOMS.items():
        for m in re.finditer(rf"(?<![a-z0-9])(?:{pat})", q, re.I):
            hits.append((m.start(), rt, m.group(0)))
    if hits:
        hits.sort()
        _, rt, ph = hits[-1] if re.search(r"\b(?:for|in|of|into|to)\b[^?]*$", q[:hits[-1][0]], re.I) else hits[0]
        return rt, ph.strip(), False
    m = re.search(r"\b(?:for|in|of)\s+(?:my|the|our|a)\s+([a-zäöüéèàù]+(?:\s+[a-zäöüéèàù]+)?)\s*\??$", q.strip(), re.I)
    return None, (m.group(1) if m else None), bool(m)


def parse(question: str) -> Optional[DeriveSpec]:
    """Regex first. None = not a derived-quantity question (the normal pipeline answers it)."""
    if not question or len(question) > 600:
        return None
    q = " ".join(question.split())
    kind = _first_kind(q)
    if kind is None:
        return None
    size = _parse_size(q) if kind in ("tiles", "planks") else {}
    mat = _W[kind]
    wants = bool(
        (re.search(rf"\b(?:{_HOWMANY})\s+(?:(?!(?:rooms?|walls?|doors?|windows?|have|has|are|is|there)\b)[\w.,x×*²-]+\s+){{0,5}}?(?:{mat})", q, re.I)
         and (size or re.search(_PURCHASE_CUE, q, re.I)))                                             # how many 30x30 cm tiles ...
        or re.search(rf"\b(?:i|we)\s+(?:need|require|have\s+to\s+buy|should\s+(?:buy|order)|must\s+(?:buy|order)|want\s+to\s+(?:buy|order))\b|"
                     rf"\bto\s+(?:buy|order)\b|{_FIRST_PERSON_NEED}", q, re.I)
        or (size and not re.search(r"\bhow\s+many\s+(?:rooms?|walls?|doors?|windows?)\b", q, re.I)))
    if kind == "lights":      # 'how many lights are there' is a count of drawn fixtures; only 'need/required/lux/to light' derive
        wants = bool(re.search(r"\b(?:i|we)\s+need|\bneed\s+(?:for|to)|lux|lumens?|to\s+light|light\s+up|illuminat\w+|tarvitsen|tarvitaan|"
                               r"brauche|ben[oö]tige|besoin|il\s+me\s+faut|bisogno|servono|occorrono", q, re.I))
    if not wants:
        return None
    room, phrase, unknown = _parse_room(q)
    room_obj: dict[str, Any] = {"room": room, "room_phrase": phrase}
    target = "floor"
    if kind == "paint":
        target = "ceiling" if re.search(rf"\b(?:{_CEIL})", _HEIGHT_RE.sub(" ", q), re.I) else "walls"   # 'ceiling height 2.7 m' is a height
    d: dict[str, Any] = {"kind": kind, "target": target, **room_obj, **size}
    m = _WASTE_RE.search(q) or _WASTE_AFTER_RE.search(q)
    if m:
        d["waste_frac"] = _f(m.group(1)) / 100.0
    elif _NO_WASTE_RE.search(q):
        d["waste_frac"] = 0.0
    if kind == "paint":
        m = _COATS_RE.search(q)
        if m:
            t = m.group(1).lower()
            d["coats"] = int(t) if t.isdigit() else _COATS_WORD.get(t)
        elif _DOUBLE_COAT.search(q):
            d["coats"] = 2
        m = _COVER_RE.search(q)
        if m:
            d["coverage_m2_per_l"] = _f(m.group(1))
        m = _HEIGHT_RE.search(q)
        if m:
            v, u = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            d["height_m"] = _f(v) * (0.01 if u.lower() == "cm" else 1.0)
    if kind in ("carpet",):
        m = _ROLL_RE.search(q)
        if m:
            v = m.group(1) or m.group(3)
            d["roll_width_m"] = _f(v)
    if kind == "lights":
        m = _LUX_RE.search(q)
        if m:
            d["lux"] = _f(m.group(1))
        m = _LUMEN_RE.search(q)
        if m:
            d["lumens"] = _f(m.group(1))
    try:
        spec = DeriveSpec(**{k: v for k, v in d.items() if v is not None})
    except ValidationError:
        return None
    if unknown and room is None:                      # 'for my attic': a room we have no word for -> keep the phrase
        spec = spec.model_copy(update={"room_phrase": phrase})
    return spec


# ---------------------------------------------------------------- compute
@dataclass
class Derived:
    ok: bool
    value: Optional[float] = None
    unit: Optional[str] = None
    sentence: str = ""
    assumptions: list[Assumption] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    interval: Optional[tuple[float, float]] = None
    decisions: list[Decision] = field(default_factory=list)
    refusal: Optional[str] = None
    tier: Optional[Tier] = None


def _m2(x: float) -> str:
    return f"{x:.1f} m²" if x >= 1 else f"{x:.2f} m²"


def _size_text(spec: DeriveSpec) -> str:
    if spec.tile_w_m and spec.tile_h_m:
        u = spec.size_unit or ("m" if max(spec.tile_w_m, spec.tile_h_m) >= 1 else "cm" if max(spec.tile_w_m, spec.tile_h_m) >= 0.05 else "mm")
        k = UNIT_M[u]

        def g(v: float) -> str:
            return f"{v / k:.4g}"
        w, h = g(spec.tile_w_m), g(spec.tile_h_m)
        return f"{w} x {h} {u}"
    return f"{spec.piece_area_m2:.4g} m²"


def _geometry(po, area_m2: float) -> dict:
    """Perimeter and short/long side (metres) of the evidence rooms, from their outline. Scale comes from the base proof's
    px_per_m when it agrees with the area, else from area_px -> area_m2 (so no new scale is ever assumed here)."""
    try:
        from shapely.geometry import Polygon
    except Exception:  # noqa: BLE001
        return {}
    polys = []
    for e in getattr(po, "evidence", []) or []:
        if e.kind == "room" and len(e.polygon) >= 3:
            try:
                p = Polygon(e.polygon)
                p = p if p.is_valid else p.buffer(0)
                if p.area > 0:
                    polys.append(p)
            except Exception:  # noqa: BLE001
                continue
    if not polys or area_m2 <= 0:
        return {}
    area_px = sum(p.area for p in polys)
    k = math.sqrt(area_m2 / area_px)               # metres per drawing unit
    ppm = getattr(getattr(po, "scale", None), "px_per_m", None)
    if ppm and abs(area_px / ppm ** 2 - area_m2) / area_m2 > 0.10:
        ppm = None                                  # evidence covers more than the answer (e.g. one floor of several)
    if ppm:
        k = 1.0 / ppm
    out = {"perimeter_m": sum(p.length for p in polys) * k, "n": len(polys)}
    if len(polys) == 1:
        r = polys[0].minimum_rotated_rectangle
        xs = list(r.exterior.coords)
        a, b = math.dist(xs[0], xs[1]) * k, math.dist(xs[1], xs[2]) * k
        out.update(short_m=min(a, b), long_m=max(a, b))
    return out


def _calc(spec: DeriveSpec, area_m2: float, geo: dict, over: Optional[dict] = None) -> dict:
    """Pure arithmetic for one set of parameters; `over` swaps individual parameters (for decision options)."""
    o = over or {}
    g = lambda k: o.get(k, getattr(spec, k) if getattr(spec, k, None) is not None else DEFAULTS.get(k))  # noqa: E731
    w = g("waste_frac")
    if spec.kind in ("tiles", "planks"):
        a_t = spec.piece_area_m2
        n = materials.tiles_count(area_m2, w, a_t)
        return {"value": float(n), "area_used": area_m2 * (1 + w), "a_t": a_t, "waste": w}
    if spec.kind == "paint":
        if spec.target == "ceiling":
            surface, perim = area_m2, None
            litres = g("coats") * surface / g("coverage_m2_per_l")
        else:
            perim = geo.get("perimeter_m")
            if perim is None:
                return {"value": None, "why": "the room outline is needed for the wall area"}
            surface = perim * g("height_m")
            litres = materials.paint_litres(perim, g("height_m"), 0.0, g("coats"), g("coverage_m2_per_l"))
        return {"value": round(litres, 1), "surface": surface, "perim": perim}
    if spec.kind == "skirting":
        perim = geo.get("perimeter_m")
        if perim is None:
            return {"value": None, "why": "the room outline is needed for the perimeter"}
        return {"value": round(perim * (1 + w), 1), "perim": perim, "waste": w}
    if spec.kind == "lights":
        n = materials.lights_count(area_m2, g("lux"), g("lumens"), g("utilisation"))
        return {"value": float(n)}
    if spec.kind == "carpet":
        rw = g("roll_width_m")
        if "short_m" in geo:
            r = materials.carpet_rolls(geo["long_m"], geo["short_m"], rw, w)
            return {"value": round(r["roll_length_m"], 1), "strips": r["strips"], "strip_len": geo["long_m"] * (1 + w),
                    "bought_m2": r["total_m2"], "roll": rw, "waste": w}
        length = area_m2 * (1 + w) / rw
        return {"value": round(length, 1), "strips": None, "roll": rw, "waste": w, "approx": True}
    raise ValueError(spec.kind)


def _assume(spec: DeriveSpec, key: str, value: Any, unit: Optional[str], stated: bool, dep: Optional[list[str]] = None) -> Assumption:
    return Assumption(key=key, value=value, unit=unit, tag=Tag.chosen if stated else Tag.defaulted,
                      source="user (in the question)" if stated else SOURCE_TABLE, depends_on=dep or [])


def _scale_is_assumed(po) -> bool:
    sc = getattr(po, "scale", None)
    if sc is None:
        return False
    real = ("user", "dimension", "scale_bar", "printed_ratio", "printed_area")
    return bool(sc.widths_relative or sc.needs_user or (sc.anchors and not any(a.kind in real for a in sc.anchors)))


def compute(spec: DeriveSpec, base_value: Optional[float], base_proof) -> Derived:
    """base_value = floor area (m²) of the named room(s); base_proof = the ProofObject that produced it (evidence, scale, tier)."""
    where = f"the {spec.room_label}" if spec.room else ("all rooms" if not spec.room_phrase else f"the {spec.room_phrase}")
    thing = {"tiles": "tiles", "planks": "planks", "paint": "paint", "carpet": "carpet", "lights": "light fittings",
             "skirting": "skirting"}[spec.kind]
    if spec.missing:
        d = Derived(ok=False, refusal="tile size missing: say how big the tiles are (e.g. '30x30 cm')", tier=Tier.amber)
        area_txt = f"The {spec.room_label or 'floor'} covers {_m2(base_value)}. " if base_value else ""
        d.sentence = (f"{area_txt}I need the tile size to count {thing} for {where}: tell me e.g. 30x30 cm, 60x60 cm or 2.0 m² per tile "
                      f"and I will count them (I do not guess it).")
        if base_value:
            opts = []
            for lab, w_, h_ in (("30 x 30 cm", .3, .3), ("45 x 45 cm", .45, .45), ("60 x 60 cm", .6, .6), ("60 x 120 cm", .6, 1.2)):
                n = materials.tiles_count(base_value, spec.waste_frac if spec.waste_frac is not None else DEFAULTS["waste_frac"], w_ * h_)
                opts.append(Option(value=lab, label=f"{lab}: {n} {thing}", total_delta=float(n)))
            ns = [o.total_delta for o in opts]
            d.decisions.append(Decision(key="tile_size", question="Which tile size?", options=opts, default=opts[0].value,
                                        tag=Tag.open, impact=max(ns) - min(ns)))
        return d
    if base_value is None or base_value <= 0:
        return Derived(ok=False, refusal=getattr(base_proof, "refusal", None) or "the base area could not be measured",
                       sentence=f"I can't count {thing} for {where}: "
                       f"{getattr(base_proof, 'refusal', None) or 'the area could not be measured from the drawing'}.", tier=Tier.grey)
    geo = _geometry(base_proof, float(base_value)) if spec.kind in ("paint", "skirting", "carpet", "tiles", "planks") else {}
    r = _calc(spec, float(base_value), geo)
    if r.get("value") is None:
        return Derived(ok=False, refusal=r["why"], tier=Tier.amber,
                       sentence=f"I can't work out the {thing} for {where}: {r['why']} (it was not measured on this drawing).")
    d = Derived(ok=True, value=r["value"])
    A = float(base_value)
    a_base = Assumption(key="derive:base_area_m2", value=round(A, 2), unit="m2", tag=Tag.drawn, source="measured from the drawing (see evidence)")
    d.assumptions.append(a_base)
    dep = ["derive:base_area_m2"]
    n_rooms = geo.get("n")
    room_txt = where if not n_rooms or n_rooms == 1 or not spec.room else f"the {n_rooms} {spec.room_label}s ({_m2(A)} combined)"
    if spec.kind in ("tiles", "planks"):
        w = r["waste"]
        d.unit = "tiles" if spec.kind == "tiles" else "planks"
        n = int(r["value"])
        a_t = r["a_t"]
        d.sentence = (f"You need {n} {thing if n != 1 else thing[:-1]} of {_size_text(spec)} for {room_txt} "
                      f"({_m2(A)} + {w * 100:.0f}% waste = {_m2(r['area_used'])}; {a_t:.4g} m² per {thing[:-1]}).")
        if spec.size_unit_guessed:
            d.notes.append(f"the tile size was written without a unit; read as {spec.size_unit}")
        d.assumptions.append(Assumption(key="piece_area_m2", value=round(a_t, 4), unit="m2", tag=Tag.chosen,
                                        source="user (in the question)" + (f", unit guessed as {spec.size_unit}" if spec.size_unit_guessed else "")))
        d.assumptions.append(_assume(spec, "tile_waste_frac", w, "fraction", spec.waste_frac is not None, dep))
        if "short_m" in geo and max(spec.tile_w_m or 0, spec.tile_h_m or 0) > geo["short_m"] and spec.tile_w_m:
            d.notes.append(f"the tile ({_size_text(spec)}) is larger than the room's short side ({geo['short_m']:.1f} m): every tile needs cutting")
            d.sentence += f" The room's short side is about {geo['short_m']:.1f} m, so the tiles must be cut."
        d.decisions.append(_decision(spec, A, geo, "waste_frac", "tile_waste_frac", "Waste allowance?", (0.05, 0.10, 0.15), lambda v: f"{v * 100:.0f}%"))
    elif spec.kind == "paint":
        d.unit = "l"
        coats = spec.coats or DEFAULTS["coats"]
        cov = spec.coverage_m2_per_l or DEFAULTS["coverage_m2_per_l"]
        if spec.target == "ceiling":
            d.sentence = (f"You need about {r['value']:.1f} litres of paint for the ceiling of {room_txt} ({_m2(A)}, {coats} coats at "
                          f"{cov:g} m² per litre).")
        else:
            h = spec.height_m or DEFAULTS["height_m"]
            d.sentence = (f"You need about {r['value']:.1f} litres of paint for the walls of {room_txt} (perimeter {r['perim']:.1f} m x "
                          f"{h:g} m high = {r['surface']:.1f} m² of wall, {coats} coats at {cov:g} m² per litre; door and window openings not deducted).")
            d.assumptions.append(_assume(spec, "ceiling_height_m", h, "m", spec.height_m is not None))
            d.assumptions.append(Assumption(key="openings_deducted_m2", value=0, unit="m2", tag=Tag.defaulted, source=SOURCE_TABLE,
                                            depends_on=[]))
        d.assumptions.append(_assume(spec, "paint_coats", coats, "count", spec.coats is not None))
        d.assumptions.append(_assume(spec, "paint_coverage_m2_per_l", cov, "m2/l", spec.coverage_m2_per_l is not None))
        d.decisions.append(_decision(spec, A, geo, "coats", "paint_coats", "How many coats?", (1, 2, 3), lambda v: f"{v} coat{'s' if v != 1 else ''}"))
    elif spec.kind == "skirting":
        d.unit = "m"
        w = r["waste"]
        d.sentence = (f"You need about {r['value']:.1f} m of skirting for {room_txt} (perimeter {r['perim']:.1f} m + {w * 100:.0f}% waste; "
                      "door openings not deducted).")
        d.assumptions.append(_assume(spec, "skirting_waste_frac", w, "fraction", spec.waste_frac is not None))
    elif spec.kind == "lights":
        d.unit = "fittings"
        n = int(r["value"])
        lux, lm, u = spec.lux or DEFAULTS["lux"], spec.lumens or DEFAULTS["lumens"], spec.utilisation or DEFAULTS["utilisation"]
        d.sentence = (f"You need {n} light fitting{'s' if n != 1 else ''} for {room_txt} ({_m2(A)} at {lux:g} lux, {lm:g} lm per fitting, "
                      f"utilisation {u:g}).")
        d.assumptions += [_assume(spec, "lux_target", lux, "lux", spec.lux is not None),
                          _assume(spec, "lumens_per_fitting", lm, "lm", spec.lumens is not None),
                          _assume(spec, "utilisation_factor", u, "fraction", spec.utilisation is not None)]
    elif spec.kind == "carpet":
        d.unit = "m"
        w, rw = r["waste"], r["roll"]
        if r.get("strips"):
            d.sentence = (f"You need about {r['value']:.1f} m of {rw:g} m wide carpet roll for {room_txt}: {r['strips']} strip"
                          f"{'s' if r['strips'] != 1 else ''} of {r['strip_len']:.1f} m (incl. {w * 100:.0f}% trim waste).")
        else:
            d.sentence = (f"You need about {r['value']:.1f} m of {rw:g} m wide carpet roll for {room_txt} ({_m2(A)} + {w * 100:.0f}% waste; "
                          "room shape unknown, so strips are not laid out).")
        d.assumptions.append(_assume(spec, "carpet_roll_width_m", rw, "m", spec.roll_width_m is not None))
        d.assumptions.append(_assume(spec, "carpet_waste_frac", w, "fraction", spec.waste_frac is not None, dep))
    # tier: the derived answer inherits the base tier; an assumed scale caps it (and is said out loud)
    base_tier = getattr(base_proof, "tier", Tier.amber)
    d.tier = base_tier
    sc = getattr(base_proof, "scale", None)
    if _scale_is_assumed(base_proof):
        d.tier = Tier.amber if base_tier == Tier.green else base_tier
        d.sentence += " The drawing has no printed scale, so the area (and this number) assumes standard 0.9 m doors."
        d.notes.append("scale assumed from door width: the derived quantity inherits that uncertainty")
    if sc is not None and getattr(sc, "rel_sigma", None):
        lo_a, hi_a = A * (1 - 2 * sc.rel_sigma), A * (1 + 2 * sc.rel_sigma)         # dA/A ~ 2 ds/s
        d.interval = (_calc(spec, max(lo_a, 1e-6), geo)["value"] or 0.0, _calc(spec, hi_a, geo)["value"] or 0.0) if spec.kind != "paint" \
            or spec.target == "ceiling" else (r["value"] * (1 - sc.rel_sigma), r["value"] * (1 + sc.rel_sigma))
        if d.interval[0] == d.interval[1]:
            d.interval = None
    return d


def _decision(spec: DeriveSpec, A: float, geo: dict, field_: str, key: str, question: str, options: tuple, fmt) -> Decision:
    default = getattr(spec, field_) if getattr(spec, field_) is not None else DEFAULTS[field_]
    vals = sorted(set(options) | {default})
    totals = {v: _calc(spec, A, geo, {field_: v})["value"] for v in vals}
    ok = {v: t for v, t in totals.items() if t is not None}
    base = ok.get(default)
    opts = [Option(value=v, label=f"{fmt(v)}: {ok[v]:g}", total_delta=(ok[v] - base) if base is not None else None) for v in vals if v in ok]
    spread = (max(ok.values()) - min(ok.values())) if ok else 0.0
    return Decision(key=key, question=question, options=opts, default=default,
                    tag=Tag.chosen if getattr(spec, field_) is not None else Tag.defaulted, impact=spread)


# ---------------------------------------------------------------- hook used by PipelineEngine.ask
class _SpecLLM:
    """Stands in for the planner LLM: returns the code-built base spec, costs nothing, makes no network call."""
    plan_tokens = 0

    def __init__(self, spec: dict):
        self._text = json.dumps(spec)

    def complete(self, system: str, user: str, max_tokens: int = 0):
        from types import SimpleNamespace
        return SimpleNamespace(text=self._text, tokens_in=0, tokens_out=0, usd=0.0)


def answer(engine, path: str, question: str, spec: DeriveSpec, *, allow_siblings: bool = True, benchmark: bool = True,
           progress=None):
    """Run the base-quantity question through the engine's normal routing, then wrap the result.

    Named room we have a code for -> the base spec is built here (no LLM call). A room phrase we have no word for and an
    LLM is on -> the planner translates the plain base question as usual. Otherwise ask which room."""
    base_q = spec.base_question()
    eng = copy.copy(engine)                         # shares caches; never mutates the live engine (server threads)
    eng.classifier = None
    unknown_room = spec.room is None and spec.room_phrase and not re.search(_ALL_ROOMS, question, re.I)
    if unknown_room and engine.llm is not None:
        base_q = f"derived quantity base: sum of floor areas of the {spec.room_phrase}"
    elif unknown_room:
        from contracts.proof import ProofObject, Provenance
        po = ProofObject(id="derive", question=question, kind="other", provenance=Provenance(file=path))
        po.tier, po.refusal = Tier.grey, f"I don't know which room '{spec.room_phrase}' is; name a room type (e.g. bedroom) or turn the planner on"
        po.answer_text = f"I can't tell which room '{spec.room_phrase}' is. Name it as bedroom, kitchen, living room, bathroom ... and I will count."
        return po
    else:
        eng.llm, eng.planner_llm = _SpecLLM(spec.base_spec()), None
    # benchmark=False: a derived quantity is never built on the dev-median prior that benchmark mode returns for an
    # unanswerable base ('no dining room on this drawing' must not become 920 tiles)
    po = eng.ask(path, base_q, allow_siblings=allow_siblings, benchmark=False, progress=progress)
    if eng.llm is not engine.llm:                   # the stub is not a model call
        po.cost.llm_calls = po.cost.planner_calls = 0
    po.question = question
    _restore_scale(eng, po, path, allow_siblings)
    po.notes.append(f"derived quantity: {spec.kind} from the floor area of {spec.room_label or 'the room'} (base question: '{base_q}')")
    return wrap(po, spec, question)


def _restore_scale(eng, po, path: str, allow: bool) -> None:
    """A planner-built area on a raster drawing leaves `po.scale` as the 'real units, px_per_m=1' placeholder even when the
    value was measured with the door-prior scale. Put the engine's real ScaleInfo back, so the derived answer cannot look
    scale-free (and so the 'which scale?' decision is offered)."""
    try:
        sc0 = po.scale
        if sc0 is not None and (sc0.anchors or sc0.px_per_m != 1.0):
            return
        facts = eng.analyze(path, allow_siblings=allow)
        if "vector" in facts.extras or po.provenance.resolved_from in ("dxf", "ifc") or po.provenance.fmt in ("dxf", "ifc", "svg"):
            return
        from engine import cache as facts_cache
        sc = eng._scale(facts, facts_cache.sha256_file(eng_abs(path)))
        if sc is not None and sc.px_per_m:
            po.scale = sc
            if sc.needs_user and not any(d.key == "scale" for d in po.decisions_open):
                po.decisions_open.append(eng._scale_decision(facts, sc))
    except Exception as e:  # noqa: BLE001
        po.notes.append(f"scale lookup skipped: {type(e).__name__}")


def eng_abs(path: str) -> str:
    from engine.pipeline import _abs
    return _abs(path)


def wrap(po, spec: DeriveSpec, question: str):
    """Replace the base proof's value by the derived one; evidence, voters, scale stay."""
    base_value = po.value if isinstance(po.value, (int, float)) else None
    if any(str(a.key).startswith("prior:") for a in po.assumptions):
        base_value = None                           # a prior is not a measurement
    d = compute(spec, base_value, po)
    po.intent = f"derive_{spec.kind}"
    po.query_spec = {"derive": spec.model_dump(exclude_none=True), "base": spec.base_spec()}
    if d.ok:
        po.kind, po.value, po.unit = "other", d.value, d.unit
        po.value = int(d.value) if d.unit in ("tiles", "planks", "fittings") else d.value
        po.refusal = None
        po.tier = d.tier or po.tier
        if d.interval:
            po.interval = Interval(lo=float(d.interval[0]), hi=float(d.interval[1]))
        else:
            po.interval = None
    else:
        po.value, po.unit, po.kind = None, None, "other"
        po.refusal = d.refusal
        po.tier = d.tier or Tier.amber
        if po.tier == Tier.amber and d.refusal and "tile size" in d.refusal:
            po.tier = Tier.grey
        po.interval = None
    po.assumptions = list(po.assumptions) + d.assumptions
    po.decisions_open = list(po.decisions_open) + d.decisions
    po.notes.extend(d.notes)
    if po.tier == Tier.amber and not any("tier:" in n for n in po.notes):
        po.notes.append("tier: amber (inherits the base area's tier)")
    po.reliability, po.reliability_note = None, ("computed by code from the measured area and the parameters listed under assumptions; "
                                                  "no calibration for derived quantities yet")
    po.answer_text = d.sentence
    return po
