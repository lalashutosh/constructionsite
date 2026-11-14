import json

from contracts.proof import Element, Provenance, SheetFacts
from engine.scale import printed_dims


def _facts():
    # two windows 156 px and 84 px long: 248x149 and 133x149 labels -> 62.9 and 63.2 px/m (agree)
    win = lambda i, x, L: Element(id=f"w{i}", kind="window", polygon=[(x, 10), (x + L, 10), (x + L, 16), (x, 16)])
    return SheetFacts(provenance=Provenance(file="f"), width_px=900, height_px=600,
                      elements=[win(1, 100, 156), win(2, 500, 84), win(3, 800, 40)])


def test_two_agreeing_printed_sizes_give_a_specified_scale(tmp_path, monkeypatch):
    monkeypatch.setattr(printed_dims, "CACHE", tmp_path)
    toks = [{"text": "248x149", "w_m": 2.48, "x": 178, "y": 30, "conf": 90},
            {"text": "133x149", "w_m": 1.33, "x": 542, "y": 30, "conf": 90},
            {"text": "248x149", "w_m": 2.48, "x": 820, "y": 30, "conf": 90}]      # misread / wrong match: disagrees
    (tmp_path / "abc-v2.json").write_text(json.dumps(toks))
    a = printed_dims.anchor(_facts(), "unused.png", "abc")
    assert a is not None and a.tag.value == "specified" and a.kind == "dimension"
    assert 62 < a.px_per_m < 64 and "1 other labels disagreed" in a.note


def test_one_label_is_not_enough(tmp_path, monkeypatch):
    monkeypatch.setattr(printed_dims, "CACHE", tmp_path)
    (tmp_path / "one-v2.json").write_text(json.dumps([{"text": "248x149", "w_m": 2.48, "x": 178, "y": 30, "conf": 90}]))
    assert printed_dims.anchor(_facts(), "unused.png", "one") is None
