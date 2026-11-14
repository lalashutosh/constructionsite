# Handoff — where the build stands and how to continue

## UPDATE 2026-11-14 ~21:00 (Abhinav's session, after pulling c73cd72) — START HERE

Live log: https://github.com/lalashutosh/constructionsite/issues/1 (read the latest comments first; post after each step).

**Done + committed (`3a8ebdd`), on top of Ashutosh's 20:30 work below:**
- Bug #2 below (folder upload "goes out of context") **fixed**. Two causes: (a) `/api/building` built 3D geometry + 2 AI
  reviews for EVERY file before classifying -> minutes -> timeout; now classification uses only cheap signals and the
  3D is built when a floor is opened; (b) PyMuPDF / IfcOpenShell are native and not thread-safe and crashed the API
  process; per-file readers now run in worker processes with a 60 s timeout, a bad file is listed with a reason.
  Full `Sports_Complex` (27 files, `find -L`): HTTP 200 in 29 s, 27/27 classified ($0.14), server stays up.
  `tests/test_building_folder.py` added.
- Bug #3 below (label overlapping the scan-check warning) **fixed**: header band in `web/src/index.css`
  (`.viewer::before`) so canvas labels pass behind the title/status/warning; the progress block covers the drawing toggle.
- Test suite fully green: 172 passed, 3 skipped. The 2 failures listed below were stale gitignored `cache/raster` facts;
  clear `cache/raster` + `cache/pipeline` after any raster change.

**Also fixed (later commit):** bathrooms found by their fixtures (a room with a toilet is a bathroom even if the
reader tagged it 'S'); Swiss PDFs/PNGs with a same-stem .dxf are built in 3D from the DXF entities (0.8 s, exact);
CAD/BIM answers no longer get the door-guess scale note. UI tweak left: hide/relabel "Set real size" for exact CAD
files ("Sizes from the CAD file") — `web/src/panels.tsx` scalecta.

**Still open:**
1. Bug #1 below (archival walls): the fix is on branch `wip/archival-walls`, which was NOT pushed (not on GitHub);
   push it from Ashutosh's machine (`git push origin wip/archival-walls`) before anyone can verify/merge it.
2. One sheet with two floor plans (e.g. "Faint two-floor scan"): engine returns `check.floors` (82a1abe) but the UI tabs
   "All · Floor 1 · Floor 2" + stacked view are NOT built (the UI agent hit the usage limit). Next UI task.
3. Raster finetune agent stopped at the usage limit; its uncommitted changes are gone from this checkout.
   Restart from `docs/handoff/raster-finetune.md` if present, else from the brief in issue #1 / the 19:15 section.
4. UI check of DXF/IFC uploads (coords `dxf-render`/`ifc-render`, `check: null`) — not verified in the browser yet.

## UPDATE 2026-11-14 ~20:30 (Ashutosh's session)

**Done + committed on `p2-finish`:**
- `1faa0e4` **Fix-first #1 solved**: `.dxf` / `.ifc` uploaded WITHOUT a sibling image now render and build 3D.
  `engine/vector/dxf_render.py` (DXF drawn with cv2; walls = closed WALL polylines merged, rooms/doors/windows/fixtures
  from entities; counts equal the DXF reader, 0.4 s) and `engine/vector/ifc_render.py` (storey with most walls;
  footprints = model meshes projected to XY, ~4 s, cached; plumbing-only models drawn as part outlines capped at 600;
  empty model -> 422 with reason). API: `_render_cad()` in `api/main.py`; coords `dxf-render` / `ifc-render`
  (proof evidence is NOT pinned on these). Tests: `tests/test_cad_render.py` (3 pass).
  Not yet checked in the browser: does the UI handle coords `dxf-render`/`ifc-render` and `check: null`?
- Test suite: 172 passed, 2 failed — both pre-existing, both from the raster-finetune WIP that was never committed
  (`test_count_rules_finetune::colorful_2002`, `test_query::fixed_specs` saunas). They pass or skip once that WIP lands
  or the test is aligned.

**Open bugs reported by the user (screenshot of a finna scan, hka.139878174949000_146761804461500.jpg):**
1. **Archival / hand-drawn scans: 3D walls are wrong.** Hand lettering, the title-block table (bottom right), street
   name text, dimension ticks and the sheet border frame get extruded as walls; real thin double-line walls are missing.
   WIP on branch **`wip/archival-walls`** (`7f3ee15`, +146 lines in `engine/geometry3d.py` + `scripts/_qa_*.py`):
   an agent's text/frame filter, stopped mid-measurement, UNVERIFIED. To finish: regression set is listed in
   `cache/qa/archival_set.txt` (local only; 12 archival scans + 4 clean cubicasa controls — rebuild if missing).
   Accept only if overlays show no walls on text/title block and cubicasa controls keep >= 0.95 of their wall IoU.
   Clear `cache/geometry` after engine edits.
2. **Folder upload of a multi-floor building fails** ("goes out of context"). Reproduce with
   `$DATASET_ROOT/data/opening_design/Sports_Complex` (subfolders `IFC Roundtrip`, `Models`, `Sheets - Current Set`,
   `Transfer`; note some files may be symlinks — use `find -L`). Not reproduced yet. Suspects: one huge LLM classifier
   prompt (classify in batches with compact per-file summaries, no-think, max_tokens), request timeout while every
   file's geometry is built serially, big IFC uploads, one bad/unsupported file failing the whole folder. Goal: a folder
   never fails as a whole; floors stacked, other files listed with a reason. Add `tests/test_building_folder.py`
   (LLM off). `1faa0e4` means IFC/DXF files in the folder can now be shown instead of dropped.
3. **UI: the boxed "Floor plan" label overlaps the scan-check warning line** ("Needs a look · View 1 (floor plan): some
   walls missing") in the drawing header. Find the component that renders scan-check view types (grep web/src for
   'Needs a look', `check.views`). "Before" screenshots: `docs/shots/ui-fix/` (1440 px and 400 px, light and dark).

**How we worked this session (repeat it):** lead session + parallel subagents on disjoint files (sonnet builders,
haiku scout for mechanical work), each told to draft tests with Verda Flash and get a Kimi review of its diff
(`scripts/verda.py`); subagents never commit, the lead verifies and commits. Agents cannot `git push`
(`.claude/settings.json` deny rule): the human pushes.

**Push (human):** `git push origin p2-finish wip/archival-walls`

## UPDATE 2026-11-14 19:15 — START HERE (supersedes the 18:20 section below where they differ)

**Live log: https://github.com/lalashutosh/constructionsite/issues/1** — read the latest comments, post after each step
(`gh issue comment 1 -R lalashutosh/constructionsite -b "..."`; only the main session can post, subagents report to it).
Branch `p2-finish`; push is blocked for agents by `.claude/settings.json`, the human pushes.

### Fix first (known bugs, in priority order)
1. **Uploaded `.dxf` / `.ifc` without a sibling image -> 3D view "geometry 404"** (answers still work: e.g. 29 doors,
   21 windows verified). `api/main.py::_drawing_png` only renders dxf/ifc through a same-stem png/pdf/svg. Fix: render
   the DXF itself (ezdxf drawing addon -> matplotlib PNG, cache by sha) and for `/api/geometry` build walls straight
   from DXF entities (layer WALL / ROOM_OUTLINE polygons, `engine/vector/dxf.py` has the parser) in that PNG's pixel space.
   IFC: render a plan cut per storey (ifcopenshell geom) or show "BIM model: open per storey" in the UI.
2. **Project view (folder upload)**: engine fixed in 52b842c (only distinct storeys stack, alternatives, display_label);
   the UI agent was asked to use it (no "Floor ?", one-line message instead of six identical refusals, non-plan files
   open flat). Verify in the browser with the Sports_Complex folder.
3. **1 failing test** at pause: most likely `tests/test_query.py::test_fixed_specs_equal_intent_path_on_cached_facts`
   (saunas 1 vs 2 on gitignored `cache/raster` facts) caused by the UNCOMMITTED raster WIP; it skips on a clean
   checkout. Re-check after the raster work is verified or reverted.
4. Large commercial PDF sheets give almost no walls (line-pair reader tuned for scans); DWG unsupported (no reader).

### 19:40 additions (committed 82a1abe, e991a6e)
- Scale from PLAIN printed dimensions too (mm values matched to plan lengths, >= 2 must agree within 3%):
  1967 -> 67.95 px/m, walls 7.70 m vs 7.79 m printed. First OCR of a sheet ~70 s, cached in `cache/scale_dims`.
- One sheet with several floor plans: `check.floors` in /api/geometry (level read by the AI reviewers). UI agent asked
  to add "All · Floor 1 · Floor 2" tabs + a stacked view (uncommitted while running).
- UI round committed: project explorer, real-looking fixtures, progress bar, hover length x breadth.

### In flight / uncommitted at pause
- `engine/raster/extract.py`, `engine/raster/ocr.py`: raster finetune agent (bedrooms via MH labels, saunas, door
  overcount, windows). NOT verified. Verify: delete `cache/raster` + `cache/pipeline`, run
  `.venv/bin/python -m evalkit.run --engine pipeline --split dev --sources cubicasa5k --no-siblings` (baseline 63.8%;
  colorful-2002 must give 2 bedrooms, key 7 windows). Commit only if it beats 63.8% with no intent below its prior;
  else `git checkout -- engine/raster/`.
- UI agent round (web/, uncommitted while running): project explorer polish, realistic low-poly fixtures,
  upload progress bar, hover-to-see length x breadth, the project-view fixes above. Commit after
  `cd web && npm run typecheck && npm run build`.

### Done since 18:20 (all pushed up to 1029b94; later commits local until the human pushes)
- 2923ed3 CNN wall reader crashed silently since 20293de -> fixed + regression test (walls back on all scans)
- 1029b94 QA sweep (docs/qa/hard-questions-sweep.md: 27/30 OK) fixes: comparisons reuse the Findings readers,
  'which room' names room + size, IFC count sentences
- 9d83c26 CI on CRACI (`.github/workflows/ci.yml`): amd64 + arm64 python, web build, egress locked (complete SBOM).
  Needs the CRACI GitHub App installed on the repo before jobs start.
- 52b842c folder -> building: only distinct storeys stack; revisions/phases are alternatives; foundation/enlarged typed
- issue #1 created as the live log; CLAUDE.md + this file point to it

### Remember
- Restart the API after engine edits (it does not hot-reload) and clear `cache/geometry` + `cache/pipeline`;
  a stale server hid the wall fix once. Start with LLM on: `LLM_PROVIDER=verda .venv/bin/python -m uvicorn api.main:app --port 8000`.
- Measured DEV: 75.0% with siblings / 70.4% without (n=6,192). Never run the holdout split.

## UPDATE 2026-11-14 18:20 (interactive lead session, branch `p2-finish`)

> **Live progress log: GitHub issue https://github.com/lalashutosh/constructionsite/issues/1 ("Build log").**
> Every agent / Claude Code session: read the latest comments there before starting, and post a short comment
> (what changed, numbers, commit hash, what is left) after each finished step: `gh issue comment 1 -R lalashutosh/constructionsite -b "..."`.

**Plain-language status:** `docs/PROGRESS.md` (newest on top). Branch `p2-finish` on GitHub; `main` untouched.

### Run it (Mac)
```
.venv/bin/python -m uvicorn api.main:app --port 8000                      # LLM off
LLM_PROVIDER=verda .venv/bin/python -m uvicorn api.main:app --port 8000   # planner + AI reviewers on
cd web && VITE_API=live npm run dev                                       # http://localhost:5173
.venv/bin/python -m pytest -q                                             # 164 passed
```
Machine setup that is NOT in git (redo on a new machine):
- `weights/` (CubiCasa5k CNN, 209 MB): `weights/model_best_val_loss_var.pkl` from the authors' README link
  (Google Drive id 1gRB7ez1e4H7a9Y09lLqRuna0luZO5VRK, via `gdown`), plus the source zip of github.com/CubiCasa/CubiCasa5k
  unpacked to `weights/_src/CubiCasa5k-master`. Without it scans fall back to route B (0 doors/windows).
- tesseract: a system one, or the micromamba conda-forge env at `cache/tools/tess-env` (engine/__init__.py finds it).
- `.env`: `DATASET_ROOT` must point at the local `junction-dataset-preview`; Verda keys from the team.
- Stale caches bite: delete `cache/raster`, `cache/pipeline`, `cache/geometry` after extractor changes.

### Measured (DEV, holdout untouched)
75.0% with siblings / 70.4% without (n=6,192; prior 37.3%). Swiss count 100% / area 97.7%, IFC area 99.8%,
CubiCasa count ~64% (weakest: windows 27%, saunas below prior, doors/bedrooms overcount). Reports:
`evalkit/out/*w2-dev*/report.md`; UI numbers via `scripts/make_claims.py` -> `web/public/claims.json`.

### What exists now (committed)
- Engine: vector `extract()` + credits; router (regex -> lexicon `engine/router_lexicon.yaml` -> n-gram -> LLM
  classifier restricted per source -> planner); complex / kind-clash questions go to the planner; planner (thinking
  off, 1 retry) with argmax/avg/ratio/difference/greater, wall elements for wall questions, 'unsupported' replies;
  answers as sentences (`answer_text`) + calibrated `reliability` (additive contract fields); printed-dimension scale
  (`engine/scale/printed_dims.py`: WxH opening labels, >= 2 must agree, tag specified); implausible user scale refused
  (HTTP 422 + unit suggestion); scan check (`engine/scancheck.py`: 2 wall readers + 2 vision reviewers, consensus) ->
  non-plan sheets refuse floor-plan questions; `engine/geometry3d.py` (CNN walls <= 1600 px, line-pair reader for
  archival scans, furniture blobs dropped); build plan (`engine/plan/`, GET /api/plan); folder -> one building
  (`engine/building.py`, POST /api/building: a reasoning model classifies every file; Sports Complex 27/27 in 24 s, $0.10).
- Web: one-story UI (3D hero, sentence answers, Why? sheet, Set real size with payoff + unit picker, How it works
  page, dark/light palettes, de-slop rules). See `docs/handoff/ui-redesign.md`.

### In flight when paused (NOT committed / NOT finished)
- Raster finetune agent: `engine/raster/extract.py`, `engine/raster/ocr.py` modified (bedrooms via MH labels, saunas,
  door overcount, windows). Unverified: run the CubiCasa DEV eval before committing
  (`.venv/bin/python -m evalkit.run --engine pipeline --split dev --sources cubicasa5k --no-siblings`; baseline 63.8%;
  regression case colorful-2002 must give 2 bedrooms). See `docs/handoff/raster-finetune.md` if it was written.
- UI agent: project file explorer for folder uploads (POST /api/building), only floor plans stacked, realistic
  low-poly fixtures (toilet / sink / bath / door leaf + swing arc / window glass / stairs).
- QA sweep (haiku) writing `docs/qa/hard-questions-sweep.md`.
- CRACI CI: not written yet. Plan: `.github/workflows/ci.yml`, `runs-on: craci`, `cracicorp/setup@v1` with
  `network: {}` (all presets, other egress denied -> complete SBOM), matrix amd64 (`image: ubuntu-24.04`) + arm64
  (`image: craci-slim-arm`), size "4"; jobs: python tests (pip install -r requirements.txt; pytest; dataset tests skip
  without the dataset), contract check, web typecheck + build. Needs the CRACI GitHub App installed on the repo.

### Next (suggested order)
1. Verify + commit the raster finetune (eval numbers), rerun full DEV and `scripts/make_claims.py`.
2. Commit the UI explorer/fixtures round after typecheck + build.
3. CRACI CI workflow. 4. G2 gate write-up in docs/STATUS.md. 5. P4 pre-ship (prompts/90, 40 step 4, MORNING.md).
Human TODOs unchanged: verify `evalkit/hard_questions.jsonl` (0/10), holdout run, ship.

---

## Original handoff (13:30)

Written 2026-11-14 13:30 when the build was paused (Claude usage limit). Everything below is committed.
Read this file first, then `docs/STATE.md` (the live checklist) and `AGENTS.md` (project rules).

## 1. What Plumb is (30 seconds)
Junction 2026, Stoa challenge "Make Blueprints Talk". Plumb turns a drawing (PNG/PDF/DXF/IFC) into numbers
with a receipt: every count/area points at the drawing elements that produced it, and lists what was
measured, assumed and chosen. Scoring on the preview dataset: counts exact, area/length/volume within 2%.
The LLM never produces numbers; it only classifies question templates and plans queries for unseen questions.

## 2. Where we are
Progress: 12 of 25 checklist items in `docs/STATE.md`.

| Phase | State | Key numbers (from committed reports/handoffs) |
|---|---|---|
| P0 bootstrap | done | `make check` OK (7,990 questions, tesseract eng+fin) |
| P1 evaluator | done | stub 6.9%, prior-only floor **37.3% DEV** [36.1, 38.5], n=6,192 |
| P1 takeoff | done | scale + area + door schedule, 44 tests |
| P1 raster-extractor | done (GO, conditional) | DEV150 **61.3%** vs prior 47.3%; beats prior on 8/12 intents; cold 2.21 s/image |
| P1 ui-builder | done | web build clean, 19 screenshots in `docs/shots/` |
| G1 gate | **GO** all 4 | see `docs/STATUS.md` |
| **P2 vector / skeptic / integrator** | **IN PROGRESS, interrupted** | code committed as WIP (`68ee2c1`); not yet verified by the lead |
| G2, P3 demo, P4 pre-ship | not started | |

Test suite at pause: **140 passed** (`.venv/bin/python -m pytest -q`, ~7 s).

What exists from P2 (WIP, unverified):
- `engine/vector/`: dxf, ifc, pdfvec, svgvec, swisspdf, schedule, sibling resolver `engine/siblings.py`
- `engine/skeptic/`: second voter(s), calibration, lexicon; `engine/triage/`: features + rules
- integrator: `engine/pipeline.py`, `router.py`, `query/` (planner, rules, schema), `cache.py`, `cost.py`, `api/main.py`,
  tests for router/query/pipeline/api, `scripts/pipeline_smoke.py`, `scripts/api_probe.py`
- handoffs written so far: `docs/handoff/integrator.md` (vector and skeptic handoffs NOT yet written)

## 3. Next steps, in order
1. **Finish P2.** For each of vector, skeptic, integrator: read its handoff if present, run its smoke/devcheck,
   finish missing pieces, write `docs/handoff/<agent>.md`. Check `git show 68ee2c1 --stat` for what changed;
   note that `engine/raster/` and `engine/takeoff/` were also touched during P2 (likely integrator wiring hooks):
   confirm these are small and don't break `raster`/`takeoff` tests.
2. **Integration pass** (`prompts/25`): DEV runs with and without siblings; hard set with LLM off vs planner on.
3. **G2 gate** (`prompts/05_gate.md`, WAVE=w2) → GO/NO-GO in `docs/STATUS.md`; up to 2 fix rounds.
4. **P3 demo** (`prompts/30`), then extras (`31`, `32`) if G2 is GO.
5. **P4 pre-ship** (`prompts/90`, `41`, `40` step 4) and `docs/MORNING.md`. Never run the HOLDOUT split until ship.

## 4. Human TODOs (agents must not do these)
- **Verify `evalkit/hard_questions.jsonl`**: 10 hand-written hard questions, 0/10 verified. It is the TEST set:
  check each expected answer by hand against the drawing; never tune on it.
- Push target: this repo had no remote at pause. Add one (`git remote add origin <url>`); never push to the
  parent `~/Downloads` repo (that is an unrelated course repo; see below).

## 5. Setup on a new machine
```
git clone <repo> plumb && cd plumb
make setup                      # creates .venv, installs requirements.txt (+ requirements-optional.txt for ifcopenshell, torch)
cp .env.example .env            # fill in values; never commit .env
make check                      # dataset + tesseract (eng+fin) + contract
.venv/bin/python -m pytest -q   # expect 140 passed
```
Dataset: download the Junction preview, set `DATASET_ROOT` to the folder containing `questions.jsonl` and `data/`
(it is NOT in git; 1.2 GB; CubiCasa is CC BY-NC-SA 4.0).

`.env` key names (values come from the team, never paste them in chat/commits):
`DATASET_ROOT`, `LLM_PROVIDER` (default `none`), `VERDA_BASE_URL_FAST`, `VERDA_BASE_URL_STRONG`, `VERDA_MODEL_FAST`,
`VERDA_MODEL_STRONG`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` (or `VERDA_API_KEY`), `BUDGET_VERDA_USD`, `HF_TOKEN`,
`FEATHERLESS_*`, `BUDGET_ANTHROPIC_USD=0`.

Verda = our Modal endpoints (OpenAI-compatible): fast = DeepSeek 4.1 Flash, strong = Kimi K3.1 Pro.
Base URLs **must end in `/v1`** (without it you get HTTP 404). Check with:
```
.venv/bin/python scripts/verda.py --ping --model fast
.venv/bin/python scripts/verda.py --ping --model strong
.venv/bin/python scripts/verda.py --spent        # running cost (was $0.0065 at pause)
```
First call after idle can take minutes (Modal cold start); the script prints each attempt.

## 6. Running the autonomous build
```
cd plumb && claude              # FIRST TIME ONLY: accept the "trust this folder" prompt, then /exit
STOP_AT=never setsid nohup bash scripts/overnight.sh > logs/overnight/supervisor.out 2>&1 < /dev/null &
```
- One lead session (Opus) follows `ORCHESTRATOR.md`, spawns builder subagents (`.claude/agents/`), commits, and
  updates `docs/STATE.md`. The supervisor restarts it after each cycle and sleeps through usage limits
  ("session limit · resets HH:MM").
- Watch: `docs/STATE.md`, `tail -f logs/overnight/SUPERVISOR.md`, `git log --oneline | head`.
- Stop: `kill $(pgrep -f 'bash scripts/[o]vernight.sh'); kill $(pgrep -f '^claude -p')`.
- Cheaper: `ORCH_MODEL=sonnet` gives more cycles per usage window.
- Before restarting after a manual pause, make sure line 1 of STATE is `STATUS: IN_PROGRESS` (BLOCKED/DONE stop it).
- Or work interactively: open `claude` in the folder and say "follow ORCHESTRATOR.md from docs/STATE.md".

## 7. Gotchas we already hit (don't repeat)
- **Nested git repo:** plumb used to live inside a `~/Downloads` git repo (a course project). The supervisor's
  `git add -A` swept 5,900 unrelated files into it (never pushed). Plumb is now its own repo; `overnight.sh`
  refuses to run unless plumb is the repo root and stages only `.`.
- **Folder trust:** a new repo root is an untrusted Claude Code project; headless runs then get every command
  denied and the lead marks STATE BLOCKED. Fix: run `claude` once in the folder, accept. `overnight.sh` now checks.
- **Session-limit message** wasn't recognised before and killed the run; fixed (sleeps until reset).
- **Background subagents lack Bash**: the lead spawns builders in the foreground.
- **Verda underused**: builders preferred writing code themselves ($0 spent on Verda during P1–P2). ORCHESTRATOR
  says "Verda-first"; if you want the Claude quota to last, make it a hard rule in briefs (e.g. tests/fixtures
  and lexicons must be drafted by Verda first, then checked by the builder).
- Some cycle-log timestamps in STATE are estimates by the lead (e.g. "~13:15"); trust git commit times instead.

## 8. Map of the important files
| file | what |
|---|---|
| `docs/STATE.md` | live checklist + cycle log (source of truth for progress) |
| `docs/STATUS.md` | gate tables with measured numbers, GO/NO-GO |
| `docs/handoff/*.md` | per-agent: what works, numbers, failures, how to run |
| `docs/decisions/*.md` | 3-line decision records |
| `ORCHESTRATOR.md`, `RUNBOOK.md` | how the lead works; phase order and gates |
| `prompts/` | the spec for each phase/agent |
| `contracts/proof.py` | the only interface between modules (frozen) |
| `evalkit/` | scoring harness; `evalkit/out/latest/report.md` is the only source for claimed numbers |
| `scripts/overnight.sh`, `scripts/verda.py` | supervisor; Verda client with budget + cost ledger |
