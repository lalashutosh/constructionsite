"""Query engine package: `run(spec, facts)`, fixed specs, planner (optional LLM)."""
from __future__ import annotations

from typing import Optional

from engine.query.fixed import spec_for  # noqa: F401
from engine.query.run import Result, SpecError, run, validate  # noqa: F401


def execute_plan(specs: list[dict], combine: str, facts, px_per_m: Optional[float] = None) -> Result:
    """Run one or several validated specs and combine them in code (sum / list / difference / ratio).
    Numbers come only from here; each part's value is kept in `groups` (part1, part2, ...) for the reasoning view."""
    results = [run(s, facts, px_per_m) for s in specs]
    if len(results) == 1 or combine == "single":
        return results[0]
    out = Result(unit=results[0].unit)
    out.evidence_ids = [i for r in results for i in r.evidence_ids]
    out.rule_applied = [x for r in results for x in r.rule_applied]
    out.needs_scale = any(r.needs_scale for r in results)
    vals = [r.value for r in results]
    out.groups = {f"part{i + 1}": r.value for i, r in enumerate(results)}
    if combine == "sum":
        out.value = None if any(v is None for v in vals) else sum(vals)
    elif combine in ("greater", "less"):              # "are there more windows than doors?" -> Yes / No
        a, b = (vals + [None, None])[:2]
        if a is None or b is None:
            out.value = None
        else:
            yes = a > b if combine == "greater" else a < b
            out.value = "Yes" if yes else "No"
            out.unit = "yes/no"
            out.notes.append(f"compared {a} with {b}")
    elif combine in ("difference", "ratio"):           # "more windows than doors?" -> part1 - part2 (or /)
        a, b = (vals + [None, None])[:2]
        if a is None or b is None or (combine == "ratio" and not b):
            out.value = None
        else:
            out.value = (a - b) if combine == "difference" else round(a / b, 4)
            out.unit = results[0].unit if combine == "difference" else "ratio"
    else:
        out.value = len(results)
        out.groups = {str(i): r.value for i, r in enumerate(results)}
    return out
