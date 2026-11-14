"""Layers of a drawing, like the systems of a body: envelope (skin), walls (skeleton), furniture/fixtures (organs),
piping (veins), electrical (nerves). Each layer is geometry in ORIGINAL image px for the viewer to toggle and colour.

- envelope: the verified building outline (engine/outline.py / legend-zone union);
- walls: the 3D model's wall rings;
- furniture: the deep-read symbol nodes (engine/symbols.py cache) when that read has run;
- piping / electrical: on an MEP sheet (sheet id M-/P-/FP- = piping, E- = electrical) the discipline's black linework
  drawn over the screened (grey) building, inside the outline, text removed, as simplified polylines.
A layer that a sheet does not carry is returned empty with a reason, never invented."""
from __future__ import annotations

import json
import re
from typing import Any

import cv2
import numpy as np

SHEET_ID = re.compile(r"^(FP|[A-Z])-?\d{2,3}[A-Z]?$")


def discipline(words: list[dict]) -> str | None:
    """'M-101A' in the title block -> 'M'. The largest such id wins (the sheet number is printed big)."""
    if not words:
        return None
    W = max(w["box"][2] for w in words)
    H = max(w["box"][3] for w in words)
    best = None
    for w in words:
        t = w["text"].strip().upper()
        m = SHEET_ID.match(t)
        if not m or w.get("angle", 0) != 0:
            continue
        in_tb = w["box"][0] > 0.8 * W or w["box"][1] > 0.88 * H      # the title block: right strip / bottom band
        sc = (w["box"][3] - w["box"][1]) * (3 if in_tb else 1)
        if best is None or sc > best[0]:
            best = (sc, m.group(1))
    return best[1] if best else None


def _linework(abs_path: str, facts, words: list[dict], max_lines: int = 2500) -> list[list[list[float]]]:
    g = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
    fp = next((e for e in facts.elements if e.kind == "footprint" and e.attrs.get("source") == "outline"), None)
    if g is None or fp is None:
        return []
    mask = np.zeros(g.shape, np.uint8)
    cv2.fillPoly(mask, [np.array(fp.polygon, np.int32)], 1)
    mask = cv2.dilate(mask, np.ones((25, 25), np.uint8))              # pipes leave through the walls
    dark = ((g < 110) & (mask > 0)).astype(np.uint8)
    for w in words:
        a, b, c, d = [int(v) for v in w["box"]]
        dark[max(0, b - 2):d + 3, max(0, a - 2):c + 3] = 0
    s = min(1.0, 3000 / max(g.shape))
    small = (cv2.resize(dark * 255, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) > 60).astype(np.uint8)
    lines = cv2.morphologyEx(small, cv2.MORPH_OPEN, np.ones((1, 9), np.uint8)) | \
        cv2.morphologyEx(small, cv2.MORPH_OPEN, np.ones((9, 1), np.uint8))       # straight runs, not symbols
    cs, _ = cv2.findContours(lines, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in sorted(cs, key=lambda c: -cv2.arcLength(c, False))[:max_lines]:
        if cv2.arcLength(c, False) < 20:
            continue
        ap = cv2.approxPolyDP(c, 1.5, False).reshape(-1, 2)
        out.append([[float(x / s), float(y / s)] for x, y in ap])
    return out


def layers(abs_path: str, facts, geo: dict) -> dict[str, Any]:
    from engine.scale import sheet_text as T
    sha = facts.provenance.sha256
    words = T.words(abs_path, sha) if sha else []
    out: dict[str, Any] = {"envelope": [], "walls": [w["outer"] for w in geo.get("walls", [])], "furniture": [],
                           "piping": [], "electrical": [], "notes": {}}
    fp = next((e for e in facts.elements if e.kind == "footprint" and e.attrs.get("source") == "outline"), None)
    if fp is not None:
        out["envelope"] = [[list(map(float, p)) for p in fp.polygon]]
    try:                                                  # furniture nodes from a finished deep read (cached)
        from engine import symbols
        for f in sorted(symbols.CACHE.glob(f"{sha}-{symbols.VERSION}*.json")):
            ck = json.loads(f.read_text())
            out["furniture"] = [{"id": e["id"], "kind": e["kind"], "label": e.get("label"), "polygon": e["polygon"]}
                                for e in ck.get("elements", [])]
            break
        if not out["furniture"]:
            out["notes"]["furniture"] = "run the deep read (checklist) to place every furniture symbol"
    except Exception:  # noqa: BLE001
        pass
    disc = discipline(words)
    out["discipline"] = disc
    if disc in ("M", "P", "FP"):
        out["piping"] = _linework(abs_path, facts, words)
        out["notes"]["electrical"] = "no electrical sheet in this set (this is a piping / mechanical sheet)"
    elif disc == "E":
        out["electrical"] = _linework(abs_path, facts, words)
        out["notes"]["piping"] = "no piping sheet in this set (this is an electrical sheet)"
    else:
        msg = f"not on this sheet ({'sheet ' + disc + '-' if disc else 'an architectural / structural sheet'}); upload the MEP sheet of the same floor"
        out["notes"]["piping"] = msg
        out["notes"]["electrical"] = msg
    return out
