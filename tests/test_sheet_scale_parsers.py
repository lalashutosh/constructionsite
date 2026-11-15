import pytest

from engine.scale import sheet_scale as SS


def _label(text, cx, cy=55.0, w=10.0, h=10.0, conf=90, angle=0):
    return {"text": text, "box": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
            "conf": conf, "angle": angle}


# --------------------------------------------------------------------------- parse_note
def test_parse_note_imperial_half_inch():
    p = SS.parse_note('SCALE: 1/2" = 1\'-0"')
    assert p["ratio"] == pytest.approx(24.0)
    assert p["system"] == "imperial"


def test_parse_note_imperial_one_inch_40ft():
    assert SS.parse_note('1" = 40\'-0"')["ratio"] == pytest.approx(480.0)


def test_parse_note_metric():
    p = SS.parse_note("SCALE 1:50")
    assert p["ratio"] == pytest.approx(50.0)
    assert p["system"] == "metric"


def test_parse_note_quarter_inch():
    assert SS.parse_note('SCALE 1/4"=1\'-0"')["ratio"] == pytest.approx(48.0)


def test_parse_note_not_to_scale():
    p = SS.parse_note("NOT TO SCALE")
    assert p is not None
    assert p.get("none") is True


def test_parse_note_date_is_none():
    assert SS.parse_note("10/5/2015 1:18:25 PM") is None


def test_parse_note_three_inch():
    assert SS.parse_note('3" = 1\'-0"')["ratio"] == pytest.approx(4.0)


# --------------------------------------------------------------------------- parse_dim
def test_parse_dim_ftin_323():
    r = SS.parse_dim("323'-4\"")
    assert len(r) == 1
    assert r[0]["m"] == pytest.approx(98.552, rel=1e-4)
    assert r[0]["kind"] == "ftin"
    assert r[0]["lax"] is False


def test_parse_dim_ftin_52():
    r = SS.parse_dim("52'-8\"")
    assert r[0]["m"] == pytest.approx(16.0528, rel=1e-4)


def test_parse_dim_lax_foot_mark_lost():
    r = SS.parse_dim('133-10"')
    assert r[0]["lax"] is True
    assert r[0]["m"] == pytest.approx(40.8, abs=0.05)


def test_parse_dim_mm():
    r = SS.parse_dim("27500")
    assert r[0]["m"] == pytest.approx(27.5)
    assert r[0]["kind"] == "mm"


def test_parse_dim_metres():
    assert SS.parse_dim("12.5 m")[0]["m"] == pytest.approx(12.5)


def test_parse_dim_garbage():
    assert SS.parse_dim("foo") == []


def test_parse_dim_year_like():
    assert SS.parse_dim("1999") == []


def test_parse_dim_inches_ge_12_invalid():
    assert SS.parse_dim("12'-14\"") == []


# --------------------------------------------------------------------------- paper_info
def test_paper_info_ansi_d_std_dpi():
    p = SS.paper_info(5100, 3300, None)
    assert p["px_per_in"] == pytest.approx(150.0)
    assert p["name"] == "ANSI D 34x22"
    assert "ANSI B 17x11" in p["ambiguous"]
    assert p["sigma"] == pytest.approx(0.05)


def test_paper_info_small_raster_guess():
    p = SS.paper_info(768, 497, None)
    assert p["px_per_in"] == pytest.approx(22.588, rel=1e-3)
    assert p["sigma"] == pytest.approx(0.25)


def test_paper_info_pdf_exact():
    p = SS.paper_info(2000, 1290, {"w_in": 34.0, "h_in": 22.0, "zoom": 2000 / 2448})
    assert p["exact"] is True
    assert p["px_per_in"] == pytest.approx(58.82, rel=1e-3)


# --------------------------------------------------------------------------- find_bars
def test_find_bars_simple():
    ws = [_label("0", 100), _label("2", 200), _label("4'", 300)]
    bars = SS.find_bars(ws)
    assert len(bars) == 1
    b = bars[0]
    assert b["unit"] == "ft"
    assert b["ppu"] == pytest.approx(50.0, rel=1e-6)
    assert b["vals"] == [0.0, 2.0, 4.0]


def test_find_bars_negative_subdivision():
    ws = [_label("2", 0), _label("0", 100), _label("2", 200), _label("4", 300)]
    bars = SS.find_bars(ws)
    assert len(bars) == 1
    b = bars[0]
    assert b["vals"] == [-2.0, 0.0, 2.0, 4.0]
    assert b["ppu"] == pytest.approx(50.0, rel=1e-6)


# --------------------------------------------------------------------------- consensus / confidence
def _cand(cid, family, ppm, weight, tag, conf, members=None):
    c = {"id": cid, "kind": family, "family": family, "ppm": ppm, "sigma": 0.05, "tag": tag,
         "label": cid, "boxes": [], "conf": conf, "weight": weight, "note": ""}
    if members is not None:
        c["members"] = members
    return c


def test_consensus_three_families():
    cands = [
        _cand("ratio", "ratio", 246.0, 0.6, "defaulted", 0.9),
        _cand("bar", "bar", 245.0, 1.0, "drawn", 0.9),
        _cand("dim", "dim", 250.0, 1.0, "specified", 0.9, members=1),
    ]
    cons = SS.consensus(cands)
    assert cons["winner"]["families"] == ["bar", "dim", "ratio"]
    assert cons["conflict"] is False
    conf = SS.confidence({}, cons)
    assert 0.8 <= conf <= 0.99


def test_confidence_single_dim_low():
    cands = [_cand("dim", "dim", 250.0, 1.0, "specified", 0.9, members=1)]
    cons = SS.consensus(cands)
    assert SS.confidence({}, cons) < 0.5


def test_consensus_conflict_two_groups():
    cands = [
        _cand("bar", "bar", 100.0, 1.0, "drawn", 0.9),
        _cand("dim", "dim", 300.0, 1.0, "specified", 0.9, members=2),
    ]
    cons = SS.consensus(cands)
    assert cons["conflict"] is True


def test_family_q_ratio_specified():
    c = _cand("ratio", "ratio", 246.0, 1.0, "specified", 0.9)
    assert SS.family_q(c) == pytest.approx(0.70)
