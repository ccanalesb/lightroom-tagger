---
plan: 04
status: complete
wave: 3
completed: 2026-04-17
commits: 3
self_check: passed
requirements:
  - FILTER-01
  - FILTER-02
depends_on: [02, 03]
---

# Plan 04-04 Summary — CatalogTab big-bang migration onto FilterSchema + useFilters + FilterBar

## What was built

CatalogTab.tsx's eleven ad-hoc filter `useState` hooks and ten `handle*` / `clearFilters` handlers are gone. A single `useMemo`d `catalogSchema: FilterSchema` drives a `useFilters(catalogSchema)` hook and one `<FilterBar schema={catalogSchema} filters={filters} summary={...} disabled={loading} />`.

- **Schema:** `posted`, `analyzed` (toggles with explicit `serialize`/`deserialize` for `all/posted/not-posted` + `all/analyzed/not_analyzed`), `month`, `keyword` (debounced 350ms), `minRating` (`numberValue`), `dateRange`, `colorLabel` (debounced 350ms), `scorePerspective` (with `className: 'min-w-[8rem]'` per D-18/plan-03), `minCatalogScore` + `sortByScore` (both `enabledBy: 'scorePerspective'` per D-03, the latter with `toParam` that drops `'none'`).
- **`loadImages`:** spreads `filters.toQueryParams()` into the `ImagesAPI.listCatalog` call; `useCallback` deps are `[page, toQueryParams]` so stable identity from the hook short-circuits churn.
- **Pagination reset (D-10):** a first `useEffect` resets `page → 1` when any non-search committed value changes (including `dateRange.from`/`.to`); a second `useEffect` with `useRef` previous-value tracking resets page when *committed* `keyword` / `colorLabel` flip (parity with legacy lines 255–264 debounce-driven reset).
- **`onPostedFilterChange` (D-21):** prop preserved; fires via `useEffect` on `filters.values.posted`.
- **Deep link (`image_key`) + month/perspective fetches:** copied verbatim — no refactor.
- **Clear-button copy:** legacy `FILTER_CLEAR` replaced by `<FilterBar>`'s `FILTER_CLEAR_ALL` (intentional per D-17).
- **Strings:** all catalog-filter copy (labels, option labels, placeholders, aria) extracted to `constants/strings.ts`.
- **Smoke test:** `CatalogTab.test.tsx` mocks `ImagesAPI` + `PerspectivesAPI`, renders inside `MemoryRouter`, asserts `CATALOG_FILTER_LABEL_KEYWORD` is rendered and `listCatalog` is called with `{ limit: 50, offset: 0 }` and no filter keys when schema defaults are in effect.

## Key files

### Created
- `apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx`

### Modified
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` (~298 insertions / 345 deletions — net simplification)
- `apps/visualizer/frontend/src/constants/strings.ts` (+33 lines; catalog-filter labels, options, placeholders, aria)

## Decisions applied

- **D-18 / plan-03 ownership:** `FilterBar` takes a `filters: UseFiltersReturn` prop; the tab owns the hook call. That keeps `CatalogTab.tsx` the sole place that wires schema ↔ state ↔ API.
- **D-19 big-bang:** no interim branch — the legacy filter block is deleted in the same commit that introduces `<FilterBar>`.
- **D-20 smoke-only test bar:** a single RTL render + API-call assertion; detailed semantics already covered by `useFilters` + `FilterBar` tests in plans 02 / 03.
- **D-10 pagination parity:** kept both reset paths — immediate on non-search changes, debounced on search — to match the legacy behavior users already rely on.
- **D-21 prop contract:** `onPostedFilterChange` stays a prop (not moved to context) so callers outside this phase are unaffected.

## Verification

- `npx vitest run src/hooks/__tests__/useDebouncedValue.test.ts src/hooks/__tests__/useFilters.test.ts src/components/filters/__tests__/FilterBar.test.tsx src/components/images/__tests__/CatalogTab.test.tsx` → 4 files, 13 tests, all pass.
- `npx tsc --noEmit` → clean.
- `npm run lint` → clean (`--max-warnings 0`).
- Full frontend sweep: `npx vitest run` → 25 files, 134 tests pass.

## Commits

- `feat(4-04): extend strings.ts with catalog filter labels/placeholders`
- `feat(4-04): migrate CatalogTab to FilterSchema + useFilters + FilterBar`
- `test(4-04): CatalogTab smoke test — labels render, listCatalog baseline`
