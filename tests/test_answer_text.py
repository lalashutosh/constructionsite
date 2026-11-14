from contracts.proof import ProofObject, Provenance
from engine.answer_text import sentence


def _po(**k):
    return ProofObject(id="x", question="q", provenance=Provenance(file="f"), **k)


def test_sentences_carry_the_computed_value():
    assert sentence(_po(kind="count", intent="doors", value=6)) == "There are 6 doors."
    assert sentence(_po(kind="count", intent="bedrooms", value=1)) == "There is 1 bedroom."
    assert sentence(_po(kind="count", intent="saunas", value=0)) == "No saunas found on this drawing."
    po = _po(kind="area", unit="m2", value=7.0, query_spec={"select": "room", "where": {"room_type": "bathroom"},
                                                            "aggregate": "sum_area"})
    assert sentence(po) == "The bathrooms cover 7.0 m² in total."
    po = _po(kind="text", value="No", query_spec={"parts": [{"select": "window", "aggregate": "count"},
                                                           {"select": "door", "aggregate": "count"}], "combine": "greater"},
             notes=["query parts: part1=6, part2=6"])
    assert sentence(po) == "No: 6 windows vs 6 doors."
    assert sentence(_po(value=None, refusal="the sheet is a photo")) == "I can't answer this from the drawing: the sheet is a photo."
