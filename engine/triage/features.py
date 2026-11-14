"""Pixel + OCR features for sheet triage. No network; tesseract is optional (flags default to 0 if missing)."""
from __future__ import annotations

import re

import cv2
import numpy as np

from engine.skeptic.prep import read_gray

KW_ELEV = re.compile(r"elevation|elevations|fa[cç]ade|fassade|ansicht|facciata|alzado|nordost|southwest|"
                     r"north elev|south elev|east elev|west elev|julkisivu|sivukuva|\bview\b", re.I)
KW_SECT = re.compile(r"section|schnitt|querschnitt|l[aä]ngsschnitt|coupe|sezione|leikkaus|profil", re.I)
KW_PLAN = re.compile(r"floor ?plan|grundri|ground floor|first floor|plan\b|pohjakuva|pohja|kerros|krs|asunto|"
                     r"\bOH\b|\bMH\b|\bKH\b|\bET\b|\bWC\b|\bkeitti|\bparveke|\bsauna|\bK\b", re.I)
KW_SITE = re.compile(r"site plan|lageplan|situation|karta|asemapiirros|tonttikartta|map|plot", re.I)
KW_SCHED = re.compile(r"schedule|door list|window list|ovilista|\bqty\b|\bmark\b|\btype\b", re.I)

FEATURE_NAMES = ["min_dim", "aspect", "blur", "bg_frac", "entropy", "sat", "ortho", "ink", "rooms", "hline",
                 "kw_elev", "kw_sect", "kw_plan", "kw_site", "kw_sched", "words"]


def ocr_text(gray: np.ndarray, timeout: int = 8) -> str:
    try:
        import pytesseract
        h, w = gray.shape
        s = 1400 / max(h, w)
        g = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        return pytesseract.image_to_string(g, lang="eng+fin", config="--psm 11", timeout=timeout)
    except Exception:  # noqa: BLE001  (tesseract missing / timeout)
        return ""


def compute(path: str, use_ocr: bool = True) -> dict:
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return {"ok": False}
    sat = 0.0
    if img.ndim == 3 and img.shape[2] >= 3:
        hsv = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2HSV)
        sat = float((hsv[:, :, 1] > 60).mean())
    g0 = read_gray(path)
    h0, w0 = g0.shape
    s = min(1.0, 1000 / max(h0, w0))
    g = cv2.resize(g0, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else g0
    # blur: variance of Laplacian relative to image contrast, on a fixed-size crop to be size independent
    sm = cv2.resize(g, (640, int(640 * g.shape[0] / g.shape[1]))) if g.shape[1] > 640 else g
    lap = float(cv2.Laplacian(sm, cv2.CV_64F).var() / (sm.astype(np.float64).var() + 1.0))
    hist = np.bincount(g.ravel(), minlength=256).astype(np.float64)
    hs = np.convolve(hist, np.ones(9) / 9, mode="same")
    mode = int(np.argmax(hs))
    bg_frac = float(hist[max(mode - 30, 0): mode + 31].sum() / hist.sum())
    p = hist / hist.sum()
    entropy = float(-(p[p > 0] * np.log2(p[p > 0])).sum())
    thr = max(mode - 45, 0)
    ink = (g < thr).astype(np.uint8) * 255
    inkf = float((ink > 0).mean())
    # right-angle structure from probabilistic Hough on edges
    edges = cv2.Canny(g, 60, 150)
    minlen = max(20, int(0.04 * max(g.shape)))
    ls = cv2.HoughLinesP(edges, 1, np.pi / 180, 40, minLineLength=minlen, maxLineGap=4)
    ortho = 0.0
    if ls is not None and len(ls) > 5:
        ls = ls[:, 0, :].astype(np.float64)
        ang = np.degrees(np.arctan2(ls[:, 3] - ls[:, 1], ls[:, 2] - ls[:, 0])) % 90
        ln = np.hypot(ls[:, 2] - ls[:, 0], ls[:, 3] - ls[:, 1])
        near = (ang < 4) | (ang > 86)
        ortho = float(ln[near].sum() / ln.sum())
    # enclosed rooms: big white regions bounded by ink
    sealed = cv2.dilate(ink, np.ones((5, 5), np.uint8))
    free = cv2.bitwise_not(sealed)
    n, lab, st, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
    area = g.shape[0] * g.shape[1]
    rooms = 0
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if 0.004 * area < a < 0.25 * area and x > 0 and y > 0 and x + w < g.shape[1] and y + h < g.shape[0] \
                and a > 0.3 * w * h and max(w, h) < 6 * min(w, h):
            rooms += 1
    # longest horizontal ink run / width (ground line of elevations)
    hl = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, max(15, g.shape[1] // 3)), np.uint8))
    hline = float(hl.any(axis=0).mean()) if hl.any() else 0.0
    f = {"ok": True, "min_dim": min(h0, w0), "w": w0, "h": h0, "aspect": w0 / h0, "blur": lap, "bg_frac": bg_frac,
         "entropy": entropy, "sat": sat, "ortho": ortho, "ink": inkf, "rooms": rooms, "hline": hline,
         "kw_elev": 0, "kw_sect": 0, "kw_plan": 0, "kw_site": 0, "kw_sched": 0, "words": 0}
    if use_ocr:
        t = ocr_text(g0)
        f["words"] = len(re.findall(r"[A-Za-zÅÄÖåäö]{3,}", t))
        f["kw_elev"] = len(KW_ELEV.findall(t))
        f["kw_sect"] = len(KW_SECT.findall(t))
        f["kw_plan"] = len(KW_PLAN.findall(t))
        f["kw_site"] = len(KW_SITE.findall(t))
        f["kw_sched"] = len(KW_SCHED.findall(t))
        f["text"] = t[:400]
    return f
