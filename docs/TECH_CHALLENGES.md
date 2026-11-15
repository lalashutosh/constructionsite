# Plumb in the Junction 2026 tech challenges

Main challenge: **Stoa, "Make Blueprints Talk"**. Plumb also enters four tech challenges. Each section below is
written against that challenge's judging criteria and points to the file in this repository that backs every claim.
Planned work is marked **Next** and kept separate from what is built.

| Tech challenge | What Plumb uses | Evidence |
|---|---|---|
| Verda Compute Track | Open-weight models through an inference API, budget-capped; drawings stay on infrastructure we choose | `scripts/verda.py`, `engine/query/llm.py`, `logs/verda_cost.jsonl` |
| Best use of Modal | The same client serves Modal endpoints (one URL per model, Modal-Key auth, cold starts handled) | `scripts/verda.py`, `docs/HANDOFF.md` §5 |
| Best Use of Gemini API | Gemini 2.5 Flash / Pro as a drop-in provider via Google's OpenAI-compatible endpoint | `engine/query/llm.py` |
| Best use of CRACI | All CI on CRACI: native amd64 + arm64, security replay, egress-lock proof | `.github/workflows/ci.yml` |

---

## Verda Compute Track

**The idea, and why compute makes it possible.** A 10,200 × 6,600 px construction sheet holds hundreds of
symbols. Plumb's computer vision finds and counts them on a laptop, but deciding what each symbol *is*, and whether a
scan is a floor plan at all, needs vision-language models that a laptop can't run. Plumb sends those two narrow
judgements to open-weight models on an inference API, and keeps every number in code.

**The right product, and why.** The **Inference API** for serving open-weight models within the application:

- **Open-weight models** (DeepSeek V4.1 Flash for fast calls, Kimi K3.1 Pro for strong ones) behind one
  OpenAI-compatible client (`scripts/verda.py`), so the model can be swapped without touching the engine.
- **European infrastructure.** Construction drawings are client data: floor plans of homes, dormitories and plants.
  Running open-weight models on infrastructure we choose means they don't have to go to a third-party model API.
- **Cost control built in.** Prices per model tier, every call appended to `logs/verda_cost.jsonl`, and a hard cap
  (`BUDGET_VERDA_USD`) that refuses a call before it can overspend.

**What it does in the product (never a number):**

1. **Two-reviewer scan check** (`engine/scancheck.py`): a fast and a strong vision model each review the sheet in a
   fixed JSON form; their consensus labels views and raises flags before anything is built in 3D. About $0.0045 per
   sheet, cached by file hash ([decision](decisions/scan-check-reviewers.md)).
2. **Symbol naming on the deep read** (`engine/symbols.py`): vision finds and counts; the models name each symbol
   type, in parallel, with a focused second pass for anything left unnamed.
3. **Query planner** (`engine/query/`): a question no template matches becomes a validated query that code runs.

**Path from first idea to prototype** (from the call log and the repo history):

| When (Helsinki) | Step |
|---|---|
| Nov 14, 12:57 | First ping to the fast model (`logs/verda_cost.jsonl`) |
| Nov 14 | Query planner for new questions; LLM kept out of every number by contract (`contracts/proof.py`) |
| Nov 14 | Two-reviewer scan check added after a mirrored model and invented walls got through ([decision](decisions/scan-check-reviewers.md)) |
| Nov 14–15 | Deep read of huge sheets: symbol naming by vision models, counts by code |
| Nov 14, 22:22 | Cheap model used as a code-writing worker with test checks (`scripts/verda_task.py`, `logs/verda_tasks.jsonl`) |
| Nov 15, 07:47 | Last logged call: **1,219 calls, 2.2 M tokens, $9.35 in total** |

**From hackathon demo to real users (Next):**

- **Batch jobs** for whole project folders: read every sheet of a building overnight and have the build plan ready
  in the morning.
- **Auto-scaling containers** for the floor-plan CNN, so scans are read on GPU at peak load and scale to zero.
- **GPU instances** to fine-tune the symbol namer on users' one-click renames, so it learns each firm's drawing style.

## Best use of Modal

**How Modal fits.** The model client (`scripts/verda.py`) was built for Modal endpoints from the start: one base URL
per model (`VERDA_BASE_URL_FAST` / `_STRONG`), `Modal-Key` / `Modal-Secret` authentication, and retries that ride out
Modal cold starts after idle (`docs/HANDOFF.md` §5). The engine just sees one OpenAI-compatible client.

**Against the criteria:**

- **Effective use:** open-weight vision-language models served behind a URL, called from the app for the scan check,
  symbol naming and query planning, all metered and budget-capped.
- **Technical ambition:** the models review a 67-megapixel sheet's contact sheets and agree or disagree in a fixed
  JSON form; disagreement is shown to the user instead of hidden.
- **Impact:** it is what lets Plumb refuse a photo or an elevation, and name 139 doors, 84 chairs and 46 beds on the
  Stoa dormitory sheet without an LLM ever producing a count.
- **Next:** `modal deploy` the FastAPI engine itself so the hosted UI (plumb-blueprints.vercel.app) gets a public
  engine URL; run `make eval` as a parallel Modal batch over all 6,192 DEV questions; move the CubiCasa CNN to a
  GPU function.

## Best Use of Gemini API

**How Gemini fits.** Gemini is a first-class provider (`engine/query/llm.py`): `LLM_PROVIDER=gemini` with
`GEMINI_API_KEY`, through Google's OpenAI-compatible endpoint. The fast tier defaults to **gemini-2.5-flash**, the
strong tier to **gemini-2.5-pro**, and both can be overridden (`GEMINI_MODEL_FAST` / `_STRONG`). It uses the same
system prompts, the same vision inputs (the sheet's contact sheet as an image), the same cost ledger and the same
budget cap as the open-weight path.

**Why this design matters.** Models in Plumb only name things and plan queries; code measures. So Gemini can take any
of the three model jobs (scan review, symbol naming, query planning) without changing how a single number is
produced, and a stronger Gemini model makes Plumb better instead of replacing it.

**Next:** a provider bake-off: run the same deep reads through Gemini and the open-weight models and publish naming
agreement and cost per sheet side by side; use Gemini 2.5 Pro as the tie-breaking third reviewer when the two scan
reviewers disagree.

## Best use of CRACI

Every push and pull request runs [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) on CRACI runners: six
jobs, each started with `cracicorp/setup@v1`, a right-sized machine and its own network policy.

| Job | Runner | What it proves |
|---|---|---|
| `python (amd64)` | `ubuntu-24.04`, 4 vCPU | the full test suite and the ProofObject contract check |
| `python (arm64)` | `craci-slim-arm`, 4 vCPU, **native arm64, no QEMU** | the same suite on the architecture most judges' laptops run |
| `web` | 4 vCPU | TypeScript typecheck and production build; `web/dist` uploaded as an artifact |
| `api smoke + security` | 2 vCPU | boots the real FastAPI server and **replays the attacks our own stress test found**: `/etc/passwd`, `../../etc/passwd`, `/proc/self/environ` must all return 400 |
| `egress lock proof` | 1 vCPU, `default: deny` + PyPI / GitHub presets | **tests the supply-chain lock instead of trusting it**: PyPI must be reachable, `example.com` must not |
| `summary` | 1 vCPU | writes the results to the job summary |

**Against the criteria:**

- **Technical depth:** the CI is a security control, not just a build. A vulnerability found once becomes a probe
  that runs on every push; the network policy is verified by a job that fails if an arbitrary host is reachable;
  no job needs secrets (dataset, weights, OCR and LLM tests skip cleanly), so there is nothing to leak through a
  compromised dependency.
- **Creative use of CRACI's features:** per-job network policies with package presets, so the build-time CycloneDX
  SBOM CRACI records for each job covers exactly what the lock allows; native arm64 next to amd64; right-sized
  machines (4 / 2 / 1 vCPU).
- **Honest status:** on 2026-11-14 the egress job showed the lock was not yet in force on our project, so it is red
  and we report it rather than claim a lock we could not verify.
- **Next:** pull each build's SBOM and network trace from the CRACI API and fail the build when a dependency appears
  that was not in the previous SBOM; feed CRACI AI fixes for flagged packages into a pull request that the same CI
  must pass before merge.
