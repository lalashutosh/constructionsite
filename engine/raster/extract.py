"""ROUTE A extractor for small CubiCasa5k-style raster floor plans: the pretrained CubiCasa5k
multi-task CNN (rooms + icons) is the primary reader (see docs/decisions/weights.md). Falls back
to ROUTE B (classical CV: dark-pixel wall mask + flood fill + OCR) if the weights are unavailable
at import time -- this never happens in this repo's current state, it is a safety net so `extract`
never raises just because `weights/` is missing in some other checkout.

`extract(path, *, allow_siblings=True) -> SheetFacts`. Every element's polygon is in ORIGINAL
image pixel coordinates (engine.raster.prep.Variant.to_original is the only place pixels get
mapped back). No network calls. Results are cached by sha256 under cache/raster/.

CPU time budget: a single forward pass of the pretrained model at the canonical (long-side-800)
scale takes ~1.2-1.9s on this machine (16 threads) -- already most of the 2s/image smoke budget,
so unlike the OCR/CV signals the CNN runs ONCE per image (no rotation/flip TTA of the heavy net).
OCR runs concurrently with the CNN in a thread pool to overlap latency instead of adding to it.
`Voter.runs` (contracts/proof.py) therefore comes from a cheap multi-threshold bootstrap of the
CNN's saved probability maps (see `_THRESHOLDS` below), not from re-running the network -- this
substitution is documented in docs/decisions/weights.md.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import pathlib

import cv2
import numpy as np

from contracts.proof import Element, Provenance, SheetFacts
from engine.raster import model as cc_model
from engine.raster import ocr as cc_ocr
from engine.raster import prep

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE_DIR = _REPO_ROOT / "cache" / "raster"

CREDIT = "CubiCasa5k dataset (Kalervo, Ylioinas, Haikio, Karhu, Kannala, 2019), CC BY-NC-SA 4.0"
LICENSE = "CC BY-NC-SA 4.0"

# icon-class -> Element.kind (engine.raster.model.ICON_CLASSES). "empty" is not an element.
_ICON_KIND = {
    "window": "window", "door": "door", "toilet": "toilet", "sink": "sink",
    "bathtub": "bath", "sauna_bench": "sauna_bench", "fire_place": "fireplace",
    "closet": "closet", "electr_appl": "appliance", "chimney": "chimney",
}
# room-class -> default Element.subtype (engine.raster.model.ROOM_CLASSES); OCR overrides this
# when a label lands inside the room's polygon (OCR is the only signal for wc/sauna/balcony, since
# the pretrained model has no separate class for them -- see docs/decisions/weights.md).
_ROOM_KIND = {
    "kitchen": "kitchen", "living_room": "living", "bedroom": "bedroom",
    "bath": "bathroom", "hallway": "hallway", "storage": "storage",
    "garage": "garage", "other_rooms": "room",
}
_ROOM_SKIP = {"background", "outdoor", "wall", "railing"}  # not room instances
_THRESHOLDS = (0.4, 0.5, 0.6)  # bootstrap confidence levels for icon Voter.runs
_MIN_ICON_AREA = 30  # 10 -> 30: sweep on 199 DEV images (windows/doors/sinks all prefer 30)
# Room components smaller than this fraction of the image are CNN slivers, not rooms. 0.015 chosen
# on a coarse grid {0.005..0.03}: bedrooms 47% -> 75%. (question: 'How many bedrooms ...')
_MIN_ROOM_FRAC = 0.015
_MIN_ROOM_AREA = 60


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(path: str, *, allow_siblings: bool = True) -> SheetFacts:
    """Extractor protocol (prompts/11_w1_raster.md Step 2). `allow_siblings` is accepted for
    protocol compatibility; cubicasa5k pngs have no vector siblings in this dataset, so it is a
    no-op here."""
    sha = sha256_file(path)
    cache_file = CACHE_DIR / f"{sha}.json"
    if cache_file.exists():
        try:
            cached = SheetFacts.model_validate_json(cache_file.read_text())
            # a route-B (no CNN) result cached before the weights existed must not outlive them
            if not (cached.extras.get("route") == "B" and cc_model.available()):
                return cached
        except Exception:
            pass  # corrupt cache entry: fall through and recompute

    img = prep.load_rgb(path)
    h, w = img.shape[:2]
    variant = prep.make_variants(w, h, cap=1)[0]  # canonical scale only, see module docstring
    rendered = variant.render(img)

    cnn_out = None
    route = "B"
    if cc_model.available():
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                f_cnn = ex.submit(cc_model.infer_tta, rendered)
                # 2 of the 4 rotations (0/90) while the CNN runs concurrently: the full 4-rotation
                # OCR pass plus the CNN pass together blew the 2s/image budget (docs/decisions/
                # weights.md); this trades some recall on upside-down text for speed.
                f_ocr = ex.submit(cc_ocr.ocr_tokens, img, rotations=(0, 1))
                cnn_out = f_cnn.result()
                tokens = f_ocr.result()
            route = "A"
        except Exception:
            cnn_out = None
            tokens = cc_ocr.ocr_tokens(img, rotations=(0, 1))
    else:
        tokens = cc_ocr.ocr_tokens(img, rotations=(0, 1))

    elements: list[Element] = []
    extras: dict = {"route": route}

    floor_elements, floor_runs = _floor_blobs(img)
    elements.extend(floor_elements)
    extras["cnn_runs"] = {"floors": floor_runs}

    claimed_token_idx: set[int] = set()
    if cnn_out is not None:
        rooms_p, icons_p = cnn_out
        el_rooms, room_runs, claimed_token_idx = _rooms_from_cnn(rooms_p, variant, tokens)
        el_icons, icon_runs = _icons_from_cnn(icons_p, variant)
        elements.extend(el_rooms)
        elements.extend(el_icons)
        extras["cnn_runs"].update(room_runs)
        extras["cnn_runs"].update(icon_runs)
    else:
        el_cv, claimed_token_idx = _route_b(img, tokens)
        elements.extend(el_cv)

    # OCR labels not claimed by any room polygon are still recorded as `label` elements: evidence
    # a human can check even when the geometry assignment failed (e.g. balconies, which the model
    # classifies as "outdoor" and are therefore never a `room` element above).
    for i, tok in enumerate(tokens):
        if tok.category:
            # every lexicon hit is kept (also those a room polygon claimed): the label-first
            # count rules (engine/count/rules.py bedrooms/saunas) need ALL MH/S hits, not only
            # the ones outside room polygons
            x, y, bw, bh = tok.bbox
            elements.append(Element(
                id=f"label_{i}", kind="label", subtype=tok.category,
                polygon=[(x, y), (x + bw, y), (x + bw, y + bh), (x, y + bh)],
                label=tok.text, conf=min(1.0, tok.conf / 100.0),
                attrs={"claimed": i in claimed_token_idx},
            ))

    facts = SheetFacts(
        provenance=Provenance(file=path, sha256=sha, fmt="png", license=LICENSE, credit=CREDIT),
        sheet_type="floor_plan", legible=True, width_px=w, height_px=h, language="fi",
        elements=elements, extras=extras,
    )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(facts.model_dump_json())
    return facts


def _components(mask_bool: np.ndarray, min_area: int):
    mask = mask_bool.astype(np.uint8)
    if mask.sum() == 0:
        return [], None, None
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    comps = []
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        x, y = int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP])
        bw, bh = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
        comps.append((x, y, bw, bh, area, i))
    return comps, labels, stats


def _floor_blobs(img: np.ndarray) -> tuple[list[Element], list[int]]:
    """Disjoint plan views: connected 'ink' (non-near-white) blobs comparable in size to the
    largest one (prompts/11_w1_raster.md Step 3: 'floors: number of disjoint plan views ...
    default 1'). Route-independent: runs directly on the loaded image, no model needed. Returns
    (elements, bootstrap-count-runs) where runs vary the 'comparable size' ratio for a cheap
    uncertainty spread (no second render needed)."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, ink = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    min_area = max(50, int(0.002 * img.shape[0] * img.shape[1]))
    comps, _, _ = _components(ink > 0, min_area)
    if not comps:
        h, w = img.shape[:2]
        el = Element(id="floor_0", kind="floor_blob",
                     polygon=[(0, 0), (w, 0), (w, h), (0, h)], conf=0.3)
        return [el], [1]
    biggest = max(c[4] for c in comps)
    runs = [sum(1 for c in comps if c[4] >= r * biggest) for r in (0.25, 0.35, 0.45)]
    elements = []
    for j, (x, y, bw, bh, area, _lbl) in enumerate(comps):
        if area >= 0.35 * biggest:
            elements.append(Element(id=f"floor_{j}", kind="floor_blob",
                                     polygon=[(x, y), (x + bw, y), (x + bw, y + bh), (x, y + bh)],
                                     conf=1.0, attrs={"area_px": area}))
    return elements, runs


def _icons_from_cnn(icons_p: np.ndarray, variant) -> tuple[list[Element], dict]:
    elements: list[Element] = []
    runs: dict[str, list[int]] = {}
    for idx, name in enumerate(cc_model.ICON_CLASSES):
        kind = _ICON_KIND.get(name)
        if kind is None:
            continue
        prob = icons_p[idx]
        counts = []
        canonical = None
        for th in _THRESHOLDS:
            comps, _, _ = _components(prob >= th, _MIN_ICON_AREA)
            counts.append(len(comps))
            if th == 0.5:
                canonical = comps
        runs[kind] = counts
        for j, (x, y, bw, bh, area, _lbl) in enumerate(canonical or []):
            corners = [(x, y), (x + bw, y), (x + bw, y + bh), (x, y + bh)]
            orig = variant.to_original(corners)
            conf = float(prob[y:y + bh, x:x + bw].max()) if bw and bh else 0.5
            elements.append(Element(id=f"{kind}_{j}", kind=kind, polygon=orig, conf=conf,
                                     attrs={"area_px": area}))
    return elements, runs


def _point_in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    pts = np.array(poly, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.pointPolygonTest(pts, (float(x), float(y)), False) >= 0


def _rooms_from_cnn(rooms_p: np.ndarray, variant, tokens) -> tuple[list[Element], dict, set[int]]:
    argmax = np.argmax(rooms_p, axis=0)
    elements: list[Element] = []
    runs: dict[str, list[int]] = {}
    claimed: set[int] = set()
    for idx, name in enumerate(cc_model.ROOM_CLASSES):
        if name in _ROOM_SKIP:
            continue
        comps, _, _ = _components(argmax == idx, max(_MIN_ROOM_AREA, int(_MIN_ROOM_FRAC * argmax.size)))
        kind = _ROOM_KIND.get(name, "room")
        runs[kind] = [len(comps)]
        for j, (x, y, bw, bh, area, _lbl) in enumerate(comps):
            corners = [(x, y), (x + bw, y), (x + bw, y + bh), (x, y + bh)]
            orig = variant.to_original(corners)
            subtype, label_text = kind, None
            for ti, tok in enumerate(tokens):
                if tok.category is None or ti in claimed:
                    continue
                tx, ty, tw, th = tok.bbox
                cx, cy = tx + tw / 2, ty + th / 2
                if _point_in_poly(cx, cy, orig):
                    subtype, label_text = tok.category, tok.text
                    claimed.add(ti)
                    break
            elements.append(Element(id=f"room_{name}_{j}", kind="room", subtype=subtype,
                                     polygon=orig, label=label_text, conf=0.8,
                                     attrs={"model_class": name, "area_px": area}))
    return elements, runs, claimed


def _route_b(img: np.ndarray, tokens) -> tuple[list[Element], set[int]]:
    """Classical-CV safety net (no pretrained weights available): dark-pixel wall mask + flood
    fill for room blobs, OCR for subtype. No icon detection (windows/doors/fixtures = 0) -- this
    path is not the measured route in docs/handoff/raster.md, it only keeps `extract` from
    crashing if weights/ is missing in some other checkout."""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    wall = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    free = cv2.bitwise_not(wall)
    comps, _, _ = _components(free > 0, int(0.01 * h * w))
    elements: list[Element] = []
    claimed: set[int] = set()
    for i, (x, y, bw, bh, area, _lbl) in enumerate(comps):
        subtype, label_text = "room", None
        for ti, tok in enumerate(tokens):
            if tok.category is None or ti in claimed:
                continue
            tx, ty, tw, th = tok.bbox
            cx, cy = tx + tw / 2, ty + th / 2
            if x <= cx <= x + bw and y <= cy <= y + bh:
                subtype, label_text = tok.category, tok.text
                claimed.add(ti)
                break
        elements.append(Element(id=f"roomB_{i}", kind="room", subtype=subtype, label=label_text,
                                 polygon=[(x, y), (x + bw, y), (x + bw, y + bh), (x, y + bh)],
                                 conf=0.4, attrs={"area_px": area}))
    return elements, claimed
