Homebrew on this M1 is the Intel build under Rosetta and compiled tesseract's ~38 dependencies from source (hours).
Decision (user approved the download): native arm64 tesseract 5.5.4 from conda-forge via micromamba into cache/tools/tess-env (gitignored, eng+fin+125 langs); engine/__init__.py puts it on PATH only when no system tesseract exists.
A system tesseract (brew, apt) still wins when present; set PLUMB_TESSERACT_BIN to force another one.
