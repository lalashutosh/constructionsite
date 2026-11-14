import json
import pathlib

from engine.router import lolo_accuracy, normalise, route

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_regex_layer_en_and_localized():
    r = route("How many windows are shown on this floor plan?", "data/cubicasa5k/a.png")
    assert (r.intent, r.layer, r.kind) == ("windows", "regex", "count")
    r = route("Kuinka monta ikkunaa pohjapiirustuksessa on?", "data/cubicasa5k/a.png")
    assert r.intent == "windows"


def test_normalise_strips_digits_and_quotes():
    assert normalise("Room 12 'Küche' on 'EG'") == normalise("Room 7 'Bad' on 'OG'")


def test_ngram_layer_catches_unseen_phrasing():
    r = route("how many windows are shown on this floor plan ?!", "data/cubicasa5k/a.png")
    assert r.intent == "windows"


def test_unknown_without_llm():
    r = route("what colour is the sky", "data/cubicasa5k/a.png")
    assert r.intent == "unknown" and r.layer == "none"


def test_leave_one_language_out_report():
    res = lolo_accuracy()
    assert res["n_templates"] > 100 and res["overall"] > 0.6
    out = ROOT / "docs" / "claims" / "integrator.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"router_lolo": res["overall"]}) + "\n")
    assert json.loads(out.read_text())["router_lolo"] == res["overall"]


# Paraphrases that are NOT in the dataset (router robustness; not the hard set, never used for scoring).
PARAPHRASES = [
    ("How many doors are there on this floor plan?", "data/swiss_dwellings/x.pdf", "doors"),
    ("How many doors are shown on this floor plan?", "data/swiss_dwellings/x.pdf", "doors"),
    ("How many doors are there on this floor plan?", "data/cubicasa5k/x.png", "doors"),
    ("Count the windows in this plan.", "data/cubicasa5k/x.png", "windows"),
    ("How many toilets are in this apartment?", "data/cubicasa5k/x.png", "toilets"),
    ("Wie viele Türen gibt es auf diesem Grundriss?", "data/swiss_dwellings/x.pdf", "doors"),
    ("How big is apartment B in square metres, without balconies?", "data/swiss_dwellings/x.pdf", "apartment_net_area"),
    ("How many WCs are there?", "data/cubicasa5k/x.png", "wc_rooms"),
]


def test_lexicon_routes_paraphrases():
    for q, p, want in PARAPHRASES:
        assert route(q, p).intent == want, q


def test_lexicon_abstains_on_area_of_counted_object():
    # an area question about a kitchen must never become the kitchen COUNT
    assert route("What is the floor area of the kitchen?", "data/cubicasa5k/x.png").intent != "kitchens"


def test_complex_questions_are_not_hijacked_by_simple_intents():
    from engine.router import is_complex
    assert is_complex("What is the average room area in apartment B?")
    assert is_complex("Are there more windows than doors?")
    assert is_complex("Which room is the largest?")
    assert not is_complex("How many windows are drawn on this floor plan?")   # dataset template
    assert not is_complex("How big is apartment B in square metres, without balconies?")


def test_kind_clash_and_have_a_go_to_the_planner():
    from engine.router import is_complex
    assert is_complex("How many rooms have a window?")
    # area wording on a count-only intent is not that intent (no LLM here -> flagged fallback or unknown)
    r = route("What is the total area of all bedrooms?", "data/cubicasa5k/x.png")
    assert r.layer in ("complex", "regex-complex") or r.intent == "unknown"


def test_uploaded_scan_routes_like_a_scanned_plan():
    up = "/Users/x/constructionsite/cache/uploads/4f40e3.png"
    assert route("How many bedrooms are there?", up).intent == "bedrooms"
    assert route("How many bedrooms are there?", "data/cubicasa5k/colorful-2002.png").intent == "bedrooms"
