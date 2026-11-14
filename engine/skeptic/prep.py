"""Shared pixel prep for the skeptic voters (own code; NOT engine/raster).

All skeptic voters share this one function, so they are independent of the raster route but NOT of each
other's binarisation. Documented in docs/handoff/skeptic.md.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Prep:
    gray: np.ndarray        # processing-resolution gray
    dark: np.ndarray        # uint8 0/255 ink mask
    scale: float            # processing px per original px
    thick: float            # estimated wall thickness (processing px)
    walls: np.ndarray       # uint8 0/255 thick structures
    ink: np.ndarray         # uint8 0/255 loose ink mask (thin anti-aliased strokes included)
    h0: int
    w0: int

    def to_orig(self, pts):
        return [(min(max(float(x) / self.scale, 0.0), self.w0 - 1.0), min(max(float(y) / self.scale, 0.0), self.h0 - 1.0))
                for x, y in pts]


def read_gray(path: str):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 3 and img.shape[2] == 4:  # composite alpha on white
        a = img[:, :, 3:4].astype(np.float32) / 255.0
        img = (img[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _runs(m: np.ndarray):
    """Run lengths of True along the last axis, as a 1-D array."""
    d = np.diff(np.pad(m.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    st = np.nonzero(d == 1)
    en = np.nonzero(d == -1)
    return (en[1] - st[1])


def estimate_thickness(dark: np.ndarray) -> float:
    """Wall thickness = length-weighted mode of horizontal and vertical ink run lengths in [4, 40] px."""
    m = dark > 0
    r = np.concatenate([_runs(m[::2]), _runs(m.T[::2])])
    r = r[(r >= 4) & (r <= 40)]
    if r.size < 20:
        return 5.0
    h = np.bincount(r, weights=r, minlength=41)[4:41]
    return float(4 + int(np.argmax(h)))


@functools.lru_cache(maxsize=4)
def prep(path: str, target: int = 1000):
    g0 = read_gray(path)
    if g0 is None:
        return None
    h0, w0 = g0.shape
    s = float(min(max(target / max(h0, w0), 0.25), 3.0))
    g = cv2.resize(g0, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    thr = min(float(cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]), 130.0)
    dark = (g < thr).astype(np.uint8) * 255
    thick = estimate_thickness(dark)
    k = max(3, int(round(thick * 0.8)))
    walls = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    bg = cv2.medianBlur(cv2.resize(g, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA), 15)
    bg = cv2.resize(bg, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_LINEAR)
    ink = ((bg.astype(np.int16) - g.astype(np.int16)) > 45).astype(np.uint8) * 255
    ink = cv2.bitwise_or(ink, dark)
    return Prep(g, dark, s, thick, walls, ink, h0, w0)
