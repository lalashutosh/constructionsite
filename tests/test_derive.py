"""Derived quantities (tiles, paint, ...): every expected value is hand-computed in the comment above it."""
from __future__ import annotations

import pytest

from contracts.proof import Element, ProofObject, Provenance, ScaleAnchor, ScaleInfo, Tag, Tier
from engine.answer_text import sentence
from engine.takeoff import derive


def _room(w_m: float, h_m: float, ppm: float = 10.0, subtype: str = "living") -> Element:
    w, h = w_m * ppm, h_m * ppm
    return Element(id="r1", kind="room", subtype=subtype, polygon=[(0, 0), (w, 0), (w, h), (0, h), (0, 0)])


def _base(area: float, room: Element | None = None, scale: ScaleInfo | None = None, tier: Tier = Tier.amber) -> ProofObject:
    return ProofObject(id="b", question="q", kind="area", value=area, unit="m2", tier=tier, scale=scale,
                       evidence=[room] if room else [], provenance=Provenance(file="f.png"))


DOOR_SCALE = ScaleInfo(px_per_m=10.0, rel_sigma=0.12, widths_relative=True, needs_user=True,
                       anchors=[ScaleAnchor(kind="door_prior", px_per_m=10.0, rel_sigma=0.12, tag=Tag.defaulted)])
REAL_SCALE = ScaleInfo(px_per_m=10.0, rel_sigma=0.02,
                       anchors=[ScaleAnchor(kind="scale_bar", px_per_m=10.0, rel_sigma=0.02, tag=Tag.drawn)])


def test_user_question_parses():
    s = derive.parse("how many 3x3 metre tiles do i need for my living room ?")
    assert (s.kind, s.room, s.tile_w_m, s.tile_h_m, s.size_unit) == ("tiles", "living", 3.0, 3.0, "m")
    assert s.base_question() == "derived quantity base: sum of floor areas of the living room"


def test_user_question_value_is_ceil_of_hand_computation():
    # 19.8 m2 * 1.10 = 21.78 m2; tile 3 x 3 = 9 m2; 21.78 / 9 = 2.42 -> 3 tiles
    s = derive.parse("how many 3x3 metre tiles do i need for my living room ?")
    d = derive.compute(s, 19.8, _base(19.8, _room(4.5, 4.4)))
    assert d.ok and d.value == 3 and d.unit == "tiles"
    assert d.sentence.startswith("You need 3 tiles of 3 x 3 m for the living room (19.8 m² + 10% waste = 21.8 m²; 9 m² per tile).")
    waste = next(a for a in d.assumptions if a.key == "tile_waste_frac")
    assert (waste.value, waste.tag, waste.source) == (0.10, Tag.defaulted, "code table v1")
    size = next(a for a in d.assumptions if a.key == "piece_area_m2")
    assert size.value == 9.0 and size.tag == Tag.chosen


def test_cut_note_when_tile_is_bigger_than_short_side():
    # room 2.5 x 4.0 m: 3 m tile > 2.5 m short side; 10 m2 * 1.1 / 9 = 1.22 -> 2
    s = derive.parse("how many 3x3 metre tiles do i need for my living room ?")
    d = derive.compute(s, 10.0, _base(10.0, _room(2.5, 4.0)))
    assert d.value == 2 and "must be cut" in d.sentence and any("every tile needs cutting" in n for n in d.notes)


def test_30x30_cm_kitchen():
    # 19.8 * 1.1 = 21.78 m2 / 0.09 m2 = 242 tiles exactly (float noise must not give 243)
    s = derive.parse("how many 30x30 cm tiles for the kitchen")
    assert s.room == "kitchen" and s.tile_w_m == pytest.approx(0.3)
    d = derive.compute(s, 19.8, _base(19.8, _room(4.5, 4.4, subtype="kitchen")))
    assert d.value == 242 and "30 x 30 cm" in d.sentence and "0.09 m² per tile" in d.sentence


def test_600x600_mm():
    # 21.78 / 0.36 = 60.5 -> 61
    s = derive.parse("600 x 600 mm tiles in the bedroom, how many?")
    assert s.size_unit == "mm"
    d = derive.compute(s, 19.8, _base(19.8, _room(4.5, 4.4)))
    assert d.value == 61 and "600 x 600 mm" in d.sentence


def test_m2_per_tile_and_inch_and_waste_in_question():
    assert derive.parse("how many tiles of 0.25 m2 each for the whole apartment").tile_area_m2 == 0.25
    assert derive.parse("how many 0.5 m2 per tile tiles for the sauna?").tile_area_m2 == 0.5
    s = derive.parse("how many 12 inch tiles for the hallway")
    assert s.tile_w_m == pytest.approx(0.3048)
    s = derive.parse("how many tiles of 0.6x1.2 m with 15% waste for the whole flat")
    assert s.room is None and s.waste_frac == 0.15 and s.piece_area_m2 == pytest.approx(0.72)
    # 10 * 1.15 / 0.72 = 15.97 -> 16, and the user-stated waste is tagged chosen
    d = derive.compute(s, 10.0, _base(10.0))
    assert d.value == 16
    assert next(a for a in d.assumptions if a.key == "tile_waste_frac").tag == Tag.chosen
    assert derive.parse("how many tiles with no waste for the kitchen").waste_frac == 0.0


@pytest.mark.parametrize("q,room,w", [
    ("kuinka monta 30x30 cm laattaa tarvitsen olohuoneeseen?", "living", 0.3),
    ("Wie viele Fliesen 60x60 cm brauche ich für die Küche?", "kitchen", 0.6),
    ("combien de carreaux de 30 cm pour la cuisine", "kitchen", 0.3),
    ("quante piastrelle 60x60 cm servono per il soggiorno", "living", 0.6),
])
def test_languages(q, room, w):
    s = derive.parse(q)
    assert s.kind == "tiles" and s.room == room and s.tile_w_m == pytest.approx(w)


def test_paint_litres_for_bedroom_walls():
    # room 4.0 x 4.5 m: A = 18 m2, P = 17 m; wall = 17 * 2.5 (defaulted height) = 42.5 m2; 2 coats / 8 m2 per l -> 10.625 l
    s = derive.parse("How much paint do I need for the bedroom walls?")
    assert s.kind == "paint" and s.target == "walls"
    d = derive.compute(s, 18.0, _base(18.0, _room(4.0, 4.5, subtype="bedroom")))
    assert d.value == pytest.approx(10.625, abs=0.06) and d.unit == "l"
    by = {a.key: a for a in d.assumptions}
    assert by["ceiling_height_m"].value == 2.5 and by["ceiling_height_m"].tag == Tag.defaulted
    assert by["paint_coats"].value == 2 and by["paint_coats"].tag == Tag.defaulted
    assert by["paint_coverage_m2_per_l"].value == 8.0
    assert "42.5 m² of wall" in d.sentence and "openings not deducted" in d.sentence


def test_paint_parameters_from_question():
    # 3 coats, 10 m2/l, 2.7 m high: 17 * 2.7 = 45.9 m2 * 3 / 10 = 13.77 -> 13.8
    s = derive.parse("how much paint for the bedroom walls, 3 coats, 10 m2 per litre, ceiling height 2.7 m")
    assert (s.coats, s.coverage_m2_per_l, s.height_m) == (3, 10.0, 2.7)
    d = derive.compute(s, 18.0, _base(18.0, _room(4.0, 4.5)))
    assert d.value == pytest.approx(13.8, abs=0.01)
    assert next(a for a in d.assumptions if a.key == "paint_coats").tag == Tag.chosen
    # the ceiling: 18 m2 * 2 coats / 8 = 4.5 l
    s = derive.parse("how much paint do I need for the bedroom ceiling")
    assert s.target == "ceiling" and derive.compute(s, 18.0, _base(18.0, _room(4.0, 4.5))).value == pytest.approx(4.5, abs=0.05)


def test_lights_carpet_skirting():
    # lights: ceil(300 * 19.8 / (1500 * 0.6)) = ceil(6.6) = 7
    d = derive.compute(derive.parse("how many lights do I need for the living room"), 19.8, _base(19.8, _room(4.5, 4.4)))
    assert d.value == 7
    # carpet 4.5 x 4.4, roll 4.0: strips = ceil(4.4/4) = 2, strip length 4.5*1.1 = 4.95 -> 9.9 m of roll
    d = derive.compute(derive.parse("I need carpet for the bedroom"), 19.8, _base(19.8, _room(4.5, 4.4)))
    assert d.value == pytest.approx(9.9, abs=0.05) and "2 strips" in d.sentence
    # skirting: perimeter 2 * (4.5 + 4.4) = 17.8 m * 1.1 = 19.58 -> 19.6
    d = derive.compute(derive.parse("how much skirting do I need for the living room"), 19.8, _base(19.8, _room(4.5, 4.4)))
    assert d.value == pytest.approx(19.6, abs=0.05)


def test_missing_tile_size_asks_instead_of_guessing():
    s = derive.parse("how many tiles for the bathroom?")
    assert s.missing == ["tile_size"]
    d = derive.compute(s, 6.0, _base(6.0, _room(2.0, 3.0, subtype="bathroom")))
    assert not d.ok and d.value is None and d.tier == Tier.amber and "tile size" in d.refusal
    assert "tell me e.g. 30x30 cm" in d.sentence and "6.0 m²" in d.sentence
    dec = d.decisions[0]
    assert dec.key == "tile_size" and dec.impact > 0
    # 30x30: ceil(6*1.1/0.09) = ceil(73.33) = 74
    assert dec.options[0].total_delta == 74


def test_assumed_scale_is_inherited_and_said():
    s = derive.parse("how many 3x3 metre tiles do i need for my living room ?")
    d = derive.compute(s, 19.8, _base(19.8, _room(4.5, 4.4), scale=DOOR_SCALE, tier=Tier.green))
    assert d.tier == Tier.amber and "no printed scale" in d.sentence and "0.9 m doors" in d.sentence
    # dA/A = 2 * 0.12 -> A in [15.05, 24.55]; ceil(15.05*1.1/9)=2, ceil(24.55*1.1/9)=4
    assert d.interval == (2.0, 4.0)
    d2 = derive.compute(s, 19.8, _base(19.8, _room(4.5, 4.4), scale=REAL_SCALE, tier=Tier.green))
    assert d2.tier == Tier.green and "no printed scale" not in d2.sentence


def test_unmeasurable_base_is_grey():
    s = derive.parse("how many 30x30 cm tiles for the kitchen")
    d = derive.compute(s, None, ProofObject(id="b", question="q", refusal="no kitchen recognised", provenance=Provenance(file="f")))
    assert not d.ok and d.tier == Tier.grey and d.refusal == "no kitchen recognised"


def test_plain_questions_are_not_hijacked():
    for q in ["How many bedrooms are there?", "how many lights are in the plan", "How many tiles are in the bathroom?",
              "On sheet A-801, how many rooms have a ceramic tile base (B2)?", "What is the total area of the living room?",
              "What is the total length of skirting boards needed?"]:
        assert derive.parse(q) is None, q


def test_planner_derive_object_is_validated():
    s = derive.from_obj({"kind": "tiles", "room": "kitchen", "tile_w_m": 0.3, "tile_h_m": 0.3})
    assert s.piece_area_m2 == pytest.approx(0.09)
    for bad in ({"kind": "bricks"}, {"kind": "tiles", "room": "attic"}, {"kind": "tiles", "tile_w_m": -1, "tile_h_m": 1},
                {"kind": "tiles", "tile_w_m": 0.3}, {"kind": "paint", "tile_area_m2": 1}, {"kind": "tiles", "price": 3}, "x"):
        with pytest.raises(ValueError):
            derive.from_obj(bad)


class _FakeEngine:
    """Stands in for PipelineEngine: records which llm the base question ran with and answers a fixed area."""
    llm = None
    planner_llm = None
    classifier = object()

    def ask(self, path, question, **kw):
        import json
        spec = json.loads(self.llm.complete("", "").text)
        po = _base(19.8, _room(4.5, 4.4))
        po.query_spec = spec
        po.cost.llm_calls = po.cost.planner_calls = 1
        po.notes.append(f"base asked: {question}; classifier={self.classifier}")
        return po


def test_answer_runs_base_area_without_an_llm_call():
    eng = _FakeEngine()
    q = "how many 3x3 metre tiles do i need for my living room ?"
    po = derive.answer(eng, "data/x.png", q, derive.parse(q))
    assert po.value == 3 and po.question == q and po.cost.llm_calls == 0
    assert po.query_spec["base"] == {"select": "room", "aggregate": "sum_area", "where": {"room_type": "living"}}
    assert po.answer_text.startswith("You need 3 tiles of 3 x 3 m for the living room")
    assert po.evidence and eng.llm is None and eng.classifier is not None     # live engine untouched
    assert any("classifier=None" in n for n in po.notes)
    assert ProofObject.model_validate(po.model_dump(mode="json")).value == 3


def test_room_label_is_never_pluralised_from_a_code():
    spec = {"select": "room", "where": {"room_type": "living"}, "aggregate": "sum_area"}
    two = ProofObject(id="x", question="q", kind="area", unit="m2", value=19.8, query_spec=spec, provenance=Provenance(file="f"),
                      evidence=[_room(3, 3), _room(3, 3).model_copy(update={"id": "r2"})])
    assert sentence(two) == "The living rooms cover 19.8 m² in total."
    one = two.model_copy(update={"evidence": two.evidence[:1]})
    assert sentence(one) == "The living room covers 19.8 m²."


def test_unmeasured_base_gives_reason_not_a_number():
    s = derive.parse("how many 30x30 cm tiles do I need for the dining area?")
    base = _base(75.2)
    base.value = None
    base.refusal = "no dining recognised on this drawing"
    po = derive.wrap(base, s, "q")
    assert po.value is None and po.tier == Tier.grey
    assert po.answer_text == "I can't count tiles for the dining room: no dining recognised on this drawing."


def test_planner_tolerates_and_validates_a_derive_object():
    from types import SimpleNamespace
    from contracts.proof import SheetFacts
    from engine.query import planner
    facts = SheetFacts(provenance=Provenance(file="f"), elements=[_room(3, 3)])

    class L:
        def __init__(self, text):
            self.text = text

        def complete(self, system, user, max_tokens=0):
            return SimpleNamespace(text=self.text, tokens_in=1, tokens_out=1, usd=0.0)

    ok = ('{"select":"room","where":{"room_type":"living"},"aggregate":"sum_area",'
          '"derive":{"kind":"tiles","room":"living","tile_w_m":0.3,"tile_h_m":0.3}}')
    p = planner.plan("q", facts, L(ok))
    assert p.specs[0]["aggregate"] == "sum_area" and p.derive.piece_area_m2 == pytest.approx(0.09)
    with pytest.raises(planner.PlannerError):
        planner.plan("q", facts, L(ok.replace('"tiles"', '"bricks"')))
