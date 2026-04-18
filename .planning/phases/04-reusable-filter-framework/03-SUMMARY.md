---
plan: 03
status: complete
wave: 2
completed: 2026-04-17
commits: 4
self_check: passed
requirements:
  - FILTER-01
depends_on: [01, 02]
---

# Plan 04-03 Summary — FilterBar and filter primitives

## What was built

Pure-presenter UI under `components/filters/`:

- **`FilterChip`** — Badge + ghost Button composite with truncation + aria-labelled ✕ (D-16).
- **`styles.ts`** — shared `CONTROL` Tailwind class extracted from CatalogTab for native `<select>` / `<input type="date">`.
- **`ToggleFilter`** — descriptor-driven tri-state `<select>`; default serialize/deserialize maps `undefined ↔ 'all'` / `true ↔ 'true'` / `false ↔ 'false'` but defers to `descriptor.serialize` / `descriptor.deserialize` when provided.
- **`SelectFilter`** — supports `descriptor.className` append and `numberValue` coercion.
- **`DateRangeFilter`** — renders two sibling `COL` blocks for From/To inside the parent ROW so flex-wrap behavior matches legacy markup.
- **`SearchFilter`** — wraps `ui/Input`, controlled on `rawValue` (D-06), honors `placeholder` / `ariaLabel` / `className` / `inputMode` from the descriptor.
- **`FilterBar`** — schema-driven layout: summary slot + `Clear all` top-right (D-17 gated on `activeCount > 0`), chip strip above inline controls (D-15 deferred list), `flex flex-wrap gap-3 items-end` control row (D-18). Type-imports `UseFiltersReturn` only — does not call `useFilters` itself (D-18 ownership). Chip `source` uses `filters.rawValues` for `search` descriptors and `filters.values` for everything else to match the D-06 / plan-02 `isActive` semantics.
- **`components/filters/index.ts`** — re-exports types + all primitives + FilterBar.

## Key files

### Created
- `apps/visualizer/frontend/src/components/filters/FilterChip/{FilterChip.tsx,index.ts}`
- `apps/visualizer/frontend/src/components/filters/styles.ts`
- `apps/visualizer/frontend/src/components/filters/ToggleFilter/{ToggleFilter.tsx,index.ts}`
- `apps/visualizer/frontend/src/components/filters/SelectFilter/{SelectFilter.tsx,index.ts}`
- `apps/visualizer/frontend/src/components/filters/DateRangeFilter/{DateRangeFilter.tsx,index.ts}`
- `apps/visualizer/frontend/src/components/filters/SearchFilter/{SearchFilter.tsx,index.ts}`
- `apps/visualizer/frontend/src/components/filters/FilterBar/{FilterBar.tsx,index.ts}`
- `apps/visualizer/frontend/src/components/filters/__tests__/FilterBar.test.tsx`

### Modified
- `apps/visualizer/frontend/src/components/filters/index.ts`

## Self-Check: PASSED

- `npx vitest run src/components/filters/__tests__/FilterBar.test.tsx` — 4/4 tests pass.
- `npx tsc --noEmit` — exit 0.
- `npx eslint src/components/filters` — exit 0.
- Acceptance grep:
  - `export function FilterBar` / `ToggleFilter` / `SelectFilter` / `DateRangeFilter` / `SearchFilter` / `FilterChip` — 1 match each.
  - `flex flex-wrap gap-3 items-end`, `FILTER_CLEAR_ALL`, `FILTER_CHIP_REMOVE_ARIA`, `chipSourceValue`, `filters.isActive(` — ≥1 match in `FilterBar.tsx`.
  - `filters.rawValues` — 2 matches (chip source + `SearchFilter` wiring).
  - `useFilters(` — 0 matches in `FilterBar.tsx`.
  - `from '../../ui/Input'` — 1 match in `SearchFilter.tsx`.
  - `descriptor.className` — 1 match in `SelectFilter.tsx`.

## Deviations

- Added an extra "Clear all hidden when activeCount=0" and "Clear all invokes clearAll" test beyond the three required by 3.4, since they were trivial to add and lock the Clear-all wiring end-to-end.
- Extracted the shared `CONTROL` class into `filters/styles.ts` rather than inlining it in each primitive, per the plan's "one file to avoid drift" note — just chose the separate styles.ts option.
- Primitive indexes also re-export the props type (`ToggleFilterProps`, etc.) for downstream tests/future consumers. Not required by the plan but cheap and consistent with the repo style.
- Exhaustive switch in `FilterBar` uses a `switch` with `default: const _never: never = d` instead of the chained `if` blocks in the plan text, per the project's no-inline-imports/exhaustive-switch convention (user rules).

## Enables next plan

Plan 04 (CatalogTab migration) can now:
1. Build a schema array defining posted/analyzed/month/keyword/minRating/dateRange/colorLabel/scorePerspective/minCatalogScore/sortByScore descriptors.
2. Call `useFilters(schema)` in `CatalogTab.tsx`.
3. Render `<FilterBar schema={schema} filters={filters} summary={<RangeSummary ... />} disabled={loading} />` in place of the existing 160-line filter block.
4. Spread `filters.toQueryParams()` into `ImagesAPI.listCatalog` to preserve the snake_case contract.
