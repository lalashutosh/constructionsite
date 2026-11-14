"""Shape cues that separate facades/sections from plans: symmetry, periodicity, wall mass, region mix."""
from __future__ import annotations

import cv2
import numpy as np

from engine.skeptic.prep import read_gray

EXTRA_NAMES = ["sym", "per", "wall_frac", "n_small", "n_mid", "small_cv"]


def compute_extra(path: str) -> dict:
    g0 = read_gray(path)
    s = 500 / max(g0.shape)
    g = cv2.resize(g0, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    hist = np.bincount(g.ravel(), minlength=256).astype(np.float64)
    mode = int(np.argmax(np.convolve(hist, np.ones(9) / 9, mode="same")))
    ink = (g < max(mode - 45, 0)).astype(np.float32)
    # mirror symmetry (left-right) via FFT cross-correlation of the ink map with its flip
    a = ink - ink.mean()
    b = a[:, ::-1]
    shp = (a.shape[0] * 2, a.shape[1] * 2)
    cc = np.fft.irfft2(np.fft.rfft2(a, s=shp) * np.conj(np.fft.rfft2(b, s=shp)))
    sym = float(cc.max() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))
    # periodicity: strongest autocorrelation peak of the column ink profile (repeated windows/bays)
    prof = ink.sum(axis=0)
    prof = prof - prof.mean()
    ac = np.correlate(prof, prof, "full")[len(prof) - 1:]
    ac = ac / (ac[0] + 1e-6)
    per = float(ac[max(5, len(ac) // 50): len(ac) // 2].max()) if len(ac) > 20 else 0.0
    u8 = (ink * 255).astype(np.uint8)
    thick = cv2.morphologyEx(u8, cv2.MORPH_OPEN, np.ones((4, 4), np.uint8))
    wall_frac = float((thick > 0).sum() / max((u8 > 0).sum(), 1))
    free = cv2.bitwise_not(cv2.dilate(u8, np.ones((3, 3), np.uint8)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
    area = g.shape[0] * g.shape[1]
    ar = np.array([st[i, 4] for i in range(1, n)
                   if st[i, 0] > 0 and st[i, 1] > 0 and st[i, 0] + st[i, 2] < g.shape[1]
                   and st[i, 1] + st[i, 3] < g.shape[0] and st[i, 4] > 12], float)
    small = ar[ar < 0.004 * area] if ar.size else ar
    n_small = int(small.size)
    n_mid = int(((ar >= 0.004 * area) & (ar < 0.2 * area)).sum()) if ar.size else 0
    small_cv = float(small.std() / (small.mean() + 1e-6)) if n_small > 3 else 0.0
    return dict(sym=sym, per=per, wall_frac=wall_frac, n_small=n_small, n_mid=n_mid, small_cv=small_cv)
