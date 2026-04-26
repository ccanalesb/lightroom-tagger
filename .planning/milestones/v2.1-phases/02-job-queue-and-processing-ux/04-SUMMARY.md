---
plan: 04
title: ProcessingPage pagination state and JobQueueTab pagination rendering
status: completed
wave: 2
commits:
  - f9ad343
---

# Summary

Lifted pagination state into `ProcessingPage`, converted socket-driven live updates to a debounced refetch of the current page slice, and rendered the existing `<Pagination>` primitive inside the jobs Card.

## Changes

- `apps/visualizer/frontend/src/pages/ProcessingPage.tsx`:
  - Module-level `PAGE_SIZE = 50`.
  - New state: `jobsTotal`, `jobsOffset`, `refreshTimerRef`.
  - `refreshJobs(offsetOverride?)` now hits `JobsAPI.list({ limit: PAGE_SIZE, offset })` and unwraps `.data` / `.total` from the paginated envelope.
  - Initial load + page-change load are driven by a `[jobsOffset]`-dependent `useEffect`.
  - `scheduleRefresh()` uses plain `setTimeout` + `useRef` for a 400ms trailing debounce; both `handleJobCreated` and `handleJobUpdated` now simply call `scheduleRefresh()` instead of mutating `jobs` in place.
  - Cleanup effect clears the pending timer on unmount.
  - `JobQueueTab` is passed `pagination={{ offset, limit, total }}` and `onOffsetChange={setJobsOffset}`.
- `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx`:
  - New `JobQueueTabPagination` interface and two new props (`pagination`, `onOffsetChange`).
  - Derived `currentPage`, `totalPages`, `rangeStart`, `rangeEnd`, and `handlePageChange`.
  - Pagination footer (range label + `<Pagination>`) renders **inside** the same `<Card padding="none">` as the jobs table, with a `border-t border-border` separator mirroring `CatalogTab`. Only rendered when `total > limit`.
  - Range label uses `JOB_QUEUE_PAGINATION_RANGE(start, end, total)` — no inline English.
  - Cancel/retry optimistic UI left intact (still mutates current slice; a socket event triggers the debounced refetch right after).
- `apps/visualizer/frontend/src/components/processing/__tests__/JobQueueTab.test.tsx` (new, 4 tests):
  - Hides pagination when `total <= limit`.
  - Shows pagination + range label when `total > limit`.
  - Clicking Next fires `onOffsetChange(offset + limit)`.
  - Correct `Showing 51–100 of 175` label on page 2.

## Verification

- `npx tsc --noEmit` — clean (pre-existing `MatchDetailModal` Timeout errors unrelated).
- `npx vitest run src/components/processing/__tests__/JobQueueTab.test.tsx` — 4/4 pass.
- `npx eslint src/pages/ProcessingPage.tsx src/components/processing/JobQueueTab.tsx ...` — clean.

## Deviations / Notes

- Followed the plan's note on **not** adopting `usePagination` here — that hook owns its own `offset`, while the Pagination ↔ live-updates contract requires `offset` to live in `ProcessingPage`. Captured as a Phase 4+ follow-up (generalize `usePagination` to accept external offset) rather than done in-plan.
- Left `setJobs` prop on `JobQueueTab` intact so the cancel/retry optimistic UI continues to work on the current slice.
