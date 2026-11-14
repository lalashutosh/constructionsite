"""Cheap sheet profiler: run FIRST, cached by sha256 (cache/profile/<sha>.json), no network.

`profile(abs_path, sha=None) -> dict` describes what kind of sheet this is so later stages can adapt instead of treating
every image like a small CubiCasa apartment scan:

  width_px, height_px      pixel size of the raster (a PDF is rendered to a 2000 px long side = the /api/image space)
  vector, paper_in         vector PDF? page size in inches (PDF only; a PNG's real size is unknown)
  sheet_type               residential_scan | archival_scan | cad_sheet | photo_nonplan
  route                    which readers are in-distribution: cubicasa_cnn | per_view | line_geometry | refuse
  border, title_block      boxes [x0,y0,x1,y1] in image px (or None)
  views                    [{n, box, kind: plan|notes|schedule|legend|key_plan|detail, title, ink_ratio}]  (main plan first)
  main_view                box of the biggest plan view (what walls/rooms are read from), or the whole sheet
  notes, tables            boxes of notes / schedules / legends
  text_density, line_density, complexity (0..1)
  words                    OCR / PDF text-layer words count (the words themselves go to engine.scale.sheet_text when present)
Boxes are in the SAME pixel space as the image the engine reads (render pixels for PDFs)."""
from __future__ import annotations

import json
import os
import pathlib
import re
from typing import Optional

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = pathlib.Path(os.environ.get("PLUMB_CACHE_DIR", str(ROOT / "cache"))) / "profile"
WORK = 1600                                    # working long side for the geometry statistics
PDF_PX = 2000                                  # PDF page long side in px (what api/main.py::_drawing_png renders)
VERSION = 5

KEYWORDS = [("notes", r"\bNOTES?\b|\bGENERAL NOTES\b"), ("legend", r"\bLEGEND\b|\bMODULE TYPE\b|\bSYMBOLS?\b"),
            ("schedule", r"\bSCHEDULE\b|\bSQUARE FOOTAGE\b|\bROOM COUNT\b|\bTABLE\b"),
            ("key_plan", r"\bKEY PLAN\b"), ("detail", r"\bDETAILS?\b|\bSECTION\b|\bELEVATION\b")]
CAD_CUES = re.compile(r"^(SHEET|SCALE|DRAWN|CHECKED|PROJECT|DATE|LEGEND|NOTES|SCHEDULE|CONSTRUCTION|REVISION|DESIGNED|APPROVED)$", re.I)
TITLE_RX = re.compile(r"\b(PLAN|SECTION|ELEVATION|DETAIL|DIAGRAM|LAYOUT|SCHEDULE|LEGEND|NOTES)\b", re.I)


# ----------------------------------------------------------------------------- loading
def _load(abs_path: str) -> tuple[np.ndarray, dict]:
    """-> (BGR image, info). PDFs are rendered; info carries vector/paper/words from the text layer."""
    info: dict = {"vector": False}
    if abs_path.lower().endswith(".pdf"):
        import fitz
        doc = fitz.open(abs_path)
        page = doc[0]
        r = page.rect
        info.update(vector=True, paper_in=[round(r.width / 72, 2), round(r.height / 72, 2)])
        zoom = min(4.0, PDF_PX / max(r.width, r.height))        # SAME pixel space as /api/image and engine.scale.sheet_text
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)[:, :, ::-1].copy()
        try:
            info["n_paths"] = len(page.get_drawings())
        except Exception:  # noqa: BLE001
            info["n_paths"] = None
        try:
            m = page.rotation_matrix * fitz.Matrix(zoom, zoom)
            info["text_layer"] = []
            for w in page.get_text("words"):
                rr = fitz.Rect(w[0], w[1], w[2], w[3]) * m
                info["text_layer"].append({"text": w[4], "box": [rr.x0, rr.y0, rr.x1, rr.y1], "conf": 100.0})
        except Exception:  # noqa: BLE001
            info["text_layer"] = []
        doc.close()
        return img, info
    img = cv2.imread(abs_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("image could not be read")
    return img, info


def _quick_words(img: np.ndarray) -> list[dict]:
    """One tesseract pass (<= 2600 px wide, ~1-3 s)."""
    try:
        import pytesseract
        from pytesseract import Output
        h, w = img.shape[:2]
        s = min(2600 / w, 3.0)
        g = cv2.cvtColor(cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2GRAY)
        d = pytesseract.image_to_data(g, config="--psm 11", output_type=Output.DICT, timeout=25)
        out = []
        for i, t in enumerate(d["text"]):
            if t.strip() and float(d["conf"][i]) > 35:
                x, y, bw, bh = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
                out.append({"text": t.strip(), "box": [x / s, y / s, (x + bw) / s, (y + bh) / s],
                            "conf": float(d["conf"][i]), "angle": 0})
        return out
    except Exception:  # noqa: BLE001
        return []


def words_for(abs_path: str, sha: str, img: np.ndarray, info: Optional[dict] = None, budget_s: float = 12.0) -> list[dict]:
    """[{text, box:[x0,y0,x1,y1], conf, angle}] in image px. Order: PDF text layer (exact) -> engine.scale.sheet_text
    (the scale agent's OCR; cached by sha, can take 20+ s cold on a dense sheet, so it runs with a time box and keeps
    caching in the background) -> one quick tesseract pass."""
    if info and info.get("text_layer"):
        return [{**w, "angle": 0} for w in info["text_layer"]]
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _TO
        from engine.scale import sheet_text            # owned by the scale agent; optional here
        ex = ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(sheet_text.words, abs_path, sha)
        try:
            w = fut.result(timeout=budget_s)
            ex.shutdown(wait=False)
            if w:
                return [{**x, "box": list(x["box"])} for x in w]
        except _TO:
            ex.shutdown(wait=False)                    # keeps running: the next call finds it cached
    except Exception:  # noqa: BLE001
        pass
    return _quick_words(img)


# ----------------------------------------------------------------------------- geometry statistics
def _ink(gray: np.ndarray) -> np.ndarray:
    """Dark-on-light ink mask; thin anti-aliased lines count (threshold relative to the paper tone)."""
    paper = float(np.percentile(gray, 90)) if gray.size else 255.0
    return (gray < paper - 55).astype(np.uint8)


def _ink_full(img: np.ndarray, s: float, delta: int = 55) -> np.ndarray:
    """Ink at full resolution, then area-downscaled so 1 px lines survive a 3x reduction."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    paper = float(np.percentile(g[::4, ::4], 90))
    full = (g < paper - delta).astype(np.float32)
    if s < 1:
        full = cv2.resize(full, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        return (full > 0.12).astype(np.uint8)
    return full.astype(np.uint8)


def _frame(ink: np.ndarray) -> tuple[Optional[list], Optional[list]]:
    """Sheet border (outermost long horizontal/vertical lines) and the title-block strip. Boxes in ink px."""
    h, w = ink.shape
    rows, cols = ink.sum(1) / w, ink.sum(0) / h
    thin = max(4, int(0.006 * max(h, w)))               # a drawn border is a thin line; a building wall is thick

    def first(a, lo, hi, thr, rev=False):
        idx = range(hi - 1, lo - 1, -1) if rev else range(lo, hi)
        for i in idx:
            if a[i] >= thr:
                run = 0
                j = i
                while 0 <= j < len(a) and a[j] >= thr:
                    run += 1
                    j += -1 if rev else 1
                return i if run <= thin else None
        return None
    top = first(rows, 0, int(h * 0.1), 0.85)
    bot = first(rows, int(h * 0.9), h, 0.85, rev=True)
    left = first(cols, 0, int(w * 0.1), 0.85)
    right = first(cols, int(w * 0.9), w, 0.85, rev=True)
    if sum(v is not None for v in (top, bot, left, right)) < 3:
        # no complete rectangle (thumbnails, crops): accept a border only if two opposite sides exist
        pass
    b = [left if left is not None else 0, top if top is not None else 0,
         right if right is not None else w - 1, bot if bot is not None else h - 1]
    n_found = sum(v is not None for v in (top, bot, left, right))
    border = b if n_found >= 3 else None
    x0, y0, x1, y1 = b
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    title = None
    # title block: leftmost near-full-height vertical line in the right 30% of the frame (then a bottom strip)
    sub = ink[y0:y1, x0:x1]
    cs = sub.sum(0) / bh
    for x in range(int(bw * 0.70), bw - 3):
        if cs[x] >= 0.85:
            run = 0
            while x + run < bw and cs[x + run] >= 0.85:
                run += 1
            if run <= thin:
                title = [x0 + x, y0, x1, y1]
            break
    if title is None and border is not None:
        rs = sub.sum(1) / bw
        for y in range(int(bh * 0.72), bh - 3):
            if rs[y] >= 0.85:
                run = 0
                while y + run < bh and rs[y + run] >= 0.85:
                    run += 1
                if run <= thin:
                    title = [x0, y0 + y, x1, y1]
                break
    return border, title


def _long_lines(ink: np.ndarray, k: int) -> np.ndarray:
    hl = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))
    vl = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, k)))
    return (hl | vl)


def _box_in(b, a, frac=0.5) -> bool:
    ix = max(0, min(b[2], a[2]) - max(b[0], a[0])) * max(0, min(b[3], a[3]) - max(b[1], a[1]))
    return ix >= frac * max(1, (b[2] - b[0]) * (b[3] - b[1]))


def _view_blobs(ink: np.ndarray, area: list, long: np.ndarray, words: list, s: float) -> list[dict]:
    """Ink clusters inside `area` (ink px) = candidate views / notes / schedules."""
    ax0, ay0, ax1, ay1 = area
    m = np.zeros_like(ink)
    m[ay0 + 3:ay1 - 3, ax0 + 3:ax1 - 3] = ink[ay0 + 3:ay1 - 3, ax0 + 3:ax1 - 3]
    n_side = max(ink.shape)
    k = max(5, int(0.022 * n_side))
    blob = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(blob, connectivity=8)
    total = float((ax1 - ax0) * (ay1 - ay0))
    out = []
    for i in range(1, n):
        x, y, bw, bh, _ = st[i]
        if bw * bh < 0.012 * total and bw * bh < 0.004 * ink.size:
            continue
        sel = (lab[y:y + bh, x:x + bw] == i)
        ink_px = float((m[y:y + bh, x:x + bw] & sel).sum())
        if ink_px < 40:
            continue
        ll = float((long[y:y + bh, x:x + bw] & sel & 1).sum())
        out.append({"box": [int(x), int(y), int(x + bw), int(y + bh)], "ink_ratio": round(ll / ink_px, 3),
                    "ink_px": ink_px})
    out.sort(key=lambda v: -(v["box"][2] - v["box"][0]) * (v["box"][3] - v["box"][1]))
    return out[:12]


def _classify_blob(v: dict, words: list, s: float, cad: bool) -> None:
    """kind from the words inside / directly under the blob and the ink statistics."""
    x0, y0, x1, y1 = [c / s for c in v["box"]]
    pad = (y1 - y0) * 0.12 + 20
    inside = [w for w in words if _box_in(w["box"], [x0, y0 - 10, x1, y1 + pad], 0.6)]
    text = " ".join(w["text"] for w in inside)
    v["n_words"] = len(inside)
    kind = None
    top_words = " ".join(w["text"] for w in inside if w["box"][1] < y0 + (y1 - y0) * 0.25)
    for k, rx in KEYWORDS:
        if re.search(rx, top_words, re.I):
            kind = k
            break
    area_px = max(1.0, (x1 - x0) * (y1 - y0))
    wd = len(inside) / area_px * 1e6               # words per megapixel
    if kind is None and v["ink_ratio"] < 0.06 and len(inside) >= 3:
        kind = "notes"
    m = re.findall(r"[A-Z0-9][A-Z0-9 ,.'\"/\-&()]*\b(?:PLAN|SECTION|ELEVATION|DETAIL|DIAGRAM|LAYOUT)\b[A-Z0-9 ,.'\"/\-&()]*", text.upper())
    v["title"] = (m[-1].strip()[:80] if m else None)
    v["kind"] = kind or "plan"
    v["words_per_mpx"] = round(wd, 1)


# ----------------------------------------------------------------------------- main
def profile(abs_path: str, sha: Optional[str] = None, *, use_cache: bool = True) -> dict:
    if sha is None:
        from engine import cache as facts_cache
        sha = facts_cache.sha256_file(abs_path)
    cf = CACHE / f"{sha}.json"
    if use_cache and cf.exists():
        try:
            d = json.loads(cf.read_text())
            if d.get("version") == VERSION:
                return d
        except Exception:  # noqa: BLE001
            pass
    img, info = _load(abs_path)
    H, W = img.shape[:2]
    s = min(1.0, WORK / max(H, W))
    small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    ink = _ink_full(img, s, 28 if info["vector"] else 55)    # clean vector renders: thin anti-aliased lines count
    sat = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[:, :, 1]
    colour_frac = float((sat > 60).mean())
    mean_dark = float(ink.mean())
    border, title = _frame(ink)
    k = max(9, int(0.04 * max(small.shape[:2])))
    long = _long_lines(ink, k)
    line_density = float(long.sum() / max(1, ink.sum()))
    words = words_for(abs_path, sha, img, info)
    inv = (lambda b: [round(c / s) for c in b]) if s < 1 else (lambda b: [int(c) for c in b])
    p: dict = {"version": VERSION, "sha256": sha, "width_px": W, "height_px": H, "vector": info["vector"],
               "paper_in": info.get("paper_in"), "n_paths": info.get("n_paths"),
               "border": inv(border) if border else None, "title_block": inv(title) if title else None,
               "words": len(words), "text_density": round(len(words) / (W * H / 1e6), 2),
               "line_density": round(line_density, 3), "ink_fraction": round(mean_dark, 4),
               "colour_fraction": round(colour_frac, 3)}
    if title is not None and (title[2] - title[0] if title[2] - title[0] < title[3] - title[1] else title[3] - title[1]) < 0.025 * max(W, H) * s:
        title = None                           # a strip thinner than 2.5% of the sheet cannot hold a title block (dimension line)
        p["title_block"] = None
    framed = border is not None or title is not None
    long_side = max(W, H)
    cues = {m.upper() for w in words for m in CAD_CUES.findall(w["text"])}
    p["cad_cues"] = sorted(cues)
    # ---- sheet type
    tiny_sheet = long_side <= 1200             # CubiCasa-size: framed apartment plans carry 40-110 words
    if (border is not None and title is not None and len(words) >= (150 if tiny_sheet else 40)) or len(cues) >= 3 or (
            title is not None and len(words) >= 150) or (
            border is not None and long_side >= 2000 and len(words) >= 200):
        stype = "cad_sheet"
    elif long_side <= 1100:
        stype = "residential_scan"
    else:
        stype = "archival_scan" if mean_dark > 0.004 else "photo_nonplan"
    if not framed and colour_frac > 0.55 and line_density < 0.12:
        stype = "photo_nonplan"
    p["sheet_type"] = stype
    # ---- views (cad sheets only; a small scan is one view)
    views: list[dict] = []
    if stype == "cad_sheet":
        bx = border or [0, 0, small.shape[1] - 1, small.shape[0] - 1]
        area = list(bx)
        if title is not None:
            if title[0] > bx[0] + 0.5 * (bx[2] - bx[0]):
                area[2] = min(area[2], title[0])
            else:
                area[3] = min(area[3], title[1])
        blobs = _view_blobs(ink, area, long, words, s)
        for v in blobs:
            _classify_blob(v, words, s, True)
            v["box"] = inv(v["box"])
            v.pop("ink_px", None)
        big = max([(v["box"][2] - v["box"][0]) * (v["box"][3] - v["box"][1]) for v in blobs if v["kind"] == "plan"] or [1])
        for v in blobs:                            # small plan-like blobs = graphic scale, key plan, symbols, titles
            if v["kind"] == "plan" and (v["box"][2] - v["box"][0]) * (v["box"][3] - v["box"][1]) < 0.08 * big:
                v["kind"] = "detail"
        plans = [v for v in blobs if v["kind"] == "plan"]
        # a plan blob must be mostly long lines or large; the biggest ones first
        views = blobs
        for i, v in enumerate(views, 1):
            v["n"] = i
        p["main_view"] = max(plans, key=lambda v: (v["box"][2] - v["box"][0]) * (v["box"][3] - v["box"][1]))["box"] if plans else (
            inv(area))
    else:
        p["main_view"] = [0, 0, W, H]
    p["views"] = views
    p["notes"] = [v["box"] for v in views if v["kind"] == "notes"]
    p["tables"] = [v["box"] for v in views if v["kind"] in ("schedule", "legend")]
    pix_m = W * H / 1e6
    p["complexity"] = round(min(1.0, 0.35 * min(1.0, pix_m / 12) + 0.35 * min(1.0, p["text_density"] / 60)
                                + 0.15 * min(1.0, len(views) / 6) + 0.15 * min(1.0, p["ink_fraction"] / 0.06)), 3)
    p["route"] = {"residential_scan": "cubicasa_cnn", "archival_scan": "per_view", "cad_sheet": "line_geometry",
                  "photo_nonplan": "refuse"}[stype]
    p["review"] = review_budget(p)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(p))
    except OSError:
        pass
    return p


def review_budget(p: dict) -> dict:
    """LLM reviewer settings chosen from complexity: bigger/denser sheet -> bigger image + more thinking; a small simple
    plan -> fast model, no thinking."""
    c = p.get("complexity", 0.0)
    if p.get("sheet_type") == "residential_scan" and c < 0.3:
        return {"image_px": 1000, "model": "fast", "think_tokens": 0}
    if c < 0.55:
        return {"image_px": 1400, "model": "strong", "think_tokens": 4000}
    return {"image_px": 1800, "model": "strong", "think_tokens": 8000}


def view_crop(img: np.ndarray, box: list, max_side: int = 1600) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Crop a view and downscale to `max_side`: (crop, scale, (x0, y0)); original = crop_px / scale + (x0, y0)."""
    x0, y0, x1, y1 = [int(v) for v in box]
    c = img[max(0, y0):y1, max(0, x0):x1]
    s = min(1.0, max_side / max(c.shape[:2]))
    if s < 1:
        c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return c, s, (max(0, x0), max(0, y0))
