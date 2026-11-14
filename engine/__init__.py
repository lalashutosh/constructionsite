"""Plumb engine package.

Tesseract lookup: pytesseract calls `tesseract` through PATH. When it is not on PATH, a repo-local install at
cache/tools/tess-env/bin (micromamba + conda-forge, see docs/decisions/tesseract-local.md) is put on PATH for this
process. Override with PLUMB_TESSERACT_BIN=<dir>."""
import os as _os
import pathlib as _pathlib
import shutil as _shutil

if _shutil.which("tesseract") is None:
    _bin = _os.environ.get("PLUMB_TESSERACT_BIN") or str(
        _pathlib.Path(__file__).resolve().parents[1] / "cache" / "tools" / "tess-env" / "bin")
    if (_pathlib.Path(_bin) / "tesseract").exists():
        _os.environ["PATH"] = _bin + _os.pathsep + _os.environ.get("PATH", "")
