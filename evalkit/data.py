"""Dataset loading: questions.jsonl -> list[Q], and the dev/holdout split.

DATASET_ROOT is read from the environment, falling back to a hand-parsed `.env`
(no extra dependency; same regex as scripts/check_env.py).
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_ENV_LINE = re.compile(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$")


def _load_dotenv(repo_root: pathlib.Path = _REPO_ROOT) -> None:
    f = repo_root / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if m:
            os.environ.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))


_load_dotenv()


def dataset_root() -> pathlib.Path:
    """DATASET_ROOT: the folder that contains questions.jsonl and data/."""
    root = os.environ.get("DATASET_ROOT")
    if not root:
        raise RuntimeError("DATASET_ROOT not set. Copy .env.example to .env and set it.")
    return pathlib.Path(root).expanduser()


def split_of(path: str) -> str:
    """Deterministic dev/holdout split, keyed by PATH so a drawing's questions never straddle splits."""
    h = int(hashlib.sha1(path.encode("utf-8")).hexdigest(), 16)
    return "holdout" if h % 5 == 0 else "dev"


@dataclass
class Q:
    path: str
    question: str
    answer: Any
    unit: Optional[str]
    type: str
    source: str
    lang: str = "xx"
    intent: str = "unknown"
    params: dict = field(default_factory=dict)
    split: str = "dev"

    def to_dict(self) -> dict:
        return {
            "path": self.path, "question": self.question, "answer": self.answer, "unit": self.unit,
            "type": self.type, "source": self.source, "lang": self.lang, "intent": self.intent,
            "params": self.params, "split": self.split,
        }


def _iter_raw_rows(root: pathlib.Path):
    qpath = root / "questions.jsonl"
    if not qpath.exists():
        raise FileNotFoundError(f"{qpath} not found; DATASET_ROOT must contain questions.jsonl and data/")
    with qpath.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_questions(root: Optional[str | pathlib.Path] = None, *, classify: bool = True) -> list[Q]:
    """Load every row of questions.jsonl into a Q, with split, language guess and intent classification.

    classify=False skips evalkit.intents (useful for tests that only exercise the split/loader).
    """
    r = pathlib.Path(root) if root is not None else dataset_root()
    classify_fn = guess_lang_fn = None
    if classify:
        from evalkit.intents import classify as classify_fn  # noqa: PLC0415
        from evalkit.intents import guess_lang as guess_lang_fn  # noqa: PLC0415

    out: list[Q] = []
    for d in _iter_raw_rows(r):
        path = d["path"]
        parts = path.split("/")
        source = parts[1] if len(parts) > 1 else "unknown"
        question = d["question"]
        lang = guess_lang_fn(question) if guess_lang_fn else "xx"
        intent_name, params = "unknown", {}
        if classify_fn:
            intent = classify_fn(question, path)
            intent_name, params, lang = intent.name, intent.params, intent.lang
        out.append(Q(
            path=path, question=question, answer=d.get("answer"), unit=d.get("unit"),
            type=d["type"], source=source, lang=lang, intent=intent_name, params=params,
            split=split_of(path),
        ))
    return out


def split_sizes(questions: list[Q]) -> dict[str, dict[str, int]]:
    """{source: {dev: n, holdout: n}} plus a TOTAL row, for the report header."""
    sizes: dict[str, dict[str, int]] = {}
    for q in questions:
        sizes.setdefault(q.source, {"dev": 0, "holdout": 0})
        sizes[q.source][q.split] += 1
    totals = {"dev": 0, "holdout": 0}
    for v in sizes.values():
        totals["dev"] += v["dev"]
        totals["holdout"] += v["holdout"]
    sizes["TOTAL"] = totals
    return sizes
