"""Preprocessing + test-time-augmentation (TTA) variant generation for raster floor plans.

Every variant carries an exact 3x3 homogeneous matrix `M` mapping a point in the
ORIGINAL image (pixels, x right, y down, origin top-left) to the variant's pixel
grid, and `Minv` for the reverse. Composition order (applied to the ORIGINAL image):
  1. uniform scale by `scale`                      S
  2. rotate by `k*90` degrees (cv2.rotate semantics) Rk
  3. horizontal flip if `flip`                      F
M = F @ Rk @ S, applied to homogeneous column vectors [x, y, 1]^T.

`engine.raster.extract` renders each variant, runs the model/CV on it, then uses
`Minv` to bring every detected polygon back to ORIGINAL pixel coordinates before
building `Element`s -- so all evidence geometry in SheetFacts is in the coordinate
system of the file on disk, never a resized/rotated copy.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

Point = tuple[float, float]

# cv2.rotate codes indexed by k (quarter turns, clockwise)
_CV_ROTATE = {0: None, 1: cv2.ROTATE_90_CLOCKWISE, 2: cv2.ROTATE_180, 3: cv2.ROTATE_90_COUNTERCLOCKWISE}


def load_rgb(path: str) -> np.ndarray:
    """Load an image, composite any alpha channel onto white, return HxWx3 uint8 RGB."""
    data = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if data is None:
        raise FileNotFoundError(f"could not read image: {path}")
    if data.ndim == 2:
        rgb = cv2.cvtColor(data, cv2.COLOR_GRAY2RGB)
        return rgb
    if data.shape[2] == 4:
        bgr = data[:, :, :3].astype(np.float32)
        alpha = data[:, :, 3:4].astype(np.float32) / 255.0
        white = np.full_like(bgr, 255.0)
        comp = bgr * alpha + white * (1 - alpha)
        rgb = cv2.cvtColor(comp.astype(np.uint8), cv2.COLOR_BGR2RGB)
        return rgb
    rgb = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)
    return rgb


@dataclass
class Variant:
    scale: float
    k: int            # quarter turns clockwise: 0, 1, 2, 3
    flip: bool         # horizontal flip, applied after rotation
    src_w: int         # original image width/height (pre-scale)
    src_h: int
    out_w: int         # rendered variant width/height
    out_h: int
    M: np.ndarray      # 3x3, original -> variant
    Minv: np.ndarray   # 3x3, variant -> original

    @property
    def name(self) -> str:
        flip_s = "f" if self.flip else "n"
        return f"s{self.scale:.2g}_r{self.k * 90}_{flip_s}"

    def render(self, img: np.ndarray) -> np.ndarray:
        """Apply this variant's transform to an ORIGINAL-sized image array."""
        if self.scale != 1.0:
            w = max(1, round(self.src_w * self.scale))
            h = max(1, round(self.src_h * self.scale))
            interp = cv2.INTER_LANCZOS4 if self.scale > 1 else cv2.INTER_AREA
            img = cv2.resize(img, (w, h), interpolation=interp)
        code = _CV_ROTATE[self.k]
        if code is not None:
            img = cv2.rotate(img, code)
        if self.flip:
            img = cv2.flip(img, 1)
        return img

    def to_variant(self, pts: list[Point]) -> list[Point]:
        return _apply(self.M, pts)

    def to_original(self, pts: list[Point]) -> list[Point]:
        return _apply(self.Minv, pts)


def _apply(mat: np.ndarray, pts: list[Point]) -> list[Point]:
    if not pts:
        return []
    arr = np.asarray(pts, dtype=np.float64)
    ones = np.ones((arr.shape[0], 1))
    hom = np.hstack([arr, ones])
    out = (mat @ hom.T).T
    return [(float(x), float(y)) for x, y in out[:, :2]]


def _scale_matrix(s: float) -> np.ndarray:
    return np.array([[s, 0, 0], [0, s, 0], [0, 0, 1]], dtype=np.float64)


def _rotate_matrix(k: int, wc: float, hc: float) -> np.ndarray:
    """Rotate k quarter-turns clockwise (cv2.rotate semantics). wc,hc = dims BEFORE this rotation."""
    k = k % 4
    if k == 0:
        return np.eye(3)
    if k == 1:  # 90 CW: new_x = hc - y, new_y = x
        return np.array([[0, -1, hc], [1, 0, 0], [0, 0, 1]], dtype=np.float64)
    if k == 2:  # 180: new_x = wc - x, new_y = hc - y
        return np.array([[-1, 0, wc], [0, -1, hc], [0, 0, 1]], dtype=np.float64)
    # k == 3: 90 CCW: new_x = y, new_y = wc - x
    return np.array([[0, 1, 0], [-1, 0, wc], [0, 0, 1]], dtype=np.float64)


def _flip_matrix(w_final: float) -> np.ndarray:
    return np.array([[-1, 0, w_final], [0, 1, 0], [0, 0, 1]], dtype=np.float64)


def make_variant(src_w: int, src_h: int, scale: float, k: int, flip: bool) -> Variant:
    wc, hc = src_w * scale, src_h * scale
    S = _scale_matrix(scale)
    Rk = _rotate_matrix(k, wc, hc)
    rotated_w, rotated_h = (hc, wc) if k % 2 == 1 else (wc, hc)
    F = _flip_matrix(rotated_w) if flip else np.eye(3)
    M = F @ Rk @ S
    Minv = np.linalg.inv(M)
    out_w, out_h = round(rotated_w), round(rotated_h)
    return Variant(scale=scale, k=k, flip=flip, src_w=src_w, src_h=src_h,
                   out_w=out_w, out_h=out_h, M=M, Minv=Minv)


def make_variants(src_w: int, src_h: int, *, cap: int = 8, target_long_side: float = 800.0) -> list[Variant]:
    """Scales {1.0, 1.5 if small} x rotations {0,90,180,270} x flip {no,yes}, capped at `cap`.

    cubicasa5k images are mostly 240-490 px (docs/recon.md) but a handful of outliers are much
    larger (observed up to 1715x1441): the long side is rescaled TOWARD `target_long_side` in
    both directions -- upscaled for the small/typical case so the pretrained model (trained on
    larger crops) and OCR see enough detail, downscaled for the rare large outlier so a single
    CNN forward pass stays inside the per-image CPU budget (docs/decisions/weights.md; a 1715px
    image at scale 1.0 took ~9.8s on this CPU, vs ~2s at the capped scale).
    """
    long_side = max(src_w, src_h)
    base_scale = target_long_side / long_side
    scales = [base_scale]
    if long_side * base_scale < 700:  # still small after the base upscale: add a second, larger scale
        scales.append(base_scale * 1.5)

    combos: list[tuple[float, int, bool]] = []
    for s in scales:
        for k in (0, 1, 2, 3):
            for flip in (False, True):
                combos.append((s, k, flip))

    if len(combos) > cap:
        idx = np.linspace(0, len(combos) - 1, cap).round().astype(int)
        seen = set()
        picked = []
        for i in idx:
            if i not in seen:
                seen.add(i)
                picked.append(combos[i])
        combos = picked

    return [make_variant(src_w, src_h, s, k, flip) for s, k, flip in combos]
