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
    selected_id: Optional[str] = None      # element selected in the viewer: "this room" means it
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


def _allowed_path(p: str) -> bool:
    """Only files inside the dataset root or our uploads folder may be read (an absolute path like /etc/passwd
    used to bypass the '..' check and was read + hashed)."""
    from engine.pipeline import _abs
    try:
        target = pathlib.Path(_abs(p)).resolve()
    except (OSError, RuntimeError):
        return False
    roots = [UPLOADS.resolve()]
    try:
        from evalkit.data import dataset_root
        roots.append(pathlib.Path(dataset_root()).resolve())
    except Exception:  # noqa: BLE001
        pass
    return any(target == r or r in target.parents for r in roots)


def _resolve(body: PathRef) -> str:
    p = body.path or body.sample_id
    if not p:
        raise HTTPException(400, "path or sample_id required")
    if ".." in pathlib.Path(p).parts or not _allowed_path(p):
        raise HTTPException(400, "bad path: only dataset drawings and your uploads can be read")
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
    from engine import selected
    if selected.applies(body.question, body.selected_id):
        po = await asyncio.to_thread(selected.answer, engine(), path, body.question, body.selected_id)
        if po is not None:
            return po
    return await asyncio.to_thread(engine().ask, path, body.question, allow_siblings=body.allow_siblings,
                                   benchmark=body.benchmark)


def _printed_scale_check(ppm: float, a: dict, facts) -> Optional[dict]:
    """The drawing prints its own sizes (room areas in the labels, opening sizes): a measurement more than 30% off
    that is refused, with the fix that matches the drawing."""
    try:
        from engine.scale import anchors as A
        got = [x for x in (A._label_area_anchor(facts), A._printed_dims_anchor(facts)) if x is not None]
    except Exception:  # noqa: BLE001
        return None
    if not got:
        return None
    pv = sorted(x.px_per_m for x in got)[len(got) // 2]
    if abs(ppm / pv - 1) <= 0.30:
        return None
    ex = ""
    try:
        c = A.label_area_candidates(facts)
        near = [x for x in c if abs(x["px_per_m"] / pv - 1) <= 0.15]
        if near:
            x = near[0]
            ex = f" (it would make {x['text'].split()[0]} {x['m2'] * (pv / ppm) ** 2:.1f} m², the drawing prints {x['m2']:g} m²)"
    except Exception:  # noqa: BLE001
        pass
    sug = None
    if "px_length" in a:
        L = float(a["px_length"]) / pv
        sug = {"label": f"Use {L:.2f} m (from the sizes printed on the drawing)", "length_m": round(L, 3), "unit": "m"}
    src = " and ".join("room areas" if x.kind == "printed_area" else "opening sizes" for x in got)
    return {"message": f"this measurement disagrees with the {src} printed on the drawing by "
                       f"{abs(ppm / pv - 1):.0%}{ex}", "suggestion": sug}


def _implausible_scale(a: dict, facts) -> Optional[dict]:
    """A measurement that makes the typical room absurd is refused (a length typed in cm/mm instead of m makes
    every area 10,000x / 1,000,000x too big). Returns {message, median_room_m2, suggestion} or None."""
    import math as _m
    try:
        vals = [float(a["px_per_m"])] if "px_per_m" in a else [float(a["px_length"]), float(a["length_m"])]
        if any((not _m.isfinite(v)) or v <= 0 for v in vals):
            return {"message": "a measurement needs a positive length on the drawing and a positive real length"}
        ppm = vals[0] if len(vals) == 1 else vals[0] / vals[1]
    except (KeyError, ValueError, ZeroDivisionError, TypeError):
        return {"message": "the measurement needs a pixel length and a length in metres"}
    from shapely.geometry import Polygon
    areas = []
    for e in facts.elements:
        if e.kind == "room" and len(e.polygon) >= 3 and "area_m2" not in e.attrs:
            try:
                areas.append(Polygon(e.polygon).area)
            except Exception:  # noqa: BLE001
                pass
    printed = _printed_scale_check(ppm, a, facts)
    if printed:
        return printed
    if len(areas) < 2 or ppm <= 0:
        return None                                      # nothing to check against
    import statistics as _st
    med_px = _st.median(areas)
    med = med_px / ppm ** 2
    if 2.0 <= med <= 120.0:
        return None
    sug = None
    if "length_m" in a:
        for f, unit in ((0.01, "cm"), (0.001, "mm"), (100.0, "m (you may have typed cm as m)")):
            m2 = med_px / (float(a["px_length"]) / (float(a["length_m"]) * f)) ** 2
            if 2.0 <= m2 <= 120.0:
                sug = f"if you meant {a['length_m']} {unit.split()[0]}, the typical room would be {m2:.1f} m²"
                break
    return {"message": f"this measurement would make the typical room {med:,.0f} m², which is not plausible; "
                       "check the length and its unit", "median_room_m2": round(med, 1), "suggestion": sug}


@app.post("/api/scale", response_model=list[ProofObject])
async def scale(body: ScaleBody):
    """User tap / line / typed scale -> stored as an anchor for this drawing -> recompute the given questions."""
    path = _resolve(body)
    eng = engine()
    sha = _sha(path)
    facts = await asyncio.to_thread(eng.analyze, path, allow_siblings=body.allow_siblings)
    for a in body.anchors:
        bad = _implausible_scale(a, facts)
        if bad:
            raise HTTPException(422, bad)
    if hasattr(eng, "user_anchors"):
        for a in body.anchors:
            a.setdefault("kind", "user")
        eng.user_anchors[sha] = list(body.anchors)
    qs = body.questions or ["What is the total net floor area in m2?"]
    return [await asyncio.to_thread(eng.ask, path, q, allow_siblings=body.allow_siblings, benchmark=body.benchmark)
            for q in qs]


class CheckAnswerBody(PathRef):
    id: str
    answer: str
    value: Optional[float] = None


def _checks_target(path: str):
    from engine.pipeline import _abs
    return _abs(path), _sha(path)


@app.get("/api/checks")
async def checks(path: str):
    """Confidence meter + yes/no questions (docs/decisions/checks-api.md)."""
    from engine.scale import checks as C
    body = PathRef(path=path)
    p = _resolve(body)
    ap, sha = _checks_target(p)
    try:
        return await asyncio.to_thread(C.get_checks, ap, sha, p)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/checks/answer")
async def checks_answer(body: CheckAnswerBody):
    """yes -> the candidate becomes a user-confirmed scale anchor; no -> rejected, next candidate asked."""
    from engine.scale import checks as C
    p = _resolve(body)
    ap, sha = _checks_target(p)
    try:
        return await asyncio.to_thread(C.answer, ap, sha, p, body.id, body.answer, body.value)
    except KeyError:
        raise HTTPException(404, f"unknown check id: {body.id}")
    except ValueError as e:
        raise HTTPException(422, str(e))


# --------------------------------------------------------------------------- element inspector + overrides
class ElementOverrideBody(PathRef):
    element_id: str
    action: str                      # retype | remove | restore
    kind: Optional[str] = None
    subtype: Optional[str] = None


_SOURCE_WORDS = {"png": "the CubiCasa model", "jpg": "the CubiCasa model", "jpeg": "the CubiCasa model",
                 "pdf": "the PDF vector data", "dxf": "the CAD file", "ifc": "the BIM model", "svg": "the SVG drawing"}
_PLURAL_Q = {"doors": "How many doors", "windows": "How many windows", "bedrooms": "How many bedrooms",
             "kitchens": "How many kitchens", "bathrooms": "How many bathrooms", "wc_rooms": "How many WC rooms",
             "saunas": "How many saunas", "balconies": "How many balconies", "toilets": "How many toilets",
             "sinks": "How many sinks", "showers_baths": "How many showers or baths", "rooms": "How many rooms",
             "total_area": "What is the total floor area"}


def _element_rows(eng, path: str, sha: str, facts) -> list[dict]:
    from engine import overrides_el as OV
    scale = None
    try:
        sc = eng._scale(facts, sha) if hasattr(eng, "_scale") else facts.scale
        if sc is not None and sc.px_per_m and not getattr(sc, "needs_user", False) and sc.px_per_m != 1.0:
            scale = sc.px_per_m
    except Exception:  # noqa: BLE001
        scale = facts.scale.px_per_m if facts.scale and facts.scale.px_per_m else None
    src = _SOURCE_WORDS.get((facts.provenance.fmt or "").lower(), "the drawing")
    if facts.extras.get("route") == "cad":           # construction sheets are not read by the residential CNN
        src = "the sheet's line geometry at its printed scale"
    rows = []
    for e in facts.elements:
        xs = [p[0] if not hasattr(p, "x") else p.x for p in e.polygon]
        ys = [p[1] if not hasattr(p, "y") else p.y for p in e.polygon]
        size = None
        if scale and xs and ys:
            w, h = (max(xs) - min(xs)) / scale, (max(ys) - min(ys)) / scale
            size = {"w": round(w, 2), "h": round(h, 2)}
            if e.kind in ("room", "region", "zone", "footprint"):
                a = abs(sum(xs[i] * ys[(i + 1) % len(xs)] - xs[(i + 1) % len(xs)] * ys[i] for i in range(len(xs)))) / 2
                size["area_m2"] = round(a / scale ** 2, 1)
        uo = e.attrs.get("user_override")
        fd = OV.feeds(e.kind, e.subtype)
        what = e.kind.replace("_", " ") + (f" ({e.subtype})" if e.subtype and e.kind == "room" else "")
        art = "an" if what[0] in "aeiou" else "a"
        if uo:
            frm = uo["from_kind"] + (f" ({uo['from_subtype']})" if uo.get("from_subtype") else "")
            expl = f"You set this to {art} {what} (it was read as {frm}). This is your decision."
        else:
            expl = f"This is {art} {what}, read from {src} ({round(e.conf * 100)}% sure)."
        qs = [_PLURAL_Q.get(i, i.replace("_", " ")) for i in fd]
        if qs:
            expl += " Counts toward " + ", ".join(f"'{q}'" for q in qs) + "."
        rows.append({"id": e.id, "kind": e.kind, "subtype": e.subtype, "label": e.label, "conf": round(e.conf, 3),
                     "polygon": [[round(x, 1), round(y, 1)] for x, y in zip(xs, ys)], "size_m": size,
                     "tag": "chosen" if uo else ("specified" if e.kind == "label" else "drawn"),
                     "feeds": fd, "explanation": expl, "user_override": uo})
    return rows


def _elements_payload(eng, path: str, sha: str, allow: bool) -> dict:
    from engine import overrides_el as OV
    facts = eng.analyze(path, allow_siblings=allow)
    facts = OV.apply(facts, sha)
    return {"elements": _element_rows(eng, path, sha, facts),
            "removed_by_user": [{k: v for k, v in r.items() if k != "element"} for r in facts.extras.get("removed_by_user", [])],
            "overrides_hash": facts.extras.get("overrides_hash", ""), "allowed_kinds": list(OV.KINDS),
            "room_subtypes": list(OV.ROOM_SUBTYPES)}


@app.get("/api/elements")
async def elements(path: str, allow_siblings: bool = True):
    """Every element with what it is, size, tag, confidence, and the answers it feeds (user overrides applied)."""
    p = _resolve(PathRef(path=path))
    return await asyncio.to_thread(_elements_payload, engine(), p, _sha(p), allow_siblings)


def _affected(eng, p: str, sha: str, allow: bool, kinds: list[tuple]) -> list[dict]:
    """Recompute the headline question of every intent the changed element touches (before/after the override)."""
    from engine import overrides_el as OV
    qs = {"doors": "How many doors are there?", "windows": "How many windows are shown on this floor plan?",
          "bedrooms": "How many bedrooms are there?", "kitchens": "How many kitchens are there?",
          "bathrooms": "How many bathrooms are there?", "wc_rooms": "How many separate WC rooms are there?",
          "saunas": "How many saunas are there?", "balconies": "How many balconies are there?",
          "toilets": "How many toilets are there?", "sinks": "How many sinks are there?",
          "showers_baths": "How many showers or baths are there?", "rooms": "How many rooms are there?",
          "total_area": "What is the total net floor area in m2?"}
    intents: list[str] = []
    for k, s in kinds:
        for i in OV.feeds(k, s):
            if i in qs and i not in intents:
                intents.append(i)
    out = []
    for i in intents:
        po = eng.ask(p, qs[i], allow_siblings=allow, benchmark=False)
        out.append({"intent": i, "question": qs[i], "value": po.value, "unit": po.unit, "tier": po.tier.value,
                    "answer_text": po.answer_text, "notes": [n for n in po.notes if "you changed" in n or "you removed" in n]})
    return out


@app.post("/api/elements/override")
async def elements_override(body: ElementOverrideBody):
    """Apply one user decision about an element (retype / remove / restore); returns the updated element and the
    findings it changes, recomputed."""
    from engine import overrides_el as OV
    p = _resolve(body)
    sha = _sha(p)
    eng = engine()
    base = await asyncio.to_thread(eng.analyze, p, allow_siblings=body.allow_siblings)
    orig = next((e for e in base.elements if e.id == body.element_id), None)
    if orig is None and not any(r["element_id"] == body.element_id for r in OV.load(sha)):
        raise HTTPException(404, f"unknown element: {body.element_id}")
    try:
        OV.validate(body.action, body.kind, body.subtype)
    except ValueError as e:
        raise HTTPException(422, str(e))
    OV.add(sha, body.element_id, body.action, body.kind, body.subtype)
    payload = await asyncio.to_thread(_elements_payload, eng, p, sha, body.allow_siblings)
    row = next((r for r in payload["elements"] if r["id"] == body.element_id), None)
    kinds = []
    if orig is not None:
        kinds.append((orig.kind, orig.subtype))
    if row:
        kinds.append((row["kind"], row["subtype"]))
    if body.kind:
        kinds.append((body.kind, body.subtype))
    findings = await asyncio.to_thread(_affected, eng, p, sha, body.allow_siblings, kinds)
    return {"element": row, "removed": row is None, "findings": findings, "overrides_hash": payload["overrides_hash"]}


@app.post("/api/elements/undo")
async def elements_undo(body: PathRef):
    from engine import overrides_el as OV
    p = _resolve(body)
    sha = _sha(p)
    eng = engine()
    last = OV.undo(sha)
    if last is None:
        return {"undone": None, "findings": [], "overrides_hash": ""}
    base = await asyncio.to_thread(eng.analyze, p, allow_siblings=body.allow_siblings)
    kinds = [(e.kind, e.subtype) for e in base.elements if e.id == last["element_id"]]
    if last.get("kind"):
        kinds.append((last["kind"], last.get("subtype")))
    findings = await asyncio.to_thread(_affected, eng, p, sha, body.allow_siblings, kinds)
    return {"undone": last, "findings": findings, "overrides_hash": OV.overrides_hash(sha)}


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
    if ".." in pathlib.Path(path).parts or not _allowed_path(path):
        raise HTTPException(400, "bad path: only dataset drawings and your uploads can be read")
    src = pathlib.Path(_abs(path))
    if src.suffix.lower() in (".dxf", ".ifc"):
        sib = next((src.with_suffix(e) for e in (".png", ".pdf", ".svg") if src.with_suffix(e).exists()), None)
        if sib is None:
            if not src.exists():
                raise HTTPException(404, f"file not found: {path}")
            return _render_cad(src, max_px)
        src = sib
    if src.suffix.lower() in (".pdf", ".png", ".jpg") and src.with_suffix(".dxf").exists():
        return _render_cad(src.with_suffix(".dxf"), max_px)   # same drawing, exact: walls/rooms from its entities
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


def _render_cad(src: pathlib.Path, max_px: int) -> tuple[pathlib.Path, str, str]:
    """A .dxf / .ifc with no image beside it: we draw it ourselves (cached by sha256). Coords `dxf-render` /
    `ifc-render`: the 3D data is built from the file's own entities in this pixel space (see /api/geometry)."""
    kind = src.suffix.lower()[1:]
    out = IMAGES / f"{facts_cache.sha256_file(str(src))}-{max_px}-{kind}.png"
    if not out.exists():
        IMAGES.mkdir(parents=True, exist_ok=True)
        try:
            if kind == "dxf":
                from engine.vector import dxf_render
                dxf_render.render(str(src), str(out), max_px)
            else:
                from engine.vector import ifc_render
                ifc_render.render(str(src), str(out), max_px)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, f"could not draw this {kind.upper()} file: {type(e).__name__}: {e}")
    return out, "image/png", f"{kind}-render"


@app.get("/api/image")
async def image(path: str, max_px: int = 2000):
    """The drawing itself, for the 3D view's floor. X-Plumb-Coords says whether evidence polygons share its pixels."""
    from fastapi.responses import FileResponse
    try:
        f, mime, coords = await asyncio.to_thread(_drawing_png, path, max_px)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"this file could not be drawn ({type(e).__name__}); is it complete?")
    return FileResponse(f, media_type=mime, headers={"X-Plumb-Coords": coords})


GEOM = ROOT / "cache" / "geometry"
_GEO_LOCKS: dict = {}
_GEO_GUARD = threading.Lock()


def _reviewers():
    """Two independent vision reviewers for the scan check (engine/scancheck.py), when an LLM is configured."""
    from engine.query import llm as L
    if L.provider() not in ("verda", "featherless"):
        return None
    out = []
    for kind in ("fast", "strong"):
        r = L.VerdaLLM(L.provider(), kind)
        r.no_think = kind == "fast"          # the strong reviewer THINKS (medium effort keeps a build ~30-60 s)
        r.effort, r.timeout = "medium", 150
        out.append(r)
    return out


def _name_geo_rooms(g: dict, img, llm, sha: str) -> None:
    """3D room tags from the printed labels: the vision label reader reads them (cached per drawing), code puts each
    label in the room polygon that contains it and maps it through engine/glossary.yaml."""
    try:
        from shapely.geometry import Point, Polygon
        from engine import label_reader as LR
        labels = LR.read_labels(img, llm, sha)
        h, w = img.shape[:2]
        named = 0
        polys = []
        for r in g.get("rooms") or []:
            if len(r.get("polygon") or []) >= 3:
                try:
                    polys.append((r, Polygon(r["polygon"])))
                except Exception:  # noqa: BLE001
                    pass
        taken = set()
        for l in labels:                     # each label names ONE room: the smallest outline that contains it
            if not l.get("room_type") or not isinstance(l.get("x"), (int, float)) or not isinstance(l.get("y"), (int, float)):
                continue
            pt = Point(l["x"] / 100 * w, l["y"] / 100 * h)
            hit = [(r, P) for r, P in polys if id(r) not in taken and P.is_valid and P.contains(pt)]
            if not hit:
                continue
            r, _ = min(hit, key=lambda t: t[1].area)
            taken.add(id(r))
            t = l["room_type"]
            r["label"], r["subtype"] = l["text"], {"living_room": "living"}.get(t, t)
            r["named_by"] = "printed label (AI read, code matched)"
            named += 1
        g.setdefault("check", {}) and g["check"].setdefault("warnings", [])
        if named:
            g["room_note"] = f"{named} rooms named from their printed labels"
    except Exception:  # noqa: BLE001  (naming is optional)
        pass


@app.get("/api/geometry")
async def geometry(path: str):
    """3D model data in the SAME pixel space as /api/image: walls (with holes) to extrude, plus rooms, doors,
    windows and fixtures from the readers when they share that space. Cached by sha256."""
    try:
        f, mime, coords = await asyncio.to_thread(_drawing_png, path)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001  (truncated PDF, corrupt image ...)
        raise HTTPException(422, f"this file could not be drawn ({type(e).__name__}); is it complete?")
    if coords == "svg":
        raise HTTPException(415, "svg geometry not supported; ask for the pdf sibling")
    sha = facts_cache.sha256_file(str(f))
    out = GEOM / f"{sha}-{coords}.json"

    def fresh():                                     # 3D built by an older reader is rebuilt, never served stale
        if not out.exists():
            return None
        g = json.loads(out.read_text())
        return g if g.get("reader_version") == facts_cache.READER_VERSION else None
    got = fresh()
    if got is not None:
        return got
    with _GEO_GUARD:
        lock = _GEO_LOCKS.setdefault(out.name, threading.Lock())

    def build_once():
        with lock:                                   # parallel opens of one new drawing build it once
            g = fresh()
            return g if g is not None else build()

    def build():
        import cv2
        from engine import geometry3d
        if coords in ("dxf-render", "ifc-render"):          # exact: walls and elements from the file's entities
            from engine.pipeline import _abs
            src = _abs(path)
            if coords == "dxf-render" and not src.lower().endswith(".dxf"):
                src = str(pathlib.Path(src).with_suffix(".dxf"))     # pdf/png drawn from its exact same-stem DXF
            t0 = __import__("time").perf_counter()
            if coords == "dxf-render":
                from engine.vector import dxf_render
                g = dxf_render.geometry(src)
            else:
                from engine.vector import ifc_render
                g = ifc_render.geometry(src)
            g["cost"] = {"ms": round((__import__("time").perf_counter() - t0) * 1000), "llm_calls": 0, "usd": 0.0,
                         "note": "3D built from the file's own entities (no image reading), cached by sha256"}
            credit = None
            try:
                from engine import siblings
                from engine.vector import credits
                credit = credits.lookup(siblings.dataset_root(), path)[1]
            except Exception:  # noqa: BLE001
                pass
            g.update(path=path, coords=coords, credit=credit, check=None, reader_version=facts_cache.READER_VERSION)
            GEOM.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(g))
            return g
        img = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(415, "image could not be read")
        import time as _t
        t0, cpu0 = _t.perf_counter(), _t.process_time()
        facts = engine().analyze(path) if coords == "pixels" else None
        revs = _reviewers()
        g = geometry3d.model(img, facts, coords, use_cnn=(coords == "pixels"), scan_check=True, llm=revs)
        if coords == "pixels" and revs:
            _name_geo_rooms(g, img, revs[-1], sha)
        rv = (g.get("check") or {}).get("reviewer") or {}
        au = (g.get("check") or {}).get("audit") or {}
        g["cost"] = {"ms": round((_t.perf_counter() - t0) * 1000), "cpu_s": round(_t.process_time() - cpu0, 1),
                     "llm_calls": (rv.get("asked", 0) if rv.get("used") else 0) + (len(revs or []) if au.get("used") else 0),
                     "usd": round(rv.get("cost_usd", 0.0) + au.get("cost_usd", 0.0), 5),
                     "note": "reading the drawing + 3D walls + scan check, paid once per file (cached by sha256)"}
        g.update(path=path, coords=coords, credit=(facts.provenance.credit if facts else None),
                 reader_version=facts_cache.READER_VERSION)
        if facts is not None and coords == "pixels":     # deep mode + layers (envelope / walls / furniture / piping)
            try:
                from engine import symbols, layers as LY
                g["deep"] = symbols.deep_info(facts.extras.get("profile") or {},
                                              sum(1 for e in facts.elements if e.kind == "room"))
                g["layers"] = LY.layers(str(f), facts, g)
            except Exception as e:  # noqa: BLE001
                g["layers_error"] = f"{type(e).__name__}: {e}"
        if facts is not None and coords == "pixels":     # printed evidence solved the scale: sizes show by default
            try:
                sc = engine()._scale(facts, sha)
                if (sc.px_per_m and not sc.needs_user and not sc.widths_relative
                        and any(a.kind in ("dimension", "scale_bar", "printed_ratio", "printed_area", "user")
                                and "REJECTED" not in (a.note or "") for a in sc.anchors)):
                    g["px_per_m"] = float(sc.px_per_m)
                    g["scale_note"] = "; ".join(a.note or a.kind for a in sc.anchors if "REJECTED" not in (a.note or ""))[:300]
            except Exception:  # noqa: BLE001
                pass
        GEOM.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(g))
        return g
    return await asyncio.to_thread(build_once)


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
                kinds = {a.kind for a in sc.anchors}
                tag = ("chosen" if "user" in kinds else
                       "specified" if kinds & {"dimension", "scale_bar", "printed_ratio", "printed_area"} else
                       "defaulted" if sc.widths_relative else "drawn")
        fpo = next((e for e in facts.elements if e.kind == "footprint" and e.attrs.get("px_per_m")), None)
        if fpo is not None:                       # construction sheet: its own verified scale, not the door guess
            px, tag = float(fpo.attrs["px_per_m"]), "specified"
        src = p.split("/")[1] if p.startswith("data/") else "cubicasa5k"   # uploads: treat as a scanned plan
        counts, sh = {}, {}
        if facts.extras.get("route") == "cad":    # counts from the deep read of this sheet (symbols + tags)
            from engine import symbols as SY
            ck = SY.cached(facts.provenance.sha256 or _sha(p)) or {}
            tot = {t["kind"]: t for t in ck.get("totals", [])}
            for key, kinds in (("doors", ["door"]), ("windows", ["window"]), ("toilets", ["toilet"]), ("sinks", ["sink"]),
                               ("showers", ["shower", "bathtub"])):
                n = sum(tot[k]["count"] for k in kinds if k in tot)
                if any(k in tot for k in kinds):
                    sh[key] = (n, "drawn", "deep read of this sheet (symbols found by repetition, counted by code)")
            PLAN_ITER = {}
        else:
            PLAN_ITER = PLAN_COUNTS.get(src, PLAN_COUNTS["cubicasa5k"])
        for key, q in PLAN_ITER.items():
            po = eng.ask(p, q, benchmark=True)
            if isinstance(po.value, (int, float)):
                # counted on the drawing either way; how sure we are goes in the source line, not the tag
                prior = any(a.tag.value == "defaulted" and a.key.startswith(("count:", "prior:")) for a in po.assumptions)
                sure = ("verified by 2 checks" if po.tier.value == "green" else
                        f"{po.reliability:.0%} reliable" if po.reliability else po.tier.value)
                sh[key] = (int(po.value), "defaulted" if prior else "drawn", f"engine answer to '{q}' ({sure})")
        if "bathtubs" in sh:                        # showers + bathtubs = one plumbing line
            v1, t1, _ = sh.pop("bathtubs")
            v0, t0, _ = sh.get("showers", (0, "drawn", ""))
            sh["showers"] = (v0 + v1, "drawn" if t0 == t1 == "drawn" else "defaulted", "showers + bathtubs answers")
        counts.update(sh)
        out = plan(facts, vibe, px, tag, needs={"it_load_kw": it_load_kw} if it_load_kw else None, counts=counts)
        out["read_from"] = use
        return out
    return await asyncio.to_thread(run)


class BuildingBody(BaseModel):
    files: list[dict[str, str]]          # [{path: <from /api/upload or dataset path>, name: <relative name in the folder>}]


@app.post("/api/building")
async def building(body: BuildingBody):
    """A folder of drawings -> floors in order (+ where each level came from) and the non-plan sheets.
    Runs the scan check per file (cached) and, with the LLM on, reads floor titles the file names do not give."""
    from engine.building import organise
    files = []
    for f in body.files:
        try:
            _resolve(PathRef(path=f.get("path")))
            files.append(f)
        except HTTPException:
            pass                                          # a bad path is skipped, not fatal for the folder
    body.files = files

    def geo(path, cached_only: bool = False):
        if cached_only:                                  # never build 3D for every file of a folder here
            try:
                f, _, coords = _drawing_png(path)
                c = GEOM / f"{facts_cache.sha256_file(str(f))}-{coords}.json"
                return json.loads(c.read_text()) if c.exists() else None
            except Exception:  # noqa: BLE001
                return None
        return asyncio.run(geometry(path))

    def img(path):
        import cv2
        fp, _, _ = _drawing_png(path, 1400)
        im = cv2.imread(str(fp))
        return cv2.imencode(".png", im)[1].tobytes()

    def abs_of(path):
        from engine.pipeline import _abs
        return _abs(path)

    thinker = None
    from engine.query import llm as L
    if L.provider() in ("verda", "featherless"):
        thinker = L.VerdaLLM(L.provider(), "strong")      # reasoning ON: organising a project is a hard task
        thinker.no_think = False
    return await asyncio.to_thread(organise, body.files, geo, None, img, abs_of, thinker)


_FINDING_QS: dict = {}


def _finding_questions() -> dict:
    """{source: [(intent, question)]}: every measurable question type the dataset asks for that kind of drawing, in
    the dataset's most common English wording; templates that need a specific room/apartment/storey are skipped."""
    global _FINDING_QS
    if _FINDING_QS:
        return _FINDING_QS
    import collections
    import re as _re
    from evalkit.data import load_questions
    cnt: dict = collections.defaultdict(collections.Counter)
    for q in load_questions():
        if q.type not in ("count", "area") or (q.lang or "en") != "en" or q.intent in (None, "unknown"):
            continue
        if _re.search(r"['\"‘“]|\b(apartment|room) [A-Z0-9]|\d", q.question):
            continue
        cnt[(q.source, q.intent)][q.question] += 1
    out: dict = collections.defaultdict(list)
    for (src, intent), c in sorted(cnt.items()):
        out[src].append((intent, c.most_common(1)[0][0]))
    _FINDING_QS = dict(out)
    return _FINDING_QS


@app.get("/api/findings")
async def findings(path: str):
    """Every standard question for this kind of drawing, answered (same readers as /api/ask). Sources are the
    dataset folders; uploads of images count as scanned plans."""
    p = _resolve(PathRef(path=path))
    from evalkit.intents import source_of
    src = source_of(p) or "cubicasa5k"
    eng = engine()

    def run():
        facts = eng.analyze(p)
        cad = facts.extras.get("route") == "cad"
        qs = CAD_FINDINGS if cad else (_finding_questions().get(src) or _finding_questions().get("cubicasa5k", []))
        rows = []
        for intent, q in qs:
            po = eng.ask(p, q, benchmark=False)
            if po.value is None or po.tier.value == "grey":
                continue                      # nothing found -> no finding (never "0 bedrooms" on a pump house)
            if po.kind == "count" and isinstance(po.value, (int, float)) and po.value == 0:
                continue
            rows.append({"intent": intent, "question": q, "proof": json.loads(po.model_dump_json())})
        if cad:
            rows += _printed_findings(p, facts)
        return rows
    return {"source": "construction_sheet" if facts_is_cad(eng, p) else src, "findings": await asyncio.to_thread(run)}


CAD_FINDINGS = [("scale_info", "What is the scale of this drawing?"),
                ("overall_size", "What is the overall length and width of the building?"),
                ("total_room_area", "What is the total area of all rooms?")]


def facts_is_cad(eng, p: str) -> bool:
    try:
        return eng.analyze(p).extras.get("route") == "cad"
    except Exception:  # noqa: BLE001
        return False


def _printed_findings(p: str, facts) -> list[dict]:
    """What the sheet prints (area / count tables, tagged equipment, pipe sizes, slab types) as findings, each with
    the printed words as evidence (engine/sheet_findings.py). Tag `specified`: the sheet says so."""
    from contracts.proof import Element, ProofObject, Provenance, Tier
    from engine import sheet_findings
    from engine.pipeline import _abs
    from engine.scale import sheet_text
    ap = _abs(p)
    sha = facts.provenance.sha256 or facts_cache.sha256_file(ap)
    out = []
    for f in sheet_findings.findings(sheet_text.words(ap, sha)):
        if f["kind"] == "note":
            continue
        ev = []
        for i, it in enumerate(f["items"]):
            for j, b in enumerate(it["boxes"][:12]):
                x0, y0, x1, y1 = [float(v) for v in b]
                ev.append(Element(id=f"{f['id']}_{i}_{j}", kind="label", polygon=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                                  label=f"{it['label']}: {it['value']}", conf=0.9, attrs={"printed": True}))
        po = ProofObject(id=f"{sha[:8]}-{f['id']}", question=f["title"], intent=f["kind"], kind="text", value=f["text"],
                         unit="label", tier=Tier.amber, evidence=ev[:60], provenance=Provenance(file=p, sha256=sha),
                         answer_text=f"{f['title']}: {f['text']}",
                         notes=["read from the sheet's own print (OCR words; boxes show each value)"])
        out.append({"intent": f["kind"], "question": f["title"], "proof": json.loads(po.model_dump_json())})
    return out


@app.get("/api/checklist")
async def checklist(path: str):
    """Deep read of a big sheet: every symbol type discovered by repetition (code), named once by two vision reviewers
    (size-checked by code), counted by clustering + template matching; rooms named individually; totals per kind.
    Cached per drawing; the first call can take minutes on a huge sheet (deep.eta_s says how long, up front)."""
    p = _resolve(PathRef(path=path))
    eng = engine()

    def run():
        from engine import symbols
        from engine.pipeline import _abs
        facts = eng.analyze(p)
        ap = _abs(p)
        sha = facts.provenance.sha256 or facts_cache.sha256_file(ap)
        revs = _reviewers()
        if revs:
            revs[-1].no_think, revs[-1].timeout = False, 240
        return symbols.checklist(ap, sha, facts, llm=revs)
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
