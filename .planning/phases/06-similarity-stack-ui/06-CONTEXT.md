# Phase 6: Similarity & Stack UI - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the visible v3.0 Phase 6 surfaces for **SIM-02** and **STACK-03**:

- A CLIP-based "More like this" path from catalog photos that returns visually similar catalog results without mixing embedding models or dimensions.
- Stack representative display in Catalog and Best Photos with a member-count badge and a way to browse stack members without breaking existing card/grid patterns.

This phase may add small reusable plumbing that naturally supports Phase 7 chat pinning and stack-aware matching, but it must not implement those future features.

</domain>

<decisions>
## Implementation Decisions

### Phase 7 Handoff
- **D-01:** Build the visible Phase 6 features first: stack display/expansion and catalog-photo visual similarity.
- **D-02:** Include small reusable plumbing only when it naturally falls out of Phase 6 work. Examples: shared similar-image API response types, frontend helper functions used by Catalog now and reusable by SearchPage later, and generic stack metadata fields that future matching can consume.
- **D-03:** Do not add speculative Phase 7 behavior in Phase 6. No chat pin UI, no split/merge/change-representative controls, and no Instagram matching behavior.
- **D-04:** Future handoff should stay generic. Prefer data shapes like `stack_id`, `stack_member_count`, `is_stack_representative`, and similar-image result metadata over matching-specific or chat-specific branches unless they are already needed by the visible Phase 6 UI.

### Carry-Forward Decisions
- **D-05:** Visual similarity must use the Phase 5 CLIP image embedding space (`image_clip_embeddings`, 512 dim, `clip-ViT-B-32`) and must not mix with Phase 3 text embeddings (`image_text_embeddings`, 768 dim).
- **D-06:** Stack UI builds on Phase 4 burst stacks only. pHash near-duplicate clustering was dropped and should not re-enter Phase 6 scope.
- **D-07:** Stack representatives come from Phase 4's representative selection contract; Phase 6 displays and navigates existing stack data rather than redefining how representatives are chosen.

### Claude's Discretion
- Exact placement of the visible "More like this" control on catalog cards/detail surfaces.
- Exact member expansion UI for stack browsing, as long as Catalog and Best Photos stay consistent with existing `ImageTile` and grid/card patterns.
- Whether the reusable frontend similarity helper is a hook, service method, or local callback, as long as it is used by Phase 6 and simple for Phase 7 to reuse.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/ROADMAP.md` — v3.0 Phase 6 scope: SIM-02 and STACK-03.
- `.planning/REQUIREMENTS.md` — SIM-02 and STACK-03 definitions plus dependencies on SIM-01 and STACK-01.
- `.planning/PROJECT.md` — v3.0 Intelligent Discovery goal and project constraints.

### Prior Phase Context
- `.planning/phases/04-stack-detection/04-CONTEXT.md` — stack schema, representative selection, and pHash descoping decisions.
- `.planning/phases/05-image-embed-search-chat/05-CONTEXT.md` — CLIP embedding model decisions and Phase 5/6/7 boundary.
- `.planning/phases/05.2-tool-calling-search/05.2-PLAN.md` — chat search tool-calling architecture and multi-turn history shape for future pin handoff awareness.

### Backend Integration Points
- `lightroom_tagger/core/database.py` — `image_clip_embeddings`, `image_stacks`, `image_stack_members`, catalog query helpers, and migration patterns.
- `lightroom_tagger/core/clip_embedding_service.py` — CLIP model constants and vector serialization helpers.
- `apps/visualizer/backend/api/images.py` — existing image search and chat search API routes; likely home for similar-image endpoint.
- `apps/visualizer/backend/api/identity.py` — Best Photos API surface that will need stack metadata.
- `apps/visualizer/backend/jobs/handlers.py` — `batch_embed_image` and `batch_stack_detect` implementations that produce Phase 6 source data.

### Frontend Integration Points
- `apps/visualizer/frontend/src/services/api.ts` — central API client and response types.
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — catalog grid and image-detail integration.
- `apps/visualizer/frontend/src/components/image-view/ImageTile.tsx` — shared tile shell, overlay badge slot, footer slot.
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx` — Best Photos stack representative/count display.
- `apps/visualizer/frontend/src/pages/SearchPage.tsx` — future chat pin consumer; do not implement pin UI in this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ImageTile` already provides shared thumbnail/card structure, overlay badge support, and footer extension points suitable for stack counts and similarity entry points.
- `ImagesAPI` and `IdentityAPI` in `api.ts` are the existing frontend service boundaries for new response fields and helper calls.
- `image_clip_embeddings` already exists from Phase 5; Phase 6 needs a read/query path for seed-image KNN.
- `image_stacks` and `image_stack_members` already exist from Phase 4; Phase 6 needs read helpers and response serialization for UI consumers.

### Established Patterns
- Search and image endpoints live in `apps/visualizer/backend/api/images.py`; API responses are normalized to frontend-facing image objects before rendering.
- Frontend pages use shared grid/tile components rather than bespoke card shells.
- Job-created data is exposed through read APIs after jobs complete; UI should degrade clearly when embeddings or stacks are missing.

### Integration Points
- Add CLIP similar-image query support without reusing text semantic search helpers that operate on the 768-d text embedding table.
- Add stack metadata to Catalog and Best Photos response paths, or provide focused read endpoints that those surfaces can call without duplicating stack lookup logic.
- Keep SearchPage changes out of scope unless a reusable type/helper is needed and remains invisible to users.

</code_context>

<specifics>
## Specific Ideas

- The user asked for the questions to be simplified; the captured product decision is: build Phase 6's visible features and include only small reusable plumbing if it naturally helps future chat pin or matching work.
- Phase 7 features are intentionally not pulled forward. Phase 6 should make Phase 7 easier, not make Phase 6 larger.

</specifics>

<deferred>
## Deferred Ideas

- Chat pin-to-image UI and behavior — Phase 7 (NLS-06).
- Stack-aware Instagram matching — Phase 7 (STACK-04).
- Split, merge, and change representative controls — Phase 7 (STACK-05).
- pHash near-duplicate stack clustering — dropped from Phase 4 and not reintroduced here.

</deferred>

---

*Phase: 06-similarity-stack-ui*
*Context gathered: 2026-04-25*
