"""Skeptic plugin: registers triage, voters, finalizer and calibrator with engine.registry.

A voter is registered for an intent only when it beat the DEV per-intent prior in engine.skeptic.devcheck
(see docs/handoff/skeptic.md). The table below is the single place that decision lives.
"""
from __future__ import annotations

import pathlib

RASTER_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")

# voter module -> intents it may answer. Everything else abstains (returns None).
ENABLED: dict[str, set[str]] = {
    "doors_arc": {"doors"},
    "windows_lines": {"windows"},
    "fixtures_template": set(),            # toilets 25% / sinks 2% on DEV: below prior, so not registered
    "rooms_ocr": set(),                    # filled from devcheck results, see handoff
}


def _wrap(mod_name: str):
    import importlib

    def fn(ctx):
        if ctx.intent not in ENABLED.get(mod_name, ()):
            return None
        if not ctx.abs_path.lower().endswith(RASTER_EXT):
            return None                    # pdf/dxf/ifc go to the vector route, not to pixel voters
        mod = importlib.import_module(f"engine.skeptic.voters.{mod_name}")
        r = mod.run(ctx)
        if r is not None:
            r.second_opinion = True        # independent cross-check of the raster detector, not a replacement
        return r

    fn.__name__ = mod_name
    return fn


def register() -> None:
    from engine import registry

    for name in ENABLED:
        registry.register_voter(name, _wrap(name), kinds=("count",))
    from engine.triage import plugin as tplugin
    tplugin.register()
    try:
        from engine.skeptic import calibrate
        calibrate.register()
    except Exception:  # noqa: BLE001  (no trained model yet: calibrator simply absent)
        pass
