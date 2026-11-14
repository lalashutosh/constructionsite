"""CLI demo: turns a SheetFacts json into a receipt (ProofObject) or a door
schedule CSV. No model calls; everything here is `engine.scale` + `engine.takeoff`.

    python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --vibe standard
    python -m engine.takeoff.demo contracts/fixtures/sample_facts.json --door-schedule
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from contracts.invariants import check as check_invariants
from contracts.proof import Cost, ProofObject, Tier, Voter
from contracts.proof import SheetFacts
from engine.decide.vibe import VIBE_NAMES, load_vibe, vibe_assumptions
from engine.scale import anchors as scale_anchors
from engine.takeoff import area, door_schedule


def _load_facts(path: str) -> SheetFacts:
    with open(path) as f:
        return SheetFacts.model_validate(json.load(f))


def build_floor_area_proof(facts: SheetFacts, vibe_name: str) -> ProofObject:
    t0 = time.perf_counter()
    rooms = [e for e in facts.elements if e.kind == "room"]
    notes: list[str] = []

    if not rooms:
        return ProofObject(
            id="demo-area", question="What is the floor area?", intent="floor_area", kind="area",
            tier=Tier.grey, refusal="no room polygons on this sheet", provenance=facts.provenance,
            cost=Cost(ms=(time.perf_counter() - t0) * 1000),
        )

    info = scale_anchors.solve(facts)
    if info.px_per_m is None:
        qs = scale_anchors.next_question(facts, info)
        for q in qs:
            notes.append(f"need scale: {q.question} (expected area interval reduction ~{q.expected_interval_reduction_pct:.0f}%)")
        return ProofObject(
            id="demo-area", question="What is the floor area?", intent="floor_area", kind="area",
            tier=Tier.grey, refusal="no scale anchor on this sheet", provenance=facts.provenance,
            notes=notes, cost=Cost(ms=(time.perf_counter() - t0) * 1000),
        )

    total_m2 = round(area.apartment_total_m2(rooms, info.px_per_m), 3)
    voters = [Voter(name="polygon_shoelace", value=total_m2, element_ids=[r.id for r in rooms])]

    for pa in facts.printed_areas:
        label_value = pa.get("value_m2")
        if label_value is not None and abs(label_value - total_m2) < 1e-6:
            voters.append(Voter(name="printed_area", value=label_value, note=f"label '{pa.get('text')}'"))

    tier = Tier.green if len({v.value for v in voters}) == 1 and len(voters) >= 2 else Tier.amber

    rel_sigma = info.rel_sigma if info.rel_sigma is not None else 0.3
    lo, hi = area.area_interval(total_m2, rel_sigma)

    if info.needs_user:
        for q in scale_anchors.next_question(facts, info):
            notes.append(f"scale is relative: {q.question} (expected area interval reduction ~{q.expected_interval_reduction_pct:.0f}%)")

    vibe = load_vibe(vibe_name)
    notes.append(f"vibe={vibe_name} (does not change floor area; affects materials.py quantities)")

    return ProofObject(
        id="demo-area", question="What is the floor area?", intent="floor_area", kind="area",
        value=total_m2, unit="m2", interval={"lo": lo, "hi": hi}, tier=tier,
        evidence=rooms, voters=voters, scale=info, provenance=facts.provenance,
        notes=notes, cost=Cost(ms=(time.perf_counter() - t0) * 1000),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="engine.takeoff demo")
    ap.add_argument("facts_path")
    ap.add_argument("--vibe", choices=VIBE_NAMES, default="standard")
    ap.add_argument("--door-schedule", action="store_true")
    args = ap.parse_args(argv)

    facts = _load_facts(args.facts_path)

    if args.door_schedule:
        info = scale_anchors.solve(facts)
        rows = door_schedule.build(facts, scale=info)
        sys.stdout.write(door_schedule.to_csv(rows))
        return 0

    po = build_floor_area_proof(facts, args.vibe)
    problems = check_invariants(po)
    if problems:
        sys.stderr.write("invariant warnings: " + "; ".join(problems) + "\n")
    print(po.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
