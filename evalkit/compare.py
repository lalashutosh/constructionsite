"""python -m evalkit.compare <run_a> <run_b>

Prints per-intent accuracy deltas between two evalkit/out/<run> directories and lists regressions.
"""
from __future__ import annotations

import argparse
import collections

from evalkit.audit import load_results


def per_intent_acc(rows: list[dict]) -> dict[str, tuple[int, int]]:
    by = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        if r.get("error") is not None:
            continue
        by[r["intent"]][1] += 1
        by[r["intent"]][0] += int(r["correct"])
    return {k: (v[0], v[1]) for k, v in by.items()}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run_a")
    p.add_argument("run_b")
    args = p.parse_args(argv)

    a = per_intent_acc(load_results(args.run_a))
    b = per_intent_acc(load_results(args.run_b))

    print(f"{'intent':30} {'A acc (n)':18} {'B acc (n)':18} delta")
    regressions = []
    for name in sorted(set(a) | set(b)):
        ak, an = a.get(name, (0, 0))
        bk, bn = b.get(name, (0, 0))
        aacc = ak / an if an else None
        bacc = bk / bn if bn else None
        delta = (bacc - aacc) if (aacc is not None and bacc is not None) else None
        a_s = f"{aacc:.1%} ({an})" if aacc is not None else "n/a"
        b_s = f"{bacc:.1%} ({bn})" if bacc is not None else "n/a"
        d_s = f"{delta:+.1%}" if delta is not None else "n/a"
        print(f"{name:30} {a_s:18} {b_s:18} {d_s}")
        if delta is not None and delta < -0.02:
            regressions.append((name, delta))

    print("\nregressions (B worse than A by > 2pp):")
    for name, delta in sorted(regressions, key=lambda t: t[1]):
        print(f"  {name}: {delta:+.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
