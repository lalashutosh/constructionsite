"""Query engine package: `run(spec, facts)`, fixed specs, planner (optional LLM)."""
from __future__ import annotations

from typing import Optional

from engine.query.fixed import spec_for  # noqa: F401
from engine.query.run import Result, SpecError, run, validate  # noqa: F401


def execute_plan(specs: list[dict], combine: str, facts, px_per_m: Optional[float] = None) -> Result:
    """Run one or several validated specs and combine them in code (sum / list). Numbers come only from here."""
    results = [run(s, facts, px_per_m) for s in specs]
    if len(results) == 1 or combine == "single":
        return results[0]
    out = Result(unit=results[0].unit)
    out.evidence_ids = [i for r in results for i in r.evidence_ids]
    out.rule_applied = [x for r in results for x in r.rule_applied]
    out.needs_scale = any(r.needs_scale for r in results)
    if combine == "sum":
        vals = [r.value for r in results]
        out.value = None if any(v is None for v in vals) else sum(vals)
    else:
        out.value = len(results)
        out.groups = {str(i): r.value for i, r in enumerate(results)}
    return out
