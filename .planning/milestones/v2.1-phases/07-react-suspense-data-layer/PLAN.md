---
phase: 7
title: React Suspense data layer (no deps)
depends_on: []
plans:
  - 01-core-primitives
  - 02-migrate-identity
  - 03-migrate-images
  - 04-migrate-processing
  - 05-migrate-analytics-dashboard
  - 06-invalidation-audit
---

# Phase 7 — React Suspense data layer

See `CONTEXT.md` for problem statement, decisions, and architecture sketch.

## Plan 01 — Core primitives

**Files added:**
- `apps/visualizer/frontend/src/data/cache.ts`
- `apps/visualizer/frontend/src/data/query.ts`
- `apps/visualizer/frontend/src/data/useQuery.ts`
- `apps/visualizer/frontend/src/data/invalidate.ts`
- `apps/visualizer/frontend/src/data/ErrorBoundary.tsx`
- `apps/visualizer/frontend/src/data/ErrorState.tsx`
- `apps/visualizer/frontend/src/data/index.ts`
- `apps/visualizer/frontend/src/data/__tests__/cache.test.ts`
- `apps/visualizer/frontend/src/data/__tests__/query.test.ts`
- `apps/visualizer/frontend/src/data/__tests__/invalidate.test.ts`
- `apps/visualizer/frontend/src/data/__tests__/ErrorBoundary.test.tsx`

**Tasks:**

1. `cache.ts` — `Map<string, CacheEntry>` module-level. Exports `getEntry`, `setEntry`, `deleteEntry`, `deleteMatching(predicate)`. Keys are stringified from `readonly unknown[]` via stable `JSON.stringify` (document: no object literals as keys — use primitives).
2. `query.ts` — `query<T>(key, fetcher): T` — if entry is missing, create a pending entry (status + promise), kick off the fetch, attach resolve/reject handlers that mutate the entry, then `throw entry.promise`. If pending, `throw entry.promise`. If fulfilled, return value. If rejected, throw error (caught by boundary).
3. `useQuery.ts` — `useQuery<T>(key, fetcher) = query(key, fetcher)`. (Wrapper exists so future migrations can add hook-scoped behavior without touching call sites.)
4. `invalidate.ts` — `invalidate(key)` = `deleteEntry(stringify(key))`. `invalidateAll(prefix)` = `deleteMatching(k => k.startsWith(stringify(prefix)))`. No re-render trigger; components re-suspend on the next render they schedule (mutations own that).
5. `ErrorBoundary.tsx` — class component, React-only. Props: `fallback: (props: { error, reset }) => ReactNode`. Renders fallback with `reset` that clears state. Key off `resetKeys?: unknown[]` for automatic reset.
6. `ErrorState.tsx` — default fallback used everywhere. Takes `error` + `reset`, renders `MSG_ERROR_GENERIC` + Retry button. Parameterized `title` prop.
7. Unit tests:
   - `cache`: set/get/delete, deleteMatching with prefix.
   - `query`: first call throws a promise; second call while pending returns same promise; on resolve, returns value; on reject, throws error; after invalidate, refetches.
   - `invalidate`: removes entry; prefix invalidation removes only matching.
   - `ErrorBoundary`: catches render error, calls fallback with `error`; `reset` re-renders children; `resetKeys` change resets automatically.

**Acceptance:**
- `npx tsc --noEmit` clean.
- `npx vitest run src/data` all green.
- No UI changes yet; phase exit = primitives exist + tested.

---

## Plan 02 — Migrate Identity page

**Files modified:**
- `apps/visualizer/frontend/src/pages/IdentityPage.tsx`
- `apps/visualizer/frontend/src/components/identity/BestPhotosGrid.tsx`
- `apps/visualizer/frontend/src/components/identity/StyleFingerprintPanel.tsx`
- `apps/visualizer/frontend/src/components/identity/PostNextSuggestionsPanel.tsx`
- `apps/visualizer/frontend/src/pages/IdentityPage.test.tsx`

**Tasks:**

1. Wrap `IdentityPage` children in `<ErrorBoundary fallback={ErrorState}><Suspense fallback={<SkeletonGrid count={24} />}>…</Suspense></ErrorBoundary>`. One boundary per logical section (fingerprint, best photos, suggestions) so one failure doesn't blank the whole page.
2. `BestPhotosGrid`:
   - Drop `rows / total / meta / loading / error / load` state.
   - `const data = useQuery(['identity.bestPhotos', page], () => IdentityAPI.getBestPhotos({ limit: 24, offset: (page-1)*24 }))`.
   - `page` stays as local `useState` (it's UI state, not server state).
   - Remove the `if (loading)` skeleton branch — Suspense owns it.
   - Remove the `if (error)` branch — boundary owns it.
3. `StyleFingerprintPanel`: same treatment, key `['identity.styleFingerprint']`.
4. `PostNextSuggestionsPanel`: key `['identity.suggestions', page]`.
5. Update `IdentityPage.test.tsx`:
   - Mocks of `IdentityAPI` unchanged.
   - Assertions switch from checking "Loading..." text to checking skeleton role / image counts after `await screen.findBy…`.
   - Add one test per section verifying error boundary catches API rejection and shows retry.

**Acceptance:**
- All existing `IdentityPage.test.tsx` cases pass (possibly rewritten).
- Manual check: on reload, backend log shows exactly 1 call each to `best-photos`, `style-fingerprint`, `suggestions` (not 2, not 4).
- `npx tsc --noEmit` + `npx vitest run` green.

---

## Plan 03 — Migrate Images page

**Files modified (non-exhaustive, update as uncovered):**
- `apps/visualizer/frontend/src/pages/ImagesPage.tsx` (wrap Suspense boundaries per tab)
- `apps/visualizer/frontend/src/components/images/InstagramTab.tsx`
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx`
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx`
- `apps/visualizer/frontend/src/components/images/InstagramDumpSettingsPanel.tsx`
- `apps/visualizer/frontend/src/components/images/CatalogSettingsPanel.tsx`
- `apps/visualizer/frontend/src/components/image-view/ImageDetailModal.tsx`
- `apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx`
- `apps/visualizer/frontend/src/components/DescriptionPanel/AIDescriptionSection.tsx`
- `apps/visualizer/frontend/src/stores/matchOptionsContext.tsx`
- Corresponding `__tests__` files.

**Tasks:**

1. Catalog every fetch call in these files. Give each a stable key: `['images.catalog', filters]`, `['images.instagram', filters]`, `['matches.list', filters]`, `['images.detail', type, key]`, `['descriptions', type, key]`, etc.
2. Replace `useEffect` fetch + state with `useQuery`.
3. Modals: keep the modal-level `Suspense` inside the portal so opening a modal doesn't flash the parent page's skeleton. Use a compact `<ModalSkeleton>` fallback.
4. `matchOptionsContext`: convert its internal `useEffect`+`setState` to `useQuery`. Provider stays; consumers change nothing.
5. Update all affected test files. Add retry-on-error coverage for at least ImageDetailModal and MatchDetailModal.

**Acceptance:**
- All tests green.
- Opening any image/match modal does not refetch data already in cache for the list view (same key = cache hit).
- `vite build` succeeds.

---

## Plan 04 — Migrate Processing page

**Files modified:**
- `apps/visualizer/frontend/src/pages/ProcessingPage.tsx`
- `apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx`
- `apps/visualizer/frontend/src/components/processing/PerspectivesTab.tsx`
- `apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx`
- `apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx`
- `apps/visualizer/frontend/src/components/processing/JobsHealthBanner.tsx`
- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx`
- Corresponding `__tests__` files.

**Tasks:**

1. Jobs list: `['jobs.list', { limit, offset, status }]`. Invalidated by `useJobSocket`'s `job_created` / `job_updated` handlers (this is the one exception: pub/sub invalidates cache).
2. Job detail: `['jobs.detail', jobId]`. Invalidated by `job_updated` if id matches.
3. Providers / Perspectives / Catalog cache tabs: one key per tab, invalidated by that tab's mutations.
4. JobsHealthBanner: `['jobs.health']`, manually invalidated after relevant actions.

**Acceptance:**
- Processing page behavior unchanged from user's perspective.
- Tests green.
- Backend log: `/api/jobs` count matches visible UI refreshes, no phantom polling.

---

## Plan 05 — Migrate Analytics / Dashboard / remaining

**Files modified:**
- `apps/visualizer/frontend/src/pages/AnalyticsPage.tsx`
- `apps/visualizer/frontend/src/pages/DashboardPage.tsx`
- `apps/visualizer/frontend/src/components/analytics/UnpostedCatalogPanel.tsx`
- `apps/visualizer/frontend/src/components/catalog/ImageScoresPanel.tsx`
- `apps/visualizer/frontend/src/hooks/useProviders.ts`
- `apps/visualizer/frontend/src/hooks/useSingleMatch.ts`
- Corresponding `__tests__` files.

**Tasks:**

1. Standard migration per call site.
2. `useProviders` becomes a ~3-line wrapper over `useQuery(['providers.defaults'], …)`. All current consumers keep the same hook signature.
3. `useSingleMatch` likewise.
4. Delete now-unused loading/error state code across these files.

**Acceptance:**
- All `useEffect` fetch blocks gone from the codebase (verified by grep: `rg "useEffect.*\\n.*API\\." src` returns 0 matches — update regex to whatever actually catches them).
- Full test suite green.

---

## Plan 06 — Invalidation audit

**Files modified:**
- `apps/visualizer/frontend/src/services/api.ts` (add invalidation calls inside mutation methods — or document that call sites do it)
- Any remaining components where mutations existed before migration.

**Tasks:**

1. Enumerate every mutation on the frontend (validate match, reject match, generate description, run scoring, create job, etc.).
2. For each, define the list of cache-key prefixes it must invalidate. Add a table to `CONTEXT.md`.
3. Choose ONE placement rule: mutations invalidate at the API layer (inside `MatchingAPI.validate` etc.). Document it.
4. Remove any leftover manual `load()` / `refetch()` calls from components.
5. Add tests that assert: after mutation X runs, the next read of key Y triggers a fresh network call.

**Acceptance:**
- Invalidation table exists in `CONTEXT.md`.
- No component calls a manual `reload`/`refetch`/`load` function after a mutation — all flow through `invalidate`.
- Mutation tests green.
- Backend log UAT: validate a match; verify `matches.list` refetches but `providers.defaults` does not.

---

## Phase acceptance (rolls up all plans)

1. Zero hand-rolled `useEffect` + `setState` fetch blocks remain.
2. Every route has `<ErrorBoundary><Suspense>` wrapping.
3. Backend log audit: reloading any page fires each unique endpoint exactly once.
4. No new dependencies in `package.json`.
5. `npx tsc --noEmit` clean.
6. `npx vitest run` all green.
7. `npx vite build` succeeds.
8. Full app manual walkthrough: Identity, Images (all tabs), Processing, Analytics, Dashboard — no user-visible regressions, noticeably faster repeat navigation (cache hits).
