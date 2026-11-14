"""Sibling resolver: "files with the same name and a different extension are the same drawing in another format".

resolve(path, allow_siblings) -> Resolved | None
  * allow_siblings=False  -> None always (bypasses everything, including `related`).
  * priority: dxf, ifc, svg, vector pdf, png. (The task statement fixes this order; ifc and dxf never coexist
    for one stem in the dataset, so their relative order is immaterial.)
  * a sibling is only returned when it is a BETTER format than the file asked about.
  * `related=True` (or env PLUMB_RELATED=1) is an opt-in stretch, always reported as its own number:
    a per-storey PDF/SVG whose stem starts with '<ifc stem>_' maps to that model-level IFC.
    Never enabled silently.
`path` is relative to $DATASET_ROOT, like questions.jsonl.
"""
from __future__ import annotations

import os
import pathlib
from typing import Optional

from engine.registry import Resolved

PRIORITY = ("dxf", "ifc", "svg", "pdf", "png")
_FMT = {"dxf": "dxf", "ifc": "ifc", "svg": "svg", "pdf": "pdf-vector", "png": "png"}


def dataset_root() -> pathlib.Path:
    root = os.environ.get("DATASET_ROOT")
    if not root:
        try:
            from evalkit.data import dataset_root as dr  # reads .env
            return dr()
        except Exception as e:  # pragma: no cover
            raise RuntimeError("DATASET_ROOT not set") from e
    return pathlib.Path(root).expanduser()


def related_enabled() -> bool:
    return os.environ.get("PLUMB_RELATED", "") not in ("", "0", "false")


def pdf_is_vector(abs_path: pathlib.Path) -> bool:
    """True when the PDF has drawing paths or a text layer (not a pure scan)."""
    try:
        import pymupdf
        with pymupdf.open(str(abs_path)) as doc:
            if len(doc) == 0:
                return False
            pg = doc[0]
            return len(pg.get_drawings()) > 10 or len(pg.get_text("words")) > 5
    except Exception:
        return False


def _rank(ext: str) -> int:
    return PRIORITY.index(ext) if ext in PRIORITY else len(PRIORITY)


def own_format(path: str) -> str:
    ext = pathlib.Path(path).suffix.lower().lstrip(".")
    return _FMT.get(ext, ext)


def resolve(path: str, allow_siblings: bool = True, related: Optional[bool] = None,
            root: Optional[pathlib.Path] = None) -> Optional[Resolved]:
    if not allow_siblings:
        return None
    root = pathlib.Path(root) if root is not None else dataset_root()
    p = pathlib.PurePosixPath(path)
    ext = p.suffix.lower().lstrip(".")
    d = root / p.parent
    if not d.is_dir():
        return None
    if related is None:
        related = related_enabled()
    if related and ext in ("pdf", "svg", "png"):
        # opt-in: the model-level IFC of a per-storey sheet beats an svg/pdf sibling of the same sheet
        for f in sorted(d.iterdir()):
            if f.suffix.lower() == ".ifc" and p.stem.startswith(f.stem + "_"):
                return Resolved(path=str(p.parent / f.name), fmt="ifc",
                                note=f"RELATED (not a same-stem sibling): model-level IFC '{f.name}' for per-storey sheet")
    best: Optional[tuple[int, str]] = None
    for f in d.iterdir():
        if f.stem != p.stem or f.suffix == "" or not f.is_file():
            continue
        e = f.suffix.lower().lstrip(".")
        if e not in PRIORITY or e == ext:
            continue
        if _rank(e) >= _rank(ext):
            continue
        if e == "pdf" and not pdf_is_vector(f):
            continue
        if best is None or _rank(e) < best[0]:
            best = (_rank(e), f.name)
    if best is not None:
        e = best[1].rsplit(".", 1)[-1].lower()
        return Resolved(path=str(p.parent / best[1]), fmt=_FMT[e],
                        note=f"same-stem sibling .{e} of .{ext or '?'} (README: same drawing in another format)")
    return None
