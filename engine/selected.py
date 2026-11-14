"""Questions about the element the user SELECTED in the viewer ("what is the size of this room?", "how long are its
walls?", "what is this?", "how many beds are in here?"). The UI sends `selected_id`; code measures that element at the
solved scale. No LLM: the selection removes the ambiguity a planner would otherwise have to guess."""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from contracts.proof import Assumption, ProofObject, Provenance, Tag, Tier, Voter

DEICTIC = re.compile(r"\b(this|that|these|it|its|here|selected|current|the\s+one)\b", re.I)
AREA = re.compile(r"\b(size|area|big|large|square|sq|m2|m²|footage|floor\s*space)\b", re.I)
PERIM = re.compile(r"\b(perimeter|walls?|skirting|baseboards?|around)\b", re.I)
DIMS = re.compile(r"\b(dimensions?|long|wide|length|width|how\s+far)\b", re.I)
WHAT = re.compile(r"\b(what\s+is|what's|which|what\s+kind|type)\b", re.I)
COUNT = re.compile(r"\bhow\s+many\s+([a-z ]+?)(?:\s+(?:are|is|in|inside|here|there)\b|\?|$)", re.I)


def applies(question: str, selected_id: Optional[str]) -> bool:
    return bool(selected_id) and bool(DEICTIC.search(question) or len(question.split()) <= 5)


def answer(eng, path: str, question: str, selected_id: str) -> Optional[ProofObject]:
    from shapely.geometry import Point, Polygon
    from engine import overrides_el
    from engine.pipeline import _abs
    from engine import cache as facts_cache
    facts = eng.analyze(path)
    sha = facts.provenance.sha256 or facts_cache.sha256_file(_abs(path))
    facts = overrides_el.apply(facts, sha)
    el = next((e for e in facts.elements if e.id == selected_id), None)
    if el is None:
        return None
    name = el.label or (el.subtype or el.kind).replace("_", " ")
    po = ProofObject(id=hashlib.sha1(f"{path}|{question}|{selected_id}".encode()).hexdigest()[:12], question=question,
                     intent="selected_element", kind="text", provenance=Provenance(file=path, sha256=sha))
    po.evidence = [el]
    scale = eng._scale(facts, sha)
    ppm = scale.px_per_m if scale is not None and scale.px_per_m else None
    poly = Polygon([(p[0], p[1]) for p in el.polygon]).buffer(0) if len(el.polygon) >= 3 else None
    xs = [p[0] for p in el.polygon]; ys = [p[1] for p in el.polygon]
    src = "the sheet's printed scale" if scale is not None and any(
        a.kind in ("dimension", "scale_bar", "printed_ratio", "printed_area", "user") for a in scale.anchors) \
        else "a scale guessed from standard door widths (give one real length to confirm)"
    m = COUNT.search(question)
    if m and poly is not None:                       # "how many beds are in this room?"
        from engine.sheet_lookup import _stem, _tok_match
        noun = _stem(m.group(1).split()[-1])
        inside = [e for e in facts.elements if e.id != el.id and e.polygon and poly.buffer(2).contains(
            Point(sum(p[0] for p in e.polygon) / len(e.polygon), sum(p[1] for p in e.polygon) / len(e.polygon)))
            and (_tok_match(noun, e.kind) or _tok_match(noun, e.subtype or "") or _tok_match(noun, e.label or ""))]
        po.kind, po.value, po.unit = "count", len(inside), None
        po.evidence = [el] + inside
        po.voters = [Voter(name="inside_selection", value=len(inside), element_ids=[e.id for e in inside],
                           note=f"elements of that kind whose centre lies inside {name}")]
        po.tier = Tier.amber
        po.answer_text = f"{len(inside)} {m.group(1).strip()} in {name}."
        return po
    if ppm is None:
        po.tier, po.refusal = Tier.grey, "the drawing's scale is not known yet: give one real length"
        po.answer_text = f"This is {name}. Its size needs the scale: give one real length (Set real size)."
        return po
    w, h = (max(xs) - min(xs)) / ppm, (max(ys) - min(ys)) / ppm
    po.scale = scale
    po.assumptions.append(Assumption(key="scale_px_per_m", value=round(ppm, 3),
                                     tag=Tag.specified if "printed" in src else Tag.defaulted, source=src))
    if PERIM.search(question) and poly is not None:
        v = poly.exterior.length / ppm
        po.kind, po.value, po.unit = "length", round(v, 2), "m"
        po.answer_text = f"The walls around {name} add up to {v:.1f} m (its outline, measured with {src})."
    elif DIMS.search(question) and not AREA.search(question):
        po.kind, po.value, po.unit = "text", f"{max(w, h):.2f} m x {min(w, h):.2f} m", "label"
        po.answer_text = f"{name} is about {max(w, h):.2f} m long and {min(w, h):.2f} m wide (measured with {src})."
    elif WHAT.search(question) and not AREA.search(question):
        po.kind, po.value, po.unit = "text", name, "label"
        tag = (el.attrs.get("user_override") or {}).get("tag") or el.attrs.get("source") or "read from the drawing"
        po.answer_text = (f"This is {name} ({el.kind}{', ' + el.subtype if el.subtype and el.subtype != el.kind else ''}), "
                          f"{tag}; about {max(w, h):.1f} x {min(w, h):.1f} m.")
    else:
        a = float(el.attrs["area_m2"]) if el.attrs.get("area_m2") else (poly.area / ppm ** 2 if poly is not None else w * h)
        po.kind, po.value, po.unit = "area", round(a, 2), "m2"
        po.answer_text = (f"{name} is {a:.1f} m² (about {max(w, h):.1f} x {min(w, h):.1f} m), measured from its "
                          f"outline with {src}.")
    po.voters = [Voter(name="selected_outline", value=po.value, element_ids=[el.id],
                       note="the element you selected, measured at the solved scale")]
    po.tier = Tier.amber
    return po
