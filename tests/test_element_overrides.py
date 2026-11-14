"""User element overrides (engine/overrides_el.py): retype / remove / undo recompute counts, tag 'chosen', receipt note."""
import pytest
from fastapi.testclient import TestClient

import api.main as M
from contracts.proof import Element, Provenance, SheetFacts
from engine import cache as facts_cache
from engine import overrides_el as OV
from engine import pipeline as P
from engine import registry as R
from engine.count import count

PATH = "data/cubicasa5k/a.png"
SHA = "f" * 64


def _sq(i, kind, x=0):
    return Element(id=f"{kind}{i}", kind=kind, polygon=[(x, 0), (x + 10, 0), (x + 10, 10), (x, 10)], conf=0.8)


def _facts():
    els = [_sq(i, "door", 20 * i) for i in range(3)] + [_sq(i, "window", 100 + 20 * i) for i in range(2)]
    els.append(Element(id="room0", kind="room", subtype="bedroom", polygon=[(0, 50), (60, 50), (60, 90), (0, 90)]))
    return SheetFacts(provenance=Provenance(file=PATH, fmt="png"), sheet_type="floor_plan", elements=els,
                      extras={"cnn_runs": {"door": [3, 3, 3], "window": [2, 2, 2]}})


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(OV, "DIR", tmp_path / "element_overrides")


def test_retype_door_to_window_changes_both_counts():
    OV.add(SHA, "door0", "retype", kind="window")
    f = OV.apply(_facts(), SHA)
    assert count("doors", f)[0] == 2 and count("windows", f)[0] == 3
    e = next(e for e in f.elements if e.id == "door0")
    assert e.kind == "window" and e.conf == 1.0
    assert e.attrs["user_override"] == {"from_kind": "door", "from_subtype": None, "tag": "chosen"}
    assert count("doors", f)[2] == [2, 2, 2]               # per-run counts shift with the user's decision


def test_remove_drops_count_and_keeps_original():
    OV.add(SHA, "window1", "remove")
    f = OV.apply(_facts(), SHA)
    assert count("windows", f)[0] == 1
    rm = f.extras["removed_by_user"]
    assert len(rm) == 1 and rm[0]["from_kind"] == "window" and rm[0]["element"]["id"] == "window1"


def test_not_element_is_remove_and_room_subtype():
    OV.add(SHA, "door1", "retype", kind="not_element")
    OV.add(SHA, "room0", "retype", kind="room", subtype="kitchen")
    f = OV.apply(_facts(), SHA)
    assert count("doors", f)[0] == 2
    assert count("bedrooms", f)[0] == 0 and next(e for e in f.elements if e.id == "room0").subtype == "kitchen"


def test_undo_and_restore():
    OV.add(SHA, "door0", "retype", kind="window")
    h1 = OV.overrides_hash(SHA)
    OV.add(SHA, "door1", "remove")
    assert count("doors", OV.apply(_facts(), SHA))[0] == 1
    assert OV.undo(SHA)["element_id"] == "door1"
    assert count("doors", OV.apply(_facts(), SHA))[0] == 2 and OV.overrides_hash(SHA) == h1
    OV.add(SHA, "door0", "restore")
    assert count("doors", OV.apply(_facts(), SHA))[0] == 3 and OV.overrides_hash(SHA) == ""
    OV.undo(SHA); OV.undo(SHA)
    assert OV.undo(SHA) is None


def test_validation():
    with pytest.raises(ValueError):
        OV.add(SHA, "door0", "retype", kind="spaceship")
    with pytest.raises(ValueError):
        OV.add(SHA, "room0", "retype", kind="room", subtype="dungeon")
    assert OV.apply(_facts(), SHA).extras.get("removed_by_user") is None   # no overrides: facts untouched


@pytest.fixture
def engine_env(tmp_path, monkeypatch):
    (tmp_path / "data" / "cubicasa5k").mkdir(parents=True)
    (tmp_path / PATH).write_bytes(b"not really a png")
    monkeypatch.setenv("DATASET_ROOT", str(tmp_path))
    monkeypatch.setattr(facts_cache, "CACHE_DIR", tmp_path / "cache")
    facts_cache.clear_memory()
    R.reset()
    P._DISCOVERED = False
    monkeypatch.setattr(P.PipelineEngine, "_extract", lambda self, *a, **k: _facts())
    monkeypatch.setattr(P, "_scan_check_refusal", lambda sha: None)
    monkeypatch.setattr(R, "triagers", lambda: [])      # the stand-in file is not a real image
    eng = P.PipelineEngine(llm=None)
    eng._prior = {"intent": {}, "source_type": {}, "type": {}}
    yield eng
    R.reset()
    P._DISCOVERED = False


def test_pipeline_answer_recomputes_and_receipt(engine_env):
    eng = engine_env
    q = "How many doors are there?"
    sha = facts_cache.sha256_file(P._abs(PATH))
    assert eng.ask(PATH, q).value == 3
    OV.add(sha, "door0", "retype", kind="window")
    po = eng.ask(PATH, q)
    assert po.value == 2
    assert any("you changed element door0 from door to window" in n for n in po.notes) or any(
        "door0" in a.key and a.tag.value == "chosen" for a in po.assumptions)
    wq = eng.ask(PATH, "How many windows are shown on this floor plan?")
    assert wq.value == 3
    pin = next(e for e in wq.evidence if e.id == "door0")
    assert pin.attrs["user_override"]["tag"] == "chosen"
    assert any("you changed element door0 from door to window" in n for n in wq.notes)
    assert any(a.key == "user_element:door0" and a.tag.value == "chosen" for a in wq.assumptions)
    OV.undo(sha)
    assert eng.ask(PATH, q).value == 3


def test_api_roundtrip(engine_env, monkeypatch):
    monkeypatch.setattr(M, "engine", lambda: engine_env)
    c = TestClient(M.app)
    r = c.get("/api/elements", params={"path": PATH})
    assert r.status_code == 200
    d = next(e for e in r.json()["elements"] if e["id"] == "door0")
    assert d["tag"] == "drawn" and "doors" in d["feeds"] and "Counts toward 'How many doors'" in d["explanation"]
    r = c.post("/api/elements/override", json={"path": PATH, "element_id": "door0", "action": "retype", "kind": "window"})
    j = r.json()
    assert r.status_code == 200 and j["element"]["kind"] == "window" and j["element"]["tag"] == "chosen"
    vals = {f["intent"]: f["value"] for f in j["findings"]}
    assert vals["doors"] == 2 and vals["windows"] == 3
    assert c.post("/api/elements/override", json={"path": PATH, "element_id": "nope", "action": "remove"}).status_code == 404
    assert c.post("/api/elements/override", json={"path": PATH, "element_id": "door1", "action": "retype", "kind": "x"}).status_code == 422
    u = c.post("/api/elements/undo", json={"path": PATH}).json()
    assert u["undone"]["element_id"] == "door0" and {f["intent"]: f["value"] for f in u["findings"]}["doors"] == 3
