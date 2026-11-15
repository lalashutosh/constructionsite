"""Building / slab outline of a big construction sheet at a KNOWN scale, and the zones inside it.

Two drawing conventions, detected per sheet:
  * screened background (MEP sheets: piping, HVAC, electrical): the architecture is printed in halftone grey (~170) and
    the discipline's own work in black. The grey layer alone IS the building, so the outline comes from it.
  * single layer (architectural / structural): walls and slab edges are drawn as PAIRS of long parallel lines
    0.05-0.6 m apart at the solved scale; dimension lines are single and carry dimension text, so they are dropped.
The outline is the orthogonal hull of the main line network (rectangles, L and T shapes are orthogonally convex),
tolerant to door gaps. Zones = the outline cut by the same paired lines (isolation joints, slab edges).

  outline(abs_path, sha, ppm, view_box) -> {polygon, area_m2, bbox_m, method, zones: [{polygon, area_m2, centroid}]}
All coordinates are ORIGINAL image pixels. No network, deterministic."""
from __future__ import annotations

import json
import pathlib
from typing import Optional

import cv2
import numpy as np

from engine.scale import sheet_scale as S
from engine.scale import sheet_text as T

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "outline"
VERSION = "v2"


def _long_lines(ink: np.ndarray, axis: int, lmin: int):
    k = np.ones((1, lmin), np.uint8) if axis == 0 else np.ones((lmin, 1), np.uint8)
    m = cv2.morphologyEx(ink, cv2.MORPH_OPEN, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, _a = st[i]
        if axis == 0 and h <= 14:
            out.append((y + h / 2, x, x + w, i, h))
        if axis == 1 and w <= 14:
            out.append((x + w / 2, y, y + h, i, w))
    return out, lab


def _paired(lines, gmin: float, gmax: float, match: bool = False):
    keep = set()
    srt = sorted(range(len(lines)), key=lambda i: lines[i][0])
    for ii, i in enumerate(srt):
        c1, a1, b1, _, t1 = lines[i]
        for j in srt[ii + 1:]:
            c2, a2, b2, _, t2 = lines[j]
            if c2 - c1 > gmax:
                break
            if match and max(t1, t2) > 1.6 * min(t1, t2) + 1:          # a heavy joint line next to a hairline is not a pair
                continue
            if c2 - c1 >= gmin and min(b1, b2) - max(a1, a2) >= 0.6 * min(b1 - a1, b2 - a2):
                keep.update((i, j))
    return [lines[k] for k in sorted(keep)]


def _ortho_hull(walls: np.ndarray, k: int) -> np.ndarray:
    """Rows spanned (leftmost..rightmost) AND columns spanned (top..bottom), each tolerant to gaps of ~2k."""
    vd = cv2.dilate(walls, np.ones((k, 1), np.uint8))
    hd = cv2.dilate(walls, np.ones((1, k), np.uint8))
    rows = np.zeros_like(walls)
    for y in np.where(vd.any(1))[0]:
        xs = np.flatnonzero(vd[y])
        rows[y, xs[0]:xs[-1] + 1] = 1
    cols = np.zeros_like(walls)
    for x in np.where(hd.any(0))[0]:
        ys = np.flatnonzero(hd[:, x])
        cols[ys[0]:ys[-1] + 1, x] = 1
    return rows & cols


def _main_network(m: np.ndarray, link: int) -> np.ndarray:
    net = cv2.dilate(m, np.ones((link | 1, link | 1), np.uint8))
    n, lab, _st, _ = cv2.connectedComponentsWithStats(net, 8)
    if n <= 2:
        return m
    sums = np.bincount(lab[m > 0].ravel(), minlength=n)
    sums[0] = 0
    return (m * (lab == int(np.argmax(sums)))).astype(np.uint8)


def outline(abs_path: str, sha: str, ppm: float, view_box: Optional[list] = None, work: int = 4000) -> Optional[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sha}-{ppm:.2f}-{VERSION}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            pass
    res = _outline(abs_path, sha, ppm, view_box, work)
    f.write_text(json.dumps(res))
    return res


def _outline(abs_path: str, sha: str, ppm: float, view_box, work: int) -> Optional[dict]:
    g0, _pdf = S.load_gray(abs_path, 2000)
    H0, W0 = g0.shape
    s = min(1.0, work / max(H0, W0))                        # work at <= 4000 px: fast, lines still 2+ px
    p = ppm * s
    dark0 = (g0 < 110).astype(np.uint8)                     # layers are told apart at FULL resolution (anti-aliased
    grey0 = ((g0 >= 135) & (g0 <= 220) & (cv2.dilate(dark0, np.ones((5, 5), np.uint8)) == 0)).astype(np.uint8)
    grey0 = cv2.morphologyEx(grey0, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))   # edges of black lines are grey too)
    c0 = cv2.imread(abs_path, cv2.IMREAD_COLOR) if not abs_path.lower().endswith(".pdf") else None
    if c0 is not None and c0.shape[:2] == g0.shape:
        sat = cv2.cvtColor(c0, cv2.COLOR_BGR2HSV)[:, :, 1]
        grey0[sat > 30] = 0                                   # colour fills (legend zones) are not screened line work
    grey0[cv2.morphologyEx(grey0, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)) > 0] = 0    # nor are solid grey fills
    screened = grey0.sum() > 0.2 * dark0.sum() and grey0.sum() > 0.002 * grey0.size

    def down(m):
        return (cv2.resize(m * 255, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) > 40).astype(np.uint8) if s < 1 else m
    ink = down(grey0) if screened else down((g0 < 150).astype(np.uint8))
    words = T.words(abs_path, sha)
    for w in words:                                         # text is not geometry
        a, b, c, d = [int(v * s) for v in w["box"]]
        ink[max(0, b - 1):d + 2, max(0, a - 1):c + 2] = 0
    if view_box:
        vm = np.zeros_like(ink)
        x0, y0, x1, y1 = [int(v * s) for v in view_box]
        vm[max(0, y0):y1, max(0, x0):x1] = 1
        ink &= vm
    if screened:
        walls = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((max(3, int(0.3 * p)) | 1,) * 2, np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(walls, 8)
        keep = np.zeros(n, bool)
        for i in range(1, n):
            if max(st[i][2], st[i][3]) >= 1.0 * p:
                keep[i] = True
        walls = keep[lab].astype(np.uint8)
        method = "screened background layer (the building printed in grey under the black piping/services)"
    else:
        lmin = max(20, int(1.5 * p))
        Hl, labH = _long_lines(ink, 0, lmin)
        Vl, labV = _long_lines(ink, 1, lmin)
        dims = []
        for w in words:
            if S.parse_dim(w["text"]):
                b = [v * s for v in w["box"]]
                dims.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, max(4.0, min(b[2] - b[0], b[3] - b[1]))))

        def carries_dim(line, axis):
            cc, a, b = line[0], line[1], line[2]
            for (x, y, h) in dims:
                u, v = (x, y) if axis == 0 else (y, x)
                if a - h <= u <= b + h and abs(v - cc) < 2.5 * h:
                    return True
            return False
        Hl = [l for l in Hl if not carries_dim(l, 0)]
        Vl = [l for l in Vl if not carries_dim(l, 1)]
        Hp, Vp = _paired(Hl, 0.05 * p, 0.6 * p), _paired(Vl, 0.05 * p, 0.6 * p)
        walls = np.zeros_like(ink)
        ih = np.zeros(labH.max() + 1, bool); ih[[l[3] for l in Hp]] = True
        iv = np.zeros(labV.max() + 1, bool); iv[[l[3] for l in Vp]] = True
        walls[ih[labH]] = 1
        walls[iv[labV]] = 1
        Hm, Vm = _paired(Hl, 0.05 * p, 0.6 * p, True), _paired(Vl, 0.05 * p, 0.6 * p, True)
        seps = np.zeros_like(ink)
        jh = np.zeros(labH.max() + 1, bool); jh[[l[3] for l in Hm]] = True
        jv = np.zeros(labV.max() + 1, bool); jv[[l[3] for l in Vm]] = True
        seps[jh[labH]] = 1
        seps[jv[labV]] = 1
        method = "paired wall / slab-edge lines (dimension lines excluded)"
    if walls.sum() == 0:
        return None
    if screened:
        seps = walls.copy()                                 # every grey wall / every same-weight line pair: separators
    walls = _main_network(walls, int(1.5 * p))
    inside = _ortho_hull(walls, max(3, int(1.0 * p)) | 1)
    k1 = max(3, int((2.4 if screened else 1.0) * p)) | 1     # screened: door landings / pads outside the walls go
    inside = cv2.morphologyEx(inside, cv2.MORPH_OPEN, np.ones((k1, k1), np.uint8))
    cnts, _ = cv2.findContours(inside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cn = max(cnts, key=cv2.contourArea)
    cn = cv2.approxPolyDP(cn, max(2.0, 0.1 * p), True)
    x, y, w, h = cv2.boundingRect(cn)
    mask = np.zeros_like(inside)
    cv2.drawContours(mask, [cn], -1, 1, -1)
    # zones: the outline cut by its own interior lines (isolation joints, slab edges, walls)
    kg = max(3, int(0.6 * p)) | 1                           # close small gaps along each separator
    sep = cv2.morphologyEx(seps, cv2.MORPH_CLOSE, np.ones((1, kg), np.uint8))
    sep = cv2.morphologyEx(sep, cv2.MORPH_CLOSE, np.ones((kg, 1), np.uint8))
    sep = cv2.dilate(sep, np.ones((3, 3), np.uint8)) & mask
    rest = (mask & (1 - sep)).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(rest, 4)
    zones = []
    for i in range(1, n):
        a_m2 = st[i][4] / p ** 2
        if a_m2 < 3.0:
            continue
        zc, _ = cv2.findContours((lab == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        z = cv2.approxPolyDP(max(zc, key=cv2.contourArea), max(2.0, 0.1 * p), True)
        zones.append({"polygon": [[float(px / s), float(py / s)] for px, py in z.reshape(-1, 2)],
                      "area_m2": round(float(a_m2), 2), "centroid": [float(cen[i][0] / s), float(cen[i][1] / s)]})
    zones.sort(key=lambda z: -z["area_m2"])
    return {"polygon": [[float(px / s), float(py / s)] for px, py in cn.reshape(-1, 2)],
            "area_m2": round(float(cv2.contourArea(cn) / p ** 2), 2), "bbox_m": [round(w / p, 2), round(h / p, 2)],
            "bbox_px": [x / s, y / s, (x + w) / s, (y + h) / s], "method": method, "screened": bool(screened),
            "zones": zones[:40]}


def subrooms(abs_path: str, sha: str, ppm: float, footprint: list, work: int = 4000) -> list[dict]:
    """Rooms INSIDE a building outline: free space enclosed by straight wall lines >= 1.2 m long (furniture, symbols and
    text are shorter or erased), door gaps up to ~1 m bridged along each wall. Returns [{polygon, area_m2, centroid}]
    in original px, each >= 2 m2 and smaller than 60% of the outline."""
    g0, _pdf = S.load_gray(abs_path, 2000)
    H0, W0 = g0.shape
    s = min(1.0, work / max(H0, W0))
    p = ppm * s
    dark0 = (g0 < 110).astype(np.uint8)
    grey0 = ((g0 >= 135) & (g0 <= 220) & (cv2.dilate(dark0, np.ones((5, 5), np.uint8)) == 0)).astype(np.uint8)
    c0 = cv2.imread(abs_path, cv2.IMREAD_COLOR) if not abs_path.lower().endswith(".pdf") else None
    if c0 is not None and c0.shape[:2] == g0.shape:
        grey0[cv2.cvtColor(c0, cv2.COLOR_BGR2HSV)[:, :, 1] > 30] = 0
    screened = grey0.sum() > 0.2 * dark0.sum() and grey0.sum() > 0.002 * grey0.size
    src = grey0 if screened else (g0 < 150).astype(np.uint8)
    ink = (cv2.resize(src * 255, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) > 40).astype(np.uint8) if s < 1 else src
    for w in T.words(abs_path, sha):
        a, b, c, d = [int(v * s) for v in w["box"]]
        ink[max(0, b - 1):d + 2, max(0, a - 1):c + 2] = 0
    mask = np.zeros_like(ink)
    cv2.fillPoly(mask, [(np.array(footprint, np.float32) * s).astype(np.int32)], 1)
    lmin = max(8, int(1.2 * p))
    walls = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, lmin), np.uint8)) | \
        cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((lmin, 1), np.uint8))
    kg = max(3, int(1.0 * p)) | 1
    walls = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, np.ones((1, kg), np.uint8)) | \
        cv2.morphologyEx(walls, cv2.MORPH_CLOSE, np.ones((kg, 1), np.uint8))
    edge = mask - cv2.erode(mask, np.ones((3, 3), np.uint8))
    free = (mask & (1 - cv2.dilate(walls | edge, np.ones((3, 3), np.uint8)))).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(free, 4)
    total = float(mask.sum())
    out = []
    for i in range(1, n):
        a_px = float(st[i][4])
        a_m2 = a_px / p ** 2
        if a_m2 < 2.0 or a_px > 0.97 * total:          # only a copy of the outline itself is not a room
            continue
        x, y, bw, bh = st[i][:4]
        if min(bw, bh) < 0.8 * p:                      # a sliver between two parallel lines (wall core), not a room
            continue
        cs, _ = cv2.findContours((lab == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = cv2.approxPolyDP(max(cs, key=cv2.contourArea), max(1.5, 0.08 * p), True)
        if len(c) < 3:
            continue
        out.append({"polygon": [[float(px / s), float(py / s)] for px, py in c.reshape(-1, 2)],
                    "area_m2": round(a_m2, 2), "centroid": [float(cen[i][0] / s), float(cen[i][1] / s)]})
    return out
