# Phase 4: AI Analysis - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Configurable AI providers, on-demand single and batch descriptions, durable storage, in-context viewing alongside photos, and coverage indicators (analyzed vs not). The provider registry, vision client, description service, job handler, and most UI components already exist — this phase closes gaps in provider validation, description surfacing across all photo views, analyzed/unanalyzed filtering, and batch scoping.

</domain>

<decisions>
## Implementation Decisions

### Provider Configuration UX (AI-01)
- **D-01:** Keep the existing card-based provider list (`ProvidersTab`, `ProviderCard`, `ModelList`, `FallbackOrderPanel`) as the configuration UI — no setup wizard.
- **D-02:** Add a connection test/validation indicator per provider. When a provider is configured, show a `Badge variant="success"` (reachable) or `Badge variant="error"` (unreachable) on the provider card. This is the only new UI work for AI-01.
- **D-03:** Provider defaults endpoint (`GET/PUT /api/providers/defaults`) already allows setting default provider+model for description and vision_comparison — wire this into the UI if not already surfaced.

### Description Viewing Experience (AI-02, AI-04, AI-05)
- **D-04:** Descriptions surface in three places at increasing detail levels:
  1. **Catalog grid cards** (`CatalogImageCard`): Small "AI" badge + best-perspective score pill (e.g., "Street 7/10") in the badge row below existing Posted/rating/pick badges. Uses the `CompactView` score format.
  2. **Catalog image modal** (`CatalogImageModal`): Collapsible `DescriptionPanel` (compact by default) in the right-side metadata area, below keywords. If no description exists, show a `GenerateButton` to trigger on-demand generation.
  3. **Dedicated Descriptions page**: Already built (`DescriptionGrid` + `DescriptionDetailModal` + `DescriptionCard`) — keep as the deep-dive view for browsing and managing all descriptions.
- **D-05:** The `DescriptionPanel` component already supports `compact` and full modes — reuse directly in the catalog modal.
- **D-06:** On-demand single-image describe from the catalog modal uses the existing `POST /api/descriptions/<key>/generate` endpoint.

### Analyzed vs Not-Analyzed Indicators (AI-06)
- **D-07:** Badge-based indicators using `Badge variant="accent"` showing "AI" (or "AI Analyzed") on `CatalogImageCard` and `CatalogImageModal` when a description exists for that image.
- **D-08:** Add an `analyzed` filter to the catalog filter bar (true/false/all) so users can filter to unanalyzed photos. This parallels the existing `posted` filter pattern — same UI control style, same API query param approach (`GET /api/images/catalog?analyzed=true|false`).

### Batch Job Scoping (AI-03)
- **D-09:** Extend the existing `DescriptionsTab` batch panel — no new multi-select grid UX. Batch scoping stays filter-based.
- **D-10:** Batch describe defaults to "unanalyzed only" (skip images that already have descriptions). The existing `force` checkbox overrides this to regenerate all.
- **D-11:** Add a minimum rating filter to batch scoping (e.g., "3+ stars only") so users can prioritize their best-rated work for AI analysis. Mirrors the catalog rating filter from Phase 1.

### Claude's Discretion
- Exact placement and sizing of the AI badge/score pill on catalog cards (as long as it follows the badge row pattern)
- Whether the catalog modal description panel starts collapsed or expanded
- Connection test implementation (ping endpoint vs model list probe)
- "Unanalyzed only" default toggle vs implicit behavior in the batch handler
- How the rating filter integrates into the existing `DescriptionsTab` layout

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design system
- `apps/visualizer/frontend/DESIGN.md` — Color palette, component specs (Badge, Card, Button), typography, spacing, shadow system

### AI/Description infrastructure (backend)
- `lightroom_tagger/core/analyzer.py` — `describe_image`, `DESCRIPTION_PROMPT`, structured JSON output format (summary, composition, perspectives, technical, subjects, best_perspective)
- `lightroom_tagger/core/description_service.py` — `describe_matched_image`, `describe_instagram_image`, storage orchestration
- `lightroom_tagger/core/vision_client.py` — `compare_images`, `generate_description`, OpenAI-compatible client, `_map_openai_error`
- `lightroom_tagger/core/provider_registry.py` — `ProviderRegistry`, `list_providers`, `get_client`, `fallback_order`, `defaults`
- `lightroom_tagger/core/provider_errors.py` — `ProviderError` hierarchy (RateLimitError, AuthenticationError, ConnectionError, ModelUnavailableError)
- `lightroom_tagger/core/fallback.py` — `FallbackDispatcher`, retry + multi-provider cascade

### API endpoints
- `apps/visualizer/backend/api/descriptions.py` — `GET /api/descriptions/`, `GET /api/descriptions/<key>`, `POST /api/descriptions/<key>/generate`
- `apps/visualizer/backend/api/providers.py` — `GET /api/providers/`, `GET/PUT /api/providers/fallback-order`, `GET/PUT /api/providers/defaults`, model CRUD
- `apps/visualizer/backend/api/images.py` — `GET /api/images/catalog` with existing filters (keyword, rating, date, color_label, posted, month)
- `apps/visualizer/backend/jobs/handlers.py` — `handle_batch_describe` with cooperative cancellation, consecutive failure circuit breaker

### Frontend components
- `apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx` — Catalog grid card with badge row
- `apps/visualizer/frontend/src/components/catalog/CatalogImageModal.tsx` — Image detail modal with metadata + keywords
- `apps/visualizer/frontend/src/components/DescriptionPanel/DescriptionPanel.tsx` — Compact/full description display
- `apps/visualizer/frontend/src/components/DescriptionPanel/CompactView.tsx` — Score pill + summary line
- `apps/visualizer/frontend/src/components/DescriptionPanel/FullView.tsx` — Full perspectives, composition, technical sections
- `apps/visualizer/frontend/src/components/ui/description-atoms/GenerateButton.tsx` — On-demand generate trigger
- `apps/visualizer/frontend/src/components/descriptions/DescriptionsTab.tsx` — Batch describe panel (Processing page)
- `apps/visualizer/frontend/src/components/descriptions/BatchActionPanel.tsx` — Date filter, force toggle, batch controls
- `apps/visualizer/frontend/src/components/descriptions/DescriptionGrid.tsx` — Description list with pagination
- `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` — Processing page batch job launcher
- `apps/visualizer/frontend/src/components/providers/ProviderCard.tsx` — Provider card display
- `apps/visualizer/frontend/src/components/providers/ModelList.tsx` — Model list per provider
- `apps/visualizer/frontend/src/components/providers/FallbackOrderPanel.tsx` — Fallback order management

### Database
- `lightroom_tagger/core/database.py` — `store_image_description`, `get_image_description`, `get_all_images_with_descriptions`, image query functions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DescriptionPanel` (compact + full): Drop-in for catalog modal — already handles null/missing descriptions
- `CompactView`: Score pill format reusable for catalog card badges
- `GenerateButton`: On-demand describe trigger, already wired to the generate endpoint
- `Badge` component: `variant="accent"` for AI indicator, `variant="success"`/`variant="error"` for provider status
- `ProviderModelSelect`: Provider+model dropdown combo, used in both matching and descriptions
- `BatchActionPanel`: Date filter + force + job status display, extendable with rating filter
- `descriptionScoreColor` util: Color mapping for perspective scores

### Established Patterns
- Catalog filters: Query params on `GET /api/images/catalog` (keyword, rating, date, color_label, posted) — extend with `analyzed`
- Badge row on cards: `CatalogImageCard` already shows Posted, rating, Pick badges — add AI badge in same row
- Job creation: `JobsAPI.create('batch_describe', metadata)` — extend metadata with rating filter
- `with_db` decorator for Flask route DB access
- `describe_matched_image` / `describe_instagram_image` for single-image generation with force flag

### Integration Points
- `CatalogImageCard.tsx` badge row — add AI badge + score
- `CatalogImageModal.tsx` metadata section — add `DescriptionPanel` + `GenerateButton`
- `GET /api/images/catalog` — add `analyzed` query param to `query_catalog_images`
- `ProviderCard.tsx` — add connection status badge
- `DescriptionsTab.tsx` (Processing) — add rating filter select
- `handle_batch_describe` handler — respect rating filter in metadata, default to unanalyzed-only
- `query_catalog_images` in `database.py` — add analyzed join/filter against descriptions table

</code_context>

<specifics>
## Specific Ideas

- Description viewing follows the design system's warm minimalist approach — whisper-weight badges, not heavy visual indicators
- Score pills use the existing `descriptionScoreColor` utility for consistent color coding
- No setup wizard for providers — the card-based list is sufficient for the target user (single photographer)
- Multi-select from catalog grid for batch describe deferred to v2 — filter-based scoping keeps it simple

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-ai-analysis*
*Context gathered: 2026-04-10*
