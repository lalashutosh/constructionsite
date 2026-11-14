"""Plugin registry: lets W2 agents land independently. The integrator's pipeline only talks to this module.

Each package exposes `engine/<pkg>/plugin.py` with a `register()` function that calls the functions below.
`autodiscover()` imports every known plugin module that exists and calls register() (missing ones are skipped).

    triage(ctx)            -> TriageResult | None      (first non-None refusal wins; sheet_type from the first answer)
    resolver(path, allow)  -> Resolved | None          (sibling / exact-format resolution, highest priority first)
    voter(ctx)             -> VoterResult | None       (independent opinions; the pipeline computes the tier from them)
    finalizer(ctx, voters) -> FinalAdjust | None       (stacker / rule correction, sees all voters, runs last)
    calibrator(po_dict)    -> float | None             (P(correct) in [0, 1] for display only)
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from contracts.proof import Element, SheetFacts, Voter

PLUGIN_MODULES = (
    "engine.raster.plugin",
    "engine.skeptic.plugin",
    "engine.vector.plugin",
    "engine.takeoff.plugin",
)


@dataclass
class Ctx:
    """What a plugin gets. `facts` may be None when the plugin is expected to read the file itself."""
    path: str                      # questions.jsonl path (relative to DATASET_ROOT)
    abs_path: str                  # absolute path on disk
    question: str
    intent: str                    # evalkit.intents name, "unknown" if not recognised
    params: dict[str, Any] = field(default_factory=dict)
    kind: str = "count"            # count | area | length | volume | text | other
    lang: str = "xx"
    allow_siblings: bool = True
    facts: Optional[SheetFacts] = None
    resolved: Optional["Resolved"] = None


@dataclass
class TriageResult:
    sheet_type: str = "unknown"
    legible: bool = True
    note: Optional[str] = None
    refuse: Optional[str] = None   # human-readable reason => product mode returns grey


@dataclass
class Resolved:
    path: str                      # path to the better file (relative to DATASET_ROOT)
    fmt: str                       # ifc | dxf | svg | pdf-vector | png
    note: Optional[str] = None


@dataclass
class VoterResult:
    voter: Voter
    evidence: list[Element] = field(default_factory=list)
    unit: Optional[str] = None
    exact: bool = False            # True for exact-format sources (dxf/ifc/schedule text)


@dataclass
class FinalAdjust:
    value: float
    note: str
    voter_name: str = "stacker"


_triage: list[tuple[str, Callable]] = []
_resolvers: list[tuple[int, str, Callable]] = []
_voters: list[tuple[str, tuple[str, ...], Callable]] = []
_finalizers: list[tuple[str, Callable]] = []
_calibrators: list[tuple[str, Callable]] = []


def reset() -> None:
    for lst in (_triage, _resolvers, _voters, _finalizers, _calibrators):
        lst.clear()


def register_triage(name: str, fn: Callable[[Ctx], Optional[TriageResult]]) -> None:
    _triage.append((name, fn))


def register_resolver(name: str, fn: Callable[[str, bool], Optional[Resolved]], priority: int = 50) -> None:
    _resolvers.append((priority, name, fn))
    _resolvers.sort(key=lambda t: t[0])


def register_voter(name: str, fn: Callable[[Ctx], Optional[VoterResult]], kinds: tuple[str, ...] = ("count",)) -> None:
    _voters.append((name, tuple(kinds), fn))


def register_finalizer(name: str, fn: Callable[[Ctx, list[VoterResult]], Optional[FinalAdjust]]) -> None:
    _finalizers.append((name, fn))


def register_calibrator(name: str, fn: Callable[[dict], Optional[float]]) -> None:
    _calibrators.append((name, fn))


def triagers() -> list[tuple[str, Callable]]:
    return list(_triage)


def resolvers() -> list[tuple[str, Callable]]:
    return [(n, f) for _, n, f in _resolvers]


def voters_for(kind: str) -> list[tuple[str, Callable]]:
    return [(n, f) for n, ks, f in _voters if kind in ks or "*" in ks]


def finalizers() -> list[tuple[str, Callable]]:
    return list(_finalizers)


def calibrators() -> list[tuple[str, Callable]]:
    return list(_calibrators)


def autodiscover(extra: tuple[str, ...] = ()) -> list[str]:
    """Import every plugin module that exists; return the names that registered. Never raises on missing modules."""
    loaded = []
    for mod in PLUGIN_MODULES + tuple(extra):
        try:
            m = importlib.import_module(mod)
        except ModuleNotFoundError as e:
            if e.name and (mod == e.name or mod.startswith(e.name + ".")):
                continue          # plugin not written yet
            raise
        reg = getattr(m, "register", None)
        if callable(reg):
            reg()
            loaded.append(mod)
    return loaded
