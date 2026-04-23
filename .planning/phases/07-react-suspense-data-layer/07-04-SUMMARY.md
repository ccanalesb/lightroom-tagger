---
phase: 7
plan: 04
slug: migrate-processing
status: complete
completed: 2026-04-23
key-files:
  modified:
    - apps/visualizer/frontend/src/pages/ProcessingPage.tsx
    - apps/visualizer/frontend/src/components/processing/AnalyzeTab.tsx
    - apps/visualizer/frontend/src/components/processing/PerspectivesTab.tsx
    - apps/visualizer/frontend/src/components/processing/ProvidersTab.tsx
    - apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx
    - apps/visualizer/frontend/src/components/processing/JobsHealthBanner.tsx
    - apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx
    - apps/visualizer/frontend/src/components/processing/MatchingTab.tsx
    - apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
    - apps/visualizer/frontend/src/hooks/useJobSocket.ts
---

# Plan 04 Summary — Migrate Processing page

## What was built

The Processing route now reads server state through the shared Suspense cache (`useQuery`) with tab-level `ErrorBoundary` + `Suspense` boundaries (aligned with ImagesPage). Pagination for the job queue stays in local React state; the jobs fetch uses cache keys `['jobs.list', { limit, offset, rev }]`, with `rev` driven by `useJobSocket` so websocket-driven invalidations actually re-render and refetch. `useJobSocket` centralizes `invalidate` / `invalidateAll` for jobs list, job detail, and health, and exposes `refreshJobList`, `jobListRevision`, and `healthRevision` for query keys and the health banner.

## Components migrated

- **ProcessingPage** — `JobQueueTabWithData` uses `useQuery` for `JobsAPI.list`; tabs wrapped in error/suspense fallbacks; passes `refreshJobList` / `healthRevision` downstream.
- **JobQueueTab** — drops `setJobs`; cancel/retry call `onInvalidateJobList` (same as refresh).
- **MatchingTab / AnalyzeTab / CatalogCacheTab** — optional `onJobEnqueued` calls `refreshJobList` after successful job creation.
- **JobsHealthBanner** — `useQuery(['jobs.health', pollTick, cacheRevision])` with polling via key bump + `invalidateAll(['jobs.health'])`; errors handled with `ErrorBoundary`.
- **CatalogCacheTab** — `useQuery(['catalog.cache.stats', listRev])` for `/api/cache/status`.
- **ProvidersTab** — single `useQuery(['providers.list', bundleRev])` for list, fallback order, and defaults; mutations bump revision / invalidate.
- **PerspectivesTab** — `useQuery` for list and per-slug detail (editor in nested `Suspense`); mutations invalidate list/detail prefixes.
- **AnalyzeTab** — `useQuery` for active perspectives and provider defaults (shared keys with other features where applicable).
- **JobDetailModal** — portal keeps `ErrorBoundary` + inner `Suspense`; body uses `useQuery(['jobs.detail', jobId])` for the initial `logs_limit: 20` fetch; log/metadata expansion remains local state; socket merge behavior preserved.

## Invalidation wiring

`useJobSocket` registers `job_created`, `job_updated`, and `jobs_recovered` (when a callback is passed). Each bumps list and health revisions and calls `invalidateAll(['jobs.list'])`, `invalidateAll(['jobs.health'])`, and on update `invalidate(['jobs.detail', job.id])`, then optional user callbacks (e.g. recovered banner).

## Verification

- `npx tsc --noEmit`: PASS
- `npx vitest run src/components/processing src/components/jobs src/pages/ProcessingPage src/hooks/__tests__/useJobSocket.test.ts`: PASS (37 tests)

## Self-Check: PASSED
