---
plan: 01
title: useDebouncedValue extraction, filter schema types, strings
wave: 1
depends_on: []
files_modified:
  - apps/visualizer/frontend/src/hooks/useDebouncedValue.ts
  - apps/visualizer/frontend/src/hooks/index.ts
  - apps/visualizer/frontend/src/hooks/__tests__/useDebouncedValue.test.ts
  - apps/visualizer/frontend/src/components/filters/types.ts
  - apps/visualizer/frontend/src/components/filters/index.ts
  - apps/visualizer/frontend/src/constants/strings.ts
  - apps/visualizer/frontend/src/components/images/CatalogTab.tsx
autonomous: true
requirements:
  - FILTER-01
  - FILTER-02
---

<objective>
Extract the inline `useDebouncedValue` hook from `CatalogTab.tsx` into a shared `hooks/useDebouncedValue.ts` with Vitest coverage; add `components/filters/types.ts` defining the Phase 4 discriminated-union filter schema (`FilterSchema` / per-primitive descriptors with `enabledBy`, `paramName`, `toParam`, `debounceMs`); centralize new filter UI strings in `constants/strings.ts`; re-export types from `components/filters/index.ts`. Apply the minimal `CatalogTab` change needed to consume the extracted hook so only one implementation exists (see `04-CONTEXT.md` `<code_context>` → “Reusable Assets” / `useDebouncedValue`).
</objective>

<context>
Implements **D-01** (typed array schema, no zod), **D-02** primitive set (`toggle`, `select`, `dateRange`, `search`), **D-03** (`enabledBy` shape), **D-04** / **D-05** (keys, labels, optional `chipLabel` / `formatValue`), **D-08** (default `debounceMs` 350 on `search`). Extracts **`useDebouncedValue`** per `04-CONTEXT.md` `<code_context>` (“Reusable Assets”). Does **not** implement `useFilters` or `<FilterBar>` — those are plans 02–03. **Scope lock:** do not touch InstagramTab, MatchesTab, AnalyticsPage, or any tab other than the single `useDebouncedValue` import swap in `CatalogTab.tsx` (REQUIREMENTS scope lock is **D-22** in `04-CONTEXT.md` — applies to the milestone as a whole, not this extraction bullet).
</context>

<tasks>
<task id="1.1">
<action>
Create `apps/visualizer/frontend/src/hooks/useDebouncedValue.ts` with exactly:

```ts
import { useEffect, useState } from 'react'

export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}
```

Append one line to `apps/visualizer/frontend/src/hooks/index.ts`:

```ts
export { useDebouncedValue } from './useDebouncedValue'
```

In `apps/visualizer/frontend/src/components/images/CatalogTab.tsx`:
1. Delete the local function `useDebouncedValue` (lines 34–41 in the pre-change file).
2. Add `useDebouncedValue` to the React import **only if** you keep `useState` from `react` — prefer: `import { useCallback, useEffect, useRef, useState } from 'react';` unchanged, and add: `import { useDebouncedValue } from '../../hooks/useDebouncedValue';` (adjust relative depth if wrong: from `components/images/` to `hooks/` is `../../hooks/useDebouncedValue`).

Do not change `DEBOUNCE_MS`, `debouncedKeyword`, or `debouncedColorLabel` usage otherwise.
</action>
<read_first>
- apps/visualizer/frontend/src/components/images/CatalogTab.tsx
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
- apps/visualizer/frontend/src/hooks/index.ts
</read_first>
<acceptance_criteria>
- `test -f apps/visualizer/frontend/src/hooks/useDebouncedValue.ts && echo ok` prints `ok`
- `rg -n "export function useDebouncedValue" apps/visualizer/frontend/src/hooks/useDebouncedValue.ts` matches 1 line
- `rg -n "function useDebouncedValue" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 0 lines
- `rg -n "from '\\.\\./\\.\\./hooks/useDebouncedValue'|from \"\\.\\./\\.\\./hooks/useDebouncedValue\"" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 1 line (executor may use double quotes — grep for `hooks/useDebouncedValue` instead): `rg -n "hooks/useDebouncedValue" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 1 line
- `rg -n "export \\{ useDebouncedValue \\}" apps/visualizer/frontend/src/hooks/index.ts` matches 1 line
</acceptance_criteria>
</task>

<task id="1.2">
<action>
Create `apps/visualizer/frontend/src/hooks/__tests__/useDebouncedValue.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebouncedValue } from '../useDebouncedValue'

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebouncedValue('a', 350))
    expect(result.current).toBe('a')
  })

  it('updates after delay', () => {
    const { result, rerender } = renderHook(({ v, d }) => useDebouncedValue(v, d), {
      initialProps: { v: 'a', d: 350 },
    })
    rerender({ v: 'b', d: 350 })
    expect(result.current).toBe('a')
    act(() => {
      vi.advanceTimersByTime(350)
    })
    expect(result.current).toBe('b')
  })

  it('resets timer when value changes rapidly', () => {
    const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 350), {
      initialProps: { v: 'a' },
    })
    rerender({ v: 'b' })
    act(() => {
      vi.advanceTimersByTime(200)
    })
    rerender({ v: 'c' })
    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(result.current).toBe('a')
    act(() => {
      vi.advanceTimersByTime(150)
    })
    expect(result.current).toBe('c')
  })
})
```
</action>
<read_first>
- apps/visualizer/frontend/src/hooks/useDebouncedValue.ts
- apps/visualizer/frontend/src/hooks/__tests__/useMatchGroups.handleRejected.test.tsx
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `cd apps/visualizer/frontend && npx vitest run src/hooks/__tests__/useDebouncedValue.test.ts` exits 0
</acceptance_criteria>
</task>

<task id="1.3">
<action>
Create `apps/visualizer/frontend/src/components/filters/types.ts` with the full discriminated union and helpers (single source of truth for plan 02 and 03). Paste exactly:

```ts
export type DateRangeValue = { from: string; to: string }

export type SelectOption = { value: string; label: string }

/** Parent gate: when `when` returns false, control is disabled and value is ignored for activeCount / toQueryParams (D-03, D-09). */
export type EnabledBy = {
  filterKey: string
  when: (parentValue: unknown) => boolean
}

type BaseDescriptor = {
  key: string
  label: string
  chipLabel?: string
  formatValue?: (value: unknown) => string
  defaultValue?: unknown
  paramName?: string
  toParam?: (value: unknown) => unknown | undefined
  enabledBy?: EnabledBy
}

export type ToggleFilterDescriptor = BaseDescriptor & {
  type: 'toggle'
  /** `<select>` rows for the tri-state control (posted / analyzed labels live in schema from strings.ts). */
  options: SelectOption[]
  /** Committed value: undefined = “all”, true/false map to the two arms (posted / analyzed). */
  defaultValue?: boolean | undefined
  /** Map tri-state to/from `<select>` string values (CatalogTab posted/analyzed string tokens). */
  serialize: (value: unknown) => string
  deserialize: (raw: string) => unknown
}

export type SelectFilterDescriptor = BaseDescriptor & {
  type: 'select'
  options: SelectOption[]
  /** Merged onto the `<select>` element (e.g. `min-w-[8rem]` for score perspective — plan 04). */
  className?: string
  /** When true, empty string option maps to numeric state (D-04). CatalogTab minRating / minCatalogScore. */
  numberValue?: boolean
  defaultValue?: string | number | ''
}

export type DateRangeFilterDescriptor = BaseDescriptor & {
  type: 'dateRange'
  fromParamName?: string
  toParamName?: string
  defaultValue?: DateRangeValue
}

export type SearchFilterDescriptor = BaseDescriptor & {
  type: 'search'
  inputMode?: 'text' | 'search'
  placeholder?: string
  ariaLabel?: string
  debounceMs?: number
  className?: string
  defaultValue?: string
}

export type FilterDescriptor =
  | ToggleFilterDescriptor
  | SelectFilterDescriptor
  | DateRangeFilterDescriptor
  | SearchFilterDescriptor

export type FilterSchema = FilterDescriptor[]

/** Default debounce for search when `debounceMs` omitted (D-08). */
export const DEFAULT_SEARCH_DEBOUNCE_MS = 350

export function defaultFormatValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function isDescriptorEnabled(
  descriptor: FilterDescriptor,
  values: Record<string, unknown>,
): boolean {
  if (!descriptor.enabledBy) return true
  return descriptor.enabledBy.when(values[descriptor.enabledBy.filterKey])
}

export function descriptorDefault(descriptor: FilterDescriptor): unknown {
  if (descriptor.defaultValue !== undefined) return descriptor.defaultValue
  switch (descriptor.type) {
    case 'toggle':
      return undefined
    case 'select':
      return ''
    case 'dateRange':
      return { from: '', to: '' }
    case 'search':
      return ''
    default: {
      const _exhaustive: never = descriptor
      return _exhaustive
    }
  }
}
```

Create `apps/visualizer/frontend/src/components/filters/index.ts`:

```ts
export * from './types'
```

(Plan 03 will append more exports; for this plan only re-export `types`.)
</action>
<read_first>
- apps/visualizer/frontend/src/components/filters/types.ts
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
- apps/visualizer/frontend/src/services/api.ts (ImagesAPI.listCatalog param names only)
</read_first>
<acceptance_criteria>
- `rg -n "export type FilterSchema" apps/visualizer/frontend/src/components/filters/types.ts` matches 1 line
- `rg -n "type: 'dateRange'" apps/visualizer/frontend/src/components/filters/types.ts` matches 1 line
- `rg -n "export function isDescriptorEnabled" apps/visualizer/frontend/src/components/filters/types.ts` matches 1 line
- `rg -n "DEFAULT_SEARCH_DEBOUNCE_MS = 350" apps/visualizer/frontend/src/components/filters/types.ts` matches 1 line
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</acceptance_criteria>
</task>

<task id="1.4">
<action>
In `apps/visualizer/frontend/src/constants/strings.ts`, under the existing `// Filters` section (after `FILTER_CLEAR`), append:

```ts
/** FilterBar — primary reset (D-17); Catalog migration uses this label. */
export const FILTER_CLEAR_ALL = 'Clear all'

/** aria-label for per-chip remove control (D-16). */
export const FILTER_CHIP_REMOVE_ARIA = (filterLabel: string) => `Remove ${filterLabel} filter`
```

Keep `FILTER_CLEAR` unchanged for backwards compatibility elsewhere.

Do **not** inline these strings in components in later plans — import from `constants/strings.ts`.
</action>
<read_first>
- apps/visualizer/frontend/src/constants/strings.ts
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "export const FILTER_CLEAR_ALL" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "export const FILTER_CHIP_REMOVE_ARIA" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx vitest run src/hooks/__tests__/useDebouncedValue.test.ts` exits 0
- `cd apps/visualizer/frontend && npx eslint src/hooks/useDebouncedValue.ts src/hooks/index.ts src/components/filters/types.ts src/components/filters/index.ts src/constants/strings.ts src/components/images/CatalogTab.tsx` exits 0 with `--max-warnings 0` behavior (repo script if applicable)
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</verification>

<must_haves>
- Exactly one `useDebouncedValue` implementation in the repo under `hooks/`; `CatalogTab` imports it (D-22).
- `FilterSchema` + four primitive descriptor variants exist as a discriminated union (D-01, D-02).
- `enabledBy`, `paramName` / `toParam` hooks exist on the shared descriptor base (D-03, D-12).
- `dateRange` is one descriptor type carrying `{ from, to }` (D-02, Claude discretion).
- New user-visible filter strings live in `constants/strings.ts` only.
- No `useFilters` / `FilterBar` code yet — avoids partial framework.
</must_haves>
