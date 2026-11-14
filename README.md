# Plumb — blueprints that show their work

Junction 2026 · Stoa challenge "Make Blueprints Talk".

Give Plumb a drawing (scan, PDF, DXF, IFC, or a whole project folder) and a question. It answers in one sentence and shows
**exactly which elements on the drawing produced the number**, what it measured, what it assumed, and where its scale came
from. It also builds the plan as a 3D model and turns it into a materials checklist and a build order.

The AI never produces a number. Readers and code do; language models only route questions, write queries for new
questions, and review the readers' work.

## How it works

1. **Read.** Exact files (DXF, IFC, vector PDF) are parsed directly. Scans go through a CubiCasa5k neural net plus OCR.
   The scale comes from measurements printed on the drawing when they exist (two printed values must agree), otherwise
   from a typical door width, or from one measurement you enter.
2. **Check.** Two independent wall readers and two vision LLM reviewers must agree before anything is built in 3D.
   Sections, site plans and title blocks are recognised and get no walls; disagreements are shown, not hidden.
3. **Answer.** Common questions use fixed readers with two independent checks ("Verified" when they agree) and a
   calibrated reliability otherwise. New questions: an LLM drafts a query, code runs it on the drawing's elements.
4. **Plan.** Building type, then a materials checklist (every line with its formula and source), then a build order.

## Measured accuracy (DEV split, 6,192 questions; the holdout split is never used for tuning)

| | with sibling files | without |
|---|---|---|
| all sources | **75.0%** | 70.4% |
| Swiss plans: counts / areas | 100% / 97.7% | |
| IFC models: areas | 99.8% | |
| CubiCasa scans: counts | ~64% | |

Source: `evalkit/out/*w2-dev*/report.md`, exported to `web/public/claims.json` by `scripts/make_claims.py`.

## CI/CD on CRACI — how we used it

Every push runs `.github/workflows/ci.yml` on **CRACI runners**, and every job is configured to use what CRACI does
that a hosted runner can't:

- **Native amd64 and arm64.** The Python suite runs twice in a matrix: `image: ubuntu-24.04` (amd64) and
  `image: craci-slim-arm` (native arm64, no QEMU). Plumb ships to laptops on both architectures (most judges' Macs are
  arm64), so both run the full suite on real hardware.
- **Locked egress on every job → complete SBOMs.** Each job starts with `cracicorp/setup@v1` and `network: {}`: all
  built-in package sources (PyPI, npm, GitHub) are allowed and recorded, everything else is blocked. CRACI generates the
  SBOM from the packages it sees each job download, and with unmatched traffic blocked the SBOM is complete: we know
  every dependency that went into each build.
- **We prove the lock instead of trusting it.** The `egress-proof` job reaches PyPI (must work) and then tries
  `example.com` from inside the locked runner. If that request succeeds, the build fails. A compromised dependency can't
  quietly send our source or keys anywhere.
- **The real API boots on CRACI and replays our security bugs.** `api-smoke` starts the FastAPI server on a runner and
  replays the attacks our stress test found: `/etc/passwd`, `../../etc/passwd` and `/proc/self/environ` must all come
  back as 400 (one of them used to be read). A security fix we found once stays fixed.
- **Right-sized machines.** `size` per job: 4 vCPU for tests and the web build, 2 for the API smoke, 1 for the probes
  and the summary.
- **Tests that never need secrets or the 1.2 GB dataset.** Everything that needs the dataset, the CNN weights,
  tesseract or LLM keys skips cleanly, so CI runs with no secrets at all (nothing to leak through a dependency).
- **Artifacts.** The production web build (`web/dist`) is uploaded from every green run.

A job summary on each run records: tests on amd64 and arm64, egress locked to package presets (complete SBOM), the
lock verified from inside the runner, and the API refusing path-traversal reads.

## Run it

```bash
make setup                                   # .venv + requirements (+ requirements-optional.txt for IFC, torch)
cp .env.example .env                         # DATASET_ROOT, optional LLM endpoint keys (never commit .env)
LLM_PROVIDER=verda .venv/bin/python -m uvicorn api.main:app --port 8000
cd web && VITE_API=live npm run dev          # http://localhost:5173
.venv/bin/python -m pytest -q
```

Not in git: the CubiCasa5k weights (`weights/`, see `docs/HANDOFF.md`) and the dataset (`DATASET_ROOT`).

## Project log

Progress and decisions: [issue #1](https://github.com/lalashutosh/constructionsite/issues/1) · `docs/HANDOFF.md` ·
`docs/PROGRESS.md` · QA and stress reports in `docs/qa/`.

## Credits and licences

CubiCasa5K (Kalervo, Ylioinas, Haikiö, Karhu, Kannala, 2019), CC BY-NC-SA 4.0, non-commercial use only. Swiss Dwellings
v3.0.0 (Archilyse AG), CC BY 4.0. IFC sample models and Opening Design drawings under the licences listed in each
`data/<source>/LICENSE.md`. The credit for a drawing is shown whenever that drawing is shown.
