import json
import pathlib

import pytest

from contracts import invariants
from contracts.proof import (
    Cost, Element, Interval, ProofObject, Provenance, ScaleAnchor, ScaleInfo, SheetFacts, Tag, Tier, Voter,
)

FIX = pathlib.Path(__file__).resolve().parents[1] / "contracts" / "fixtures"
PROV = Provenance(file="data/x/y.png")


@pytest.mark.parametrize("p", sorted(FIX.glob("sample_proof_*.json")), ids=lambda p: p.stem)
def test_fixture_proofs_are_valid(p):
    po = ProofObject.model_validate(json.loads(p.read_text()))
    assert invariants.check(po) == []


def test_fixture_facts_roundtrip():
    f = SheetFacts.model_validate(json.loads((FIX / "sample_facts.json").read_text()))
    assert f.sheet_type == "floor_plan" and f.elements


def test_green_requires_agreeing_voters():
    po = ProofObject(id="a", question="q", value=3, tier=Tier.green, provenance=PROV,
                     voters=[Voter(name="a", value=3), Voter(name="b", value=4)])
    assert any("agree" in m for m in invariants.check(po))


def test_grey_needs_refusal():
    po = ProofObject(id="a", question="q", tier=Tier.grey, provenance=PROV)
    assert any("refusal" in m for m in invariants.check(po))


def test_door_prior_only_must_be_relative():
    sc = ScaleInfo(px_per_m=100, rel_sigma=0.1,
                   anchors=[ScaleAnchor(kind="door_prior", px_per_m=100, rel_sigma=0.1, tag=Tag.defaulted)])
    po = ProofObject(id="a", question="q", kind="area", value=10.0, unit="m2", tier=Tier.amber, scale=sc,
                     provenance=PROV)
    assert any("circular" in m for m in invariants.check(po))
    sc.widths_relative = True
    assert invariants.check(po) == []


def test_area_without_scale_is_flagged():
    po = ProofObject(id="a", question="q", kind="area", value=10.0, tier=Tier.amber, provenance=PROV)
    assert any("scale" in m for m in invariants.check(po))


def test_count_must_be_int():
    po = ProofObject(id="a", question="q", kind="count", value=2.5, tier=Tier.amber, provenance=PROV)
    assert any("int" in m for m in invariants.check(po))
