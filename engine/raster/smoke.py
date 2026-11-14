"""python -m engine.raster.smoke: extract() on 20 cubicasa5k images (seed 7), writes debug
overlays to docs/shots/raster/smoke/ (downscaled to <= 1000px), prints per-image timing.
Exit 0 iff every image extracts without raising. The <2s/image target is best-effort on this CPU --
see docs/decisions/weights.md for the measured number and why the heavy model only runs once.
"""
from __future__ import annotations

import random
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from engine.raster import extract as extract_mod
from engine.raster import prep
from evalkit.data import dataset_root, load_questions

SEED = 7
OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "shots" / "raster" / "smoke"

_COLORS = {
    "window": (255, 200, 0), "door": (0, 0, 255), "toilet": (0, 255, 0), "sink": (255, 255, 0),
    "bath": (255, 0, 255), "sauna_bench": (0, 128, 255), "fireplace": (128, 0, 0),
    "closet": (160, 160, 160), "appliance": (0, 180, 180), "chimney": (90, 60, 0),
    "room": (0, 160, 0), "bedroom": (0, 160, 0), "kitchen": (255, 140, 0),
    "bathroom": (0, 160, 160), "wc": (0, 90, 220), "sauna": (200, 0, 200), "balcony": (0, 200, 0),
    "living": (160, 200, 0), "label": (120, 120, 120),
}


def _overlay(img_rgb: np.ndarray, elements, out_path: Path) -> None:
    vis = img_rgb.copy()
    for e in elements:
        color = _COLORS.get(e.subtype or "", _COLORS.get(e.kind, (200, 200, 200)))
        pts = np.array(e.polygon, dtype=np.int32)
        if len(pts) >= 3:
            cv2.polylines(vis, [pts], True, color, 1)
        elif len(pts) == 2:
            cv2.line(vis, tuple(pts[0]), tuple(pts[1]), color, 1)
        if pts.size and (e.subtype or e.label):
            x, y = pts[0]
            text = (e.label or e.subtype or "")[:10]
            cv2.putText(vis, text, (int(x), max(10, int(y) - 2)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
    h, w = vis.shape[:2]
    if max(h, w) > 1000:
        s = 1000.0 / max(h, w)
        vis = cv2.resize(vis, (round(w * s), round(h * s)))
    cv2.imwrite(str(out_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))


def main() -> int:
    root = dataset_root()
    qs = [q for q in load_questions() if q.source == "cubicasa5k"]
    paths = sorted({q.path for q in qs})
    rng = random.Random(SEED)
    rng.shuffle(paths)
    sample = paths[:20]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    times: list[float] = []
    ok = True
    for p in sample:
        abs_path = str(root / p)
        t0 = time.time()
        try:
            facts = extract_mod.extract(abs_path)
        except Exception as e:  # noqa: BLE001 - smoke must report every failure, never half-crash
            print(f"FAIL {p}: {e}", file=sys.stderr)
            ok = False
            continue
        dt = time.time() - t0
        times.append(dt)
        img = prep.load_rgb(abs_path)
        _overlay(img, facts.elements, OUT_DIR / (Path(p).stem + ".png"))
        print(f"{p}: {dt:.2f}s route={facts.extras.get('route')} elements={len(facts.elements)}")

    if times:
        print(f"median {statistics.median(times):.2f}s, max {max(times):.2f}s over {len(times)} images")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
