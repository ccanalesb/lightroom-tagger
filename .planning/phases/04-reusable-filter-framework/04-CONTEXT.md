# Phase 4: Reusable filter framework - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a declarative filter foundation — schema + `<FilterBar>` + `useFilters(schema)` hook — and validate it by migrating `CatalogTab.tsx` end-to-end with no functional regression. CatalogTab is the stress test (11+ filter pieces, the most complex filter set in the app); if the framework survives CatalogTab, it has earned the name "reusable."

**In scope:**
- Declarative filter **schema** (TypeScript types) covering the primitives CatalogTab uses today: toggle/tri-state, select, date-range (from/to), debounced search, numeric select (rating, min-score), and dependent-group (perspective-gated min-score + sort)
- `<FilterBar>` component renders the schema into form controls with the current CatalogTab visual treatment (label-above-control, `flex-wrap gap-3`, h-9 controls)
- `useFilters(schema)` hook returning `values`, `setValue`, `clearAll`, `activeCount`, and `toQueryParams`, with debouncing handled internally
- Active filters surface as removable chips with a consistent "Clear all" affordance
- CatalogTab migrated end-to-end — the ~100 lines of `useState` + handlers replaced by a schema declaration and framework usage, with no behavioural regression (identical filter fields, identical API calls, identical empty/loading states, identical outward `onPostedFilterChange` dispatch)
- Extract the inline `useDebouncedValue` from `CatalogTab.tsx:34` into a reusable hook (scope: `apps/visualizer/frontend/src/hooks/useDebouncedValue.ts`) so the filter framework and any other consumer share one implementation
- All new UI strings (chip labels, "Clear all" button text, aria labels) go through `constants/strings.ts`

**Out of scope (handed to later phases / seeds):**
- Migrating **InstagramTab, MatchesTab, DescriptionsTab, MatchingTab, AnalyticsPage** to the framework — REQUIREMENTS.md Implementation Guidance explicitly scopes this to CatalogTab only in v2.1. These rides are future milestone work (SEED-007 full rollout).
- URL syncing of filter state (`?posted=true&month=2025-03`) — rides with SEED-010 (persist tab + filter state)
- Saved-filter presets — not in FILTER-01/02
- Natural-language search (SEED-005) compiling into the schema — v3.0 territory
- **AnalyticsPage's apply-button pattern** — AnalyticsPage uses a distinct "edit then click Apply" UX with a separate `applied` state, not the live-update model Phase 4 targets. The framework is designed for live filtering first; supporting apply-button flows is deferred. See `<deferred>` for rationale.
- Filter **removal** from any current surface — this phase is additive behind the current UX; no surface loses filters.
- Backend changes — the server already accepts every query param CatalogTab sends; the framework just reshapes how the frontend builds the request.

Requirements locked by `.planning/REQUIREMENTS.md`:
- **FILTER-01** — Developer can declare a filter schema (toggle, select, date-range, search) and get a fully-working `<FilterBar>` with consistent visual treatment (active chips, clear-all, active count)
- **FILTER-02** — Developer gets centralised filter state via a `useFilters(schema)` hook returning values, setters, clear-all, active count, and query-param mapping — with debouncing handled internally

CatalogTab migration is the acceptance condition, not a separate requirement (REQUIREMENTS.md, "Implementation Guidance").

</domain>

<decisions>
## Implementation Decisions

### Schema shape & primitive set

- **D-01:** The schema is a typed array of filter descriptors — `type FilterSchema = FilterDescriptor[]`. Each descriptor is a discriminated union keyed on `type`. No runtime schema validation library (zod, yup) — TypeScript's compile-time check is enough for an internal foundation.
- **D-02:** Primitives shipped in Phase 4 — and only these, so CatalogTab migrates cleanly without overshooting:
  - `toggle` — tri-state (`true | false | undefined`). Rendered as a `<select>` today; future CVA pass (SEED-011) can upgrade to a real toggle. Used for `posted` and `analyzed`.
  - `select` — single-value dropdown with `{ value, label }[]` options (options may be async / loaded). Used for `month`, `minRating`, `scorePerspective`, `minScore`, `sortByScore`.
  - `dateRange` — pair of ISO date strings `{ from, to }`. One descriptor produces two controls + one chip summarizing the range. Used for `dateFrom`/`dateTo`.
  - `search` — debounced string input. `debounceMs` is a per-descriptor option. Used for `keyword` and `colorLabel`.
- **D-03:** Conditional visibility / dependent filters use an explicit `enabledBy: { filterKey: string, when: (value) => boolean }` field on the dependent descriptor, NOT hidden/shown children. When `enabledBy` is not satisfied, the control renders disabled (matches existing CatalogTab behaviour where `minScore` and `sortByScore` are `disabled={!scorePerspective}`) and the filter does NOT contribute to `activeCount` or `toQueryParams`. `minScore` and `sortByScore` each declare `enabledBy: { filterKey: 'scorePerspective', when: v => !!v }`. No nested `dependentGroup` primitive — the flat approach is simpler and matches existing DOM.
- **D-04:** No `numberRange` primitive in Phase 4. CatalogTab's `minRating` is a single-value select (`''|1..5`) and `minScore` is a single-value select (`''|1..10`) — both fit `select`. If a future migration needs a true two-ended numeric range, it can add a `numberRange` primitive then; YAGNI now.
- **D-05:** Each descriptor has a stable `key: string` (used as the state key, the chip `key`, and the basis for the query-param name). Labels and chip formatters are separate fields (`label`, `chipLabel?`, `formatValue?`) so the display string is independent of the state key.

### State hook semantics — `useFilters(schema)` surface

- **D-06:** The hook's return shape is an object (not a tuple — tuple ordering would hurt readability with this many members):
  ```ts
  {
    values: Record<string, unknown>,           // current committed values
    rawValues: Record<string, unknown>,        // pre-debounce values (for controlled inputs)
    setValue: (key: string, value: unknown) => void,
    setValues: (patch: Record<string, unknown>) => void,  // for multi-field updates (e.g. perspective change clears min/sort)
    clearAll: () => void,
    activeCount: number,
    toQueryParams: () => Record<string, unknown>,
    isActive: (key: string) => boolean,
  }
  ```
  Debounced filters expose the **debounced** value via `values` (that's what the API call should use) and the **immediate** value via `rawValues` (that's what the `<input>` should display). Non-debounced filters have identical `values[key]` and `rawValues[key]`.
- **D-07:** The hook runs in **live-update mode** — every `setValue` flows into `values` (post-debounce where applicable), and consumers re-fetch via the usual `useEffect(loadImages, [values])` pattern. No apply-button mode in Phase 4 (see out-of-scope note on AnalyticsPage).
- **D-08:** Debouncing is driven by the schema (`debounceMs` on `search` descriptors; defaults to 350ms to match the current `DEBOUNCE_MS` constant in `CatalogTab.tsx:12`). Other primitives are not debounced — their values commit synchronously. The hook uses a single internal `useDebouncedValue` per debounced key; no global debounce timer.
- **D-09:** `activeCount` counts filters where the current value differs from the descriptor's declared `defaultValue`. Each primitive ships a sensible default (`toggle: undefined`, `select: ''`, `dateRange: { from: '', to: '' }`, `search: ''`) and descriptors can override. The dependent-disabled filters (D-03) do NOT contribute to the count even if their value is non-default, because the user can't see or change them until the parent is set.
- **D-10:** `clearAll` resets every value to its descriptor's `defaultValue`. Consumers who need to reset pagination on clear wire their own `setPage(1)` into a `useEffect(() => setPage(1), [values])` — the framework does NOT own pagination. (Rationale: pagination lives outside the filter system today, and CatalogTab's `setPage(1)` currently fires in every handler — moving it into the hook would couple two responsibilities that Phase 2 deliberately separated.)
- **D-11:** `setValue` and `setValues` handle dependent clearing automatically: when the parent of a dependent group changes to a value where `enabledBy.when` is false, the hook clears all dependent keys to their defaults in the same render. This preserves the existing CatalogTab behaviour where clearing `scorePerspective` also clears `minCatalogScore` and resets `sortByScore` to `'none'` (`CatalogTab.tsx:210-217`), without asking the consumer to chain calls.

### Query-param mapping

- **D-12:** Mapping rules live on the descriptor (`paramName?: string`, `toParam?: (value) => unknown | undefined`). The hook's `toQueryParams()` walks the schema and applies each rule. A filter that returns `undefined` from `toParam` is omitted (same shape as the existing conditional-spread pattern in `CatalogTab.tsx:89-108`).
- **D-13:** `paramName` defaults to the descriptor's `key` in snake_case — `colorLabel` → `color_label`, `scorePerspective` → `score_perspective`, `minCatalogScore` → `min_score`. Explicit `paramName` overrides the default. (Matches existing server param names exactly — no backend change required.)
- **D-14:** No dedicated "rename / compose" hook for multi-key outputs. The three server fields gated by `scorePerspective` (`score_perspective`, `min_score`, `sort_by_score`) are three separate descriptors with `enabledBy`, and each contributes independently via its own `toParam` / `paramName`. This matches the current spread-pattern output 1:1.

### `<FilterBar>` layout & chip affordance

- **D-15:** **Chips supplement, not replace, the inline controls.** CatalogTab today renders all 11 controls inline and that's the UX the user is familiar with; shifting to chips-only (controls in a popover) would be a net-new UX direction that belongs in a future phase. Phase 4 keeps the inline control row and adds a chip row above (or below — Claude's discretion) showing active filters with ✕ buttons. This is additive, low-risk, and makes "active state at a glance" visible without hiding controls.
- **D-16:** Chip rendering: one chip per active filter, showing `chipLabel` (defaults to `label`) + the formatted value (via `formatValue?(value)` on the descriptor, default: `String(value)`). Date-range renders as a single chip "`Date: 2025-01-01 → 2025-03-01`" (or "from …" / "to …" for open-ended ranges). Clicking ✕ clears that filter only.
- **D-17:** "Clear all" button position stays **top-right of the filter region**, matching the current CatalogTab layout (`CatalogTab.tsx:304-313`) so the migration is visually unchanged. It's visible only when `activeCount > 0` (current behaviour preserved). The chip row's ✕ buttons are per-filter; "Clear all" is the global reset.
- **D-18:** `<FilterBar>` accepts `schema`, the hook return value, and a `summary?: ReactNode` slot (for the "Showing X of Y" summary text that currently lives above the control row in CatalogTab). Layout wraps `flex-wrap gap-3 items-end` — identical to the current CatalogTab layout. No popover, no modal, no collapse affordance.

### Migration strategy for CatalogTab

- **D-19:** Migration is **big-bang** inside CatalogTab.tsx, not incremental. Incremental (half-native / half-framework) would double the code and leave a weird transitional state in the diff. The framework lands in one plan; the CatalogTab migration lands in the next, in a single focused rewrite.
- **D-20:** Regression strategy — **three-layer**:
  1. The existing `CatalogTab.test.tsx` (if any — planner verifies) stays green unchanged. The framework is an implementation detail; tests assert behaviour.
  2. **New tests for the framework itself** — unit tests for `useFilters` (active-count math, debouncing, dependent clear, `toQueryParams` output, `clearAll`) and `<FilterBar>` (chip render, ✕ click clears, disabled state for dependent filters).
  3. **Manual smoke check** called out in the plan's verification — every filter in CatalogTab toggled once after migration, confirm the same network request shape.
- **D-21:** The outward `onPostedFilterChange?(posted)` callback prop (CatalogTab.tsx:44-46) survives as-is. CatalogTab reads `values.posted` and calls the prop in a `useEffect`. No framework-level "subscription" abstraction — one consumer needing one outward value doesn't justify an API. If a second consumer needs similar observability later, generalise then.

### Canonical refs captured during discussion

- **D-22:** Downstream agents MUST read REQUIREMENTS.md "Implementation Guidance" before planning — it explicitly scopes the migration to CatalogTab only. Widening scope (e.g. also migrating MatchesTab or AnalyticsPage) is a REQUIREMENTS.md violation and must be deferred.

### Claude's Discretion

- Exact TypeScript names for the discriminated union variants (`ToggleFilter` vs `FilterToggle` etc.) — planner picks, consistent with existing codebase naming.
- File/folder layout under `apps/visualizer/frontend/src/components/filters/` vs co-located in `components/ui/` — planner picks based on the ui/ folder's existing convention (each primitive has its own sub-folder with `index.ts`).
- Exact chip row position (above or below the inline controls) and chip visual treatment (use existing `Badge` primitive with a "chip" variant, or a new minimal component) — pick what matches the existing design language; do not introduce a new primitive if `Badge` + an ✕ button composes cleanly.
- Whether `dateRange` is one descriptor producing two controls, or two linked `date` descriptors composed under the hood — either works; pick whichever is easier to express in the chip formatter.
- Whether to extract `useDebouncedValue` into `hooks/useDebouncedValue.ts` in the same plan as the framework or as a small prep commit — planner decides; either is acceptable as long as only one copy exists post-phase.
- Test framework specifics — match whatever `useMatchGroups.test.ts` / existing frontend tests use (Vitest + Testing Library, per STACK.md).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` §"Reusable filter framework" — FILTER-01, FILTER-02 acceptance criteria
- `.planning/REQUIREMENTS.md` §"Implementation Guidance" — explicit scope lock: CatalogTab only, other tabs deferred
- `.planning/ROADMAP.md` §"Phase 4: Reusable filter framework" — 4 success criteria, dependency on Phase 5 (DASH-03)

### Existing seeds (source of truth for rationale)
- `.planning/seeds/SEED-007-reusable-filter-component.md` — original seed with schema example, breadcrumbs to all current filter implementations, and phased rollout notes (Phase 4 here = Phase 1 + Phase 2 of that seed's internal plan)

### Codebase — the stress test
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — 11 filter `useState`s, 10 custom handlers, inline `useDebouncedValue`, conditional-spread `toQueryParams` pattern, tri-state `posted`/`analyzed`, perspective-gated `minScore`/`sortByScore`, outward `onPostedFilterChange` dispatch. **Migration target**.
- `apps/visualizer/frontend/src/services/api.ts` — `ImagesAPI.listCatalog()` signature; framework's `toQueryParams` output must match this shape.

### Codebase — reusable primitives
- `apps/visualizer/frontend/src/components/ui/Input/` — text input primitive, used by current `keyword` and `colorLabel` filters
- `apps/visualizer/frontend/src/components/ui/Badge/` — composable badge, candidate base for chip rendering (D-16, Claude's discretion)
- `apps/visualizer/frontend/src/components/ui/Button/` — used for "Clear all" and chip ✕
- `apps/visualizer/frontend/src/components/ui/Pagination.tsx` — lives outside the filter system; D-10 keeps it that way
- `apps/visualizer/frontend/src/constants/strings.ts` — every new UI string goes through here (project convention, reinforced Phases 1–3)

### Codebase — contrast examples (not migration targets in Phase 4)
- `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` — minimal single-filter example (`date_folder` only); migration deferred
- `apps/visualizer/frontend/src/pages/AnalyticsPage.tsx` — apply-button paradigm with `AppliedFilters` state (`from`/`to`/`granularity`); deliberately NOT a Phase 4 consumer (see `<deferred>`)
- `apps/visualizer/frontend/src/components/analytics/UnpostedCatalogPanel.tsx` — yet another independent filter implementation; migration deferred

### Prior-phase context (established patterns to follow)
- `.planning/phases/01-matching-review-polish/01-CONTEXT.md` D-14 — UI strings via `constants/strings.ts`
- `.planning/phases/02-job-queue-and-processing-ux/02-CONTEXT.md` — `<Pagination>` usage pattern (currentPage pinned, `setPage(1)` on filter change — framework keeps this boundary)
- `.planning/codebase/CONVENTIONS.md` — TypeScript/React conventions, Tailwind patterns, test naming
- `.planning/codebase/STACK.md` — Vite + React 19 + ESLint max-warnings 0 quality gate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`useDebouncedValue`** — currently inlined in `CatalogTab.tsx:34-41` (7-line hook). Extract to `hooks/useDebouncedValue.ts` and consume from the framework. Only other current caller is the same file.
- **`<Input>`, `<Badge>`, `<Button>`** — all live in `components/ui/` with an established `ComponentName/ComponentName.tsx + index.ts` pattern. Filter primitives follow the same convention.
- **`constants/strings.ts`** — central UI string home. New keys needed: `FILTER_CLEAR_ALL` (exists as `FILTER_CLEAR` — rename or add a plural variant), `FILTER_CHIP_REMOVE_LABEL` (aria), per-filter `chipLabel` keys if the planner decides chip labels differ from control labels.
- **`<Pagination>`** from `components/ui/Pagination.tsx` — filter changes trigger `setPage(1)` at the consumer level (D-10); framework doesn't own this.

### Established Patterns
- **Container/presenter:** pages fetch data, dumb components receive props. `<FilterBar>` is a dumb presenter; `useFilters` is the smart hook; the tab (CatalogTab) is the container — same split as today.
- **Conditional spread for query params:** CatalogTab.tsx:89-108 is the current idiom. `toQueryParams` must produce identical output so the server sees an unchanged request shape.
- **Tri-state filters via `select` with `'all'` sentinel:** `posted` maps `'all' | 'posted' | 'not-posted'` to `undefined | true | false` (CatalogTab.tsx:183-192). The `toggle` primitive encapsulates this mapping internally.
- **Test co-location:** tests under `__tests__/` next to source. New tests for the framework follow this layout.
- **No over-abstraction:** prior phases consistently reject features that aren't needed yet (no toast system, no Undo affordance, no animation library). Phase 4 follows the same bar — no URL sync, no presets, no popover UX.

### Integration Points
- **`ImagesAPI.listCatalog()`** (`services/api.ts`) is the single API the migrated CatalogTab calls. The framework's `toQueryParams()` output is passed here. No change to the API surface, no change to the backend.
- **Router deep-link in `CatalogTab.tsx:169-177`** (image_key URL param for modal deep-linking) is unrelated to filters. Preserve untouched.
- **`PerspectivesAPI.list()` async load** populates `scorePerspective` options (`CatalogTab.tsx:156-163`). The `select` primitive's `options` field supports async population at the consumer level (consumer fetches, passes options into the schema via `useMemo`).

</code_context>

<specifics>
## Specific Ideas

- User explicitly waived detailed discussion of the six gray areas. Decisions above are inferred from: the existing CatalogTab code (which is the de-facto spec), REQUIREMENTS.md Implementation Guidance (hard scope lock), and patterns established in Phases 1–3 (minimal surface, no new primitives without need, central strings, container/presenter split). If the planner surfaces a genuine ambiguity not covered here, surface it back to the user rather than guessing.
- Framework naming: "reusable filter framework" is the roadmap name, but the code can call it anything — `useFilters` hook + `<FilterBar>` component feels natural. No strong preference captured.
- CatalogTab's inline-controls layout is the visual target — the migration should be visually imperceptible to the user beyond the new chip row.

</specifics>

<deferred>
## Deferred Ideas

- **AnalyticsPage migration (apply-button paradigm)** — explicitly deferred. Phase 4's hook is live-update only (D-07). Adding apply-button mode later is a hook option flag; not shipping it now keeps the API narrow. When a future milestone migrates AnalyticsPage, the hook gains a `mode: 'live' | 'apply'` option and an `apply()` method; the schema stays unchanged.
- **Migrating InstagramTab / MatchesTab / DescriptionsTab / MatchingTab / UnpostedCatalogPanel** — deferred per REQUIREMENTS.md Implementation Guidance. Future milestone work (see SEED-007 "Future Requirements" in REQUIREMENTS.md).
- **URL syncing (`?posted=true&month=2025-03`)** — deferred to SEED-010 (persist tab + filter state in-memory/URL). The hook can gain a `syncToUrl: boolean` option then without breaking consumers.
- **Saved-filter presets** — deferred. Not in FILTER-01/02, not in any v2.1 seed.
- **Natural-language search compiling to schema (SEED-005)** — v3.0 territory; the schema being declarative is what makes this future work feasible, but no Phase 4 code writes toward it.
- **`numberRange` primitive** — deferred (D-04). CatalogTab's current numeric filters all fit `select`. Add when a real consumer needs a two-ended numeric range.
- **`dependentGroup` nested primitive** — deferred (D-03). Flat descriptors with `enabledBy` cover the current need.
- **Popover / collapsible filter UX (chips-only, controls hidden)** — deferred (D-15). Significant UX shift, not a Phase 4 goal. Framework supports it later by rendering `<FilterBar mode="popover">` without changing the hook.
- **Framework-level outward value subscription** — deferred (D-21). The single existing outward dispatch (`onPostedFilterChange`) doesn't justify a generic subscription API.

</deferred>

---

*Phase: 04-reusable-filter-framework*
*Context gathered: 2026-04-17*
