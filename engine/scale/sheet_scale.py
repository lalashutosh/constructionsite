"""Scale of a big construction / architectural sheet, read from the sheet itself.

Evidence, all measured on the pixels of /api/image (no network, no model):
  notes   'SCALE: 1/4" = 1'-0"', '1" = 40'-0"', '1:50', 'NTS' / 'AS INDICATED' / 'NOT TO SCALE' (= no scale)
  bars    graphic scale bars: collinear labels 0 .. N (+unit), px per unit by least squares on the label centres,
          each centre snapped to the bar's tick mark when one is within reach
  dims    dimension strings (323'-4", 52'-8", 27500 mm, 12.5 m) each matched to its dimension line: a straight dark
          line next to the text, measured between the ticks / arrows / extension lines that bracket the text
  paper   sheet size from the PDF page (exact) or from the raster's aspect (a guess) -> px per paper inch
Every piece becomes a ScaleAnchor; anchors.solve() combines them. Confidence is computed from how many INDEPENDENT
kinds agree within AGREE, their tags and the OCR confidence (see `confidence`), never from a model's own report.

analyze(abs_path, sha) -> dict (cached by sha in cache/sheet_scale/); anchors_for(facts) -> (anchors, info).
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import re
import statistics
from typing import Any, Optional

import cv2
import numpy as np

from contracts.proof import ScaleAnchor, Tag
from engine.scale import sheet_text

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache" / "sheet_scale"
CHECKS = ROOT / "cache" / "checks"
VERSION = "v2"
AGREE = 0.05           # anchors within 5% count as agreeing
M_PER_IN = 0.0254

# (long, short) paper sizes in inches. First entry of a list is the prior for that aspect.
PAPER_IN = {
    "ANSI D 34x22": (34.0, 22.0), "ANSI B 17x11": (17.0, 11.0), "ANSI C 22x17": (22.0, 17.0),
    "ANSI E 44x34": (44.0, 34.0), "ANSI A 11x8.5": (11.0, 8.5),
    "ARCH D 36x24": (36.0, 24.0), "ARCH E 48x36": (48.0, 36.0), "ARCH C 24x18": (24.0, 18.0),
    "ARCH E1 42x30": (42.0, 30.0), "ARCH B 18x12": (18.0, 12.0),
    "ISO A0": (1189 / 25.4, 841 / 25.4), "ISO A1": (841 / 25.4, 594 / 25.4),
    "ISO A2": (594 / 25.4, 420 / 25.4), "ISO A3": (420 / 25.4, 297 / 25.4),
}
STD_DPI = (72, 96, 100, 150, 200, 300, 400, 600)

# --------------------------------------------------------------------------- text normalisation / lines
_QUOTES = str.maketrans({"″": '"', "”": '"', "“": '"', "′": "'", "’": "'", "‘": "'",
                         "`": "'", "´": "'"})


def norm(t: str) -> str:
    t = t.translate(_QUOTES).replace("''", '"')
    return re.sub(r"\s+", " ", t).strip()


def merge_lines(ws: list[dict]) -> list[dict]:
    """Words -> text lines [{text, box, angle, conf, words}] (same angle, same baseline, small gaps)."""
    out = []
    for ang in (0, 90):
        items = [w for w in ws if w.get("angle", 0) == ang]
        if not items:
            continue
        # along-axis a, cross-axis c
        def ax(w):
            b = w["box"]
            return (b[0], b[2], (b[1] + b[3]) / 2, b[3] - b[1]) if ang == 0 else (b[1], b[3], (b[0] + b[2]) / 2, b[2] - b[0])
        lines: list[list[dict]] = []
        ends: list[float] = []
        for w in sorted(items, key=lambda w: ax(w)[0]):       # reading order along the line: no word is skipped
            a0, a1, c, h = ax(w)
            best, bd = None, None
            for k, ln in enumerate(lines):
                la0, la1, lc, lh = ax(ln[-1])
                gap = a0 - ends[k]
                if abs(lc - c) < 0.5 * max(h, lh) and -0.5 * h < gap < 2.2 * max(h, lh):
                    if bd is None or abs(lc - c) < bd:
                        best, bd = k, abs(lc - c)
            if best is None:
                lines.append([w])
                ends.append(a1)
            else:
                lines[best].append(w)
                ends[best] = max(ends[best], a1)
        for ln in lines:
            ln.sort(key=lambda w: ax(w)[0])
            xs0 = [w["box"][0] for w in ln]; ys0 = [w["box"][1] for w in ln]
            xs1 = [w["box"][2] for w in ln]; ys1 = [w["box"][3] for w in ln]
            out.append({"text": norm(" ".join(w["text"] for w in ln)), "box": [min(xs0), min(ys0), max(xs1), max(ys1)],
                        "angle": ang, "conf": statistics.mean(w["conf"] for w in ln), "words": ln})
    return out


# --------------------------------------------------------------------------- scale notes
_FRAC = r"(?:\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+(?:\.\d+)?)"
_IMP = re.compile(rf"(?P<p>{_FRAC})\s*(?:\"|in\b|inch(?:es)?\b)?\s*=\s*(?P<f>\d+(?:\.\d+)?)\s*(?:'|ft\b|feet\b|foot\b)"
                  rf"(?:\s*-?\s*(?P<i>\d+(?:\.\d+)?(?:\s*\d+/\d+)?)\s*\"?)?", re.I)
_MET = re.compile(r"(?<![\d:.])1\s*:\s*(\d{1,4})(?![\d:]|\s*(?:am|pm)\b)", re.I)
_NONE = re.compile(r"\b(?:NTS|N\.T\.S\.?|NOT\s+TO\s+SCALE|NO\s+SCALE|AS\s+INDICATED|VARIES|AS\s+NOTED|AS\s+SHOWN)\b", re.I)


def _frac(s: str) -> float:
    s = s.strip()
    if " " in s and "/" in s:
        a, b = s.split(None, 1)
        return float(a) + _frac(b)
    if "/" in s:
        n, d = s.split("/")
        return float(n) / float(d)
    return float(s)


def parse_note(text: str) -> Optional[dict]:
    """One scale note -> {'ratio': real/paper, 'label': str, 'system': 'imperial'|'metric'} or {'none': True}."""
    t = norm(text)
    m = _IMP.search(t)
    if m:
        paper = _frac(m.group("p"))
        real_in = float(m.group("f")) * 12.0 + (_frac(m.group("i")) if m.group("i") else 0.0)
        if paper > 0 and real_in > 0 and 1.0 <= real_in / paper <= 3000:
            return {"ratio": real_in / paper, "system": "imperial", "label": m.group(0).strip(),
                    "key": f"{m.group('p').replace(' ', '')}in={m.group('f')}ft{m.group('i') or ''}".replace("/", "_")}
    m = _MET.search(t)
    if m and re.search(r"scale|[Ss]cale|SCALE", t) or (m and len(t) <= 8):
        n = int(m.group(1))
        if 2 <= n <= 5000:
            return {"ratio": float(n), "system": "metric", "label": f"1:{n}", "key": f"1_{n}"}
    if _NONE.search(t):
        return {"none": True, "label": _NONE.search(t).group(0)}
    return None


# --------------------------------------------------------------------------- dimension strings
_FTIN = re.compile(r"^(\d{1,4})\s*'\s*-?\s*(\d{1,2})?(?:\s*(\d)/(\d{1,2}))?\s*\"?$")
_FTIN_LAX = re.compile(r"^(\d{2,4})\s*[-–]\s*(\d{1,2})\s*\"$")          # foot mark lost by OCR: 133-10"
_INCH = re.compile(r"^(\d{1,3})\s*\"$")
_MM = re.compile(r"^(\d{1,3}(?:[ ,]\d{3})+|\d{3,6})(?:\s*mm)?$", re.I)
_M = re.compile(r"^(\d{1,3}(?:[.,]\d{1,3}))\s*m$", re.I)


def parse_dim(text: str) -> list[dict]:
    """A token -> plausible readings [{m, kind, lax}]; imperial (ft-in), mm (plain integer) or metres."""
    t = norm(text).strip(" .,;:|[]()")
    t = re.sub(r"^(\d{1,4})'\s*[.,_~=]\s*(\d{1,2}\s*\")$", r"\1'-\2", t)     # OCR: 55'.8" -> 55'-8"
    out = []
    m = _FTIN.match(t)
    if m and (m.group(2) is not None or t.endswith("'") or "-" in t):
        ft = int(m.group(1))
        inch = int(m.group(2) or 0) + (int(m.group(3)) / int(m.group(4)) if m.group(3) else 0)
        if inch < 12 and (ft or inch):
            out.append({"m": (ft * 12 + inch) * M_PER_IN, "kind": "ftin", "lax": False})
    m = _FTIN_LAX.match(t)
    if m and not out and int(m.group(2)) < 12:
        out.append({"m": (int(m.group(1)) * 12 + int(m.group(2))) * M_PER_IN, "kind": "ftin", "lax": True})
    m = _INCH.match(t)
    if m and int(m.group(1)) >= 12 and not out:
        out.append({"m": int(m.group(1)) * M_PER_IN, "kind": "in", "lax": True})
    m = _M.match(t)
    if m:
        out.append({"m": float(m.group(1).replace(",", ".")), "kind": "m", "lax": False})
    m = _MM.match(t)
    if m and not out:
        v = int(re.sub(r"[ ,]", "", m.group(1)))
        if 300 <= v <= 150000 and not (1900 <= v <= 2100 and len(t) == 4):
            out.append({"m": v / 1000.0, "kind": "mm", "lax": not t.lower().endswith("mm")})
    return out


def fmt_len(m: float, kind: str, label: str) -> str:
    return f"{label} ({m:.1f} m)" if m >= 10 else f"{label} ({m:.2f} m)"


# --------------------------------------------------------------------------- image
def load_gray(abs_path: str, max_px: int) -> tuple[np.ndarray, Optional[dict]]:
    """Grey pixels in /api/image space + PDF page info {w_in, h_in, zoom} (None for rasters)."""
    if pathlib.Path(abs_path).suffix.lower() == ".pdf":
        import fitz
        with fitz.open(abs_path) as doc:
            page = doc[0]
            z = sheet_text.pdf_zoom(page, max_px)
            pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False, colorspace=fitz.csGRAY)
            g = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
            return g, {"w_in": page.rect.width / 72.0, "h_in": page.rect.height / 72.0, "zoom": z}
    g = cv2.imread(abs_path, cv2.IMREAD_GRAYSCALE)
    if g is None:
        raise ValueError("unreadable image")
    return g, None


def paper_info(w_px: int, h_px: int, pdf: Optional[dict]) -> dict:
    """{'px_per_in', 'name', 'exact', 'sigma', 'tag', 'ambiguous': [names]} - px per inch of PAPER."""
    long_px = max(w_px, h_px)
    asp = max(w_px, h_px) / max(1, min(w_px, h_px))
    if pdf:
        long_in = max(pdf["w_in"], pdf["h_in"])
        name = next((n for n, (L, S) in PAPER_IN.items() if abs(L - long_in) / L < 0.02 and abs(S - min(pdf["w_in"], pdf["h_in"])) / S < 0.02), None)
        return {"px_per_in": pdf["zoom"] * 72.0, "name": name or f"{pdf['w_in']:.1f}x{pdf['h_in']:.1f} in", "exact": True,
                "sigma": 0.03 if name else 0.05, "tag": "specified" if name else "defaulted", "ambiguous": []}
    cands = [(n, L, S) for n, (L, S) in PAPER_IN.items() if abs(L / S - asp) / asp < 0.025]
    if not cands:
        return {"px_per_in": None, "name": None, "exact": False, "sigma": 0.3, "tag": "defaulted", "ambiguous": []}
    # a candidate whose implied dpi is a standard one wins; otherwise the first (largest-sheet prior)
    for n, L, S in cands:
        dpi = long_px / L
        if any(abs(dpi / s - 1) < 0.01 for s in STD_DPI):
            return {"px_per_in": dpi, "name": n, "exact": False, "sigma": 0.05, "tag": "defaulted",
                    "ambiguous": [c[0] for c in cands if c[0] != n], "std_dpi": True}
    n, L, S = cands[0]
    return {"px_per_in": long_px / L, "name": n, "exact": False, "sigma": 0.25, "tag": "defaulted",
            "ambiguous": [c[0] for c in cands[1:]]}


# --------------------------------------------------------------------------- dimension line measurement
def ink_mask(g: np.ndarray) -> np.ndarray:
    paper = float(np.percentile(g[::4, ::4], 90)) if g.size else 255.0
    return (g < paper - 55)


def _runs(row: np.ndarray, start: int, step: int, gap: int, lim: int) -> int:
    """Walk from `start` in `step` direction while dark or within `gap` of dark; returns the last dark index."""
    x, last, miss = start, start, 0
    while 0 <= x < lim:
        if row[x]:
            last, miss = x, 0
        else:
            miss += 1
            if miss > gap:
                break
        x += step
    return last


def measure_dim(B: np.ndarray, wmask: np.ndarray, box: list[float], angle: int) -> Optional[dict]:
    """Pixel length of the dimension line that belongs to the text `box` (None when no ticked line is found).
    B is the ink mask, wmask is True inside OCR word boxes (excluded when looking for ticks)."""
    if angle == 90:
        B, wmask = B.T, wmask.T
        box = [box[1], box[0], box[3], box[2]]
    H, W = B.shape
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    h = max(3, y1 - y0)
    cx = (x0 + x1) // 2
    gap = max(2, int(0.35 * h))
    t = max(3, int(0.8 * h))
    best = None
    for y in range(max(0, y0 - int(2.4 * h)), min(H, y1 + int(2.4 * h) + 1)):
        row = B[y]
        cov = row[max(0, x0):x1 + 1].mean() if x1 > x0 else 0
        side_l = row[max(0, x0 - gap - 1):x0 + 1].any() if x0 > 0 else False
        side_r = row[x1:min(W, x1 + gap + 2)].any()
        if not (cov >= 0.8 or (side_l and side_r and cov < 0.5)):
            continue
        L = _runs(row, max(0, x0 - 1), -1, gap + (x1 - x0 if cov < 0.5 else 0) * 0, W)
        R = _runs(row, min(W - 1, x1 + 1), 1, gap, W)
        if cov >= 0.8:                     # line runs under/over the text: extend from the text centre outward
            L = _runs(row, cx, -1, gap, W)
            R = _runs(row, cx, 1, gap, W)
        if R - L < 3 * (x1 - x0) * 0.6 or R - L < 8 * h * 0.5:
            continue
        # ticks along [L-t, R+t]: ink above/below the line, outside any word box
        up = B[max(0, y - t):max(0, y - 1), :].copy()
        dn = B[min(H, y + 2):min(H, y + t + 1), :].copy()
        wm_up = wmask[max(0, y - t):max(0, y - 1), :]
        wm_dn = wmask[min(H, y + 2):min(H, y + t + 1), :]
        up &= ~wm_up
        dn &= ~wm_dn
        prof = up.sum(0) + dn.sum(0)
        lo, hi = max(0, L - t), min(W, R + t + 1)
        cols = np.where(prof[lo:hi] >= max(2, int(0.5 * t)))[0] + lo
        if len(cols) == 0:
            continue
        clusters, cur = [], [cols[0]]
        for c in cols[1:]:
            if c - cur[-1] <= max(2, h // 3):
                cur.append(c)
            else:
                clusters.append(cur)
                cur = [c]
        clusters.append(cur)
        ticks = [float(np.average(c, weights=prof[c])) for c in clusters if c[-1] - c[0] <= 2.5 * h]
        left = [p for p in ticks if p <= x0 - h]
        right = [p for p in ticks if p >= x1 + h]
        if not left or not right:
            continue
        tl, tr = max(left), min(right)
        if tr - tl < max(10, 0.9 * (x1 - x0)):
            continue
        if tl < L - 2 * t or tr > R + 2 * t:
            continue
        score = abs(y - (y0 + y1) / 2)
        if best is None or score < best[0]:
            ol = min(p for p in left if p >= L - 2 * t)          # outermost ticks of the same line: extension lines of
            orr = max(p for p in right if p <= R + 2 * t)        # other dimensions crossing it look like nearer ticks
            best = (score, tl, tr, y, ol, orr)
    if best is None:
        return None
    _, tl, tr, y, ol, orr = best
    pt = (lambda xx: [y, xx]) if angle == 90 else (lambda xx: [xx, y])   # transposed back: (x, y) endpoints
    out = {"len_px": tr - tl, "a": pt(tl), "b": pt(tr), "alts": []}
    if (orr - ol) > 1.05 * (tr - tl):
        out["alts"].append({"len_px": orr - ol, "a": pt(ol), "b": pt(orr)})
    return out


# --------------------------------------------------------------------------- line-first dimensions (tiny rasters)
def _ocr_token_crop(c: np.ndarray, up: int) -> list[tuple[str, float]]:
    import pytesseract
    c = cv2.resize(c, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    c = cv2.copyMakeBorder(c, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    out = []
    try:
        d = pytesseract.image_to_data(c, config="--psm 7",
                                      output_type=pytesseract.Output.DICT, timeout=10)
    except Exception:  # noqa: BLE001
        return out
    toks = [(t.strip(), float(cf)) for t, cf in zip(d["text"], d["conf"]) if t.strip()]
    if toks:
        out.append(("".join(t for t, _ in toks), min(cf for _, cf in toks)))
        out += toks
    return out


def line_first_dims(g: np.ndarray, B: np.ndarray, max_spans: int = 40) -> list[dict]:
    """For small rasters where word OCR cannot read dimension text: find ticked straight lines first, then read the
    label crop above/below each span between consecutive ticks (4x and 6x, single-line OCR)."""
    H, W = g.shape
    hh = max(8, int(round(max(W, H) / 85)))
    t = max(4, int(0.7 * hh))
    Lmin = max(30, int(0.05 * max(W, H)))
    spans: list[dict] = []
    paper = float(np.percentile(g[::4, ::4], 90))
    for ang in (0, 90):
        G = (g if ang == 0 else g.T).astype(np.int16)
        M = (G < paper - 20).astype(np.uint8)                       # light ink: anti-aliased hairlines count
        ridge = np.zeros(G.shape, np.uint8)                          # a hairline is darker than rows 3 px either side
        ridge[3:-3] = ((G[3:-3] < G[:-6] - 10) & (G[3:-3] < G[6:] - 10) & (G[3:-3] < paper - 20)).astype(np.uint8)
        MH, MW = M.shape
        seg = cv2.morphologyEx(ridge, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (Lmin, 1)))
        prev = np.zeros(MW, bool)
        for y in range(t + 2, MH - t - 2):
            row = seg[y] > 0
            if not row.any():
                prev = row
                continue
            d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
            starts, ends = np.where(d == 1)[0], np.where(d == -1)[0] - 1
            for xs, xe in zip(starts, ends):
                if prev[xs:xe + 1].mean() > 0.5:
                    continue                                  # same line as the row above (thick stroke)
                up = M[y - t:y - 1, xs - t:xe + t + 1].sum(0)
                dn = M[y + 2:y + t + 1, xs - t:xe + t + 1].sum(0)
                cols = np.where((up >= 2) & (dn >= 2))[0] + (xs - t)
                if len(cols) < 2:
                    continue
                cl, cur = [], [cols[0]]
                for c in cols[1:]:
                    if c - cur[-1] <= 3:
                        cur.append(c)
                    else:
                        cl.append(float(np.mean(cur)))
                        cur = [c]
                cl.append(float(np.mean(cur)))
                if len(cl) < 2 or len(cl) > 14:
                    continue
                for a, b in zip(cl, cl[1:]):
                    if b - a >= 4 * hh:
                        spans.append({"ang": ang, "y": y, "a": a, "b": b})
                if len(cl) > 2 and cl[-1] - cl[0] >= 4 * hh:
                    spans.append({"ang": ang, "y": y, "a": cl[0], "b": cl[-1]})
            prev = row
    if os.environ.get("PLUMB_DBG"): print("spans", len(spans), spans[:10])
    spans.sort(key=lambda s: -(s["b"] - s["a"]))
    out = []
    for sp in spans[:max_spans]:
        a, b, y, ang = sp["a"], sp["b"], sp["y"], sp["ang"]
        for band in ((y - int(1.8 * hh), y - 1), (y + 2, y + int(1.8 * hh))):
            lo, hi = max(0, band[0]), band[1]
            x0, x1 = int(a + 3), int(b - 3)
            if ang == 0:
                crop = g[lo:hi, x0:x1]
                box = [x0, lo, x1, hi]
            else:
                crop = cv2.rotate(g[x0:x1, lo:hi], cv2.ROTATE_90_CLOCKWISE)
                box = [lo, x0, hi, x1]
            if crop.size == 0 or (crop < 140).mean() < 0.01:
                continue
            for up in (4, 6):
                for txt, cf in _ocr_token_crop(crop, up)[:1]:
                    reads = parse_dim(txt)
                    if not reads:
                        continue
                    ends = ([[a, y], [b, y]] if ang == 0 else [[y, a], [y, b]])
                    r = reads[0]
                    if r["m"] <= 0:
                        continue
                    out.append({"text": txt, "box": box, "angle": ang, "conf": cf, "m": r["m"], "kind": r["kind"],
                                "lax": r["lax"] or up == 4, "len_px": b - a, "ends": ends, "ppm": (b - a) / r["m"],
                                "via": "line-first"})
    return out


# --------------------------------------------------------------------------- graphic scale bars
_BARNUM = re.compile(r"^(\d{1,3}(?:\.\d+)?)\s*(?:'|\"|m|ft|mm|M|FT)?$")


def _robust_bar(pts: list[dict]) -> list[dict]:
    """Labels that lie on one straight line value -> position (pairwise RANSAC). A misread label ('38' for 8') is
    dropped instead of bending the fit; needs >= 3 consistent labels, else []."""
    if len(pts) < 3:
        return []
    best: list[dict] = []
    best_r = 1e18
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dv = pts[j]["v"] - pts[i]["v"]
            if dv == 0:
                continue
            ppu = (pts[j]["cx"] - pts[i]["cx"]) / dv
            if ppu <= 0:
                continue
            a = pts[i]["cx"] - ppu * pts[i]["v"]
            span = ppu * (max(p["v"] for p in pts) - min(p["v"] for p in pts))
            tol = max(0.9 * max(p["h"] for p in pts), 0.012 * span)
            inl = [p for p in pts if abs(p["cx"] - (a + ppu * p["v"])) <= tol]
            r = sum(abs(p["cx"] - (a + ppu * p["v"])) for p in inl)
            if len(inl) > len(best) or (len(inl) == len(best) and r < best_r):
                best, best_r = inl, r
    return best if len(best) >= 3 else []


def find_bars(ws: list[dict], B: Optional[np.ndarray] = None) -> list[dict]:
    """Collinear numeric labels (0 .. N with units) -> px per unit. Returns [{unit, ppu, resid, boxes, vals}]."""
    nums = []
    for w in ws:
        t = norm(w["text"])
        if re.fullmatch(r"[Oo]\s*(?:'|\"|m|ft|mm|M|FT)?", t):     # OCR reads the bar's zero as the letter O
            t = "0" + t[1:]
        m = _BARNUM.match(t)
        if m and w["conf"] >= 30:
            unit = "ft" if t.endswith("'") else ("m" if t.lower().endswith("m") and not t.lower().endswith("mm") else
                                               ("mm" if t.lower().endswith("mm") else ("ft" if t.lower().endswith("ft") else None)))
            nums.append({"v": float(m.group(1)), "unit": unit, "box": w["box"], "cx": (w["box"][0] + w["box"][2]) / 2,
                         "cy": (w["box"][1] + w["box"][3]) / 2, "h": w["box"][3] - w["box"][1], "angle": w.get("angle", 0)})
    out = []
    used: set[int] = set()
    zeros = [i for i, n in enumerate(nums) if n["v"] == 0 and n["angle"] == 0]
    for zi in zeros:
        z = nums[zi]
        grp = [i for i, n in enumerate(nums) if n["angle"] == 0 and abs(n["cy"] - z["cy"]) < 0.6 * max(z["h"], n["h"]) and
               abs(n["cx"] - z["cx"]) < 40 * z["h"] and i not in used]
        grp.sort(key=lambda i: nums[i]["cx"])
        if len(grp) < 3 or zi not in grp:
            continue
        pos = [nums[i] for i in grp]
        k0 = [i for i, n in enumerate(pos) if n is z][0]
        # left of the zero are negative subdivisions; right must increase
        right = pos[k0:]
        if len(right) < 3 or any(right[i + 1]["v"] <= right[i]["v"] for i in range(len(right) - 1)):
            right2 = [right[0]]
            for n in right[1:]:
                if n["v"] > right2[-1]["v"]:
                    right2.append(n)
            right = right2
        if len(right) < 3:
            continue
        left = [dict(n, v=-n["v"]) for n in pos[:k0] if n["v"] > 0]
        pts = _robust_bar(left + right)
        if len(pts) < 3:
            continue
        xs = np.array([n["cx"] for n in pts])
        vs = np.array([n["v"] for n in pts])
        ppu, a = np.polyfit(vs, xs, 1)
        if ppu <= 0:
            continue
        resid = float(np.sqrt(np.mean((xs - (a + ppu * vs)) ** 2)))
        unit = next((n["unit"] for n in reversed(pts) if n["unit"]), None)
        out.append({"unit": unit, "ppu": float(ppu), "resid_px": resid, "vals": [float(v) for v in vs],
                    "boxes": [n["box"] for n in pts], "span_px": float(ppu * (vs.max() - vs.min()))})
        used.update(grp)
    return out


# --------------------------------------------------------------------------- analysis (cached)
def analyze(abs_path: str, sha: str, max_px: int = 2000) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sha}-{max_px}-{VERSION}.json"
    if f.exists() and not os.environ.get("PLUMB_NO_SCALE_CACHE"):
        try:
            return json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            pass
    res = _analyze(abs_path, sha, max_px)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(res))
    tmp.replace(f)
    return res


def _analyze(abs_path: str, sha: str, max_px: int) -> dict:
    g, pdf = load_gray(abs_path, max_px)
    H, W = g.shape
    ws = sheet_text.words(abs_path, sha, max_px)
    lines = merge_lines(ws)
    paper = paper_info(W, H, pdf)
    res: dict[str, Any] = {"w": W, "h": H, "pdf": pdf is not None, "paper": paper, "notes": [], "none_notes": [],
                           "bars": [], "dims": [], "n_words": len(ws)}
    # --- notes
    for ln in lines:
        p = parse_note(ln["text"])
        if not p:
            continue
        if p.get("none"):
            res["none_notes"].append({"label": p["label"], "box": ln["box"]})
        else:
            res["notes"].append({**p, "box": ln["box"], "conf": ln["conf"], "text": ln["text"]})
    # --- bars
    B = ink_mask(g)
    unit_hint = "ft" if any(n["system"] == "imperial" for n in res["notes"]) else None
    if unit_hint is None and not res["notes"]:        # no note: the dimension strings' style says which unit family
        kinds = [parse_dim(w["text"])[0]["kind"] for w in ws if parse_dim(w["text"]) and 
                 re.search(r"['\"]", w["text"])]
        if len(kinds) >= 2 and all(k in ("ftin", "in") for k in kinds):
            unit_hint = "ft"
    for b in find_bars(ws):
        b["unit"] = b["unit"] or unit_hint or ("m" if any(n["system"] == "metric" for n in res["notes"]) else None)
        res["bars"].append(b)
    # --- dimension strings
    wmask = np.zeros_like(B)
    for w in ws:
        x0, y0, x1, y1 = [int(round(v)) for v in w["box"]]
        wmask[max(0, y0 - 1):y1 + 2, max(0, x0 - 1):x1 + 2] = True
    metric_sheet = any(n["system"] == "metric" for n in res["notes"]) and not any(n["system"] == "imperial" for n in res["notes"])
    imperial_sheet = any(n["system"] == "imperial" for n in res["notes"])
    seen = 0
    for w in sorted(ws, key=lambda w: -w["conf"]):
        if seen > 400:
            break
        reads = parse_dim(w["text"])
        if not reads:
            continue
        if reads[0]["kind"] == "mm" and (imperial_sheet or not (metric_sheet or reads[0]["m"] >= 1.0)):
            continue
        if metric_sheet and reads[0]["kind"] in ("ftin", "in"):
            continue
        seen += 1
        ang = w.get("angle", 0)
        ms = measure_dim(B, wmask, w["box"], ang)
        if ms is None or ms["len_px"] < 25 or ms["len_px"] > 0.9 * max(W, H):
            continue
        for r in reads[:1]:
            res["dims"].append({"text": norm(w["text"]), "box": w["box"], "angle": ang, "conf": w["conf"], "m": r["m"],
                                "kind": r["kind"], "lax": r["lax"], "len_px": ms["len_px"], "ends": [ms["a"], ms["b"]],
                                "ppm": ms["len_px"] / r["m"],
                                "alts": [{"len_px": x["len_px"], "ends": [x["a"], x["b"]], "ppm": x["len_px"] / r["m"]}
                                         for x in ms.get("alts", [])]})
    if pdf is None and max(W, H) < 2200 and len(res["dims"]) < 3 and not res["bars"] and not res["notes"]:
        try:
            res["dims"] += line_first_dims(g, B)
        except Exception:  # noqa: BLE001  (a failed fallback never breaks the sheet)
            pass
    return res


# --------------------------------------------------------------------------- candidates -> anchors
def _cluster(vals: list[tuple[float, Any]], tol: float) -> list[list[tuple[float, Any]]]:
    """Group (ppm, item) pairs whose ppm lie within tol of the group's median (greedy by size)."""
    vals = sorted(vals, key=lambda v: v[0])
    best: list[list[tuple[float, Any]]] = []
    for v, _ in vals:
        grp = [x for x in vals if abs(x[0] / v - 1) <= tol]
        best.append(grp)
    best.sort(key=lambda g: -len(g))
    out, taken = [], set()
    for g in best:
        g = [x for x in g if id(x[1]) not in taken]
        if g:
            out.append(g)
            taken.update(id(x[1]) for x in g)
    return out


def candidates(res: dict) -> list[dict]:
    """All scale hypotheses on the sheet: [{id, kind, ppm, sigma, tag, label, boxes, members, conf, scale_kind}]
    ordered best first. `kind` is the ScaleAnchor kind; `family` the independence class used for consensus."""
    out: list[dict] = []
    paper = res["paper"]
    # printed ratio notes x paper
    if paper.get("px_per_in"):
        seen = set()
        for n in res["notes"]:
            if n["key"] in seen:
                continue
            seen.add(n["key"])
            ppm = paper["px_per_in"] / (M_PER_IN * n["ratio"])
            sig = paper["sigma"] if paper["exact"] or paper.get("std_dpi") else paper["sigma"]
            out.append({"id": f"scale:note:{n['key']}", "kind": "printed_ratio", "family": "ratio", "ppm": ppm,
                        "sigma": max(0.03, sig), "tag": "specified" if paper["exact"] else "defaulted",
                        "label": n["label"], "boxes": [n["box"]], "conf": n["conf"] / 100.0,
                        "note": f"scale note '{n['label']}' on {paper['name'] or 'sheet'}"
                                f"{'' if paper['exact'] else ' (sheet size guessed from the aspect ratio)'}",
                        "weight": 1.2 if paper["exact"] else (0.6 if paper.get("std_dpi") else 0.35)})
            if not paper["exact"]:            # same aspect, other sheet size (half-size prints): a weaker alternative
                long_px = max(res["w"], res["h"])
                for alt in paper.get("ambiguous", [])[:2]:
                    dpi = long_px / PAPER_IN[alt][0]
                    std = any(abs(dpi / sd - 1) < 0.01 for sd in STD_DPI)
                    out.append({"id": f"scale:note:{n['key']}:{alt.split()[0]}{alt.split()[1]}", "kind": "printed_ratio",
                                "family": "ratio", "ppm": dpi / (M_PER_IN * n["ratio"]), "sigma": 0.05, "tag": "defaulted",
                                "label": n["label"], "boxes": [n["box"]], "conf": n["conf"] / 100.0,
                                "note": f"scale note '{n['label']}' if printed on {alt} (half/double-size print)",
                                "weight": 0.45 if std else 0.25})
    # graphic bars
    for i, b in enumerate(res["bars"]):
        if not b["unit"]:
            continue
        per_m = {"ft": 1 / (12 * M_PER_IN), "m": 1.0, "mm": 1000.0}[b["unit"]]
        ppm = b["ppu"] * per_m
        sig = max(0.03, 2 * b["resid_px"] / max(b["span_px"], 1))
        out.append({"id": f"scale:bar:{i}", "kind": "scale_bar", "family": "bar", "ppm": ppm, "sigma": sig, "tag": "drawn",
                    "label": f"graphic scale 0-{max(b['vals']):g} {b['unit']}", "boxes": b["boxes"], "conf": 0.8,
                    "note": f"graphic scale bar labels {', '.join(f'{v:g}' for v in b['vals'])} {b['unit']}", "weight": 1.0})
    # dimension strings: group those that agree
    W = max(res["w"], res["h"])
    dims = [d for d in res["dims"] if not (d["kind"] == "in") and W / 3000.0 <= d["ppm"] <= W / 5.0]
    uniq: dict[tuple, dict] = {}
    for d in dims:                      # one measured span read twice (4x and 6x OCR) is one dimension
        k = (round(d["len_px"] / 3), round(d["ends"][0][0] / 3), round(d["ends"][0][1] / 3))
        if k not in uniq or (d["conf"] > uniq[k]["conf"] and not d["lax"]):
            uniq[k] = d
    pool = []
    for k, d in uniq.items():
        d["_k"] = k
        pool.append((d["ppm"], d))
        for al in d.get("alts", []):          # the same dimension read between its outermost ticks
            if W / 3000.0 <= al["ppm"] <= W / 5.0:
                pool.append((al["ppm"], dict(d, len_px=al["len_px"], ends=al["ends"], ppm=al["ppm"], alt=True, alts=[])))
    used_k: set = set()
    groups = []
    for grp in sorted(_cluster(pool, 0.04), key=lambda g: -len({x[1]["_k"] for x in g})):
        seen_k: dict = {}
        for ppm_, d in sorted(grp, key=lambda x: bool(x[1].get("alt"))):     # primary reading first
            if d["_k"] not in seen_k and d["_k"] not in used_k:
                seen_k[d["_k"]] = (ppm_, d)
        if seen_k:
            used_k.update(seen_k)
            groups.append(list(seen_k.values()))
    for grp in groups:
        items = [x[1] for x in grp]
        ppms = [x[0] for x in grp]
        # weight each by its span: long dimension lines measure more accurately
        wts = [d["len_px"] for d in items]
        ppm = math.exp(sum(w * math.log(p) for w, p in zip(wts, ppms)) / sum(wts))
        spread = max(ppms) / min(ppms) - 1
        sig = max(0.02, spread / 2, 0.04 / math.sqrt(len(items)))
        single = len(items) == 1
        longest = max(items, key=lambda d: d["len_px"])
        lax = sum(1 for d in items if d["lax"])
        out.append({"id": f"scale:dim:{longest['text']}", "kind": "dimension", "family": "dim", "ppm": ppm, "sigma": sig,
                    "tag": "specified", "label": ", ".join(d["text"] for d in items[:6]),
                    "boxes": [d["box"] for d in items], "conf": statistics.mean(d["conf"] for d in items) / 100.0,
                    "members": len(items), "lax": lax, "longest": longest,
                    "note": (f"printed dimension {items[0]['text']} matched to its dimension line" if single else
                             f"{len(items)} printed dimensions ({', '.join(d['text'] for d in items[:6])}) matched to their "
                             f"dimension lines agree within {spread:.0%}"),
                    "weight": 0.7 if single else 1.0 + 0.3 * min(len(items) - 1, 3), "single": single})
    return out


def consensus(cands: list[dict]) -> dict:
    """Group candidates by agreement (AGREE), score each group by distinct independent families, pick the best.
    Returns {'winner': group|None, 'groups': [...], 'conflict': bool}."""
    if not cands:
        return {"winner": None, "groups": [], "conflict": False}
    pool = [(c["ppm"], c) for c in cands]
    groups = []
    for grp in _cluster(pool, AGREE):
        items = [x[1] for x in grp]
        fam = {}
        for c in items:
            fam[c["family"]] = max(fam.get(c["family"], 0), c["weight"])
        score = sum(fam.values())
        groups.append({"items": items, "families": sorted(fam), "score": score,
                       "ppm": math.exp(sum(c["weight"] * math.log(c["ppm"]) / c["sigma"] ** 2 for c in items) /
                                       sum(c["weight"] / c["sigma"] ** 2 for c in items))})
    groups.sort(key=lambda g: -g["score"])
    top = groups[0]
    conflict = len(groups) > 1 and groups[1]["score"] >= 0.5 * top["score"] and any(
        c["tag"] != "defaulted" for c in groups[1]["items"])
    if conflict:                      # many agreeing dimension lines outvote a few that share one misreading
        n1 = sum(c.get("members", 0) for c in top["items"] if c["family"] == "dim")
        n2 = sum(c.get("members", 0) for c in groups[1]["items"] if c["family"] == "dim")
        if n1 >= 10 and n2 < 0.3 * n1 and "bar" not in groups[1]["families"]:
            conflict = False
    return {"winner": top, "groups": groups, "conflict": conflict}


def family_q(c: dict) -> float:
    """Probability-like support of one candidate (before OCR scaling): how often evidence of that kind is right."""
    if c["family"] == "bar":
        return 0.65
    if c["family"] == "ratio":
        return 0.70 if c["tag"] == "specified" else (0.55 if c["weight"] >= 0.6 else 0.2)
    n = c.get("members", 1)
    return 0.35 if n == 1 else min(0.9, 0.6 + 0.12 * (n - 1))


def confidence(res: dict, cons: dict) -> float:
    """0..1, computed (never a model's self-report). Each independent FAMILY in the winning agreement group
    (dimension strings / scale bar / scale note x paper size) contributes support q (single dimension 0.35, n agreeing
    dimensions 0.6+0.12(n-1), bar 0.65, note on a PDF page 0.70, note on a guessed raster size 0.2-0.55); families
    combine as 1 - prod(1 - q) (independent evidence), each q scaled by (0.8 + 0.2 * OCR confidence); a competing group
    backed by printed (non-defaulted) evidence halves the result."""
    w = cons["winner"]
    if not w:
        return 0.0
    best: dict[str, float] = {}
    for c in w["items"]:
        q = family_q(c) * (0.8 + 0.2 * max(0.3, min(1.0, c["conf"])))
        best[c["family"]] = max(best.get(c["family"], 0.0), q)
    miss = 1.0
    for q in best.values():
        miss *= 1.0 - q
    conf = 1.0 - miss
    if cons["conflict"]:
        conf *= 0.5
    return round(max(0.0, min(0.99, conf)), 3)


# --------------------------------------------------------------------------- user answers (cache/checks/<sha>.json)
def load_answers(sha: str) -> dict:
    f = CHECKS / f"{sha}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"answers": {}}


def save_answers(sha: str, data: dict) -> None:
    CHECKS.mkdir(parents=True, exist_ok=True)
    f = CHECKS / f"{sha}.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(f)


def user_value(c: dict, ans: dict) -> Optional[float]:
    """px_per_m a user answer implies for candidate c (yes -> its own; no + typed metres -> span / typed)."""
    if ans.get("answer") == "yes":
        return c["ppm"]
    if ans.get("answer") == "no" and ans.get("value") and c.get("longest"):
        return c["longest"]["len_px"] / float(ans["value"])
    return None


def sheet_state(abs_path: str, sha: str, max_px: int = 2000) -> dict:
    """Everything the solver and the Checks API need: analysis, candidates, consensus, answers, confidence."""
    res = analyze(abs_path, sha, max_px)
    cands = candidates(res)
    answers = load_answers(sha)["answers"]
    rejected = {i for i, a in answers.items() if a.get("answer") == "no" and not user_value(next((c for c in cands if c["id"] == i), {"ppm": 0}), a)}
    live = [c for c in cands if c["id"] not in rejected]
    users = []
    for i, a in answers.items():
        c = next((c for c in cands if c["id"] == i), None)
        v = user_value(c, a) if c else (a.get("ppm") if a.get("answer") == "yes" else None)
        if v:
            users.append({"id": i, "ppm": v, "label": c["label"] if c else i, "boxes": c["boxes"] if c else []})
    cons = consensus(live)
    return {"res": res, "cands": cands, "live": live, "rejected": sorted(rejected), "answers": answers, "users": users,
            "cons": cons, "conf": 0.99 if users else confidence(res, cons)}


def anchors_for(abs_path: str, sha: str, max_px: int = 2000) -> tuple[list[ScaleAnchor], dict]:
    """ScaleAnchors for anchors.solve (+ the state). Anchors outside the winning agreement group are returned with
    note 'REJECTED: ...' (kept for the receipt, skipped by the combination)."""
    st = sheet_state(abs_path, sha, max_px)
    out: list[ScaleAnchor] = []
    win = st["cons"]["winner"]
    for u in st["users"]:
        out.append(ScaleAnchor(kind="user", px_per_m=u["ppm"], rel_sigma=0.01, tag=Tag.chosen,
                               note=f"you confirmed: {u['label']}"))
    for c in st["live"]:
        a = ScaleAnchor(kind=c["kind"], px_per_m=c["ppm"], rel_sigma=c["sigma"], tag=Tag(c["tag"]), note=c["note"])
        if st["users"] and abs(c["ppm"] / st["users"][0]["ppm"] - 1) > AGREE:
            a.note += "; REJECTED: disagrees with the scale you confirmed"
        elif win and c not in win["items"]:
            a.note += f"; REJECTED: outside the {win['ppm']:.2f} px/m agreement group"
        out.append(a)
    return out, st
