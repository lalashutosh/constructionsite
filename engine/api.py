"""Engine entry point used by evalkit and the API. W0 ships a STUB; the integrator replaces it in Wave 2.

    from engine.api import get_engine
    eng = get_engine("stub" | "pipeline")
    facts = eng.analyze(path); po = eng.ask(path, question)
"""
from __future__ import annotations

import time

from contracts.proof import Cost, ProofObject, Provenance, SheetFacts, Tier


class StubEngine:
    """Always answers 0 / amber. Gives the evaluator a floor to beat and lets the UI run without a backend."""

    def analyze(self, path: str, *, allow_siblings: bool = True) -> SheetFacts:
        return SheetFacts(provenance=Provenance(file=path), sheet_type="unknown")

    def ask(self, path: str, question: str, *, allow_siblings: bool = True, benchmark: bool = True) -> ProofObject:
        t0 = time.perf_counter()
        return ProofObject(
            id=f"stub-{abs(hash((path, question))) % 10**8}", question=question, kind="count", value=0,
            tier=Tier.amber, provenance=Provenance(file=path), notes=["stub engine: no extraction"],
            cost=Cost(ms=(time.perf_counter() - t0) * 1000),
        )


def get_engine(mode: str = "stub"):
    if mode == "stub":
        return StubEngine()
    if mode == "pipeline":
        from engine.pipeline import PipelineEngine  # written by the integrator in Wave 2

        return PipelineEngine()
    raise ValueError(f"unknown engine mode {mode}")
