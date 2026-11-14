"""Registry glue: sibling resolver (priority 10) + exact-source voters.

Voters (the pipeline computes the tier from their agreement):
  slot 0  `ifc_exact` / `dxf_exact` / `pdf_vector`  : the primary exact reading
  slot 1  `ifc_geometry` / `dxf_alt`                : an independent second reading of the SAME exact file
  slot 2  `ifc_property`                            : (IFC rooms) the author's rounded area property
A single exact voter is flagged in its note ("exact source, single voter"): never green on one voter.
Every VoterResult carries exact=True; `Ctx.resolved` (or our own resolve) tells which file/format was used.
"""
from __future__ import annotations

import os
import pathlib
from functools import lru_cache
from typing import Optional

from contracts.proof import Element, Voter
from engine import registry
from engine import siblings

_IFC = ".ifc"


def _fmt_of(path: str) -> str:
    ext = pathlib.Path(path).suffix.lower().lstrip(".")
    return {"ifc": "ifc", "dxf": "dxf", "svg": "svg", "pdf": "pdf-vector", "png": "png"}.get(ext, ext)


def _target(ctx) -> Optional[tuple[str, str, Optional[str]]]:
    """(relative path, fmt, note) of the file to read, or None."""
    if ctx.allow_siblings:
        r = ctx.resolved or siblings.resolve(ctx.path, True)
        if r is not None:
            return r.path, r.fmt, r.note
    fmt = _fmt_of(ctx.path)
    if fmt in ("ifc", "dxf", "svg", "pdf-vector"):
        return ctx.path, fmt, None
    return None


def _swiss_pdf(pdf_path, intent, question, params):
    from . import swisspdf
    from .dxf_query import DxfAnswer
    return [DxfAnswer(n, v, u, note, els) for (n, v, u, note, els) in swisspdf.answer(pdf_path, intent, question, params)]


@lru_cache(maxsize=256)
def _compute(abs_path: str, fmt: str, intent: str, question: str, params_key: tuple):
    params = dict(params_key)
    if fmt == "ifc":
        from . import ifc_query
        if intent not in ifc_query.INTENTS:
            return ()
        return tuple(ifc_query.answer(abs_path, intent, question, params))
    if fmt == "dxf":
        from . import dxf_query
        if intent not in dxf_query.INTENTS:
            return ()
        dx = list(dxf_query.answer(abs_path, intent, question, params))
        pdf_path = abs_path[:-4] + ".pdf"           # same-stem sibling of the same drawing: independent reading
        px = []
        if os.path.exists(pdf_path):
            try:
                px = _swiss_pdf(pdf_path, intent, question, params)
            except Exception:
                px = []
        if intent in ("toilets", "washbasins", "bathtubs", "showers") and px:
            # the PDF symbol counts are exact on the answer key; the DXF cluster classifier is a fitted heuristic
            return tuple(px + dx)
        main, alt = [a for a in dx if a.voter == "dxf_exact"], [a for a in dx if a.voter != "dxf_exact"]
        return tuple(main + alt + px)
    if fmt == "svg":
        from . import svgvec
        return tuple(svgvec.answer(abs_path, intent, question, params))
    if fmt == "pdf-vector":
        if "/swiss_dwellings/" in abs_path.replace("\\", "/"):
            return tuple(_swiss_pdf(abs_path, intent, question, params))
        from . import schedule, pdfvec
        a = schedule.answer(abs_path, intent, question, params)
        if not a and intent in ("room_net_area", "total_net_area_storey", "count_on_storey"):
            a = pdfvec.answer(abs_path, intent, question, params)
        return tuple(a)
    return ()


def _slot(ctx, k: int):
    tgt = _target(ctx)
    if tgt is None:
        return None
    rel, fmt, rnote = tgt
    root = siblings.dataset_root()
    abs_path = str(root / rel) if not pathlib.Path(rel).is_absolute() else rel
    pkey = tuple(sorted((a, str(b)) for a, b in (ctx.params or {}).items()))
    try:
        answers = _compute(abs_path, fmt, ctx.intent, ctx.question, pkey)
    except Exception as e:  # never let a parser bug break the batch
        return None if k else registry.VoterResult(
            voter=Voter(name=f"{fmt}_error", value=None, note=f"{type(e).__name__}: {e}"[:200]), exact=False)
    if not answers or k >= len(answers):
        return None
    a = answers[k]
    name = a.voter
    if fmt == "pdf-vector" and name == "dxf_exact":
        name = "pdf_vector"
    note = a.note
    if k == 0 and len(answers) == 1 and "single voter" not in note:
        note += "; exact source, single voter"
    if rnote and k == 0:
        note += f" [{rnote}]"
    ev: list[Element] = []
    ids: list[str] = []
    if hasattr(a, "elements"):
        for (eid, kind, pts, label, attrs) in a.elements[:400]:
            ev.append(Element(id=eid, kind=kind, polygon=pts, label=label, attrs=attrs,
                              subtype=attrs.get("subtype")))
            ids.append(eid)
    elif getattr(a, "element_ids", None):
        ids = list(a.element_ids)[:400]
        ev = [Element(id=i, kind="ifc_element", polygon=[]) for i in ids[:200]]
    value = a.value
    if a.unit == "count":
        value = int(round(value))
    else:
        value = round(float(value), 4)
    return registry.VoterResult(voter=Voter(name=name, value=value, element_ids=ids, note=note),
                                evidence=ev, unit=a.unit, exact=True)


def voter_primary(ctx):
    return _slot(ctx, 0)


def voter_second(ctx):
    return _slot(ctx, 1)


def voter_third(ctx):
    return _slot(ctx, 2)


def resolver(path: str, allow: bool):
    return siblings.resolve(path, allow)


def extract(path: str, allow_siblings: bool = True):
    """Sheet-level facts for a vector file (pdf/dxf/ifc/svg) so the pipeline does not fall through to the raster
    extractor. Values come from the exact-source voters; this only records provenance, licence and credit.
    Raises if the file cannot be opened, so the pipeline can still try the raster route (scanned PDFs)."""
    from contracts.proof import Provenance, SheetFacts
    from engine.vector import credits

    root = siblings.dataset_root()
    p = pathlib.Path(path)
    abs_path = p if p.is_absolute() else root / path
    if not abs_path.exists() or abs_path.stat().st_size == 0:
        raise FileNotFoundError(f"vector file not found or empty: {abs_path}")
    fmt = _fmt_of(str(abs_path))
    if fmt == "pdf-vector":
        import fitz
        with fitz.open(str(abs_path)) as doc:
            page = doc[0]
            if not page.get_drawings() and not page.get_text().strip():
                raise ValueError("pdf has no vector paths or text (scanned?): use the raster route")
    rel = str(abs_path.relative_to(root)) if abs_path.is_relative_to(root) else path
    lic, credit = credits.lookup(root, rel)
    elements, el_note = [], None
    if fmt == "dxf":
        try:
            from engine.vector.elements import from_dxf
            elements = from_dxf(str(abs_path))
            el_note = "elements in DXF units (metres); for the query engine / planner"
        except Exception as e:  # noqa: BLE001  (elements are a bonus; exact voters do not need them)
            el_note = f"elements unavailable: {type(e).__name__}"
    sheet_type = "schedule" if "/opening_design/" in rel.replace("\\", "/") and "schedule" in rel.lower() else "floor_plan"
    return SheetFacts(provenance=Provenance(file=path, fmt=fmt, license=lic, credit=credit),
                      sheet_type=sheet_type, legible=True, elements=elements,
                      extras={"vector": {"fmt": fmt, "read_from": rel, "allow_siblings": allow_siblings,
                                         "elements_note": el_note}})


def register() -> None:
    registry.register_resolver("vector_siblings", resolver, priority=10)
    kinds = ("count", "area", "length", "volume")
    registry.register_voter("vector_exact", voter_primary, kinds=kinds)
    registry.register_voter("vector_exact_2", voter_second, kinds=kinds)
    registry.register_voter("vector_exact_3", voter_third, kinds=kinds)
