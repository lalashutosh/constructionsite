"""Words on a drawing sheet with boxes in the pixel space of /api/image.

words(abs_path, sha, max_px=2000) -> [{text, box:[x0,y0,x1,y1], conf, angle}]   (cached by sha + max_px)

PDF:    the exact text layer (pymupdf), mapped through the page rotation and the SAME zoom /api/image renders with.
        When the layer has no usable scale/dimension text (outlined fonts), the render is also OCR'd.
Raster: tesseract (eng) in ~2000 px tiles with overlap at native resolution; tiny images are upscaled 2-3x first;
        a second pass on the image rotated 90 deg reads vertical dimension text. Two threads, no network.
conf: 100 for the PDF text layer, tesseract's 0..100 otherwise. angle: 0 (horizontal) or 90 (reads bottom-to-top).
"""
from __future__ import annotations

import json
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "sheet_text"
VERSION = "v1"
TILE = 2000
OVERLAP = 220
RASTER_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def pdf_zoom(page, max_px: int) -> float:
    """Exactly the zoom api/main.py::_drawing_png renders a PDF page with."""
    return min(4.0, max_px / max(page.rect.width, page.rect.height))


# --------------------------------------------------------------------------- PDF text layer
def _pdf_words(path: str, max_px: int) -> list[dict]:
    import fitz
    out: list[dict] = []
    with fitz.open(path) as doc:
        page = doc[0]
        z = pdf_zoom(page, max_px)
        m = page.rotation_matrix * fitz.Matrix(z, z)
        for x0, y0, x1, y1, t, *_ in page.get_text("words"):
            r = fitz.Rect(x0, y0, x1, y1) * m
            r.normalize()
            t = t.strip()
            if not t:
                continue
            w, h = r.width, r.height
            out.append({"text": t, "box": [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)],
                        "conf": 100.0, "angle": 90 if h > 1.6 * w and len(t) > 2 else 0})
    return out


def _render_pdf_gray(path: str, long_px: int) -> tuple[np.ndarray, float]:
    """Page 1 as grey pixels, long side ~long_px; returns (image, zoom)."""
    import fitz
    with fitz.open(path) as doc:
        page = doc[0]
        z = min(6.0, long_px / max(page.rect.width, page.rect.height))
        pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False, colorspace=fitz.csGRAY)
        return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy(), z


# --------------------------------------------------------------------------- tesseract
def _tess(img: np.ndarray, timeout: int = 40) -> list[tuple[str, int, int, int, int, float]]:
    import pytesseract
    try:
        d = pytesseract.image_to_data(img, config="--psm 11", output_type=pytesseract.Output.DICT, timeout=timeout)
    except Exception:  # noqa: BLE001  (a tile that times out contributes nothing)
        return []
    out = []
    for t, x, y, w, h, c in zip(d["text"], d["left"], d["top"], d["width"], d["height"], d["conf"]):
        t = (t or "").strip()
        if t and float(c) >= 25:
            out.append((t, int(x), int(y), int(w), int(h), float(c)))
    return out


def _tiles(h: int, w: int) -> list[tuple[int, int, int, int]]:
    step = TILE - OVERLAP
    ys = list(range(0, max(1, h - OVERLAP), step)) or [0]
    xs = list(range(0, max(1, w - OVERLAP), step)) or [0]
    return [(y, min(h, y + TILE), x, min(w, x + TILE)) for y in ys for x in xs]


def ocr_gray(g: np.ndarray, vertical: bool = True) -> list[dict]:
    """Tesseract over a grey image in tiles; boxes in g's pixels. Blank tiles are skipped."""
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    H, W = g.shape
    jobs = []
    for (y0, y1, x0, x1) in _tiles(H, W):
        t = g[y0:y1, x0:x1]
        if (t < 140).mean() < 0.002:
            continue
        jobs.append(("h", y0, x0, t))
        if vertical:
            jobs.append(("v", y0, x0, cv2.rotate(t, cv2.ROTATE_90_CLOCKWISE)))

    def run(job):
        kind, y0, x0, t = job
        res = _tess(t)
        out = []
        th, tw = (t.shape if kind == "h" else (t.shape[1], t.shape[0]))   # original tile size
        for s, x, y, w, h, c in res:
            if kind == "h":
                bx = [x0 + x, y0 + y, x0 + x + w, y0 + y + h]
            else:   # rotated CW: (x', y') -> original (y', tile_h-1-x')
                bx = [x0 + y, y0 + (th - x - w), x0 + y + h, y0 + (th - x)]
            out.append({"text": s, "box": bx, "conf": c, "angle": 0 if kind == "h" else 90})
        return out

    with ThreadPoolExecutor(2) as ex:
        res = [w for part in ex.map(run, jobs) for w in part]
    return _dedupe(res)


def _dedupe(ws: list[dict]) -> list[dict]:
    """Tile overlaps and the two passes read the same word twice: keep the higher-confidence one."""
    ws = sorted(ws, key=lambda w: -w["conf"])
    keep: list[dict] = []
    grid: dict[tuple[int, int], list[dict]] = {}
    for w in ws:
        cx, cy = (w["box"][0] + w["box"][2]) / 2, (w["box"][1] + w["box"][3]) / 2
        key = (int(cx // 60), int(cy // 60))
        dup = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((key[0] + dx, key[1] + dy), []):
                    kx, ky = (k["box"][0] + k["box"][2]) / 2, (k["box"][1] + k["box"][3]) / 2
                    sz = max(k["box"][2] - k["box"][0], k["box"][3] - k["box"][1], 8)
                    if abs(kx - cx) < 0.6 * sz and abs(ky - cy) < 0.6 * sz and (k["text"] == w["text"] or
                                                                              _iou(k["box"], w["box"]) > 0.3):
                        dup = True
        if not dup:
            keep.append(w)
            grid.setdefault(key, []).append(w)
    return keep


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def _raster_words(path: str) -> list[dict]:
    g = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if g is None:
        return []
    long_side = max(g.shape)
    up = 1.0 if long_side >= 2000 else (2.0 if long_side >= 1000 else 3.0)
    if up != 1.0:
        g = cv2.resize(g, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    ws = ocr_gray(g)
    if up != 1.0:
        for w in ws:
            w["box"] = [round(v / up, 1) for v in w["box"]]
    return ws


def _useful(ws: list[dict]) -> bool:
    """Does the text layer carry a numeric scale note? (outlined fonts leave only stray words; then OCR the render)"""
    import re
    blob = " ".join(w["text"] for w in ws)
    return bool(re.search(r"\d\s*[\"\u2033]\s*=\s*\d+\s*['\u2032]|(?<![\d:])1\s*:\s*\d{2,}(?![\d:])", blob))


def words(abs_path: str, sha: str, max_px: int = 2000) -> list[dict]:
    """See module docstring. Cached at cache/sheet_text/<sha>-<max_px>-v1.json."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sha}-{max_px}-{VERSION}.json"
    if f.exists() and not os.environ.get("PLUMB_NO_SCALE_CACHE"):
        try:
            return json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            pass
    ext = pathlib.Path(abs_path).suffix.lower()
    out: list[dict[str, Any]] = []
    if ext == ".pdf":
        out = _pdf_words(abs_path, max_px)
        if not _useful(out):                      # outlined fonts: read the render instead
            g, z = _render_pdf_gray(abs_path, 4200)
            zz = pdf_zoom_for(abs_path, max_px)
            ocr = ocr_gray(g, vertical=False)
            k = zz / z
            for w in ocr:
                w["box"] = [round(v * k, 1) for v in w["box"]]
            seen = {w["text"] for w in out}
            out += [w for w in ocr if w["text"] not in seen or w["conf"] > 0]
            out = _dedupe(sorted(out, key=lambda w: -w["conf"]))
    elif ext in RASTER_EXT:
        out = _raster_words(abs_path)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(out))
    tmp.replace(f)
    return out


def pdf_zoom_for(path: str, max_px: int) -> float:
    import fitz
    with fitz.open(path) as doc:
        return pdf_zoom(doc[0], max_px)
