# Phase 1: Visual tags & keyword search — Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the describe pipeline to extract visual attribute fields (`dominant_colors`, `mood_tags`, `has_repetition`) alongside existing output, and introduce FTS5-based keyword search over AI-generated description text (`summary` + `subjects`).

Two requirements in scope:
- **VIS-01**: Visual attributes extracted at describe-time, stored as nullable columns on `image_descriptions`, with a backfill path
- **NLS-02**: FTS5 index over description text; catalog API supports keyword/phrase search with no raw SQL from user input

</domain>

<decisions>
## Implementation Decisions

### FTS5 Architecture
- **D-01:** Use **SQLite FTS5** (not DuckDB, Tantivy, or any external service). Already in the same `.db` file, zero new infrastructure, 1–5ms query latency, sufficient for this dataset size.
- **D-02:** FTS virtual table uses `tokenize='porter unicode61'` — Porter stemming handles English description text correctly ("moody" matches "mood", "capturing" matches "capture").
- **D-03:** FTS table is an **external content table** backed by `image_descriptions` with BM25 ranking available via `bm25()`.

### FTS Sync Mechanism
- **D-04:** FTS index is maintained **Python-side inside `store_image_description`** — not via database triggers. Every describe/re-describe goes through this single write path (`library_write` context manager). Consistent with existing codebase patterns and fully testable in pytest without trigger side-effects.
- **D-05:** At migration time, run `INSERT INTO image_descriptions_fts(image_descriptions_fts) VALUES('rebuild')` once to index all existing `summary` text in pre-existing rows.

### What Gets Indexed
- **D-06:** FTS indexes **`summary` + `subjects` flattened**. The `subjects` JSON array (e.g. `["man in yellow raincoat", "wet cobblestone"]`) is joined as space-separated text before indexing. This makes specific scene elements searchable ("cobblestone", "raincoat") that may not appear verbatim in the summary paragraph.
- **D-07:** Lightroom metadata fields (`title`, `caption`, `keywords` from the `images` table) are **NOT** included in this FTS index — those remain as structured filter chips in the existing `FilterBar`.

### Search Integration in Catalog
- **D-08:** FTS search is a **dedicated "description search" input** — it does NOT replace or unify with the existing LIKE-based Lightroom keyword filter. The existing keyword filter on `images` table fields stays as-is (separate filter chip). The new FTS input searches AI-generated description content only.
- **D-09:** The existing `query_catalog_images` `keyword` param (LIKE on `images` table) remains unchanged. A new search parameter (e.g. `description_search`) triggers FTS lookup on `image_descriptions_fts`.
- **D-10:** FTS search returns matching `image_key` values, which are then used as an additional filter in the catalog query (inner join / WHERE IN).

### User Input Handling
- **D-11:** **Token AND mode** — user input is split on whitespace, each token is sanitized (FTS5 special characters stripped/escaped), and tokens are AND-joined: `token1 AND token2 AND token3`. All tokens must appear in the description (order-independent). This is the most natural behavior for searching description text.
- **D-12:** Minimum query length: 2 characters. Queries shorter than 2 characters are rejected at the API layer with a clear error (not passed to FTS).
- **D-13:** Empty queries (after sanitization) return the full unfiltered catalog (no FTS applied).

### Visual Attributes (VIS-01)
- **D-14:** `dominant_colors` (JSON array), `mood_tags` (JSON array), `has_repetition` (INTEGER 0/1) added as **nullable columns** on `image_descriptions`. Old rows default NULL — no breaking change to existing description consumers.
- **D-15:** Visual attributes are extracted **as part of the existing describe prompt** (one LLM call, not a separate pass). The prompt is extended to request these fields alongside `summary`, `composition`, `perspectives`, etc.
- **D-16:** `_store_structured` in `description_service.py` is the extension point — new fields are mapped from LLM output there, same as existing fields.
- **D-17:** Null-safe: rows missing visual attribute columns (pre-migration) must not cause 500s. `COALESCE`/`DEFAULT NULL` at schema level; Python deserialization treats missing keys as `None`.

### Backfill
- **D-18:** Backfill uses the **existing batch describe job** with a new filter: re-describe images where `dominant_colors IS NULL` (i.e. not yet attributed). No new job type needed. Re-describing goes through `store_image_description`, so FTS is updated automatically as part of backfill.
- **D-19:** Backfill is **user-initiated** (not auto-triggered at startup). Surfaced as a job option, consistent with existing batch describe UX.

### Claude's Discretion
- Schema migration approach (ALTER TABLE ADD COLUMN vs new migration file) — follow existing migration pattern in the codebase
- Exact FTS table name (`image_descriptions_fts` or similar)
- Exact API parameter name for description search (`description_search`, `q`, `desc_search`)
- Whether subjects are concatenated at index-time (in `store_image_description`) or at FTS-table-definition-time via a generated column

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — VIS-01 (visual attribute extraction), NLS-02 (keyword search over descriptions); implementation guidance section specifies nullable JSON columns and no raw SQL

### Roadmap
- `.planning/ROADMAP.md` §Phase 1 — success criteria: additive schema, denormalized `search_text`/FTS5, API search parameter with injection tests, null-safe serialization

### Codebase — describe pipeline
- `lightroom_tagger/core/description_service.py` — `_store_structured`, `describe_matched_image`, `describe_instagram_image` — the write path to extend
- `lightroom_tagger/core/database.py` — `store_image_description`, `query_catalog_images`, `library_write` context manager
- `lightroom_tagger/core/analyzer.py` — `describe_image`, `_describe_image_via_provider` — where the LLM call and prompt live
- `lightroom_tagger/core/prompt_builder.py` — prompt assembly; visual attribute fields need to be added here

### Codebase — API layer
- `apps/visualizer/backend/api/images.py` — `/api/images/catalog` endpoint; where new `description_search` param goes
- `apps/visualizer/backend/tests/test_images_catalog_api.py` — existing catalog API tests; injection-safety tests for new param go here

### Codebase — frontend
- `apps/visualizer/frontend/src/` — `FilterBar`, `useFilters` hook — where the new description search input plugs in (separate from existing keyword filter chip)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `store_image_description` — single write path, already uses `library_write` context; extend here for FTS update
- `_store_structured` in `description_service.py` — maps LLM output dict → DB record; add visual attribute fields here
- `query_catalog_images` — already accepts optional filter params; add `description_search` param alongside existing `keyword`
- `FilterBar` + `useFilters` hook — existing reusable filter framework from v2.1; description search input is a new `search` descriptor
- `success_paginated` / `error_bad_request` in `utils/responses.py` — use for API response and input validation

### Established Patterns
- JSON columns stored as serialized strings, deserialized in Python (`_serialize_json` / `json.loads`)
- `library_write` context manager for all DB writes — FTS update must happen inside the same context
- `ALTER TABLE ADD COLUMN` with `DEFAULT NULL` for additive schema changes (no breaking migrations)
- Pydantic / allowlist validation for any user-provided filter input (existing pattern in NLS-01 scope, but injection safety applies here too)

### Integration Points
- `store_image_description` → add FTS upsert call after the main INSERT
- `query_catalog_images` → add optional FTS JOIN when `description_search` param is present
- Catalog frontend `FilterBar` → new `search` descriptor for description text search

</code_context>

<specifics>
## Specific Ideas

- Porter stemming (`tokenize='porter unicode61'`) was explicitly chosen after researching FTS5 tokenizer options — it handles English natural language description text better than the default `unicode61` alone
- The "subjects flattened" approach: `" ".join(subjects_list)` before inserting into FTS, not a separate indexed column — keep it simple
- Token AND mode sanitization: strip `"*()-+^` characters from user input before splitting and AND-joining
- FTS `rebuild` command at migration time: `INSERT INTO image_descriptions_fts(image_descriptions_fts) VALUES('rebuild')` — one-shot backfill of existing summaries into the index

</specifics>

<deferred>
## Deferred Ideas

- Typo tolerance / fuzzy matching — FTS5 doesn't support this; covered by Phase 3 semantic embeddings
- Prefix/autocomplete search — could be added later with `prefix='2 3'` config on the FTS table; not needed for Phase 1
- Searching Lightroom metadata fields (title, caption, keywords) via FTS — separate concern; existing LIKE filter handles this
- Cross-table unified search (descriptions + Lightroom fields in one query) — Phase 2 facets/NL filters territory
- BM25 relevance ranking in API response — could expose `rank` score per result; deferred until Phase 3 when hybrid ranking is designed

</deferred>

---

*Phase: 01-visual-tags-keyword-search*
*Context gathered: 2026-04-23*
