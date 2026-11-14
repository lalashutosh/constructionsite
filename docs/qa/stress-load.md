# Plumb API load and robustness stress test

Target: http://localhost:8000 (engine: pipeline). Dataset root: ~/Downloads/junction-dataset-preview.
Raw results: /tmp/claude-501/stress-c/results.json. Driver: /tmp/claude-501/stress-c/run.py.
Latencies are wall-clock seconds measured client-side. GET /health was 200 before the run and after every block.

## Test 1: concurrency and determinism

Drawings (random.Random(42), cubicasa + swiss):

| # | Drawing |
|---|---|
| 1 | data/cubicasa5k/high_quality_architectural-381.png |
| 2 | data/cubicasa5k/high_quality-1391.png |
| 3 | data/cubicasa5k/colorful-2194.png |
| 4 | data/swiss_dwellings/site3238_bldg4922_floor22515.png |
| 5 | data/swiss_dwellings/site285_bldg527_floor51568.png |

Simple question, 20 parallel calls (4 per drawing), "How many doors are shown on this floor plan?":

| Batch | n | p50 (s) | p95 (s) | max (s) | failures |
|---|---|---|---|---|---|
| simple | 20 | 74.442 | 78.75 | 78.75 | 0 |
| hard (10 parallel, 2 questions per drawing) | 10 | 1.947 | 6.798 | 6.798 | 0 |
| all | 30 | 68.694 | 78.294 | 78.75 | 0 |

Determinism (answer JSON compared with timing and id-like fields removed):

| Drawing | Question | Parallel OK calls | Identical | Distinct answers |
|---|---|---|---|---|
| all 5 drawings | doors (simple) | 4 each | yes | 1 each |
| all 5 drawings | largest room / bathroom share (hard) | 1 each | not testable | n/a |

Each hard (drawing, question) pair ran only once, so determinism for the hard questions was not measured.

Observation: the simple-question latencies are dominated by first-time analysis of each drawing. All 20 calls ran cold, concurrently. Serial latency was not measured.

## Test 2: parallel geometry on unseen drawings

Six random cubicasa drawings not used in Test 1 and not colorful-2002.png:

| Drawing | Status | Latency (s) |
|---|---|---|
| data/cubicasa5k/high_quality_architectural-10196.png | 200 | 44.969 |
| data/cubicasa5k/high_quality-5682.png | 200 | 45.301 |
| data/cubicasa5k/high_quality_architectural-6051.png | 200 | 47.558 |
| data/cubicasa5k/high_quality-13137.png | 200 | 41.354 |
| data/cubicasa5k/high_quality_architectural-4845.png | 200 | 41.354 |
| data/cubicasa5k/high_quality_architectural-6081.png | 200 | 46.175 |

Summary: p50 45.301 s, p95 47.558 s, max 47.558 s, failures 0.

## Test 3: bad uploads (POST /api/upload, then /api/geometry and /api/ask on the returned path)

| Case | Upload | Geometry | Ask |
|---|---|---|---|
| empty x.png (0 bytes) | 200 | 415 "image could not be read" | 200, value null |
| text renamed plan.png | 200 | 415 "image could not be read" | 200, value null |
| 1x1 px png | 200 | 200 (10.336 s) | 200, value null |
| truncated PDF ("%PDF-1.4" only) | 200 | **500 "Internal Server Error"** | 200, value null |
| garbage x.dxf | 200 | 422 "could not draw this DXF file: OSError ..." | 200 (1.165 s), value null |
| garbage x.ifc | 200 | 422 "could not draw this IFC file: Error: Unable to parse IFC SPF header" | 200, value null |
| evil.exe | 415 "unsupported file type '.exe'" | skipped | skipped |

5xx found: GET /api/geometry on the truncated PDF upload. Reproduced twice with the same status:

    GET /api/geometry?path=/Users/abhinavchutani/Documents/GitHub/constructionsite/cache/uploads/e16fa5d9b51928755db85b917f0297babaf22c7a47e97d9212adab56e61ba04e.pdf

Upload was POST /api/upload, multipart field "file", filename plan.pdf, bytes "%PDF-1.4".

Observation: asks on the unreadable files (empty, text, garbage DXF/IFC, truncated PDF) return 200 with value null rather than an error. This is not a 5xx but may mislead callers.

## Test 4: path abuse and question edge cases (POST /api/ask)

| Case | Path | Status | Latency (s) | Body (first 200 chars) |
|---|---|---|---|---|
| traversal | ../../etc/passwd | 400 | 0.014 | {"detail":"bad path"} |
| absolute path | /etc/passwd | **200** | 0.017 | ProofObject, value null, provenance.file "/etc/passwd" with a sha256 |
| embedded traversal | data/../../../etc/hosts | 400 | 0.015 | {"detail":"bad path"} |
| empty question | colorful-11397.png | 200 | 1.937 | ProofObject, question "" |
| 5,000-char question | colorful-11397.png | 200 | 2.169 | ProofObject, echoed |
| Finnish question | colorful-11397.png | 200 | 0.184 | ProofObject, intent doors, value 12 |
| emoji-only question | colorful-11397.png | 200 | 2.132 | ProofObject, intent unknown, value 12 |

Security observation: absolute paths bypass the ".." check in `_resolve`. /api/ask on /etc/passwd computed and returned that file's sha256 in provenance. The file was read outside the dataset root. /api/geometry on /etc/passwd returned 415 "cannot render", and /api/geometry on ../../etc/passwd returned 400.

## Test 5: absurd scale anchors (POST /api/scale on data/cubicasa5k/colorful-2002.png)

Run last, because accepted anchors are stored in memory per drawing.

| Anchor | Status | Latency (s) | Body (first 200 chars) |
|---|---|---|---|
| px_length 0, length_m 1 | 200 | 0.216 | ProofObject list, accepted |
| length_m 0, px_length 100 | 422 | 0.037 | {"detail":{"message":"the measurement needs a pixel length and a length in metres"}} |
| px_length -100, length_m 1 | 200 | 0.194 | ProofObject list, accepted |
| px_length 100, length_m -1 | 200 | 0.221 | ProofObject list, accepted |
| px_length 1e9, length_m 1 | 422 | 0.030 | {"detail":{"message":"this measurement would make the typical room 0 m², which is not plausible; check the length and its unit",...}} |

Observation: the plausibility check in `_implausible_scale` returns early when the scale is <= 0, so zero and negative pixel-per-metre anchors pass and are stored in `eng.user_anchors` for colorful-2002.png. The last stored anchor was px_length 100, length_m -1. A follow-up area ask on that drawing returned scale null, so the effect on answers was not visible in this run. The server was not restarted, so the stored anchors remain until restart.

## Server stability

- GET /health returned 200 before the run and after each of Tests 1 to 5.
- The server did not crash or hang. Every request returned a response within the 240 s client timeout.
- One 5xx (truncated PDF geometry), described above.
