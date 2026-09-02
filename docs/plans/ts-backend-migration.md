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
RAF or SR2 at all, and `exifr` only yields 160×120 thumbnails — so `libraw-wasm` is
the only viable path, not one option among many.

Two caveats:

1. `libraw-wasm` ships a **browser** build. It calls `new Worker(url, {type:'module'})`
   and its Emscripten runtime fetches `libraw.wasm` over `file://`. Running it in Node
   needs a ~25-line adapter: a `globalThis.Worker` shim over `node:worker_threads`, a
   worker-side `self` shim (it assigns `self.onmessage` / calls `self.postMessage`),
   and a `fetch` polyfill for `file://` URLs. This is proven working, but it is our
   code to own and re-verify on `libraw-wasm` upgrades.
2. `halfSize` is **ignored for DNG** — the DNG sample decoded at full 6209×4299.
   With 17,590 DNGs that is the dominant cost. Downscale explicitly after decode.

### CLIP embeddings — viable, but requires a full one-time reindex

`@huggingface/transformers` (transformers.js v3) with `Xenova/clip-vit-base-patch32`
at `dtype: 'fp32'` produces 512-d embeddings at **19.5 ms/image**. Re-embedding all
43,451 cached JPEGs is **~14 min single-threaded**, ~3.5 min across 4 worker threads.
`q8` is not faster (20.3 ms), so use fp32.

The critical finding: **JS vectors are not interchangeable with the stored Python
vectors.** Feeding the exact same cache JPEG to both implementations:

- same-image cosine, JS vs Python: **mean 0.931** (range 0.907–0.953)
- baseline cosine between unrelated photos (Python vs Python, 780 pairs): mean 0.557, p95 0.717, max 0.848
- **top-10 neighbour overlap: only 5.3/10**
- self-retrieval: 8/8 at rank 0

So a JS vector reliably identifies *its own* image, but the near-duplicate *ranking*
disagrees about half the time — and near-duplicate ranking is exactly what stack
detection and catalog similarity do. The drift is preprocessing (resampling), not
quantization.

**Consequence:** all 43,451 embeddings must be regenerated in one pass at cutover.
Mixing Python-written and JS-written vectors in the same index is not acceptable.
Once the whole index is JS-generated it is self-consistent and the drift is moot.

### Perceptual hashing — viable, reimplement directly

`imagehash.phash` is ~15 lines: greyscale → 32×32 LANCZOS → 2D DCT-II → top-left
8×8 → threshold at median. Reimplemented over `sharp` and compared against the
phashes Python stored in `vision_cache`:

- **7/12 exact matches**, mean Hamming distance **0.83 bits of 64**
- residual differences are 2 bits, from PIL-vs-libvips LANCZOS differences

Duplicate thresholds are far above 2 bits, so this is safe. No wavelet library is
needed: `imagehash.whash` is reachable only from `compute_multiple_hashes`, which
**nothing in production calls**. It is dead code — drop it.

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
| CLIP | **@huggingface/transformers**, fp32 | |
| LLM providers | **openai** npm SDK; `fetch` for Ollama | |
| Tests | **Vitest** | Already used by the frontend. |

Rejected: **tRPC** — deletes the OpenAPI seam ADR-0013 and the CI drift gate depend
on. **NestJS** — DI and decorator overhead unjustified for 63 routes. **Fastify** —
workable, but its OpenAPI story is a looser fit than Hono's.

## Sequencing

Vertical slices, each one shipping a working seam with a real consumer (per the
repo's slicing convention), not build-then-wire.

0. **Foundation** — TS project, config loader, `better-sqlite3` + `sqlite-vec` layer,
   `utils/responses` equivalents, Hono app shell with OpenAPI document.
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

1. **The CLIP reindex is all-or-nothing.** Half-migrated embeddings silently corrupt
   stack detection and catalog similarity (top-10 overlap 5.3/10). Back up
   `library.db` first and treat the reindex as a single gated step.
2. **DNG decode cost.** `halfSize` is ignored for DNG; 17,590 files at ~1.35 s each is
   ~6.5 hours single-threaded if the vision cache ever needs a full rebuild. The
   existing cache is intact (43,451/43,451 files present on disk), so this only bites
   on new imports or a forced rebuild — but budget for it.
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
