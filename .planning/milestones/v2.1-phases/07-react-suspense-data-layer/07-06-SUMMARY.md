---
phase: 7
plan: 06
slug: invalidation-audit
status: complete
completed: 2026-04-23
key-files:
  modified:
    - apps/visualizer/frontend/src/services/api.ts
    - apps/visualizer/frontend/src/services/__tests__/api.test.ts
    - apps/visualizer/frontend/src/hooks/useProviders.ts
    - apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx
    - apps/visualizer/frontend/src/components/processing/PerspectivesTab.tsx
    - apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
    - .planning/phases/07-react-suspense-data-layer/CONTEXT.md
---

# Plan 06 Summary — Invalidation audit

## What was built

All write/mutation helpers in `services/api.ts` were enumerated (only this module defines frontend HTTP mutations today). Each mutation now awaits the network call, then runs the appropriate `invalidate` / `invalidateAll` so Suspense query keys refetch without ad hoc `load()`/`refetch()` at call sites. Duplicate invalidation after the same API call was removed from `JobDetailModal` (retry), `useProviders.updateFallbackOrder`, `ProvidersTab` (fallback-order and defaults save), and `PerspectivesTab` (perspective CRUD now relies on API invalidation plus minimal `setListRev` / `setSelectedSlug` where a re-render is still required). The invalidation contract is documented in `CONTEXT.md`.

## Mutations catalogued

Sixteen mutation endpoints across **PerspectivesAPI** (4), **JobsAPI** (3), **ConfigAPI** (2), **MatchingAPI** (2), **DescriptionsAPI** (1), and **ProvidersAPI** (5). **Read-only** surfaces (e.g. `ImagesAPI`, `ScoresAPI`, `AnalyticsAPI`, `IdentityAPI`, `SystemAPI`, `DumpMediaAPI`) have no invalidation added.

## Invalidation placement

Per **D-2**, invalidation runs inside each mutation method in `api.ts` after a successful response. **Exception (documented in CONTEXT):** `JobsAPI.create` does not invalidate description or image-detail keys for `single_describe`, because work is asynchronous and completion already triggers cache clears via `useJobSocket` and `AIDescriptionSection`.

## Remaining manual load() calls

**None** in application source. The only `grep` hit for `load(` in `src` was `fireEvent.load` in a thumbnail unit test (unrelated).

## Verification

- `npx tsc --noEmit`: PASS
- `npx vitest run`: PASS (248 tests)
- `npx vite build`: PASS

## Final fetch useEffect audit

Command:

`grep -rn "useEffect" apps/visualizer/frontend/src … | grep "API\." | head -20`

**Result:** no matching lines (exit code 1). No `useEffect` blocks in non-test source combine `useEffect` with direct `SomethingAPI.` fetch calls on the same line.

## Self-Check: PASSED
