"""FastAPI service. Bodies and returns are contract types (ProofObject, SheetFacts, Decision, Cost totals).

GET /health | POST /api/analyze | POST /api/ask | POST /api/scale | POST /api/decide | GET /api/cost
POST|DELETE /api/override (user verdict on one element) | GET /api/image?path= (the drawing) |
GET /api/geometry?path= (walls + elements for the 3D view, same pixel space as /api/image)
GET /api/plan?path=&vibe=&it_load_kw= (building type, checklist with quantities, build steps)
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


class OverrideBody(PathRef):
    question: str
    element_id: str
    polygon: list[list[float]]            # the element's polygon in ORIGINAL drawing coordinates
    keep: bool                            # True = "yes, this is one", False = "no, it is not"
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


@app.post("/api/override", response_model=ProofObject)
async def override(body: OverrideBody):
    """User verdict on one element (Skeptic Duel: "Is this a door? Yes / No") -> recompute the answer.
    The verdict corrects every voter's element set; the tier is recomputed from agreement (engine.pipeline)."""
    path = _resolve(body)
    eng = engine()
    if not hasattr(eng, "overrides"):
        raise HTTPException(501, "this engine does not support overrides")
    from engine.router import route
    sha = _sha(path)
    intent = route(body.question, path).intent
    lst = [v for v in eng.overrides.get((sha, intent), []) if v.get("id") != body.element_id]
    lst.append({"id": body.element_id, "polygon": body.polygon, "keep": body.keep})
    eng.overrides[(sha, intent)] = lst
    return await asyncio.to_thread(eng.ask, path, body.question, allow_siblings=body.allow_siblings,
                                   benchmark=body.benchmark)


@app.delete("/api/override")
async def clear_overrides(body: PathRef):
    eng = engine()
    sha = _sha(_resolve(body))
    for k in [k for k in getattr(eng, "overrides", {}) if k[0] == sha]:
        del eng.overrides[k]
    return {"cleared": True}


IMAGES = ROOT / "cache" / "images"
RASTER_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _drawing_png(path: str, max_px: int = 2000) -> tuple[pathlib.Path, str, str]:
    """(file to show, media type, coords) for a dataset path: raster as is, svg as is, pdf page 1 rendered to png
    (cached by sha256), dxf/ifc via their same-stem png/pdf/svg sibling (same drawing, README rule)."""
    from engine.pipeline import _abs
    if ".." in pathlib.Path(path).parts:
        raise HTTPException(400, "bad path")
    src = pathlib.Path(_abs(path))
    if src.suffix.lower() in (".dxf", ".ifc"):
        sib = next((src.with_suffix(e) for e in (".png", ".pdf", ".svg") if src.with_suffix(e).exists()), None)
        if sib is None:
            raise HTTPException(404, f"no renderable sibling for {path}")
        src = sib
    if not src.exists():
        raise HTTPException(404, f"file not found: {path}")
    ext = src.suffix.lower()
    if ext in RASTER_MIME:
        return src, RASTER_MIME[ext], "pixels"
    if ext == ".svg":
        return src, "image/svg+xml", "svg"
    if ext == ".pdf":
        out = IMAGES / f"{facts_cache.sha256_file(str(src))}-{max_px}.png"
        if not out.exists():
            import fitz
            with fitz.open(str(src)) as doc:
                page = doc[0]
                zoom = min(4.0, max_px / max(page.rect.width, page.rect.height))
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                IMAGES.mkdir(parents=True, exist_ok=True)
                pix.save(str(out))
        return out, "image/png", "pdf-render"
    raise HTTPException(415, f"cannot render {ext}")


@app.get("/api/image")
async def image(path: str, max_px: int = 2000):
    """The drawing itself, for the 3D view's floor. X-Plumb-Coords says whether evidence polygons share its pixels."""
    from fastapi.responses import FileResponse
    f, mime, coords = await asyncio.to_thread(_drawing_png, path, max_px)
    return FileResponse(f, media_type=mime, headers={"X-Plumb-Coords": coords})


GEOM = ROOT / "cache" / "geometry"


def _reviewers():
    """Two independent vision reviewers for the scan check (engine/scancheck.py), when an LLM is configured."""
    from engine.query import llm as L
    if L.provider() not in ("verda", "featherless"):
        return None
    out = []
    for kind in ("fast", "strong"):
        r = L.VerdaLLM(L.provider(), kind)
        r.no_think = True
        out.append(r)
    return out


@app.get("/api/geometry")
async def geometry(path: str):
    """3D model data in the SAME pixel space as /api/image: walls (with holes) to extrude, plus rooms, doors,
    windows and fixtures from the readers when they share that space. Cached by sha256."""
    f, mime, coords = await asyncio.to_thread(_drawing_png, path)
    if coords == "svg":
        raise HTTPException(415, "svg geometry not supported; ask for the pdf sibling")
    sha = facts_cache.sha256_file(str(f))
    out = GEOM / f"{sha}-{coords}.json"
    if out.exists():
        return json.loads(out.read_text())

    def build():
        import cv2
        from engine import geometry3d
        img = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(415, "image could not be read")
        facts = engine().analyze(path) if coords == "pixels" else None
        g = geometry3d.model(img, facts, coords, use_cnn=(coords == "pixels"), scan_check=True, llm=_reviewers())
        g.update(path=path, coords=coords, credit=(facts.provenance.credit if facts else None))
        GEOM.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(g))
        return g
    return await asyncio.to_thread(build)


# standard questions whose answers feed the build plan's counts (same numbers the Findings panel shows)
PLAN_COUNTS = {
    "swiss_dwellings": {"doors": "How many doors are drawn on this floor plan?",
                        "windows": "How many windows are drawn on this floor plan?",
                        "toilets": "How many toilets are drawn on this floor plan?",
                        "sinks": "How many washbasins are drawn on this floor plan?",
                        "showers": "How many showers are drawn on this floor plan?",
                        "bathtubs": "How many bathtubs are drawn on this floor plan?"},
    "cubicasa5k": {"doors": "How many doors are shown on this floor plan?",
                   "windows": "How many windows are shown on this floor plan?",
                   "toilets": "How many toilets are shown on this floor plan?",
                   "sinks": "How many sinks are shown on this floor plan?",
                   "showers": "How many showers or bathtubs are shown on this floor plan?",
                   "kitchens": "How many kitchens are shown on this floor plan?"},
}


@app.get("/api/plan")
async def build_plan(path: str, vibe: str = "standard", it_load_kw: Optional[float] = None):
    """What building is this, what to get, in which order to build it. Shape: engine/plan/build.py `plan()`.
    Counts come from the engine's own answers (with their tier); areas from the exact file or the scale."""
    p = _resolve(PathRef(path=path))

    def run():
        from engine import siblings
        from engine.plan.build import plan
        eng = engine()
        r = siblings.resolve(p, True)
        use = r.path if (r is not None and r.fmt in ("dxf", "ifc")) else p
        facts = eng.analyze(use)
        px, tag = None, "open"
        if "vector" not in facts.extras and hasattr(eng, "_scale"):
            sc = eng._scale(facts, _sha(p))
            if sc.px_per_m:
                px = sc.px_per_m
                tag = "defaulted" if sc.widths_relative else "drawn"
        src = p.split("/")[1] if p.startswith("data/") else "cubicasa5k"   # uploads: treat as a scanned plan
        counts, sh = {}, {}
        for key, q in PLAN_COUNTS.get(src, PLAN_COUNTS["cubicasa5k"]).items():
            po = eng.ask(p, q, benchmark=True)
            if isinstance(po.value, (int, float)):
                t = "drawn" if po.tier.value == "green" else "defaulted"
                sh[key] = (int(po.value), t, f"engine answer to '{q}' ({po.tier.value})")
        if "bathtubs" in sh:                        # showers + bathtubs = one plumbing line
            v1, t1, _ = sh.pop("bathtubs")
            v0, t0, _ = sh.get("showers", (0, "drawn", ""))
            sh["showers"] = (v0 + v1, "drawn" if t0 == t1 == "drawn" else "defaulted", "showers + bathtubs answers")
        counts.update(sh)
        out = plan(facts, vibe, px, tag, needs={"it_load_kw": it_load_kw} if it_load_kw else None, counts=counts)
        out["read_from"] = use
        return out
    return await asyncio.to_thread(run)


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
