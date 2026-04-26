---
phase: 7
plan: 03
slug: migrate-images
status: complete
completed: 2026-04-23
key-files:
  modified:
    - apps/visualizer/frontend/src/pages/ImagesPage.tsx
    - apps/visualizer/frontend/src/components/images/CatalogTab.tsx
    - apps/visualizer/frontend/src/components/images/InstagramTab.tsx
    - apps/visualizer/frontend/src/components/images/MatchesTab.tsx
    - apps/visualizer/frontend/src/components/image-view/ImageDetailModal.tsx
    - apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx
    - apps/visualizer/frontend/src/components/DescriptionPanel/AIDescriptionSection.tsx
    - apps/visualizer/frontend/src/stores/matchOptionsContext.tsx
---

# Plan 03 Summary — Migrate Images page

## What was built

Images-area data loading was moved from ad-hoc `useEffect` + loading/error state to the shared `useQuery` cache with Suspense for loading and `ErrorBoundary` + `ErrorState` at the tab level on `ImagesPage`. Catalog and Instagram list queries use stable serialized params for cache keys. Match groups load via `useQuery` for the first page; “Load more” still uses imperative `MatchingAPI.list` with the existing merge logic extracted to `matchGroupMutations.ts`. `ImageDetailModal` keeps scroll lock and focus trap outside Suspense; detail fetch, inner `ErrorBoundary` for failures, and a fallback that preserves `initialImage` live inside the modal. `AIDescriptionSection` uses `useQuery` for `providers.defaults` (shared key with match options) and per-image descriptions, with `invalidate` on refresh after jobs. `MatchOptionsProvider` wraps an inner impl in `Suspense` and loads defaults via `useQuery`, seeding options in `useLayoutEffect` so dependents (e.g. Matching tab) see provider IDs before interaction.

## Components migrated

| Area | Notes |
|------|--------|
| `CatalogTab` | `useQuery` for months, perspectives, and paginated `listCatalog` with `stableSerializeRecord(listParams)` key. Inline error/loading UI removed; tab-level boundary handles failures. |
| `InstagramTab` | `useQuery` for months + list; local page state drives offset; removed `SkeletonGrid`/`PageError` in favor of tab Suspense. |
| `MatchesTab` | `useQuery(['matching.groups', sortParam])` for first page; `useMatchGroupMutations` + `appendMatchGroupsPage` for validation/reject/load-more. |
| `ImageDetailModal` | `ImageDetailModalBody` + `useQuery`; `invalidate` + bump on `onDataChanged`; inner `ErrorBoundary` + `Suspense` fallback with `initialImage` support. |
| `MatchDetailModal` | **Unchanged** — no list/detail `useEffect` fetch; props-driven only. |
| `AIDescriptionSection` | Outer `Suspense`; inner `useQuery` for defaults + `DescriptionsAPI.get`; `invalidate(['descriptions', imageKey])` on refresh. |
| `matchOptionsContext` | `MatchOptionsProvider` → `Suspense` → `MatchOptionsProviderImpl` with `useQuery(['providers.defaults'])`. |
| `ImagesPage` | Each tab wrapped in `ErrorBoundary` (with `invalidateAll` for that tab’s key prefix) and `Suspense` + `SkeletonGrid`. |

## Verification

- `npx tsc --noEmit`: PASS
- `npx vitest run src/components/images src/components/image-view src/components/matching`: PASS (48 tests)
- `npx vitest run src/pages/__tests__/MatchingPage.test.tsx src/pages/IdentityPage.test.tsx`: PASS (related provider defaults / identity regressions)

## Deviations

- **`InstagramDumpSettingsPanel` / `CatalogSettingsPanel`**: Not migrated; they are settings/config panels, not part of the Images browse tabs.
- **`MatchDetailModal`**: No migration; no fetch lifecycle to replace.
- **Test commit naming**: Catalog/Instagram/ImageDetailModal test updates were committed with their feature commits; `MatchingPage.test.tsx` gained `deleteMatching` in `beforeEach` so `providers.defaults` is not shared across examples (committed separately).

## Self-Check: PASSED
