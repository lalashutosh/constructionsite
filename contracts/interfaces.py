"""Function-level interfaces. Implementations live in engine/*. Keep these signatures stable."""
from __future__ import annotations

from typing import Protocol

from .proof import ProofObject, SheetFacts


class Extractor(Protocol):
    def extract(self, path: str, *, allow_siblings: bool = True) -> SheetFacts:
        """Read ONE drawing into SheetFacts. `path` is the questions.jsonl path (relative to DATASET_ROOT).
        allow_siblings=False forces the pure-image/pure-given-file route (the honest 'images only' number)."""


class Answerer(Protocol):
    def answer(self, question: str, facts: SheetFacts) -> ProofObject:
        """Answer one question from facts only. Must always return a value in benchmark mode (best guess),
        with tier/voters telling a human how far to trust it."""


class Engine(Protocol):
    """What evalkit and api call. engine/api.py exposes `get_engine(mode)`."""

    def analyze(self, path: str, *, allow_siblings: bool = True) -> SheetFacts: ...

    def ask(self, path: str, question: str, *, allow_siblings: bool = True, benchmark: bool = True) -> ProofObject: ...
