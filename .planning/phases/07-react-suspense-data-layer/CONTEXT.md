# Phase 7 — React Suspense data layer (no deps)

## Problem

Every data-fetching component in `apps/visualizer/frontend` uses the same hand-rolled pattern:

```ts
const [data, setData] = useState(null)
const [loading, setLoading] = useState(true)
const [error, setError] = useState<string | null>(null)
useEffect(() => { /* fetch, setState */ }, [deps])
```

Consequences observed in production use:

- **Duplicate requests.** `/api/providers/defaults` fired 4× in a row on Identity page load. `best-photos` / `style-fingerprint` / `suggestions` refetch on every remount.
- **Ghost connections.** No shared request dedup → no shared cache → each modal / panel opens its own Socket.IO session (fixed separately, but symptom of the same root cause).
- **Inconsistent loading UI.** Some components show `<SkeletonGrid>`, others show `"Loading..."` text, others show nothing. No structural enforcement.
- **Error handling drift.** Every component re-implements "try/catch → setError → render error text".
- **No invalidation story.** After a mutation (validate match, generate description), components have to manually call `load()` again. Easy to miss.

## Goal

Introduce a minimal **React-only** (no new deps) Suspense + cache layer that:

1. Deduplicates in-flight requests by key.
2. Caches completed responses indefinitely (per browser session).
3. Lets components read data via `use(promise)` so `<Suspense fallback>` works uniformly.
4. Provides explicit `invalidate(key)` for mutations.
5. Delivers errors to page-level `<ErrorBoundary>` components with a shared `<ErrorState>` fallback.

Migrate **every** `useEffect`+`setState`+API call site in the frontend. ~24 files identified.

## Decisions (from ideation)

- **D-1. Scope:** All fetch call sites in `apps/visualizer/frontend/src`. One phase, not a pilot. (User choice A.)
- **D-2. Invalidation:** Manual. Mutations call `invalidate(key)` or `invalidateAll(prefix)`. No socket-driven auto-invalidation in this phase. (User choice A.)
- **D-3. Eviction:** Never. Cache persists for the tab's lifetime. No TTL / LRU. (User choice A.)
- **D-4. Errors:** Page-level `<ErrorBoundary>` + shared `<ErrorState>` fallback. Drop per-component `error` state. (User choice A.)
- **D-5. No external libraries.** No React Query, SWR, TanStack anything. Plain React 19 primitives (`use`, `Suspense`, `ErrorBoundary` from `react-error-boundary`… **not allowed** — we write a tiny one ourselves).
- **D-6. DRY / KISS.** One cache module, one `useQuery` wrapper, one `useMutation` helper. Components go from ~15 lines of fetch plumbing to 1 line of `use(query(...))`.

## Non-goals

- No background refetching / stale-while-revalidate.
- No optimistic updates (mutations invalidate + re-suspend).
- No websocket → cache bridge (tracked as follow-up).
- No changes to backend API shapes.
- No migration of `useJobSocket` (pub/sub, not request/response — stays as-is).

## Architecture sketch

```
src/data/
  cache.ts           # Map<key, { status, promise, value, error }>
  query.ts           # query(key, fetcher) -> throws promise | returns value
  useQuery.ts        # thin wrapper: useQuery(key, fetcher) = use(query(...))
  invalidate.ts      # invalidate(key), invalidateAll(prefix)
  ErrorBoundary.tsx  # React-only (no react-error-boundary dep)
  ErrorState.tsx     # shared error fallback
```

Call site before:

```tsx
const [rows, setRows] = useState([])
const [loading, setLoading] = useState(true)
const [error, setError] = useState<string | null>(null)
useEffect(() => {
  IdentityAPI.getBestPhotos({ limit: 24, offset }).then(d => {
    setRows(d.items); setLoading(false)
  }).catch(e => { setError(e.message); setLoading(false) })
}, [offset])
if (loading) return <SkeletonGrid />
if (error) return <ErrorState message={error} />
return <Grid rows={rows} />
```

Call site after:

```tsx
const data = useQuery(['identity.bestPhotos', offset], () =>
  IdentityAPI.getBestPhotos({ limit: 24, offset }))
return <Grid rows={data.items} />
```

Wrapped at page level:

```tsx
<ErrorBoundary fallback={ErrorState}>
  <Suspense fallback={<SkeletonGrid count={24} />}>
    <BestPhotosGrid />
  </Suspense>
</ErrorBoundary>
```

## Risks

- **R-1. Render loop if cache key is unstable.** Mitigation: keys are primitive arrays; document "no object literals"; add a dev-mode warning.
- **R-2. Hard-coded `error` UI lost.** Mitigation: catalog every existing error string before migration; mapper in `<ErrorState>` chooses wording per boundary context via prop.
- **R-3. Mutation invalidation misses.** Mitigation: co-locate `invalidate` calls in the mutation helpers (`MatchingAPI.validate` etc.) rather than leaving it to call sites. Write invalidation rules in a table.
- **R-4. Tests break en masse.** Mitigation: Migration wave-by-wave (see plans), each wave keeps `tsc` + `vitest` green before moving on.

## Plans in this phase

1. `01-core-primitives` — cache, query, useQuery, invalidate, ErrorBoundary, ErrorState. No UI touched. Full unit tests.
2. `02-migrate-identity` — IdentityPage + BestPhotosGrid + StyleFingerprintPanel + PostNextSuggestionsPanel. First real consumer; proves the pattern end-to-end.
3. `03-migrate-images` — InstagramTab, CatalogTab, MatchesTab, ImageDetailModal, MatchDetailModal, AIDescriptionSection, settings panels, MatchOptionsContext.
4. `04-migrate-processing` — ProcessingPage, AnalyzeTab, PerspectivesTab, ProvidersTab, CatalogCacheTab, JobDetailModal, JobsHealthBanner.
5. `05-migrate-analytics-dashboard` — AnalyticsPage, DashboardPage, UnpostedCatalogPanel, ImageScoresPanel, remaining hooks (`useProviders`, `useSingleMatch`).
6. `06-invalidation-audit` — go through every mutation endpoint, wire `invalidate()` calls, write the rule table, remove any leftover `load()` manual refetches.

## Success criteria

1. Zero `useEffect` blocks whose sole purpose is fetching state remain in `apps/visualizer/frontend/src`.
2. Every page route is wrapped in `<ErrorBoundary><Suspense>…</Suspense></ErrorBoundary>`.
3. `/api/providers/defaults` (or any endpoint) fires at most once per unique key per session (verified via backend log grep in UAT).
4. `npx tsc --noEmit`, `npx vitest run`, `npx vite build` all green.
5. No new runtime dependencies added to `package.json`.
6. Loading UI across the app is a single shared `<SkeletonGrid>` family (no stray `"Loading..."` text nodes).

## Out of scope / follow-ups

- Websocket event → `invalidate(key)` bridge.
- Route-level prefetching.
- Suspense-aware mutations (optimistic UI).
