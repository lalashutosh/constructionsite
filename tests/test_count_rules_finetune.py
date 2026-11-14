"""Counting rules learned from the answered DEV questions (docs/handoff/raster-finetune.md)."""
import os
import pathlib

import pytest

from contracts.proof import Element, Provenance, SheetFacts
from engine.count import count


def _facts(elements):
    return SheetFacts(provenance=Provenance(file="x.png", sha256="0", fmt="png"),
                      sheet_type="floor_plan", legible=True, width_px=400, height_px=300,
                      elements=elements)


def _box(x, y, w=20, h=10):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _label(i, sub, x, y, conf=0.9, claimed=False):
    return Element(id=f"label_{i}", kind="label", subtype=sub, polygon=_box(x, y), label=sub.upper(),
                   conf=conf, attrs={"claimed": claimed})


def test_bedrooms_labels_beat_cnn_when_more():
    # "How many bedrooms (makuuhuone, usually marked MH)": MH 1 + MH 2 => 2 although the CNN
    # produced a single merged bedroom room
    room = Element(id="room_bedroom_0", kind="room", subtype="bedroom", polygon=_box(10, 10, 100, 100))
    f = _facts([room, _label(1, "bedroom", 20, 20, claimed=True), _label(2, "bedroom", 300, 200)])
    assert count("bedrooms", f)[0] == 2
    # a claimed label inside its room must not be counted twice
    assert count("bedrooms", _facts([room, _label(1, "bedroom", 90, 90, claimed=True)]))[0] == 1


def test_bedrooms_duplicate_ocr_hits_collapse():
    f = _facts([_label(1, "bedroom", 20, 20), _label(2, "bedroom", 22, 21)])
    assert count("bedrooms", f)[0] == 1


def test_saunas_bench_icon_wins_over_labels():
    bench = Element(id="sauna_bench_0", kind="sauna_bench", polygon=_box(5, 5), conf=0.9)
    f = _facts([bench, _label(1, "sauna", 100, 100), _label(2, "sauna", 300, 200)])
    assert count("saunas", f)[0] == 1


def test_saunas_label_fallback_needs_confidence():
    f = _facts([_label(1, "sauna", 100, 100, conf=0.3)])
    assert count("saunas", f)[0] == 0
    f = _facts([_label(1, "sauna", 100, 100, conf=0.9)])
    assert count("saunas", f)[0] == 1


_ROOT = os.environ.get("DATASET_ROOT")


@pytest.mark.skipif(not _ROOT or not (pathlib.Path(_ROOT).expanduser() / "data/cubicasa5k/colorful-2002.png").exists(),
                    reason="dataset not available")
def test_colorful_2002_has_two_bedrooms():
    from engine.raster import extract
    from engine.raster import model
    if not model.available():
        pytest.skip("weights not available")
    facts = extract.extract(str(pathlib.Path(_ROOT).expanduser() / "data/cubicasa5k/colorful-2002.png"))
    assert count("bedrooms", facts)[0] == 2
