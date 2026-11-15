import cv2
import numpy as np

from engine.raster import stairs


def _plan(with_stairs: bool) -> np.ndarray:
    img = np.full((600, 800, 3), 255, np.uint8)
    # thick outer and inner walls, rooms without hatching
    cv2.rectangle(img, (20, 20), (780, 580), (0, 0, 0), 10)
    cv2.line(img, (400, 20), (400, 580), (0, 0, 0), 8)
    cv2.line(img, (20, 300), (400, 300), (0, 0, 0), 8)
    cv2.rectangle(img, (500, 400), (560, 440), (0, 0, 0), 2)   # a fixture box
    if with_stairs:
        x0, y0, w = 120, 80, 55          # tread ~5.5% of the diagonal
        cv2.rectangle(img, (x0, y0), (x0 + w, y0 + 8 * 22), (0, 0, 0), 2)   # stringers
        for i in range(8):
            y = y0 + 11 + i * 22
            cv2.line(img, (x0, y), (x0 + w, y), (0, 0, 0), 2)
    return img


def test_one_flight_found():
    got = stairs.detect(_plan(True))
    assert len(got) == 1
    f = got[0]
    assert f["kind"] == "stairs" and len(f["polygon"]) == 4
    assert f["attrs"]["treads"] >= 7
    xs = [p[0] for p in f["polygon"]]
    ys = [p[1] for p in f["polygon"]]
    assert 100 <= min(xs) and max(xs) <= 210 and 60 <= min(ys) and max(ys) <= 280


def test_no_stairs_in_plain_rooms():
    assert stairs.detect(_plan(False)) == []
