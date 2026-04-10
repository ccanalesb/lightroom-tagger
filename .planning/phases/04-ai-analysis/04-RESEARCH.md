# Phase 4: AI Analysis — Research

Research for planners: what already exists, where to plug in, conventions, gaps, risks, and ordering. Grounded in `04-CONTEXT.md` user decisions and verified against the repo (2026-04-10).

## Existing Infrastructure

### Core library (Python)

- **`lightroom_tagger/core/analyzer.py`** — `describe_image`, structured JSON (summary, composition, perspectives, technical, subjects, `best_perspective`); used by description pipeline.
- **`lightroom_tagger/core/description_service.py`** — `describe_matched_image(db, catalog_key, force=False, provider_id=None, model=None, log_callback=None) -> bool`; `describe_instagram_image(...)` — skips when `get_image_description` exists unless `force`; resolves paths; calls `describe_image`; persists via `store_image_description`.
- **`lightroom_tagger/core/vision_client.py`** — OpenAI-compatible client; `generate_description` / `compare_images`; errors mapped via `_map_openai_error` into `provider_errors`.
- **`lightroom_tagger/core/provider_registry.py`** — `ProviderRegistry`: `list_providers()`, `list_models(provider_id)`, `get_client(provider_id)`, `fallback_order`, `defaults` property, `update_defaults` (allowed keys: `vision_comparison`, `description` only).
- **`lightroom_tagger/core/provider_errors.py`** — `ProviderError` hierarchy; used by Flask `descriptions` routes (429/401/503 mapping).
- **`lightroom_tagger/core/fallback.py`** — `FallbackDispatcher` for retry + multi-provider cascade (used from vision/describe paths per architecture docs).

### Database (`lightroom_tagger/core/database.py`)

- **`image_descriptions`** — `image_key TEXT PRIMARY KEY`, `image_type`, JSON-ish text columns for structured fields, `best_perspective`, `model_used`, `described_at`. Index `idx_desc_image_type` on `image_type`.
- **`store_image_description(db, record)`** — upsert by `image_key`.
- **`get_image_description(db, image_key)`** — single row by key only (no `image_type` filter; consistent with PK).
- **`get_undescribed_catalog_images(db, months=None)`** / **`get_undescribed_instagram_images`** — LEFT JOIN pattern for “no row in `image_descriptions`” (batch job uses these when `force` is false).
- **`query_catalog_images(db, *, posted, month, keyword, min_rating, date_from, date_to, color_label, limit, offset)`** — returns `(rows, total)`; **no** `analyzed` filter or description fields today.
- **`get_all_images_with_descriptions`** — powers `GET /api/descriptions/`.

### Visualizer API (Flask)

- **`apps/visualizer/backend/api/descriptions.py`** — `GET /`, `GET /<image_key>`, `POST /<image_key>/generate` — body: `image_type` (`catalog` | `instagram`), `force`, optional `model`, `provider_id`, `provider_model`; mutates `DESCRIPTION_VISION_MODEL` env when legacy `model` without `provider_id`.
- **`apps/visualizer/backend/api/providers.py`** — `GET/PUT /providers/defaults`, `GET/PUT /providers/fallback-order`, model CRUD; **no** dedicated “ping” or health route today.
- **`apps/visualizer/backend/api/images.py`** — `GET /catalog` calls `query_catalog_images` with `posted`, `month`, `keyword`, `min_rating`, `date_from`, `date_to`, `color_label`.
- **`apps/visualizer/backend/jobs/handlers.py`** — **`handle_batch_describe(runner, job_id, metadata)`** — reads `image_type`, `date_filter` (`all` | `3months` | `6months` only in code), `force`, `provider_id`, `provider_model`, `max_workers`; builds list from SQL or `get_undescribed_*`; parallel path via `ThreadPoolExecutor` + per-worker `init_database`; cooperative cancel; consecutive-failure circuit breaker (10). **`_describe_single_image`** delegates to `describe_matched_image` / `describe_instagram_image`.

### Frontend

- **`apps/visualizer/frontend/src/services/api.ts`** — `ImagesAPI.listCatalog({ posted, month, keyword, min_rating, ... })`; `DescriptionsAPI.get` / `list` / `generate`; `ProvidersAPI.getDefaults` / `updateDefaults`; types `CatalogImage`, `ImageDescription`.
- **`apps/visualizer/frontend/src/components/images/CatalogTab.tsx`** — Debounced filters; **Status** select maps to `posted` query param (IG-06 pattern to mirror for `analyzed`).
- **`apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx`** — Badge row: Posted, rating, Pick only.
- **`apps/visualizer/frontend/src/components/catalog/CatalogImageModal.tsx`** — Metadata + keywords; **no** description UI.
- **`apps/visualizer/frontend/src/components/DescriptionPanel/DescriptionPanel.tsx`** — `DescriptionPanel({ description, compact? })` — null → copy from `DESC_PANEL_NO_DESCRIPTION`.
- **`apps/visualizer/frontend/src/components/DescriptionPanel/CompactView.tsx`** — Summary line + perspective score pill via `descriptionScoreColor`.
- **`apps/visualizer/frontend/src/components/ui/description-atoms/GenerateButton.tsx`** — `GenerateButton({ hasDescription, generating, onClick })`.
- **`apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx`** — Batch launcher: `JobsAPI.create('batch_describe', { image_type, date_filter, force, max_workers, provider_id?, provider_model? })`.
- **`apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx`** + **`ProviderCard.tsx`** — Card list; header shows `Badge` from static `provider.available` (registry/env), not a live connection test.
- **`apps/visualizer/frontend/src/stores/matchOptionsContext.tsx`** — On mount, `ProvidersAPI.getDefaults()` applies **`defaults.vision_comparison`** to `providerId` / `providerModel` only — **`defaults.description` is not applied** to batch UI.

### Tests worth extending

- **`apps/visualizer/backend/tests/test_images_catalog_api.py`** — Pattern for `posted`, `min_rating`; add `analyzed` cases once implemented.
- **`apps/visualizer/backend/tests/test_handlers_batch_describe.py`** — Contract tests for metadata shaping (e.g. future `min_rating`).

## Integration Points

### Backend: catalog list + SQL

1. **`list_catalog_images` in `images.py`** — Parse `analyzed` from query string (`true` / `false` / omit), same tri-state style as `posted`; pass into `query_catalog_images`.
2. **`query_catalog_images` in `database.py`** — Extend signature with `analyzed: bool | None`. Implement with `EXISTS` or `LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog'` and filter `d.image_key IS NULL` / `IS NOT NULL`.
3. **Optional enrichment for grid cards (CONTEXT D-04)** — To avoid N+1 `GET /descriptions/<key>` per thumbnail, extend the catalog SELECT (or a parallel batch endpoint) with `summary`, `best_perspective`, and maybe a minimal `perspectives` JSON for the score pill — planner should choose: **(A)** extra columns on `GET /images/catalog` via JOIN, or **(B)** separate batched API for visible keys only.

### Backend: batch describe

1. **`handle_batch_describe`** — After building candidate keys, apply **`min_rating`** from metadata (filter catalog rows by `images.rating >= min_rating` — align with catalog’s `min_rating` semantics). Instagram-only rows may ignore rating unless product wants dump-side metadata (not in current `images` table for IG files — clarify: rating filter likely **catalog-only**).
2. **`date_filter`** — UI offers **`12months`** in `DescriptionsTab`, but handler only maps `3months` and `6months`; `months` becomes `None` for `12months` → **currently behaves like “all dates”** for the month window. Phase should fix mapping (e.g. `{'3months': 3, '6months': 6, '12months': 12}`) and ensure SQL `date('now', '-N months')` paths in both `force` and `get_undescribed_*` branches stay consistent.

### Backend: provider validation (AI-01)

- **No existing route** for “test this provider.” Options: new `GET /api/providers/<id>/health` or `POST .../test` that performs a lightweight probe (model list HTTP call vs minimal completion). **`ProviderRegistry`** already has discovery / availability logic (`_is_available`); distinguish **configured vs reachable** per CONTEXT (success/error badges).

### Frontend: catalog UX

1. **`CatalogImage` interface and `ImagesAPI.listCatalog`** — Add `analyzed?` filter param; extend response type if server adds description snippets.
2. **`CatalogImageCard`** — Accept optional description summary / best perspective for pill; show `Badge variant="accent"` “AI” when analyzed (CONTEXT D-07).
3. **`CatalogImageModal`** — Fetch `DescriptionsAPI.get(image.key)` on open (or use embedded catalog fields); render `DescriptionPanel` below keywords; wire `GenerateButton` + `DescriptionsAPI.generate(image.key, 'catalog', ...)` with loading state; consider `useMatchOptions` or **description defaults** for provider/model.

### Frontend: Processing batch panel

- **`DescriptionsTab`** — Add min rating control; pass `min_rating` in job metadata; optionally load **`defaults.description`** for `ProviderModelSelect` initial values (or document that advanced options still use shared `matchOptions` but seeded from description defaults).

## Patterns & Conventions

- **Catalog filters** — Query params on `GET /api/images/catalog`, mirrored in `ImagesAPI.listCatalog` and `CatalogTab` select + `clearFilters` / `hasActiveFilters` (see `posted` implementation and comment referencing IG-06).
- **Badge row** — `CatalogImageCard` uses `flex-wrap` + `Badge`; match spacing and variants per `DESIGN.md` / CONTEXT (whisper-weight).
- **Jobs** — `JobsAPI.create('batch_describe', metadata)`; metadata keys snake_case; handler reads from `metadata` dict.
- **DB access in routes** — `@with_db` + `utils.db` for library connection on image/description routes; jobs open `init_database` with `LIBRARY_DB` / config `db_path`.
- **Provider errors** — HTTP mapping already in `generate_description` route; reuse patterns for any new provider probe endpoint.
- **Tests** — Backend integration tests under `apps/visualizer/backend/tests/`; frontend Vitest in `__tests__` / component tests.

## Gap Analysis

| Area | Requirement IDs | Gap |
|------|-----------------|-----|
| Provider UX + validation | AI-01 | Connection test badges on `ProviderCard`; possible new API; CONTEXT says wire **defaults** — `defaults.description` not surfaced in Providers UI; batch/matching context only loads `vision_comparison`. |
| On-demand single describe | AI-02 | Endpoint exists; **catalog modal** lacks generate + panel. |
| Batch describe scope | AI-03 | Job exists; add **min_rating** in UI + handler; fix **12months** date window; “unanalyzed only” already default when `force` false. |
| Durable storage | AI-04 | Already `image_descriptions` + service layer; no change strictly required unless schema additions. |
| View alongside photos | AI-05 | Descriptions page exists; **catalog grid/modal** missing in-context viewing per CONTEXT. |
| Analyzed vs not | AI-06 | **`analyzed` filter** end-to-end (DB query, API, `ImagesAPI`, `CatalogTab`); badges on card/modal; optional stats (`GET /api/stats`) extension if product wants dashboard counts (not strictly required by CONTEXT). |

**Files likely touched (indicative):** `lightroom_tagger/core/database.py`, `apps/visualizer/backend/api/images.py`, `apps/visualizer/backend/jobs/handlers.py`, `apps/visualizer/frontend/src/services/api.ts`, `apps/visualizer/frontend/src/components/images/CatalogTab.tsx`, `apps/visualizer/frontend/src/components/catalog/CatalogImageCard.tsx`, `apps/visualizer/frontend/src/components/catalog/CatalogImageModal.tsx`, `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx`, `apps/visualizer/frontend/src/components/providers/ProviderCard.tsx`, `apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx` (or new small component), possibly new `api/providers.py` route.

## Risk Areas

1. **Catalog + descriptions JOIN** — Large catalogs: ensure filtered queries stay indexed (`image_descriptions.image_key` is PK — good for join by key).
2. **Parallel `batch_describe`** — Workers use separate connections; safe for SQLite WAL in typical single-writer patterns; watch lock contention if other jobs write heavily.
3. **Provider health probes** — Risk of false negatives (firewall, slow Ollama), rate limits, and user annoyance if probed too often; define when to run (on demand vs on card expand vs periodic).
4. **`get_image_description` and PK** — One row per `image_key` globally; if catalog and Instagram keys ever collided, behavior would be wrong — low probability but inherent to schema.
5. **`GenerateButton` styling** — Uses gray/indigo utility classes; catalog modal uses design tokens elsewhere — planner may want token alignment for visual consistency.
6. **Env mutation in `generate_description`** — `DESCRIPTION_VISION_MODEL` set/cleared in route; batch handler uses `provider_id` / `provider_model` on describe calls — keep plans consistent to avoid env races under concurrent requests.

## Dependencies & Ordering

1. **Database + catalog API** — Implement `analyzed` filter in `query_catalog_images` and wire `GET /api/images/catalog` before or in parallel with frontend filter control; add/extend `test_images_catalog_api.py`.
2. **Catalog list payload for cards** — If cards need score pill without extra round-trips, define server fields **before** `CatalogImageCard` work (or accept explicit `DescriptionsAPI.list` batching as follow-up).
3. **Catalog modal** — Depends on ability to load description (`DescriptionsAPI.get` or enriched catalog row) + generate endpoint (already stable).
4. **Batch min_rating + 12months** — Backend handler + `DescriptionsTab` metadata should ship together; update handler tests.
5. **Provider connection badges** — Depends on chosen probe mechanism (registry method vs new route); frontend badges last.
6. **Defaults for description** — Can be done independently: extend `MatchOptionsProvider` or Descriptions-specific hook to read `defaults.description`; optionally add UI on `ProvidersTab` to edit defaults (PUT already exists).

**Natural workstreams:** (A) Catalog analyzed filter + optional JOIN fields; (B) Catalog modal description + generate; (C) Batch scoping fixes + min rating; (D) Provider health + defaults UX.

## Technical Notes

- **CONTEXT D-10** — “Unanalyzed only” is already **`force=False`** path using `get_undescribed_*`; no new flag unless product adds an explicit toggle.
- **CONTEXT D-11** — Rating filter for batch: mirror **`min_rating`** on catalog API for familiarity; handler must apply to catalog portion of `images_to_describe` when `image_type` is `catalog` or `both`.
- **Single-photo generate** — `POST /api/descriptions/<path:image_key>/generate` with `image_type: 'catalog'` already calls `describe_matched_image` with `provider_id` / `provider_model`.
- **Regression to catch** — `DescriptionsTab` `DateFilter` type includes `'12months'` but backend `months = {'3months': 3, '6months': 6}.get(date_filter)` leaves `12months` without a bounded window today.

## RESEARCH COMPLETE
