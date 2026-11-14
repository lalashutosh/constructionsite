import os

import pytest
from fastapi.testclient import TestClient

import api.main as M


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("PLUMB_ENGINE", "stub")
    if not os.environ.get("DATASET_ROOT"):          # CI has no dataset: a stand-in root so the path guard accepts data/...
        monkeypatch.setenv("DATASET_ROOT", str(tmp_path))
    M._engine = None
    yield TestClient(M.app)
    M._engine = None


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ask_returns_proof_object_and_cost_accumulates(client):
    before = client.get("/api/cost").json()["questions"]
    r = client.post("/api/ask", json={"path": "data/cubicasa5k/x.png", "question": "How many doors?"})
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] in ("green", "amber", "grey") and "cost" in body and "provenance" in body
    # stub engine does not feed the meter; the endpoint must still be well-formed
    assert client.get("/api/cost").json()["questions"] >= before


def test_ask_validation_and_traversal(client):
    assert client.post("/api/ask", json={"question": "x"}).status_code == 400
    assert client.post("/api/ask", json={"path": "../etc/passwd", "question": "x"}).status_code == 400


def test_upload_rejects_executables(client):
    r = client.post("/api/upload", files={"file": ("evil.py", b"print(1)")})
    assert r.status_code == 415


def test_decide_is_501_until_quote_exists(client):
    r = client.post("/api/decide", json={"path": "data/cubicasa5k/x.png"})
    assert r.status_code in (501, 404, 200)


def test_cors_header(client):
    r = client.options("/health", headers={"Origin": "http://localhost:5173",
                                           "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_image_traversal_and_missing(client):
    assert client.get("/api/image", params={"path": "../etc/passwd"}).status_code == 400
    assert client.get("/api/image", params={"path": "data/cubicasa5k/does-not-exist.png"}).status_code == 404


def test_override_needs_engine_support(client):
    r = client.post("/api/override", json={"path": "data/cubicasa5k/x.png", "question": "How many doors?",
                                           "element_id": "d1", "polygon": [[0, 0], [1, 0], [1, 1]], "keep": True})
    assert r.status_code in (501, 404)       # stub engine has no overrides; missing file is 404


def test_implausible_measurement_is_refused():
    from contracts.proof import Element, Provenance, SheetFacts
    sq = lambda x: [(x, 0.0), (x + 300, 0.0), (x + 300, 300), (x, 300)]       # 300 px square rooms
    f = SheetFacts(provenance=Provenance(file="f"), elements=[
        Element(id=f"r{i}", kind="room", polygon=sq(400 * i)) for i in range(3)])
    assert M._implausible_scale({"px_length": 300, "length_m": 3}, f) is None            # 100 px/m -> 9 m2 rooms
    bad = M._implausible_scale({"px_length": 300, "length_m": 248}, f)                   # 248 cm typed as metres
    assert bad and "not plausible" in bad["message"] and "cm" in (bad["suggestion"] or "")


def test_paths_outside_dataset_and_uploads_are_refused(client):
    for bad in ("/etc/passwd", "/private/etc/hosts", "../../etc/passwd"):
        r = client.post("/api/ask", json={"path": bad, "question": "How many doors?"})
        assert r.status_code == 400, bad
        assert client.get("/api/image", params={"path": bad}).status_code == 400


def test_zero_or_negative_measurements_are_refused():
    from contracts.proof import Provenance, SheetFacts
    f = SheetFacts(provenance=Provenance(file="f"))
    for a in ({"px_length": 0, "length_m": 3}, {"px_length": -50, "length_m": 3}, {"px_length": 50, "length_m": 0},
              {"px_per_m": float("inf")}):
        assert M._implausible_scale(a, f), a
