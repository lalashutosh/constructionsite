"""Big-sheet path: router phrasings, sheet profile, line-geometry rooms (synthetic sheet, no dataset needed)."""
import cv2
import numpy as np
import pytest

from engine import bigsheet, profile
from engine.router import route, sheet_intent


@pytest.mark.parametrize("q,intent", [
    ("What is the total area of all rooms?", "total_room_area"),
    ("What is the combined area of every room?", "total_room_area"),
    ("How big is the building?", "total_room_area"),
    ("What's the square footage?", "total_room_area"),
    ("What is the sum of all room sizes", "total_room_area"),
    ("Mikä on huoneiden kokonaispinta-ala?", "total_room_area"),
    ("Wie groß ist die Gesamtfläche?", "total_room_area"),
    ("How many rooms are there?", "rooms_count"),
    ("hur många rum finns det?", "rooms_count"),
    ("Which is the largest room?", "largest_room"),
    ("What is the overall length and width of the building?", "overall_size"),
    ("What is the scale of this drawing?", "scale_info"),
])
def test_sheet_intents(q, intent):
    r = route(q, "cache/x.png")
    assert (r.intent, r.layer) == (intent, "sheet")
    assert r.kind != "count" or intent == "rooms_count"       # an area question is never answered with a count


@pytest.mark.parametrize("q", ["total area of the bedrooms", "What is the area of the dining room?", "area of the guest room",
                               "how many bedrooms", "How many doors?"])
def test_typed_rooms_are_not_sheet_level(q):
    assert sheet_intent(q) is None or sheet_intent(q)[0] not in ("total_room_area", "rooms_count")


def _sheet() -> np.ndarray:
    img = np.full((1100, 1700, 3), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (1680, 1080), (0, 0, 0), 2)                  # border
    cv2.line(img, (1400, 20), (1400, 1080), (0, 0, 0), 2)                     # title block edge
    for k, t in enumerate(["SHEET", "SCALE", "DATE", "DRAWN", "PROJECT"]):
        cv2.putText(img, t, (1420, 100 + 60 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.rectangle(img, (200, 200), (1100, 800), (0, 0, 0), 14)               # outer walls
    cv2.line(img, (650, 200), (650, 800), (0, 0, 0), 14)                      # partition -> two rooms
    return img


def test_profile_and_rooms(tmp_path):
    f = tmp_path / "sheet.png"
    cv2.imwrite(str(f), _sheet())
    prof = profile.profile(str(f), "synthetic-sha", use_cache=False)
    assert prof["sheet_type"] == "cad_sheet" and prof["route"] == "line_geometry"
    assert prof["title_block"] and prof["title_block"][0] > 1300
    assert prof["main_view"][2] < 1400                                       # the plan view excludes the title block
    words = [{"text": "KITCHEN", "box": [300, 480, 420, 520], "conf": 95.0, "angle": 0},
             {"text": "HALL", "box": [800, 480, 900, 520], "conf": 95.0, "angle": 0}]
    img = cv2.imread(str(f))
    els = bigsheet.elements(img, {**prof, "width_px": 1700, "height_px": 1100}, words)
    rooms = [e for e in els if e.kind in ("room", "region")]
    assert len(rooms) == 2
    assert {e.label for e in rooms} == {"KITCHEN", "HALL"}
    assert any(e.kind == "footprint" for e in els)


def test_cubicasa_scan_is_never_routed_as_cad_sheet():
    """Dimension lines can look like a sheet frame; the dataset source overrides the profile (DEV must not regress)."""
    import glob, os
    from engine.pipeline import PipelineEngine
    fs = sorted(glob.glob(os.path.join(os.environ.get("DATASET_ROOT", ""), "data/cubicasa5k/*.png")))[:25]
    if not fs:
        pytest.skip("dataset not available")
    for f in fs:
        assert PipelineEngine._profile(f)["sheet_type"] != "cad_sheet"
