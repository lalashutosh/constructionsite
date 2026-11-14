"""Generate contract fixtures. UI work starts from these before any backend exists.
Run:  python scripts/make_fixtures.py      (idempotent)
Fixtures are SYNTHETIC demo data. Never show them as results on a real drawing.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts import invariants  # noqa: E402
from contracts.proof import (  # noqa: E402
    Assumption, Cost, Decision, Element, Interval, Option, ProofObject, Provenance,
    ScaleAnchor, ScaleInfo, SheetFacts, Tag, Tier, Voter,
)

OUT = ROOT / "contracts" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)


def rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]


prov = Provenance(
    file="data/cubicasa5k/SYNTHETIC-DEMO.png", fmt="png",
    license="SYNTHETIC demo fixture", credit="Synthetic fixture, not a real drawing",
)

# A 400x500 px "flat": 4 m x 5 m room at 100 px/m, plus 7 doors in a row of the strip below it.
room = Element(id="room1", kind="room", subtype="living", polygon=rect(40, 40, 400, 500), label="OH", conf=0.9)
doors = [
    Element(id=f"d{i}", kind="door", polygon=rect(60 + i * 50, 560, 30, 12), conf=0.95 if i != 3 else 0.55,
            attrs={"width_px": 90 if i != 3 else 70})
    for i in range(7)
]
windows = [Element(id=f"w{i}", kind="window", polygon=rect(80 + i * 120, 30, 70, 8), conf=0.9) for i in range(3)]

scale_unknown = ScaleInfo(
    px_per_m=None, rel_sigma=None, needs_user=True,
    anchors=[ScaleAnchor(kind="door_prior", px_per_m=100.0, rel_sigma=0.12, tag=Tag.defaulted,
                         note="median door leaf 0.9 m (assumed)", element_ids=["d0", "d1"])],
    widths_relative=True,
)

facts = SheetFacts(
    provenance=prov, sheet_type="floor_plan", legible=True, width_px=480, height_px=620, language="fi",
    elements=[room, *doors, *windows], scale=scale_unknown,
    printed_areas=[{"text": "20.0 m2", "value_m2": 20.0, "polygon": rect(200, 260, 80, 20)}],
)

po_doors = ProofObject(
    id="demo-doors", question="How many doors are in this apartment?", intent="doors", kind="count", value=7,
    unit="count", tier=Tier.amber,
    evidence=doors,
    voters=[
        Voter(name="detector", value=7, element_ids=[d.id for d in doors], runs=[7, 7, 8, 7, 7, 6, 7, 7]),
        Voter(name="arc_geometry", value=6, element_ids=[d.id for d in doors if d.id != "d3"],
              note="d3 has no swing arc: open doorway without a leaf?"),
    ],
    provenance=prov, cost=Cost(ms=1620.0),
    notes=["Voters disagree on d3. Question asks for doorways fitted with a leaf."],
)

po_area = ProofObject(
    id="demo-area", question="What is the floor area?", intent="floor_area", kind="area", value=20.0, unit="m2",
    interval=Interval(lo=12.4, hi=31.0), tier=Tier.amber, evidence=[room],
    voters=[Voter(name="polygon_shoelace", value=20.0, element_ids=["room1"]),
            Voter(name="printed_area", value=20.0, note="label '20.0 m2' inside room1")],
    scale=ScaleInfo(px_per_m=100.0, rel_sigma=0.12,
                    anchors=[ScaleAnchor(kind="printed_area", px_per_m=100.0, rel_sigma=0.02, tag=Tag.specified,
                                         note="printed 20.0 m2 equals polygon at 100 px/m", element_ids=["room1"]),
                             ScaleAnchor(kind="door_prior", px_per_m=100.0, rel_sigma=0.12, tag=Tag.defaulted)]),
    assumptions=[Assumption(key="scale", value=100.0, unit="px/m", tag=Tag.specified, source="printed label")],
    decisions_open=[Decision(
        key="door_leaf_m", question="Door leaf width?", default=0.9, impact=0.0,
        options=[Option(value=0.8, label="0.8 m", fits=True), Option(value=0.9, label="0.9 m", fits=True),
                 Option(value=1.0, label="1.0 m", fits=False, note="opening too narrow without widening")])],
    provenance=prov, cost=Cost(ms=40.0),
)

po_grey = ProofObject(
    id="demo-refusal", question="How many doors are in this drawing?", intent="doors", kind="count", value=None,
    tier=Tier.grey, refusal="Sheet looks like an elevation (no walls/rooms found). I will not count doors here.",
    provenance=Provenance(file="data/europeana/SYNTHETIC-ELEVATION.jpg", fmt="jpg", credit="Synthetic fixture"),
)

for name, obj in [("sample_facts", facts), ("sample_proof_doors", po_doors), ("sample_proof_area", po_area),
                  ("sample_proof_refusal", po_grey)]:
    (OUT / f"{name}.json").write_text(json.dumps(json.loads(obj.model_dump_json()), indent=2))
    if isinstance(obj, ProofObject):
        problems = invariants.check(obj)
        print(f"{name}: {'OK' if not problems else problems}")
    else:
        print(f"{name}: written")
