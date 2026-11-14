"""Split determinism/stability and the questions.jsonl loader. Tiny synthetic dataset, no real data."""
from __future__ import annotations

import hashlib
import json

from evalkit.data import load_questions, split_of, split_sizes


def test_split_is_deterministic_formula():
    path = "data/cubicasa5k/some-1234.png"
    expected = "holdout" if int(hashlib.sha1(path.encode()).hexdigest(), 16) % 5 == 0 else "dev"
    assert split_of(path) == expected


def test_split_stable_across_repeated_calls():
    paths = [f"data/cubicasa5k/img-{i}.png" for i in range(50)]
    first = [split_of(p) for p in paths]
    second = [split_of(p) for p in paths]
    assert first == second


def test_split_keyed_by_path_not_question():
    # same path, different question text -> same split (a drawing's questions never straddle splits)
    p = "data/swiss_dwellings/site1_bldg1_floor1.pdf"
    assert split_of(p) == split_of(p)


def _write_dataset(tmp_path, rows):
    root = tmp_path / "ds"
    root.mkdir()
    with (root / "questions.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return root


def test_load_questions_parses_rows_and_source(tmp_path):
    rows = [
        {"path": "data/cubicasa5k/a-1.png", "question": "How many windows are shown on this floor plan?",
         "answer": 3, "unit": "count", "type": "count"},
        {"path": "data/swiss_dwellings/b-2.pdf", "question": "How many bathtubs are drawn on this floor plan?",
         "answer": 1, "unit": "count", "type": "count"},
    ]
    root = _write_dataset(tmp_path, rows)
    qs = load_questions(root, classify=False)
    assert len(qs) == 2
    assert qs[0].source == "cubicasa5k"
    assert qs[1].source == "swiss_dwellings"
    assert qs[0].split in ("dev", "holdout")


def test_split_sizes_totals(tmp_path):
    rows = [
        {"path": f"data/cubicasa5k/img-{i}.png", "question": "q", "answer": 1, "unit": "count", "type": "count"}
        for i in range(20)
    ]
    root = _write_dataset(tmp_path, rows)
    qs = load_questions(root, classify=False)
    sizes = split_sizes(qs)
    assert sizes["cubicasa5k"]["dev"] + sizes["cubicasa5k"]["holdout"] == 20
    assert sizes["TOTAL"]["dev"] + sizes["TOTAL"]["holdout"] == 20


def test_load_questions_missing_file_raises(tmp_path):
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    try:
        load_questions(empty_root, classify=False)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
