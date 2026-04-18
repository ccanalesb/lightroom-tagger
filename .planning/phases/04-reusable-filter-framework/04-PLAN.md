---
plan: 04
title: CatalogTab big-bang migration onto schema + useFilters + FilterBar
wave: 3
depends_on: [02, 03]
files_modified:
  - apps/visualizer/frontend/src/components/images/CatalogTab.tsx
  - apps/visualizer/frontend/src/constants/strings.ts
  - apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx
autonomous: true
requirements:
  - FILTER-01
  - FILTER-02
---

<objective>
Replace all ad-hoc filter `useState` / handlers in `CatalogTab.tsx` with a single `useMemo`d `FilterSchema`, `useFilters(schema)`, and `<FilterBar schema={...} filters={...} summary={...} disabled={loading} />`, preserving `ImagesAPI.listCatalog` query parity, pagination semantics (including debounced search page reset), async month + perspective loading, deep-link `image_key` behaviour, and `onPostedFilterChange` via `useEffect` (**D-19–D-21**). Add any missing catalog filter copy to `constants/strings.ts`. Add a minimal RTL smoke test for `CatalogTab` because no `CatalogTab.test.tsx` exists today (**D-20** layer 1).
</objective>

<context>
Delivers roadmap Phase 4 success criterion #4 and REQUIREMENTS “Implementation Guidance” acceptance. Depends on plans **01–03**. **Scope lock:** touch **only** `CatalogTab.tsx`, `constants/strings.ts` for this tab’s extracted copy, and the new test file — **do not** migrate other tabs/pages. **Out of scope:** URL filter sync, Analytics apply-button flow, InstagramTab, etc. (see `04-CONTEXT.md` `<deferred>`). **Clear-button copy (D-17):** migrating to `<FilterBar>` switches the reset control from legacy `FILTER_CLEAR` (`'Clear'`) to **`FILTER_CLEAR_ALL`** (`'Clear all'`) — intentional per **D-17**, not a regression to paper over.
</context>

<tasks>
<task id="4.1">
<action>
Extend `apps/visualizer/frontend/src/constants/strings.ts` (Filters section) with every **user-visible** English string currently hard-coded in `CatalogTab.tsx` for filters + empty states that you keep after migration. Minimum set:

```ts
// Catalog tab — filters (extracted from CatalogTab.tsx)
export const CATALOG_FILTER_LABEL_STATUS = 'Status'
export const CATALOG_FILTER_LABEL_ANALYZED = 'Analyzed'
export const CATALOG_FILTER_LABEL_MONTH = 'Month'
export const CATALOG_FILTER_LABEL_KEYWORD = 'Keyword'
export const CATALOG_FILTER_LABEL_MIN_RATING = 'Min rating'
export const CATALOG_FILTER_LABEL_FROM = 'From'
export const CATALOG_FILTER_LABEL_TO = 'To'
export const CATALOG_FILTER_LABEL_COLOR = 'Color label'
export const CATALOG_FILTER_LABEL_SCORE_PERSPECTIVE = 'Score perspective'
export const CATALOG_FILTER_LABEL_MIN_SCORE = 'Min score'
export const CATALOG_FILTER_LABEL_SORT_SCORE = 'Sort by score'

export const CATALOG_FILTER_POSTED_ALL = 'All Images'
export const CATALOG_FILTER_POSTED = 'Posted'
export const CATALOG_FILTER_NOT_POSTED = 'Not Posted'

export const CATALOG_FILTER_ANALYZED_ALL = 'All'
export const CATALOG_FILTER_ANALYZED_ONLY = 'Analyzed only'
export const CATALOG_FILTER_NOT_ANALYZED = 'Not analyzed'

export const CATALOG_FILTER_MIN_RATING_ANY = 'Any'
export const CATALOG_FILTER_SCORE_ANY = 'Any'
export const CATALOG_FILTER_SORT_NONE = 'None'
export const CATALOG_FILTER_SORT_HIGH_LOW = 'High → Low'
export const CATALOG_FILTER_SORT_LOW_HIGH = 'Low → High'

export const CATALOG_FILTER_KEYWORD_PLACEHOLDER = 'Search…'
export const CATALOG_FILTER_KEYWORD_ARIA = 'Keyword search'
export const CATALOG_FILTER_COLOR_PLACEHOLDER = 'e.g. Red'
export const CATALOG_FILTER_COLOR_ARIA = 'Color label'
```

Remove the corresponding literal strings from `CatalogTab.tsx` / schema `options` / `placeholder` / `ariaLabel` fields after adding these exports.

**Chip formatters:** pass `formatValue` / `chipLabel` on descriptors using these strings where helpful (e.g. chip shows `Status: Posted` not raw tokens).
</action>
<read_first>
- apps/visualizer/frontend/src/components/images/CatalogTab.tsx
- apps/visualizer/frontend/src/constants/strings.ts
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `rg -n "export const CATALOG_FILTER_POSTED_ALL" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "export const CATALOG_FILTER_KEYWORD_PLACEHOLDER" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "'All Images'" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 0 lines (string moved to constants)
</acceptance_criteria>
</task>

<task id="4.2">
<action>
Rewrite `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` to remove the eleven filter-related `useState` declarations (`postedFilter` through `sortByScore`) and all ten `handle*` / `clearFilters` handlers (lines 59–73, 183–253 in the pre-migration file). Keep all grid/modal/pagination/loading/error state intact.

**Add imports:**

```ts
import { useMemo } from 'react'
import { FilterBar, type FilterSchema } from '../filters'
import { useFilters } from '../../hooks/useFilters'
```

(Adjust relative paths: from `components/images/` → `components/filters` is `../filters`, hooks is `../../hooks/useFilters`.)

**Build `catalogSchema: FilterSchema` inside `useMemo(() => [...], [availableMonths, scorePerspectives])`.** Each descriptor `key` must match what `useFilters` / `toQueryParams` expect. Recommended keys/state shapes (committed):

| key | type | Notes |
|-----|------|-------|
| `posted` | `toggle` | `options` + `serialize`/`deserialize` mapping `all/posted/not-posted` ↔ `undefined/true/false` exactly like legacy `handlePostedFilterChange`. `toParam`: `undefined→undefined`, booleans pass through. |
| `analyzed` | `toggle` | Map `all/analyzed/not_analyzed` ↔ `undefined/true/false`; `toParam`: only emit `analyzed:true/false` when not `undefined` (matches spread lines 91–95). |
| `month` | `select` | options prepend `{ value: '', label: FILTER_ALL_DATES }` then months with `formatMonth(month)` labels. |
| `keyword` | `search` | `debounceMs: 350`, placeholders/aria from strings. |
| `minRating` | `select` | `numberValue: true`, stars options identical to current map. |
| `dateRange` | `dateRange` | value `{ from, to }`; default `{ from: '', to: '' }`; rely on hook defaults for `date_from`/`date_to` param names. |
| `colorLabel` | `search` | debounced 350ms. |
| `scorePerspective` | `select` | options Any + perspectives; set **`className: 'min-w-[8rem]'`** on the descriptor (plan **01** `SelectFilterDescriptor.className`, plan **03** `SelectFilter`) — never key-gate width inside `SelectFilter`. |
| `minCatalogScore` | `select` | `numberValue: true`, `paramName: 'min_score'`, `enabledBy` per D-03. |
| `sortByScore` | `select` | `paramName: 'sort_by_score'`, `enabledBy`, `toParam`: `(v) => (v === 'none' || v === '' ? undefined : v)` |

**`useFilters(catalogSchema)`** — destructure as `filters`.

**`loadImages`:** replace manual object with:

```ts
const params = {
  ...filters.toQueryParams(),
  limit: LIMIT,
  offset: (page - 1) * LIMIT,
}
await ImagesAPI.listCatalog(params)
```

**`useCallback` dependency array:** depend on `page`, `filters.values` (or each scalar field inside `filters.values` to avoid unstable identity if hook returns fresh object each render — prefer depending on explicit primitives extracted before `useCallback`).

**Pagination reset (D-10, parity with old lines 183–253 + 255–264):**
1. `useEffect(() => { setPage(1) }, [filters.values.posted, filters.values.analyzed, filters.values.month, filters.values.minRating, filters.values.dateRange, filters.values.scorePerspective, filters.values.minCatalogScore, filters.values.sortByScore])` — for `dateRange`, depend on `filters.values.dateRange.from` and `.to` (or JSON-stringify the object).
2. **Debounced text parity:** reproduce the old `prevKeyword` / `prevColor` effect: `useRef` holding previous committed keyword/color; `useEffect` that runs when `filters.values.keyword` or `filters.values.colorLabel` (debounced) changes and calls `setPage(1)` when changed compared to refs — copy the structure from legacy lines 255–264 substituting `filters.values.keyword` for `debouncedKeyword` and `filters.values.colorLabel` for `debouncedColorLabel`.

**`onPostedFilterChange` (D-21):** keep prop signature; add:

```ts
useEffect(() => {
  onPostedFilterChange?.(filters.values.posted as boolean | undefined)
}, [filters.values.posted, onPostedFilterChange])
```

**`hasActiveFilters` replacement:** after hook guarantees search raw counting in `activeCount`, use `const hasActiveFilters = filters.activeCount > 0` for summary / empty / Clear visibility — assert mentally against legacy matrix (if any mismatch during QA, adjust hook in plan 02, not here).

**Deep link (lines 169–177) and perspective/month effects:** copy verbatim — **do not** refactor.

**Render:** Replace the manual filter `<div className="space-y-3">` innards (summary row + old flex row) with:

```tsx
<FilterBar schema={catalogSchema} filters={filters} summary={<p className="text-sm text-text-secondary">{summaryText}</p>} disabled={loading} />
```

Ensure `summaryText` computation still uses `hasActiveFilters` / `loading` / `loadError` / `images` / `total` exactly as before.

**Remove unused imports** (`Input` if both searches use `SearchFilter` wrapping `Input` internally — `CatalogTab` no longer imports `Input` unless still needed elsewhere in file — it should not be).

**`FILTER_CLEAR`:** no longer used in this file after migration — remove import if unused.
</action>
<read_first>
- apps/visualizer/frontend/src/components/images/CatalogTab.tsx
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
- apps/visualizer/frontend/src/hooks/useFilters.ts
- apps/visualizer/frontend/src/components/filters/FilterBar/FilterBar.tsx
- apps/visualizer/frontend/src/components/filters/types.ts
- apps/visualizer/frontend/src/services/api.ts (`ImagesAPI.listCatalog`)
</read_first>
<acceptance_criteria>
- `rg -n "useState<boolean \\| undefined>\\(undefined\\)" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 0 lines (no postedFilter useState)
- `rg -n "const \\[keyword, setKeyword\\]" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 0 lines
- `rg -n "useFilters\\(catalogSchema\\)|useFilters\\(" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 1 line
- `rg -n "<FilterBar" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 1 line
- `rg -n "ImagesAPI\\.listCatalog\\(\\{\\s*\\.\\.\\.filters\\.toQueryParams" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 0 lines — allow multiline: `rg -n "filters\\.toQueryParams\\(\\)" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 1 line
- `rg -n "onPostedFilterChange\\?\\.\\(filters\\.values\\.posted" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches 0 lines — effect form may differ: `rg -n "onPostedFilterChange" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches at least 2 lines (prop + effect)
- `rg -n "image_key" apps/visualizer/frontend/src/components/images/CatalogTab.tsx` matches at least 1 line (deep link preserved)
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</acceptance_criteria>
</task>

<task id="4.3">
<action>
Create `apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx`.

**Minimum bar (D-20):**
- `vi.mock('../../services/api', () => ({ ImagesAPI: { listCatalog: vi.fn(), getCatalogMonths: vi.fn() }, PerspectivesAPI: { list: vi.fn() } }))` — adjust relative import depth to match file location (`services/api` from `components/images/__tests__` is `../../../services/api`).
- Before render, resolve mocks: `getCatalogMonths` → `{ months: [] }`, `PerspectivesAPI.list` → `[]`, `listCatalog` → `{ images: [], total: 0 }`.
- `import { MemoryRouter } from 'react-router-dom'` and wrap `<CatalogTab />` because the component uses `useLocation` / `useNavigate`.
- One test: `it('renders catalog filters', () => { render(<MemoryRouter><CatalogTab /></MemoryRouter>); expect(screen.getByText(/Catalog|Images|Keyword|Score perspective/)).toBeTruthy() })` — loosen matcher to something that reliably exists post-migration (e.g. `CATALOG_FILTER_LABEL_KEYWORD` imported string).

**Do not** assert pixel-perfect layout — behaviour smoke only.
</action>
<read_first>
- apps/visualizer/frontend/src/components/images/CatalogTab.tsx
- apps/visualizer/frontend/src/pages/__tests__/MatchingPage.test.tsx
- .planning/phases/04-reusable-filter-framework/04-CONTEXT.md
</read_first>
<acceptance_criteria>
- `test -f apps/visualizer/frontend/src/components/images/__tests__/CatalogTab.test.tsx && echo ok` prints `ok`
- `cd apps/visualizer/frontend && npx vitest run src/components/images/__tests__/CatalogTab.test.tsx` exits 0
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx vitest run src/hooks/__tests__/useDebouncedValue.test.ts src/hooks/__tests__/useFilters.test.ts src/components/filters/__tests__/FilterBar.test.tsx src/components/images/__tests__/CatalogTab.test.tsx` exits 0
- `cd apps/visualizer/frontend && npm run lint` exits 0 (or `npx eslint src/...` covering changed paths)
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</verification>

<must_haves>
- **Big-bang migration** inside `CatalogTab.tsx` only — no half-old filter state (**D-19**).
- **API parity:** query keys are a subset of `ImagesAPI.listCatalog`’s supported params and match the old conditional-spread semantics (**D-12–D-14**, `api.ts:217–231`). Full confidence is gated on the **Human UAT checklist** below (D-20 layer 3).
- **Pagination:** non-search filters reset page immediately on change; **search** filters reset page only when debounced committed values change (**D-10**, legacy lines 255–264 behaviour).
- **`onPostedFilterChange`:** still driven off committed `posted` value (**D-21**).
- **Deep link `image_key`:** preserve behaviour described in `04-CONTEXT.md` `<code_context>` → “Integration Points” (`CatalogTab.tsx:169-177`).
- **Async perspective + month options:** preserve behaviour in the same `<code_context>` section (`CatalogTab.tsx:144-163` analogues post-migration).
- **Strings:** no new user-visible English literals left in `CatalogTab.tsx` for migrated controls — live in `constants/strings.ts`.
- **Tests:** new `CatalogTab` smoke test + all plan 01–03 tests remain green (**D-20** layers 1–2).

### Human UAT checklist (D-20 layer 3 — not machine-gated)

Executor or reviewer completes once in a real browser after implementation:

1. Start visualizer; open Images → Catalog.
2. Toggle **Posted** all three values — Network `GET /api/images/catalog` query must include/exclude `posted=true/false` exactly as before.
3. Toggle **Analyzed** all three — `analyzed` query must match legacy semantics.
4. Pick a month (if months load), min rating, date from/to, color, keyword (wait >350ms), score perspective + min score + sort — each mutation should fire refetch with expected query keys (`score_perspective`, `min_score`, `sort_by_score` only when perspective set).
5. Clear all — all params cleared, page resets to 1.
6. Deep link `?image_key=foo` still opens modal stub and strips param.
</must_haves>
