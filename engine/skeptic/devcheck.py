"""Quick per-voter, per-intent DEV accuracy loop (own; reads questions.jsonl). python -m engine.skeptic.devcheck --n 150"""
from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
import time

from evalkit.data import dataset_root, load_questions

# intent -> list of voter module names
VOTER_INTENTS = {
    "doors": ["doors_arc"],
    "windows": ["windows_lines"],
    "toilets": ["fixtures_template"],
    "sinks": ["fixtures_template"],
    "bedrooms": ["rooms_ocr"],
    "bathrooms": ["rooms_ocr"],
    "wc_rooms": ["rooms_ocr"],
    "kitchens": ["rooms_ocr"],
    "saunas": ["rooms_ocr"],
    "balconies": ["rooms_ocr"],
    "floors": ["rooms_ocr"],
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--intent", default=None)
    ap.add_argument("--voter", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    qs = [q for q in load_questions() if q.source == "cubicasa5k" and q.split == "dev" and q.type == "count"]
    root = dataset_root()
    rng = random.Random(7)
    by = {}
    for q in qs:
        by.setdefault(q.intent, []).append(q)
    res = {}
    for intent, voters in VOTER_INTENTS.items():
        if a.intent and intent != a.intent:
            continue
        rows = by.get(intent, [])
        rng.shuffle(rows)
        rows = rows[: a.n]
        for vn in voters:
            if a.voter and vn != a.voter:
                continue
            mod = importlib.import_module(f"engine.skeptic.voters.{vn}")
            ok = n = ab = 0
            t0 = time.time()
            errs = []
            for q in rows:
                try:
                    v = mod.count_for(str(root / q.path), intent) if hasattr(mod, "count_for") else mod.count(str(root / q.path))[0]
                except Exception as e:  # noqa: BLE001
                    v = None
                    errs.append(repr(e)[:80])
                n += 1
                ab += int(v is None)
                ok += int(v is not None and int(v) == int(q.answer))
                res.setdefault(f"{vn}/{intent}", []).append((q.path, q.answer, v))
            print(f"{vn:20s} {intent:14s} n={n:4d} acc_all={ok / max(n, 1):.3f} answered={n - ab} acc_answered={ok / max(n - ab, 1):.3f} "
                  f"{(time.time() - t0) / max(n, 1):.2f}s/img errs={len(errs)} {errs[:1]}")
            sys.stdout.flush()
    if a.json:
        json.dump(res, open(a.json, "w"))


if __name__ == "__main__":
    main()
