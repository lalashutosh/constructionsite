"""Questions about ONE floor of a sheet that holds several floor plans ("How many bedrooms on floor 2?",
"Montako makuuhuonetta 2. kerroksessa?").

The scan check (engine/scancheck.py) finds each floor plan's box on the sheet and its level (read by the AI reviewers
from titles like "1. KERROS", else position). Here a count answered for the whole sheet is restricted to the elements
inside the asked floor's box. Code decides membership (element centre inside the box); no model produces the number.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEOM = ROOT / "cache" / "geometry"

_ORD = {"ground": 0, "first": 1, "second": 2, "third": 3, "fourth": 4, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4,
        "ensimmäi": 1, "toi": 2, "kolma": 3}


def asked_floor(question: str) -> Optional[tuple[str, int]]:
    """('index', n) for the n-th floor counted from 1, ('ground', 0), ('top', -1), or None."""
    q = question.lower()
    if re.search(r"\b(upstairs|upper floor|top floor|yläkerta|yläkerr)", q):
        return ("top", -1)
    if re.search(r"\b(downstairs|ground floor|lower floor|bottom floor|alakerta|alakerr|pohjakerr)", q):
        return ("ground", 0)
    m = re.search(r"\b(\d)\s*\.?\s*(?:kerro\w*|krs\b)", q) or re.search(r"\b(?:floor|level|storey|story)\s*(\d)\b", q)
    if m:
        return ("index", int(m.group(1)))
    m = re.search(r"\b(ground|first|second|third|fourth|1st|2nd|3rd|4th)\s+(?:floor|level|storey|story)", q)
    if m:
        n = _ORD[m.group(1)]
        return ("ground", 0) if n == 0 else ("index", n)
    return None


def sheet_floors(sha: str) -> list[dict]:
    f = GEOM / f"{sha}-pixels.json"
    if not f.exists():
        return []
    try:
        fl = (json.loads(f.read_text()).get("check") or {}).get("floors") or []
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(fl, key=lambda x: x.get("level") if isinstance(x.get("level"), int) else 50) if len(fl) > 1 else []


def pick(floors: list[dict], want: tuple[str, int]) -> Optional[dict]:
    if not floors:
        return None
    kind, n = want
    if kind == "top":
        return floors[-1]
    if kind == "ground":
        return floors[0]
    return floors[n - 1] if 1 <= n <= len(floors) else None


def _inside(box, poly) -> bool:
    if not poly:
        return False
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def restrict(po, question: str, sha: Optional[str]) -> Optional[str]:
    """In place: a count over the whole sheet -> the count on the asked floor (evidence inside that floor's box)."""
    want = asked_floor(question)
    if not want or not sha or po.kind != "count" or not po.evidence or not isinstance(po.value, (int, float)):
        return None
    floors = sheet_floors(sha)
    fl = pick(floors, want)
    if fl is None:
        if floors:
            po.notes.append(f"the sheet has {len(floors)} floor plans; the floor asked for is not one of them")
        return None
    keep = [e for e in po.evidence if _inside(fl["box"], e.polygon)]
    total = int(po.value)
    po.evidence = keep
    po.value = len(keep)
    label = fl.get("label") or "that floor"
    po.notes.append(f"counted on {label} only: {len(keep)} of {total} on the sheet "
                    f"(floor plans found by the scan check; level {fl.get('level_source', 'from position')})")
    return label


def name_floor(text: Optional[str], label: str) -> Optional[str]:
    """'There are 4 bedrooms.' -> 'There are 4 bedrooms on 2. KERROS.'"""
    if not text:
        return text
    t = text.rstrip()
    if " on this drawing" in t:
        return t.replace(" on this drawing", f" on {label}")
    return (t[:-1] if t.endswith(".") else t) + f" on {label}."
