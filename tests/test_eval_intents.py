"""Intent classification on real question templates, language guessing, and EN<->other-language pairing."""
from __future__ import annotations

from evalkit.build_localized import build
from evalkit.intents import classify, guess_lang


# Five real question templates (verbatim from evalkit/intents.yaml / docs/recon.md), one per source family.
REAL_TEMPLATES = [
    ("data/cubicasa5k/high_quality-1.png",
     "How many windows are shown on this floor plan?", "windows"),
    ("data/cubicasa5k/high_quality-2.png",
     "How many saunas are on this floor plan?", "saunas"),
    ("data/swiss_dwellings/site1_bldg1_floor1.pdf",
     "How many bathtubs are drawn on this floor plan?", "bathtubs"),
    ("data/swiss_dwellings/site1_bldg1_floor1.pdf",
     "What is the net floor area of apartment A in m2?", "apartment_net_area"),
    ("data/ifc_models/model-1.ifc",
     "What is the total length of all walls on 'Level 1'?", "walls_length_storey"),
]


def test_classify_matches_five_real_templates():
    for path, question, expected_intent in REAL_TEMPLATES:
        intent = classify(question, path)
        assert intent.name == expected_intent, f"{question!r} -> {intent.name}, expected {expected_intent}"


def test_classify_unknown_for_unmatched_question():
    intent = classify("What colour is the roof?", "data/cubicasa5k/high_quality-1.png")
    assert intent.name == "unknown"


def test_classify_params_extracted():
    intent = classify("What is the net floor area of apartment B in m2?",
                       "data/swiss_dwellings/site1_bldg1_floor1.pdf")
    assert intent.name == "apartment_net_area"
    assert intent.params.get("letter") == "B"


def test_guess_lang_heuristic():
    assert guess_lang("How many windows are shown on this floor plan?") == "en"
    assert guess_lang("Kuinka monta ikkunaa pohjapiirustuksessa on?") == "fi"
    assert guess_lang("") == "xx"


def test_pairing_verification_on_synthetic_rows():
    """EN row immediately followed by a translated row (same path/answer/unit) should resolve
    to the English row's intent via the localized map, without touching real dataset files."""
    rows = [
        {"path": "data/cubicasa5k/x-1.png",
         "question": "How many windows are shown on this floor plan?", "answer": 3, "unit": "count"},
        {"path": "data/cubicasa5k/x-1.png",
         "question": "Kuinka monta ikkunaa pohjapiirustuksessa on?", "answer": 3, "unit": "count"},
        {"path": "data/cubicasa5k/x-2.png",
         "question": "How many saunas are on this floor plan?", "answer": 1, "unit": "count"},
        {"path": "data/cubicasa5k/x-2.png",
         "question": "Kuinka monta saunaa pohjapiirustuksessa on?", "answer": 1, "unit": "count"},
    ]
    meta = build(rows, write=False)
    assert meta["n_pairs_formed"] == 2
    assert meta["pairing_pct"] == 100.0
    assert meta["n_localized_candidates"] == meta["n_localized_covered"] == 2


def test_pairing_verification_handles_unpaired_rows():
    """A non-English row with no matching EN predecessor / mismatched answer never counts as covered."""
    rows = [
        {"path": "data/cubicasa5k/y-1.png",
         "question": "How many windows are shown on this floor plan?", "answer": 2, "unit": "count"},
        {"path": "data/cubicasa5k/y-1.png",
         "question": "Kuinka monta ikkunaa pohjapiirustuksessa on?", "answer": 9, "unit": "count"},  # mismatched
    ]
    meta = build(rows, write=False)
    assert meta["n_pairs_formed"] == 0
    assert meta["n_localized_candidates"] == 1
    assert meta["n_localized_covered"] == 0
    assert meta["pairing_pct"] == 0.0
