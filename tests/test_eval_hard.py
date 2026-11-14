"""Hard set loader: unverified rows document the format but are NEVER scored."""
from __future__ import annotations

import json

from evalkit.hard import load_hard_questions


def _write_hard_file(tmp_path, rows):
    p = tmp_path / "hard.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


def test_unverified_rows_excluded_by_default(tmp_path):
    rows = [
        {"path": "data/swiss_dwellings/a.pdf", "question": "q1", "answer": 1, "unit": "count",
         "type": "count", "lang": "en", "kind_of_hard": "filter", "verified": True, "author": "x"},
        {"path": "data/swiss_dwellings/a.pdf", "question": "q2", "answer": 2, "unit": "count",
         "type": "count", "lang": "en", "kind_of_hard": "group", "verified": False, "author": "x"},
    ]
    p = _write_hard_file(tmp_path, rows)
    verified = load_hard_questions(p, verified_only=True)
    assert len(verified) == 1
    assert verified[0]["question"] == "q1"


def test_unverified_rows_included_when_asked_explicitly(tmp_path):
    rows = [
        {"path": "data/swiss_dwellings/a.pdf", "question": "q1", "answer": 1, "unit": "count",
         "type": "count", "lang": "en", "kind_of_hard": "filter", "verified": False, "author": "x"},
    ]
    p = _write_hard_file(tmp_path, rows)
    everything = load_hard_questions(p, verified_only=False)
    assert len(everything) == 1


def test_missing_verified_key_treated_as_unverified(tmp_path):
    rows = [
        {"path": "data/swiss_dwellings/a.pdf", "question": "q1", "answer": 1, "unit": "count",
         "type": "count", "lang": "en", "kind_of_hard": "filter", "author": "x"},
    ]
    p = _write_hard_file(tmp_path, rows)
    assert load_hard_questions(p, verified_only=True) == []


def test_missing_file_returns_empty(tmp_path):
    assert load_hard_questions(tmp_path / "nope.jsonl") == []


def test_shipped_hard_questions_file_has_no_verified_rows_yet():
    """The 10 seed rows are explicitly verified: false until a human checks them (RUNBOOK section 8)."""
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "evalkit" / "hard_questions.jsonl"
    rows = load_hard_questions(p, verified_only=False)
    assert len(rows) >= 10
    scored = load_hard_questions(p, verified_only=True)
    assert scored == [], "seed rows must stay verified:false until a human checks them against the drawing"
