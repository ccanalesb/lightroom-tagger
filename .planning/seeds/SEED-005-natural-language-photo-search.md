---
id: SEED-005
status: dormant
planted: 2026-04-15
planted_during: v2.0 (milestone complete)
trigger_when: next major feature milestone (v3.0 or similar)
scope: Large
---

# SEED-005: Natural language search over catalog using descriptions and scores

## Why This Matters

The system already generates rich structured data for every photo — summaries, composition analysis, subject tags, per-perspective scores with rationale text, and Instagram posting status. But there's no way to *query* this data conversationally. You can't ask "What was my best street photo from December that I haven't posted yet?" even though all the data to answer that question already exists in the database.

This is the difference between a tool that *analyzes* your photos and one that *understands* your catalog. Natural language search would let you explore your own work the way you think about it — by mood, subject, time, quality, posting status — rather than scrolling through grids and mentally cross-referencing panels.

## When to Surface

**Trigger:** Next major feature milestone (v3.0 or similar)

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- Search or discovery features for the catalog
- AI-powered query or conversational interface
- Major new feature milestone beyond polish/UX
- Embedding or vector database integration
- Making the app "smart" beyond analysis (interactive intelligence)

## Scope Estimate

**Large** — A full milestone. This is a significant capability addition with multiple layers:

1. **Query understanding** — Parse natural language into structured filters (date ranges, perspective slugs, score thresholds, posted/unposted, subjects). Could use an LLM to convert questions into SQL-compatible filters, or a lighter NLU approach.
2. **Semantic search over descriptions** — The `summary`, `composition`, `perspectives`, `subjects`, and `rationale` fields contain rich free text. Full-text search (SQLite FTS5) handles keyword matching, but genuine semantic search (e.g. "moody cityscape at night") requires embeddings and vector similarity.
3. **Embedding pipeline** — Generate and store embeddings for description text. Options: local models (sentence-transformers), API-based (OpenAI embeddings), or hybrid. Needs a storage layer (sqlite-vss, pgvector, or a dedicated vector DB).
4. **Search UI** — A search bar or conversational interface in the frontend. Results should show thumbnails, scores, descriptions, and why each result matched the query.
5. **Hybrid ranking** — Combine semantic similarity with structured filters (date, score, posted status) for results that actually answer compound questions.

## Breadcrumbs

Related code and decisions found in the current codebase:

### Data already available
- `lightroom_tagger/core/database.py` — `image_descriptions` table (line 302): `summary`, `composition`, `perspectives`, `technical`, `subjects`, `best_perspective` — all free text ready for embedding
- `lightroom_tagger/core/database.py` — `image_scores` table (line 329): `rationale` field contains per-perspective text explanations of why a score was given
- `lightroom_tagger/core/database.py` — `catalog_images` table: `date_taken`, `keywords`, `rating` — structured fields for filtering
- `lightroom_tagger/core/database.py` — `matches` table: join to determine posted/unposted status

### Description service (generates the text to search)
- `lightroom_tagger/core/description_service.py` — generates structured descriptions per image
- `lightroom_tagger/core/scoring_service.py` — generates scores with rationale text

### Existing query patterns
- `lightroom_tagger/core/database.py` — `get_image_description()` (line 1528), `get_current_scores_for_image()` (line 1815)
- `lightroom_tagger/core/identity_service.py` — already aggregates scores + descriptions for identity/best-photos; similar aggregation needed for search results
- `apps/visualizer/backend/api/images.py` — existing image API endpoints that could host a `/search` route

### Frontend entry points
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — catalog browser, natural place for a search bar
- `apps/visualizer/frontend/src/pages/ImagesPage.tsx` — images page layout

## Notes

The phased approach would likely be:

**Phase 1 — Structured query via LLM.** Send the user's question + the database schema to an LLM, get back structured filters (date range, perspective, min score, posted status, keyword), execute as SQL. No embeddings needed — just smart filter generation. This alone handles "best photo from December I haven't posted" perfectly.

**Phase 2 — Full-text search.** Add SQLite FTS5 over description summaries and rationales. Handles keyword-style queries ("sunset over bridge") without embeddings.

**Phase 3 — Semantic search with embeddings.** Generate embeddings for all description text, store in sqlite-vss or similar. Handles abstract queries ("moody atmosphere", "feeling of solitude") where keywords don't match but meaning does.

**Phase 4 — Conversational interface.** Multi-turn search where you can refine ("show me more like #3 but from summer"). Chat-style UI in the frontend.

The existing provider registry pattern (supporting multiple AI providers) would extend naturally to embedding providers.
