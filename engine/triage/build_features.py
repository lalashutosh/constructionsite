"""Compute triage features for labelled images and cache to cache/triage/features.jsonl (dev tool).

Positives: cubicasa images (DEV split by path hash, so the triage tree never sees HOLDOUT paths).
Negatives/others: hand-labelled europeana/finna/habs/wikimedia images (engine/triage/labels.py).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

from evalkit.data import dataset_root, split_of
from engine.triage import features
from engine.triage.labels import labels

OUT = pathlib.Path("cache/triage/features.jsonl")


def main():
    root = dataset_root()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        done = {json.loads(l)["path"] for l in OUT.open()}
    items = []
    for f in sorted(os.listdir(root / "data" / "cubicasa5k")):
        if f.lower().endswith(".png"):
            p = f"data/cubicasa5k/{f}"
            items.append((p, "floor_plan", "cubicasa5k", split_of(p)))
    for folder, idx, lab in labels():
        fs = sorted(f for f in os.listdir(root / "data" / folder) if f.lower().endswith((".jpg", ".png", ".jpeg")))
        p = f"data/{folder}/{fs[idx]}"
        items.append((p, lab, folder, "dev"))
    with OUT.open("a") as fo:
        for p, lab, src, split in items:
            if p in done:
                continue
            f = features.compute(str(root / p))
            f.update(path=p, label=lab, source=src, split=split)
            fo.write(json.dumps(f) + "\n")
            fo.flush()
    print("rows", sum(1 for _ in OUT.open()))


if __name__ == "__main__":
    main()
