"""Confusion table for triage. python -m engine.triage.eval [--cubicasa 241] [--no-ocr]

Rows = hand label (engine/triage/labels.py; cubicasa images are floor_plan), columns = triage outcome
(answer / refuse:<rule>). Reports false refusals on cubicasa floor plans and recall on refuse-classes.
"""
from __future__ import annotations

import argparse
import collections
import os

from evalkit.data import dataset_root
from engine.triage import rules
from engine.triage.labels import labels

REFUSE_CLASSES = {"elevation", "section", "detail", "not_a_plan"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cubicasa", type=int, default=241)
    ap.add_argument("--no-ocr", action="store_true")
    a = ap.parse_args(argv)
    root = dataset_root()
    items = []
    cub = sorted(f for f in os.listdir(root / "data" / "cubicasa5k") if f.lower().endswith(".png"))[: a.cubicasa]
    items += [(str(root / "data/cubicasa5k" / f), "floor_plan", "cubicasa5k") for f in cub]
    for folder, idx, lab in labels():
        fs = sorted(f for f in os.listdir(root / "data" / folder) if f.lower().endswith((".jpg", ".png", ".jpeg")))
        items.append((str(root / "data" / folder / fs[idx]), lab, folder))
    import cv2
    for folder in ("wikimedia", "europeana", "finna", "habs"):          # every thumbnail (< 150 px) is a refuse-class sample
        for f in sorted(os.listdir(root / "data" / folder)):
            if f.lower().endswith((".jpg", ".png", ".jpeg")):
                im = cv2.imread(str(root / "data" / folder / f))
                if im is not None and min(im.shape[:2]) < 150:
                    items.append((str(root / "data" / folder / f), "not_a_plan", folder))
    conf = collections.defaultdict(collections.Counter)
    fr_cub = fr_other_plan = 0
    n_other_plan = 0
    for path, lab, src in items:
        r = rules.classify(path, use_ocr=not a.no_ocr)
        out = f"refuse:{r['rule']}" if r["refuse"] else "answer"
        conf[lab][out] += 1
        if lab == "floor_plan" and src == "cubicasa5k" and r["refuse"]:
            fr_cub += 1
        if lab in ("floor_plan", "multi_view", "site_plan") and src != "cubicasa5k":
            n_other_plan += 1
            fr_other_plan += int(bool(r["refuse"]))
    cols = sorted({c for v in conf.values() for c in v})
    print("label".ljust(14) + "".join(c.ljust(20) for c in cols))
    for lab in sorted(conf):
        print(lab.ljust(14) + "".join(str(conf[lab][c]).ljust(20) for c in cols))
    tp = sum(v for lab in REFUSE_CLASSES for c, v in conf[lab].items() if c != "answer")
    tot = sum(sum(conf[lab].values()) for lab in REFUSE_CLASSES)
    ncub = sum(conf["floor_plan"].values()) - sum(1 for _, l, s in items if l == "floor_plan" and s != "cubicasa5k")
    print(f"\nrefuse-class recall (elevation/section/detail/not_a_plan): {tp}/{tot} = {tp / max(tot, 1):.2f}")
    print(f"false refusals on cubicasa floor plans: {fr_cub}/{len(cub)} = {fr_cub / max(len(cub), 1):.3%}")
    print(f"false refusals on other-folder floor_plan/multi_view/site_plan: {fr_other_plan}/{n_other_plan}")


if __name__ == "__main__":
    main()
