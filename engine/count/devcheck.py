"""python -m engine.count.devcheck --n 150

Runs engine.raster.extract + engine.count.count on a random DEV sample of cubicasa5k's 12 count
intents (English questions only -- non-English rows are the same drawings, scored separately
elsewhere), prints per-intent exact-match accuracy next to the per-intent DEV median baseline
("prior"), and writes overlay PNGs for the worst failures to docs/shots/raster/devcheck/.

Reports TWO accuracy numbers (prompts/11_w1_raster.md Step 0.3 / AGENTS.md): all DEV images, and
only the "clean" subset NOT in the pretrained model's own TRAIN split (engine.raster.leakage) --
the honest number. Also writes docs/claims/raster.json with {"clean_acc": ...}.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random
import statistics
import time
import traceback

import cv2
import numpy as np

from engine.count import count as count_fn
from engine.raster import extract as extract_mod
from engine.raster import leakage
from engine.raster import prep
from evalkit.data import dataset_root, load_questions

SEED = 7
INTENTS = ("windows", "floors", "toilets", "sinks", "showers_baths", "doors", "saunas",
           "kitchens", "bedrooms", "wc_rooms", "bathrooms", "balconies")
HERE = pathlib.Path(__file__).resolve().parents[2]
SHOTS_DIR = HERE / "docs" / "shots" / "raster" / "devcheck"
CLAIMS_PATH = HERE / "docs" / "claims" / "raster.json"


def _dev_cubicasa_en(questions):
    return [q for q in questions
            if q.source == "cubicasa5k" and q.split == "dev" and q.lang == "en" and q.intent in INTENTS]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--shots", type=int, default=20)
    args = ap.parse_args()

    root = dataset_root()
    all_q = load_questions()
    pool = _dev_cubicasa_en(all_q)

    # Per-intent DEV median baseline, fit on the WHOLE dev pool (not just the sample we score) so
    # the prior isn't accidentally tuned on the same rows it's being compared against.
    by_intent = collections.defaultdict(list)
    for q in pool:
        by_intent[q.intent].append(float(q.answer))
    median = {k: statistics.median(v) for k, v in by_intent.items()}

    rng = random.Random(SEED)
    sample = list(pool)
    rng.shuffle(sample)
    sample = sample[: args.n]

    correct = collections.Counter()
    correct_clean = collections.Counter()
    prior_correct = collections.Counter()
    total = collections.Counter()
    total_clean = collections.Counter()
    times = []
    failures = []  # (abs_delta, q, value, element_ids, abs_path)
    n_mapped = 0

    for q in sample:
        abs_path = str(root / q.path)
        t0 = time.time()
        try:
            facts = extract_mod.extract(abs_path)
            value, elem_ids, runs = count_fn(q.intent, facts)
        except Exception:
            traceback.print_exc()
            value, elem_ids, runs = None, [], []
        dt = time.time() - t0
        times.append(dt)

        total[q.intent] += 1
        truth = int(q.answer)
        ok = value is not None and int(round(value)) == truth
        if ok:
            correct[q.intent] += 1

        clean = leakage.is_clean(q.path)
        if clean is not None:
            n_mapped += 1
            if clean:
                total_clean[q.intent] += 1
                if ok:
                    correct_clean[q.intent] += 1

        prior_val = median.get(q.intent)
        if prior_val is not None and int(round(prior_val)) == truth:
            prior_correct[q.intent] += 1

        if not ok:
            delta = abs((value if value is not None else -999) - truth)
            failures.append((delta, q, value, elem_ids, abs_path))

    _print_table(total, correct, prior_correct)
    print()
    if n_mapped == 0:
        print("leakage mapping unavailable (weights/_splits missing): clean subset = null")
        clean_acc = None
    else:
        _print_table(total_clean, correct_clean, {}, header="CLEAN subset (not in model TRAIN split)")
        n_clean = sum(total_clean.values())
        clean_acc = (sum(correct_clean.values()) / n_clean) if n_clean else None
        print(f"clean images scored: {n_clean} / {sum(total.values())} "
              f"({n_clean / max(1, sum(total.values())) * 100:.0f}%)")

    if times:
        print(f"\nmedian {statistics.median(times):.2f}s/image, max {max(times):.2f}s, n={len(times)}")

    failures.sort(key=lambda t: -t[0])
    _write_overlays(failures[: args.shots], root)

    CLAIMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLAIMS_PATH.write_text(json.dumps({"clean_acc": clean_acc}, indent=2))
    return 0


def _print_table(total, correct, prior_correct, header="ALL dev images"):
    print(header)
    print(f"{'intent':<14}{'n':>5}{'ours':>8}{'prior':>8}")
    tn = to = tp = 0
    for intent in INTENTS:
        n = total.get(intent, 0)
        if n == 0:
            continue
        acc = correct.get(intent, 0) / n
        line = f"{intent:<14}{n:>5}{acc * 100:>7.1f}%"
        if prior_correct:
            pacc = prior_correct.get(intent, 0) / n
            line += f"{pacc * 100:>7.1f}%"
            tp += prior_correct.get(intent, 0)
        print(line)
        tn += n
        to += correct.get(intent, 0)
    if tn:
        line = f"{'TOTAL':<14}{tn:>5}{to / tn * 100:>7.1f}%"
        if prior_correct:
            line += f"{tp / tn * 100:>7.1f}%"
        print(line)


def _write_overlays(failures, root):
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    for i, (delta, q, value, elem_ids, abs_path) in enumerate(failures):
        try:
            img = prep.load_rgb(abs_path)
            facts = extract_mod.extract(abs_path)
        except Exception:
            continue
        vis = img.copy()
        wanted = set(elem_ids)
        for e in facts.elements:
            if elem_ids and e.id not in wanted:
                continue
            pts = np.array(e.polygon, dtype=np.int32)
            if len(pts) >= 3:
                cv2.polylines(vis, [pts], True, (0, 0, 255), 1)
        h, w = vis.shape[:2]
        if max(h, w) > 1000:
            s = 1000.0 / max(h, w)
            vis = cv2.resize(vis, (round(w * s), round(h * s)))
        name = f"{i:02d}_{q.intent}_got{value}_want{q.answer}_{pathlib.Path(q.path).stem}.png"
        cv2.imwrite(str(SHOTS_DIR / name), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))


if __name__ == "__main__":
    raise SystemExit(main())
