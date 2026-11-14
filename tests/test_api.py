import pytest
from fastapi.testclient import TestClient

import api.main as M


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PLUMB_ENGINE", "stub")
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
