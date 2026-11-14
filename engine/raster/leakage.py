"""Leakage check (prompts/11_w1_raster.md Step 0.3).

CubiCasa5k ships train/val/test splits keyed by folder id, e.g. a line
`/high_quality_architectural/6044/` in weights/_splits/train.txt. The dataset image filenames in
this preview are `<category>-<id>.png` with category in {colorful, high_quality,
high_quality_architectural} -- the same categories as the split folders. This module maps a
dataset path to the model's own split so raster accuracy can be reported twice: all DEV images,
and only those NOT in the model's TRAIN list (the honest number -- AGENTS.md "Dataset facts" +
this file's Step 0.3).
"""
from __future__ import annotations

import pathlib
import re
from functools import lru_cache

_HERE = pathlib.Path(__file__).resolve().parents[2]
_SPLIT_DIR = _HERE / "weights" / "_splits"
_NAME_RE = re.compile(r"([a-zA-Z_]+)-(\d+)\.png$")


def _load(fn: str) -> set[tuple[str, str]]:
    path = _SPLIT_DIR / fn
    out: set[tuple[str, str]] = set()
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip().strip("/")
        if not line:
            continue
        parts = line.split("/")
        if len(parts) >= 2:
            out.add((parts[0], parts[1]))
    return out


@lru_cache(maxsize=1)
def _splits() -> tuple[set, set, set]:
    return _load("train.txt"), _load("val.txt"), _load("test.txt")


def splits_available() -> bool:
    train, val, test = _splits()
    return bool(train or val or test)


def model_split(dataset_path: str) -> str | None:
    """'train' | 'val' | 'test' per the CubiCasa5k authors' own splits, or None if this filename
    could not be mapped (unknown pattern, or split files missing -- callers must treat None as
    "cannot establish", never as "clean")."""
    name = pathlib.Path(dataset_path).name
    m = _NAME_RE.search(name)
    if not m:
        return None
    key = (m.group(1), m.group(2))
    train, val, test = _splits()
    if key in train:
        return "train"
    if key in val:
        return "val"
    if key in test:
        return "test"
    return None


def is_clean(dataset_path: str) -> bool | None:
    """True if NOT in the pretrained model's TRAIN split (honest-accuracy subset), False if it IS
    in TRAIN, None if the mapping could not be established for this path at all."""
    s = model_split(dataset_path)
    if s is None:
        return None
    return s != "train"
