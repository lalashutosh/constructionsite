"""'sum of the lengths of the walls of the garage' / 'perimeter of the kitchen' / 'wall length of all bedrooms' ->
a query spec with aggregate 'perimeter' (no LLM). The room is matched against the subtypes and labels the drawing
actually has, so any room type the readers know (garage, sauna, dorm ...) works without a list per question."""
from __future__ import annotations

import re
from typing import Optional

PERIM = re.compile(
    r"\bperimeter\b|\bcircumference\b|\bwall\s+lengths?\b|\blengths?\s+of\s+(?:the\s+|all\s+(?:the\s+)?|its\s+)?walls?\b|"
    r"\bwalls?\b.{0,30}\b(?:total|combined|summed|sum|overall)?\s*lengths?\b|\bhow\s+long\s+are\s+(?:the|its|all)\s+.{0,20}walls\b|"
    r"\bseinien\s+pituus|\bv[äa]ggarnas\s+l[äa]ngd|\bwandl[äa]nge|\bumfang\b", re.I)
SYN = {"living": r"living|lounge|olohuone|vardagsrum|wohnzimmer", "bedroom": r"bed\s*rooms?|makuuhuone|sovrum|schlafzimmer",
       "kitchen": r"kitchen|keitti|k[öo]k|k[üu]che", "bathroom": r"bath\s*rooms?|kylpy|badrum|badezimmer",
       "wc": r"\bwc\b|toilet|vessa|restroom", "hallway": r"hall(?:way)?|corridor|eteinen|entrance", "garage": r"garage|autotalli",
       "balcony": r"balcon|parveke|balkong|balkon", "storage": r"storage|closet|varasto|förråd", "sauna": r"sauna",
       "utility": r"utility|laundry|kodinhoito", "dining": r"dining|ruokailu"}


def parse(question: str, facts) -> Optional[dict]:
    if not PERIM.search(question):
        return None
    q = question.lower()
    subtypes = {e.subtype for e in facts.elements if e.kind in ("room", "zone", "region") and e.subtype}
    for st, rx in SYN.items():
        if re.search(rx, q) and st in subtypes:
            return {"select": ["room", "zone"], "where": {"subtype": st}, "aggregate": "perimeter"}
    for st in sorted(subtypes, key=len, reverse=True):          # a subtype the readers use that SYN does not list
        if len(st) >= 3 and re.search(rf"\b{re.escape(st.replace('_', ' '))}", q):
            return {"select": ["room", "zone"], "where": {"subtype": st}, "aggregate": "perimeter"}
    labels = {(e.label or "").strip().lower() for e in facts.elements if e.kind in ("room", "zone") and e.label}
    for lb in sorted(labels, key=len, reverse=True):
        if len(lb) >= 3 and lb in q:
            return {"select": ["room", "zone"], "where": {"label": lb}, "aggregate": "perimeter"}
    if re.search(r"\b(all|every|each)\b.{0,15}\brooms?\b", q):
        return {"select": ["room", "zone"], "aggregate": "perimeter"}
    # no room named: the building's outer walls (its verified outline), else every room
    if any(e.kind == "footprint" for e in facts.elements):
        return {"select": ["footprint"], "aggregate": "perimeter", "_target": "outside of the building"}
    return {"select": ["room"], "aggregate": "perimeter"}
