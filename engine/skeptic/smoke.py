"""python -m engine.skeptic.smoke : 20 DEV images through every registered skeptic voter + triage samples."""
from __future__ import annotations

import math
import os
import random
import sys
import time

import cv2

from engine import registry
from engine.registry import Ctx
from evalkit.data import dataset_root, load_questions
from engine.triage.labels import labels

PER_IMAGE_BUDGET_S = 3.0


def _check_poly(el, w, h):
    assert len(el.polygon) >= 3, f"{el.id}: polygon has < 3 points"
    for x, y in el.polygon:
        assert math.isfinite(x) and math.isfinite(y), f"{el.id}: non-finite"
        assert -2 <= x <= w + 2 and -2 <= y <= h + 2, f"{el.id}: point ({x:.0f},{y:.0f}) outside {w}x{h}"


def main() -> int:
    registry.reset()
    registry.autodiscover()
    root = dataset_root()
    qs = [q for q in load_questions() if q.source == "cubicasa5k" and q.split == "dev" and q.type == "count"]
    rng = random.Random(7)
    by_path = {}
    for q in qs:
        by_path.setdefault(q.path, q)
    paths = sorted(by_path)
    rng.shuffle(paths)
    paths = paths[:20]
    fails = 0
    worst = 0.0
    n_vote = 0
    for p in paths:
        im = cv2.imread(str(root / p))
        h, w = im.shape[:2]
        t0 = time.time()
        for intent in ("doors", "windows"):
            ctx = Ctx(path=p, abs_path=str(root / p), question="", intent=intent, kind="count")
            for name, fn in registry.voters_for("count"):
                if not name.startswith(("doors_arc", "windows_lines", "fixtures", "rooms_ocr")):
                    continue
                vr = fn(ctx)
                if vr is None:
                    continue
                n_vote += 1
                try:
                    assert vr.voter.value is not None and vr.voter.value >= 0
                    assert len(vr.voter.element_ids) == len(vr.evidence) == vr.voter.value or vr.voter.name == "rooms_ocr"
                    for el in vr.evidence:
                        _check_poly(el, w, h)
                    assert vr.voter.note, "voter must carry an honest weakness note"
                except AssertionError as e:
                    fails += 1
                    print("FAIL", p, name, e)
        dt = time.time() - t0
        worst = max(worst, dt)
        if dt > PER_IMAGE_BUDGET_S:
            fails += 1
            print(f"FAIL {p}: {dt:.1f}s > {PER_IMAGE_BUDGET_S}s")
    print(f"voters: {len(paths)} images, {n_vote} voter outputs, slowest image {worst:.2f}s")
    # triage: thumbnail + elevation samples must be refused, a real plan must not be
    tri = registry.triagers()
    assert tri, "no triage registered"
    name, tfn = tri[0]
    refused = {}
    samples = []
    for folder in ("wikimedia", "europeana", "finna", "habs"):
        for f in sorted(os.listdir(root / "data" / folder)):
            if f.lower().endswith((".jpg", ".png", ".jpeg")):
                im = cv2.imread(str(root / "data" / folder / f))
                if im is not None and min(im.shape[:2]) < 150:
                    samples.append(("thumbnail", f"data/{folder}/{f}"))
    for folder, idx, lab in labels():
        if lab == "elevation" and len([s for s in samples if s[0] == "elevation"]) < 3:
            fs = sorted(f for f in os.listdir(root / "data" / folder) if f.lower().endswith((".jpg", ".png", ".jpeg")))
            samples.append(("elevation", f"data/{folder}/{fs[idx]}"))
    for kind, p in samples:
        r = tfn(Ctx(path=p, abs_path=str(root / p), question="", intent="doors"))
        refused.setdefault(kind, []).append(bool(r and r.refuse))
        print(f"triage {kind:9s} {p[-40:]:42s} refuse={bool(r and r.refuse)} {r.refuse if r and r.refuse else ''}"[:200])
    r = tfn(Ctx(path=paths[0], abs_path=str(root / paths[0]), question="", intent="doors"))
    assert r is not None and not r.refuse, "real plan was refused"
    if not all(refused.get("thumbnail", [False])):
        fails += 1
        print("FAIL: thumbnail not refused")
    print("elevation samples refused:", sum(refused.get("elevation", [])), "of", len(refused.get("elevation", [])))
    print("SMOKE", "OK" if fails == 0 else f"FAILED ({fails})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
