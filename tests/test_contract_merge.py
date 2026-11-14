from contracts import invariants
from contracts.proof import Cost, ProofObject, Provenance


def _po(**kw):
    return ProofObject(id="t", question="q", provenance=Provenance(file="data/x.png"), **kw)


def test_planner_answer_needs_query_spec():
    assert any("query_spec" in b for b in invariants.check(_po(cost=Cost(llm_calls=1, planner_calls=1))))


def test_planner_answer_with_spec_passes():
    assert invariants.check(_po(cost=Cost(llm_calls=1, planner_calls=1), query_spec={"select": "room"})) == []


def test_new_fields_default_empty():
    po = _po()
    assert po.query_spec is None and po.cost.planner_calls == 0
