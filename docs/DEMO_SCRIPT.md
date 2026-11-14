# Plumb — demo script, video storyboard, Q&A

**One line:** Plumb turns a drawing into numbers with a receipt: what was measured, what was assumed, what was chosen, and the few decisions to make before ordering.
**Positioning:** every number points at the pixels that produced it.

## The judge map (four equal quarters, every beat proves one)
| Quarter | What the judge must see | Beats |
|---|---|---|
| Accuracy | held-out numbers with confidence intervals; "green" really means right; honest refusal | Duel, Cost+Honesty |
| Verifiable reasoning | every number one click from its pixels; two independent readers; receipt | Hook, Duel, Receipt |
| Creativity | decision ledger ranked by impact, lazy scale-ask, draft door schedule, reconcile, tamper test, agent-to-agent | Scale, Decisions, Reconcile, Tamper, A2A |
| Low cost | live meter, LLM calls = 0 by default, CPU-seconds per drawing, extract once / lookups | Hook, Cost+Honesty |

**Rule:** any number on screen or in a caption is read from `claims.json` or the live API. Written here as ⟨claim:key⟩. Anything synthetic or demo wears a ribbon. Every drawing shows its credit string.

---

## First 10 seconds (the part that decides everything)
| t | On screen | Caption | Sound |
|---|---|---|---|
| 0.0–1.0 | Black. A tiny, grainy Finnish scan appears centre at its TRUE pixel size (dim) | `A ⟨w⟩ px scan. Finnish labels. No scale.` | soft click |
| 1.0–2.5 | Scan-line sweeps down; wall strokes trace in as the line passes (stroke-dashoffset) | — | rising tone |
| 2.5–4.5 | The plan lifts and EXPLODES into the evidence stack: scan, walls, rooms, doors, windows | `Every number gets a receipt.` | whoosh |
| 4.5–6.5 | Numbered chips pop on each door 1…7; tally bar fills; footer meter runs `0 tokens · $0.00 · 412 ms` | — | tick per chip |
| 6.5–8.0 | Stack folds back flat. Huge **7**, green chip: `2 independent readers agree` | — | soft chord |
| 8.0–10.0 | Title: **Plumb** — `Blueprints that show their work.` | (same) | silence |

The recipe: a real, ugly input (credible, not a staged hero image) + a transformation nobody has seen + immediate proof of cost and verification. No logo splash, no talking head, no "hi we are team".

---

## Full storyboard (≈100 s). Cut to the 60-second version by keeping the bold beats.
| # | Time | Beat | What happens (exact click path) | Caption | Proves |
|---|---|---|---|---|---|
| 0 | 0:00–0:10 | **HOOK** | see above | see above | verifiable, cost |
| 1 | 0:10–0:24 | **Skeptic Duel** (bold) | Open an amber plan. Two overlays (two colours, two shapes). Banner `7 vs 6`. One door pulses amber. Click it → `Is this a door? Yes`. Count settles at 7, chip turns green, the door-schedule row appears | `Two readers that never see each other. Disagreement = look here first.` | accuracy, verifiable |
| 1b | 0:24–0:38 | **Harder question** (bold) | Ask "total area of bedrooms that have a window" (or a Finnish multi-part question). The answer card shows the readable query line with the badge `planned by LLM, computed by code`; the rooms and windows used light up | `Questions become queries. The model never invents the number.` | accuracy, verifiable |
| 2 | 0:24–0:38 | **Scale band collapse** (bold) | Ask "area of the living room". Band `⟨lo⟩–⟨hi⟩ m²` plus the cheapest question `Tap a door: is this 0.9 m?`. Tap. The band springs down to `±⟨p⟩%` | `We ask the cheapest question — only when the number needs it.` | creativity |
| 3 | 0:38–0:52 | **Decisions + receipt** (only if W2 gate GO) | Switch to Decide. Vibe row: Budget / Standard / Premium / Nordic; the receipt prints line by line (Drawn / Specified / Chosen / Defaulted / Open). Top card: `Door width moves the order by ⟨n⟩ leaves — decide this first.` Pick 0.9 m; one line flips from Defaulted to Chosen | `Or choose the vibe. Every assumption is on the receipt.` | creativity, verifiable |
| 4 | 0:52–1:06 | **Draft door schedule + reconcile** (only if W2 gate GO) | `Generate door schedule` → table slides in. `Reconcile with order` (ribbon `DEMO DATA`) → cards: `⟨a⟩ ordered · ⟨b⟩ drawn · ⟨c⟩ ordered, drawn nowhere`. Click a card → pins light up | `The drawn side of every order check — with proof.` | creativity |
| 5 | 1:06–1:16 | **Tamper test** (only if W2 gate GO) | Select a door → `Simulate revision: remove` (ribbon `SYNTHETIC REVISION`). Delta card: `−1 door · −1 leaf · −1 frame · −3 hinges`. Revision scrubber wipes between the two stops | `A changed drawing, priced in order lines.` | creativity |
| 6 | 1:16–1:26 | **Honest refusal + cost** (bold) | Drop an elevation / tiny thumbnail: grey state, no number, reason `This is an elevation; floor-plan questions do not apply`. Footer: `LLM calls ⟨claim:llm_calls⟩ · ⟨claim:mean_ms⟩ ms · ⟨claim:usd_total⟩ USD`. A small card: `held-out accuracy ⟨claim:headline_acc_holdout⟩ (CI ⟨claim:headline_ci⟩) · green right ⟨claim:green_acc⟩ of the time` | `It would rather say "I can't" than guess.` | accuracy, cost |
| 7 | 1:26–1:34 | **Agent asks our agent** (only if W2 gate GO) | Side panel: another agent (A2A) asks `how many doors?`; task `working` → `input-required: door width?` → answered `0.9` → `completed` with the receipt | `Any agent can hire Plumb.` | creativity |
| 8 | 1:34–1:40 | **Close** | Receipt line `Drawn · Specified · Chosen · Defaulted · Open`, then the title card with credit line: `Drawings: CubiCasa5k (CC BY-NC-SA 4.0), Swiss Dwellings, ...` | `Plumb. Blueprints that show their work.` | — |

### 60-second cut (for `docs/video/plumb-60s.mp4`)
Hook 0:00–0:10 · Duel 0:10–0:24 · Harder question (trim to 10 s) · Scale (trim to 10 s) · Honest refusal + cost 1:16–1:26 · Close 1:34–1:40.

## Voiceover (optional, one calm voice, ≤ 15 words per beat)
1. "A tiny scan, no scale. Watch what it becomes." 2. "Two independent readers. Where they disagree, you look — one click." 3. "No scale on the drawing? We ask the cheapest question, once." 4. "Pick a vibe, or decide. Every assumption is on the receipt." 5. "Doors drawn, doors ordered — the gaps, with proof." 6. "Change the drawing, see the order change." 7. "When it can't know, it says so. Zero model calls by default." 8. "Plumb. We cite to the pixel."

## Recording rules
- 1920×1080, screen scaling 100%, hide dock/bookmarks, dark mode, notifications off.
- Automatic take: `cd web && node scripts/record_demo.mjs && bash scripts/make_video.sh` (fake cursor, captions burned in). Manual take: follow the click paths above; record at 60 fps; cut on the beat.
- Captions always on (autoplay is muted). Max two lines. No music with unclear rights; silence or a royalty-free track credited in the description.
- Show the live cost meter in at least three beats. Show at least one drawing at its true tiny size.
- Honest labelling in frame: `SYNTHETIC DEMO`, `DEMO DATA`, `SYNTHETIC REVISION`, credit strings. Do not blur or crop them out.

## Dry run (the gate for the ship step; do it on a clean cache)
```
rm -rf cache/ && make api &  make web &
open http://localhost:5173
```
Walk beats 0–8 from the table without touching the keyboard except the clicks listed. Every beat must complete in under the time given. Anything that does not is cut from the video, not patched on the day.

## Live pitch variant (3 minutes)
0:00 hook (10 s, skippable only by you) · 0:10 duel with a plan the judges pick from the sample strip · 0:50 scale collapse · 1:20 reconcile + tamper · 2:00 refusal + the claims card · 2:30 one sentence on scaling: "extract once per file hash, every question is a lookup, routing uses the title block only, the model-free path costs ⟨claim:cpu_per_drawing_s⟩ s of CPU per drawing (estimate)". Leave 30 s for questions.

## Q&A cheat sheet (answers use repo evidence only)
- **What does this add to a document-level citation?** We prove the number from the pixels, with two independent readers, the assumptions listed, and the decisions ranked. We produce the "drawn" side that order checks need.
- **Why would a stronger model not make this obsolete?** A better model gives a better guess; it still cannot show which pixels it used, which assumption it made, or whether it agrees with an independent reader. Our layer gets more valuable as models improve: they become the optional third voter we already log.
- **What does green mean?** Two independent readers agree. On held-out drawings green was right ⟨claim:green_acc⟩ of the time on ⟨claim:green_coverage⟩ of the questions; amber ⟨claim:amber_acc⟩.
- **What if it is wrong?** The proof names the disputed element; one click fixes it and everything downstream recomputes. Wrong-and-green cases are listed in the report.
- **Cost?** ⟨claim:llm_calls⟩ model calls by default, ⟨claim:mean_ms⟩ ms per question, ⟨claim:usd_total⟩ USD for the whole held-out run. Optional model use is limited to one call per distinct question template and one planner call per question no template matches (counted separately: ⟨claim:planner_calls⟩). The model never produces the number.
- **Unknown languages / 30 languages?** Routing is by template, language-agnostic fallback measured leave-one-language-out: ⟨claim:router_lolo⟩. New language costs at most one call per distinct template, cached.
- **No scale on the drawing?** Counts never need scale. For areas we use the best anchor available, show the interval, and ask the cheapest question only if it matters.
- **Is the benchmark leaked to the pretrained weights?** Possibly for CubiCasa5k train images. We report the clean subset (images not in the weights' train list) separately: ⟨claim:clean_acc⟩.
- **Does it scale to 14,000 drawings?** Extract once per file hash (cached), questions are lookups, ⟨claim:cpu_per_drawing_s⟩ s CPU per drawing (estimate), in-network, no per-question model call.

- **Harder questions than the dataset?** The planner turns them into checked queries over the extracted facts. Hard set, held out: ⟨claim:hard_acc_holdout⟩ with the planner, reported next to the LLM-off number.

## Submission checklist
- [ ] `make test` green on a fresh clone · [ ] holdout run done once, `claims.json` committed · [ ] README generated, no hand-typed numbers
- [ ] video 85–110 s, captions, credit line, ribbons visible · [ ] repo public or shared as required · [ ] `.env`, weights, caches not committed
- [ ] `docs/review.md` says GO · [ ] screenshots of beats in `docs/shots/` · [ ] submission text pasted from `docs/SUBMISSION.md`
