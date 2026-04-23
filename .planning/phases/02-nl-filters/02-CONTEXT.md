# Phase 2: NL filters — Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend-only phase. Implement a natural language → structured filter translation endpoint that accepts a plain text query, calls the LLM via `ProviderRegistry`, returns a validated Pydantic filter object AND the matching catalog results.

No new frontend UI — the Phase 5 chat panel (NLS-05) will consume this endpoint.

**Requirement in scope:** NLS-01 only. VIS-02 was removed from the roadmap (manual color/mood chips rejected in favor of LLM-driven discovery).

</domain>

<decisions>
## Implementation Decisions

### Endpoint shape
- **D-01:** New endpoint — `POST /api/images/nl-search` (or similar) — accepts `{"query": "..."}` body.
- **D-02:** Response returns **both** the derived filter object AND the catalog results, so Phase 5 can show "I interpreted your query as: posted=false, mood=moody, min_score=7". Shape: `{"filters": {...}, "results": [...], "total": N}`.
- **D-03:** No frontend changes in this phase — endpoint only.

### LLM call
- **D-04:** Always call the LLM — no bypass logic for "simple" queries. Let the LLM decide whether to use `description_search`, `dominant_colors`, `mood_tags`, or any other field. Consistent behavior, simpler code.
- **D-05:** Use existing `ProviderRegistry` pattern (same as describe, score, match). No new provider abstraction.

### Filter object (Pydantic)
- **D-06:** LLM returns a **validated Pydantic model** — allowlisted fields only, never raw SQL. Invalid or unrecognised fields are rejected with a clear error.
- **D-07:** Allowed fields map directly to `query_catalog_images` parameters: `posted`, `month`, `keyword`, `min_rating`, `date_from`, `date_to`, `score_perspective`, `min_score`, `sort_by_score`, `sort_by_date`, `description_search`, `dominant_colors` (list), `mood_tags` (list).
- **D-08:** `dominant_colors` and `mood_tags` require adding array-contains filter support to `query_catalog_images` (JSON array membership via SQLite `json_each` or LIKE — Claude's discretion on implementation).

### Error handling
- **D-09:** LLM parse failures (malformed JSON, fields outside allowlist) return HTTP 400 with a clear error message — not a 500.
- **D-10:** Empty or whitespace-only query returns 400.

### Claude's Discretion
- Exact endpoint path (`/api/images/nl-search` vs `/api/search/nl` vs other)
- Exact Pydantic model name and module location
- Prompt design for the LLM (system prompt instructing it to return JSON filter object)
- SQLite implementation for `dominant_colors`/`mood_tags` array-contains filtering

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — NLS-01 definition; Implementation Guidance (Pydantic filter object, ProviderRegistry pattern, no raw SQL)

### Roadmap
- `.planning/ROADMAP.md` §Phase 2 — success criteria

### Phase 1 context
- `.planning/phases/01-visual-tags-keyword-search/01-CONTEXT.md` — D-07 through D-13 (description_search FTS), D-14 through D-17 (dominant_colors/mood_tags schema)

### Codebase — backend
- `apps/visualizer/backend/api/images.py` — existing `/api/images/catalog` endpoint and `query_catalog_images` call; new endpoint follows same pattern
- `lightroom_tagger/core/database.py` — `query_catalog_images` function; needs `dominant_colors`/`mood_tags` filter params added
- `apps/visualizer/backend/api/providers.py` — `ProviderRegistry` usage pattern
- `lightroom_tagger/core/provider_registry.py` — registry internals; how other features call it
- `apps/visualizer/backend/utils/responses.py` — `success_paginated`, `error_bad_request` response helpers

### Codebase — existing NL-adjacent patterns
- `lightroom_tagger/core/analyzer.py` — how LLM calls are structured (prompt + provider call pattern to follow)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `query_catalog_images` — already accepts all the structured filter params; extend with `dominant_colors`/`mood_tags`
- `ProviderRegistry` — existing LLM call infrastructure; reuse exactly as describe/score/match do
- `success_paginated` / `error_bad_request` — response helpers already in use across all API endpoints

### Established Patterns
- All LLM calls go through `ProviderRegistry` with fallback order
- API endpoints live in `apps/visualizer/backend/api/` as Flask blueprints
- Input validation returns 400 via `error_bad_request`
- JSON array fields (`dominant_colors`, `mood_tags`) stored as serialized strings; deserialized in Python

### Integration Points
- New endpoint registered in `apps/visualizer/backend/app.py` alongside existing blueprints
- `query_catalog_images` in `lightroom_tagger/core/database.py` needs two new optional params

</code_context>

<specifics>
## Specific Ideas

- Response shape explicitly includes derived `filters` object so Phase 5 chat panel can display "I understood: ..." to the user
- LLM decides whether to use `description_search` (FTS) or `dominant_colors`/`mood_tags` or both — no hardcoded bypass rules

</specifics>

<deferred>
## Deferred Ideas

- Frontend NL input UI — belongs in Phase 5 (NLS-05 chat panel)
- VIS-02 (manual color/mood filter chips) — removed from roadmap entirely; LLM-driven discovery is the chosen approach

</deferred>

---

*Phase: 02-nl-filters*
*Context gathered: 2026-04-23*
