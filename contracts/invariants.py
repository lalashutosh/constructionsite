"""Invariants every ProofObject must satisfy before it reaches the UI or the scorer. Returns a list of problems."""
from __future__ import annotations

from .proof import ProofObject, Tier

AGREE_TOL = 0.02   # area/length/volume: same tolerance as the scorer and engine.pipeline._agree


def check(po: ProofObject) -> list[str]:
    bad: list[str] = []

    if po.tier == Tier.grey:
        if not po.refusal:
            bad.append("grey tier needs a refusal reason")
        if po.value is not None:
            bad.append("grey tier must not carry a value in product mode")

    if po.tier == Tier.green:
        vals = [v.value for v in po.voters if v.value is not None]
        if len(vals) < 2:
            bad.append("green needs >= 2 independent voters")
        elif po.kind == "count" and len(set(vals)) != 1:
            bad.append(f"green requires voters to agree, got {vals}")
        elif po.kind != "count" and (max(vals) - min(vals)) > AGREE_TOL * max(abs(v) for v in vals):
            # area/length/volume agree within the scoring tolerance (docs/decisions/contract-invariants-area-tolerance.md)
            bad.append(f"green requires voters to agree within {AGREE_TOL:.0%}, got {vals}")

    if po.kind == "count" and po.value is not None and not isinstance(po.value, int):
        bad.append("count value must be int")

    if po.kind in ("area", "length", "volume") and po.value is not None:
        if po.scale is None or po.scale.px_per_m is None:
            bad.append(f"{po.kind} answer needs a scale (or a vector source with real units)")

    if po.scale and po.scale.anchors:
        only_prior = all(a.kind == "door_prior" for a in po.scale.anchors)
        if only_prior and not po.scale.widths_relative:
            bad.append("scale from door prior only: widths_relative must be true (circular evidence)")

    for e in po.evidence:
        if len(e.polygon) < 2:
            bad.append(f"evidence {e.id} has no geometry")

    if po.interval and po.interval.lo > po.interval.hi:
        bad.append("interval lo > hi")

    if po.cost.planner_calls > 0 and po.query_spec is None:
        bad.append("planner answer must carry its query_spec")

    if not po.provenance.file:
        bad.append("provenance.file missing")

    return bad
