"""Swiss Dwellings floor-plan PDFs (vector, text layer) read through PyMuPDF `get_drawings()` / `get_text()`.

Symbol signatures were found by comparing path counts with the answer key (see docs/handoff/vector.md):
  doors      = stroked 1-quad paths, colour (0.27,0.27,0.27), width 0.37          (one per door frame)
  toilets    = single-line black paths, width 0.51, 1 item                          (WC symbol marker)
  washbasins = 47-item black line paths (width 0.51)  minus toilets                  (the WC symbol also draws one)
  bathtubs   = 68-item black line paths (width 0.51)
  showers    = single-quad black paths, width 0.51
  room_labelled / apartments / printed areas: text layer ('Stanza', 'App. A', '5.37 m²').
Used (a) alone when the PDF is the given file (`--no-siblings`) and (b) as an independent second voter next to the DXF.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

import pymupdf

from .dxf import APT_LABEL, NUM_RE

BLACK = (0.0, 0.0, 0.0)
GREY27 = (0.27, 0.27, 0.27)


@lru_cache(maxsize=16)
def load(path: str) -> dict:
    pg = pymupdf.open(path)[0]
    sig: dict = {}
    door_boxes, tub, sho = [], [], []
    for d in pg.get_drawings():
        if d.get("fill") is not None:
            continue
        col = tuple(round(x, 2) for x in d["color"]) if d.get("color") else None
        w = round(d.get("width") or 0, 2)
        kinds = {it[0] for it in d["items"]}
        n = len(d["items"])
        r = d["rect"]
        box = [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]
        if col == GREY27 and w == 0.37 and kinds == {"qu"} and n == 1:
            door_boxes.append(box)
        elif col == BLACK and w == 0.51 and kinds == {"l"}:
            sig.setdefault(("l", n), []).append(box)
        elif col == BLACK and w == 0.51 and kinds == {"qu"} and n == 1:
            sho.append(box)
    lines = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t:
                x0, y0, x1, y1 = l["bbox"]
                lines.append((t, x0, y0, x1, y1))
    ratio = None
    for t, *_ in lines:
        m = re.search(r"\b1\s*:\s*(\d{2,4})\b", t)
        if m:
            ratio = float(m.group(1))
            break
    words = [w[4] for w in pg.get_text("words")]
    return dict(doors=door_boxes, l1=sig.get(("l", 1), []), l47=sig.get(("l", 47), []), l68=sig.get(("l", 68), []),
                showers=sho, lines=lines, ratio=ratio, words=words)


def printed_areas(words: list[str]) -> dict[str, float]:
    """room number -> printed area, from the word stream '... 5.02 15.84 m² ...'."""
    out = {}
    for i, w in enumerate(words):
        if NUM_RE.match(w) and i + 2 < len(words) and words[i + 2] == "m²":
            try:
                out[w] = float(words[i + 1])
            except ValueError:
                pass
    return out


def room_names(lines) -> set[str]:
    names = set()
    for t, *_ in lines:
        if NUM_RE.match(t) or "m²" in t or APT_LABEL.match(t) or len(t) > 40:
            continue
        names.add(t)
    return names


def fixture_counts(sh: dict) -> dict[str, int]:
    nt = len(sh["l1"])
    return {"toilets": nt, "washbasins": max(0, len(sh["l47"]) - nt), "bathtubs": len(sh["l68"]), "showers": len(sh["showers"])}


def answer(path: str, intent: str, question: str, params: Optional[dict] = None):
    """Returns list of (voter_name, value, unit, note, elements) for the intents this PDF can answer exactly."""
    from . import dxf_query as DQ  # label parsing helper
    params = params or {}
    sh = load(path)
    out = []
    if intent == "doors":
        out.append(("pdf_vector", float(len(sh["doors"])), "count",
                    "stroked door-frame quads (grey 0.27, width 0.37) in the PDF vector layer",
                    [(f"pdf:door#{i}", "door", [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], None, {}) for i, b in enumerate(sh["doors"])]))
    elif intent in ("toilets", "washbasins", "bathtubs", "showers"):
        fc = fixture_counts(sh)
        key = "l1" if intent == "toilets" else "l68" if intent == "bathtubs" else "showers" if intent == "showers" else "l47"
        boxes = sh[key]
        out.append(("pdf_vector", float(fc[intent]), "count",
                    {"toilets": "WC symbol markers (1-line black paths)", "washbasins": "47-item basin/WC symbol paths minus toilets",
                     "bathtubs": "68-item bathtub symbol paths", "showers": "single-quad shower symbols"}[intent] + " in the PDF vector layer",
                    [(f"pdf:{intent}#{i}", "fixture", [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], None, {"subtype": intent}) for i, b in enumerate(boxes)]))
    elif intent == "apartments":
        labs = [t for t, *_ in sh["lines"] if APT_LABEL.match(t.strip())]
        out.append(("pdf_vector", float(len(labs)), "count", "apartment labels (App./Whg. X) in the PDF text layer", []))
    elif intent == "room_labelled":
        names = room_names(sh["lines"])
        lab = _label(question, names, params)
        if lab:
            els = [(f"pdf:label#{i}", "label", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], t, {}) for i, (t, x0, y0, x1, y1) in enumerate(sh["lines"]) if t == lab]
            out.append(("pdf_vector", float(len(els)), "count", f"text lines equal to '{lab}' in the PDF text layer", els))
    elif intent == "room_area":
        num = params.get("room")
        if not num:
            m = re.search(r"\b([A-Z]{0,2}\d+\.\d+)\b", question)
            num = m.group(1) if m else None
        pa = printed_areas(sh["words"])
        if num in pa:
            out.append(("pdf_vector", pa[num], "m2", f"printed area label of room {num} in the PDF text layer", []))
    elif intent in ("room_area_labelled", "total_net_area", "apartment_net_area"):
        pass
    return out


def _label(question: str, names: set[str], params: dict) -> Optional[str]:
    ns = sorted(names, key=len, reverse=True)
    m2 = re.search(r"[«“„‘'\"]\s*(.+)\s*[»”“’'\"]", question, re.S)
    if m2:
        cand = m2.group(1).strip().casefold()
        for n in ns:
            if n.casefold() == cand:
                return n
    q = question.casefold()
    for n in ns:
        if re.search(r"(?<!\w)" + re.escape(n.casefold()) + r"(?!\w)", q):
            return n
    return params.get("label")
