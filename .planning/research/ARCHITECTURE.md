# Architecture Research — v3.0 Intelligent Discovery

Research grounded in the current Flask + SQLite + job-queue architecture (`lightroom_tagger/core/database.py`, `apps/visualizer/backend/jobs/handlers.py`, `apps/visualizer/backend/api/`, `lightroom_tagger/core/provider_registry.py`, `lightroom_tagger/core/analyzer.py`).

**Naming note:** The catalog table is `images` (not `catalog_images`). There is no `capture_time` column today; timing for burst detection should use `date_taken` and/or EXIF in `exif` JSON until a dedicated sub-second field is added if required.

---

## New Database Tables

### `image_stacks`

Represents a stack of duplicate/near-duplicate or burst photos. One row per stack; members reference the stack by id.

| Column | Type | Notes |
|--------|------|--------|
| `id` | INTEGER PK AUTOINCREMENT | Stable stack id |
| `stack_type` | TEXT NOT NULL | e.g. `burst`, `phash`, `manual` — how the stack was formed |
| `primary_image_key` | TEXT | Representative catalog key (nullable until chosen) |
| `created_at` / `updated_at` | TEXT (ISO) | Audit |
| `metadata` | TEXT JSON | Tunables: pHash threshold, time window (seconds), model ids |

| Index | Purpose |
|-------|---------|
| `idx_stacks_primary` on `primary_image_key` | Lookup by rep |

**FK:** Soft reference to `images.key` (SQLite optional); enforce in app when deleting images.

### `image_stack_members`

| Column | Type | Notes |
|--------|------|--------|
| `stack_id` | INTEGER NOT NULL | → `image_stacks.id` |
| `image_key` | TEXT NOT NULL | → `images.key` |
| `role` | TEXT | e.g. `primary`, `member` |
| `sort_order` | INTEGER | Burst sequence |
| `joined_at` | TEXT | When added to stack |

| Constraint | |
|------------|--|
| `PRIMARY KEY (stack_id, image_key)` | One membership per key per stack |
| Unique on `image_key` *if* every catalog image is in at most one stack (recommended for v1) | `UNIQUE(image_key)` |

### `image_text_embeddings` (semantic search over description text)

Stores dense vectors for **catalog** (and optionally Instagram) description text used for hybrid retrieval with FTS5.

| Column | Type | Notes |
|--------|------|--------|
| `image_key` | TEXT NOT NULL | |
| `image_type` | TEXT NOT NULL | `catalog` \| `instagram` — align with `image_descriptions` |
| `model_id` | TEXT NOT NULL | e.g. `text-embedding-3-small` or local model name |
| `dim` | INTEGER NOT NULL | Vector length |
| `embedding` | BLOB | `float32` array little-endian, length `dim` |
| `source_fingerprint` | TEXT | Hash of source text (summary + selected fields) to skip re-embed on unchanged text |
| `created_at` / `updated_at` | TEXT | |

| Constraint | |
|------------|--|
| `PRIMARY KEY (image_key, image_type, model_id)` | One row per model per image |

**Alternative:** `sqlite-vec` / `vss0` virtual table for ANN. Requires loadable extension and deployment story; a plain BLOB table keeps the first ship aligned with the rest of the app (Python-side cosine similarity in batches) until scale demands ANN.

### `image_embeddings` (visual / CLIP-style)

| Column | Type | Notes |
|--------|------|--------|
| `image_key` | TEXT NOT NULL | |
| `image_type` | TEXT NOT NULL | Default `catalog` |
| `model_id` | TEXT NOT NULL | e.g. `openai/clip` or `ViT-B/32` + provider id |
| `dim` | INTEGER | |
| `embedding` | BLOB | `float32` as above |
| `derived_from` | TEXT | `filepath` mtime or `vision_cache` key — invalidation |
| `created_at` / `updated_at` | TEXT | |

| Constraint | |
|------------|--|
| `PRIMARY KEY (image_key, image_type, model_id)` | |

### FTS5: `image_descriptions_fts` (virtual)

Not a “business” table; created alongside migrations.

- **Pattern:** `CREATE VIRTUAL TABLE image_descriptions_fts USING fts5( summary, composition, perspectives, technical, subjects, content='image_descriptions', content_rowid='rowid' )` *if* the library uses SQLite rowid linkage — the existing `image_descriptions` table has `TEXT` PK `image_key`, so the hidden `rowid` is still available for `content='...' content_rowid='rowid'` on SQLite 3.x.
- **Safer first step:** *External* contentless FTS5 with columns matching what you want to search, maintained by **AFTER INSERT/UPDATE/DELETE triggers** on `image_descriptions` (mirrors the single-writer discipline already used for `library_write` on writes to descriptions).
- Indexed text should include: `summary`, stringified JSON blobs (or a dedicated `search_blob` denormalized column updated in `store_image_description`).

**Optional denormalized column** on `image_descriptions`: `search_text` (TEXT) — concat of all fields used in FTS, maintained in application code in one place (`store_image_description`) to avoid fragile triggers parsing JSON.

---

## Modified `image_descriptions` (or adjacent columns)

**Visual attribute tags** (milestone) — add nullable columns to avoid breaking existing JSON consumers:

| Column | Type | Notes |
|--------|------|--------|
| `dominant_colors` | TEXT | JSON array of strings (or normalized hex) |
| `mood_tags` | TEXT | JSON array — prompt today already has `mood` inside `technical` in `analyzer.DESCRIPTION_PROMPT`; promote to first-class for facets |
| `has_repetition` | INTEGER | 0/1 boolean |

`store_image_description()` in `lightroom_tagger/core/database.py` and `ON CONFLICT` update list must include these fields.

**Rationale:** `parse_description_response()` already returns nested dicts; extend parsing (or a small normalizer) to fill these from model output and legacy `technical` for backfill.

---

## Modified Files

| File | Changes |
|------|---------|
| `lightroom_tagger/core/database.py` | `init_database`: new tables, FTS5 virtual table + triggers *or* `search_text` + FTS; `_migrate_add_column` for new `image_descriptions` columns; `store_image_description` / `get_image_description` / deserialization; extend `query_catalog_images` (and any raw SQL for search) with filters for mood/color/stack/similarity parameters as each feature lands |
| `lightroom_tagger/core/analyzer.py` | `DESCRIPTION_PROMPT` + `parse_description_response` (or post-parse step) to emit `dominant_colors`, `mood_tags`, `has_repetition` consistently |
| `apps/visualizer/backend/jobs/handlers.py` | New handlers for stack/embed jobs; register in `JOB_HANDLERS`; optional shared inner pattern like `_run_describe_pass` for checkpointing |
| `apps/visualizer/backend/jobs/checkpoint.py` | Fingerprint helpers for new job types (mirror `fingerprint_batch_describe`) |
| `apps/visualizer/backend/library_db.py` | Add new job types to `JOB_TYPES_REQUIRING_CATALOG` where handlers open the library DB |
| `apps/visualizer/backend/app.py` | Register new API blueprint(s) if split from `images` |
| `apps/visualizer/backend/api/images.py` | `GET` catalog list query params; **new** routes e.g. `GET/POST /api/images/similar`, `POST /api/search` or `/api/catalog/query` — see Integration |
| `apps/visualizer/backend/api/jobs.py` | No structural change; new job `type` strings whitelisted by handler registry |
| `lightroom_tagger/core/scoring_service.py` (or call sites in handlers) | Stack-aware scoring: score primary only, then propagate to members via UPDATE `image_scores` or denormalized inherited rows — **decision** |
| `lightroom_tagger/core/phash.py` | Optional: batch clustering helpers; core `hamming_distance` / `compare_hashes` already fit pHash stack job |
| `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` | New `FilterBar` schema entries for new facets |
| `apps/visualizer/frontend/src/hooks/useFilters.ts` (or catalog-specific schema module) | Encode new filter keys → API query params |
| `lightroom_tagger/core/provider_registry.py` | Optional: `defaults` key for `embedding` / `text_embedding` if using OpenAI-compatible providers only; *or* no change if embedders are code-first (sentence-transformers, local CLIP) |

---

## New Files / Modules

| Suggested path | Role |
|----------------|------|
| `lightroom_tagger/core/search/fts.py` (or `search_utils.py`) | Build/rebuild FTS, trigger definitions, `search_text` normalization |
| `lightroom_tagger/core/search/llm_sql.py` | LLM prompt with **schema snapshot** (generated from PRAGMA or hand-maintained) → JSON filter object → validate → call `query_catalog_images` with safe parameters only |
| `lightroom_tagger/core/search/hybrid.py` | Combine FTS hits + embedding similarity + structured filters; rank / fuse |
| `lightroom_tagger/core/embeddings/text.py` | Batch text embed API (provider or local) + write `image_text_embeddings` |
| `lightroom_tagger/core/embeddings/image.py` | Image embed pipeline (CLIP) + write `image_embeddings` |
| `lightroom_tagger/core/stacks/burst.py` | Sort by `date_taken` (+ optional future sub-second), group within Δt |
| `lightroom_tagger/core/stacks/phash_cluster.py` | Union-find or greedy clustering over `images.phash` using `phash.py` |
| `apps/visualizer/backend/api/search.py` (optional) | Dedicated blueprint for `POST /api/search` natural language + `GET` health for index status |
| Tests under `apps/visualizer/backend/tests/` and `lightroom_tagger/core/test_*.py` | New tables, handlers, and API contracts |

---

## Build Order

Dependency-oriented sequence (items in the same bullet can parallelize after dependencies are met).

1. **Schema + migration foundation**  
   - Add `image_descriptions` columns (visual attributes), `image_stack_members` / `image_stacks`, `image_text_embeddings`, `image_embeddings`.  
   - *Why first:* All features persist data; avoids rework in handlers.

2. **Describe pipeline extension (visual attributes)**  
   - Prompt + parse + `store_image_description` + API serialization.  
   - *Why early:* No dependency on stacks/embeddings; unblocks filter facets in UI.  
   - *Informs* FTS5 `search_text` content.

3. **FTS5 + denormalized `search_text` (or trigger-maintained fts)**  
   - Backfill job or one-time migration from existing rows.  
   - *Before* LLM-assisted search that expects keyword search over descriptions.

4. **Text embedding pipeline**  
   - `batch_text_embed` job (or lazy: embed on first search with queue).  
   - *Depends on:* stable text fields in `image_descriptions` (including `search_text`).  
   - *Before* “semantic” leg of natural language / hybrid search.

5. **Natural language search (LLM-to-SQL *filter object*, not raw SQL)**  
   - LLM returns a **structured** filter (perspective, date range, mood_tags, min_score, fts_query) validated by Pydantic; **never** execute model-generated SQL strings.  
   - *Depends on:* `query_catalog_images` (and hybrid module) understanding those fields; FTS + optional text embeddings for ranking.  
   - **API:** `POST /api/search` or `POST /api/images/query` with `{ "q": "..." }` returning the same shape as list catalog (or a thin wrapper) — keeps React data layer consistent.

6. **Image embedding pipeline + `/api/images/similar`**  
   - New job e.g. `batch_embed_image`; read file via `images.filepath` + `resolve_filepath`.  
   - *Can parallel* with (5) after (1) if teams split; *depends on* (1) for `image_embeddings`.

7. **Stack detection jobs + `image_stacks` population**  
   - `batch_stack_burst` (time-ordered) and/or `batch_stack_phash` (pHash graph).  
   - *Depends on:* (1). Uses existing `phash` on `images` where present.  
   - **Stack-aware scoring** *depends on* stacks existing — either new handler pass after `batch_score` or extended `batch_score` metadata `respect_stacks: true`.

**Critical path for “full” Intelligent Discovery UI:** (1) → (2) → (3) → (4) → (5); visual similarity (6) and stacking (7) are parallel after (1), with (7) scoring policy depending on (7) stacks + existing score pipeline.

---

## Integration Points

### 1. Natural language search (LLM + FTS + text embeddings)

| Layer | Integration |
|-------|-------------|
| **API** | New endpoint is cleaner than overloading `GET /api/images/` — e.g. `POST /api/search` with natural language, server returns `{ filters_applied, items, total }` reusing `query_catalog_images` *after* resolution. `GET` list remains for explicit filters (FilterBar). |
| **LLM** | Reuse `ProviderRegistry.get_client()` for chat completions; separate small module validates output schema (closes the loop with `query_catalog_images` parameters + `fts_query` string). |
| **FTS5** | Created in `init_database` or versioned migration in `database.py` following existing `_migrate_add_column` / `PRAGMA user_version` style for one-time rebuilds. |
| **Embeddings** | **New job type** `batch_text_embed` (or `embed_text` phase inside a composite job) is consistent with `batch_describe` — checkpoint, progress, logs. **Lazy** embed-on-search is possible but hurts latency; job-first matches existing UX. |

### 2. Photo stacking (burst + pHash)

| Layer | Integration |
|-------|-------------|
| **Data** | `image_stacks` + `image_stack_members`; `query_catalog_images` gains optional `stack_id` / `exclude_stack_members` / `stack_role` for UI. |
| **Jobs** | New handler(s): `handle_batch_stack_burst`, `handle_batch_stack_phash` *or* single `handle_batch_stack` with `metadata.mode` — same `JOB_HANDLERS` + `create_job` pattern. Checkpoint per processed key set like describe. **Sub-handlers** as pure functions in `lightroom_tagger/core/stacks/` keep `handlers.py` thin. |
| **Time** | Burst: `ORDER BY date_taken, key` on `images`; group consecutive rows within `delta_ms` (from metadata). Sub-second: may require new column from EXIF later. |
| **pHash** | `images.phash` + `phash.compare_hashes` / Hamming in nested loop or spatial index (future). |

### 3. Visual attribute tags

| Layer | Integration |
|-------|-------------|
| **Describe** | `analyzer.py` already documents `dominant_colors` and `mood` under `technical` in the prompt. Extend prompt with explicit `mood_tags` and `has_repetition` at top level; `store_image_description` persists new columns. |
| **No breaking change** | Old rows: NULL new columns; `GET` serializers default empty. JSON fields unchanged for old clients. |
| **Filters** | Extend `query_catalog_images` with `mood_tag`, `color`, `has_repetition` predicates; extend `FilterBar` schema in `CatalogTab`. |

### 4. Visual similarity (CLIP + endpoint)

| Layer | Integration |
|-------|-------------|
| **Storage** | `image_embeddings` table; no change to `provider_registry` *unless* embeddings use OpenAI/Ollama APIs — then same client pattern with `base_url` + model id. **Local** PyTorch/OpenCLIP: separate module, not necessarily `ProviderRegistry` (which is OpenAI-sdk oriented). |
| **Jobs** | `batch_embed_image` with selection parity to describe (date window, force, min_rating) — copy metadata patterns from `handle_batch_describe`. |
| **API** | `GET /api/images/<key>/similar?limit=…&model=…` *or* `POST` with a query key; load embedding for key, cosine against table (or sqlite-vss when enabled). |
| **sqlite-vss** | Optional second phase: load `vss0` in `init_database` *only if* extension available; else pure Python ANN. |

---

## Key Design Decisions

1. **LLM-to-SQL vs LLM-to-filters** — Use **LLM-to-structured-filters** only; map to whitelisted `query_catalog_images` / hybrid search. Do not execute generated SQL. Reduces injection and matches existing query helper.

2. **FTS5 maintenance** — Prefer a single `search_text` column updated in `store_image_description` + one FTS5 table, vs parsing JSON in triggers (simpler to debug).

3. **Text embeddings: job vs lazy** — Default **batch job** after describe for predictable performance; optional lazy path for small libraries.

4. **Image embeddings: provider** — Decide: OpenAI/compatible image embedding API *vs* local CLIP; affects `provider_registry` and deployment (GPU, size).

5. **Stack + scores** — Choose one: (a) only `primary_image_key` has `is_current=1` scores, members inherit in API layer; (b) duplicate `image_scores` rows for members with `inherited_from` pointer; (a) is less storage, (b) faster SQL filters.

6. **Single writer** — New writes must go through `library_write` where they touch `library.db`, consistent with `store_image_description` / score inserts.

7. **ANN at scale** — Start with BLOB + numpy cosine in Python; plan sqlite-vec or FAISS if libraries exceed ~50k images.

8. **instagram vs catalog** — For v1, restrict similarity + semantic search to `catalog` keys unless product requires parity; simplifies joins.

---

## Summary Table (capabilities ↔ primary touchpoints)

| Capability | DB | Jobs | API | Provider registry |
|------------|----|----|-----|---------------------|
| NL search + FTS + text embed | `image_descriptions_fts`, `image_text_embeddings`, optional `search_text` | `batch_text_embed` | `POST /api/search` | Text embed if remote |
| Stacking | `image_stacks`, `image_stack_members` | `batch_stack_*` | Optional admin GET stacks | N/A |
| Visual tags | `image_descriptions` new cols | (describe only) | `GET` images / filters | Unchanged (vision) |
| Visual similarity | `image_embeddings` | `batch_embed_image` | `/api/images/…/similar` | Optional if API-based |

This document is intended for ROADMAP / requirements authors: all file and table names are concrete; ordering reflects real dependencies in this codebase.
