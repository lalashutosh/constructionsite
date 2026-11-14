"""python -m evalkit.audit [--run latest] [--intent doors] [--wrong-only] [--n 20]

Prints path, truth, prediction, tier from a results.jsonl so extractor agents can inspect failures.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

OUT_ROOT = Path(__file__).resolve().parent / "out"


def load_results(run: str) -> list[dict]:
    run_dir = OUT_ROOT / run
    f = run_dir / "results.jsonl"
    if not f.exists():
        raise FileNotFoundError(f"{f} not found")
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", default="latest")
    p.add_argument("--intent", default=None)
    p.add_argument("--source", default=None)
    p.add_argument("--wrong-only", action="store_true")
    p.add_argument("--n", type=int, default=20)
    args = p.parse_args(argv)

    rows = load_results(args.run)
    if args.intent:
        rows = [r for r in rows if r["intent"] == args.intent]
    if args.source:
        rows = [r for r in rows if r["source"] == args.source]
    if args.wrong_only:
        rows = [r for r in rows if not r["correct"]]

    for r in rows[: args.n]:
        pred = r["po"]["value"] if r.get("po") else None
        tier = r.get("tier")
        print(f"{r['path']}\ttruth={r['truth']}\tpred={pred}\ttier={tier}\tintent={r['intent']}\t{r['question'][:80]}")
    print(f"\n{len(rows)} matching rows (showing up to {args.n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
