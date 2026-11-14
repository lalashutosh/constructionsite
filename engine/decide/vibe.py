"""Load a vibe preset YAML (`engine/decide/vibes/<name>.yaml`) into plain values
and into `Assumption` objects tagged `defaulted` (the vibe picked them; the
user is free to override any one of them -> becomes `chosen`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from contracts.proof import Assumption, Tag

VIBES_DIR = Path(__file__).parent / "vibes"
VIBE_NAMES = ("budget", "standard", "premium", "nordic")


def load_vibe(name: str) -> dict[str, Any]:
    """Return {key: {"value":..., "unit":..., "source":...}} for the named vibe."""
    path = VIBES_DIR / f"{name}.yaml"
    if not path.exists():
        raise ValueError(f"unknown vibe {name!r}, choose one of {VIBE_NAMES}")
    with open(path) as f:
        return yaml.safe_load(f) or {}


def vibe_value(vibe: dict[str, Any], key: str) -> Any:
    return vibe[key]["value"]


def vibe_assumptions(vibe: dict[str, Any], vibe_name: str, keys: list[str] | None = None) -> list[Assumption]:
    """Turn the chosen keys (default: all) of a loaded vibe into Assumptions tagged `defaulted`."""
    keys = keys if keys is not None else list(vibe.keys())
    out = []
    for k in keys:
        entry = vibe[k]
        value = entry["value"]
        if isinstance(value, list):
            value = str(value)
        out.append(
            Assumption(
                key=k,
                value=value,
                unit=entry.get("unit"),
                tag=Tag.defaulted,
                source=f"vibe:{vibe_name}",
            )
        )
    return out
