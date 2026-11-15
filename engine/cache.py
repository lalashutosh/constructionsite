"""SheetFacts cache keyed by (sha256, allow_siblings): JSON on disk under cache/pipeline/, atomic writes,
plus a small in-process dict. Analysis happens once per drawing; questions are lookups."""
from __future__ import annotations

import hashlib
import os
import pathlib
import tempfile
from typing import Optional

from contracts.proof import SheetFacts

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE_DIR = pathlib.Path(os.environ.get("PLUMB_CACHE_DIR", str(ROOT / "cache"))) / "pipeline"
_MEM: dict = {}
# Bump when a reader or the routing changes what a drawing's facts are (e.g. construction sheets stopped going through
# the residential CNN). Facts / 3D built by an older reader are re-read instead of being served forever.
READER_VERSION = "2026-11-15.no-tile-stairs"
MEM_MAX = 256


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _file(sha: str, allow: bool) -> pathlib.Path:
    return CACHE_DIR / f"{sha}.{'sib' if allow else 'nosib'}.json"


def get(sha: str, allow: bool) -> Optional[SheetFacts]:
    key = (sha, allow)
    if key in _MEM:
        return _MEM[key].model_copy(deep=True)
    f = _file(sha, allow)
    if f.exists():
        try:
            facts = SheetFacts.model_validate_json(f.read_text())
        except Exception:  # corrupt entry: recompute
            return None
        if facts.extras.get("reader_version") != READER_VERSION:
            return None                  # read by an older reader: read again
        _remember(key, facts)
        return facts.model_copy(deep=True)
    return None


def put(sha: str, allow: bool, facts: SheetFacts) -> None:
    facts.extras["reader_version"] = READER_VERSION
    _remember((sha, allow), facts)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(CACHE_DIR), suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        fh.write(facts.model_dump_json())
    os.replace(tmp, _file(sha, allow))


def _remember(key, facts: SheetFacts) -> None:
    if len(_MEM) >= MEM_MAX:
        _MEM.pop(next(iter(_MEM)))
    _MEM[key] = facts.model_copy(deep=True)


def clear_memory() -> None:
    _MEM.clear()
