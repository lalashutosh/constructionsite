"""PipelineEngine: sha256 cache -> triage -> sibling resolve -> extract -> vote -> tier -> ProofObject.

Everything outside the registry is optional: with ZERO plugins this returns an amber 0 with a note. Extraction and
voting make no network calls; the LLM (LLM_PROVIDER != none) only classifies templates and drafts query specs."""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import os
import pathlib
import statistics
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
        for fn in fns:
            try:
                f = fn(use_path if fn.__module__.startswith("engine.vector") else use_abs, allow_siblings=allow)
                f.provenance.file = path
                return f
            except Exception as e:  # noqa: BLE001
                err = f"{fn.__module__}: {type(e).__name__}: {e}"
        return SheetFacts(provenance=Provenance(file=path), sheet_type="unknown", legible=False,
                          legibility_note=f"extraction failed ({err})")

    # ------------------------------------------------------------------ ask
    def ask(self, path: str, question: str, *, allow_siblings: bool = True, benchmark: bool = True,
            progress: Optional[Callable[[str], None]] = None) -> ProofObject:
        t0 = time.perf_counter()
        stage = progress or (lambda s: None)
        rt = route_question(question, path, classifier=self.classifier)
        po = self._ask(path, question, rt, allow_siblings, benchmark, stage)
        if rt.layer == "regex-complex":       # LLM off and the question asks more than the matched template
            if po.tier == Tier.green:
                po.tier = Tier.amber
            po.notes.append(f"this answers the simpler question '{rt.intent}'; the question asks more "
                            "(turn the planner on: LLM_PROVIDER=verda)")
        po.cost.ms = (time.perf_counter() - t0) * 1000
        for f in ("llm_calls", "tokens_in", "tokens_out", "usd"):
            setattr(po.cost, f, getattr(po.cost, f) + getattr(rt.cost, f))
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
        if kind in ("area", "length", "volume"):
            scale = self._scale(facts, sha)
            if scale.px_per_m:
                ctx.params["_px_per_m"] = scale.px_per_m

        # vote
        stage("vote")
        results = self._vote(ctx, notes)
        if kind == "count":
            self._apply_overrides(results, sha, rt.intent, po, notes)
        planner_cost = Cost()
        if not results and self.llm is not None and rt.intent == "unknown":
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
                return self._grey(po, "no extractor could answer this question from the drawing")
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

        # evidence
        seen: set[str] = set()
        for r in results:
            for e in r.evidence:
                if e.id not in seen and len(po.evidence) < 400 and len(e.polygon) >= 2:
                    seen.add(e.id)
                    po.evidence.append(e)
        if not po.evidence and results:
            by = {e.id: e for e in facts.elements}
            for r in results:
                for i in r.voter.element_ids[:400]:
                    if i in by and i not in seen and len(by[i].polygon) >= 2:
                        seen.add(i)
                        po.evidence.append(by[i])

        for e in po.evidence:                 # voters may leak numpy scalars into attrs (JSON can't encode them)
            e.attrs = _native(e.attrs)
        unit = next((r.unit for r in results if r.unit), None)
        po.unit = unit or {"area": "m2", "length": "m", "volume": "m3", "count": "count"}.get(kind)
        po.value = value
        po.tier = Tier.amber if (capped and tier != Tier.grey) else tier
        if kind in ("area", "length", "volume") and value is not None:
            self._attach_scale(po, scale, facts, value)
        for name, fn in registry.calibrators():
            try:
                p = fn(po.model_dump(mode="json"))
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                notes.append(f"historically right {p:.0%} of the time at this agreement level")
        log.info("ask %s intent=%s kind=%s value=%s tier=%s voters=%s", path, rt.intent, kind, po.value,
                 po.tier.value, [v.name for v in po.voters])
        return po

    # ------------------------------------------------------------------ helpers
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
        try:
            plan = planner.plan(question, facts, self.llm)
            cost = plan.cost
            res = query.execute_plan(plan.specs, plan.combine, facts, ctx.params.get("_px_per_m"))
        except Exception as e:  # noqa: BLE001
            notes.append(f"planner failed: {type(e).__name__}: {e}")
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
            return [], cost
        by = {e.id: e for e in facts.elements}
        if po.kind not in ("area", "length", "volume") and res.unit in ("m2", "m", "m3"):
            po.kind = {"m2": "area", "m": "length", "m3": "volume"}[res.unit]
        elif res.unit == "count":
            po.kind = "count"
        notes.append("answer computed by code from an LLM-drafted query_spec")
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
