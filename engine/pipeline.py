"""PipelineEngine: sha256 cache -> triage -> sibling resolve -> extract -> vote -> tier -> ProofObject.

Everything outside the registry is optional: with ZERO plugins this returns an amber 0 with a note. Extraction and
voting make no network calls; the LLM (LLM_PROVIDER != none) only classifies templates and drafts query specs."""
from __future__ import annotations

import hashlib
import math
import importlib
import json
import logging
import os
import pathlib
import statistics
import re
import threading
import time
from typing import Any, Callable, Optional

from contracts import invariants
from contracts.proof import (Assumption, Cost, Decision, Element, Interval, Option, ProofObject, Provenance,
                             ScaleInfo, SheetFacts, Tag, Tier, Voter)
from engine import cache as facts_cache
from engine import registry
from engine.cost import METER
from engine.router import Route, TemplateClassifier, route as route_question

log = logging.getLogger("plumb.pipeline")
ROOT = pathlib.Path(__file__).resolve().parents[1]
AREA_TOL = 0.02
_DETECTOR_KINDS = {"doors": "door", "windows": "window", "toilets": "toilet", "sinks": "sink", "showers_baths": "bath",
                   "washbasins": "washbasin", "bathtubs": "bathtub", "showers": "shower"}
STAGES = ("triage", "resolve", "extract", "vote", "finalize")
VECTOR_EXT = {".pdf", ".dxf", ".ifc", ".svg"}
_DISCOVERED = False


def _discover() -> list[str]:
    global _DISCOVERED
    if not _DISCOVERED:
        registry.reset()
        loaded = registry.autodiscover()
        _DISCOVERED = True
        log.info("plugins: %s", loaded)
        return loaded
    return []


def _abs(path: str) -> str:
    p = pathlib.Path(path)
    if p.is_absolute():
        return str(p)
    root = os.environ.get("DATASET_ROOT")
    if not root:
        try:
            from evalkit.data import dataset_root
            root = str(dataset_root())
        except Exception:  # noqa: BLE001
            root = "."
    return str(pathlib.Path(root).expanduser() / path)


def _kind_note(n: Optional[str]) -> bool:
    return bool(n) and n.startswith("prior fallback")


def _spread(v: Voter) -> float:
    return (max(v.runs) - min(v.runs)) if v.runs else 0.0


def _agree(a: float, b: float, kind: str) -> bool:
    if kind == "count":
        return a == b
    return abs(a - b) <= AREA_TOL * max(abs(a), abs(b), 1e-12)


def pick_value(results: list, kind: str):
    """Exact-source voter wins; else the median voter (ties -> smaller TTA spread)."""
    if kind == "text":                          # "which room is largest?" -> a name
        return next((r.voter.value for r in results if isinstance(r.voter.value, str)), None)
    scored = [r for r in results if isinstance(r.voter.value, (int, float))]
    if not scored:
        return None
    exact = [r for r in scored if r.exact]
    if exact:
        return float(exact[0].voter.value) if kind != "count" else int(exact[0].voter.value)
    primary = [r for r in scored if not getattr(r, "second_opinion", False)]
    scored = primary or scored            # weak cross-checks move the tier, not the number
    vals = [float(r.voter.value) for r in scored]
    med = statistics.median(vals)
    best = min(scored, key=lambda r: (abs(float(r.voter.value) - med), _spread(r.voter)))
    return float(best.voter.value) if kind != "count" else int(round(best.voter.value))


def compute_tier(results: list, kind: str) -> tuple[Tier, str]:
    vals = [r for r in results if isinstance(r.voter.value, (int, float))]
    indep = [r for r in vals if not _kind_note(r.voter.note)]
    if len(vals) >= 2 and len(indep) >= 2 and all(
            _agree(float(vals[0].voter.value), float(r.voter.value), kind) for r in vals[1:]):
        return Tier.green, f"{len(indep)} independent voters agree"
    if len(vals) >= 2:
        return Tier.amber, "voters disagree or only one is independent"
    return Tier.amber, "single voter" if vals else "no voter produced a value"


class PipelineEngine:
    name = "pipeline"

    def __init__(self, llm: Any = None):
        from engine.query import llm as llm_mod
        self.llm = llm if llm is not None else llm_mod.default_llm()
        self.classifier = TemplateClassifier(self.llm) if self.llm else None
        # new questions are planned by the STRONG model with reasoning on (open-weight endpoints are cheap; the fast
        # model with thinking off is kept for routing and as a fallback)
        self.planner_llm = None
        if self.llm is not None and hasattr(self.llm, "kind"):
            from engine.query.llm import VerdaLLM
            self.planner_llm = VerdaLLM(getattr(self.llm, "prov", "verda"), "strong")
            self.planner_llm.no_think = False
            self.planner_llm.plan_tokens = 6000
        self.user_anchors: dict[str, list[dict]] = {}
        self.choices: dict[str, dict] = {}
        # user verdicts on single elements, per (sha256, intent): [{"polygon": [[x,y],...], "keep": bool, "id": str}]
        self.overrides: dict[tuple[str, str], list[dict]] = {}
        self._prior: Optional[dict] = None
        _discover()

    # ------------------------------------------------------------------ analyze
    def analyze(self, path: str, *, allow_siblings: bool = True, _ctx=None, _progress=None) -> SheetFacts:
        abs_path = _abs(path)
        try:
            sha = facts_cache.sha256_file(abs_path)
        except OSError:
            return SheetFacts(provenance=Provenance(file=path), sheet_type="unknown", legible=False,
                              legibility_note="file not found")
        hit = facts_cache.get(sha, allow_siblings)
        if hit is not None:
            return hit
        with _file_lock(sha, allow_siblings):            # 20 parallel questions on one new drawing -> 1 extraction
            hit = facts_cache.get(sha, allow_siblings)
            if hit is not None:
                return hit
            return self._analyze_uncached(path, abs_path, sha, allow_siblings, _ctx)

    def _analyze_uncached(self, path, abs_path, sha, allow_siblings, _ctx) -> SheetFacts:
        facts = self._extract(path, abs_path, allow_siblings, _ctx)
        facts.provenance.sha256 = facts.provenance.sha256 or sha
        if not (facts.legibility_note or "").startswith("extraction failed"):
            facts_cache.put(sha, allow_siblings, facts)  # never cache failures: a better extractor may land later
        return facts

    def _extract(self, path: str, abs_path: str, allow: bool, ctx) -> SheetFacts:
        use_path, use_abs = path, abs_path
        if ctx is not None and ctx.resolved is not None:
            use_path, use_abs = ctx.resolved.path, _abs(ctx.resolved.path)
        ext = pathlib.Path(use_abs).suffix.lower()
        fns: list[Callable] = []
        if ext in VECTOR_EXT:
            for mod in ("engine.vector.plugin", "engine.vector.extract"):
                try:
                    fn = getattr(importlib.import_module(mod), "extract", None)
                except ImportError:
                    fn = None
                if callable(fn):
                    fns.append(fn)
        try:
            from engine.raster.extract import extract as raster_extract
            fns.append(raster_extract)
        except ImportError:
            pass
        err = "no extractor available"
        prof = self._profile(use_abs)
        is_cad = bool(prof) and prof.get("sheet_type") == "cad_sheet" and ext in (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".pdf")
        if is_cad and ext != ".pdf":
            # a CAD / construction sheet is NOT a CubiCasa apartment scan: read line geometry of the main plan view
            try:
                from engine import bigsheet
                f = bigsheet.extract_facts(path, use_abs, prof)
                return f
            except Exception as e:  # noqa: BLE001
                err = f"bigsheet: {type(e).__name__}: {e}"
        for fn in fns:
            try:
                if is_cad and fn.__module__.startswith("engine.raster"):
                    continue                     # never run the CubiCasa CNN over a whole construction sheet
                f = fn(use_path if fn.__module__.startswith("engine.vector") else use_abs, allow_siblings=allow)
                f.provenance.file = path
                if is_cad and not f.elements:     # exact vector readers (Swiss PDF, ...) win whenever they read anything
                    try:                         # vector reader found nothing drawable: read the rendered page instead
                        from engine import bigsheet
                        g = bigsheet.extract_facts(path, use_abs, prof)
                        g.extras.update({k: v for k, v in f.extras.items() if k not in g.extras and k != "vector"})
                        return g
                    except Exception as e:  # noqa: BLE001
                        err = f"bigsheet: {type(e).__name__}: {e}"
                if prof:
                    f.extras.setdefault("profile", {k: v for k, v in prof.items() if k != "sha256"})
                return f
            except Exception as e:  # noqa: BLE001
                err = f"{fn.__module__}: {type(e).__name__}: {e}"
        if is_cad and ext == ".pdf":
            try:
                from engine import bigsheet
                return bigsheet.extract_facts(path, use_abs, prof)
            except Exception as e:  # noqa: BLE001
                err = f"bigsheet: {type(e).__name__}: {e}"
        return SheetFacts(provenance=Provenance(file=path), sheet_type="unknown", legible=False,
                          legibility_note=f"extraction failed ({err})")

    @staticmethod
    def _profile(abs_path: str) -> Optional[dict]:
        """Cheap sheet profile (engine/profile.py), cached by sha256; None when the file is not an image/PDF."""
        if not abs_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".pdf")):
            return None
        if os.environ.get("PLUMB_NO_PROFILE") == "1":          # A/B switch: the pre-profile behaviour
            return None
        try:
            from engine import profile as P
            prof = P.profile(abs_path)
            if prof.get("sheet_type") == "cad_sheet" and "/cubicasa5k/" in abs_path.replace("\\", "/"):
                # the dataset says what this file is: a CubiCasa residential scan (dimension lines can look like a frame)
                prof = {**prof, "sheet_type": "residential_scan", "route": "cubicasa_cnn", "views": [],
                        "note": "profile said cad_sheet; overridden by the dataset source"}
            return prof
        except Exception as e:  # noqa: BLE001
            log.warning("profile failed for %s: %s", abs_path, e)
            return None

    # ------------------------------------------------------------------ ask
    def ask(self, path: str, question: str, *, allow_siblings: bool = True, benchmark: bool = True,
            progress: Optional[Callable[[str], None]] = None) -> ProofObject:
        t0 = time.perf_counter()
        stage = progress or (lambda s: None)
        # --- derived quantities ('how many 3x3 m tiles ...'): engine/takeoff/derive.py runs the base area through ask() ---
        from engine.takeoff import derive
        _dspec = derive.parse(question)
        if _dspec is not None:
            return derive.answer(self, path, question, _dspec, allow_siblings=allow_siblings, benchmark=benchmark, progress=progress)
        # --- end derived quantities ---
        rt = route_question(question, path, classifier=self.classifier)
        from engine.query import measure as _measure
        if _measure.PERIM.search(question) and rt.kind == "count":
            rt = Route("unknown", {}, "length", rt.lang, "measure")   # 'perimeter of the kitchen' is not the kitchen COUNT
        po = self._ask(path, question, rt, allow_siblings, benchmark, stage)
        try:                                  # "... on floor 2" on a sheet with several floor plans
            from engine import sheetfloor
            on_floor = sheetfloor.restrict(po, question, po.provenance.sha256)
        except Exception as e:  # noqa: BLE001
            on_floor = None
            po.notes.append(f"per-floor split skipped: {type(e).__name__}")
        if rt.layer == "regex-complex":       # LLM off and the question asks more than the matched template
            if po.tier == Tier.green:
                po.tier = Tier.amber
            po.notes.append(f"this answers the simpler question '{rt.intent}'; the question asks more "
                            "(turn the planner on: LLM_PROVIDER=verda)")
        po.cost.ms = (time.perf_counter() - t0) * 1000
        for f in ("llm_calls", "tokens_in", "tokens_out", "usd"):
            setattr(po.cost, f, getattr(po.cost, f) + getattr(rt.cost, f))
        try:
            from engine.answer_text import sentence
            po.answer_text = sentence(po)
            pa = next((n[len("printed answer: "):] for n in po.notes if n.startswith("printed answer: ")), None)
            if pa and po.value is not None:          # read from the sheet's own print: say exactly what it prints
                po.answer_text = pa[0].upper() + pa[1:]
            if on_floor:
                po.answer_text = sheetfloor.name_floor(po.answer_text, on_floor)
        except Exception:  # noqa: BLE001  (the sentence is a convenience; never fail an answer over it)
            po.answer_text = None
        bad = invariants.check(po)
        if bad:
            log.warning("invariants violated for %s: %s", path, bad)
            if po.tier == Tier.green:
                po.tier = Tier.amber
            po.notes.append("invariants: " + "; ".join(bad))
        METER.add(po.cost)
        return po

    def _ask(self, path, question, rt: Route, allow, benchmark, stage) -> ProofObject:
        from engine.registry import Ctx

        abs_path = _abs(path)
        kind = rt.kind if rt.kind in ("count", "area", "length", "volume", "text") else "other"
        ctx = Ctx(path=path, abs_path=abs_path, question=question, intent=rt.intent, params=dict(rt.params),
                  kind=kind, lang=rt.lang, allow_siblings=allow)
        po = ProofObject(id=hashlib.sha1(f"{path}|{question}|{allow}".encode()).hexdigest()[:12], question=question,
                         intent=rt.intent, kind=kind, provenance=Provenance(file=path))
        notes = po.notes
        if rt.intent == "unknown":
            notes.append(f"router: no intent matched (layer {rt.layer})")
        try:
            po.provenance.sha256 = sha = facts_cache.sha256_file(abs_path)
        except OSError:
            return self._grey(po, "file not found")
        po.provenance.fmt = pathlib.Path(abs_path).suffix.lstrip(".").lower() or None
        ctx.facts = facts_cache.get(sha, allow)

        # triage
        stage("triage")
        refusal = None
        for name, fn in registry.triagers():
            try:
                tr = fn(ctx)
            except Exception as e:  # noqa: BLE001
                notes.append(f"triage {name} failed: {type(e).__name__}: {e}")
                continue
            if tr is None:
                continue
            if tr.note:
                notes.append(f"triage: {tr.note}")
            if tr.refuse and not refusal:
                refusal = tr.refuse
        if not refusal:
            refusal = _scan_check_refusal(sha)     # the 3D scan check found no floor plan on this sheet
        capped = False
        if refusal:
            if not benchmark:
                return self._grey(po, refusal)
            notes.append(f"triage would refuse: {refusal}")
            capped = True

        # resolve siblings
        stage("resolve")
        if allow:
            for name, fn in registry.resolvers():
                try:
                    res = fn(path, allow)
                except Exception as e:  # noqa: BLE001
                    notes.append(f"resolver {name} failed: {type(e).__name__}: {e}")
                    continue
                if res is not None:
                    ctx.resolved = res
                    po.provenance.resolved_from = res.fmt
                    if res.note:
                        notes.append(f"resolved: {res.note}")
                    break

        # extract
        stage("extract")
        if ctx.facts is None:
            ctx.facts = self.analyze(path, allow_siblings=allow, _ctx=ctx)
        facts = ctx.facts
        # --- element overrides (user) ---
        from engine import overrides_el
        facts = ctx.facts = overrides_el.apply(facts, sha)
        # --- end element overrides (user) ---
        po.provenance.fmt = facts.provenance.fmt or po.provenance.fmt
        po.provenance.license = facts.provenance.license
        po.provenance.credit = facts.provenance.credit
        po.provenance.page = facts.provenance.page
        po.provenance.revision = facts.provenance.revision
        if not facts.legible or facts.sheet_type in ("not_a_plan",):
            reason = facts.legibility_note or f"sheet is {facts.sheet_type}"
            if not benchmark:
                return self._grey(po, reason)
            notes.append(f"unreadable or not a plan: {reason}")
            capped = True

        # scale (area/length/volume only; counts never need it)
        scale: Optional[ScaleInfo] = None
        sheet_text = rt.layer == "sheet" and kind == "text"
        if kind in ("area", "length", "volume") or sheet_text:
            scale = self._scale(facts, sha)
            if scale.px_per_m:
                ctx.params["_px_per_m"] = scale.px_per_m

        # vote
        stage("vote")
        results = self._vote(ctx, notes)
        # --- perimeter / wall length of a named room (engine/query/measure.py; works with the LLM off) ---
        if rt.intent == "unknown" and not results:
            from engine.query import measure
            mspec = measure.parse(ctx.question, facts)
            if mspec is not None:
                from engine import query
                from engine.registry import VoterResult
                if scale is None:
                    scale = self._scale(facts, sha)
                px = scale.px_per_m if scale is not None and scale.px_per_m else None
                target = mspec.pop("_target", None)
                if mspec.get("select") == ["footprint"]:          # main outline only (verified one first)
                    fps = [e for e in facts.elements if e.kind == "footprint"]
                    best = next((e for e in fps if e.attrs.get("source") == "outline"), fps[0])
                    mspec["where"] = {"id": best.id}
                res = query.run(mspec, facts, px)
                po.query_spec = mspec
                notes.extend(f"query: {n}" for n in res.notes)
                if res.value is not None:
                    by = {e.id: e for e in facts.elements}
                    kind = po.kind = "length"
                    po.scale = scale
                    tgt = target or (mspec.get("where") or {}).get("subtype") or (mspec.get("where") or {}).get("label") or "rooms"
                    n_r = len(res.evidence_ids)
                    src = ("the sheet's printed scale" if scale is not None and any(
                        a.kind in ("dimension", "scale_bar", "printed_ratio", "printed_area", "user") for a in scale.anchors)
                        else "a scale guessed from standard door widths (give one real length to confirm)")
                    notes.append(f"printed answer: the walls around the {tgt.replace('_', ' ')}"
                                 f"{'' if n_r == 1 else f' ({n_r} rooms)'} add up to {float(res.value):.1f} m "
                                 f"(length of its outline, measured with {src}).")
                    results = [VoterResult(Voter(name="room_perimeter", value=float(res.value), element_ids=res.evidence_ids,
                                                 note=f"outline length of {len(res.evidence_ids)} room(s) at the solved scale "
                                                      "(= the summed lengths of the walls around them)"),
                                           evidence=[by[i] for i in res.evidence_ids if i in by], unit="m")]
        # --- end perimeter ---
        if sheet_text:                                   # largest room / overall size / scale: no registry voter
            results = self._sheet_text(ctx, rt, facts, scale, po, notes)
        if rt.layer == "sheet" and kind == "count" and not any(e.kind == "room" for e in facts.elements):
            results = []                                 # "how many rooms" with no recognised room is not "0 rooms"
        # --- printed on the sheet (engine/sheet_lookup.py): notes, schedules, tags, overall dimensions ---
        if facts.extras.get("route") == "cad" or (facts.extras.get("profile") or {}).get("sheet_type") == "cad_sheet":
            try:
                got = self._printed(ctx, rt, kind, facts, scale, po, notes, results)
            except Exception as e:  # noqa: BLE001  (a failed lookup never breaks the answer)
                got = None
                notes.append(f"printed-text lookup failed: {type(e).__name__}: {e}")
            if got is not None:
                results, kind = got
                po.kind = kind
        # --- end printed on the sheet ---
        if (facts.extras.get("route") == "cad" and kind == "count" and rt.intent in _DETECTOR_KINDS
                and not any(e.kind == _DETECTOR_KINDS[rt.intent] for e in facts.elements)
                and not any(getattr(r, "exact", False) for r in results)):   # exact vector voters (Swiss PDF) still count
            return self._grey(po, f"{rt.intent.replace('_', ' ')} are not read on construction sheets yet: the symbol "
                                  "detectors are trained on small residential scans, so a '0' would be a guess")
        if not results and rt.layer == "sheet":          # a sheet-level question is never handed to a count or the prior
            return self._sheet_grey(po, rt, facts, scale, notes)
        if kind == "count" and rt.intent == "doors":
            self._door_fusion(results, facts, notes)
        if kind == "count":
            self._label_vote(results, ctx, facts, notes)
            self._apply_overrides(results, sha, rt.intent, po, notes)
        planner_cost = Cost()
        if not results and self.llm is not None:      # no reader answered the matched type -> let the planner try
            if rt.intent != "unknown":
                notes.append(f"no reader answers '{rt.intent}' on this drawing; trying the planner")
            results, planner_cost = self._plan_vote(ctx, question, facts, po, notes)
            kind = po.kind                      # the planner decides the answer's kind (count / area / text)
        for r in results:
            r.voter.runs = list(r.voter.runs)
        po.voters = [r.voter for r in results]
        value = pick_value(results, kind)
        tier, why = compute_tier(results, kind)
        if po.query_spec is not None and len(results) == 1:
            tier = Tier.amber
        notes.append(f"tier: {tier.value} ({why})")

        # prior fallback for benchmark mode when nobody produced a value
        if value is None:
            if benchmark:
                value, pnote = self._prior_value(path, rt.intent, kind)
                if pnote:
                    notes.append(pnote)
                    po.assumptions.append(Assumption(key=f"prior:{rt.intent}", value=value if value is not None else 0,
                                                     tag=Tag.defaulted, source="dev-median prior"))
                tier = Tier.amber
            else:
                return self._grey(po, po.refusal or "no reader or query could answer this question from the drawing")
        if capped and tier == Tier.green:
            tier = Tier.amber

        # finalizers (stacker etc.)
        stage("finalize")
        pre = value
        for name, fn in registry.finalizers():
            try:
                adj = fn(ctx, results)
            except Exception as e:  # noqa: BLE001
                notes.append(f"finalizer {name} failed: {type(e).__name__}: {e}")
                continue
            if adj is not None:
                value = int(round(adj.value)) if kind == "count" else float(adj.value)
                po.voters.append(Voter(name=adj.voter_name, value=value, note=adj.note))
                notes.append(adj.note)
        if value != pre and tier == Tier.green:
            tier = Tier.amber

        # count_defaults -> Tag.defaulted (docs/decisions/count-defaults-tag.md)
        d = facts.extras.get("count_defaults", {}).get(rt.intent) if kind == "count" else None
        if d:
            po.assumptions.append(Assumption(
                key=f"count:{rt.intent}", value=int(d.get("value", value or 0)), tag=Tag.defaulted,
                source=str(d.get("reason", "dev-median prior"))))
            notes.append(f"{rt.intent}: value is a prior (defaulted), not a detection")

        # evidence = the elements of the reading that gave the answer (6 windows -> pins 1..6). Other voters'
        # candidates stay listed under their voter (element_ids) for 'Why?', but are not pinned as the answer.
        def _same(v):
            try:
                return v is not None and value is not None and (
                    int(v) == int(value) if kind == "count" else abs(float(v) - float(value)) <= 0.02 * max(abs(float(value)), 1e-9))
            except (TypeError, ValueError):
                return v == value
        chosen = [r for r in results if _same(r.voter.value)] or results[:1]
        if chosen and isinstance(value, (int, float)) and kind == "count":
            chosen = chosen[:1]                    # one reading's elements, numbered 1..value
        seen: set[str] = set()
        for r in chosen:
            for e in r.evidence:
                if e.id not in seen and len(po.evidence) < 400 and len(e.polygon) >= 2:
                    seen.add(e.id)
                    po.evidence.append(e)
        if not po.evidence and results:
            by = {e.id: e for e in facts.elements}
            for r in chosen:
                for i in r.voter.element_ids[:400]:
                    if i in by and i not in seen and len(by[i].polygon) >= 2:
                        seen.add(i)
                        po.evidence.append(by[i])

        # --- element overrides (user): receipt ---
        overrides_el.annotate(po, facts)
        # --- end element overrides (user): receipt ---
        for e in po.evidence:                 # voters may leak numpy scalars into attrs (JSON can't encode them)
            e.attrs = _native(e.attrs)
        unit = next((r.unit for r in results if r.unit), None)
        po.unit = unit or {"area": "m2", "length": "m", "volume": "m3", "count": "count"}.get(kind)
        po.value = value
        po.tier = Tier.amber if (capped and tier != Tier.grey) else tier
        if kind in ("area", "length", "volume") and value is not None:
            if scale is None and "vector" not in facts.extras and po.provenance.resolved_from not in ("dxf", "ifc"):
                # planner-built area on a raster: the question was not 'area' when the scale was solved; use the engine's
                # real scale (what the planner fallback set, else solve now) instead of the metre placeholder
                prev = po.scale
                scale = prev if (prev is not None and prev.px_per_m and prev.px_per_m != 1.0) else self._scale(facts, sha)
            self._attach_scale(po, scale, facts, value)
        for name, fn in registry.calibrators():
            try:
                p = fn(po.model_dump(mode="json"))
            except Exception:  # noqa: BLE001
                p = None
            if p is not None and po.query_spec is None:     # calibrated on fixed-intent answers only
                notes.append(f"historically right {p:.0%} of the time at this agreement level")
                po.reliability = round(float(p), 3)
                po.reliability_note = (f"answers with this agreement pattern were right {p:.0%} of the time on "
                                       "DEV drawings (calibrator trained on 600 DEV answers)")
        log.info("ask %s intent=%s kind=%s value=%s tier=%s voters=%s", path, rt.intent, kind, po.value,
                 po.tier.value, [v.name for v in po.voters])
        return po

    # ------------------------------------------------------------------ helpers
    # intents where the vision label reader beat the current reader on DEV (40 scans, 350 questions, cache/proto/
    # labeleval.py): bedrooms 88% vs 71%, wc_rooms 91% vs 74%. Elsewhere it is a second opinion (tier only).
    LABEL_PRIMARY = {"bedrooms", "wc_rooms"}

    @staticmethod
    def _door_fusion(results: list, facts: SheetFacts, notes: list[str]) -> None:
        """Doors the network saw only weakly (0.35 <= p < 0.5) count when the independent arc-geometry voter found a
        door swing at the same place (two weak, independent signals on ONE element). Fine-line scans draw thin swings
        the network is unsure about; the arc voter alone over-counts (no wall-gap test). Neither signal alone adds."""
        weak = [w for w in (facts.extras.get("weak_icons") or []) if w.get("kind") == "door"]
        det = next((r for r in results if r.voter.name == "detector"), None)
        arc = next((r for r in results if r.voter.name == "doors_arc"), None)
        if not weak or det is None or arc is None or not arc.evidence:
            return

        def centre(poly):
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            return (sum(xs) / len(xs), sum(ys) / len(ys)), max(max(xs) - min(xs), max(ys) - min(ys))
        strong = [centre([(pt[0], pt[1]) for pt in e.polygon]) for e in facts.elements if e.kind == "door" and e.polygon]
        arcs = []
        for e in arc.evidence:
            c, size = centre([(pt[0], pt[1]) for pt in e.polygon])
            r = float(e.attrs.get("radius_px") or size)
            if not any(math.hypot(c[0] - s[0][0], c[1] - s[0][1]) < max(r, s[1]) for s in strong):
                arcs.append((c, r))              # an arc no counted door explains
        used, added = set(), []
        for i, w in enumerate(weak):
            c, size = centre(w["polygon"])
            j = next((k for k, (ac, r) in enumerate(arcs) if k not in used
                      and math.hypot(c[0] - ac[0], c[1] - ac[1]) < 1.2 * max(r, size)), None)
            if j is None:
                continue
            used.add(j)
            added.append(Element(id=f"door_weak_{i}", kind="door", polygon=[tuple(p) for p in w["polygon"]],
                                 conf=round(w["p"], 2), attrs={"confirmed_by": "doors_arc", "cnn_p": w["p"]}))
        if not added:
            return
        old = det.voter.value
        det.voter.value = int(old) + len(added)
        det.voter.element_ids = list(det.voter.element_ids) + [e.id for e in added]
        det.voter.runs = [int(v) + len(added) for v in det.voter.runs] if det.voter.runs else [det.voter.value]
        det.evidence = list(det.evidence) + added
        det.voter.note = ((det.voter.note or "") + f" +{len(added)} doors the network saw weakly (p 0.35-0.5) and the arc "
                          "voter confirmed at the same spot").strip()
        notes.append(f"door fusion: {old} confident detections + {len(added)} weak detections confirmed by a door "
                     "swing arc at the same place")

    def _label_vote(self, results: list, ctx, facts: SheetFacts, notes: list[str]) -> None:
        """Vision LLM transcribes the room labels; code maps them through engine/glossary.yaml and counts."""
        from engine import label_reader as LR
        if self.llm is None or not hasattr(self.llm, "complete_vision") or not ctx.abs_path.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp")):
            return
        if ctx.intent not in LR.glossary()["intent_room_types"]:
            return
        try:
            import cv2
            from engine.registry import VoterResult
            img = cv2.imread(ctx.abs_path, cv2.IMREAD_COLOR)
            labels = LR.read_labels(img, self.llm, facts_cache.sha256_file(ctx.abs_path))
            got = LR.count(labels, ctx.intent)
            if got is None:
                return
            n, hits = got
            h, w = img.shape[:2]
            ev = []
            for i, l in enumerate(l for l in labels if l.get("text") in hits):
                if isinstance(l.get("x"), (int, float)) and isinstance(l.get("y"), (int, float)):
                    cx, cy, r = l["x"] / 100 * w, l["y"] / 100 * h, 0.025 * max(w, h)
                    ev.append(Element(id=f"label_{i}", kind="label", label=l["text"],
                                      polygon=[(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)],
                                      attrs={"read_by": "vision label reader"}))
            primary = ctx.intent in self.LABEL_PRIMARY
            if primary:
                for r in results:                   # the measured-better reader decides; the others cross-check
                    r.second_opinion = True
            note = (f"AI read the room labels {', '.join(hits) or '(none of this type)'} -> {n} "
                    f"(glossary: {', '.join(sorted({LR.norm_label(h) for h in hits})) or '-'})")
            results.append(VoterResult(voter=Voter(name="label_reader", value=int(n), element_ids=[e.id for e in ev],
                                                   runs=[int(n)], note=note),
                                       evidence=ev, unit="count", second_opinion=not primary))
            notes.append("labels read by a vision model, counted by code" + (" (decides this answer)" if primary else ""))
        except Exception as e:  # noqa: BLE001  (the label reader is optional)
            notes.append(f"label reader unavailable: {type(e).__name__}")

    def _named_rooms(self, facts: SheetFacts, ctx, notes: list[str]) -> SheetFacts:
        """Rooms named from the printed labels (vision label reader + glossary) and tagged with their floor, so planner
        queries like 'which bedroom is the smallest' or 'bedrooms on 2. KERROS' select the right rooms."""
        if self.llm is None or not hasattr(self.llm, "complete_vision") or not ctx.abs_path.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp")) or not any(e.kind == "room" for e in facts.elements):
            return facts
        try:
            import cv2
            from engine import label_reader as LR, sheetfloor
            img = cv2.imread(ctx.abs_path, cv2.IMREAD_COLOR)
            sha = facts_cache.sha256_file(ctx.abs_path)
            labels = LR.read_labels(img, self.llm, sha)
            h, w = img.shape[:2]
            facts = self._audited(facts, sha, notes)
            out = LR.name_rooms(facts, labels, w, h, sheetfloor.sheet_floors(sha))
            n = sum(1 for e in out.elements if e.attrs.get("named_by"))
            if n:
                notes.append(f"{n} rooms named from their printed labels (AI read the text, code matched label to room)")
            return out
        except Exception as e:  # noqa: BLE001
            notes.append(f"room naming skipped: {type(e).__name__}")
            return facts

    @staticmethod
    def _audited(facts: SheetFacts, sha: str, notes: list[str]) -> SheetFacts:
        """Apply the 3D build's AI audit (engine/room_audit.py): rooms both reviewers placed on text/legend/outside are
        dropped, verified missing rooms (e.g. a balcony) are added. Read from the cached geometry of this drawing."""
        f = pathlib.Path(__file__).resolve().parents[1] / "cache" / "geometry" / f"{sha}-pixels.json"
        if not f.exists():
            return facts
        try:
            g = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            return facts
        aud = (g.get("check") or {}).get("audit") or {}
        drop, added = set(aud.get("drop") or []), set(aud.get("added") or [])
        if not drop and not added:
            return facts
        out = facts.model_copy(deep=True)
        out.elements = [e for e in out.elements if e.id not in drop]
        for r in g.get("rooms") or []:
            if r.get("id") in added:
                out.elements.append(Element(id=r["id"], kind="room", subtype=r.get("subtype"), label=r.get("label"),
                                            polygon=[tuple(p) for p in r["polygon"]],
                                            attrs={"added_by": "AI audit, region verified by code"}))
        notes.append(f"AI audit applied: {len(drop)} non-rooms removed, {len(added)} labelled rooms added")
        return out

    READER_Q = {"window": "How many windows are shown on this floor plan?",
                "door": "How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count.",
                "toilet": "How many toilet bowls (WC seats) are drawn on this floor plan?",
                "sink": "How many sinks and wash basins (kitchen and bathroom combined; a double-bowl sink counts as one) are drawn on this floor plan?"}

    def _parts_from_readers(self, plan, res, ctx, notes: list[str]) -> None:
        """A comparison like 'more windows than doors?' must use the same readers as 'how many windows?' (the
        Findings), not raw element counts. Plain count parts of a known object are recomputed that way."""
        from engine.query import execute_plan
        swapped, vals = False, []
        for spec in plan.specs:
            sel = spec.get("select")
            q = self.READER_Q.get(sel) if isinstance(sel, str) and spec.get("aggregate") == "count" \
                and not spec.get("where") and "/swiss_dwellings/" not in ctx.abs_path else None
            if q:
                po = self.ask(ctx.path, q, allow_siblings=ctx.allow_siblings, benchmark=True)
                if isinstance(po.value, (int, float)):
                    vals.append(int(po.value))
                    swapped = True
                    continue
            vals.append(None)
        if not swapped:
            return
        parts = [v if v is not None else res.groups.get(f"part{i + 1}") for i, v in enumerate(vals)]
        a, b = (parts + [None, None])[:2]
        if a is None or b is None:
            return
        if plan.combine in ("greater", "less"):
            res.value = "Yes" if ((a > b) if plan.combine == "greater" else (a < b)) else "No"
        elif plan.combine == "difference":
            res.value = a - b
        elif plan.combine == "ratio" and b:
            res.value = round(a / b, 4)
        elif plan.combine == "sum":
            res.value = sum(p for p in parts if p is not None)
        res.groups = {f"part{i + 1}": p for i, p in enumerate(parts)}
        notes.append("counts in this comparison come from the same readers as the Findings")

    def _with_walls(self, facts: SheetFacts, ctx, po: ProofObject, notes: list[str]) -> SheetFacts:
        """Scans carry no wall elements; for wall questions add the CNN wall pieces (same walls as the 3D view) with
        footprint area, centre-line length and volume through the drawing scale and a style ceiling height."""
        try:
            import cv2
            from shapely.geometry import Polygon
            from engine import geometry3d
            from engine.decide.vibe import load_vibe
            img = cv2.imread(ctx.abs_path, cv2.IMREAD_COLOR)
            got = geometry3d.cnn_walls(img) if img is not None else None
            if not got or not got[0]:
                return facts
            sc = self._scale(facts, facts_cache.sha256_file(ctx.abs_path))
            px = sc.px_per_m
            h = float(load_vibe("standard")["ceiling_height_m"]["value"])
            els = list(facts.elements)
            for i, wl in enumerate(got[0]):
                g = Polygon(wl["outer"], wl["holes"]).buffer(0)
                if g.area <= 0:
                    continue
                attrs = {"area_px": round(g.area, 1)}
                if px:
                    a_m2 = g.area / px ** 2
                    # centre-line length of a band of walls ~ area / mean thickness (thickness from the outline)
                    thick = max(1e-6, 2 * g.area / max(g.length, 1e-6))
                    length_m = (g.area / thick) / px
                    attrs.update(area_m2=round(a_m2, 3), length_m=round(length_m, 2), volume_m3=round(a_m2 * h, 3))
                els.append(Element(id=f"wall_{i}", kind="wall", polygon=[tuple(p) for p in wl["outer"]], attrs=attrs))
            if px:
                po.assumptions.append(_scale_assumption(sc))
                po.assumptions.append(Assumption(key="wall_height_m", value=h, unit="m", tag=Tag.defaulted,
                                                 source="standard style ceiling height"))
            notes.append(f"walls: {len(got[0])} wall pieces from the 3D wall reader added for this question")
            return facts.model_copy(update={"elements": els})
        except Exception as e:  # noqa: BLE001
            notes.append(f"walls unavailable: {type(e).__name__}")
            return facts

    def _apply_overrides(self, results: list, sha: str, intent: str, po: ProofObject, notes: list[str]) -> None:
        """A user verdict ("this IS / is NOT a door") corrects every voter's element set: a voter that lacks a
        confirmed element gains it, a voter that has a rejected one loses it (match: IoU >= 0.3). Values change by
        those corrections only, and the tier is then recomputed from agreement as usual, so resolving every
        disputed element is what turns an answer green. Each verdict is recorded as a `chosen` assumption."""
        verdicts = self.overrides.get((sha, intent)) or []
        if not verdicts:
            return
        from shapely.geometry import Polygon

        def poly(pts):
            try:
                g = Polygon([(float(p[0]), float(p[1])) for p in pts])
                return g if g.is_valid and g.area > 0 else g.buffer(0)
            except Exception:  # noqa: BLE001
                return None

        def iou(a, b):
            if a is None or b is None or a.is_empty or b.is_empty:
                return 0.0
            u = a.union(b).area
            return a.intersection(b).area / u if u else 0.0

        for r in results:
            if not isinstance(r.voter.value, (int, float)) or r.exact:
                continue
            own = [poly([(pt.x, pt.y) if hasattr(pt, "x") else pt for pt in e.polygon]) for e in r.evidence]
            delta = 0
            for v in verdicts:
                g = poly(v["polygon"])
                has = any(iou(g, o) >= 0.3 for o in own)
                if v["keep"] and not has:
                    delta += 1
                elif not v["keep"] and has:
                    delta -= 1
            if delta:
                r.voter.value = max(0, int(r.voter.value) + delta)
                r.voter.note = (r.voter.note + "; " if r.voter.note else "") + f"user corrections {delta:+d}"
        for v in verdicts:
            po.assumptions.append(Assumption(key=f"user:{intent}:{v.get('id', '?')}", value=bool(v["keep"]),
                                             tag=Tag.chosen, source="user"))
        notes.append(f"user verdicts applied: {sum(v['keep'] for v in verdicts)} confirmed, "
                     f"{sum(not v['keep'] for v in verdicts)} rejected")

    def _sheet_text(self, ctx, rt: Route, facts: SheetFacts, scale: Optional[ScaleInfo], po: ProofObject, notes: list[str]) -> list:
        """Sheet-level text answers computed by code: largest/smallest room, overall size (query engine), scale."""
        from engine import query
        from engine.registry import VoterResult
        px = ctx.params.get("_px_per_m")
        if rt.intent == "scale_info":
            if scale is not None and scale.px_per_m and not scale.needs_user:
                src = "; ".join(a.note or a.kind for a in scale.anchors if a.kind != "door_prior") or "solved scale"
                v = f"1 m = {scale.px_per_m:.1f} px on this image ({src})"
                po.assumptions.append(_scale_assumption(scale))
                po.scale = scale
                return [VoterResult(Voter(name="scale_solver", value=v, note=src), unit="label")]
            return []
        spec = query.spec_for(rt.intent, {}, None)
        if rt.intent == "overall_size":
            fps = sorted((e.id for e in facts.elements if e.kind == "footprint"),
                         key=lambda i: (not next(x for x in facts.elements if x.id == i).attrs.get("from_walls"),
                                        next(x for x in facts.elements if x.id == i).attrs.get("source") != "outline",
                                        int(i.rsplit("_", 1)[-1]) if i.rsplit("_", 1)[-1].isdigit() else -1))
                                         # verified outline first, then wall-network outlines, then main view first
            if fps:                                  # several plan views (foundation + roof): the main view's outline
                spec = {**spec, "where": {"id": fps[0]}}
                if len(fps) > 1:
                    notes.append(f"{len(fps)} plan views on the sheet; the outline of the main one is measured")
            else:
                spec = {**spec, "select": ["room"]}
        if spec is None:
            return []
        res = query.run(spec, facts, px)
        po.query_spec = spec
        for n in res.notes:
            notes.append(f"query: {n}")
        if res.value is None:
            return []
        by = {e.id: e for e in facts.elements}
        if scale is not None and px:
            po.scale = scale
        return [VoterResult(Voter(name="sheet_query", value=res.value, element_ids=res.evidence_ids, runs=[],
                                  note="computed from the sheet's recognised outline / rooms"),
                            evidence=[by[i] for i in res.evidence_ids if i in by], unit=res.unit)]

    def _printed(self, ctx, rt: Route, kind: str, facts: SheetFacts, scale: Optional[ScaleInfo], po: ProofObject,
                 notes: list[str], results: list):
        """Answers the sheet PRINTS (tag `specified`, evidence = the printed words). Returns (results, kind) or None."""
        import re as _re
        from engine import sheet_lookup as L
        from engine.registry import VoterResult
        q, ap, sha = ctx.question, ctx.abs_path, po.provenance.sha256

        def vr(name, value, boxes, label, note, unit=None, exact=True, second=False, prefix="printed"):
            ev = L.element_boxes(f"{prefix}_{name}", boxes, label)
            return VoterResult(Voter(name=name, value=value, element_ids=[e.id for e in ev], note=note), evidence=ev,
                               unit=unit, exact=exact, second_opinion=second)

        if rt.intent == "overall_size":
            sc = scale if scale is not None and scale.px_per_m else self._scale(facts, sha)
            od = L.overall_dims(ap, sha, sc.px_per_m if sc else None)
            if not (od and "w" in od and "d" in od):
                return None
            v = f"{od['w']['m']:.2f} m x {od['d']['m']:.2f} m"
            why = f"width {od['w']['text']}: {od['w']['how']}; depth {od['d']['text']}: {od['d']['how']}"
            notes.append(f"printed answer: {v} ({od['w']['text']} x {od['d']['text']} printed on the sheet; {why}).")
            po.scale = sc
            for r in results:
                r.second_opinion = True
            return [vr("printed_dimensions", v, [od["w"]["box"], od["d"]["box"]], None, why, unit="label")] + results, "text"

        want_count = bool(_re.search(r"\bhow\s+many\b|\bnumber\s+of\b", q, _re.I))
        if want_count and (rt.intent == "unknown" or (rt.intent in _DETECTOR_KINDS and not results)):
            noun = L._noun(q) or ""
            cc = L.class_count(ap, sha, noun) if noun else None     # 'how many valves': every valve-type series
            tc = None if cc else L.tag_count(ap, sha, q)
            lk = L.lookup(ap, sha, q)
            res = []
            if cc:
                parts = "; ".join(f"{g['n']} {g['series']} ({g['meaning']}; {g['why']}"
                                  + (f": {', '.join(g['tags'][:8])}" if g["tags"] else "") + ")" for g in cc["groups"])
                boxes = [b for g in cc["groups"] for b in g["boxes"]]
                res.append(vr("tag_classes", cc["total"], boxes, None, f"{cc['total']} {noun} tagged on the sheet: {parts}",
                              exact=False, prefix="tag"))
                notes.append(f"printed answer: {cc['total']} {noun} tagged on the sheet — {parts}.")
                return res, "count"
            if lk and lk["kind"] == "count":
                res.append(vr("printed_count", lk["value"], lk["boxes"], lk["text"], f"the sheet prints '{lk['text']}'"))
            if tc:
                val = tc["numbered"] if tc["missing"] else tc["read"]
                nt = (f"{tc['read']} distinct {tc['prefix']} tags read on the sheet ({', '.join(tc['tags'])}); "
                      f"{tc['prefix']} = {tc['noun']} from {tc['why']}")
                if tc["missing"]:
                    nt += f"; the numbering implies {tc['numbered']} (not read: {', '.join(tc['missing'])})"
                res.append(vr("equipment_tags", val, tc["boxes"], None, nt, exact=False, second=bool(res), prefix="tag"))
            if not res:
                return None
            v = res[0].voter.value
            src = res[0].voter.note
            other = [r.voter for r in res[1:] if r.voter.value != v]
            notes.append(f"printed answer: {v} ({src}" + (f"; but {other[0].note}" if other else "") + ").")
            return res, "count"

        fp = next((e for e in facts.elements if e.kind == "footprint" and e.attrs.get("source") == "outline"), None)
        area_q = kind == "area" or (rt.intent == "unknown" and bool(L.AREA_CUE.search(q)))

        def outline_area():
            if fp is None:
                return None
            a = float(fp.attrs["area_m2"])
            notes.append(f"printed answer: {a:.1f} m² measured inside the building outline "
                         f"({fp.attrs.get('bbox_m', ['?', '?'])[0]} x {fp.attrs.get('bbox_m', ['?', '?'])[1]} m, "
                         f"{fp.attrs.get('method')}; scale {fp.attrs.get('px_per_m', 0):.1f} px/m from the sheet).")
            return [VoterResult(Voter(name="outline_area", value=a, element_ids=[fp.id],
                                      note=f"area inside the building outline read from {fp.attrs.get('method')}"),
                                evidence=[fp], unit="m2")], "area"

        if area_q and kind != "area":
            lk = L.lookup(ap, sha, q)
            if lk and lk["kind"] == "area" and lk["coverage"] >= 0.99:
                kind = "area"
            else:
                return outline_area()
        if kind == "area":
            lk = L.lookup(ap, sha, q)
            generic = {"building", "room", "floor", "plan", "house", "structure", "space", "sheet", "drawing", "everything"}
            if (lk and lk["kind"] == "text" and lk["coverage"] >= 0.99
                    and not set(lk["keywords"]) <= generic and rt.intent == "total_room_area"):
                # 'how big is the SUMP?' names a printed thing: its note answers, not the building's total area
                notes.append(f"printed answer: the sheet prints '{lk['printed']}'.")
                return [vr("printed_note", lk["printed"], lk["boxes"], lk["text"], f"the sheet prints '{lk['text']}'",
                           unit="label")], "text"
            if lk and lk["kind"] == "area" and lk["coverage"] >= 0.99:
                notes.append(f"printed answer: {lk['printed']} = {lk['value']:.1f} m² (the sheet prints '{lk['text']}').")
                return [vr("printed_area", float(lk["value"]), lk["boxes"], lk["text"], f"the sheet prints '{lk['text']}'",
                           unit="m2")], "area"
            gross = bool(_re.search(r"\b(slab|footprint|building|gross|pad|foundation|plot|whole\s+floor)\b", q, _re.I))
            if rt.intent == "total_room_area" and gross and fp is not None and not L.printed_total_area(ap, sha):
                return outline_area()             # 'total SLAB area' = the outline, not the sum of the panels in it
            if rt.intent == "total_room_area":
                pt = L.printed_total_area(ap, sha)
                if pt:
                    for r in results:
                        r.second_opinion = True
                    meas = next((r.voter.value for r in results if isinstance(r.voter.value, (int, float))), None)
                    cmp = (f"; measured from the drawing: {meas:.0f} m² ({(meas / pt['m2'] - 1) * 100:+.0f}%)"
                           if meas else "")
                    notes.append(f"printed answer: {pt['printed']} = {pt['m2']:.1f} m² (the sheet prints '{pt['text']}'{cmp}).")
                    return [vr("printed_total_area", float(pt["m2"]), [pt["box"]], pt["text"],
                               f"the sheet prints '{pt['text']}'", unit="m2")] + results, "area"
                if not results:
                    return outline_area()
            return None

        if rt.intent == "unknown" or (kind == "text" and not results):
            lk = L.lookup(ap, sha, q)
            if not lk:
                return None
            k = lk["kind"]
            val = lk["value"] if k != "text" else lk["printed"]
            alts = "".join(f"; also printed: '{a['text']}'" for a in lk.get("alts", [])[:2])
            shown = lk["printed"] if k == "text" else f"{lk['printed']}"
            notes.append(f"printed answer: the sheet prints '{shown}'{alts}.")
            unit = "m2" if k == "area" else ("label" if k == "text" else None)
            return [vr("printed_note", val, lk["boxes"], lk["text"], f"the sheet prints '{lk['text']}'", unit=unit)], k
        return None

    def _sheet_grey(self, po: ProofObject, rt: Route, facts: SheetFacts, scale: Optional[ScaleInfo], notes: list[str]) -> ProofObject:
        prof = facts.extras.get("profile") or {}
        kinds = {e.kind for e in facts.elements}
        why = None
        if rt.intent in ("rooms_count", "total_room_area", "largest_room", "smallest_room") and "room" not in kinds and (
                rt.intent == "rooms_count" or "zone" not in kinds):
            why = "no enclosed rooms or colour-filled zones were recognised on this sheet"
            if prof.get("sheet_type") == "cad_sheet":
                why += f" ({prof.get('sheet_type').replace('_', ' ')}: {len(prof.get('views') or [])} views, main plan view read from line geometry)"
        elif rt.intent == "overall_size" and scale is not None and scale.px_per_m:
            why = "no building outline could be recognised in the main plan view"
        elif rt.intent in ("total_room_area", "overall_size", "scale_info") or any("scale" in n for n in notes):
            why = "the drawing's scale is not known yet: give one real length (a printed dimension or a known door width)"
            if scale is not None:
                po.decisions_open.append(self._scale_decision(facts, scale if scale.px_per_m else ScaleInfo(needs_user=True)))
        elif rt.intent == "rooms_count":
            why = "no individual rooms recognised (only colour-filled zones or none)"
        return self._grey(po, why or "the sheet has nothing this question can be computed from")

    @staticmethod
    def _grey(po: ProofObject, reason: str) -> ProofObject:
        po.tier, po.value, po.refusal = Tier.grey, None, reason
        po.notes.append(f"refused: {reason}")
        return po

    def _vote(self, ctx, notes: list[str]) -> list:
        out = []
        for name, fn in registry.voters_for(ctx.kind):
            try:
                r = fn(ctx)
            except Exception as e:  # noqa: BLE001
                notes.append(f"voter {name} failed: {type(e).__name__}: {e}")
                log.warning("voter %s raised", name, exc_info=True)
                continue
            if r is not None:
                out.append(r)
        return out

    def _scale(self, facts: SheetFacts, sha: str) -> ScaleInfo:
        user = tuple(self.user_anchors.get(sha, []))
        if facts.scale and facts.scale.px_per_m and not user:
            return facts.scale
        try:
            from engine.scale.anchors import solve
            return solve(facts, user)
        except Exception:  # noqa: BLE001
            return facts.scale or ScaleInfo(needs_user=True)

    def _attach_scale(self, po: ProofObject, scale: Optional[ScaleInfo], facts: SheetFacts, value: float) -> None:
        if "vector" in facts.extras or po.provenance.resolved_from in ("dxf", "ifc"):
            # exact CAD/BIM read: values are already in metres; no door guess, no 'ask for a reference length'
            po.scale = ScaleInfo(px_per_m=1.0, rel_sigma=0.001, anchors=[], widths_relative=False, needs_user=False)
            return
        if scale is not None and scale.px_per_m:
            po.scale = scale
            if scale.rel_sigma is not None and po.kind == "area":
                from engine.takeoff.area import area_interval
                lo, hi = area_interval(float(value), scale.rel_sigma)
                po.interval = Interval(lo=lo, hi=hi)
            if scale.needs_user:
                po.decisions_open.append(self._scale_decision(facts, scale))
                po.notes.append("scale rests on the door prior only: ask the user for a reference length")
        else:
            # real-unit source (vector/IFC): values are already metres, no scale was needed
            po.scale = ScaleInfo(px_per_m=1.0, rel_sigma=0.001, anchors=[], widths_relative=False, needs_user=False)
            po.notes.append("real-unit source: px_per_m=1 means coordinates are metres")
            if scale is not None and scale.needs_user and not po.evidence:
                po.decisions_open.append(self._scale_decision(facts, scale))

    @staticmethod
    def _scale_decision(facts: SheetFacts, scale: ScaleInfo) -> Decision:
        opts: list[Option] = []
        try:
            from engine.scale.anchors import next_question
            for q in next_question(facts, scale):
                opts.append(Option(value=q.anchor_kind, label=q.question,
                                   note=f"scale sigma -> {q.expected_rel_sigma:.3f}"))
        except Exception:  # noqa: BLE001
            pass
        if not opts:
            opts = [Option(value="user", label="draw a line of known length and type it")]
        return Decision(key="scale", question="What is the scale of this drawing?", options=opts,
                        default=opts[0].value, tag=Tag.open)

    def _plan_vote(self, ctx, question, facts, po: ProofObject, notes: list[str]):
        """Planner path: the LLM drafts a query_spec; code executes it. The number never comes from the LLM."""
        from engine import query
        from engine.query import planner
        from engine.registry import VoterResult

        cost = Cost()
        if re.search(r"\bwall|partition|seinä|wand|mur\b|parete", question, re.I) and \
                not any(e.kind == "wall" for e in facts.elements) and "vector" not in facts.extras:
            facts = self._with_walls(facts, ctx, po, notes)
        facts = self._named_rooms(facts, ctx, notes)
        try:
            try:
                plan = planner.plan(question, facts, self.planner_llm or self.llm)
            except Exception as e:  # noqa: BLE001  (strong model failed / empty: fall back to the fast one)
                if self.planner_llm is None:
                    raise
                notes.append(f"strong planner failed ({type(e).__name__}); fast planner used")
                plan = planner.plan(question, facts, self.llm)
            cost = plan.cost
            px = ctx.params.get("_px_per_m")
            res = query.execute_plan(plan.specs, plan.combine, facts, px)
            if len(plan.specs) > 1:
                self._parts_from_readers(plan, res, ctx, notes)
            if res.value is None and res.needs_scale and not px:
                # areas on a scan without a printed scale: fall back to the engine's scale (door-width prior or the
                # user's anchors), say so, and let the user type the real size
                sc = self._scale(facts, facts_cache.sha256_file(ctx.abs_path))
                if sc.px_per_m:
                    res = query.execute_plan(plan.specs, plan.combine, facts, sc.px_per_m)
                    po.scale = sc
                    po.assumptions.append(_scale_assumption(sc))
                    if not any(a.kind in ("user", "dimension", "scale_bar", "printed_ratio", "printed_area")
                               for a in sc.anchors):
                        notes.append("no printed scale: sizes assume typical 0.9 m doors; enter a real dimension to fix")
                    else:
                        notes.append("scale: " + "; ".join(a.note or a.kind for a in sc.anchors if a.kind != "door_prior"))
        except Exception as e:  # noqa: BLE001
            notes.append(f"planner failed: {type(e).__name__}: {e}")
            m = re.search(r"unsupported: (.+)", str(e))
            if m:
                po.refusal = f"this question needs something the query engine cannot express yet ({m.group(1)})"
            c = getattr(e, "cost", None)
            if c is not None:  # LLM was called but the spec was rejected: account the call, no planner answer
                po.cost = Cost(**{**po.cost.model_dump(), "llm_calls": c.llm_calls, "tokens_in": c.tokens_in,
                                  "tokens_out": c.tokens_out, "usd": c.usd})
            return [], cost
        po.cost = Cost(**{**po.cost.model_dump(), "llm_calls": cost.llm_calls, "planner_calls": cost.planner_calls,
                          "tokens_in": cost.tokens_in, "tokens_out": cost.tokens_out, "usd": cost.usd})
        po.query_spec = plan.specs[0] if len(plan.specs) == 1 else {"parts": plan.specs, "combine": plan.combine}
        if res.value is None or isinstance(res.value, list):
            notes.append("planner spec ran but produced no scalar (needs scale or list answer)")
            miss = next((n.split(": ", 1)[1] for n in res.notes if n.startswith("no matching elements")), None)
            if miss:
                po.refusal = miss                    # e.g. "no bathroom recognised on this drawing"
            return [], cost
        by = {e.id: e for e in facts.elements}
        if res.unit == "ratio":
            po.kind = "other"                       # a share/ratio: keep the fraction, never round to a count
        elif po.kind not in ("area", "length", "volume") and res.unit in ("m2", "m", "m3"):
            po.kind = {"m2": "area", "m": "length", "m3": "volume"}[res.unit]
        elif res.unit == "count":
            po.kind = "count"
        notes.append("answer computed by code from an LLM-drafted query_spec")
        po.reliability_note = ("computed by a query the LLM drafted (shown below); no measured reliability for "
                               "free-form questions yet: check the parts and the highlighted elements")
        for n in res.notes:
            notes.append(f"query: {n}")
        if res.groups:
            notes.append("query parts: " + ", ".join(f"{k}={v}" for k, v in res.groups.items()))
        if isinstance(res.value, str):                  # "which room ..." -> a name, not a number
            po.kind = "text"
            v = res.value
        else:
            v = int(res.value) if po.kind == "count" else float(res.value)
        return [VoterResult(Voter(name="planner_query", value=v, element_ids=res.evidence_ids,
                              runs=[] if isinstance(v, str) else [v],
                                  note="LLM-drafted spec executed by the query engine"),
                            evidence=[by[i] for i in res.evidence_ids if i in by], unit=res.unit)], cost

    # ------------------------------------------------------------------ prior
    def _prior_value(self, path: str, intent: str, kind: str):
        if self._prior is None:
            self._prior = _load_priors()
        src = path.split("/")[1] if "/" in path else "unknown"
        p = self._prior
        v = p["intent"].get(intent)
        if v is None:
            v = p["source_type"].get(f"{src}|{kind}")
        if v is None:
            v = p["type"].get(kind)
        if v is None:
            return (0 if kind == "count" else None), "no prior available"
        v = int(round(v)) if kind == "count" else float(v)
        return v, f"benchmark best guess: per-{'intent' if intent in p['intent'] else 'source/type'} dev-median prior"


_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()


def _file_lock(sha: str, allow: bool) -> "threading.Lock":
    with _LOCKS_GUARD:
        return _LOCKS.setdefault((sha, allow), threading.Lock())


def _scan_check_refusal(sha: str) -> Optional[str]:
    """If the scan check (2 wall readers + 2 vision reviewers, api /api/geometry) already ran on this file and found
    no floor plan, floor-plan questions do not apply. Reads the cached result only; never calls a model here."""
    try:
        import json as _json
        f = ROOT / "cache" / "geometry" / f"{sha}-pixels.json"
        if not f.exists():
            return None
        views = (_json.loads(f.read_text()).get("check") or {}).get("views") or []
        types = [v.get("type") for v in views if v.get("type")]
        src = {v.get("type_source", "") for v in views}
        if types and "floor_plan" not in types and any("reviewer" in s for s in src):
            shown = ", ".join(sorted({t.replace("_", " ") for t in types}))
            return (f"this sheet shows a {shown}, not a floor plan (scan check: two AI reviewers agree), "
                    "so floor-plan counts do not apply")
    except Exception:  # noqa: BLE001
        return None
    return None


def _scale_assumption(sc: ScaleInfo) -> Assumption:
    """Where the drawing's scale came from, as an assumption with an honest tag."""
    kinds = {a.kind for a in sc.anchors}
    if "user" in kinds:
        tag, src = Tag.chosen, "your measurement"
    elif kinds & {"dimension", "scale_bar", "printed_ratio", "printed_area"}:
        a = next(a for a in sc.anchors if a.kind in ("dimension", "scale_bar", "printed_ratio", "printed_area"))
        tag, src = Tag.specified, f"measurements printed on the drawing: {a.note or a.kind}"
    else:
        tag, src = Tag.defaulted, "typical door width (0.9 m) on this drawing"
    return Assumption(key="scale_px_per_m", value=round(sc.px_per_m, 3), unit="px/m", tag=tag, source=src)


def _native(x):
    """numpy scalars/arrays -> plain Python, recursively."""
    if isinstance(x, dict):
        return {k: _native(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_native(v) for v in x]
    if hasattr(x, "item") and type(x).__module__ == "numpy":
        return x.tolist() if getattr(x, "ndim", 0) else x.item()
    return x


def _load_priors() -> dict:
    """Dev-split medians (the same prior the `prior` baseline uses), cached in cache/priors.json."""
    f = ROOT / "cache" / "priors.json"
    try:
        return json.loads(f.read_text())
    except Exception:  # noqa: BLE001
        pass
    empty: dict = {"intent": {}, "source_type": {}, "type": {}}
    try:
        from evalkit.data import load_questions
        from evalkit.run import PriorEngine
        dev = [q for q in load_questions() if q.split == "dev"]
        pe = PriorEngine(dev)
        data = {"intent": dict(pe.median_intent),
                "source_type": {f"{k[0]}|{k[1]}": v for k, v in pe.median_source_type.items()},
                "type": dict(pe.median_type)}
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data))
        return data
    except Exception:  # noqa: BLE001
        log.warning("priors unavailable", exc_info=True)
        return empty
