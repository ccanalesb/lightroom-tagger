---
phase: 4.1
title: InstagramTab filter migration
milestone: v2.1
inserted_after: 4
inserted_at: 2026-04-17
requirements:
  - FILTER-02
---

# Phase 4.1 — InstagramTab filter migration (INSERTED)

## Why this phase exists

Phase 4 built the filter framework (`FilterSchema`, `useFilters`, `FilterBar`) and stress-tested it on `CatalogTab`. Phase 4's scope explicitly deferred every other consumer (`InstagramTab`, `MatchesTab`, `DescriptionsTab`, `MatchingTab`, `AnalyticsPage`, `UnpostedCatalogPanel`) to SEED-007's "full rollout" — a later-milestone concern.

User observed that `InstagramTab` still shows its ad-hoc single-select date filter and asked to migrate it inside v2.1 rather than wait for SEED-007. InstagramTab is the smallest consumer (one filter, `date_folder`) — migrating it now:

- Validates the framework against a minimal schema (opposite end of the spectrum from CatalogTab's 11-filter schema).
- Removes one ad-hoc filter implementation from the codebase before Phase 5 touches adjacent Identity/Insights surfaces.
- Does **not** unblock Phase 5 (which only depends on Phase 4 for `DASH-03`'s Top Photos strip).

## Scope

- **In scope:** `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` end-to-end migration onto `useFilters` + `<FilterBar>`; one smoke test.
- **Out of scope:** MatchesTab, DescriptionsTab, MatchingTab, AnalyticsPage, UnpostedCatalogPanel — still SEED-007 full-rollout territory.
- **Out of scope:** URL sync, saved presets (still deferred per Phase 4 `<deferred>`).

## Current state (pre-migration)

`InstagramTab.tsx` has:
- `const [dateFilter, setDateFilter] = useState('')` with `'' = all dates, 'YYYYMM' = that month`
- `handleFilterChange(filter)` → sets state + refetches from offset 0
- `clearFilter()` → resets state + refetches from offset 0
- Inline `<select>` with `availableMonths` + "All dates" option + ad-hoc "Clear" button (`FILTER_CLEAR`, not `FILTER_CLEAR_ALL`)
- Imports `FILTER_ALL_DATES`, `FILTER_CLEAR` from `constants/strings.ts`

API shape: `ImagesAPI.listInstagram({ limit, offset, date_folder?: string })`. Empty filter omits the key entirely.

## Decisions

- **D-1 Schema shape.** Single `select` descriptor with `key: 'dateFolder'`, `paramName: 'date_folder'`, `numberValue: false`, options prepended by `{ value: '', label: FILTER_ALL_DATES }` then `availableMonths.map(m => ({ value: m, label: formatMonth(m) }))`. Memoized with `useMemo` on `[availableMonths]`.
- **D-2 Empty string handling.** The existing `...(filter && { date_folder: filter })` spread maps `''` → key omitted. In `useFilters.toQueryParams`, an empty string is falsy and gets filtered per `descriptorIsActive` → key omitted naturally. No custom `toParam` needed.
- **D-3 Clear copy.** Consistent with CatalogTab: `<FilterBar>` renders `FILTER_CLEAR_ALL` ("Clear all") instead of legacy `FILTER_CLEAR` ("Clear"). Intentional, matches Phase 4 D-17.
- **D-4 Pagination reset.** Legacy behavior: changing the filter refetches from offset 0 (via `fetchImages(0, filter)`). New behavior: a `useEffect` resets `pagination.current_page = 1` (and offset) when the committed `dateFolder` value changes. Match CatalogTab's non-search immediate-reset pattern.
- **D-5 Summary copy.** Keep the existing `{total.toLocaleString()} images total` summary — pass it to `<FilterBar summary={...}>`.
- **D-6 No debounce.** `select` doesn't debounce in the framework; nothing to change.
- **D-7 Test scope.** One smoke test mirroring `CatalogTab.test.tsx`: mock `ImagesAPI.listInstagram` + `getInstagramMonths`, assert the date-filter label renders and `listInstagram` is called with `{ limit, offset: 0 }` and no `date_folder` at baseline.
- **D-8 Prop surface.** InstagramTab currently takes no props (`export function InstagramTab()`). No prop changes.

## Acceptance criteria

1. `rg -n "useState.*dateFilter|handleFilterChange|clearFilter" apps/visualizer/frontend/src/components/images/InstagramTab.tsx` → 0 lines
2. `rg -n "useFilters\(" apps/visualizer/frontend/src/components/images/InstagramTab.tsx` → 1 line
3. `rg -n "<FilterBar" apps/visualizer/frontend/src/components/images/InstagramTab.tsx` → 1 line
4. `cd apps/visualizer/frontend && npx vitest run src/components/images/__tests__/InstagramTab.test.tsx` → exit 0
5. `cd apps/visualizer/frontend && npm run lint && npx tsc --noEmit` → both exit 0
6. Full frontend suite `npx vitest run` → no regressions

## Success criteria (roadmap-level)

1. InstagramTab's date filter uses `FilterSchema` + `useFilters` + `<FilterBar>` with zero ad-hoc `useState`/handler code paths for filter state.
2. Query-param parity: `listInstagram` still receives `date_folder: 'YYYYMM'` when a month is picked, and the key is absent when the filter is cleared.
3. No regression to the existing pagination, modal, or skeleton behavior.
