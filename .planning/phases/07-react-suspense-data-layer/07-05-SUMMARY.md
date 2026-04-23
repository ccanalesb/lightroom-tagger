---
phase: 7
plan: 05
slug: migrate-analytics-dashboard
status: complete
completed: 2026-04-23
key-files:
  modified:
    - apps/visualizer/frontend/src/pages/AnalyticsPage.tsx
    - apps/visualizer/frontend/src/pages/DashboardPage.tsx
    - apps/visualizer/frontend/src/pages/DashboardPage.test.tsx
    - apps/visualizer/frontend/src/components/analytics/UnpostedCatalogPanel.tsx
    - apps/visualizer/frontend/src/components/analytics/UnpostedCatalogPanel.test.tsx
    - apps/visualizer/frontend/src/components/catalog/ImageScoresPanel.tsx
    - apps/visualizer/frontend/src/hooks/useProviders.ts
  examined_no_change:
    - apps/visualizer/frontend/src/hooks/useSingleMatch.ts
---

# Plan 05 Summary — Migrate Analytics/Dashboard

## What was built

Migrated analytics, dashboard, unposted catalog, provider hooks, and image scores UI to the shared `useQuery` cache + Suspense pattern. Per-request error handling for analytics and dashboard is preserved via `Promise.allSettled` inside fetchers that always resolve (so `useQuery` suspends once per key, then charts still show field-level errors). `useProviders` / `useProviderModels` now read through `useQuery` with `invalidateAll(['providers.list'])` + a small revision bump so `refresh` / `updateFallbackOrder` still trigger refetches. **`useSingleMatch` was not changed**: it has no mount-time data fetch—only job polling and lifecycle resets (see below).

## Components migrated

- `useProviders`, `useProviderModels` — parallel `list` + `getFallbackOrder` for the hook bundle; models keyed by `providerId` (empty id resolves to `[]` without a network call).
- `AnalyticsPage` — `AnalyticsCharts` + `AnalyticsTimezoneFooter` share one cache key; `UnpostedCatalogPanel` sits outside the chart Suspense subtree so its local state is not torn down when the analytics key changes.
- `DashboardPage` — single `fetchDashboardBundle` keyed by posting range (`['dashboard', from, to]`).
- `UnpostedCatalogPanel` — `fetchUnpostedPanelData` combines `getCatalogMonths` + `getUnpostedCatalog` under `['analytics','unposted', …]`; wrapped in data `ErrorBoundary` + `Suspense`.
- `ImageScoresPanel` — `ScoresAPI.getCurrent` via `useQuery`; lazy history fetch remains `useEffect` + callbacks.

## Remaining useEffect inventory

Non-fetch / intentional effects (grep over `src/`, excluding tests):

| Area | Purpose |
|------|--------|
| `ThemeContext` | Theme / document class sync |
| `useCandidateKeyboardNav`, `useFocusTrap`, `useBodyScrollLock`, `Modal` | Focus, scroll lock, a11y |
| `ProviderModelSelect` | Keep selected model valid when model list changes |
| `BestPhotosGrid`, `PostNextSuggestionsPanel`, `InstagramTab`, `CatalogTab`, settings panels | Filter URL sync, debounced list loads, local UI state (some already migrated in earlier phases; remaining effects are not simple `useQuery` replacements) |
| `AnalyzeTab`, `ProvidersTab`, `PerspectivesTab`, `JobQueueTab`, `JobsHealthBanner` | Derived state from query results, polling, health |
| `AIDescriptionSection` | Sync description state from query payload |
| `JobDetailModal`, `ImageDetailModal` | Modal lifecycle, fetch coordination, sockets |
| `ImageScoresPanel` | Reset expanded/history when image or `reloadToken` changes; load history when a row expands |
| `useFilters` | URL ↔ filter sync |
| `useJobSocket` | WebSocket connection |
| `useDebouncedValue` | Timer |
| `useSingleMatch` | Reset on `imageKey`; `setInterval` polling for job status |
| `ImagesPage` | Tab local state |

No remaining **mount-only fetch** `useEffect` blocks were left behind in the files targeted by this plan.

## Verification

- `npx tsc --noEmit`: PASS
- `npx vitest run`: PASS (245 tests)

## Self-Check: PASSED
