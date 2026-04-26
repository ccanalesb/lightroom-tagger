---
plan: 03
title: FilterBar and filter primitives (presenter only)
wave: 2
depends_on: [01, 02]
files_modified:
  - apps/visualizer/frontend/src/components/filters/ToggleFilter/ToggleFilter.tsx
  - apps/visualizer/frontend/src/components/filters/ToggleFilter/index.ts
  - apps/visualizer/frontend/src/components/filters/SelectFilter/SelectFilter.tsx
  - apps/visualizer/frontend/src/components/filters/SelectFilter/index.ts
  - apps/visualizer/frontend/src/components/filters/DateRangeFilter/DateRangeFilter.tsx
  - apps/visualizer/frontend/src/components/filters/DateRangeFilter/index.ts
  - apps/visualizer/frontend/src/components/filters/SearchFilter/SearchFilter.tsx
  - apps/visualizer/frontend/src/components/filters/SearchFilter/index.ts
  - apps/visualizer/frontend/src/components/filters/FilterChip/FilterChip.tsx
  - apps/visualizer/frontend/src/components/filters/FilterChip/index.ts
  - apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx
  - apps/visualizer/frontend/src/components/filters/FilterBar/index.ts
  - apps/visualizer/frontend/src/components/filters/index.ts
  - apps/visualizer/frontend/src/components/filters/__tests__/FilterBar.test.tsx
autonomous: true
requirements:
  - FILTER-01
---

<objective>
Build dumb UI primitives under `components/filters/` plus `<FilterBar>` that renders a `FilterSchema` using the shared layout from **D-15–D-18**: summary row + top-right **Clear all** when `filters.activeCount > 0`, a **chip row above** the inline `flex flex-wrap gap-3 items-end` control row, per-chip ✕ that calls `filters.setValue(key, descriptorDefault)` (import `descriptorDefault` from `./types`), no popover. **Does not import `useFilters`** — accepts `filters: UseFiltersReturn` as a prop (**D-18**). Cover chip render, ✕ clearing, and dependent-disabled selects with RTL tests.
</objective>

<context>
Implements **D-15** (chips supplement inline controls; chips **above** controls — planner discretion), **D-16** (chip label + formatted value + ✕), **D-17** (Clear all top-right, visible iff `activeCount > 0`), **D-18** (`summary` slot + `flex-wrap gap-3 items-end`; presenter receives hook return as prop). **D-16 chip visual:** compose existing `Badge` + small `Button` (`variant="ghost"`, `size="sm"`) for the ✕ — **no new `ui/` primitive**. **Type-only dependency on plan 02:** `FilterBar.tsx` imports `UseFiltersReturn` from `hooks/useFilters.ts` — plan **03** must run after plan **02** (`depends_on: [01, 02]`) so parallel wave-2 executors do not hit missing-type `tsc` failures. **Scope lock:** only files under `components/filters/` + its test; do not migrate `CatalogTab` yet (plan 04).
</context>

<tasks>
<task id="3.1">
<action>
Create `FilterChip/FilterChip.tsx` + `index.ts`:

```tsx
import { Badge } from '../../ui/Badge'
import { Button } from '../../ui/Button'

export type FilterChipProps = {
  text: string
  removeAriaLabel: string
  onRemove: () => void
  disabled?: boolean
}

export function FilterChip({ text, removeAriaLabel, onRemove, disabled }: FilterChipProps) {
  return (
    <Badge variant="default" className="inline-flex items-center gap-1 pr-1">
      <span className="max-w-[14rem] truncate">{text}</span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="!px-1 !py-0 min-w-0 h-6 text-text-secondary hover:text-text"
        aria-label={removeAriaLabel}
        disabled={disabled}
        onClick={onRemove}
      >
        ×
      </Button>
    </Badge>
  )
}
```

`index.ts`: `export { FilterChip } from './FilterChip'`
</action>
<read_first>
- apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx
- apps/visualizer/frontend/src/components/ui/Button/Button.tsx
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `test -f apps/visualizer/frontend/src/components/filters/FilterChip/FilterChip.tsx && echo ok` prints `ok`
- `rg -n "export function FilterChip" apps/visualizer/frontend/src/components/filters/FilterChip/FilterChip.tsx` matches 1 line
</acceptance_criteria>
</task>

<task id="3.2">
<action>
Create primitives (each folder: `Component.tsx` + `index.ts` exporting the component). Shared **Tailwind** class for `<select>` and native date `<input>` — copy the class string from `CatalogTab.tsx` lines 325, 404 (the `h-9 px-3 rounded-base border...` pattern) into a module-level constant in **one** file (e.g. `FilterBar.tsx` or a tiny `styles.ts`) and reuse across primitives to avoid drift:

`const CONTROL = 'h-9 px-3 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all disabled:opacity-60'`

**`ToggleFilter/ToggleFilter.tsx`**
Props: `{ descriptor: ToggleFilterDescriptor; value: unknown; onChange: (v: unknown) => void; disabled?: boolean }`. Read `descriptor.options`, `descriptor.serialize`, `descriptor.deserialize` only (no catalog-specific keys inside this file). Derive `<select value>` via `(descriptor.serialize ?? defaultSerialize)(value)` where module `defaultSerialize` maps `undefined→'all'`, `true→'true'`, `false→'false'`. On change, `(descriptor.deserialize ?? defaultDeserialize)(e.target.value)`. CatalogTab (plan 04) supplies `serialize`/`deserialize` + `options` on the descriptor for posted (`all`/`posted`/`not-posted`) and analyzed (`all`/`analyzed`/`not_analyzed`).

**`SelectFilter/SelectFilter.tsx`**
Props: `{ descriptor: SelectFilterDescriptor; value: unknown; onChange: (v: unknown) => void; disabled?: boolean }`. Render `<select className={[CONTROL, descriptor.className].filter(Boolean).join(' ')}>`. When `numberValue`, coerce `e.target.value` to `number` or `''`. **Do not** branch on `descriptor.key` — plan **04** passes `className: 'min-w-[8rem]'` on the score-perspective descriptor (plan **01** `SelectFilterDescriptor.className`).

**`DateRangeFilter/DateRangeFilter.tsx`**
Props: `{ descriptor: DateRangeFilterDescriptor; value: unknown; onChange: (next: DateRangeValue) => void; disabled?: boolean }`. Cast value to `{from:'',to:''}` defaults.

**`SearchFilter/SearchFilter.tsx`**
Props: `{ descriptor: SearchFilterDescriptor; rawValue: unknown; onChange: (v: string) => void; disabled?: boolean }`. Use `Input` from `../../ui/Input`. `value={String(rawValue ?? '')}` — **must use raw** for controlled typing (**D-06**).

Each `index.ts`: `export { X } from './X'`
</action>
<read_first>
- apps/visualizer/frontend/src/components/images/CatalogTab.tsx (control markup)
- apps/visualizer/frontend/src/components/ui/Input/Input.tsx
- apps/visualizer/frontend/src/components/filters/types.ts
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "export function ToggleFilter" apps/visualizer/frontend/src/components/filters/ToggleFilter/ToggleFilter.tsx` matches 1 line
- `rg -n "export function SelectFilter" apps/visualizer/frontend/src/components/filters/SelectFilter/SelectFilter.tsx` matches 1 line
- `rg -n "export function DateRangeFilter" apps/visualizer/frontend/src/components/filters/DateRangeFilter/DateRangeFilter.tsx` matches 1 line
- `rg -n "export function SearchFilter" apps/visualizer/frontend/src/components/filters/SearchFilter/SearchFilter.tsx` matches 1 line
- `rg -n "descriptor\\.className" apps/visualizer/frontend/src/components/filters/SelectFilter/SelectFilter.tsx` matches at least 1 line
- `rg -n "from '\\.\\./\\.\\./ui/Input'|from \"\\.\\./\\.\\./ui/Input\"" apps/visualizer/frontend/src/components/filters/SearchFilter/SearchFilter.tsx` matches 0 lines — path from `components/filters/SearchFilter/` to `components/ui/Input` is `../../ui/Input`: `rg -n "from '\\.\\./\\.\\./ui/Input'" apps/visualizer/frontend/src/components/filters/SearchFilter/SearchFilter.tsx` matches 1 line
</acceptance_criteria>
</task>

<task id="3.3">
<action>
Create `FilterBar/FilterBar.tsx` + `index.ts`. Implement the **full** component below (executor may adjust import paths if eslint complains, but preserve behaviour). **Chip value source (plan 02 parity):** for `descriptor.type === 'search'`, build the formatted chip payload from **`filters.rawValues[descriptor.key]`** so chips stay correct during the debounce window; for all other types use **`filters.values[descriptor.key]`**. **Do not** call `useFilters` — only `import type { UseFiltersReturn }`.

```tsx
import type { ReactNode } from 'react'
import type { FilterSchema, FilterDescriptor } from '../types'
import { descriptorDefault, defaultFormatValue, isDescriptorEnabled } from '../types'
import type { UseFiltersReturn } from '../../../hooks/useFilters'
import { ToggleFilter } from '../ToggleFilter'
import { SelectFilter } from '../SelectFilter'
import { DateRangeFilter } from '../DateRangeFilter'
import { SearchFilter } from '../SearchFilter'
import { FilterChip } from '../FilterChip'
import { Button } from '../../ui/Button'
import { FILTER_CLEAR_ALL, FILTER_CHIP_REMOVE_ARIA } from '../../../constants/strings'

const ROW = 'flex flex-wrap gap-3 items-end'
const COL = 'flex flex-col gap-1.5'
const LABEL = 'text-xs font-medium text-text-tertiary'

function chipSourceValue(descriptor: FilterDescriptor, filters: UseFiltersReturn): unknown {
  if (descriptor.type === 'search') {
    return filters.rawValues[descriptor.key]
  }
  return filters.values[descriptor.key]
}

export type FilterBarProps = {
  schema: FilterSchema
  filters: UseFiltersReturn
  summary?: ReactNode
  disabled?: boolean
}

export function FilterBar({ schema, filters, summary, disabled }: FilterBarProps) {
  const chipRow =
    filters.activeCount > 0 ? (
      <div className="flex flex-wrap gap-2 mb-3">
        {schema
          .filter((d) => filters.isActive(d.key))
          .map((d) => {
            const source = chipSourceValue(d, filters)
            const display = d.formatValue ? d.formatValue(source) : defaultFormatValue(source)
            const chipLabel = d.chipLabel ?? d.label
            return (
              <FilterChip
                key={d.key}
                text={`${chipLabel}: ${display}`}
                removeAriaLabel={FILTER_CHIP_REMOVE_ARIA(chipLabel)}
                disabled={disabled}
                onRemove={() => filters.setValue(d.key, descriptorDefault(d))}
              />
            )
          })}
      </div>
    ) : null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">{summary}</div>
        {filters.activeCount > 0 && (
          <Button type="button" variant="secondary" size="sm" disabled={disabled} onClick={filters.clearAll}>
            {FILTER_CLEAR_ALL}
          </Button>
        )}
      </div>
      {chipRow}
      <div className={ROW}>
        {schema.map((d) => {
          const controlDisabled = Boolean(disabled) || !isDescriptorEnabled(d, filters.values)
          if (d.type === 'toggle') {
            return (
              <div key={d.key} className={COL}>
                <span className={LABEL}>{d.label}</span>
                <ToggleFilter
                  descriptor={d}
                  value={filters.values[d.key]}
                  onChange={(v) => filters.setValue(d.key, v)}
                  disabled={controlDisabled}
                />
              </div>
            )
          }
          if (d.type === 'select') {
            return (
              <div key={d.key} className={COL}>
                <span className={LABEL}>{d.label}</span>
                <SelectFilter
                  descriptor={d}
                  value={filters.values[d.key]}
                  onChange={(v) => filters.setValue(d.key, v)}
                  disabled={controlDisabled}
                />
              </div>
            )
          }
          if (d.type === 'dateRange') {
            return (
              <DateRangeFilter
                key={d.key}
                descriptor={d}
                value={filters.values[d.key]}
                onChange={(next) => filters.setValue(d.key, next)}
                disabled={controlDisabled}
              />
            )
          }
          if (d.type === 'search') {
            return (
              <div key={d.key} className={COL}>
                <span className={LABEL}>{d.label}</span>
                <SearchFilter
                  descriptor={d}
                  rawValue={filters.rawValues[d.key]}
                  onChange={(v) => filters.setValue(d.key, v)}
                  disabled={controlDisabled}
                />
              </div>
            )
          }
          const _never: never = d
          return _never
        })}
      </div>
    </div>
  )
}
```

**`DateRangeFilter` layout contract:** if `DateRangeFilter` currently returns a fragment with two columns, ensure it renders the **From** / **To** label+control pairs so the parent `ROW` lays them out like legacy `CatalogTab` (two siblings in the flex row). If it wraps both in one outer `div`, that `div` must use `className={ROW}` internally or `className="contents"` with two `COL` children so the visual grid matches.

**Important:** `FilterBar.tsx` must **not** call `useFilters` — only type-import `UseFiltersReturn`.

Re-export everything from `apps/visualizer/frontend/src/components/filters/index.ts`:

```ts
export * from './types'
export { FilterChip } from './FilterChip'
export { ToggleFilter } from './ToggleFilter'
export { SelectFilter } from './SelectFilter'
export { DateRangeFilter } from './DateRangeFilter'
export { SearchFilter } from './SearchFilter'
export { FilterBar } from './FilterBar'
```
</action>
<read_first>
- apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx
- apps/visualizer/frontend/src/components/images/CatalogTab.tsx
- apps/visualizer/frontend/src/hooks/useFilters.ts
- apps/visualizer/frontend/src/components/filters/types.ts
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "flex flex-wrap gap-3 items-end" apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx` matches at least 1 line
- `rg -n "FILTER_CLEAR_ALL" apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx` matches at least 1 line
- `rg -n "FILTER_CHIP_REMOVE_ARIA" apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx` matches at least 1 line
- `rg -n "filters\\.rawValues" apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx` matches at least 2 lines (chip source + `SearchFilter` wiring)
- `rg -n "filters\\.isActive\\(" apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx` matches at least 1 line
- `rg -n "chipSourceValue" apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx` matches at least 1 line
- `rg -n "useFilters\\(" apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx` matches 0 lines
- `rg -n "export function FilterBar" apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx` matches 1 line
</acceptance_criteria>
</task>

<task id="3.4">
<action>
Create `apps/visualizer/frontend/src/components/filters/__tests__/FilterBar.test.tsx`.

**Schema fixture** (inline): one `search` (`keyword`), one `select` with `enabledBy` pointing at `parent`, one `parent` `select` with options `''` and `'x'`.

**Tests:**
1. **Chip renders when active:** render `FilterBar` with a **fake** `filters` object (plain object implementing `UseFiltersReturn` with `activeCount: 1`, `isActive: (k) => k === 'keyword'`, `values: { keyword: 'cat' }`, `rawValues: { keyword: 'cat' }`, `setValue: vi.fn()`, `setValues: vi.fn()`, `clearAll: vi.fn()`, `toQueryParams: () => ({})`) — minimal stub; screen should show chip text containing `Keyword` (or chipLabel) and `cat`.
2. **✕ calls setValue with default:** click remove on chip, expect `setValue` called with `('keyword', '')` or `descriptorDefault` for search (`''`).
3. **Dependent select disabled:** `isDescriptorEnabled` false path — `values: { parent: '' , child: '1' }`, `enabledBy` on child; `disabled` prop on `SelectFilter` should be true (use `const { container } = render(...)` or assert `toBeDisabled()` on the child `<select>`).

Use `@testing-library/react` `render`/`screen`/`fireEvent`/`within` as needed. Import `FilterBar` from `../FilterBar` or `../index` consistent with repo path depth (`from '../FilterBar'` from `__tests__/` sibling of `filters`).

**Note:** stub does not need full hook behaviour — only the interface consumed by `FilterBar`.
</action>
<read_first>
- apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx
- apps/visualizer/frontend/src/components/processing/__tests__/JobQueueTab.test.tsx
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `cd apps/visualizer/frontend && npx vitest run src/components/filters/__tests__/FilterBar.test.tsx` exits 0
- `rg -n "describe\\('FilterBar'" apps/visualizer/frontend/src/components/filters/__tests__/FilterBar.test.tsx` matches 1 line
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx vitest run src/components/filters/__tests__/FilterBar.test.tsx` exits 0
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
- `cd apps/visualizer/frontend && npx eslint src/components/filters` exits 0
</verification>

<must_haves>
- `<FilterBar>` is a pure presenter: `schema` + `filters` + optional `summary` + `disabled` (**D-18**).
- Layout preserves **Clear all** top-right with summary on the left; chip strip only when `activeCount > 0` (**D-17**).
- Inline controls remain a single `flex-wrap gap-3 items-end` row (**D-18**); chips are **not** a popover (**D-15** deferred list).
- Chip remove and Clear all route through `filters.setValue` / `filters.clearAll` only — no duplicate state.
- **Search chip copy** reads from `filters.rawValues` (immediate typing) while non-search chips read from `filters.values` — matches plan **02** `activeCount` / `isActive` semantics for `search`.
- All new copy uses `FILTER_CLEAR_ALL` / `FILTER_CHIP_REMOVE_ARIA` from `constants/strings.ts`.
- **No** imports of `InstagramTab`, `AnalyticsPage`, or other tabs.
</must_haves>
