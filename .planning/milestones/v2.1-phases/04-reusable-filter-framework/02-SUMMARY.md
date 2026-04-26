---
plan: 02
status: complete
wave: 2
completed: 2026-04-17
commits: 2
self_check: passed
requirements:
  - FILTER-02
depends_on: [01]
---

# Plan 04-02 Summary — useFilters(schema) hook

## What was built

`apps/visualizer/frontend/src/hooks/useFilters.ts` exposes the D-06 hook surface:

- `values` — committed snapshot (post-debounce for search).
- `rawValues` — immediate state for controlled inputs.
- `setValue(key, value)` / `setValues(patch)` — trigger dependent-clears, route search keys through per-key debounce timers.
- `clearAll()` — reset to schema defaults and cancel pending timers.
- `activeCount` / `isActive(key)` — compute against committed snapshot but use raw-trim for `search` to match legacy CatalogTab behavior.
- `toQueryParams()` — snake_case default names, descriptor `toParam` overrides (supports object-returning descriptors that merge multiple keys), `numberValue` coercion, `dateRange` split `fromParamName` / `toParamName`, search trim + omit-empty.

Module helper `keyToSnakeCase` handles camelCase → snake_case fallback. `applyDependentClears` walks schema until stable, resetting disabled descriptors to `descriptorDefault` (D-11) and cancelling any in-flight debounce for cleared search children.

`hooks/index.ts` exports `useFilters` and `UseFiltersReturn`.

## Key files

### Created
- `apps/visualizer/frontend/src/hooks/useFilters.ts`
- `apps/visualizer/frontend/src/hooks/__tests__/useFilters.test.ts`

### Modified
- `apps/visualizer/frontend/src/hooks/index.ts`

## Self-Check: PASSED

- `npx vitest run src/hooks/__tests__/useFilters.test.ts` — 5/5 tests pass.
- `npx vitest run src/hooks/__tests__/useDebouncedValue.test.ts` — 3/3 (re-run, still green).
- `npx eslint src/hooks/useFilters.ts src/hooks/index.ts src/hooks/__tests__/useFilters.test.ts` — exit 0.
- `npx tsc --noEmit` — exit 0.
- Acceptance grep:
  - `export function useFilters` — 1 match.
  - `export type UseFiltersReturn` — 1 match.
  - `function keyToSnakeCase` — 1 match.
  - `enabledBy` in useFilters.ts — 3 matches.
  - `export { useFilters }` in hooks/index.ts — 1 match.

## Deviations

- Plan text suggested writing per-descriptor "applyDependentClears" in a single pass; implementation uses a bounded fixed-point loop so chained `enabledBy` dependencies resolve correctly in one `setValue` call.
- `descriptorDefault('sortByScore')` was not set in the plan fixture; the test schema sets `defaultValue: 'none'` explicitly so the sort descriptor's "default" is `'none'` (matches CatalogTab). Without that default, `sortByScore === 'none'` would count as non-default and inflate `activeCount`. Same fixture ships into plan 04 when we migrate CatalogTab.
- `activeCount`/`isActive` for search keys intentionally read `rawValues` (not `committedValues`) to preserve `CatalogTab.tsx:266-277` hasActiveFilters semantics.

## Enables next plan

Plan 03 (FilterBar + primitives) can consume `useFilters` to drive controlled descriptor inputs and chip lists. Plan 04 (CatalogTab migration) can replace the `useState` + `useDebouncedValue` + inline-spread query construction with `useFilters(schema).toQueryParams()` and assert snake_case parity against `ImagesAPI.listCatalog`.
