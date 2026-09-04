# TypeScript backend migration — stack decision and plan

Scope: replace **all** Python in this repo with TypeScript, leaving no Python in the
running process. Covers `apps/visualizer/backend/` (Flask API + job queue) and the
`lightroom_tagger/` library (vision, scoring, identity, catalog, CLI).

## What we are migrating

| Area | LOC | Notes |
|---|---|---|
| `apps/visualizer/backend` non-test | 10,146 | 63 routes, spectree/pydantic, SocketIO, threaded job queue |
| `apps/visualizer/backend/tests` | 12,455 | contract tests gate CI |
| `lightroom_tagger/` | 22,892 | includes its own colocated tests |
| **Total Python** | **46,815** | 257 files |

Background ecosystem research, with 84 cited primary sources, is in
[`docs/research/nodejs-raw-clip-whash-feasibility.md`](../research/nodejs-raw-clip-whash-feasibility.md).
This document records the decisions; that one records the evidence for the library
choices.

## Feasibility: measured, not assumed

Every claim below was verified by running code against the live `library.db`
(638 MB, 43,451 embedded images) and real files on the mounted NAS. Scripts live in
the session scratchpad; results reproduced here.

### SQLite, sqlite-vec and FTS5 — no problem

`better-sqlite3` + the `sqlite-vec` npm package opened the production database
read-only and loaded extension version **v0.1.9 — the exact version Python pins**.
Cosine KNN over the `image_clip_embeddings` vec0 table returned correct neighbours
from Node, and stored blobs are 2048 bytes = 512 float32 with L2 norm 1.000000.
`image_descriptions_fts` (FTS5) is readable.

**No data migration is required.** The database is the stable interface.

### RAW decoding — viable via `libraw-wasm`

`rawpy.imread(p).postprocess(use_camera_wb=True, half_size=True)` maps onto
`libraw-wasm`'s `{ useCameraWb: true, halfSize: true }`. Verified decode of one
real file per format present in the catalog:

| Format | In catalog | Decode | Time |
|---|---|---|---|
| `.dng` | 17,590 | 6209×4299 | 1350 ms |
| `.arw` | 12,259 | 2012×3012 (half) | 244 ms |
| `.raf` | 11,252 | 2014×3016 (half) | 980 ms |
| `.sr2` | 272 | 2748×1836 (half) | 221 ms |
| `.cr2` | 239 | 1732×2601 (half) | 399 ms |

Output was JPEG-encoded through `sharp` and visually confirmed correct (colour and
orientation) on the Fuji RAF sample. Notably, `sharp`/libvips **cannot** open ARW,
RAF or SR2 at all — `sharp-libvips` is built `-Draw=disabled` — and `exifr` only
yields 160×120 thumbnails. So `libraw-wasm` is the only viable path, not one option
among many.

A soak test of 60 sequential decodes: **60/60 succeeded, 872 ms/image** average
(the mix includes full-size DNGs), RSS oscillating 405–716 MB with no unbounded
growth. Extrapolated, a **full** vision-cache rebuild of ~41,000 RAW files is
**~10 hours single-threaded**, ~2.5 hours over 4 workers.

Three caveats:

1. `libraw-wasm` ships a **browser** build. It calls `new Worker(url, {type:'module'})`
   and its Emscripten runtime fetches `libraw.wasm` over `file://`. Running it in Node
   needs a ~25-line adapter: a `globalThis.Worker` shim over `node:worker_threads`, a
   worker-side `self` shim (it assigns `self.onmessage` / calls `self.postMessage`),
   and a `fetch` polyfill for `file://` URLs. Proven working, but it is our code to
   own and re-verify on every `libraw-wasm` upgrade.
2. **Construct a fresh instance per image and dispose it.** Reusing one instance
   across 25 decodes grew RSS 405 → 699 MB; fresh-per-image stays flat. Driving the
   Emscripten factory in-process instead (the alternative integration) reportedly
   fails outright after ~14 images without an explicit `delete()`. The Worker-based
   adapter above did not reproduce that failure — another reason to prefer it.
3. `halfSize` is **ignored for DNG** — the DNG sample decoded at full 6209×4299.
   With 17,590 DNGs that is the dominant cost. Downscale explicitly after decode.

Format coverage is not a concern for *this* catalog. Full inventory:

| `.dng` | `.arw` | `.raf` | `.tif` | `.jpg` | `.sr2` | `.cr2` | `.mp4` | `.mov` | `.heic` | `.psd` |
|---|---|---|---|---|---|---|---|---|---|---|
| 17,590 | 12,259 | 11,252 | 1,270 | 853 | 272 | 239 | 32 | 23 | 2 | 2 |

The formats with known WASM problems — `.x3f` (does not decode in Node at all),
`.orf` and `.srw` (numeric divergence in the WASM build), plus `.nef`, `.cr3`,
`.rw2` — have **zero** files in the catalog, even though `RAW_EXTENSIONS` lists them.
Keep them listed and let them fail loudly rather than pretending they are supported.

### CLIP embeddings — viable and drop-in compatible, via a resampler port

`@huggingface/transformers` (transformers.js v3) with `Xenova/clip-vit-base-patch32`
at `dtype: 'fp32'` produces 512-d embeddings at **19.5 ms/image**. `q8` is not faster
(20.3 ms), so use fp32.

Used naively, JS vectors are **not** interchangeable with the stored Python ones.
Feeding the same cache JPEG to both:

- same-image cosine, JS vs Python: **mean 0.931** over 8 images spread across the
  library (range 0.907–0.953), and 0.947 over 8 frames from a single burst
- baseline cosine between unrelated photos (Python vs Python, 780 pairs): mean 0.557, p95 0.717, max 0.848
- **top-10 neighbour overlap: only 5.3/10**
- self-retrieval: 8/8 at rank 0

A JS vector reliably identifies *its own* image, but the near-duplicate *ranking*
disagrees about half the time — and that ranking is exactly what stack detection and
catalog similarity do.

**The cause is preprocessing alone, and it is fixable.** Dumping Python's own
`pixel_values` tensor and feeding it through the Node graph unchanged gives:

```
key                    python-tensor->node   sharp-preproc->node
2020-03-08__CC14833        1.000000              0.942312
2020-03-08__CC14832        1.000000              0.960001
...
mean                       1.000000              0.947187
1 - cos (python tensor path): 2.575e-12
```

The ONNX weights are numerically exact to 2.6e-12. Every bit of the drift comes from
`transformers.js`'s `RawImage.resize`, which resizes via sharp/libvips bicubic — not
PIL bicubic. (Its source comment claims PIL parity; that claim is wrong, and upstream
issues #482/#595/#816 have tracked it unfixed since 2023.)

**This is now done and the reindex is eliminated.** `src/imaging/pil-resample.ts`
ports Pillow's resampler and `src/imaging/clip-preprocess.ts` builds the tensor,
bypassing `RawImage.resize`. Measured against the stored corpus over 8 images spread
across the catalog (`tests/clip-parity.test.ts`):

- **worst cosine 1.000000000**, worst `1 - cos` = **3.52e-12**
- **top-10 neighbour lists identical** to the stored query vectors, up from 5.3/10

Node now writes vectors that are drop-in compatible with the 43,451 already stored.
Re-embedding remains available as a fallback (~14 min single-threaded) but is no
longer part of the plan.

### Perceptual hashing — viable, reimplement directly

`imagehash.phash` is ~15 lines: greyscale → 32×32 LANCZOS → 2D DCT-II → top-left
8×8 → threshold at median. Reimplemented over `sharp` and compared against the
phashes Python stored in `vision_cache`:

With the Pillow-exact resampler it reproduces Python's stored hashes **12/12
exactly, max Hamming distance 0 of 64 bits** (`tests/phash-parity.test.ts`).

One correction to an earlier measurement here. A first pass using `sharp` for the
resize scored 7/12 exact with ~2 bits of drift, and that was attributed purely to
resampling — but it also compared the wrong input. `vision_cache` hashes the
*viewable* image, not the compressed cache file:

```python
viewable_path = get_viewable_path(original_path)
temp_path = compress_image(viewable_path)
phash = compute_phash(viewable_path)   # the viewable, not the cache JPEG
```

So part of that 2-bit drift was comparing a different image at a different
resolution. The parity test therefore restricts itself to originals that are already
JPEG, where `get_viewable_path` returns the path unchanged and the input is
reproducible. For RAW originals the viewable was a temp file that no longer exists,
so those rows cannot be used to verify a hash — worth knowing before anyone tries.

No wavelet library is needed: `imagehash.whash` is reachable only from
`compute_multiple_hashes`, which **nothing in production calls**. It is dead code —
drop it rather than port it. (For the record, had it been live: the 2D Haar DWT is
~12 lines, and `remove_max_haar_ll=True` is arithmetically a no-op.)

### The one cross-cutting risk: Pillow's resampler is load-bearing twice

Both CLIP and phash reach parity only through a PIL-equivalent resize, because every
value already in the database came through Pillow. `sharp` is not a substitute:

| Resize via `sharp` | Measured consequence |
|---|---|
| CLIP embeddings | cosine 0.93–0.97 vs the stored corpus — inside the near-duplicate band |
| phash | 7/12 exact, ~2 bits drift |
| whash (if it were live) | only 33% exact, up to 22/64 bits wrong |

There is a **third** silent divergence beyond the resize, not covered by the research:
`sharp().greyscale()` disagrees with PIL `convert("L")` on **23.7% of pixels** (max 11
levels) on a real cache JPEG. PIL uses ITU-R 601-2 luma in fixed point,
`(R*19595 + G*38470 + B*7471 + 0x8000) >> 16`, which `pilGreyscale` implements. Since
phash greyscales *before* resizing, using sharp here would corrupt every hash.

What is NOT a problem: **JPEG/PNG decoding is byte-identical.** sharp and PIL produced
the same 2,098,176 bytes with zero differences on a real cache JPEG, so decoding can
be delegated to sharp and only the resize and colour conversion need porting.

This is built as **one shared module**, `src/imaging/pil-resample.ts`, pinned by
golden files generated from Pillow itself
(`tests/fixtures/imaging/regenerate-fixtures.py`, 80 bit-exact resize comparisons
across bicubic and lanczos, RGB and single-channel planes). The trap it guards is that
`sharp` runs fine and looks right while being quietly wrong.

One caveat found while wiring it up: `@huggingface/transformers` depends on
`sharp ^0.34.5` and bundles its own libvips. Installing a newer sharp alongside it
loads **two** libvips into the process, which macOS flags as duplicate Objective-C
classes and warns "may cause spurious casting failures and mysterious crashes". An
npm `overrides` entry pins sharp to a single copy; keep it in step with the
transformers dependency.

### Everything else

Complete non-test third-party surface, all with direct equivalents:

| Python | TypeScript | Notes |
|---|---|---|
| `sqlite3` (43) | `better-sqlite3` | synchronous, matches current model |
| `flask` (15) | `hono` | |
| `spectree` (12) | `@hono/zod-openapi` | keeps OpenAPI backend-authoritative |
| `pydantic` (12) | `zod` | |
| `PIL` (9) | `sharp` | |
| `flask_socketio` / `eventlet` | `socket.io` | frontend already uses socket.io-client |
| `threading` (8) | `node:worker_threads` | |
| `openai` (3) | `openai` (official Node SDK) | same API surface |
| `numpy` (3) | typed arrays | only histogram / cumsum / log2 / entropy |
| `sqlite_vec` (2) | `sqlite-vec` | v0.1.9 verified |
| `imagehash` (2) | ~15 lines | verified above |
| `sentence_transformers` (1) | `@huggingface/transformers` | verified above |
| `rawpy` (1) | `libraw-wasm` | verified above |
| `yaml` (5) | `yaml` | |
| `dotenv` (3) | `node --env-file` | |

No unassessed dependency remains.

## Stack decision

**Node 24 · TypeScript 5.9 · ESM · Hono · Zod · better-sqlite3 · socket.io · Vitest**

| Concern | Choice | Why |
|---|---|---|
| HTTP | **Hono** + `@hono/zod-openapi` | ADR-0013 requires backend-authoritative OpenAPI feeding `api.gen.ts` with a CI drift gate. `@hono/zod-openapi` reproduces the pydantic→spectree→OpenAPI chain exactly. |
| Validation | **Zod** | Direct pydantic replacement; also the schema source for OpenAPI. |
| Database | **better-sqlite3** + **sqlite-vec**, raw SQL with hand-written row types | Verified against the live DB. Synchronous, matching today's usage. |
| ORM | **none** | Drizzle cannot model `vec0` or FTS5, and schema ownership stays with the existing migrations. Kysely is optional later for the plain-table subset. |
| Realtime | **socket.io** | Frontend already runs `socket.io-client`; zero frontend change. |
| Jobs | **`node:worker_threads`** pool | `better-sqlite3` is synchronous, so jobs on the main loop would stall every request. Mirrors today's thread-per-job design and `runner.thread_db()`. |
| Images | **sharp** + **libraw-wasm** | |
| CLIP | **@huggingface/transformers**, fp32, **with `RawImage.resize` bypassed** | Weights are exact; its resize is not PIL-equivalent. Feed our own tensor. `onnxruntime-node` + the raw `vision_model.onnx` is the fallback if bypassing proves awkward. |
| Resampling | **vendored PIL-exact resampler** | Required for CLIP and phash parity (see above). No npm equivalent. |
| LLM providers | **openai** npm SDK; `fetch` for Ollama | |
| Tests | **Vitest** | Already used by the frontend. |

Rejected: **tRPC** — deletes the OpenAPI seam ADR-0013 and the CI drift gate depend
on. **NestJS** — DI and decorator overhead unjustified for 63 routes. **Fastify** —
workable, but its OpenAPI story is a looser fit than Hono's.

## Sequencing

Vertical slices, each one shipping a working seam with a real consumer (per the
repo's slicing convention), not build-then-wire.

0. **Foundation** — TS project, config loader, `better-sqlite3` + `sqlite-vec` layer,
   `utils/responses` equivalents, Hono app shell with OpenAPI document. **Done.**
0b. **PIL-exact resampler** — the shared module CLIP and phash both depend on, with a
   fixture test asserting bit-exact agreement with Pillow. **Done.** Includes
   `pilResize` (bicubic/lanczos), `pilGreyscale`, `centerCrop`, the CLIP
   preprocessing chain, the phash port, and the CLIP embedding service.
1. **First vertical slice: `/api/system`** — proves the whole contract chain from a TS
   route through OpenAPI to `api.gen.ts`. **Done** (`/status`, `/stats`,
   `/catalog/status`), with the emitted OpenAPI diffed route-by-route against Flask.
2. **Route groups. Done — 52 of 52 OpenAPI paths.**
   `tests/openapi-contract.test.ts` pins every emitted path and method against a
   captured inventory of the Flask document and ratchets the migrated count, so a
   group cannot silently regress or invent a path. At 52 the ratchet is an
   equality check in practice: every path Flask serves has a TS equivalent.

   | Group | Status |
   |---|---|
   | system | done |
   | scores | done |
   | perspectives | done, including writes |
   | config | done |
   | descriptions | done, including `POST /generate` and the vision pipeline behind it |
   | catalog + stacks | done |
   | identity | done |
   | providers | done |
   | frame substance | done, including the `.lrcat` keyword writer |
   | jobs | routes, runner and processor done; handlers landing one family at a time (step 4) |

   The route surface being complete does not mean the backend is: three of the
   eleven `JOB_TYPES` still carry `handler: null`, so those jobs fail on enqueue.
   That is step 4.
3. **Job engine — done.** worker_threads runner, `JOB_TYPES` registry, transitions
   state machine, checkpoints, socket.io progress, with the ADR-0010 guardrails
   preserved.
4. **Job handlers**, one family per slice — catalog sync, embed, analyze/score,
   describe, stacks, frame substance, path diagnostics. ~3,394 lines of Python.

   **Describe is done** (`single_describe`, `batch_describe`), and it carried the
   three shared pieces every later family needs: `jobs/checkpoint.ts`,
   `jobs/handlers/path-diagnostics.ts` and `jobs/handlers/common.ts` (catalog
   selection, date windows, failure severity, the library-DB lifecycle).
   **Embed is done** too, on top of those plus `db/library/embeddings.ts`, and so
   are the two standalone **stacks** jobs, which needed only the similarity write
   helpers — the CLIP KNN and the representative query were already ported for
   the routes.

   | Family | Types | Status |
   |---|---|---|
   | describe | `single_describe`, `batch_describe` | done |
   | embed | `batch_embed_image` | done |
   | stacks | `batch_stack_detect`, `batch_catalog_similarity` | done |
   | stacks | `catalog_cache_build` | blocked — its first stage is `catalog_sync` |
   | score | `single_score`, `batch_score` | done, with the scoring library core underneath them |
   | analyze | `batch_analyze` | done, minus the frame-substance stage between its two passes |
   | frame substance | `batch_frame_substance` | not started — needs the detector (step 5) |
   | catalog | `catalog_sync` | not started — needs `catalog_sync` (step 5) |

   Two structural departures from the Python, both worth repeating in the
   remaining families. Concurrency is a bounded **async pool over one
   connection**, not a `ThreadPoolExecutor` with a connection per worker: the time
   is spent waiting on the provider's HTTP response, so threads bought nothing,
   and the pool deletes Python's duplicated `max_workers == 1` branch — which had
   already drifted to different log messages than its parallel twin. And
   cancellation is an explicit `cancelCheck` passed down rather than the
   thread-local `cancel_scope`, which the retry backoff already honours.

   Embed added a third departure of the same kind. Python buffered eight paths
   and called `encode_images(paths, batch_size=8)` with a per-image retry loop
   for when the batch threw; here `encodeImages` is a sequential loop over
   `encodePixels`, because the ONNX session is already internally threaded and
   batching bought only peak memory. That makes the buffer an indirection around
   a one-element list and the retry a re-run of work that never shared a fate, so
   both are gone — and with them a double-count in the original, where a file
   that failed the batch *and* the retry was tallied under `encode_failed` twice.

   Stack detection contributed one more, plus a trap. Python selected the work
   list, then re-fetched the same rows in 500-key `IN (...)` chunks and
   substituted a null-dated row for any key the second query failed to return —
   but both queries read `images`, so that fallback covers a case the first query
   cannot produce; here it is one query. The trap is `date_taken` parsing:
   Python's `fromisoformat` yields a naive datetime that the handler then stamps
   as UTC, while `new Date('2024-01-15T10:00:00')` reads the same text as *local*
   time. Left alone that would move where a burst begins by the machine's offset
   from Greenwich, so `parseDateTakenUtc` parses the string by hand — and keeps
   sub-millisecond precision, because the gap is compared against `delta_ms` as a
   float.

   Scoring brought its own library core with it — `structured-output.ts`,
   `analyzer/scoring.ts`, the four `image_scores` write helpers and
   `vision/scoring-service.ts` — because `single_score` is the only thing that
   has ever called it. Two departures. Python's
   `parse_score_response_with_retry` takes *two* repair hooks, a plain `fixer`
   and an `llm_fixer`; nothing has ever passed the first except its own unit
   test, so only the LLM one is ported. And Python's single `ValidationError`
   role is split in two: `ScoreValidationError` means "worth repairing" and
   `StructuredOutputError` means "give up", which pydantic gets for free and
   here has to be explicit. Collapsing them would send half a megabyte of
   garbage to the provider for a repair attempt, since the size gate raises the
   terminal one.

   One thing the port found, worth knowing before writing any more timestamps:
   `image_scores.scored_at` is the **only** column Python writes through
   `.replace(microsecond=0)`. Every other UTC column keeps its fractional part.
   These columns are compared and sorted as text, so a millisecond field on a
   new score would order it against existing rows wrongly —
   `nowIsoUtcSeconds` exists for that one column, and `utils/datetime.ts` said
   the opposite until now.

   `batch_score` then followed the describe pass almost line for line, with one
   real difference in shape: its unit is an image × perspective **triple**, so
   the checkpoint resumes on `key|itype|slug` and activating a rubric mid-run
   changes the fingerprint — correctly, because the stored "done" set says
   nothing about a slug that was not in it. The pre-filter is the same idea as
   describe's and a harder query: "already scored" is per rubric version, so it
   matches on each slug's live `prompt_version`, and an edited perspective falls
   out of it by itself. Python computes that slug → version map twice, once in
   the pre-filter and once in the `redo_unless_model` filter; here it is built
   once. The one new piece of SQL is `excludeVoidSubstance` in
   `selectCatalogKeys` — the scoring selection drops condemned frames in the
   query, so a lens cap is not even counted as a skip. Worth noting for
   `batch_analyze`: `redo_unless_model` implies a per-item `force` and the
   result payload reports that widened flag, not the one the user sent.

   `batch_analyze` then composed those two passes, and the generalization it
   needed came out smaller than Python's. Python gives each pass four independent
   parameters — `progress_range`, `log_prefix`, `finalize`,
   `nested_analyze_checkpoint` — but only two combinations of them are ever
   passed, so here there is one optional `PassStage` argument: absent, the pass
   owns the job; present, it owns a band of the progress bar, prefixes its logs,
   writes into a sub-object of the composite's checkpoint, and returns its summary
   instead of completing the job. Both passes are otherwise unchanged, which is
   the point — the body reads the same because `log` and `progress` are two local
   closures that apply the prefix and the band.

   The composite's own content is the shared selection and the nested checkpoint.
   Selecting once is the reason the job exists: run `batch_describe` and
   `batch_score` back to back and the second selection has moved, because every
   image the first job described is now described and drops out of an
   undescribed-only window. The consequence, worth knowing before reading a
   support ticket about it, is that an already-described image is out of scope for
   *both* stages unless `force_describe` widens the selection — sharing the list
   means sharing its filter. The checkpoint holds two fingerprints and two
   processed sets under one `stage` marker, so a run interrupted while scoring
   resumes into scoring; re-entering a finished describe stage would be nearly
   free, but "nearly" is a preflight and a pre-filter over the whole selection to
   arrive at no work, so the fingerprint match skips it outright.

   One stage is missing. Python runs frame-substance detection between describe
   and score, over the images this run just cached, so that a frame condemned
   during the run is dropped from its own scoring pass. That needs
   `frame_substance_detector` and `frame_substance_batch`, which are step 5, so
   the handler currently runs describe (0–48) and score (52–100) with the 48–52
   band left empty rather than closed — the bands stay where a resumed Flask-era
   job expects them, and wiring the stage in later is one call. Scoring still
   drops condemned frames, on the verdicts that were already in the table:
   `filterVoidSubstanceFromScoringSelection` runs between the passes, where
   standalone `batch_score` does it in the selection SQL. Until the detector
   lands, an analyze run will not *discover* a lens cap, only remember one.

   Two smaller departures. `batch_analyze` was the only caller that counted
   `silent_compression_skips`, for no reason the code gives; here every describe
   pass counts it, which drops a branch and tells a standalone `batch_describe`
   the same useful thing. And the selection block that `handle_batch_describe`
   and `handle_batch_analyze` duplicate in Python is one exported
   `selectDescribeCandidates`, parameterized on the force flag they read from
   different metadata keys.

   Neither `batch_embed_image` nor the two stacks handlers have a
   `_catalog_cache_chain` branch: only `catalog_cache_build` sets that flag, and
   it cannot run until `catalog_sync` is ported, so the suppression of logging
   and checkpointing that flag selects lands with the composite that needs it
   rather than being guessed at three times. Note that most of what
   `_CatalogCacheStageRunner` does — mapping a stage's 5–100% into a quarter of
   the bar, capturing `complete_job`, swallowing checkpoints — is a wrapper
   around the runner and needs nothing from the handlers; only the log
   suppression is a real branch inside them.

   The checkpoint fingerprints hash **bytes identical to
   `json.dumps(sort_keys=True)`**, pinned by golden digests generated from the
   Python function. That is load-bearing for cutover: a `batch_describe`
   checkpointed by Flask has to resume under the TS backend rather than
   re-describing 40,000 images, and `JSON.stringify` differs from Python on both
   key order and non-ASCII escaping.
5. **Library core — partly done.** The `library.db` read/write seam, providers,
   vision op, identity, imaging, the Lightroom writer and the scoring stack
   (`scoring_service`, `score_perspective`, `structured_output`) are ported.
   Still Python only: `catalog_sync`, `frame_substance_detector` and
   `frame_substance_batch`, `lightroom/reader` + `enricher` + `schema`, and the
   small shared utilities (`managed_connections`, `path_utils`, `cancel_scope`,
   `text_constants`). The detector pair now unblocks two things rather than one:
   the `batch_frame_substance` handler and the middle stage of `batch_analyze`.
   It is the least mechanical port left — five statistics over an 8-bit greyscale
   array that numpy does in five lines, plus thresholds that have to reproduce
   Python's verdicts on the same previews, so it wants golden-value parity tests
   the way the resampler did.
6. **CLI** — replaces the `lightroom-tagger` console script. Not started.
7. **Cutover** — back up `library.db`, point the Vite proxy at the TS backend, and
   delete the Flask tree. No CLIP reindex: embeddings are already drop-in compatible.

## Risks

1. ~~**Everything image-derived depends on the resampler port.**~~ **Retired.** The
   port is done and pinned: CLIP reproduces the stored corpus to `1 - cos` = 3.52e-12
   with identical neighbour rankings, and phash matches 12/12 exactly. The residual
   risk is regression, which the golden-file tests and the two gated parity tests now
   cover. Still back up `library.db` before the first write-path run.
2. **RAW decode cost.** Measured 872 ms/image over a 60-image soak, so a full
   vision-cache rebuild of ~41,000 files is ~10 hours single-threaded (~2.5 h over 4
   workers). `halfSize` being ignored for DNG makes 17,590 files the dominant share.
   The existing cache is intact (43,451/43,451 files present on disk), so this only
   bites on new imports or a forced rebuild — but budget for it.
3. **`libraw-wasm` adapter is ours to maintain.** A browser-targeted package driven
   from Node through three shims; pin the version and cover it with a test that
   decodes one fixture per format.
4. **Tests are the bulk of the work.** ~12,455 LOC of backend tests plus the library's
   colocated tests must be re-expressed in Vitest. The contract tests in
   `tests/contract-tests.txt` gate CI and must keep gating it.
5. **CI installs Python today.** `.github/workflows/ci.yml` sets up Python and pip-installs
   the backend. A GitHub App cannot push `.github/workflows/**`, so the updated
   workflow must be handed to a maintainer to install by hand — same constraint that
   produced `.sandcastle/ci-drift-gate.yml`.
6. **Lightroom catalog writes.** `utils/lr_catalog_write.py` and
   `lightroom_tagger/lightroom/writer.py` mutate a live `.lrcat`. Port last, behind the
   existing write-serialization discipline.
7. **A faithful port inherits the original's latent bugs, and the new tests find
   them.** Porting `store_image_description` line by line carried over an FTS5
   defect: on the external-content `image_descriptions_fts` that every real catalog
   has, `DELETE ... WHERE rowid = ?` removes the wrong terms, so a regenerated
   description stays searchable under its old text — silently, with
   `integrity-check` still passing. It surfaced only because the TS fixture builds
   the table in the production shape, while every Python test builds the standalone
   shape `init_database` produces, where the same statement is correct. Fixed on
   both sides ([#303](https://github.com/ccanalesb/lightroom-tagger/pull/303) for
   Python).

   `batch_embed_image` carried a smaller one of the same kind, not worth a Python
   PR but worth recording: when a file failed both the batch encode and the
   per-image retry, `encode_failed` was incremented twice, once by `record_skip`
   and once by the `vec is None` branch. The TS port has no fallback loop, so it
   cannot reproduce it.

   Two working rules for the remaining slices. Build fixtures from the *production*
   schema, not from what `init_database` happens to create — the two have already
   diverged, and migrations gated on `user_version` mean an existing catalog never
   converges. And when a ported test fails, establish whether Python actually
   passes the same case before assuming the port is wrong; here it was the original
   that was broken.

---
Created using Anthropic Claude. This line should stay on internal versions until a
human has reviewed and verified the content.
