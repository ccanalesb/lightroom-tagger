---
id: SEED-018
status: dormant
planted: 2026-04-17
planted_during: active development (post v2.0)
trigger_when: when we add a proper search/filter UI to the catalog
scope: Large
---

# SEED-018: Visual attribute search — filter by color, repetition, and abstract concepts

## Why This Matters

The catalog browser today is a grid you scroll through. There's no way to ask
"show me all shots with dominant red tones", "find images where the same element
repeats across the frame", or "show me everything that feels isolated and quiet".
These queries require understanding the *visual content* of images — not just the
text descriptions we already have, but semantic embeddings of what the images look
like. This turns the catalog from a chronological archive into a navigable visual
library, surfacing patterns in your own shooting style you couldn't find by hand.

Complements SEED-005 (natural language search over structured text data) —
that seed handles "best street photo from December"; this seed handles
"everything with bold graphic lines" or "images with repetition of shapes".

## When to Surface

**Trigger:** When we add a proper search/filter UI to the catalog

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- Adding a search bar, filter panel, or query UI to the catalog/images page
- Starting a "smart collections" or browsing improvement milestone
- Integrating embeddings or vector search (SEED-005 Phase 3 overlap)
- Adding a "similar images" or "find more like this" feature

## Scope Estimate

**Large** — A full milestone. Three distinct capability layers need to be built:

1. **Visual embeddings pipeline** — Generate and store image embeddings using a
   vision model (CLIP, or via existing provider API). Needs a new table or
   sqlite-vss extension for vector storage. The existing `provider_registry`
   pattern could host an embedding provider abstraction.

2. **Attribute extraction** — For explicit attributes like dominant color and
   repetition, a lightweight extraction pass at describe-time (or lazily on
   query) can extract structured tags: `dominant_colors: [red, orange]`,
   `has_repetition: true`, `mood: isolated`. These would live as indexed columns
   or JSON in a new `image_visual_attributes` table alongside `image_descriptions`.

3. **Search UI** — A search/filter bar on the catalog page with facets (color
   palette chips, mood tags, concept keywords) plus a freeform semantic query
   input. Results ranked by embedding similarity + attribute match.

## Breadcrumbs

### Data layer — where to add visual attributes
- `lightroom_tagger/core/database.py` — `image_descriptions` table: `summary`,
  `composition`, `subjects` — already exists; visual attributes could be a
  new sibling table `image_visual_attributes`
- `lightroom_tagger/core/description_service.py` — the describe pipeline;
  attribute extraction could run as an extra pass here or be a separate job type
- `lightroom_tagger/core/structured_output.py` — Pydantic validation pattern to
  follow for a new `VisualAttributesResponse` model

### Job system — new job type for attribute extraction
- `apps/visualizer/backend/jobs/handlers.py` — `JOB_HANDLERS` dict; new
  `batch_extract_attributes` handler would follow the same pattern as
  `batch_describe`
- `lightroom_tagger/core/analyzer.py` — prompt/parse layer for vision calls;
  attribute extraction prompts would live here

### Frontend — catalog filter entry point
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — catalog
  browser, natural home for a color/concept filter bar
- `apps/visualizer/frontend/src/pages/ImagesPage.tsx` — page layout
- `apps/visualizer/frontend/src/services/api.ts` — API service layer where a
  new `/api/images/search` endpoint call would be added

### Related seeds
- SEED-005 (`natural-language-photo-search`) — overlaps on semantic search
  infra; Phase 3 of that seed (embeddings) and this seed share the same
  vector storage and embedding provider concerns. Coordinate to avoid
  building two separate embedding pipelines.

## Notes

**Phased approach:**

**Phase 1 — Explicit attribute tags at describe-time.** Extend the describe
prompt to also return `dominant_colors`, `has_repetition`, `mood_tags` as
structured fields. Store in `image_descriptions` or a new sidecar table. Filter
UI uses these as facets — no embeddings needed yet.

**Phase 2 — Image embeddings for semantic similarity.** Run a CLIP-style
embedding over catalog images. Store vectors in sqlite-vss. Power "more like
this" and abstract concept queries ("show me images that feel claustrophobic").

**Phase 3 — Hybrid search UI.** Combine facet filters (color chips, mood tags)
with a freeform semantic query box. Rank results by combined score: attribute
match + embedding cosine similarity.

The provider registry abstraction (`lightroom_tagger/core/provider_registry.py`)
is the right place to add an embedding provider interface so multiple backends
(local CLIP, OpenAI embeddings, Cohere) can be swapped in without changing
the pipeline code.
