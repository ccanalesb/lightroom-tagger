---
phase: 7
plan: 01
slug: core-primitives
status: complete
completed: 2026-04-23
key-files:
  created:
    - apps/visualizer/frontend/src/data/cache.ts
    - apps/visualizer/frontend/src/data/query.ts
    - apps/visualizer/frontend/src/data/useQuery.ts
    - apps/visualizer/frontend/src/data/invalidate.ts
    - apps/visualizer/frontend/src/data/ErrorBoundary.tsx
    - apps/visualizer/frontend/src/data/ErrorState.tsx
    - apps/visualizer/frontend/src/data/index.ts
    - apps/visualizer/frontend/src/data/__tests__/cache.test.ts
    - apps/visualizer/frontend/src/data/__tests__/query.test.ts
    - apps/visualizer/frontend/src/data/__tests__/invalidate.test.ts
    - apps/visualizer/frontend/src/data/__tests__/ErrorBoundary.test.tsx
---

# Plan 01 Summary — Core Suspense primitives

## What was built
Introduced `src/data/` module: module-level cache, `query()` with Suspense throw-promise protocol, `useQuery` wrapper, `invalidate`/`invalidateAll` helpers, custom `ErrorBoundary` class component, and shared `ErrorState` fallback. Full unit test coverage. No UI changes in this plan.

## Verification
- `npx tsc --noEmit`: PASS
- `npx vitest run src/data`: PASS (all tests green)

## Self-Check: PASSED
