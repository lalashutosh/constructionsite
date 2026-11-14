"""Full evalkit.run with the stub engine on a synthetic dataset: must not crash, must finish fast,
must write results.jsonl/report.md/report.json/claims.json and update the `latest` symlink."""
from __future__ import annotations

import json

from evalkit import run as run_mod
from evalkit.data import Q, split_of


def _make_questions(n: int = 30) -> list[Q]:
    sources = ["cubicasa5k", "swiss_dwellings", "ifc_models"]
    types = ["count", "area", "text"]
    qs = []
    for i in range(n):
        source = sources[i % len(sources)]
        qtype = types[i % len(types)]
        path = f"data/{source}/synthetic-{i}.png"
        answer = 3 if qtype == "count" else (12.5 if qtype == "area" else "some text")
        qs.append(Q(
            path=path, question=f"synthetic question {i}", answer=answer,
            unit="count" if qtype == "count" else ("m2" if qtype == "area" else None),
            type=qtype, source=source, intent="unknown", split=split_of(path),
        ))
    return qs


def test_run_questions_stub_engine_never_crashes_and_is_fast(tmp_path, monkeypatch):
    import time

    from engine.api import get_engine

    engine = get_engine("stub")
    questions = _make_questions(30)

    t0 = time.perf_counter()
    rows = run_mod.run_questions(engine, questions, allow_siblings=True, workers=1)
    elapsed = time.perf_counter() - t0

    assert len(rows) == 30
    assert elapsed < 10.0
    for r in rows:
        assert r["error"] is None
        assert r["po"] is not None
        assert "correct" in r


def test_aggregate_produces_required_sections():
    from engine.api import get_engine

    engine = get_engine("stub")
    questions = _make_questions(30)
    rows = run_mod.run_questions(engine, questions, allow_siblings=True, workers=1)
    stats = run_mod.aggregate(rows)

    for key in ("headline_dev", "headline_holdout", "headline_overall", "headline_text",
                "by_source_type", "by_intent", "tier_table", "coverage_curve", "cost",
                "failure_buckets", "wrong_examples", "n_invariant_violations", "n_exceptions"):
        assert key in stats


def test_render_report_contains_required_sections():
    from engine.api import get_engine

    engine = get_engine("stub")
    questions = _make_questions(30)
    rows = run_mod.run_questions(engine, questions, allow_siblings=True, workers=1)
    stats = run_mod.aggregate(rows)
    meta = {
        "tag": "test", "engine": "stub", "split": "all", "no_siblings": False,
        "cmdline": "test", "commit": "deadbeef", "split_sizes": {},
        "llm_mode": "none",
    }
    report = run_mod.render_report(stats, meta)
    assert "## 1. Headline accuracy" in report
    assert "## 2. Source x type" in report
    assert "## 3. Per-intent" in report
    assert "## 4. Tier calibration" in report
    assert "## 5. Cost" in report
    assert "Holdout is never used to tune anything" in report


def test_full_run_cli_writes_output_files(tmp_path, monkeypatch):
    # Build a tiny synthetic dataset on disk and point evalkit.run at it via --root.
    root = tmp_path / "ds"
    root.mkdir()
    rows = []
    for i in range(30):
        source = ["cubicasa5k", "swiss_dwellings"][i % 2]
        rows.append({
            "path": f"data/{source}/synthetic-{i}.png",
            "question": "How many windows are shown on this floor plan?",
            "answer": 2, "unit": "count", "type": "count",
        })
    with (root / "questions.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    monkeypatch.setattr(run_mod, "OUT_ROOT", tmp_path / "out")
    rc = run_mod.main(["--engine", "stub", "--split", "all", "--root", str(root), "--tag", "synthtest"])
    assert rc == 0

    out_root = tmp_path / "out"
    latest = out_root / "latest"
    assert latest.exists()
    assert (latest / "results.jsonl").exists()
    assert (latest / "report.md").exists()
    assert (latest / "report.json").exists()
    assert (latest / "claims.json").exists()

    results = [json.loads(l) for l in (latest / "results.jsonl").read_text().splitlines() if l.strip()]
    assert len(results) == 30
    claims = json.loads((latest / "claims.json").read_text())
    for key in ("headline_acc_holdout", "green_acc", "n_questions", "n_drawings", "engine", "commit"):
        assert key in claims
