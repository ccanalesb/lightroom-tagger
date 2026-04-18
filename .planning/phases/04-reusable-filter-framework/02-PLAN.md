---
plan: 02
title: useFilters(schema) hook — state, debounce, toQueryParams, dependent clear
wave: 2
depends_on: [01]
files_modified:
  - apps/visualizer/frontend/src/hooks/useFilters.ts
  - apps/visualizer/frontend/src/hooks/index.ts
  - apps/visualizer/frontend/src/hooks/__tests__/useFilters.test.ts
autonomous: true
requirements:
  - FILTER-02
---

<objective>
Implement `useFilters(schema: FilterSchema)` returning the object surface from **D-06** (`values`, `rawValues`, `setValue`, `setValues`, `clearAll`, `activeCount`, `toQueryParams`, `isActive`) with **D-07** live-update semantics, **D-08** per-`search` debounce timers (no hooks-in-a-loop violation), **D-09** / **D-03** active counting with `enabledBy` + defaults, **D-10** consumer-owned pagination (no pagination inside hook), **D-11** dependent auto-clear, and **D-12–D-14** query mapping (`paramName` default snake_case + optional `toParam`). Validate with focused Vitest tests that lock `ImagesAPI.listCatalog` param shape against the pre-migration `CatalogTab.tsx` spread pattern.
</objective>

<context>
Implements **D-06–D-14** and relies on types from plan 01 (`components/filters/types.ts`). **Does not** render UI (plan 03). **Does not** migrate `CatalogTab` (plan 04). **Out of scope:** URL sync, presets, apply-button mode, framework-level `onPostedFilterChange` subscription (D-21 deferred).
</context>

<tasks>
<task id="2.1">
<action>
Add `apps/visualizer/frontend/src/hooks/useFilters.ts` implementing the hook and a named export type `UseFiltersReturn` matching **D-06** exactly (property names and meanings).

**Snake_case default (D-13)** — add module-local helper:

```ts
function keyToSnakeCase(key: string): string {
  return key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase()
}
```

**Default `toParam` / emission rules** when `descriptor.toParam` is absent:
- `toggle`: emit nothing when value is `undefined`; when `true` / `false`, emit boolean at `paramName ?? keyToSnakeCase(key)` (posted + analyzed match `ImagesAPI.listCatalog`: `posted` and `analyzed` are already snake_case keys — use `paramName` on descriptors whose `key` is camelCase if needed).
- `select`: empty string `''` omits; when `numberValue: true`, non-empty string stores as `number` in state but `toQueryParams` must pass `Number(value)` for `min_rating` / `min_score`; when value is `'none'` for sort, omit `sort_by_score` (plan 04 will supply explicit `toParam` on that descriptor — the default select rule is `value === '' ? undefined : value` for string params).
- `dateRange`: if both `from` and `to` are falsy after trim, omit both; else set `fromParamName ?? 'date_from'` / `toParamName ?? 'date_to'` to trimmed strings when non-empty (each side optional, matching `CatalogTab.tsx:99-100`).
- `search`: trim; empty string omits; else `paramName ?? keyToSnakeCase(key)` with trimmed string.

**`toQueryParams()` algorithm:**
1. Start with `{} as Record<string, unknown>`.
2. Iterate `schema` in array order. If `!isDescriptorEnabled(descriptor, workingValues)` where `workingValues` is the **committed** `values` object (post-debounce for search — i.e. the same object returned as `values` from the hook), **skip** the descriptor entirely (D-03, D-09).
3. If `descriptor.toParam` exists, call `descriptor.toParam(workingValues[descriptor.key])`; if result is `undefined`, skip; if result is a **plain object**, shallow-merge its enumerable keys into the accumulator (supports one descriptor contributing multiple keys); if result is non-object, set single key `descriptor.paramName ?? keyToSnakeCase(descriptor.key)` to that value.
4. If no `toParam`, apply the default rules above (single-key set or two keys for `dateRange`).

**State model (D-06, D-08):**
- Keep `rawValues: Record<string, unknown>` in `useState`, initialized from `schema.map` using `descriptorDefault`.
- Keep `committedValues: Record<string, unknown>` in `useState`, same initializer.
- On `setValue` / `setValues` for a **non-`search`** descriptor: compute `nextRaw = applyPatch`, then `nextRaw = applyDependentClears(schema, nextRaw)` (**D-11** — when any `enabledBy.when` is false for a descriptor, force that descriptor’s key back to `descriptorDefault(descriptor)`; loop until stable), then `setRawValues(nextRaw); setCommittedValues(nextRaw)` (identical for non-search).
- For **`search`** descriptor: `setRawValues` with cleared dependents; **do not** immediately copy to `committedValues` for that key. Instead maintain `const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout> | undefined>>({})`. On search key change: `clearTimeout` previous for that key; `setTimeout` for `descriptor.debounceMs ?? DEFAULT_SEARCH_DEBOUNCE_MS` then `setCommittedValues(prev => ({...prev, [key]: nextRaw[key]}))` (and ensure raw stays).

**Initial mount:** for each `search` descriptor, schedule nothing; `rawValues` and `committedValues` equal defaults.

**Returned `values`:** always `committedValues` after dependent resolution on each render — but note search keys lag in `committedValues`; `rawValues` has immediate typing state.

**`rawValues` return:** the live `rawValues` state (immediate for inputs).

**`clearAll`:** rebuild defaults map from schema, `setRawValues` + `setCommittedValues` to that map; clear all debounce timers.

**`activeCount` (D-09) + CatalogTab parity:** iterate descriptors; if `!isDescriptorEnabled(descriptor, committedValues)` skip. For each descriptor, decide “active” vs default:
- For `type: 'search'`, treat as active when `String(rawValues[descriptor.key] ?? '').trim() !== ''` **even if** the debounced `committedValues` is still `''` — this matches legacy `CatalogTab.tsx:266-277` where `hasActiveFilters` used `keyword`/`colorLabel` (immediate), not the debounced values.
- For all other types, compare `committedValues[descriptor.key]` to `descriptorDefault(descriptor)` using **deep equality for `dateRange` only** (`from`/`to` strings); for toggles/selects use `===` / `''` / `undefined` rules so `sortByScore !== 'none'` counts as active, etc.

**`isActive(key)`:** same rule as `activeCount` per descriptor — for `search`, use **raw** trim test; for others use **committed** value vs default. If `!isDescriptorEnabled(descriptor, committedValues)`, return `false` (D-03, D-09).

**`useMemo` / `useCallback`:** stabilize `toQueryParams` and handlers; include `schema` in dependency arrays where needed.

Export:

```ts
export type UseFiltersReturn = {
  values: Record<string, unknown>
  rawValues: Record<string, unknown>
  setValue: (key: string, value: unknown) => void
  setValues: (patch: Record<string, unknown>) => void
  clearAll: () => void
  activeCount: number
  toQueryParams: () => Record<string, unknown>
  isActive: (key: string) => boolean
}

export function useFilters(schema: FilterSchema): UseFiltersReturn { ... }
```

Append to `apps/visualizer/frontend/src/hooks/index.ts`:

```ts
export { useFilters } from './useFilters'
export type { UseFiltersReturn } from './useFilters'
```

Imports at top of `useFilters.ts`:

```ts
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  DEFAULT_SEARCH_DEBOUNCE_MS,
  descriptorDefault,
  isDescriptorEnabled,
  type FilterSchema,
  type FilterDescriptor,
} from '../components/filters/types'
```
</action>
<read_first>
- apps/visualizer/frontend/src/hooks/useFilters.ts
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
- apps/visualizer/frontend/src/components/filters/types.ts
- apps/visualizer/frontend/src/components/images/CatalogTab.tsx (query spread pattern lines 89–108)
- apps/visualizer/frontend/src/services/api.ts (`ImagesAPI.listCatalog` lines 217–231)
</read_first>
<acceptance_criteria>
- `rg -n "export function useFilters" apps/visualizer/frontend/src/hooks/useFilters.ts` matches 1 line
- `rg -n "export type UseFiltersReturn" apps/visualizer/frontend/src/hooks/useFilters.ts` matches 1 line
- `rg -n "function keyToSnakeCase" apps/visualizer/frontend/src/hooks/useFilters.ts` matches 1 line
- `rg -n "applyDependentClears|dependent" apps/visualizer/frontend/src/hooks/useFilters.ts` matches at least 1 line (executor names helper — grep for `enabledBy` handling): `rg -n "enabledBy" apps/visualizer/frontend/src/hooks/useFilters.ts` matches at least 2 lines
- `rg -n "export \\{ useFilters \\}" apps/visualizer/frontend/src/hooks/index.ts` matches 1 line
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</acceptance_criteria>
</task>

<task id="2.2">
<action>
Create `apps/visualizer/frontend/src/hooks/__tests__/useFilters.test.ts` with Vitest + `@testing-library/react`’s `renderHook` + `act` (same imports style as `useMatchGroups.handleRejected.test.tsx` — single quotes optional but eslint must pass).

**Fixture schema A — minimal catalog-shaped slice** (inline in test file):

```ts
const triSerialize = (v: unknown) =>
  v === undefined ? 'all' : v === true ? 'true' : 'false'
const triDeserialize = (raw: string) =>
  raw === 'all' ? undefined : raw === 'true' ? true : false

const minimalSchema: FilterSchema = [
  {
    type: 'toggle',
    key: 'posted',
    label: 'Status',
    options: [
      { value: 'all', label: 'All' },
      { value: 'true', label: 'Posted' },
      { value: 'false', label: 'Not' },
    ],
    serialize: triSerialize,
    deserialize: triDeserialize,
  },
  {
    type: 'toggle',
    key: 'analyzed',
    label: 'Analyzed',
    options: [
      { value: 'all', label: 'All' },
      { value: 'true', label: 'Analyzed' },
      { value: 'false', label: 'Not analyzed' },
    ],
    serialize: triSerialize,
    deserialize: triDeserialize,
  },
  {
    type: 'select',
    key: 'scorePerspective',
    label: 'Perspective',
    options: [{ value: '', label: 'Any' }, { value: 'p1', label: 'P1' }],
  },
  {
    type: 'select',
    key: 'minCatalogScore',
    label: 'Min score',
    options: [{ value: '', label: 'Any' }],
    numberValue: true,
    enabledBy: { filterKey: 'scorePerspective', when: (v) => Boolean(v) },
  },
  {
    type: 'select',
    key: 'sortByScore',
    label: 'Sort',
    options: [
      { value: 'none', label: 'None' },
      { value: 'asc', label: 'Asc' },
      { value: 'desc', label: 'Desc' },
    ],
    enabledBy: { filterKey: 'scorePerspective', when: (v) => Boolean(v) },
  },
  {
    type: 'search',
    key: 'keyword',
    label: 'Keyword',
    debounceMs: 350,
  },
]
```

**Required test cases:**
1. **activeCount baseline:** initial `activeCount === 0`.
2. **toggle posted:** `setValue('posted', true)` then `toQueryParams().posted === true` and `activeCount` increments (expect `1` or higher depending on other fields — assert `>= 1` and `isActive('posted')`).
3. **dependent clear (D-11):** `setValue('scorePerspective', 'p1')`, `setValue('minCatalogScore', 5)`, then `setValue('scorePerspective', '')` — after act, `result.current.values.minCatalogScore` must be `''` (or `descriptorDefault`) and `toQueryParams()` must **not** contain `min_score` or `score_perspective`.
4. **search debounce:** `setValue('keyword', 'cat')`, immediately `toQueryParams()` should omit `keyword` (still debouncing), `act` + `vi.advanceTimersByTime(350)`, then `toQueryParams().keyword === 'cat'`. Use `vi.useFakeTimers()` in that test with `afterEach` restore.
5. **clearAll:** after mutating several fields, `clearAll()` resets `activeCount` to `0` and `toQueryParams()` returns `{}` (only keys with values — empty object).

Use `renderHook(() => useFilters(minimalSchema))` and `result.current` throughout.
</action>
<read_first>
- apps/visualizer/frontend/src/hooks/useFilters.ts
- apps/visualizer/frontend/src/hooks/__tests__/useMatchGroups.handleRejected.test.tsx
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `cd apps/visualizer/frontend && npx vitest run src/hooks/__tests__/useFilters.test.ts` exits 0
- `rg -n "dependent clear|scorePerspective" apps/visualizer/frontend/src/hooks/__tests__/useFilters.test.ts` matches at least 2 lines
- `rg -n "vi\\.useFakeTimers" apps/visualizer/frontend/src/hooks/__tests__/useFilters.test.ts` matches at least 1 line
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx vitest run src/hooks/__tests__/useFilters.test.ts` exits 0
- `cd apps/visualizer/frontend && npx vitest run src/hooks/__tests__/useDebouncedValue.test.ts` exits 0
- `cd apps/visualizer/frontend && npx eslint src/hooks/useFilters.ts src/hooks/__tests__/useFilters.test.ts` exits 0
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</verification>

<must_haves>
- `UseFiltersReturn` matches **D-06** field names exactly.
- Debouncing applies **only** to `type: 'search'` descriptors, per-key trailing debounce, default **350ms** when omitted (**D-08**).
- `activeCount` / `isActive` / `toQueryParams` all respect `enabledBy` on the **committed** value snapshot (**D-03**, **D-09**).
- `setValue` / `setValues` clear dependents when parent gate fails (**D-11**).
- `toQueryParams` output keys align with `ImagesAPI.listCatalog` (`posted`, `analyzed`, `month`, `keyword`, `min_rating`, `date_from`, `date_to`, `color_label`, `score_perspective`, `min_score`, `sort_by_score`) — tests or assertions in plan 04 migration lock full parity; this plan’s tests must at least cover `posted`, `analyzed`, `score_perspective`, `min_score`, `keyword` omission/presence rules.
- No React hooks called in a dynamic loop over schema length.
</must_haves>
