"""Loader for the hand-written hard set (evalkit/hard_questions.jsonl).

Rows: {path, question, answer, unit, type, lang, kind_of_hard, verified, author}.
kind_of_hard in {filter, group, adjacency, mixed, cross_format, multilingual}.
Scored separately from the main dataset, split by the same path hash, NEVER used to tune anything.
Unverified rows (verified: false) are never scored -- they only document the format.
"""
from __future__ import annotations

import json
from pathlib import Path

KINDS = {"filter", "group", "adjacency", "mixed", "cross_format", "multilingual"}


def load_hard_questions(path: Path | str, *, verified_only: bool = True) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if verified_only and not d.get("verified", False):
                continue
            rows.append(d)
    return rows
