"""python -m evalkit.run --engine {stub,prior,pipeline} --split {dev,holdout,all} [--no-siblings]
                         [--limit N] [--sources a,b] [--workers N] [--tag name] [--hard]

Writes evalkit/out/<timestamp>-<tag>/{results.jsonl, report.md, report.json, claims.json} and
updates the evalkit/out/latest symlink. See prompts/10_w1_evaluator.md for the full spec.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import statistics
import subprocess
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from contracts import invariants
from contracts.proof import Cost, ProofObject, Provenance, SheetFacts, Tier
from evalkit import score as scoring
from evalkit.data import Q, dataset_root, load_questions, split_sizes
from evalkit.hard import load_hard_questions

SEED = 7
HERE = Path(__file__).resolve().parent
OUT_ROOT = HERE / "out"


# --------------------------------------------------------------------------------------
# The "prior" engine: evalkit's own honest floor, built from per-intent DEV medians.
# Never built from holdout. Mirrors the Engine protocol (analyze/ask) so run.py treats it
# exactly like engine.api.get_engine("stub"|"pipeline").
# --------------------------------------------------------------------------------------
class PriorEngine:
    name = "prior"

    def __init__(self, dev_questions: list[Q]):
        from evalkit import intents as intents_mod

        self._intent_kind = intents_mod
        by_intent: dict[str, list[float]] = collections.defaultdict(list)
        by_source_type: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
        by_type: dict[str, list[float]] = collections.defaultdict(list)
        for q in dev_questions:
            if q.type == "text":
                continue
            v = scoring._to_number(q.answer)
            if v is None:
                continue
            by_intent[q.intent].append(v)
            by_source_type[(q.source, q.type)].append(v)
            by_type[q.type].append(v)

        self.median_intent = {k: statistics.median(v) for k, v in by_intent.items()}
        self.median_source_type = {k: statistics.median(v) for k, v in by_source_type.items()}
        self.median_type = {k: statistics.median(v) for k, v in by_type.items()}
        self.n_fit = sum(len(v) for v in by_intent.values())

    def analyze(self, path: str, *, allow_siblings: bool = True) -> SheetFacts:
        return SheetFacts(provenance=Provenance(file=path), sheet_type="unknown")

    def ask(self, path: str, question: str, *, allow_siblings: bool = True, benchmark: bool = True) -> ProofObject:
        t0 = time.perf_counter()
        from evalkit import intents as intents_mod

        parts = path.split("/")
        source = parts[1] if len(parts) > 1 else "unknown"
        intent = intents_mod.classify(question, path)
        kind = _intent_kind_guess(intent.name) or "count"

        if intent.name in self.median_intent:
            value = self.median_intent[intent.name]
        elif (source, kind) in self.median_source_type:
            value = self.median_source_type[(source, kind)]
        elif kind in self.median_type:
            value = self.median_type[kind]
        else:
            value = 0

        if kind == "count":
            value = int(round(value))
        else:
            value = float(value)

        return ProofObject(
            id=f"prior-{abs(hash((path, question))) % 10**8}", question=question, intent=intent.name,
            kind=kind if kind in ("count", "area", "length", "volume", "text", "other") else "other",
            value=value, tier=Tier.amber, provenance=Provenance(file=path),
            notes=[f"prior engine: per-intent DEV median (n_fit={self.n_fit})"],
            cost=Cost(ms=(time.perf_counter() - t0) * 1000),
        )


_KIND_CACHE: dict[str, Optional[str]] = {}


def _intent_kind_guess(name: str) -> Optional[str]:
    if name in _KIND_CACHE:
        return _KIND_CACHE[name]
    from evalkit import intents as intents_mod

    kind = None
    for rule in intents_mod._rules():
        if rule.name == name:
            kind = rule.kind
            break
    _KIND_CACHE[name] = kind
    return kind


def build_engine(mode: str, dev_questions: list[Q]):
    if mode == "prior":
        return PriorEngine(dev_questions)
    from engine.api import get_engine  # evalkit never imports engine internals besides this

    return get_engine(mode)


# --------------------------------------------------------------------------------------
# Running questions through an engine
# --------------------------------------------------------------------------------------
def ask_one(engine, q: Q, allow_siblings: bool) -> dict:
    row: dict[str, Any] = {
        "path": q.path, "question": q.question, "truth": q.answer, "unit": q.unit, "type": q.type,
        "source": q.source, "lang": q.lang, "intent": q.intent, "params": q.params, "split": q.split,
        "error": None, "po": None, "correct": False, "tier": None,
    }
    t0 = time.perf_counter()
    try:
        po = engine.ask(q.path, q.question, allow_siblings=allow_siblings, benchmark=True)
        row["po"] = po.model_dump(mode="json")
        row["tier"] = po.tier.value if isinstance(po.tier, Tier) else po.tier
        row["correct"] = scoring.score(q.type, po.value, q.answer)
        row["violations"] = invariants.check(po)
    except Exception as exc:  # noqa: BLE001 - never let one bad question crash the run
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["violations"] = []
        row["_traceback"] = traceback.format_exc(limit=4)
    row["wall_ms"] = (time.perf_counter() - t0) * 1000
    return row


def run_questions(engine, questions: list[Q], allow_siblings: bool, workers: int) -> list[dict]:
    if workers <= 1 or len(questions) < 4:
        return [ask_one(engine, q, allow_siblings) for q in questions]

    # Process-pool path: only meaningful once a real (non-prior) engine exists; each worker
    # builds its own engine instance via engine.api.get_engine(mode) as required by the spec.
    from concurrent.futures import ProcessPoolExecutor

    mode = getattr(engine, "name", None) or "stub"
    chunks = [questions[i::workers] for i in range(workers)]
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_worker_run_chunk, mode, chunk, allow_siblings) for chunk in chunks if chunk]
        for fut in futures:
            results.extend(fut.result())
    return results


def _worker_run_chunk(mode: str, chunk: list[Q], allow_siblings: bool) -> list[dict]:
    from engine.api import get_engine

    eng = get_engine(mode)
    return [ask_one(eng, q, allow_siblings) for q in chunk]


# --------------------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------------------
def _acc(rows: list[dict]) -> tuple[int, int]:
    k = sum(1 for r in rows if r["correct"])
    return k, len(rows)


def aggregate(rows: list[dict], prior_rows: Optional[list[dict]] = None) -> dict:
    quantitative = [r for r in rows if r["type"] != "text" and r["error"] is None]
    text_rows = [r for r in rows if r["type"] == "text" and r["error"] is None]
    errored = [r for r in rows if r["error"] is not None]

    stats: dict[str, Any] = {}

    # (1) headline, by split
    for split in ("dev", "holdout"):
        sub = [r for r in quantitative if r["split"] == split]
        k, n = _acc(sub)
        stats[f"headline_{split}"] = {"k": k, "n": n, "ci": scoring.wilson(k, n)}
    k, n = _acc(quantitative)
    stats["headline_overall"] = {"k": k, "n": n, "ci": scoring.wilson(k, n)}
    tk, tn = _acc(text_rows)
    stats["headline_text"] = {"k": tk, "n": tn, "ci": scoring.wilson(tk, tn)}

    # (2) source x type
    st = collections.defaultdict(list)
    for r in rows:
        if r["error"] is None:
            st[(r["source"], r["type"])].append(r)
    stats["by_source_type"] = {
        f"{s}|{t}": {"k": (a := _acc(v))[0], "n": a[1], "ci": scoring.wilson(*a)} for (s, t), v in sorted(st.items())
    }

    # (3) per-intent, with prior baseline alongside
    prior_by_intent = collections.defaultdict(list)
    if prior_rows:
        for r in prior_rows:
            if r["error"] is None:
                prior_by_intent[r["intent"]].append(r)
    by_intent = collections.defaultdict(list)
    for r in rows:
        if r["error"] is None:
            by_intent[r["intent"]].append(r)
    intent_table = {}
    for name, v in sorted(by_intent.items()):
        k, n = _acc(v)
        prior_acc = None
        if name in prior_by_intent:
            pk, pn = _acc(prior_by_intent[name])
            prior_acc = pk / pn if pn else None
        intent_table[name] = {"k": k, "n": n, "ci": scoring.wilson(k, n), "prior_acc": prior_acc}
    stats["by_intent"] = intent_table

    # (4) tier calibration
    tiers = {"green": [], "amber": [], "grey": []}
    for r in quantitative + text_rows:
        t = r.get("tier")
        if t in tiers:
            tiers[t].append(r)
    n_total = len(quantitative) + len(text_rows)
    tier_table = {}
    for t, v in tiers.items():
        k, n = _acc(v)
        tier_table[t] = {"k": k, "n": n, "coverage": (n / n_total if n_total else 0.0), "ci": scoring.wilson(k, n)}
    stats["tier_table"] = tier_table

    rnd = random.Random(SEED)
    rank = {"green": 0, "amber": 1, "grey": 2}
    scored_rows = [r for r in quantitative + text_rows]
    scored_rows.sort(key=lambda r: (rank.get(r.get("tier"), 3), rnd.random()))
    coverage_curve = []
    for pct in range(10, 101, 10):
        take = max(1, round(len(scored_rows) * pct / 100)) if scored_rows else 0
        sub = scored_rows[:take]
        k, n = _acc(sub)
        coverage_curve.append({"coverage_pct": pct, "k": k, "n": n, "acc": (k / n if n else None)})
    stats["coverage_curve"] = coverage_curve

    # (5) cost
    costs = [r["po"]["cost"] for r in rows if r.get("po")]
    ms_list = [c["ms"] for c in costs] if costs else []
    tokens_total = sum(c["tokens_in"] + c["tokens_out"] for c in costs)
    usd_total = sum(c["usd"] for c in costs)
    llm_calls = sum(c["llm_calls"] for c in costs)
    planner_calls = sum(c["planner_calls"] for c in costs)

    by_path_ms: dict[str, list[float]] = collections.defaultdict(list)
    for r in rows:
        if r.get("po"):
            by_path_ms[r["path"]].append(r["po"]["cost"]["ms"])
    first_ms = [v[0] for v in by_path_ms.values() if v]
    marginal_ms = [x for v in by_path_ms.values() for x in v[1:]]

    def _pct(vals: list[float], p: float) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        idx = min(len(s) - 1, int(round(p * (len(s) - 1))))
        return s[idx]

    n_drawings = len(by_path_ms) or 1
    cpu_s_per_drawing = sum(first_ms) / 1000 / n_drawings if first_ms else 0.0
    stats["cost"] = {
        "mean_ms": statistics.mean(ms_list) if ms_list else 0.0,
        "median_ms": statistics.median(ms_list) if ms_list else 0.0,
        "p95_ms": _pct(ms_list, 0.95),
        "tokens_total": tokens_total, "usd_total": usd_total, "llm_calls": llm_calls,
        "planner_calls": planner_calls,
        "mean_first_of_drawing_ms": statistics.mean(first_ms) if first_ms else 0.0,
        "mean_marginal_ms": statistics.mean(marginal_ms) if marginal_ms else 0.0,
        "cpu_s_per_drawing_estimate": cpu_s_per_drawing,
        "cpu_s_per_14000_drawings_estimate": cpu_s_per_drawing * 14000,
    }

    # (6) failure buckets
    wrong = [r for r in quantitative if not r["correct"]]
    buckets = collections.defaultdict(int)
    for r in wrong:
        p, t = scoring._to_number(r["po"]["value"] if r.get("po") else None), scoring._to_number(r["truth"])
        direction = "over" if (p is not None and t is not None and p > t) else (
            "under" if (p is not None and t is not None and p < t) else "n/a")
        wpx = r["po"].get("notes") if r.get("po") else None
        width_bucket = "unknown"  # width_px not populated by stub/prior; real engine reports it via facts
        buckets[(r["source"], r["intent"], width_bucket, direction)] += 1
    stats["failure_buckets"] = {"|".join(k): v for k, v in sorted(buckets.items(), key=lambda kv: -kv[1])}

    # (7) random wrong examples
    rnd2 = random.Random(SEED)
    sample = rnd2.sample(wrong, min(20, len(wrong))) if wrong else []
    stats["wrong_examples"] = [
        {"path": r["path"], "question": r["question"], "truth": r["truth"],
         "prediction": r["po"]["value"] if r.get("po") else None, "tier": r.get("tier")}
        for r in sample
    ]

    # (8) invariants / exceptions
    stats["n_invariant_violations"] = sum(len(r.get("violations") or []) for r in rows)
    stats["n_exceptions"] = len(errored)
    stats["exceptions_sample"] = [{"path": r["path"], "question": r["question"], "error": r["error"]}
                                   for r in errored[:10]]

    stats["n_questions"] = len(rows)
    stats["n_drawings"] = len({r["path"] for r in rows})
    return stats


# --------------------------------------------------------------------------------------
# Report rendering
# --------------------------------------------------------------------------------------
def _fmt_ci(cell: dict) -> str:
    lo, hi = cell["ci"]
    acc = cell["k"] / cell["n"] if cell["n"] else 0.0
    return f"{acc:.1%} [{lo:.1%}, {hi:.1%}] (n={cell['n']})"


def render_report(stats: dict, meta: dict, hard_stats: Optional[dict] = None) -> str:
    L = []
    L.append(f"# evalkit report — {meta['tag']}\n")
    L.append(f"engine: `{meta['engine']}` · split: `{meta['split']}` · siblings: "
             f"`{'off' if meta['no_siblings'] else 'on'}` · LLM_PROVIDER=`{meta['llm_mode']}`\n")
    L.append("Split is deterministic by `int(sha1(path), 16) % 5 == 0` -> holdout, else dev. "
              "Holdout is never used to tune anything.\n")

    L.append("## 1. Headline accuracy (quantitative types only; text excluded, see below)\n")
    for split in ("dev", "holdout", "overall"):
        cell = stats[f"headline_{split}"]
        L.append(f"- **{split}**: {_fmt_ci(cell)}")
    L.append(f"- text (reported separately, excluded from headline): {_fmt_ci(stats['headline_text'])}\n")

    L.append("## 2. Source x type\n")
    L.append("| source | type | accuracy [95% CI] (n) |")
    L.append("|---|---|---|")
    for key, cell in stats["by_source_type"].items():
        s, t = key.split("|")
        L.append(f"| {s} | {t} | {_fmt_ci(cell)} |")
    L.append("")

    L.append("## 3. Per-intent (prior baseline alongside)\n")
    L.append("| intent | accuracy [95% CI] (n) | prior baseline acc |")
    L.append("|---|---|---|")
    for name, cell in stats["by_intent"].items():
        prior = f"{cell['prior_acc']:.1%}" if cell["prior_acc"] is not None else "n/a"
        L.append(f"| {name} | {_fmt_ci(cell)} | {prior} |")
    L.append("")

    L.append("## 4. Tier calibration (benchmark mode always returns a value)\n")
    L.append("| tier | n | coverage | accuracy [95% CI] |")
    L.append("|---|---|---|---|")
    for t in ("green", "amber", "grey"):
        cell = stats["tier_table"][t]
        L.append(f"| {t} | {cell['n']} | {cell['coverage']:.1%} | {_fmt_ci(cell)} |")
    L.append("\n### accuracy vs coverage (10 levels, ranked green>amber>grey)\n")
    L.append("| coverage | accuracy | n |")
    L.append("|---|---|---|")
    for row in stats["coverage_curve"]:
        acc = f"{row['acc']:.1%}" if row["acc"] is not None else "n/a"
        L.append(f"| {row['coverage_pct']}% | {acc} | {row['n']} |")
    L.append("")

    c = stats["cost"]
    L.append("## 5. Cost\n")
    L.append(f"- mean/median/p95 ms per question: {c['mean_ms']:.2f} / {c['median_ms']:.2f} / {c['p95_ms']:.2f}")
    L.append(f"- tokens total: {c['tokens_total']} · USD total: {c['usd_total']:.4f} · "
              f"llm_calls: {c['llm_calls']} · planner_calls: {c['planner_calls']}")
    L.append(f"- first-question-of-drawing (analysis) mean ms: {c['mean_first_of_drawing_ms']:.2f} "
              f"(cache-eligible; marginal mean ms for follow-up questions: {c['mean_marginal_ms']:.2f})")
    L.append(f"- estimate: CPU-seconds per drawing: {c['cpu_s_per_drawing_estimate']:.4f} "
              f"· per 14,000 drawings: {c['cpu_s_per_14000_drawings_estimate']:.1f} (estimate, extrapolated)\n")

    L.append("## 6. Failure buckets (source|intent|width_bucket|direction -> n)\n")
    for k, v in list(stats["failure_buckets"].items())[:25]:
        L.append(f"- {k}: {v}")
    L.append("")

    L.append("## 7. 20 random wrong examples\n")
    L.append("| path | question | truth | prediction | tier |")
    L.append("|---|---|---|---|---|")
    for ex in stats["wrong_examples"]:
        q = ex["question"].replace("|", "/")[:70]
        L.append(f"| {ex['path']} | {q} | {ex['truth']} | {ex['prediction']} | {ex['tier']} |")
    L.append("")

    L.append("## 8. Invariant violations and exceptions\n")
    L.append(f"- invariant violations: {stats['n_invariant_violations']}")
    L.append(f"- exceptions: {stats['n_exceptions']}")
    for ex in stats["exceptions_sample"]:
        L.append(f"  - {ex['path']}: {ex['error']}")
    L.append("")

    if hard_stats is not None:
        L.append("## 10. Hard set (hand-written, never used for tuning)\n")
        L.append(f"- dev: {hard_stats['dev']['k']}/{hard_stats['dev']['n']}, "
                  f"holdout: {hard_stats['holdout']['k']}/{hard_stats['holdout']['n']}")
        L.append("| kind_of_hard | n | accuracy [95% CI] |")
        L.append("|---|---|---|")
        for k, cell in hard_stats["by_kind"].items():
            L.append(f"| {k} | {cell['n']} | {_fmt_ci(cell)} |")
        L.append("")

    L.append("## 9. Reproduce\n")
    L.append(f"- command: `{meta['cmdline']}`")
    L.append(f"- git commit: `{meta['commit']}`")
    L.append(f"- n_questions: {stats['n_questions']} · n_drawings: {stats['n_drawings']}")
    L.append(f"- split sizes: `{meta['split_sizes']}`\n")
    return "\n".join(L)


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                               cwd=HERE.parent, timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def merge_claims_dir(claims: dict) -> dict:
    claims_dir = HERE.parent / "docs" / "claims"
    if not claims_dir.exists():
        return claims
    for f in sorted(claims_dir.glob("*.json")):
        extra = json.loads(f.read_text())
        for k, v in extra.items():
            if k in claims and claims[k] != v:
                raise ValueError(f"claims.json key clash on '{k}' from {f.name}: {claims[k]!r} vs {v!r}")
            claims[k] = v
    return claims


def build_claims(stats: dict, meta: dict, hard_stats: Optional[dict]) -> dict:
    c = stats["cost"]
    tier = stats["tier_table"]
    claims = {
        "headline_acc_holdout": (stats["headline_holdout"]["k"] / stats["headline_holdout"]["n"]
                                  if stats["headline_holdout"]["n"] else None),
        "headline_ci": list(stats["headline_holdout"]["ci"]) if stats["headline_holdout"]["n"]
        else list(stats["headline_overall"]["ci"]),
        "green_acc": (tier["green"]["k"] / tier["green"]["n"] if tier["green"]["n"] else None),
        "green_coverage": tier["green"]["coverage"],
        "amber_acc": (tier["amber"]["k"] / tier["amber"]["n"] if tier["amber"]["n"] else None),
        "grey_share": tier["grey"]["coverage"],
        "mean_ms": c["mean_ms"],
        "tokens_total": c["tokens_total"],
        "usd_total": c["usd_total"],
        "llm_calls": c["llm_calls"],
        "n_questions": stats["n_questions"],
        "n_drawings": stats["n_drawings"],
        "split_sizes": meta["split_sizes"],
        "engine": meta["engine"],
        "commit": meta["commit"],
        "hard_acc_dev": hard_stats["dev"]["k"] / hard_stats["dev"]["n"] if hard_stats and hard_stats["dev"]["n"] else None,
        "hard_n_dev": hard_stats["dev"]["n"] if hard_stats else 0,
        "hard_acc_holdout": (hard_stats["holdout"]["k"] / hard_stats["holdout"]["n"]
                              if hard_stats and hard_stats["holdout"]["n"] else None),
        "hard_n_holdout": hard_stats["holdout"]["n"] if hard_stats else 0,
        "planner_calls": c["planner_calls"],
        "llm_mode": meta["llm_mode"],
        "cpu_per_drawing_s": c["cpu_s_per_drawing_estimate"],
    }
    return merge_claims_dir(claims)


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--engine", choices=["stub", "prior", "pipeline"], default="stub")
    p.add_argument("--split", choices=["dev", "holdout", "all"], default="all")
    p.add_argument("--no-siblings", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sources", type=str, default=None, help="comma-separated source names")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--tag", type=str, default="")
    p.add_argument("--hard", action="store_true", help="also score evalkit/hard_questions.jsonl")
    p.add_argument("--root", type=str, default=None, help="override DATASET_ROOT (mainly for tests)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cmdline = "python -m evalkit.run " + " ".join(argv if argv is not None else __import__("sys").argv[1:])

    all_q = load_questions(args.root)
    dev_q = [q for q in all_q if q.split == "dev"]

    questions = all_q
    if args.split != "all":
        questions = [q for q in questions if q.split == args.split]
    if args.sources:
        wanted = set(args.sources.split(","))
        questions = [q for q in questions if q.source in wanted]
    if args.limit:
        questions = questions[: args.limit]

    allow_siblings = not args.no_siblings
    engine = build_engine(args.engine, dev_q)
    rows = run_questions(engine, questions, allow_siblings, args.workers)

    prior_rows = rows
    if args.engine != "prior":
        prior_engine = PriorEngine(dev_q)
        prior_rows = run_questions(prior_engine, questions, allow_siblings, 1)

    stats = aggregate(rows, prior_rows)

    hard_stats = None
    if args.hard:
        hard_rows = load_hard_questions(HERE / "hard_questions.jsonl", verified_only=True)
        hard_results = []
        for hq in hard_rows:
            full_q = Q(path=hq["path"], question=hq["question"], answer=hq["answer"], unit=hq.get("unit"),
                       type=hq["type"], source=hq["path"].split("/")[1], lang=hq.get("lang", "xx"))
            from evalkit.data import split_of

            full_q.split = split_of(full_q.path)
            hard_results.append((hq, ask_one(engine, full_q, allow_siblings)))
        by_split = {"dev": {"k": 0, "n": 0}, "holdout": {"k": 0, "n": 0}}
        by_kind: dict[str, list] = collections.defaultdict(list)
        for hq, r in hard_results:
            split = split_of(hq["path"])
            by_split[split]["n"] += 1
            by_split[split]["k"] += int(r["correct"])
            by_kind[hq["kind_of_hard"]].append(r)
        hard_stats = {
            "dev": by_split["dev"], "holdout": by_split["holdout"],
            "by_kind": {k: {"n": len(v), "ci": scoring.wilson(*_acc(v)), "k": _acc(v)[0]}
                        for k, v in by_kind.items()},
        }

    ts = time.strftime("%Y%m%d-%H%M%S")
    tag = args.tag or args.engine
    out_dir = OUT_ROOT / f"{ts}-{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    meta = {
        "tag": tag, "engine": args.engine, "split": args.split, "no_siblings": args.no_siblings,
        "cmdline": cmdline, "commit": git_commit(), "split_sizes": split_sizes(all_q),
        "llm_mode": os.environ.get("LLM_PROVIDER", "none"),
    }
    report_md = render_report(stats, meta, hard_stats)
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(stats, default=str, indent=2), encoding="utf-8")
    claims = build_claims(stats, meta, hard_stats)
    (out_dir / "claims.json").write_text(json.dumps(claims, default=str, indent=2), encoding="utf-8")

    latest = OUT_ROOT / "latest"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out_dir.name)

    print(report_md)
    print(f"\nwrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
