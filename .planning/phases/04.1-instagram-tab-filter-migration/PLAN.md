---
plan: 01
phase: 4.1
title: InstagramTab migration to useFilters + FilterBar
wave: 1
depends_on: []
autonomous: true
requirements:
  - FILTER-02
files_modified:
  - apps/visualizer/frontend/src/components/images/InstagramTab.tsx
  - apps/visualizer/frontend/src/components/images/__tests__/InstagramTab.test.tsx
---

<objective>
Migrate `InstagramTab.tsx` off its ad-hoc `dateFilter` `useState` + `handleFilterChange` / `clearFilter` handlers and onto the Phase 4 framework (`FilterSchema` + `useFilters(schema)` + `<FilterBar>`). Preserve `ImagesAPI.listInstagram` query-param parity (`date_folder: 'YYYYMM'` when a month is picked, key omitted otherwise) and pagination behavior (filter change resets to page 1 / offset 0). Add a minimum RTL smoke test.
</objective>

<context>
InstagramTab has a single `select` filter and no search / date-range / toggle. It is the minimum-complexity consumer and validates that the framework degrades gracefully to a one-descriptor schema.

See `CONTEXT.md` decisions D-1..D-8.
</context>

<tasks>
<task id="1">
<action>
Rewrite `apps/visualizer/frontend/src/components/images/InstagramTab.tsx`:

1. Drop imports of `FILTER_CLEAR` (no longer used — `<FilterBar>` uses `FILTER_CLEAR_ALL` internally).
2. Add imports:
   ```ts
   import { useMemo } from 'react'
   import { FilterBar, type FilterSchema } from '../filters'
   import { useFilters } from '../../hooks/useFilters'
   ```
3. Remove:
   - `const [dateFilter, setDateFilter] = useState('')`
   - `handleFilterChange`
   - `clearFilter`
   - The inline `<select>` + Clear button block (lines 94–117 of the pre-migration file).
4. Build `instagramSchema` inside `useMemo(() => [...], [availableMonths])`:
   ```ts
   const instagramSchema = useMemo<FilterSchema>(
     () => [
       {
         type: 'select',
         key: 'dateFolder',
         label: 'Date',
         paramName: 'date_folder',
         defaultValue: '',
         options: [
           { value: '', label: FILTER_ALL_DATES },
           ...availableMonths.map((month) => ({ value: month, label: formatMonth(month) })),
         ],
       },
     ],
     [availableMonths],
   )
   ```
5. `const filters = useFilters(instagramSchema)`. Destructure `const { values: filterValues, toQueryParams } = filters`.
6. `fetchImages`: remove the `filter: string = dateFilter` second arg; always derive params from `toQueryParams()`:
   ```ts
   const params = {
     ...toQueryParams(),
     limit: ITEMS_PER_PAGE,
     offset: newOffset,
   }
   await ImagesAPI.listInstagram(params)
   ```
   Update `useCallback` deps to `[toQueryParams]`.
7. Replace the legacy filter-change → fetch-from-0 pattern with a `useEffect`:
   ```ts
   useEffect(() => {
     fetchImages(0)
   }, [filterValues.dateFolder])
   ```
   This keeps the "filter change → back to page 1" semantics. The `initialize` effect already handles the first load, so this secondary effect should **only** fire when the filter changes post-mount. Use a `useRef<boolean>(true)` "first run" guard (pattern mirrors CatalogTab's debounced-text-ref approach) to skip the initial render.
8. Render:
   ```tsx
   <FilterBar
     schema={instagramSchema}
     filters={filters}
     summary={
       <p className="text-sm text-text-secondary">
         {total.toLocaleString()} images total
       </p>
     }
     disabled={isLoading}
   />
   ```
   Replace the old `<div className="flex items-center justify-between">…</div>` block above the grid with this single `<FilterBar>` call. Keep the rest of the component (PageError, SkeletonGrid, grid, Pagination, ImageDetailsModal) untouched.
9. `availableMonths.length > 0` gate: previously hid the filter when no months loaded. The new behavior always renders the select (schema always present); when `availableMonths` is empty the only option is "All dates" and no month can be picked. This is acceptable — matches CatalogTab behavior with an empty month list.
</action>
<acceptance_criteria>
- `rg -n "useState.*dateFilter|handleFilterChange|clearFilter" apps/visualizer/frontend/src/components/images/InstagramTab.tsx` matches 0 lines
- `rg -n "useFilters\(" apps/visualizer/frontend/src/components/images/InstagramTab.tsx` matches 1 line
- `rg -n "<FilterBar" apps/visualizer/frontend/src/components/images/InstagramTab.tsx` matches 1 line
- `rg -n "FILTER_CLEAR\b" apps/visualizer/frontend/src/components/images/InstagramTab.tsx` matches 0 lines (only `FILTER_ALL_DATES` and `ITEMS_PER_PAGE` remain from the strings import)
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</acceptance_criteria>
</task>

<task id="2">
<action>
Create `apps/visualizer/frontend/src/components/images/__tests__/InstagramTab.test.tsx` modeled on `CatalogTab.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { InstagramTab } from '../InstagramTab'

const listInstagramMock = vi.fn()
const getInstagramMonthsMock = vi.fn()

vi.mock('../../../services/api', () => ({
  ImagesAPI: {
    listInstagram: (...args: unknown[]) => listInstagramMock(...args),
    getInstagramMonths: (...args: unknown[]) => getInstagramMonthsMock(...args),
  },
}))

describe('InstagramTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listInstagramMock.mockResolvedValue({
      images: [],
      total: 0,
      pagination: { current_page: 1, total_pages: 1, has_more: false },
    })
    getInstagramMonthsMock.mockResolvedValue({ months: [] })
  })

  it('calls listInstagram with pagination defaults and no date_folder at baseline', async () => {
    render(<InstagramTab />)

    await waitFor(() => {
      expect(listInstagramMock).toHaveBeenCalled()
    })
    const firstCall = listInstagramMock.mock.calls[0]?.[0] ?? {}
    expect(firstCall.limit).toBeGreaterThan(0)
    expect(firstCall.offset).toBe(0)
    expect(firstCall).not.toHaveProperty('date_folder')
  })

  it('renders the Date filter label once schema mounts', async () => {
    render(<InstagramTab />)
    await waitFor(() => {
      expect(screen.getAllByText('Date').length).toBeGreaterThan(0)
    })
  })
})
```

Note: InstagramTab does not use `useLocation` / `useNavigate`, so no `MemoryRouter` needed (confirmed by reading the current file).
</action>
<acceptance_criteria>
- `test -f apps/visualizer/frontend/src/components/images/__tests__/InstagramTab.test.tsx && echo ok` prints `ok`
- `cd apps/visualizer/frontend && npx vitest run src/components/images/__tests__/InstagramTab.test.tsx` exits 0
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx vitest run` exits 0 (full suite, no regressions)
- `cd apps/visualizer/frontend && npm run lint` exits 0
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</verification>
