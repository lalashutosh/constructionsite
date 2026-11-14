"""Readers for big CAD / construction sheets (title block, border, several views). No CubiCasa CNN here.

Input: the image (BGR), the sheet profile (engine/profile.py) and the sheet words. Everything is read from LINE GEOMETRY
inside the main plan view only (title block, notes, schedules, legends, key plans are outside it; text is erased first,
so dimension chains and grid bubbles do not become walls):
  walls(img, prof, words)  -> [{outer, holes}]      thick/hatched wall bands and long line pairs, connected network only
  rooms(img, prof, words)  -> [Element room]        (a) closed regions of that wall network, labelled by the words inside
                                                    (b) colour-filled modules whose colour matches a legend swatch
                                                    (labelled by the legend text next to the swatch)
All coordinates are ORIGINAL image pixels. A region without a printed label stays a room-like space with label None."""
from __future__ import annotations

import re
from typing import Optional

import cv2
import numpy as np

from contracts.proof import Element

WORK = 2200
DIM_RX = re.compile(r"^[\d'\"\-/.,xX°′″()]+$|^\d+['\"]|^[A-Z]-?\d{1,3}$|^TYP\.?$|^\(?TYP\)?$|^SEE$|^NOTE", re.I)
STOP = {"TYP", "SEE", "AND", "THE", "OF", "FOR", "TO", "AT", "IN", "ON", "PER", "MAX", "MIN", "EL", "SIM", "NTS", "NOTE", "NOTES"}


def _boxes(prof: dict) -> list[list[int]]:
    """Plan views to read: the main view plus other plan views that are at least 30% as big."""
    plans = [v for v in prof.get("views", []) if v.get("kind") == "plan"]
    main = prof.get("main_view") or [0, 0, prof["width_px"], prof["height_px"]]
    a = lambda b: max(1, (b[2] - b[0]) * (b[3] - b[1]))
    out = [main] + [v["box"] for v in plans if v["box"] != main and a(v["box"]) >= 0.3 * a(main)]
    return out[:3]


def _ink_crop(img: np.ndarray, box: list[int], words: list[dict], prof: dict) -> tuple[np.ndarray, float]:
    from engine.profile import _ink_full
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img[y0:y1, x0:x1]
    s = min(1.0, WORK / max(crop.shape[:2]))
    ink = _ink_full(crop, s, 28 if prof.get("vector") else 55)
    if prof.get("vector") and max(crop.shape[:2]) < 2600:
        ink = cv2.dilate(ink, np.ones((2, 2), np.uint8))      # hairlines of a low-res PDF render survive the opening
    for v in prof.get("views", []):                          # notes / schedules / legends are not plan geometry
        if v.get("kind") in ("notes", "schedule", "legend", "key_plan") and v["box"] != box:
            a, b = int((v["box"][0] - x0) * s), int((v["box"][1] - y0) * s)
            c, d = int((v["box"][2] - x0) * s), int((v["box"][3] - y0) * s)
            ink[max(0, b):max(0, d), max(0, a):max(0, c)] = 0
    for w in words:                                          # text is not geometry
        bx0, by0, bx1, by1 = w["box"]
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            a, b = int((bx0 - x0) * s) - 2, int((by0 - y0) * s) - 2
            c, d = int((bx1 - x0) * s) + 2, int((by1 - y0) * s) + 2
            ink[max(0, b):max(0, d), max(0, a):max(0, c)] = 0
    return ink, s


def _solid(ink: np.ndarray, widen: float = 1.0) -> tuple[np.ndarray, int]:
    h, w = ink.shape
    gap = max(5, int(round(max(h, w) * 0.011 * widen)))          # bridges dashes and cross-hatching of a drawn wall band
    solid = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (gap, gap)))
    o = 3
    solid = cv2.morphologyEx(solid, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (o, o)))
    bridge = cv2.dilate(solid, np.ones((gap * 3, gap * 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(bridge, connectivity=8)
    keep = np.zeros_like(solid)
    if n > 1:
        big = max(st[i][4] for i in range(1, n))
        for i in range(1, n):
            if st[i][4] >= 0.10 * big:
                keep[lab == i] = 255
    return cv2.bitwise_and(solid, keep), gap


def walls(img: np.ndarray, prof: dict, words: list[dict]) -> list[dict]:
    """Wall bands of the plan view(s) as polygons in original px."""
    from engine import geometry3d
    out = []
    for box in _boxes(prof):
        ink, s = _ink_crop(img, box, words, prof)
        solid, gap = _solid(ink)
        solid[:2, :] = solid[-2:, :] = solid[:, :2] = solid[:, -2:] = 0
        x0, y0 = box[0], box[1]
        conv = lambda pts, s=s, x0=x0, y0=y0: [(x / s + x0, y / s + y0) for x, y in pts]
        h, w = solid.shape
        for wl in geometry3d._trace(solid, max(h * w * 0.00004, gap * gap * 2), max(1.0, gap * 0.25), conv):
            out.append(wl)
    return out


def _label_for(poly_px: np.ndarray, words: list[dict]) -> Optional[str]:
    inside = []
    for w in words:
        cx, cy = (w["box"][0] + w["box"][2]) / 2, (w["box"][1] + w["box"][3]) / 2
        if cv2.pointPolygonTest(poly_px.astype(np.float32).reshape(-1, 1, 2), (float(cx), float(cy)), False) >= 0:
            t = w["text"].strip()
            letters = sum(c.isalpha() for c in t)
            if letters >= 3 and letters >= 0.6 * len(t) and not DIM_RX.match(t) and t.upper() not in STOP and w.get("conf", 100) >= 50:
                inside.append((round(cy / 20), cx, t))
    if not inside:
        return None
    inside.sort()
    return " ".join(t for _, _, t in inside)[:48]


def _solidity(c) -> float:
    hull = cv2.convexHull(c)
    ha = cv2.contourArea(hull)
    return cv2.contourArea(c) / ha if ha > 0 else 0.0


def _wall_regions(img: np.ndarray, prof: dict, words: list[dict]) -> list[Element]:
    out: list[Element] = []
    for vi, box in enumerate(_boxes(prof)):
        ink, s = _ink_crop(img, box, words, prof)
        for widen in (1.0, 2.5):                         # second chance: a wall band with gaps (dashes, faint hatch)
            els = _regions_one(ink, s, box, vi, words, widen)
            if els:
                break
        out += els
    return out


def _regions_one(ink, s, box, vi, words, widen) -> list[Element]:
    out: list[Element] = []
    if True:
        x0, y0 = box[0], box[1]
        h, w = ink.shape
        gap = max(3, int(round(max(h, w) * 0.006 * widen)))   # bridges dash gaps and door openings in a drawn outline
        solid = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (gap, gap)))
        if ink.sum() < 0.004 * h * w:
            return out                                   # (almost) no linework here
        free = (solid == 0).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
        for i in range(1, n):
            x, y, bw, bh, a = st[i]
            if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
                continue                                 # touches the view edge = outside
            if not (0.003 * h * w <= a <= 0.75 * h * w):
                continue
            m = (lab == i).astype(np.uint8)
            cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            c = max(cs, key=cv2.contourArea)
            if _solidity(c) < 0.5:
                continue
            ring = cv2.dilate(m, np.ones((5, 5), np.uint8)) - m           # the region must be bounded by wall pixels
            if (solid[ring > 0] > 0).mean() < 0.55:
                continue
            ap = cv2.approxPolyDP(c, max(1.5, gap * 0.4), True)
            poly = [(float(p[0][0] / s + x0), float(p[0][1] / s + y0)) for p in ap]
            if len(poly) < 3:
                continue
            label = _label_for(np.array(poly), words)
            out.append(Element(id=f"space_{vi}_{i}", kind="room", subtype="enclosed_space", polygon=poly, label=label,
                               conf=0.6 if label else 0.45,
                               attrs={"source": "wall-network region", "area_px": float(a / (s * s)),
                                      "labelled": bool(label)}))
    return out


# ----------------------------------------------------------------------------- colour modules (legend swatches)
def _swatches(img: np.ndarray, prof: dict, words: list[dict]) -> list[dict]:
    """Chromatic filled rectangles outside the main view that have a legend word on their right."""
    H, W = img.shape[:2]
    s = min(1.0, 1800 / max(H, W))
    small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.int16)
    chroma = np.hypot(lab[:, :, 1] - 128, lab[:, :, 2] - 128)
    mask = (chroma > 7).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, lb, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    main = prof.get("main_view") or [0, 0, W, H]
    out = []
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if not (30 <= a <= 0.002 * small.shape[0] * small.shape[1]) or a < 0.8 * bw * bh or not (0.7 <= bw / bh <= 8):
            continue
        cx, cy = (x + bw / 2) / s, (y + bh / 2) / s
        if main[0] < cx < main[2] and main[1] < cy < main[3] and not _near_legend(prof, cx, cy):
            continue
        # a legend word on the same line to the right
        cand = [w for w in words if abs((w["box"][1] + w["box"][3]) / 2 - cy) < max(bh / s, 8)
                and 0 < w["box"][0] - (x + bw) / s < 30 * max(bw / s, 10)]
        if not cand:
            continue
        x_first = min(w["box"][0] for w in cand)
        line = sorted([w for w in words if abs((w["box"][1] + w["box"][3]) / 2 - cy) < max(bh / s, 8)
                       and w["box"][0] >= x_first - 2 and w["box"][0] - x_first < 400 * max(1, 1 / s)], key=lambda w: w["box"][0])
        text = " ".join(w["text"] for w in line)[:60]
        colour = np.median(lab[lb == i], axis=0)
        out.append({"lab": colour.tolist(), "label": text, "box": [x / s, y / s, (x + bw) / s, (y + bh) / s]})
    return out


def _near_legend(prof: dict, cx: float, cy: float) -> bool:
    for v in prof.get("views", []):
        if v.get("kind") in ("legend", "schedule", "key_plan") and v["box"][0] <= cx <= v["box"][2] and v["box"][1] <= cy <= v["box"][3]:
            return True
    return False


def _colour_modules(img: np.ndarray, prof: dict, words: list[dict]) -> list[Element]:
    sw = _swatches(img, prof, words)
    if not sw:
        return []
    box = prof.get("main_view") or [0, 0, prof["width_px"], prof["height_px"]]
    x0, y0, x1, y1 = [int(v) for v in box]
    crop = img[y0:y1, x0:x1]
    s = min(1.0, WORK / max(crop.shape[:2]))
    small = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else crop
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = small.shape[:2]
    out: list[Element] = []
    seen = []
    for k, sv in enumerate(sw):
        if any(np.linalg.norm(np.array(sv["lab"]) - np.array(o)) < 6 for o in seen):
            continue
        seen.append(sv["lab"])
        m = (np.linalg.norm(lab - np.array(sv["lab"], np.float32), axis=2) < 16).astype(np.uint8)
        k = max(3, int(0.006 * max(h, w)))              # white cell walls inside a coloured wing do not split it
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        n, lb, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
        for i in range(1, n):
            a = st[i][4]
            if a < 0.0015 * h * w:
                continue
            cs, _ = cv2.findContours((lb == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            c = max(cs, key=cv2.contourArea)
            ap = cv2.approxPolyDP(c, 2.0, True)
            if len(ap) < 3:
                continue
            poly = [(float(p[0][0] / s + x0), float(p[0][1] / s + y0)) for p in ap]
            out.append(Element(id=f"module_{k}_{i}", kind="zone", subtype="colour_module", polygon=poly,
                               label=sv["label"], conf=0.55,
                               attrs={"source": "legend colour", "legend": sv["label"], "area_px": float(a / (s * s))}))
    return out


def footprints(img: np.ndarray, prof: dict, words: list[dict]) -> list[Element]:
    """Overall outline (minimum rotated rectangle) of the biggest connected wall network of each plan view."""
    out: list[Element] = []
    for vi, box in enumerate(_boxes(prof)):
        ink, s = _ink_crop(img, box, words, prof)
        solid, gap = _solid(ink)
        h, w = solid.shape
        found = None
        for src, mask in (("wall network", solid), ("closed ink", cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((max(5, int(0.015 * max(h, w))),) * 2, np.uint8)))):
            n, lab, st, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
            if n < 2:
                continue
            i = max(range(1, n), key=lambda k: st[k][2] * st[k][3])
            if st[i][2] * st[i][3] >= 0.04 * h * w and st[i][4] >= 0.004 * h * w:
                found = (lab, i, src)
                break
        if found is None:
            continue
        lab, i, src = found
        # the building is every sizeable piece of the view, not only the biggest: wings of a T/L-shaped plan are often
        # joined by a thin corridor that breaks the wall network into several components
        keep = [k for k in range(1, n) if st[k][4] >= 0.15 * st[i][4]] or [i]   # n, st: the mask `found` came from
        pts = cv2.findNonZero(np.isin(lab, keep).astype(np.uint8))
        (cx, cy), (rw, rh), ang = cv2.minAreaRect(pts)
        poly = [(float(x / s + box[0]), float(y / s + box[1])) for x, y in cv2.boxPoints(((cx, cy), (rw, rh), ang))]
        out.append(Element(id=f"footprint_{vi}", kind="footprint", subtype="wall_network_outline", polygon=poly,
                           label=None, conf=0.5, attrs={"source": f"outline of the connected {src}", "from_walls": src == "wall network",
                                                       "length_px": float(max(rw, rh) / s), "width_px": float(min(rw, rh) / s)}))
    return out


def rooms(img: np.ndarray, prof: dict, words: list[dict]) -> list[Element]:
    mods = _colour_modules(img, prof, words)
    reg = _wall_regions(img, prof, words)
    if mods:                                             # colour modules explain the plan: wall regions inside them
        reg = []                                         # are the individual cells, not rooms to add on top
    els = mods + reg
    els.sort(key=lambda e: -e.attrs.get("area_px", 0))
    return els[:200]


ARCH_RX = re.compile(r"\b(FLOOR\s+PLAN|ROOMS?|DORM\w*|UNIT\s+PLAN|OFFICES?|KITCHEN|BEDROOMS?|BATH\w*|CORRIDOR|LIVING|APARTMENTS?|"
                     r"SUITES?|LOBBY|OPEN\s+TO\s+BELOW|LEVEL\s+\d|FIRST\s+FLOOR|SECOND\s+FLOOR|WC|TOILET|CLASSROOM)\b", re.I)
KINDS = [("foundation", r"FOUNDATION|FOOTING|SLAB"), ("roof", r"ROOF"), ("framing", r"FRAMING"), ("piping", r"PIPING|PIPE|FUEL|TANK"),
         ("site", r"SITE\s+PLAN|GRADING|UTILIT"), ("floor", r"FLOOR\s+PLAN|LEVEL|DORM|ROOM"), ("section", r"SECTION|ELEVATION|DETAIL")]


def plan_kind(prof: dict, words: list[dict]) -> str:
    """What the main drawing is (from view titles, else all sheet words): foundation / roof / piping / floor ..."""
    titles = " ".join((v.get("title") or "") for v in prof.get("views", []) if v.get("kind") == "plan")
    for text in (titles, " ".join(w["text"] for w in words)):
        for name, rx in KINDS:
            if re.search(rx, text, re.I):
                return name
    return "unknown"


def elements(img: np.ndarray, prof: dict, words: list[dict]) -> list[Element]:
    """Rooms only on sheets that look architectural (room/floor-plan words); on foundation / roof / piping sheets the
    closed regions are reported as 'region' (not rooms), so 'how many rooms' is not answered with tank pads."""
    text = " ".join(w["text"] for w in words)
    arch = bool(ARCH_RX.search(text))
    rs = rooms(img, prof, words)
    if not arch:
        for e in rs:
            if e.subtype == "enclosed_space":
                e.kind = "region"
    return rs + footprints(img, prof, words)


def extract_facts(path: str, abs_path: str, prof: dict):
    """SheetFacts for a CAD / construction sheet from line geometry (no CubiCasa CNN)."""
    from contracts.proof import Provenance, SheetFacts
    from engine import profile as P
    img, info = P._load(abs_path)
    words = P.words_for(abs_path, prof["sha256"], img, info)
    els = elements(img, prof, words)
    H, W = img.shape[:2]
    extras = {"route": "cad", "profile": light(prof), "n_words": len(words), "plan_kind": plan_kind(prof, words)}
    notes = []
    if not any(e.kind == "room" for e in els):
        notes.append(f"no rooms recognised (plan kind: {extras['plan_kind']})")
    return SheetFacts(provenance=Provenance(file=path, sha256=prof["sha256"], fmt=abs_path.rsplit(".", 1)[-1].lower()),
                      sheet_type="floor_plan", legible=True, width_px=W, height_px=H, elements=els, extras=extras,
                      legibility_note="; ".join(notes) or None)


def light(prof: dict) -> dict:
    """The profile without bulky fields, for facts.extras (the UI and other stages read it from there)."""
    return {k: v for k, v in prof.items() if k not in ("sha256",)}
