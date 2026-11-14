"""Door schedule reader for opening_design sheets (vector PDF with a text layer), PyMuPDF words only.

The A-801 style sheet is rotated: schedule rows are vertical text lines. Words are grouped into rows by their
cross-axis coordinate, tokens inside a row are read in the order the sheet prints them, and columns are recognised
from token PATTERNS (door number 'NNN.A1', frame/door material codes 'STL-1', 'WD-1', 'AL-1/GL-1', door type 'A1', feet-inch
strings), which is robust to column drift. Scanned sheets (no text layer) return [].
Evidence = row bounding boxes in PDF user units (multiply by 150/72 for a 150 dpi render).
"""
from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache
from typing import Optional

import pymupdf

from . import ifc_query as Q

DOOR_NO = re.compile(r"^\d{2,3}\.[A-Z]\d*$")
MATL = re.compile(r"^(STL|AL|WD|GL|HM|FRP|ALUM|WOOD)-\d+(?:/(?:STL|AL|WD|GL|HM)-\d+)?$")
TYPE = re.compile(r"^[A-Z]\d$")
DIM = re.compile(r"(?:(\d+/\d+)\")?\s*(\d+)\"?\s*-\s*(\d+)'")


def _cell_dim(tokens: list[str]) -> list[str]:
    s = " ".join(tokens)
    out = []
    for m in DIM.finditer(s):
        frac, inch, feet = m.groups()
        inches = f"{inch} {frac}" if frac else inch
        out.append(f"{feet}'-{inches}\"")
    return out


@lru_cache(maxsize=8)
def load(path: str):
    doc = pymupdf.open(path)
    pg = doc[0]
    words = pg.get_text("words")
    if len(words) < 50:
        return None
    vertical = sum(1 for w in words if (w[3] - w[1]) > 1.5 * (w[2] - w[0])) > len(words) / 2
    rows = defaultdict(list)
    for x0, y0, x1, y1, w, b, l, n in words:
        if vertical:
            rows[round((x0 + x1) / 2 / 3)].append((y0, w, (x0, y0, x1, y1)))
        else:
            rows[round((y0 + y1) / 2 / 3)].append((x0, w, (x0, y0, x1, y1)))
    # column anchors from the header words (position along the reading axis)
    def hdr(word):
        return sorted(t[0] for r in rows.values() for t in r if t[1] == word)
    notes_y = min(hdr("Notes"), default=None)
    specs_y = min(hdr("Specs"), default=None)
    matl_y = hdr("Matl")
    matl_split = (matl_y[0] + matl_y[1]) / 2 if len(matl_y) >= 2 else None
    doors = []
    for k in sorted(rows):
        toks = sorted(rows[k])
        if notes_y is not None:                      # legends/keynotes share the same lines left of the table
            toks = [t for t in toks if t[0] >= notes_y - 15]
        texts = [t[1] for t in toks]
        dn = [t for t in texts if DOOR_NO.match(t)]
        if not dn:
            continue
        dn_pos = next(i for i, t in enumerate(toks) if DOOR_NO.match(t[1]))
        room_no = None
        door_type = None
        frame_m, door_m = [], []
        for i, (c, t, bb) in enumerate(toks):
            if i == dn_pos:
                continue
            if re.fullmatch(r"\d{2,3}", t) and room_no is None and t == dn[0].split(".")[0]:
                room_no = t
            elif MATL.match(t):
                if matl_split is not None:
                    (door_m if c >= matl_split - 8 else frame_m).append(t)
                else:
                    (frame_m if not frame_m else door_m).append(t)
            elif TYPE.match(t) and door_type is None:
                door_type = t
        matl = [frame_m[0] if frame_m else None, door_m[0] if door_m else None]
        notes = []
        for c, t, bb in toks:
            if notes_y is not None and c < notes_y - 15:
                continue
            if specs_y is not None and c >= specs_y - 5:
                break
            if re.fullmatch(r"[A-Z],?", t):
                notes.append(t.rstrip(","))
        dims = _cell_dim([t[1] for t in toks])
        xs0 = min(t[2][0] for t in toks); ys0 = min(t[2][1] for t in toks)
        xs1 = max(t[2][2] for t in toks); ys1 = max(t[2][3] for t in toks)
        doors.append(dict(number=dn[0], room=room_no or dn[0].split(".")[0], frame_matl=matl[0], door_matl=matl[1],
                          door_type=door_type, notes=sorted(set(notes)), height=dims[0] if dims else None,
                          width=dims[1] if len(dims) > 1 else None, bbox=(xs0, ys0, xs1, ys1)))
    return dict(doors=doors, vertical=vertical)


def _box(b):
    x0, y0, x1, y1 = b
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def answer(path: str, intent: str, question: str, params: Optional[dict] = None):
    params = params or {}
    if "opening_design" not in path.replace("\\", "/"):
        return []
    if not intent.startswith("door_schedule") and intent != "unknown":
        return []
    sh = load(path)
    if not sh or not sh["doors"]:
        return []
    D = sh["doors"]
    note = "door-schedule rows from the PDF text layer (PyMuPDF words); exact source, single voter"

    def mk(rows, what):
        return [Q.IfcAnswer("pdf_vector", float(len(rows)), "count", f"{what}: {len(rows)} schedule rows; {note}",
                            element_ids=[f"pdf:row#{r['number']}" for r in rows])]
    if intent == "door_schedule_total":
        return mk(D, "all door rows")
    if intent == "door_schedule_by_type":
        return mk([r for r in D if r["door_type"] == params.get("type")], f"door type {params.get('type')}")
    if intent == "door_schedule_by_material":
        return mk([r for r in D if r["door_matl"] and params.get("material") and params["material"] in r["door_matl"].split("/")],
                  f"door material {params.get('material')}")
    if intent == "door_schedule_by_frame":
        codes = re.findall(r"[A-Z]{2,3}-\d", params.get("frame") or "")
        return mk([r for r in D if r["frame_matl"] in codes], f"frame {codes}")
    if intent == "door_schedule_by_note":
        return mk([r for r in D if params.get("note") in r["notes"]], f"note {params.get('note')}")
    if intent == "door_schedule_by_width":
        w = params.get("width")
        high = re.search(r"\bhigh\b", question, re.I) is not None
        key = "height" if high else "width"
        return mk([r for r in D if r[key] == w], f"{key} {w}")
    if intent == "unknown":
        m = re.search(r"list for room (\d{2,3})", question)
        if m:
            return mk([r for r in D if r["room"] == m.group(1)], f"doors of room {m.group(1)}")
    return []
