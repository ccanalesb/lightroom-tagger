# Phase 8: Embedding pre-filter & catalog cache pipeline - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver v3.0 Phase 8 behavior for MATCH-02 and CACHE-01:

- `vision_match` consults `image_clip_embeddings` to cosine-shortlist date-windowed catalog representatives before LLM judgment runs. Pre-filter aims at ≥10× LLM-call reduction vs the Phase 7 baseline while preserving recall on user-validated match pairs.
- `batch_stack_detect` and `batch_catalog_similarity` are recognized as catalog-cache work — their UI triggers move from MatchingTab to the catalog cache surface (`CatalogCacheTab`). Cache builds as a chain (`batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity`).
- `batch_embed_image` is extended to also embed `image_type='instagram'` rows so Instagram CLIP vectors become first-class cached artifacts and the matcher reads them from the DB instead of computing inline.

Out of scope:
- Wider-search fallback when shortlist is empty (was MATCH-03, dropped 2026-04-27 — not user-requested)
- Embedding model A/B benchmark (DINOv2 / SigLIP / OpenCLIP variants) — captured in `.planning/todos/pending/benchmark-embedding-recall.md`, separate work, may promote a different model in a later phase
- FAISS migration — sqlite-vec is the default; FAISS only if recall/latency targets fail in Phase 8 verification
- Any change to how stacks are constructed or how matching applies to stack members (Phase 7 contract preserved)

</domain>

<decisions>
## Implementation Decisions

### Instagram embedding source (G1)
- **D-01:** Extend `batch_embed_image` to also process `image_type='instagram'` rows. Instagram CLIP vectors live in `image_clip_embeddings` alongside catalog vectors, keyed by `image_type` + `image_key`. Matching reads pre-computed IG embeddings from the DB; no inline embed during `vision_match`.

### Pre-filter top-k (G2a)
- **D-02:** Pre-filter top-k default = 50. Exposed as a numeric UI override on the matching tab so the value can be tuned per run without redeploy.

### Pre-filter scope (G2b)
- **D-03:** The CLIP cosine shortlist gates the entire scoring stack — phash, description, and the final visual LLM judgment all run only on the shortlist. Rationale: description scoring is itself LLM-driven, so gating only the visual LLM would not deliver the intended cost reduction.

### Catalog cache pipeline UI (G3)
- **D-04:** `CatalogCacheTab` exposes one composite "Build cache" action that chains `batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity`. The chain runs the embed step over both catalog and Instagram rows (per D-01).
- **D-05:** Individual stage triggers (including the legacy `prepare_catalog`) live under an Advanced section on `CatalogCacheTab`. The Advanced section **reuses** the existing `AdvancedOptions` component pattern from the matching tab (DRY mandate from Phase 7 retained).
- **D-06:** Stack-detect and catalog-similarity job triggers are removed from `MatchingTab`. Their canonical home is `CatalogCacheTab`.

### Pipeline observability
- **D-07:** `vision_match` job log emits per-stage candidate counts: `date-window in → CLIP shortlist out → LLM judgments`. Counts are throttled per-batch summary, not per-image, to keep log volume reasonable.
- **D-08:** Cache-pipeline chain emits per-stage progress and skip reasons in the job log so operators can verify each step did or did not need to run.

### Claude's Discretion
- Exact UI copy for the "Build cache" button and Advanced section labels.
- Whether the chain is a single composite job handler or a sequential enqueue with dependencies — pick whichever cleanly preserves resume/cancel semantics.
- Default behavior when a prior stage is missing/incomplete (block downstream, warn, or auto-trigger) — pick the option that is least surprising and most observable.
- Numeric min/max bounds on the per-run top-k override (e.g. 1 ≤ k ≤ 500).
- Exact result-key shape for the new per-stage count metadata in `vision_match` results.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/ROADMAP.md` — v3.0 Phase 8 scope and success criteria for MATCH-02, CACHE-01
- `.planning/REQUIREMENTS.md` — detailed requirement language and dependency constraints
- `.planning/STATE.md` — current project phase pointer and milestone status

### Prior phase context
- `.planning/phases/05-image-embed-search-chat/05-CONTEXT.md` — image embedding service, `image_clip_embeddings` schema, `model_id`/`dim` invalidation rules
- `.planning/phases/06-similarity-stack-ui/06-CONTEXT.md` — `lightroom_tagger/core/clip_similarity.py` KNN utilities and stack representative contract
- `.planning/phases/07-stacks-in-matching-pin-similarity/07-CONTEXT.md` — representative-only matching contract that the pre-filter must respect

### Codebase maps
- `.planning/codebase/CONVENTIONS.md` — coding/test/style conventions
- `.planning/codebase/STRUCTURE.md` — backend/frontend ownership and extension points
- `.planning/codebase/STACK.md` — runtime stack and tooling constraints

### Backend integration points
- `lightroom_tagger/scripts/match_instagram_dump.py` — `match_dump_media` is where the CLIP shortlist hooks in (after the representative filter from Phase 7, before `score_candidates_with_vision`)
- `lightroom_tagger/core/matcher.py` — `find_candidates_by_date`, `score_candidates_with_vision` (the LLM/description/phash scoring path the shortlist gates)
- `lightroom_tagger/core/clip_similarity.py` — existing `knn_clip_catalog_keys`, `get_clip_embedding_blob_for_key`, `list_pin_similarity_candidate_keys`, `run_clip_similar_for_seed` utilities to reuse
- `apps/visualizer/backend/jobs/handlers.py` — `handle_vision_match`, `handle_batch_embed_image`, `handle_batch_stack_detect`, `handle_batch_catalog_similarity` (current handlers; `handle_batch_embed_image` is what gets extended for IG)
- `apps/visualizer/backend/jobs/checkpoint.py` — `fingerprint_*` helpers for idempotency on the extended embed job and any new chain handler

### Frontend integration points
- `apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx` — new home for the composite Build cache action and the Advanced individual triggers (incl. legacy `prepare_catalog`)
- `apps/visualizer/frontend/src/components/processing/MatchingTab.tsx` — add the per-run top-k numeric override; **remove** stack-detect + catalog-similarity trigger UI
- `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx` — reusable component to lift/share for `CatalogCacheTab` Advanced section
- `apps/visualizer/frontend/src/services/api.ts` — `JobsAPI` mutation methods for new chain trigger and any extended `batch_embed_image` parameters
- `apps/visualizer/frontend/src/constants/strings.ts` — all new copy for cache pipeline + top-k override lives here (no inline strings)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `image_clip_embeddings` (sqlite-vec table) already populated for catalog rows — the IG extension reuses the same table and embed pipeline.
- `clip_similarity.py` already exposes order-preserving KNN over a candidate key list, which is the exact shape the matcher needs (input: date-windowed representative keys; output: top-k by cosine).
- `AdvancedOptions` is already the established pattern for advanced-but-occasional job controls; lifting it to `CatalogCacheTab` is a direct DRY win.
- Existing `fingerprint_*` helpers + checkpoint resume already cover the idempotency pattern the extended embed job and chain runner need.

### Established Patterns
- Job handlers register in `JOB_HANDLERS` dict + emit progress 5–100% + write per-step checkpoints.
- Catalog-bound jobs are tagged via `JOB_TYPES_REQUIRING_CATALOG` so the worker enforces availability.
- Frontend job triggers go through `JobsAPI` and centralised `strings.ts`; new chain trigger follows that pattern.
- Result-key metadata pattern (e.g. `processed`, `skipped_*`, per-step counts) is the conventional place to surface observability data the UI/logs read.

### Integration Points
- `batch_embed_image` fingerprint must distinguish catalog-only vs catalog+instagram source sets so re-running with IG newly enabled actually picks up IG rows.
- `match_dump_media` gets a new shortlist step between the representative filter and `score_candidates_with_vision`. Per-stage counts are emitted from this point.
- `CatalogCacheTab` gains a primary "Build cache" CTA + Advanced disclosure; the `prepare_catalog` legacy trigger lives only inside Advanced.

</code_context>

<specifics>
## Specific Ideas

- DRY mandate (continued from Phase 7): `AdvancedOptions` is reused — no new advanced-controls component is created.
- Embedding model swap is explicitly deferred. Phase 8 wires the existing CLIP vectors; `benchmark-embedding-recall.md` is the hand-off if a future phase wants to compare DINOv2 / SigLIP / etc.
- sqlite-vec stays the KNN backend. FAISS is only justified if Phase 8 verification shows sqlite-vec can't hit the recall/latency target on this catalog size; that is a verification finding, not a Phase 8 design assumption.
- Per-run top-k UI override is intentionally numeric input (not slider/preset) so users can record exact values during recall benchmarking.

</specifics>

<deferred>
## Deferred Ideas

- **Wider-search fallback (was MATCH-03):** Dropped 2026-04-27 — Claude-introduced during requirements drafting, not user-requested. May resurface only if Phase 8 verification shows shortlist-empty cases are common enough to be a real workflow problem.
- **Embedding model A/B benchmark:** `.planning/todos/pending/benchmark-embedding-recall.md` — separate work, sets the top-k floor and may motivate a model swap in a later phase. Not a Phase 8 gate.
- **Backend restart and compression fix follow-up:** `.planning/todos/pending/2026-04-26-plan-backend-restart-and-compression-fix.md` — orthogonal infrastructure work, untouched by Phase 8.
- **Embed job discoverability and path failures follow-up:** `.planning/todos/pending/2026-04-26-fixes-for-embed-job-discoverability-and-path-failures.md` — relevant nearby work but separately scoped.

</deferred>

---

*Phase: 08-embedding-prefilter-and-cache-pipeline*
*Context gathered: 2026-04-27*
