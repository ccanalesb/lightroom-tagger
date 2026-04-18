---
plan: 01
phase: 4.1
status: complete
completed: 2026-04-17
commits: 2
self_check: passed
requirements:
  - FILTER-02
---

# Phase 4.1 / Plan 01 Summary — InstagramTab migration

## What was built

`InstagramTab.tsx` is now a framework consumer. One `useMemo`d `instagramSchema` (single `select` descriptor keyed `dateFolder` → `paramName: 'date_folder'`) drives `useFilters(instagramSchema)` + `<FilterBar>`.

- **Removed:** `dateFilter` `useState`, `handleFilterChange`, `clearFilter`, the inline `<select>` + ad-hoc Clear button block, `FILTER_CLEAR` import.
- **Added:** `useMemo` / `useRef` imports, `useFilters` hook, `FilterBar` + `FilterSchema` imports.
- **`fetchImages`:** spreads `filters.toQueryParams()` into `ImagesAPI.listInstagram`; empty filter → key omitted by the hook's `isActive` gate (D-2).
- **Filter-change reset:** `useRef<boolean>(true)` "first run" guard in a dedicated `useEffect` that watches `filterValues.dateFolder` — post-mount changes trigger `fetchImages(0)`, preserving legacy "filter change → offset 0" behavior without double-firing on initial render.
- **Clear copy:** now `FILTER_CLEAR_ALL` ("Clear all") via `<FilterBar>`, consistent with CatalogTab (D-3).
- **Summary:** `{total.toLocaleString()} images total` passed into `<FilterBar summary={...}>` instead of living in a sibling flex container.
- **Always-rendered filter:** schema is always present now; when `availableMonths` is empty, the only option is "All dates". Minor UX change vs. legacy (which hid the select entirely until months loaded) — acceptable and matches CatalogTab's behavior with an empty month list.

## Key files

### Created
- `apps/visualizer/frontend/src/components/images/__tests__/InstagramTab.test.tsx` (2 smoke tests: baseline `listInstagram` call + Date label renders)

### Modified
- `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` (51 insertions / 46 deletions — net +5 lines; most of the delta is import reshuffling + the first-run guard)

## Decisions applied

- **D-1 schema shape:** single `select` descriptor with manual "All dates" sentinel `value: ''` matching the legacy `date_folder` omission semantics.
- **D-2 empty string:** hook's `descriptorIsActive` already drops empty-string `select` values — no custom `toParam` needed.
- **D-3 Clear copy parity:** inherits `FILTER_CLEAR_ALL` from `<FilterBar>`.
- **D-4 pagination reset:** `useRef` first-run guard + `useEffect` on committed `dateFolder` — pattern borrowed from CatalogTab's debounced-text parity effect but adapted for a non-debounced `select`.
- **D-7 test scope:** RTL smoke only (no `MemoryRouter` needed — InstagramTab doesn't use router hooks); semantic filter behavior already covered by `useFilters` / `FilterBar` tests in Phase 4.

## Verification

- `npx vitest run src/components/images/__tests__/InstagramTab.test.tsx` → 2/2 pass.
- `npx vitest run` (full suite) → 26 files / 136 tests pass (was 25/134 pre-migration; +1 file, +2 tests).
- `npm run lint` → clean (`--max-warnings 0`).
- `npx tsc --noEmit` → clean.

## Commits

- `feat(4.1-01): migrate InstagramTab to FilterSchema + useFilters + FilterBar`
- `test(4.1-01): InstagramTab smoke — Date label + listInstagram baseline`
