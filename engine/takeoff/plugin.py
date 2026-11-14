"""Registry plugin for takeoff: `area_polygons` (area/length/volume from room/wall elements through the scale) and
`query_engine` (fixed query specs for intents the raster detector does not cover). Both run engine.query, no LLM."""
from __future__ import annotations

from contracts.proof import Voter
from engine import registry

_EXACT_FMT = {"ifc", "dxf", "svg"}


def _run(ctx, name: str):
    from engine import query

    facts = ctx.facts
    if facts is None or not facts.elements:
        return None   # a count over zero extracted elements is not evidence (vector facts carry no elements;
                      # the exact vector voters answer those files)
    source = ctx.path.split("/")[1] if "/" in ctx.path else None
    if ctx.intent == "apartments":
        from engine.query.graph import apartment_of
        amap = apartment_of(facts)
        ids = sorted(amap)
        n = len(set(amap.values()))
        by = {e.id: e for e in facts.elements}
        return registry.VoterResult(
            Voter(name=name, value=n, element_ids=ids, runs=[n], note="rooms connected without entrance doors"),
            evidence=[by[i] for i in ids if i in by], unit="count",
            exact=(facts.provenance.fmt or "") in _EXACT_FMT)
    spec = query.spec_for(ctx.intent, ctx.params, source)
    if spec is None:
        return None
    px = ctx.params.get("_px_per_m")
    res = query.run(spec, facts, px)
    if res.value is None:
        return None
    by = {e.id: e for e in facts.elements}
    note = "; ".join(res.notes + [f"rules: {', '.join(res.rule_applied)}"] * bool(res.rule_applied)) or None
    return registry.VoterResult(
        Voter(name=name, value=res.value, element_ids=res.evidence_ids, runs=list(res.runs), note=note),
        evidence=[by[i] for i in res.evidence_ids if i in by], unit=res.unit,
        exact=(facts.provenance.fmt or "") in _EXACT_FMT)


def area_polygons(ctx):
    return _run(ctx, "area_polygons")


def query_engine(ctx):
    from engine.count import INTENTS

    facts = ctx.facts
    if facts is not None and ctx.intent in INTENTS and (facts.provenance.fmt or "") in ("png", "jpg", "jpeg") :
        return None  # detector already answers this; same logic would not be an independent voter
    return _run(ctx, "query_engine")


def register() -> None:
    registry.register_voter("area_polygons", area_polygons, kinds=("area", "length", "volume"))
    registry.register_voter("query_engine", query_engine, kinds=("count",))
