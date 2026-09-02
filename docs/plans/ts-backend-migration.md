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

**Consequence — a strictly better plan than reindexing:** port Pillow's resampler
(~90–110 lines, fixed-point) and feed our own tensor, bypassing `RawImage.resize`.
Node then writes vectors that are drop-in compatible with the 43,451 already stored,
and **no reindex is required**. Re-embedding everything stays available as a fallback
if the port proves troublesome: ~14 min single-threaded, ~3.5 min over 4 workers.

### Perceptual hashing — viable, reimplement directly

`imagehash.phash` is ~15 lines: greyscale → 32×32 LANCZOS → 2D DCT-II → top-left
8×8 → threshold at median. Reimplemented over `sharp` and compared against the
phashes Python stored in `vision_cache`:

- **7/12 exact matches**, mean Hamming distance **0.83 bits of 64**
- residual differences are 2 bits, from PIL-vs-libvips LANCZOS differences

Duplicate thresholds are far above 2 bits, so this is safe even as-is — and the same
Pillow resampler port that CLIP needs makes it **bit-exact**, since the 2-bit residual
has exactly the same cause. This is the second consumer of that shared module.

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

Budget this as **one deliberate shared module** with a fixture test asserting
bit-exactness against Pillow output. The trap is that `sharp` runs fine and looks
right while being quietly wrong.

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
   fixture test asserting bit-exact agreement with Pillow. Do this before any image
   work, because everything downstream inherits its correctness.
1. **First vertical slice: `/api/system`** — proves the whole contract chain from a TS
   route through OpenAPI to `api.gen.ts` with the drift gate green. Highest-value
   slice: it de-risks ADR-0013 before any domain work.
2. **Read-only route groups** — catalog/images, scores, descriptions, perspectives,
   identity, providers, stacks, frame substance.
3. **Job engine** — worker_threads runner, `JOB_TYPES` registry, transitions state
   machine, checkpoints, socket.io progress. Preserve the ADR-0010 guardrails.
4. **Job handlers**, one family per slice — catalog sync, embed, analyze/score,
   describe, stacks, frame substance, path diagnostics.
5. **Library core** — database package, scoring, identity, vision providers, prompt
   builder, frame substance detector, hasher, image prep, RAW/vision cache.
6. **CLI** — replaces the `lightroom-tagger` console script.
7. **Cutover** — back up `library.db`, run the full CLIP reindex (~14 min), switch.

## Risks

1. **Everything image-derived depends on the resampler port.** If it is not
   bit-exact, CLIP embeddings drift into the near-duplicate band and silently corrupt
   stack detection and catalog similarity (top-10 overlap 5.3/10). It fails quietly,
   not loudly. Gate it with a Pillow-comparison fixture test before wiring any
   consumer, and back up `library.db` before the first write-path run. If the port is
   abandoned, the fallback is a single all-or-nothing reindex of all 43,451
   embeddings (~14 min) — never a partial one.
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

---
Created using Anthropic Claude. This line should stay on internal versions until a
human has reviewed and verified the content.
