from __future__ import annotations

from contracts.proof import Tag
from engine.decide import ledger


# ---------------------------------------------------------------------------
# impact = max(Q(o)) - min(Q(o)) over options that fit; top 3 ranked first
# ---------------------------------------------------------------------------


def test_impact_hand_computed_and_ranked_descending():
    # paint coats decision: 1/2/3 coats on a fixed 45 m^2 net wall / 9 m2/l coverage
    coats_spec = ledger.DecisionSpec(
        key="paint_coats", question="How many coats?", options=[(1, "1 coat"), (2, "2 coats"), (3, "3 coats")],
        default=2, quantity_fn=lambda c: c * 45.0 / 9.0,  # 5, 10, 15 litres
    )
    # tile waste decision: small spread
    waste_spec = ledger.DecisionSpec(
        key="tile_waste", question="Waste factor?", options=[(0.08, "8%"), (0.10, "10%"), (0.12, "12%")],
        default=0.10, quantity_fn=lambda w: 20.0 * (1 + w) / 0.09,
    )
    decisions = ledger.rank([coats_spec, waste_spec])
    # coats impact = 15-5 = 10 litres; waste impact = 20*1.12/0.09 - 20*1.08/0.09 = (24.89-24.0)=0.89 approx
    assert decisions[0].key == "paint_coats"
    assert decisions[0].impact == 10.0
    assert decisions[1].key == "tile_waste"
    assert decisions[1].impact < decisions[0].impact


def test_top_three_are_tagged_open_rest_defaulted():
    specs = []
    for i in range(5):
        specs.append(
            ledger.DecisionSpec(
                key=f"d{i}", question=f"q{i}?",
                options=[(0, "a"), (1, "b")],
                default=0,
                # decision i has impact i (0,1,2,3,4) so order after ranking is reversed
                quantity_fn=lambda v, i=i: v * i,
            )
        )
    decisions = ledger.rank(specs)
    assert [d.tag for d in decisions[:3]] == [Tag.open, Tag.open, Tag.open]
    assert [d.tag for d in decisions[3:]] == [Tag.defaulted, Tag.defaulted]
    # ranked descending by impact
    impacts = [d.impact for d in decisions]
    assert impacts == sorted(impacts, reverse=True)


# ---------------------------------------------------------------------------
# option fit filtering: never silently drop, always show fits=False + reason
# ---------------------------------------------------------------------------


def test_door_leaf_fit_filters_by_opening_width():
    fits_fn = ledger.door_leaf_fit(opening_width_m=0.9)
    spec = ledger.DecisionSpec(
        key="door_leaf", question="Leaf width?",
        options=[(0.8, "0.8 m"), (0.9, "0.9 m"), (1.0, "1.0 m")],
        default=0.9, quantity_fn=lambda w: w, fits_fn=fits_fn,
    )
    decisions = ledger.rank([spec])
    opts = {o.label: o for o in decisions[0].options}
    assert opts["0.8 m"].fits is True
    assert opts["0.9 m"].fits is True
    assert opts["1.0 m"].fits is False
    assert "too narrow" in opts["1.0 m"].note
    # impact only considers options that fit: max(0.9,0.8) - min(0.9,0.8) = 0.1
    assert decisions[0].impact == 0.1


def test_clear_passage_minimum_also_filters():
    fits_fn = ledger.door_leaf_fit(opening_width_m=1.2, clear_passage_min_m=0.8)
    spec = ledger.DecisionSpec(
        key="door_leaf", question="Leaf width?",
        options=[(0.7, "0.7 m"), (0.9, "0.9 m")],
        default=0.9, quantity_fn=lambda w: w, fits_fn=fits_fn,
    )
    decisions = ledger.rank([spec])
    opts = {o.label: o for o in decisions[0].options}
    assert opts["0.7 m"].fits is False
    assert opts["0.9 m"].fits is True
