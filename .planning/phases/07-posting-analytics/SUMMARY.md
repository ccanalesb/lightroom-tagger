# Phase 07 — Plan 07-01 execution summary

**Date:** 2026-04-12  
**Plan:** 07-01 — Posting analytics SQL layer and REST API

## Delivered

- **`lightroom_tagger/core/posting_analytics.py`** — Shared CTE `posted_dump_media` (validated `matches` × `instagram_dump_media`), `COALESCE(created_at, YYYYMM→month-start UTC)` event time, parameterized SQL only. Helpers: `get_posting_frequency` (day/week/month, zero-filled buckets), `get_posting_time_heatmap` (dow×hour UTC), `get_caption_hashtag_stats` (captions/hashtags/words in Python), `query_unposted_catalog` (thin wrapper over `query_catalog_images` with `posted=False`).
- **`apps/visualizer/backend/api/analytics.py`** — Blueprint `analytics` at `/api/analytics`: `posting-frequency`, `posting-heatmap`, `caption-stats`, `unposted-catalog`. ISO date validation, `_clamp_pagination` from `api.images`, generic `error_server_error()` on unexpected errors.
- **`apps/visualizer/backend/app.py`** — `register_blueprint(analytics.bp, url_prefix='/api/analytics')`.
- **Tests:** `lightroom_tagger/core/test_posting_analytics.py` (fixture DB), `apps/visualizer/backend/tests/test_analytics_api.py` (Flask client, `LIBRARY_DB` monkeypatch).

## Commits (atomic)

1. `feat(07-01): add posting analytics SQL helpers module`
2. `feat(07-01): add posting analytics Flask blueprint`
3. `feat(07-01): register analytics blueprint at /api/analytics`
4. `test(07-01): add posting_analytics SQLite unit tests`
5. `test(07-01): add Flask tests for analytics API routes`
6. `docs(07-01): add phase 07-01 execution summary`

## Verification

- `pytest lightroom_tagger/core/test_posting_analytics.py apps/visualizer/backend/tests/test_analytics_api.py -q`
- `ruff check lightroom_tagger/core/posting_analytics.py apps/visualizer/backend/api/analytics.py`
- `mypy --follow-imports=silent lightroom_tagger/core/posting_analytics.py` (avoids transitive errors from legacy `database.py` typing)

## Notes

- Responses expose **`meta.timezone_assumption` / `timezone_note`** where applicable (POST roadmap / 07-CONTEXT).
- Manual smoke: `curl -sS "http://127.0.0.1:<port>/api/analytics/posting-frequency?date_from=2024-01-01&date_to=2024-01-31"` → JSON with `meta.timezone_assumption`.

---

# Phase 07 — Plan 07-02 execution summary

**Date:** 2026-04-12  
**Plan:** 07-02 — Analytics page: posting timeline, heatmap, and caption/hashtag views

## Delivered

- **`recharts` ^3.8.1** — Added to `apps/visualizer/frontend` (install used `npm install --legacy-peer-deps` due to existing `@testing-library/react` vs React 19 peer conflict).
- **`AnalyticsAPI`** in `src/services/api.ts` — Typed clients for `/api/analytics/posting-frequency`, `posting-heatmap`, and `caption-stats` (required `date_from` / `date_to` aligned with backend).
- **Strings** — `NAV_ANALYTICS`, section titles, empty-state copy, heatmap legend, timezone disclaimer, caption stat labels.
- **Navigation & route** — `Layout` nav item **Analytics**; `App` route `path="analytics"` with `ErrorBoundary`.
- **`PostingFrequencyChart`** — Recharts `AreaChart` / `ResponsiveContainer`, theme CSS variables, loading/error/empty, optional meta line (granularity + timestamp source).
- **`PostingHeatmap`** — 7×24 grid from API `cells`, `meta.dow_labels`, intensity from count/max, `title` tooltips, UTC legend.
- **`CaptionHashtagPanel`** — Summary stats, scrollable top-hashtags table with bar widths; text-only hashtag display (no HTML injection).
- **`AnalyticsPage`** — Default range last 12 months, date inputs + granularity + Apply, parallel fetches with `Promise.allSettled`, per-widget errors, `sr-only` `aria-live` for errors, footer with API `meta` timezone / scope text.

## Commits (atomic; `/analytics` route committed after `AnalyticsPage` so `tsc` stays green between commits)

1. `feat(07-02): add recharts dependency`
2. `feat(07-02): add AnalyticsAPI client and types`
3. `feat(07-02): add analytics navigation and copy strings`
4. `feat(07-02): add Analytics link to main navigation`
5. `feat(07-02): add PostingFrequencyChart with Recharts`
6. `feat(07-02): add PostingHeatmap day-by-hour grid`
7. `feat(07-02): add CaptionHashtagPanel stats and table`
8. `feat(07-02): add Analytics page with date range and fetches`
9. `feat(07-02): register /analytics route`
10. `docs(07-02): append plan 07-02 execution summary`

## Verification

- `npm run build` and `npm run lint` in `apps/visualizer/frontend` (exit 0).
- Manual: open `/analytics`, adjust range and **Apply**, confirm chart/heatmap/caption sections refetch.

## Notes

- **`unposted-catalog`** client left for plan 07-03 (not stubbed in `AnalyticsAPI`).
- Heatmap cells use **`color-mix`** with `var(--color-accent)` for theme-aware intensity; requires a modern browser (same baseline as the rest of the UI).

---

# Phase 07 — Plan 07-03 execution summary

**Date:** 2026-04-12  
**Plan:** 07-03 — Catalog vs posted gap UI (unposted catalog browse, POST-04)

## Delivered

- **`AnalyticsAPI.getUnpostedCatalog`** in `src/services/api.ts` — Typed client for `GET /api/analytics/unposted-catalog` with `date_from`, `date_to`, `min_rating`, `month`, `limit`, `offset`; response matches backend (`total`, `images`, `pagination`).
- **Strings** — `ANALYTICS_NOT_POSTED_*`, help copy, empty states, `IMAGES_OPEN_POSTING_ANALYTICS` for cross-link.
- **`UnpostedCatalogPanel`** — Independent date / min-rating / month filters (Apply updates server query); paginated grid (50/page) reusing `CatalogImageCard` + `CatalogImageModal` via minimal `CatalogImage` stubs from API rows (key, filename, date_taken, rating only); loading/error/empty parity with other analytics sections.
- **`AnalyticsPage`** — Renders `UnpostedCatalogPanel` after captions/hashtags; gap filters stay independent of the main analytics date range.
- **Images → Catalog** — When **Not Posted** is selected, a callout with **`Link` to `/analytics`** appears above the catalog tab; `CatalogTab` reports posted filter via optional `onPostedFilterChange`.
- **Tests** — `UnpostedCatalogPanel.test.tsx` (empty state + one-row grid), mocks `AnalyticsAPI.getUnpostedCatalog` and `ImagesAPI.getCatalogMonths`.

## Commits (atomic)

1. `feat(07-03): add AnalyticsAPI getUnpostedCatalog client`
2. `feat(07-03): add strings for unposted catalog analytics panel`
3. `feat(07-03): add UnpostedCatalogPanel with filters and catalog modal`
4. `feat(07-03): mount UnpostedCatalogPanel on Analytics page`
5. `feat(07-03): link to Analytics when catalog shows not posted filter`
6. `test(07-03): add UnpostedCatalogPanel Vitest coverage`
7. `docs(07-03): append plan 07-03 execution summary`

## Verification

- `npm test -- --run`, `npm run build`, `npm run lint` in `apps/visualizer/frontend` (exit 0).
- Manual: `/analytics` → Not posted section lists `instagram_posted=0` rows; filters and pagination; card opens catalog modal.

## Notes

- Backend returns **`images`**, not `items`; pagination uses **`limit`/`offset`** (aligned with catalog list API).
