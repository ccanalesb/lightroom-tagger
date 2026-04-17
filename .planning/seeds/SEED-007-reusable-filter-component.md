---
id: SEED-007
status: dormant
planted: 2026-04-15
amended: 2026-04-17
planted_during: v2.0 (milestone complete)
trigger_when: next UX improvements milestone, Images page redesign, or Analytics/Insights filter work
scope: Medium
---

# SEED-007: Build a reusable, composable filter component for consistent filtering across the app

## Why This Matters

The Images page has three tabs (Catalog, Instagram, Matches) and each has a completely different filter experience:

- **Catalog tab** has 11+ independent filter pieces (posted, analyzed, month, keyword, minRating, dateFrom, dateTo, colorLabel, scorePerspective, minCatalogScore, sortByScore), each as its own `useState` with its own UI treatment.
- **Instagram tab** has just a date/month dropdown.
- **Matches tab** has no filters at all.
- **Analytics page** has its own from/to/granularity filter UI (`AppliedFilters` in `AnalyticsPage.tsx`) implemented independently — another consumer that should adopt the shared framework.
- **Insights → Top Photos strip** has no filter at all, but SEED-009 calls for adding a posted/unposted tri-state filter to it — that should come from this same framework, not a bespoke implementation.

This inconsistency creates two real problems:

1. **User confusion.** Filters that exist on one tab don't exist on another, even when they'd make sense (posted status, date range, score filters). The user has to mentally reset their filter expectations every time they switch tabs.
2. **Developer friction.** Adding a new filter means duplicating state management, URL syncing (if any), clear-all logic, and UI treatment. Filters that should behave the same (date ranges, posted toggles) are implemented differently every time.

The app needs a reusable filter framework — a component library + state pattern where each filter is declarative, toggleable via props, and consistent in look and behavior. Tabs/pages declare "I want these filters: date, posted, keyword" and the component handles rendering, state, clear-all, and URL syncing.

## When to Surface

**Trigger:** Next UX improvements milestone or Images page redesign

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- UX consistency or information architecture improvements
- Images page or filter experience redesign
- Analytics or Insights page filter / UX work
- Design system or component library work
- Preparation for natural language search (SEED-005) — which builds on structured filters
- Work on SEED-009 (posted vs unposted on Insights top photos) — that seed depends on this framework

## Scope Estimate

**Medium** — A phase or two. The work involves:

1. **Design the filter primitive API.** A declarative schema like:
   ```ts
   filters: [
     { type: 'toggle', key: 'posted', label: 'Posted', tri-state: true },
     { type: 'select', key: 'month', label: 'Month', options: [...] },
     { type: 'dateRange', key: 'date', label: 'Date taken' },
     { type: 'search', key: 'keyword', debounce: 300 },
     { type: 'numberRange', key: 'rating', min: 0, max: 5 },
     { type: 'dependentGroup', enabledBy: 'scorePerspective', filters: [...] },
   ]
   ```
2. **Build the core components.** `FilterBar`, `FilterChip`, `FilterPopover`, and a set of filter primitives (toggle, select, date-range, number-range, search, dependent-group).
3. **Centralize state via a hook.** `useFilters(schema)` returns `{ values, setValue, clearAll, activeCount, toQueryParams }`. Handles debouncing, URL sync, and clear-all consistently.
4. **Migrate existing tabs.** CatalogTab, InstagramTab, MatchesTab, DescriptionsTab, MatchingTab all switch to the new framework. Each tab declares its filter schema; the framework renders and manages state.
5. **Consistent visual treatment.** Active filters show as removable chips. "Clear all" is always in the same place. Filter count badge is consistent.

## Breadcrumbs

Related code and decisions found in the current codebase:

### Examples of current inconsistency
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — 11+ useState hooks for filters (lines 59-73), custom handlers for each (`handlePostedFilterChange`, `handleAnalyzedFilterChange`, `handleMonthFilterChange`), ad-hoc clear-all (`clearFilters` line 240), manual `hasActiveFilters` check (line 266)
- `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` — minimal single-filter pattern (line 21), different `handleFilterChange` shape
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx` — no filters at all despite the page being filter-heavy
- `apps/visualizer/frontend/src/components/processing/DescriptionsTab.tsx` — another independent filter implementation
- `apps/visualizer/frontend/src/components/analytics/UnpostedCatalogPanel.tsx` — yet another filter implementation
- `apps/visualizer/frontend/src/pages/AnalyticsPage.tsx` — `AppliedFilters` (from/to/granularity) state and bespoke filter UI (line 45+); should migrate to shared framework

### Existing primitives that could be reused
- `apps/visualizer/frontend/src/hooks/useDebouncedValue.ts` — already used for keyword/color debouncing; would live inside the new hook
- `apps/visualizer/frontend/src/components/ui/` — existing UI primitives (Card, Button, Badge) would be used by the filter components

### API layer (mostly consistent filter params already)
- `apps/visualizer/frontend/src/services/api.ts` — `ImagesAPI.listCatalog()` accepts a rich filter object; the backend is already parameterized, so the frontend framework can map filter values to query params uniformly
- `apps/visualizer/backend/api/images.py` — handles the query params

### Related seeds
- SEED-005 (natural language search) — a structured filter framework is the backbone that natural-language queries would ultimately compile into
- SEED-003 (rethink Identity page) — the Identity page would also benefit from consistent filter UI
- SEED-009 (posted vs unposted on Insights top photos) — depends on the posted tri-state filter from this framework

## Notes

The key design principle: **declarative over imperative**. Each page/tab declares "I want these filters" and gets a fully-working, consistent filter experience for free. No more copy-pasting useState hooks and custom handlers.

A reasonable phased rollout within the milestone:
- **Phase 1:** Design the schema + build the core primitives (toggle, select, date-range, search). Build `useFilters` hook with debouncing and clear-all.
- **Phase 2:** Migrate CatalogTab (most complex filter set — good stress test). Validate the API works for real cases.
- **Phase 3:** Migrate remaining tabs (Instagram, Matches, Descriptions, Matching). Add missing filters where they make sense.
- **Phase 4:** Add URL sync so filter state survives reloads and deep-links. Add saved-filter presets if time permits.

Consider whether filters should sync to URL params (`?posted=true&month=2025-03`) for shareable filtered views. This is a meaningful UX upgrade and is easier to design in from the start than retrofit later.

## Amendments

**2026-04-17:** Added Analytics page (`AnalyticsPage.tsx` with its bespoke `AppliedFilters` from/to/granularity UI) as another consumer of the shared filter framework. Also linked to SEED-009 (posted vs unposted on Insights top photos), which depends on the posted tri-state toggle this framework provides. User confirmed Analytics filter reuse during the planting of SEED-009.
