"""Dev loop for the vector plugin: accuracy per source and intent (Wilson CI), seconds per file, worst failures.

    .venv/bin/python -m engine.vector.devcheck --source ifc_models [--no-siblings] [--related] [--split dev]

Reads questions.jsonl through evalkit.data (DEV split = sha1(path) % 5 != 0). Never tune on --split holdout.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
import time

from evalkit.data import load_questions
from evalkit.score import score, wilson_str
from engine import registry
from engine.vector import plugin


def _truth(q):
    a = q.answer
    if isinstance(a, str):
        try:
            return float(a.split()[0].replace(",", "."))
        except ValueError:
            return a
    return a


def run(source: str | None, split: str, allow_siblings: bool, related: bool, limit: int | None = None,
        intents: set | None = None, quiet: bool = False):
    if related:
        os.environ["PLUMB_RELATED"] = "1"
    else:
        os.environ.pop("PLUMB_RELATED", None)
    qs = [q for q in load_questions() if (source is None or q.source == source)
          and (split == "all" or q.split == split) and q.type in ("count", "area", "length", "volume")]
    if intents:
        qs = [q for q in qs if q.intent in intents]
    if limit:
        qs = qs[:limit]
    by = collections.defaultdict(lambda: [0, 0, 0, 0, 0])   # n, answered, correct, green, green_correct
    fails = []
    per_file = collections.defaultdict(float)
    for q in qs:
        ctx = registry.Ctx(path=q.path, abs_path="", question=q.question, intent=q.intent, params=q.params,
                           kind=q.type, lang=q.lang, allow_siblings=allow_siblings)
        t0 = time.time()
        vals = []
        for fn in (plugin.voter_primary, plugin.voter_second, plugin.voter_third):
            vr = fn(ctx)
            if vr is not None and vr.voter.value is not None:
                vals.append(vr.voter.value)
        per_file[q.path] += time.time() - t0
        key = (q.source, q.intent)
        r = by[key]
        r[0] += 1
        if not vals:
            fails.append((q.path, q.intent, q.question[:80], q.answer, None))
            continue
        r[1] += 1
        ok = score(q.type, vals[0], _truth(q))
        r[2] += ok
        green = len(vals) > 1 and any(score(q.type, v, vals[0]) for v in vals[1:])
        r[3] += green
        r[4] += green and ok
        if not ok:
            fails.append((q.path, q.intent, q.question[:80], q.answer, vals))
    tot = [0, 0, 0, 0, 0]
    print(f"source={source} split={split} siblings={'on' if allow_siblings else 'OFF'} related={'on' if related else 'off'}")
    print(f"{'source/intent':46s} {'n':>5s} {'ans':>5s} {'acc (CI)':>26s} {'green':>6s} {'green acc':>10s}")
    for (s, i), r in sorted(by.items()):
        print(f"{s + '/' + i:46s} {r[0]:5d} {r[1]:5d} {wilson_str(r[2], r[0]):>26s} {r[3]:6d} "
              f"{(r[4] / r[3] if r[3] else float('nan')):10.3f}")
        for k in range(5):
            tot[k] += r[k]
    print(f"{'TOTAL':46s} {tot[0]:5d} {tot[1]:5d} {wilson_str(tot[2], tot[0]):>26s} {tot[3]:6d} "
          f"{(tot[4] / tot[3] if tot[3] else float('nan')):10.3f}")
    if per_file:
        tt = sorted(per_file.values())
        print(f"files {len(tt)}; seconds per file: median {tt[len(tt) // 2]:.2f} max {tt[-1]:.2f} total {sum(tt):.1f}")
    if not quiet:
        print("worst failures (path, intent, question, truth, predicted):")
        for f in fails[:15]:
            print("  ", f)
    return by, fails


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None)
    ap.add_argument("--split", default="dev", choices=["dev", "holdout", "all"])
    ap.add_argument("--no-siblings", action="store_true")
    ap.add_argument("--related", action="store_true", help="opt-in: model-level IFC for per-storey sheets (own number)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--intent", action="append", default=None)
    a = ap.parse_args(argv)
    run(a.source, a.split, not a.no_siblings, a.related, a.limit, set(a.intent) if a.intent else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
