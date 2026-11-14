"""FastAPI service. Bodies and returns are contract types (ProofObject, SheetFacts, Decision, Cost totals).

GET /health | POST /api/analyze | POST /api/ask | POST /api/scale | POST /api/decide | GET /api/cost
GET /api/facts | GET /api/stream/{job} (SSE stage events) | POST /api/ask_async -> {job}
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import queue
import threading
import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from contracts.proof import Cost, ProofObject, SheetFacts
from engine import cache as facts_cache
from engine.api import get_engine
from engine.cost import METER

ROOT = pathlib.Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "cache" / "uploads"
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".dxf", ".ifc", ".webp"}
MAX_UPLOAD = 60 * 1024 * 1024

app = FastAPI(title="Plumb", version="0.2")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

_engine = None
_engine_lock = threading.Lock()
_JOBS: dict[str, "queue.Queue"] = {}


def engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = get_engine(os.environ.get("PLUMB_ENGINE", "pipeline"))
        return _engine


# ----------------------------------------------------------------------------- bodies
class PathRef(BaseModel):
    path: Optional[str] = None
    sample_id: Optional[str] = None
    allow_siblings: bool = True


class AskBody(PathRef):
    question: str
    benchmark: bool = False
    questions: Optional[list[str]] = None


class ScaleBody(PathRef):
    anchors: list[dict[str, Any]] = Field(default_factory=list)  # {kind:"user", px_per_m | px_length+length_m, ...}
    questions: list[str] = Field(default_factory=list)
    benchmark: bool = False


class DecideBody(PathRef):
    request: dict[str, Any] = Field(default_factory=dict)
    vibe: str = "standard"
    choices: dict[str, Any] = Field(default_factory=dict)


def _resolve(body: PathRef) -> str:
    p = body.path or body.sample_id
    if not p:
        raise HTTPException(400, "path or sample_id required")
    if ".." in pathlib.Path(p).parts:
        raise HTTPException(400, "bad path")
    return p


def _sha(path: str) -> str:
    from engine.pipeline import _abs
    try:
        return facts_cache.sha256_file(_abs(path))
    except OSError:
        raise HTTPException(404, f"file not found: {path}")


# ----------------------------------------------------------------------------- routes
@app.get("/health")
def health():
    return {"status": "ok", "engine": getattr(engine(), "name", "stub"), "time": time.time()}


@app.get("/api/cost")
def cost() -> dict:
    return METER.snapshot()


@app.post("/api/analyze", response_model=SheetFacts)
async def analyze(file: Optional[UploadFile] = File(None), path: Optional[str] = Form(None),
                  sample_id: Optional[str] = Form(None), allow_siblings: bool = Form(True)):
    if file is not None:
        ref = await _save_upload(file)
    else:
        ref = _resolve(PathRef(path=path, sample_id=sample_id))
    return await asyncio.to_thread(engine().analyze, ref, allow_siblings=allow_siblings)


@app.post("/api/analyze/json", response_model=SheetFacts)
async def analyze_json(body: PathRef):
    return await asyncio.to_thread(engine().analyze, _resolve(body), allow_siblings=body.allow_siblings)


@app.get("/api/facts", response_model=SheetFacts)
async def facts(path: str, allow_siblings: bool = True):
    return await asyncio.to_thread(engine().analyze, _resolve(PathRef(path=path)), allow_siblings=allow_siblings)


async def _save_upload(file: UploadFile) -> str:
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"unsupported file type {ext!r}")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "file too large")
    import hashlib
    sha = hashlib.sha256(data).hexdigest()
    UPLOADS.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS / f"{sha}{ext}"
    if not dest.exists():
        dest.write_bytes(data)  # stored, never executed
    return str(dest)  # absolute path: the pipeline accepts absolute paths


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    return {"path": await _save_upload(file)}


@app.post("/api/ask", response_model=ProofObject)
async def ask(body: AskBody):
    path = _resolve(body)
    return await asyncio.to_thread(engine().ask, path, body.question, allow_siblings=body.allow_siblings,
                                   benchmark=body.benchmark)


@app.post("/api/scale", response_model=list[ProofObject])
async def scale(body: ScaleBody):
    """User tap / line / typed scale -> stored as an anchor for this drawing -> recompute the given questions."""
    path = _resolve(body)
    eng = engine()
    sha = _sha(path)
    if hasattr(eng, "user_anchors"):
        for a in body.anchors:
            a.setdefault("kind", "user")
        eng.user_anchors[sha] = list(body.anchors)
    qs = body.questions or ["What is the total net floor area in m2?"]
    return [await asyncio.to_thread(eng.ask, path, q, allow_siblings=body.allow_siblings, benchmark=body.benchmark)
            for q in qs]


@app.post("/api/decide")
async def decide(body: DecideBody):
    """Apply a choice -> recompute. engine.decide.quote may not exist yet: 501 with a clear message."""
    try:
        from engine.decide import quote  # type: ignore[attr-defined]
    except ImportError:
        quote = None
    if quote is None:
        raise HTTPException(501, "engine.decide.quote is not implemented yet (takeoff owns it)")
    path = _resolve(body)
    f = await asyncio.to_thread(engine().analyze, path, allow_siblings=body.allow_siblings)
    out = await asyncio.to_thread(quote, f, body.request, body.vibe, body.choices)
    return json.loads(out.model_dump_json()) if hasattr(out, "model_dump_json") else out


# ----------------------------------------------------------------------------- SSE
@app.post("/api/ask_async")
async def ask_async(body: AskBody) -> dict:
    """Start an ask in a thread; stream stage names from GET /api/stream/{job}."""
    path = _resolve(body)
    job = uuid.uuid4().hex[:12]
    q: "queue.Queue" = queue.Queue()
    _JOBS[job] = q

    def run():
        try:
            po = engine().ask(path, body.question, allow_siblings=body.allow_siblings, benchmark=body.benchmark,
                              progress=lambda s: q.put({"stage": s, "t": time.time()}))
            q.put({"stage": "done", "t": time.time(), "result": json.loads(po.model_dump_json())})
        except Exception as e:  # noqa: BLE001
            q.put({"stage": "error", "t": time.time(), "error": f"{type(e).__name__}: {e}"})
        q.put(None)

    threading.Thread(target=run, daemon=True).start()
    return {"job": job}


@app.get("/api/stream/{job}")
async def stream(job: str):
    q = _JOBS.get(job)
    if q is None:
        raise HTTPException(404, "unknown job")

    async def gen():
        while True:
            try:
                item = await asyncio.to_thread(q.get, True, 120)
            except queue.Empty:
                break
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
        _JOBS.pop(job, None)

    return StreamingResponse(gen(), media_type="text/event-stream")
