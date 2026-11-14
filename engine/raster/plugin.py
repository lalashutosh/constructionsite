"""Registry plugin for the raster package: the `detector` count voter (engine.count.count over raster SheetFacts)."""
from __future__ import annotations

from engine import registry
from contracts.proof import Voter

_RASTER_FMT = {"png", "jpg", "jpeg", "webp"}


def detector(ctx):
    from engine.count import INTENTS, count

    facts = ctx.facts
    if facts is None or ctx.intent not in INTENTS:
        return None
    if (facts.provenance.fmt or "") not in _RASTER_FMT and "cnn_runs" not in facts.extras:
        return None  # not a raster-extracted sheet: the query-engine voter handles it
    value, ids, runs = count(ctx.intent, facts)  # may write facts.extras["count_defaults"][intent]
    note = None
    default = facts.extras.get("count_defaults", {}).get(ctx.intent)
    if default:
        note = f"prior fallback, no detector evidence ({default.get('reason', '')})"
    by_id = {e.id: e for e in facts.elements}
    return registry.VoterResult(
        Voter(name="detector", value=value, element_ids=ids, runs=list(runs), note=note),
        evidence=[by_id[i] for i in ids if i in by_id])


def register() -> None:
    registry.register_voter("detector", detector, kinds=("count",))
