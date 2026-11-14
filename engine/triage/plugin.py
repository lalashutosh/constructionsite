"""Triage plugin: registers the rule-based sheet triage with engine.registry (raster files only)."""
from __future__ import annotations

import functools

from engine.skeptic.plugin import RASTER_EXT


@functools.lru_cache(maxsize=512)
def _cached(path: str):
    from engine.triage import rules
    return rules.classify(path)


def triage(ctx):
    from engine.registry import TriageResult

    if not ctx.abs_path.lower().endswith(RASTER_EXT):
        return None
    r = _cached(ctx.abs_path)
    f = r["feats"]
    return TriageResult(sheet_type=r["sheet_type"], legible=r["legible"],
                        note=f"triage rule={r['rule']}" if r["rule"] else "triage: no refusal rule fired",
                        refuse=r["refuse"])


def register() -> None:
    from engine import registry

    registry.register_triage("skeptic_rules", triage)
