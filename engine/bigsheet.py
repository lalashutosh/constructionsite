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
        try:                                              # legend words are short and small: re-read them at 2x
            from engine import sheet_lookup as SL
            bx = [min(w["box"][0] for w in line), min(w["box"][1] for w in line),
                  max(w["box"][2] for w in line), max(w["box"][3] for w in line)]
            hh = float(np.median([w["box"][3] - w["box"][1] for w in line]))
            rr = SL.reread_box(prof.get("_abs_path", ""), [bx[0] + 2.6 * hh, bx[1] + 1.2 * hh, bx[2], bx[3] - 1.2 * hh], hh) \
                if prof.get("_abs_path") else None
            rr = re.sub(r"^[^A-Za-z0-9(]+|[^A-Za-z0-9)]+$", "", rr or "") or None   # swatch edge / stray marks
            if rr and 0.5 <= len(rr) / max(1, len(text)) <= 1.6 and sum(c.isalpha() for c in rr) >= 0.7 * len(rr.replace(" ", "")):
                text = rr[:60]
        except Exception:  # noqa: BLE001
            pass
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
    blank = np.zeros((h, w), bool)                       # notes / legends / schedules / key plans are not the plan
    for v in prof.get("views", []):
        if v.get("kind") in ("notes", "schedule", "legend", "key_plan") and v["box"] != box:
            a, b = int((v["box"][0] - x0) * s), int((v["box"][1] - y0) * s)
            c, d = int((v["box"][2] - x0) * s), int((v["box"][3] - y0) * s)
            blank[max(0, b):max(0, d), max(0, a):max(0, c)] = True
    wordm = np.zeros((h, w), np.uint8)
    from engine.sheet_lookup import _english
    for wd in words:              # REAL words only (dictionary, confident): furniture / hatch OCR noise is not text
        t = re.sub(r"[^A-Za-z]", "", wd["text"])
        if len(t) < 3 or wd.get("conf", 0) < 60 or not _english(t):
            continue
        a, b = int((wd["box"][0] - x0) * s), int((wd["box"][1] - y0) * s)
        c, d = int((wd["box"][2] - x0) * s), int((wd["box"][3] - y0) * s)
        if c > 0 and d > 0 and a < w and b < h:
            wordm[max(0, b):d, max(0, a):c] = 1
    out: list[Element] = []
    seen = []
    for k, sv in enumerate(sw):
        if any(np.linalg.norm(np.array(sv["lab"]) - np.array(o)) < 6 for o in seen):
            continue
        seen.append(sv["lab"])
        m = (np.linalg.norm(lab - np.array(sv["lab"], np.float32), axis=2) < 16).astype(np.uint8)
        m[blank] = 0
        k = max(3, int(0.006 * max(h, w)))              # white cell walls inside a coloured wing do not split it
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        n, lb, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
        for i in range(1, n):
            a = st[i][4]
            if a < 0.0015 * h * w:
                continue
            comp = (lb == i)
            if wordm[comp].mean() > 0.12:
                continue                       # a block of text (notes, tables), not a coloured room / wing
            cs, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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
    prof = {**prof, "_abs_path": abs_path}
    els = elements(img, prof, words)
    H, W = img.shape[:2]
    extras = {"route": "cad", "profile": light(prof), "n_words": len(words), "plan_kind": plan_kind(prof, words)}
    try:                       # at a solved scale the verified outline + its zones replace the line-geometry guesses
        ol = _outline_elements(abs_path, prof, words)
    except Exception as e:  # noqa: BLE001
        ol = None
        extras["outline_error"] = f"{type(e).__name__}: {e}"
    colour = [e for e in els if e.kind == "zone"]
    post_subrooms = True
    if ol is not None:
        els_ol, info = ol
        els = colour + els_ol                                   # legend-matched colour modules stay (they are read
        extras["outline"] = info                                # from the legend); slivers / hatch 'rooms' go
    elif colour:                                                # colour-coded plan: the building = its legend zones
        fp = _zones_union(colour, abs_path, prof)
        els = colour + ([fp] if fp is not None else [])
        if fp is not None:
            extras["outline"] = {k: fp.attrs.get(k) for k in ("area_m2", "bbox_m", "method", "px_per_m")}
    try:                                   # every enclosed space inside the building, named when the sheet names it
        fp = next((e for e in els if e.kind == "footprint" and e.attrs.get("source") == "outline"), None)
        if fp is not None and post_subrooms:
            els += _subroom_elements(abs_path, prof, words, fp, colour)
    except Exception as e:  # noqa: BLE001
        extras["subroom_error"] = f"{type(e).__name__}: {e}"
    notes = []
    if not any(e.kind == "room" for e in els):
        notes.append(f"no rooms recognised (plan kind: {extras['plan_kind']})")
    return SheetFacts(provenance=Provenance(file=path, sha256=prof["sha256"], fmt=abs_path.rsplit(".", 1)[-1].lower()),
                      sheet_type="floor_plan", legible=True, width_px=W, height_px=H, elements=els, extras=extras,
                      legibility_note="; ".join(notes) or None)


_SPACE_EXTRA = {"ROOM", "PUMPHOUSE", "PUMP HOUSE", "OFFICE", "CORRIDOR", "LOBBY", "MECHANICAL", "ELECTRICAL", "STAIR",
                "STAIRS", "STORAGE", "TOILET", "RESTROOM", "DORMITORY", "WAREHOUSE", "GARAGE", "SERVER", "DATA", "HALL",
                "CLASSROOM", "LAB", "LABORATORY", "KITCHEN", "BREAKROOM", "MEETING", "CONFERENCE", "UTILITY", "JANITOR",
                "SHOP", "VESTIBULE", "ENTRY", "CIRCULATION", "TELECOM", "IT", "UPS", "BATTERY", "GENERATOR", "GENSET"}


def _space_word(t: str) -> bool:
    """Is this printed word the NAME of a space (room glossary of the readers + common commercial space nouns)?"""
    from engine import label_reader as LR
    w = re.sub(r"[^A-Za-z ]", "", t).strip().upper()
    if not w:
        return False
    try:
        gl = {k.upper() for k in LR.glossary().get("room_labels", {})} if hasattr(LR, "glossary") else set()
    except Exception:  # noqa: BLE001
        gl = set()
    return w in _SPACE_EXTRA or (len(w) >= 4 and w in gl)


def _subroom_elements(abs_path: str, prof: dict, words: list[dict], fp, colour: list) -> list[Element]:
    from shapely.geometry import Point, Polygon
    from engine import outline as O
    from engine.sheet_lookup import _english
    ppm = float(fp.attrs["px_per_m"])
    rs = O.subrooms(abs_path, prof["sha256"], ppm, fp.polygon)
    zones = [(Polygon(z.polygon).buffer(0), z.label) for z in colour if len(z.polygon) >= 3 and z.label]
    slab = re.compile(r"^\d{2,3}$")
    out = []
    for i, r in enumerate(rs):
        poly = Polygon(r["polygon"]).buffer(0)
        inside = [w for w in words if poly.contains(Point((w["box"][0] + w["box"][2]) / 2, (w["box"][1] + w["box"][3]) / 2))]
        name = next((w["text"] for w in sorted(inside, key=lambda w: -(w["box"][3] - w["box"][1])) if _space_word(w["text"])), None)
        if name is None:                         # the legend zone it lies in (DORMITORY, CIRCULATION ...)
            c = Point(*r["centroid"])
            name = next((lb for z, lb in zones if z.contains(c)), None)
        if name is None:                         # a slab note printed in it: '300 SLAB-ON-GRADE W/ D16'
            txt = " ".join(w["text"] for w in sorted(inside, key=lambda w: (w["box"][1], w["box"][0])))
            m = re.search(r"\b(\d{2,3})\s*SLAB", txt.upper())
            if m:
                bar = re.search(r"D\d{1,2}", txt.upper())
                name = f"{m.group(1)} slab" + (f" {bar.group(0)}" if bar else "")
        out.append(Element(id=f"room_sub_{i}", kind="room", subtype=(name or "space").lower().replace(" ", "_")[:30],
                           polygon=[tuple(p) for p in r["polygon"]], label=name, conf=0.6,
                           attrs={"area_m2": r["area_m2"], "source": "enclosed by wall lines inside the outline",
                                  "px_per_m": ppm}))
    return out


def _outline_elements(abs_path: str, prof: dict, words: list[dict]):
    """Footprint + zones from engine/outline.py at the sheet's own solved scale (None when the scale is not solid)."""
    from engine import outline as O
    from engine.scale import sheet_scale as S
    sha = prof["sha256"]
    st = S.sheet_state(abs_path, sha)
    win = st["cons"]["winner"]
    if not win or st["conf"] < 0.4:
        return None
    ppm = float(win["ppm"])
    r = O.outline(abs_path, sha, ppm, prof.get("main_view"))
    if not r or r["area_m2"] < 4:
        return None
    try:                       # cross-check against the printed overall dimensions (verified ones only)
        from engine import sheet_lookup as L
        od = L.overall_dims(abs_path, sha, ppm) or {}
        if "w" in od and "d" in od:
            pw, pd = sorted([od["w"]["m"], od["d"]["m"]])
            mw, md = sorted(r["bbox_m"])
            if abs(mw / pw - 1) > 0.15 or abs(md / pd - 1) > 0.15:
                return None    # the traced outline is not the building the sheet dimensions: do not show it
    except Exception:  # noqa: BLE001
        pass
    from shapely.geometry import Polygon, Point
    out = [Element(id="footprint_ol", kind="footprint", polygon=[tuple(p) for p in r["polygon"]], conf=0.7,
                   attrs={"area_m2": r["area_m2"], "bbox_m": r["bbox_m"], "method": r["method"], "px_per_m": ppm,
                          "from_walls": True, "source": "outline"})]
    labels = []
    from engine.sheet_lookup import _english
    for w in words:               # zone names from REAL printed words only (no hatch / pipe-symbol OCR noise)
        t = w["text"].strip()
        tt = re.sub(r"[^A-Za-z]", "", t)
        if (len(tt) >= 3 and w.get("conf", 0) >= 70 and _english(tt) and not DIM_RX.match(t)
                and t.upper() not in STOP):
            b = w["box"]
            labels.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, t, b[3] - b[1]))
    for i, z in enumerate(r["zones"]):
        if z["area_m2"] < 0.02 * r["area_m2"]:
            continue
        poly = Polygon(z["polygon"])
        inside = [l for l in labels if poly.contains(Point(l[0], l[1]))]
        inside.sort(key=lambda l: (-l[3], l[1], l[0]))                     # biggest printed name first
        named = [l for l in inside if _space_word(l[2])]                  # a SPACE name, not a callout inside it
        lab = named[0][2] if named else None
        out.append(Element(id=f"zone_ol_{i}", kind="region", subtype="zone", polygon=[tuple(p) for p in z["polygon"]],
                           label=lab, conf=0.6, attrs={"area_m2": z["area_m2"], "source": "outline zones",
                                                        "px_per_m": ppm}))
    return out, {"area_m2": r["area_m2"], "bbox_m": r["bbox_m"], "method": r["method"], "px_per_m": ppm,
                 "zones": len(out) - 1}


def _zones_union(colour: list, abs_path: str, prof: dict):
    """Footprint of a colour-coded plan = union of its legend zones (white cell walls between them bridged)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from engine.scale import sheet_scale as S
    st = S.sheet_state(abs_path, prof["sha256"])
    win = st["cons"]["winner"]
    if not win or st["conf"] < 0.4:
        return None
    ppm = float(win["ppm"])
    polys = [Polygon(e.polygon).buffer(0) for e in colour if len(e.polygon) >= 3]
    u = unary_union([p.buffer(0.6 * ppm, join_style=2) for p in polys if p.area > 0]).buffer(-0.6 * ppm, join_style=2)
    if u.is_empty:
        return None
    if u.geom_type == "MultiPolygon":
        u = max(u.geoms, key=lambda g: g.area) if max(g.area for g in u.geoms) > 0.8 * u.area else u.convex_hull
    u = u.simplify(0.1 * ppm)
    x0, y0, x1, y1 = u.bounds
    return Element(id="footprint_zones", kind="footprint", polygon=[tuple(map(float, c)) for c in u.exterior.coords][:-1],
                   conf=0.65, attrs={"area_m2": round(u.area / ppm ** 2, 1),
                                     "bbox_m": [round((x1 - x0) / ppm, 2), round((y1 - y0) / ppm, 2)],
                                     "method": "union of the legend colour zones", "px_per_m": ppm,
                                     "from_walls": True, "source": "outline"})


def light(prof: dict) -> dict:
    """The profile without bulky fields, for facts.extras (the UI and other stages read it from there)."""
    return {k: v for k, v in prof.items() if k not in ("sha256",)}
