# Phase 5: Image Embed & Search Chat — Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Two deliverables:

1. **`batch_embed_image` job** — generates and stores image embeddings (CLIP-style) for catalog images in sqlite-vec; follows the same job infrastructure pattern as `batch_text_embed` (Phase 3) and `batch_stack_detect` (Phase 4).

2. **Chat search panel** — a dedicated `/search` page with a split layout: conversation thread (left, ~40%) and results grid (right, ~60%). Each user message runs a search; the LLM sees prior turns as context so follow-up messages can refine the active result set.

Requirements in scope:
- **SIM-01**: Job generates and stores image embeddings with `model_id` + `dim`; checkpointed, cancellable, skips unchanged images via fingerprint comparison
- **NLS-05**: Chat-like panel with conversation history and results grid; each message refines the active result set

Out of scope:
- **NLS-06** (pin-to-image visual similarity) — Phase 7
- **SIM-02** ("more like this" UI) — Phase 6
- Backend `/api/images/similar` endpoint — Phase 6

</domain>

<decisions>
## Implementation Decisions

### Chat Panel Placement
- **D-01:** The chat search UI lives at a new **`/search` route** — a full dedicated page, not a tab or overlay. A "Search" nav item is added to the Layout header alongside Insights, Images, Analytics, Identity, Processing.
- **D-02:** Page layout: conversation thread left column (~40%), results grid right column (~60%). This is the canonical split for Phase 5; no other page uses this layout.

### Image Embedding Model
- **D-03:** Use **`sentence-transformers` CLIP variant** — specifically `clip-ViT-B-32` (or equivalent from the sentence-transformers hub). Same library already in `requirements.txt` from Phase 3; no new dependency. Offline, model cached in `~/.cache/torch`.
- **D-04:** Embedding dim: **512** (ViT-B/32). Store with `model_id = "clip-ViT-B-32"` and `dim = 512` in the image embeddings table (separate from the 768-dim text embedding table from Phase 3).
- **D-05:** The shared text+image vector space means the chat panel can encode a text query with the CLIP text encoder and retrieve visually matching images — no extra infrastructure needed. This is the primary motivation for this model choice over `open_clip`.

### Search Routing in Chat
- **D-06:** **NL-first cascade**: every chat message hits the Phase 2 NL filter endpoint (`POST /api/images/nl-search`) first. If the LLM extracts structured filters (dates, scores, posted status, keywords), run a catalog query with those filters. If no filters are extracted (or the query is abstract/semantic), fall through to Phase 3 hybrid semantic search (`POST /api/images/semantic-search`).
- **D-07:** The cascade decision is made server-side in the `/search` chat endpoint handler — the frontend sends a single request and receives results regardless of which path ran. The response includes a `search_mode` metadata field (`"nl_filter"` or `"semantic"`) so the frontend can surface it if useful.

### Result Refinement / Multi-turn Context
- **D-08:** **True multi-turn context**: each new message is sent to the backend with the full conversation history (prior user messages + prior assistant responses). The LLM in the Phase 2 NL path sees prior turns and can interpret references like "those," "now narrow to landscape," or "add more from last month."
- **D-09:** Conversation history is stored **client-side** in React state (array of `{role, content, results}` turns). It is sent as a `messages` array in the chat request payload. No server-side session storage.
- **D-10:** Each turn's result set fully replaces the grid — the conversation history in the left panel shows what the previous queries returned (thumbnail strip or count), but the right panel always shows the current turn's results.

### Claude's Discretion
- Exact sqlite-vec table name for image embeddings (e.g., `image_embeddings_clip` or a single `image_vector_embeddings` table keyed by `(image_key, model_id)`)
- Whether the CLIP text encoder path (text query → CLIP text embedding → KNN) is wired in Phase 5 or deferred to Phase 6
- Exact API route for the chat search endpoint (e.g., `POST /api/images/chat-search` or `POST /api/search/chat`)
- How conversation history is serialized in the request (OpenAI-style `messages` array or a simpler `history` field)
- Empty, loading, and error state copy and visual treatment in the chat panel

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — SIM-01 and NLS-05 definitions; NLS-06 dependency note (pin comes in Phase 7, not here)

### Roadmap
- `.planning/ROADMAP.md` §Phase 5 — success criteria (4 items); build order note referencing Phase 1–3 search stack

### Prior phase context (MUST read — decisions build on these)
- `.planning/phases/03-semantic-search-and-results/03-CONTEXT.md` — D-01 (sqlite-vec), D-02/D-03 (all-mpnet-base-v2 768-dim text embeddings), D-04 (sentence-transformers exception to ProviderRegistry), D-05/D-06 (batch_text_embed job pattern), D-07/D-08 (RRF hybrid), D-09 (degradation: exclude unembedded), D-10/D-11 (why_matched string)
- `.planning/phases/04-stack-detection/04-CONTEXT.md` — D-01 (job registration pattern), D-04/D-05 (incremental + force rebuild semantics), D-10/D-11 (job lifecycle and result payload shape)

### Codebase — backend
- `lightroom_tagger/core/database.py` — `init_database` (where CLIP extension load follows same pattern as sqlite-vec text load), `query_catalog_images` (used after NL filter extraction)
- `apps/visualizer/backend/library_db.py` — `JOB_TYPES_REQUIRING_CATALOG` (add `batch_embed_image`)
- `apps/visualizer/backend/api/jobs.py` — `create_new_job` (job creation + progress pattern)
- `apps/visualizer/backend/api/images.py` — `POST /api/images/nl-search` (Phase 2 NL filter endpoint — cascade start), `POST /api/images/semantic-search` (Phase 3 semantic endpoint — cascade fallback)

### Codebase — frontend
- `apps/visualizer/frontend/src/components/Layout.tsx` — nav items array (add "Search" → `/search`)
- `apps/visualizer/frontend/src/App.tsx` — Routes (add `/search` route)
- `apps/visualizer/frontend/src/pages/ImagesPage.tsx` — reference for page + tab pattern (Phase 5 does NOT use tabs — full split layout instead)
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — reference for results grid rendering patterns

### External
- `sentence-transformers` CLIP models: https://www.sbert.net/docs/pretrained_models.html#image-text-models — `clip-ViT-B-32` and variants

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sqlite-vec` extension: already loaded in `database.py` from Phase 3 — image embedding table creation follows same migration pattern
- `sentence-transformers` library: already in `requirements.txt` — add CLIP model usage alongside existing `all-mpnet-base-v2` text encoder
- Batch job infrastructure: `batch_text_embed` (Phase 3) and `batch_stack_detect` (Phase 4) both implement checkpointing, cancellation, and progress reporting — `batch_embed_image` should follow the same shape exactly
- `CatalogTab.tsx`: image grid rendering logic — the `/search` results grid can reuse the same grid component or a simplified variant
- `Tabs` + `Tab` components: available but not used in `/search` page (split layout, not tab layout)

### Established Patterns
- Jobs: registered in `JOB_TYPES_REQUIRING_CATALOG`, triggered via `POST /api/jobs`, progress via existing job progress mechanism, result payload is a dict of counts
- Frontend pages: `ErrorBoundary` wraps each route in `App.tsx`; pages use `Suspense` + `SkeletonGrid` for loading states
- Nav: `Layout.tsx` navItems array — adding an entry here + a Route in `App.tsx` is the full addition needed

### Integration Points
- `Layout.tsx`: add `{ to: '/search', label: 'Search' }` to navItems
- `App.tsx`: add `<Route path="search" element={<ErrorBoundary><SearchPage /></ErrorBoundary>} />`
- `database.py`: new `_migrate_image_embeddings_clip` step in `init_database` for the vec0 table
- `library_db.py`: add `"batch_embed_image"` to `JOB_TYPES_REQUIRING_CATALOG`
- New backend route: `POST /api/images/chat-search` (or `/api/search/chat`) — orchestrates the NL-first cascade and accepts `messages` history array

</code_context>

<specifics>
## Specific Ideas

- User explicitly chose **`sentence-transformers` CLIP** over `open_clip` specifically because text+image sharing the same vector space enables text→image retrieval in the chat panel
- User wants **true multi-turn LLM context** (not just visual history or client-side narrowing) — the LLM in the NL-first path should receive prior conversation turns so follow-up messages can reference prior results
- The **NL-first cascade** was chosen over semantic-only or parallel hybrid — Phase 2's structured filter extraction should run first; semantic is the fallback for abstract queries
- The `/search` page is a **full dedicated route** with split layout — not a tab, not an overlay; this is a first-class page in the app

</specifics>

<deferred>
## Deferred Ideas

- **CLIP text encoder → KNN image search** (text query → visual results): the model choice (D-03) enables this, but whether to wire the CLIP text encoder path in Phase 5 or Phase 6 is Claude's discretion
- **NLS-06 pin-to-image**: explicitly Phase 7 per roadmap
- **SIM-02 "more like this" UI**: explicitly Phase 6

</deferred>

---

*Phase: 05-image-embed-search-chat*
*Context gathered: 2026-04-24*
