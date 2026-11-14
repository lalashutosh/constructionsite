"""Licence + credit per file, read from the dataset's own `data/<source>/LICENSE.md`.

Two layouts exist in the preview set:
  * a markdown table `| file | title | licence | credit | source |` (ifc_models, opening_design)
  * one line `All files: <LICENCE>. Credit: <credit>` (swiss_dwellings)
The credit string MUST be shown whenever the drawing is shown (AGENTS.md, licences).
"""
from __future__ import annotations

import pathlib
import re
from functools import lru_cache
from typing import Optional

_ALL = re.compile(r"^All files:\s*(.+?)\.\s+Credit:\s*(.+)$", re.M)   # licence ids contain dots (CC-BY-4.0)


@lru_cache(maxsize=32)
def _table(lic_path: str) -> tuple[dict, Optional[tuple[str, str]]]:
    p = pathlib.Path(lic_path)
    if not p.exists():
        return {}, None
    text = p.read_text(encoding="utf-8", errors="replace")
    rows: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.lower().startswith("| file"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4:
            rows[cells[0]] = (cells[2], cells[3])
    m = _ALL.search(text)
    return rows, ((m.group(1).strip(), m.group(2).strip()) if m else None)


def lookup(root: pathlib.Path, rel_path: str) -> tuple[Optional[str], Optional[str]]:
    """(licence, credit) for a dataset-relative path like `data/ifc_models/x.ifc`, or (None, None)."""
    parts = pathlib.PurePosixPath(rel_path.replace("\\", "/")).parts
    if len(parts) < 3 or parts[0] != "data":
        return None, None
    source = parts[1]
    inner = "/".join(parts[2:])
    rows, default = _table(str(root / "data" / source / "LICENSE.md"))
    if inner in rows:
        return rows[inner]
    if default is not None:
        return default
    return None, None
