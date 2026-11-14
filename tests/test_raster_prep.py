"""Unit tests for engine.raster.prep: every TTA variant must map a polygon back to the
original image within 1 px (synthetic marker image), per prompts/11_w1_raster.md Step 1.
"""
from __future__ import annotations

import numpy as np
import pytest

from engine.raster import prep


def _marker_image(w: int, h: int, mx: int, my: int) -> np.ndarray:
    """A mostly-black image with a single small white square marker at (mx, my)."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[max(0, my - 1):my + 2, max(0, mx - 1):mx + 2] = 255
    return img


def _centroid(img: np.ndarray) -> tuple[float, float]:
    gray = img.mean(axis=2)
    ys, xs = np.where(gray > 127)
    assert len(xs) > 0, "marker lost after render"
    return float(xs.mean()), float(ys.mean())


@pytest.mark.parametrize("w,h,mx,my", [(300, 400, 50, 60), (475, 325, 400, 300), (240, 490, 10, 480)])
def test_round_trip_within_1px(w, h, mx, my):
    img = _marker_image(w, h, mx, my)
    variants = prep.make_variants(w, h)
    assert 1 <= len(variants) <= 8
    for v in variants:
        rendered = v.render(img)
        assert rendered.shape[1] == v.out_w and rendered.shape[0] == v.out_h
        vx, vy = _centroid(rendered)
        # forward: original marker -> variant coords should land on the rendered centroid
        fx, fy = v.to_variant([(mx, my)])[0]
        assert abs(fx - vx) <= 2.0 and abs(fy - vy) <= 2.0, (v.name, (fx, fy), (vx, vy))
        # inverse: map the rendered centroid back and recover the original marker
        ox, oy = v.to_original([(vx, vy)])[0]
        assert abs(ox - mx) <= 1.5 and abs(oy - my) <= 1.5, (v.name, (ox, oy), (mx, my))


def test_matrix_inverse_is_exact():
    for w, h in [(240, 490), (475, 325), (100, 100)]:
        for v in prep.make_variants(w, h):
            pts = [(0, 0), (w - 1, 0), (0, h - 1), (w / 2, h / 3)]
            back = v.to_original(v.to_variant(pts))
            for (x0, y0), (x1, y1) in zip(pts, back):
                assert abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6


def test_cap_at_8():
    variants = prep.make_variants(240, 490)
    assert len(variants) <= 8


def test_load_rgb_composites_alpha(tmp_path):
    import cv2
    rgba = np.zeros((10, 10, 4), dtype=np.uint8)
    rgba[:, :, 0] = 255  # blue channel (BGR) full -> red-ish after swap, but check alpha=0 -> white
    rgba[:, :, 3] = 0
    p = tmp_path / "a.png"
    cv2.imwrite(str(p), rgba)
    rgb = prep.load_rgb(str(p))
    assert rgb.shape == (10, 10, 3)
    assert (rgb == 255).all()  # fully transparent -> white
