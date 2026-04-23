# Phase 3: Semantic Search & Results — Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

**Backend only.** Introduce text embedding infrastructure and a hybrid semantic search API. No frontend UI in this phase — all result display is deferred to Phase 5 (NLS-05 chat panel).

Requirements in scope:
- **NLS-03**: `batch_text_embed` job stores text vectors; semantic queries return ranked results using hybrid ranking
- **NLS-04 (partial)**: API response shape includes thumbnails, scores, and "why matched" string per result row — the data contract only; the UI that renders it belongs to Phase 5

</domain>

<decisions>
## Implementation Decisions

### Vector Storage
- **D-01:** Use **`sqlite-vec`** SQLite extension. Vectors stored in the same `.db` file as catalog data, queryable via SQL alongside `query_catalog_images`. Add `pip install sqlite-vec` to requirements; load extension at connection time in `database.py` (e.g., `init_database` or a dedicated `load_extensions` call).

### Embedding Model
- **D-02:** Use **local `sentence-transformers`** — no API calls, no cost, reproducible offline. Add `pip install sentence-transformers` to requirements.
- **D-03:** Model: **`all-mpnet-base-v2`** — 768-dimensional vectors. Better semantic quality for descriptive prose than MiniLM. Model is downloaded on first use and cached in `~/.cache/torch`.
- **D-04:** Embedding generation does **not** go through `ProviderRegistry` or `FallbackDispatcher` — `sentence-transformers` runs locally and is a direct Python call. This is the only exception to the "all LLM calls via ProviderRegistry" pattern.

### Batch Embed Job
- **D-05:** `batch_text_embed` is a **proper job type** registered in `JOB_TYPES_REQUIRING_CATALOG`, triggerable by the user through the existing job API (`POST /api/jobs` with `type: "batch_text_embed"`). It appears in `JobQueueTab` with progress reporting consistent with `batch_describe` and `batch_score`.
- **D-06:** Coverage/progress: job reports per-image progress through the existing job progress mechanism (same pattern as other batch jobs). The response metadata on semantic search queries includes how many catalog images are not yet embedded (so callers know the index is partial).

### Hybrid Ranking
- **D-07:** Use **RRF (Reciprocal Rank Fusion)** to combine FTS5 and semantic similarity rank lists. Score formula: `1/(k + rank)` per list, summed. Standard constant `k=60`. No calibration needed; deterministic given same inputs; test-stable.
- **D-08:** Hybrid is always applied when both FTS and embedding results are available. Pure semantic (embedding-only) is never exposed — FTS always participates.
- **D-09:** **Degradation**: images without embeddings are **excluded** from semantic search results entirely. No mixed-mode fallback for unembedded images. The API response includes a `missing_embeddings_count` (or equivalent) metadata field so callers can surface "X images not yet indexed."

### "Why Matched" String
- **D-10:** Generated **template-based** from ranking signals available at query time — not an LLM call. Examples: `"Semantic match (0.87) · keyword: moody"`, `"FTS match · embedding: 0.79"`, `"Embedding match (0.84)"`. Assembles from whichever signals contributed to the final RRF score.
- **D-11:** The `why_matched` string is included in **each result row** in the API response JSON alongside `thumbnail_url` (or equivalent image key), `score`, and catalog fields. This is the NLS-04 data contract — Phase 5 renders it.

### Frontend
- **D-12:** **No frontend changes in this phase.** All result display, dedicated search page, and UI layout decisions are deferred to Phase 5 (NLS-05). Phase 3 delivers only the API and backend infrastructure.

### Claude's Discretion
- Exact sqlite-vec table name and schema (e.g., `image_embeddings` vec0 table keyed by `image_key`)
- Exact vector distance metric (cosine similarity is standard for mpnet; L2 is the alternative)
- Whether embeddings are stored inline in the main DB file or a companion `embeddings.db` (same directory, same backup story)
- Python module structure for the embedding service (`lightroom_tagger/core/embedding_service.py` or similar)
- Exact `missing_embeddings_count` field name in API response metadata

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — NLS-03 and NLS-04 definitions; dependency notes (NLS-03 depends on NLS-01 and NLS-02)

### Roadmap
- `.planning/ROADMAP.md` §Phase 3 — success criteria (4 items)
- `.planning/ROADMAP.md` §Phase 5 — NLS-05 chat panel owns the frontend; Phase 3 must not lock layout decisions

### Prior phase context
- `.planning/phases/01-visual-tags-keyword-search/01-CONTEXT.md` — D-03 (FTS5 external content table, BM25 via `bm25()`), D-06 (what gets indexed: summary + subjects), D-11 (token AND mode)
- `.planning/phases/02-nl-filters/02-CONTEXT.md` — D-02 (response shape `{"filters":…, "images":…, "total":…}`), D-06/D-07 (Pydantic allowlist)

### Codebase — backend
- `lightroom_tagger/core/database.py` — `query_catalog_images` (integration point for hybrid results), `init_database` (where sqlite-vec extension load should go), `_migrate_image_descriptions_fts` (pattern for new migration steps)
- `lightroom_tagger/core/analyzer.py` — `describe_image` / `_describe_image_via_provider` (batch job pattern; do NOT follow for embedding — D-04)
- `apps/visualizer/backend/library_db.py` — `JOB_TYPES_REQUIRING_CATALOG` (add `batch_text_embed` here)
- `apps/visualizer/backend/api/jobs.py` — `create_new_job` (job creation pattern, progress reporting)

### External
- `sqlite-vec` docs: https://alexgarcia.xyz/sqlite-vec/ — vec0 virtual table, extension loading
- `sentence-transformers` model card: `sentence-transformers/all-mpnet-base-v2` (768-dim, cosine similarity)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `lightroom_tagger/core/database.py` — `library_write` context manager (use for all embedding writes), `init_database` (extension load point)
- `lightroom_tagger/core/fallback.py` + `vision_client.py` — do NOT use for local sentence-transformers (D-04); reference only for job callback/logging patterns
- `apps/visualizer/backend/api/jobs.py` — `create_job`, job progress callbacks — reuse exactly for `batch_text_embed`
- `lightroom_tagger/core/database.py` — `_migrate_image_descriptions_fts` — reference for adding new migration step to `init_database`

### Established Patterns
- Batch jobs: `batch_describe` is the canonical reference — checkpointed progress, cancellation via `cancel_scope`, queued via job API, visible in `JobQueueTab`
- DB migrations: `_migrate_add_column` + idempotent `CREATE TABLE IF NOT EXISTS` inside `init_database`
- FTS5 query: `build_description_search_document`, `build_description_fts_query` — reuse for generating the text to embed (same content that's indexed in FTS)

### Integration Points
- `query_catalog_images` — hybrid search returns image keys that feed into this function (or replaces it with a new `query_catalog_semantic` function)
- `init_database` — sqlite-vec extension load goes here
- `JOB_TYPES_REQUIRING_CATALOG` in `library_db.py` — register `batch_text_embed`
- `POST /api/images/nl-search` (Phase 2) — semantic results could optionally be folded into the NL search path in a future phase; Phase 3 adds a separate `POST /api/images/semantic-search` (or equivalent) — planner's call on exact path

</code_context>

<specifics>
## Specific Ideas

- "Why matched" string format example: `"Semantic match (0.87) · keyword: moody"` — planner should follow this template shape
- `batch_text_embed` should embed the same text that FTS5 indexes (`summary` + flattened `subjects`) to keep the two retrieval signals semantically aligned
- `missing_embeddings_count` in the response lets Phase 5 show a "not all images indexed" notice without extra API calls

</specifics>

<deferred>
## Deferred to Phase 5

- **Dedicated search results page** — layout, routing, and all UI for displaying semantic results. Phase 5 (NLS-05) owns the chat panel that will absorb this surface.
- **NLS-04 result display** — thumbnails, scores, "why matched" rendered in the UI. Phase 3 delivers the data contract (API response shape); Phase 5 renders it.
- **Search input UX** — where the user types a semantic query (chat panel, search bar, etc.) is Phase 5.

## Deferred Ideas

None raised during discussion that were out of scope.

</deferred>

---

*Phase: 03-semantic-search-and-results*
*Context gathered: 2026-04-23*
