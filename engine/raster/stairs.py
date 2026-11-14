"""Stair flights on raster floor plans, by classical line geometry (no network, no model).

A flight is drawn as a run of short, roughly equal, evenly spaced thin lines (the treads): parallel on a
straight run, fanning by a few tens of degrees per step on winders. We find thin dark segments, merge
fragments of the same stroke, then walk from tread to tread: the next tread lies one spacing further along
the current tread's normal, is about as long, and turns by at most MAX_TURN degrees. A walk of
>= MIN_TREADS lines with near-constant spacing is one flight; its polygon is the minimum-area box of the
treads' endpoints (long axis = walking direction for typical flights).

Rejected look-alikes (checked on CubiCasa5k scans):
  * sauna benches / slatted decks: coloured ink, slats far longer than their spacing (ratio > MAX_RATIO)
  * wardrobes / shelf rows: boxes about as deep as wide (ratio < MIN_RATIO)
  * hatching inside walls: lies on thick ink, removed before line finding
"""
from __future__ import annotations

import math

import cv2
import numpy as np

MIN_TREADS = 5
MAX_TURN = 46.0          # degrees between neighbouring treads (0 on straight runs, 15-45 on winders)
MIN_RATIO, MAX_RATIO = 1.8, 7.5   # median tread length / mean tread spacing
GAP_CV = 0.30            # coefficient of variation of the spacing
LEN_CV = 0.30            # coefficient of variation of the tread lengths
MAX_SHEAR = 0.35         # along-tread drift per unit of walking distance on straight runs
MAX_BG_SAT = 60          # median saturation of the background inside a flight
MERGE_TOL = 3.5          # px, at least: both edges of one pen stroke (LSD sees each edge)
READER = "tread-line detector"


def _ink(img: np.ndarray, faint: bool = False) -> np.ndarray:
    """Thin, dark, unsaturated ink (uint8 0/255); thick strokes (walls, fills) removed. faint=True: ink is what is
    clearly darker than its own neighbourhood (light pencil / faded scans, where a global threshold loses the treads)."""
    if img.ndim == 2:
        gray, sat = img, np.zeros_like(img)
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1]
    if faint:
        bg = cv2.dilate(gray, np.ones((9, 9), np.uint8))           # local paper brightness
        dark = (((bg.astype(np.int16) - gray) > 18) & (sat < 90)).astype(np.uint8) * 255
    else:
        t, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        t = min(float(t), 170.0) if t > 40 else 128.0   # pure black/white renders: Otsu returns ~0
        dark = ((gray < t) & ((sat < 90) | (gray < 60))).astype(np.uint8) * 255
    k = max(3, int(round(min(gray.shape) / 220)) | 1) + 2   # wider than a pen stroke
    thick = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    thick = cv2.dilate(thick, np.ones((3, 3), np.uint8))
    return cv2.bitwise_and(dark, cv2.bitwise_not(thick))


def _stroke(thin: np.ndarray) -> float:
    """Typical pen width of the thin layer (ink area / centre-line length)."""
    from skimage.morphology import skeletonize
    sk = int(skeletonize(thin > 0).sum())
    return float(np.count_nonzero(thin)) / sk if sk else 2.0


def _segments(thin: np.ndarray) -> np.ndarray:
    """LSD on the thin-ink layer: clean full-length segments, one per stroke edge (pairs merged later)."""
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    got = lsd.detect(cv2.GaussianBlur(255 - thin, (3, 3), 0))[0]
    return np.zeros((0, 4), np.float64) if got is None else got[:, 0, :].astype(np.float64)


def _merge(segs: np.ndarray, tol: float, maxgap: float) -> np.ndarray:
    """Join fragments and double edges of one stroke: same angle (6 deg), within tol of the same line,
    and touching or nearly touching along it. Returns merged segments (x1,y1,x2,y2)."""
    n = len(segs)
    if n == 0:
        return segs
    d = segs[:, 2:] - segs[:, :2]
    ang = (np.degrees(np.arctan2(d[:, 1], d[:, 0])) + 180.0) % 180.0
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        da = np.abs((ang - ang[i] + 90.0) % 180.0 - 90.0)
        js = np.where((da <= 6.0) & (np.arange(n) > i))[0]
        if not len(js):
            continue
        u = d[i] / (np.hypot(*d[i]) + 1e-9)
        nv = np.array([-u[1], u[0]])
        o = segs[i, :2] @ nv
        a0, a1 = sorted((segs[i, :2] @ u, segs[i, 2:] @ u))
        for j in js:
            p, q = segs[j, :2], segs[j, 2:]
            if abs(p @ nv - o) > tol or abs(q @ nv - o) > tol:
                continue
            b0, b1 = sorted((p @ u, q @ u))
            if max(a0, b0) - min(a1, b1) <= maxgap:
                parent[find(j)] = find(i)
    groups: dict = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out = []
    for g in sorted(groups.values()):
        P = segs[g].reshape(-1, 2)
        dd = d[g]
        # direction from the longest member, extent from all endpoints
        k = int(np.argmax(np.hypot(dd[:, 0], dd[:, 1])))
        u = dd[k] / (np.hypot(*dd[k]) + 1e-9)
        c = P.mean(axis=0)
        t = (P - c) @ u
        out.append([*(c + t.min() * u), *(c + t.max() * u)])
    return np.asarray(out, np.float64)


def _walks(segs: np.ndarray, gmin: float, gmax: float, tol: float = MERGE_TOL) -> list[list[int]]:
    mid = (segs[:, :2] + segs[:, 2:]) / 2
    d = segs[:, 2:] - segs[:, :2]
    ln = np.hypot(d[:, 0], d[:, 1])
    u = d / ln[:, None]
    nrm = np.stack([-u[:, 1], u[:, 0]], axis=1)
    cos_turn = math.cos(math.radians(MAX_TURN))

    def step(i: int, ndir: np.ndarray, prev_gap: float | None, banned: set) -> tuple[int, np.ndarray, float] | None:
        dm = mid - mid[i]
        p = dm @ ndir
        q = np.abs(dm @ u[i])
        par = np.abs(u @ u[i])
        ok = (p > tol) & (p <= gmax) & (q <= 0.3 * ln[i]) & (par >= cos_turn) \
            & (ln >= 0.6 * ln[i]) & (ln <= 1.67 * ln[i])
        for b in banned:
            ok[b] = False
        js = np.where(ok)[0]
        if not len(js):
            return None
        j = int(js[np.argmin(p[js])])
        # a nearer look-alike than any tread spacing means slats / hatching, not stairs: stop here
        if p[j] < gmin or (prev_gap is not None and not (0.6 * prev_gap <= p[j] <= 1.6 * prev_gap)):
            return None
        nj = nrm[j] if nrm[j] @ ndir > 0 else -nrm[j]
        return j, nj, float(p[j])

    used = np.zeros(len(segs), bool)
    walks = []
    for s in np.lexsort((mid[:, 0], mid[:, 1])):
        if used[s]:
            continue
        chain = [int(s)]
        seen = {int(s)}
        for sign in (1.0, -1.0):
            cur, ndir, gap = int(s), sign * nrm[s], None
            side = []
            while True:
                r = step(cur, ndir, gap, seen)
                if r is None:
                    break
                cur, ndir, gap = r
                seen.add(cur)
                side.append(cur)
            chain = chain + side if sign > 0 else side[::-1] + chain
        if len(chain) >= MIN_TREADS:
            walks.append(chain)
            used[chain] = True
    return walks


def _pair_clean(segs: np.ndarray, i: int, j: int, ink: np.ndarray) -> bool:
    """No third line parallel to the treads between treads i and j (rules out slats and hatching,
    where the walk skipped lines closer than a tread spacing)."""
    p0, p1, q0, q1 = segs[i, :2], segs[i, 2:], segs[j, :2], segs[j, 2:]
    if np.hypot(*(p0 - q0)) + np.hypot(*(p1 - q1)) > np.hypot(*(p0 - q1)) + np.hypot(*(p1 - q0)):
        q0, q1 = q1, q0
    h, w = ink.shape
    g = np.linspace(0.15, 0.85, 15)[:, None]
    A, B = p0 + g * (p1 - p0), q0 + g * (q1 - q0)
    for f in (0.3, 0.5, 0.7):
        P = np.rint((1 - f) * A + f * B).astype(int)
        P[:, 0] = P[:, 0].clip(0, w - 1)
        P[:, 1] = P[:, 1].clip(0, h - 1)
        if ink[P[:, 1], P[:, 0]].mean() > 0.6 * 255:
            return False
    return True


def _fan_ok(segs: np.ndarray, i: int, j: int) -> bool:
    """Two non-parallel neighbours of a winder meet near the newel, i.e. within about one tread length
    of tread i's midpoint; slightly skewed hatching meets far away."""
    p, r = segs[i, :2], segs[i, 2:] - segs[i, :2]
    q, s = segs[j, :2], segs[j, 2:] - segs[j, :2]
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9:
        return True
    t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / den
    x = p + t * r
    return float(np.hypot(*(x - (p + r / 2)))) <= 1.0 * float(np.hypot(*r))


def _extend(segs: np.ndarray, ink: np.ndarray, reach: float) -> np.ndarray:
    """Push each end outward along the segment while the stroke continues (gaps < 3 px).
    LSD stops short at crossings (text, walking line); board and siding lines then show their real,
    long length and drop out of the tread length range."""
    h, w = ink.shape
    K = int(reach) + 1
    k = np.arange(1, K + 1, dtype=np.float64)
    out = segs.copy()
    for n, (x1, y1, x2, y2) in enumerate(segs):
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1:
            continue
        u = np.array([x2 - x1, y2 - y1]) / L
        for end, sgn, sl in ((np.array([x2, y2]), 1.0, slice(2, 4)), (np.array([x1, y1]), -1.0, slice(0, 2))):
            P = np.rint(end + sgn * k[:, None] * u).astype(int)
            inside = (P[:, 0] >= 0) & (P[:, 0] < w) & (P[:, 1] >= 0) & (P[:, 1] < h)
            v = np.zeros(K, bool)
            v[inside] = ink[P[inside, 1], P[inside, 0]] > 0
            gap = ~v
            run = gap[:-2] & gap[1:-1] & gap[2:]
            stop = int(np.argmax(run)) if run.any() else K
            out[n, sl] = end + sgn * stop * u
    return out


def _best_window(chain: list[int], segs: np.ndarray, ink: np.ndarray, tol: float = MERGE_TOL) -> tuple[list[int], dict] | None:
    """Longest contiguous run of the walk that reads as a flight."""
    mid = (segs[:, :2] + segs[:, 2:]) / 2
    d = segs[:, 2:] - segs[:, :2]
    ln = np.hypot(d[:, 0], d[:, 1])
    ang = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 180.0
    n = len(chain)
    dang = [((ang[chain[k + 1]] - ang[chain[k]]) + 90.0) % 180.0 - 90.0 for k in range(n - 1)]
    clean = [_pair_clean(segs, chain[k], chain[k + 1], ink)
             and (abs(dang[k]) <= 6.0 or _fan_ok(segs, chain[k], chain[k + 1])) for k in range(n - 1)]
    for size in range(n, MIN_TREADS - 1, -1):
        for a in range(0, n - size + 1):
            if not all(clean[a:a + size - 1]):
                continue
            da = np.asarray(dang[a:a + size - 1])
            big = da[np.abs(da) > 6.0]
            if len(big) and not (np.all(big > 0) or np.all(big < 0)):
                continue                                     # winders turn one way; zigzags and text do not
            w = chain[a:a + size]
            gaps = np.hypot(*np.diff(mid[w], axis=0).T)
            gm = float(gaps.mean())
            gcv = float(gaps.std() / gm)
            lens = ln[w]
            lcv = float(lens.std() / lens.mean())
            ratio = float(np.median(lens)) / gm
            if not (gcv <= GAP_CV and lcv <= LEN_CV and MIN_RATIO <= ratio <= MAX_RATIO):
                continue
            if np.abs(da).sum() < 20.0:
                # straight run: treads start and end on a common stringer square to them (hatching is sheared)
                u0 = d[w[0]] / ln[w[0]]
                n0 = np.array([-u0[1], u0[0]])
                t, sh = mid[w] @ n0, mid[w] @ u0
                if abs(float(np.polyfit(t - t.mean(), sh - sh.mean(), 1)[0])) > MAX_SHEAR:
                    continue
            return w, {"gap": gm, "gcv": gcv, "lcv": lcv, "len": float(np.median(lens)), "turn": float(np.abs(da).sum())}
    return None


def detect(image_bgr: np.ndarray, rooms=None, walls=None) -> list[dict]:
    """Stair flights as oriented boxes in image pixels.

    walls (list of {"outer": [[x,y],...]}), when given, mask out treads lying on wall bodies; rooms is
    accepted for API symmetry. Deterministic, no network. A faint-ink pass runs only when the normal one finds nothing."""
    got = _detect(image_bgr, walls, faint=False)
    if not got and image_bgr is not None and image_bgr.size:
        got = _detect(image_bgr, walls, faint=True)
        for f in got:
            f["attrs"]["reader"] = READER + " (faint-ink pass)"
    if not got and image_bgr is not None and image_bgr.size:
        got = _rungs(image_bgr)
    return got


def _rungs(image_bgr: np.ndarray) -> list[dict]:
    """Second stair test (fallback): a window crossed by >= 6 evenly spaced, near-full-width parallel lines (treads).
    Text rows are not continuous lines; a single hatch does not span the window. Faint ink, both orientations."""
    thin = _ink(image_bgr, True) > 0
    h, w = thin.shape
    out: list[dict] = []
    for frac in (0.22, 0.16, 0.12):
        win = int(frac * min(h, w))
        step = max(4, win // 3)
        for y0 in range(0, h - win + 1, step):
            for x0 in range(0, w - win + 1, step):
                sub = thin[y0:y0 + win, x0:x0 + win]
                for axis in (1, 0):                 # axis 1: horizontal treads (rows), 0: vertical treads (columns)
                    cov = sub.mean(axis=axis)
                    rows = np.where(cov >= 0.55)[0]
                    if len(rows) < 6:
                        continue
                    groups = np.split(rows, np.where(np.diff(rows) > 2)[0] + 1)
                    cen = np.array([g.mean() for g in groups])
                    if len(cen) < 6:
                        continue
                    gaps = np.diff(cen)
                    if gaps.mean() < 4 or gaps.std() / gaps.mean() > 0.3 or len(cen) * 2 > win / 3:
                        continue
                    a, b = cen.min(), cen.max()
                    lens = []                        # full length of each line (beyond the window): slats run on
                    for c0 in cen[:: max(1, len(cen) // 4)]:
                        if axis == 1:
                            row, mid = thin[int(y0 + c0)], x0 + win // 2
                        else:
                            row, mid = thin[:, int(x0 + c0)], y0 + win // 2
                        lo, hi, miss = mid, mid, 0
                        while lo > 0 and miss <= 3:
                            lo -= 1; miss = 0 if row[lo] else miss + 1
                        miss = 0
                        while hi < len(row) - 1 and miss <= 3:
                            hi += 1; miss = 0 if row[hi] else miss + 1
                        lens.append(hi - lo)
                    if float(np.median(lens)) / gaps.mean() > MAX_RATIO:
                        continue                     # deck slats / hatching: far longer than their spacing
                    if axis == 1:
                        poly = [[x0, y0 + a], [x0 + win, y0 + a], [x0 + win, y0 + b], [x0, y0 + b]]
                    else:
                        poly = [[x0 + a, y0], [x0 + b, y0], [x0 + b, y0 + win], [x0 + a, y0 + win]]
                    out.append({"kind": "stairs", "polygon": [[float(x), float(y)] for x, y in poly],
                                "conf": round(min(0.8, 0.35 + 0.04 * len(cen)), 3),
                                "attrs": {"treads": int(len(cen)), "spacing_px": round(float(gaps.mean()), 1),
                                          "tread_px": float(win), "turn_deg": 0,
                                          "reader": "evenly spaced parallel treads (fallback window test)"}})
    return _dedupe(out)


def _detect(image_bgr: np.ndarray, walls, faint: bool) -> list[dict]:
    if image_bgr is None or image_bgr.size == 0:
        return []
    h, w = image_bgr.shape[:2]
    diag = math.hypot(w, h)
    thin = _ink(image_bgr, faint)
    if walls:
        wm = np.zeros((h, w), np.uint8)
        for wl in walls:
            P = np.asarray(wl.get("outer") or [], np.int32)
            if len(P) >= 3:
                cv2.fillPoly(wm, [P], 255)
        thin = cv2.bitwise_and(thin, cv2.bitwise_not(wm))
    lmin, lmax = max(10.0, 0.015 * diag), 0.12 * diag   # treads ~0.8-1.2 m on a 7-30 m sheet (zoomed scans: larger)
    gmin, gmax = max(4.0, 0.004 * diag), 0.03 * diag
    tol = max(MERGE_TOL, _stroke(thin) + 1.5)
    ink_s = cv2.dilate(thin, np.ones((3, 3), np.uint8))
    segs = _segments(thin)
    if not len(segs):
        return []
    segs = _merge(_extend(segs, ink_s, lmax), tol=tol, maxgap=max(4.0, 0.003 * diag))
    ln = np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1])
    segs = segs[(ln >= lmin) & (ln <= lmax)]
    out: list[dict] = []
    sat = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)[:, :, 1] if image_bgr.ndim == 3 else None
    for chain in _walks(segs, gmin, gmax, tol):
        got = _best_window(chain, segs, ink_s, tol)
        if got is None:
            continue
        win, st = got
        pts = segs[win].reshape(-1, 2).astype(np.float32)
        box = cv2.boxPoints(cv2.minAreaRect(pts))
        if sat is not None:
            m = np.zeros((h, w), np.uint8)
            cv2.fillPoly(m, [np.rint(box).astype(np.int32)], 255)
            m[ink_s > 0] = 0
            if m.any() and float(np.median(sat[m > 0])) > MAX_BG_SAT:
                continue                                     # slats on a coloured fill: sauna bench, deck
        turn = st["turn"]
        conf = min(0.95, 0.45 + 0.05 * min(len(win), 10) - st["gcv"] - 0.5 * st["lcv"])
        out.append({"kind": "stairs",
                    "polygon": [[round(float(x), 1), round(float(y), 1)] for x, y in box],
                    "conf": round(max(conf, 0.05), 3),
                    "attrs": {"treads": len(win), "spacing_px": round(st["gap"], 1),
                              "tread_px": round(st["len"], 1), "turn_deg": round(turn),
                              "reader": READER}})
    return _dedupe(out)


def _dedupe(found: list[dict]) -> list[dict]:
    """Drop flights whose box mostly lies inside a stronger one."""
    found.sort(key=lambda f: (-f["attrs"]["treads"], -f["conf"]))
    keep: list[dict] = []
    for f in found:
        P = np.asarray(f["polygon"], np.float32)
        a = abs(cv2.contourArea(P))
        if not any(a > 0 and cv2.intersectConvexConvex(P, np.asarray(g["polygon"], np.float32))[0]
                   > 0.5 * min(a, abs(cv2.contourArea(np.asarray(g["polygon"], np.float32)))) for g in keep):
            keep.append(f)
    return keep
