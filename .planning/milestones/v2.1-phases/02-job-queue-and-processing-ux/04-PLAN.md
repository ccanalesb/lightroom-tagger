---
plan: 04
title: ProcessingPage pagination state and JobQueueTab pagination rendering
wave: 2
depends_on: [02]
files_modified:
  - apps/visualizer/frontend/src/pages/ProcessingPage.tsx
  - apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx
  - apps/visualizer/frontend/src/components/processing/__tests__/JobQueueTab.test.tsx
autonomous: true
requirements:
  - JOB-05
---

<objective>
Make the Processing → Job Queue tab paginated and stable under live updates. Lift pagination state (`limit`, `offset`, `total`) into `ProcessingPage`, switch to the paginated `JobsAPI.list` envelope, and render the existing `Pagination` primitive inside `JobQueueTab`. Socket events (`job_created`, `job_updated`) must no longer mutate the jobs array in place — they must **debounce a refetch of the current page slice** so pagination stays accurate. Delivers JOB-05.
</objective>

<context>
Implements **D-15 through D-23** and the Pagination ↔ live-updates contract (the "D-20/D-21/D-22" block in 02-CONTEXT.md):
- **D-15:** Default page size on the frontend is **50**, aligned with the implicit backend cap and SEED-013's guidance. No user-facing page-size control.
- **D-16:** `JobQueueTab` consumes the existing `<Pagination>` primitive and the existing `usePagination` hook for offset/currentPage/totalPages bookkeeping. No new pagination primitive is introduced.
- **D-17:** The `<Pagination>` component renders **inside** the same `<Card>` as the jobs table (matching `CatalogTab`'s pattern), underneath the `</table>` element. Hidden automatically when `totalPages <= 1` (existing `Pagination` behaviour).
- **D-18:** Any filter change (currently no status filter is wired; D-18 is a forward-guarantee) MUST reset the page to 1 via `reset()`. This plan does not wire a new filter, but the hook contract is preserved for Phase 4 consumers.
- **D-19:** The `"Refresh"` button keeps the current page — it re-fetches the current `{limit, offset}` slice.
- **Pagination ↔ live updates (CONTEXT "Pagination ↔ live updates contract" section):** Socket `job_created` / `job_updated` events schedule a debounced `refreshJobs()` (400ms trailing, coalescing) that re-requests the current slice, instead of mutating the `jobs` array in place. This is the single most important behavioural change in Phase 2.
- **D-22:** 400ms trailing debounce falls in the 250–500ms band CONTEXT specifies.
- **D-23:** The cancel/retry optimistic UI inside `JobQueueTab` still mutates `jobs` in place — that's allowed because it is confined to the currently-displayed page slice and a server-sourced refetch follows via socket.
- Previously, `handleJobCreated` prepended and `handleJobUpdated` mapped in-place over the `jobs` array. Under pagination, that would silently drift the displayed slice (e.g. a new job arriving while the user is on page 2 would bloat page 1 in state). The debounced refetch fixes this.
- Implementation detail: debounce is a plain `setTimeout` + `useRef` — no `lodash.debounce` dependency.
- Tab switching (matching ↔ jobs ↔ settings) preserves `offset` and `jobs` because all pagination state lives in `ProcessingPage`, not inside the tab content.
</context>

<tasks>
<task id="4.1">
<action>
Rewrite `ProcessingPage` state, effects, and callbacks in `apps/visualizer/frontend/src/pages/ProcessingPage.tsx` to manage paginated job state. Change summary:

1. Add `PAGE_SIZE = 50` module-level constant (above `PROCESSING_TAB_IDS`). Matches D-15 and the backend default `limit=50` from plan 01.
2. Replace the `jobs` / `jobsLoading` state block (lines 53–55) with:

```ts
const [jobs, setJobs] = useState<Job[]>([]);
const [jobsLoading, setJobsLoading] = useState(true);
const [jobsTotal, setJobsTotal] = useState(0);
const [jobsOffset, setJobsOffset] = useState(0);
const [jobsRecoveredBanner, setJobsRecoveredBanner] = useState<string | null>(null);
const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
```

3. Add `useRef` to the existing react import (currently `import { useCallback, useEffect, useMemo, useState } from 'react';`), making it:

```ts
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
```

4. Replace `refreshJobs` (lines 57–67) with a version that takes an explicit `offsetOverride?: number` so socket refetches always hit the **current** `jobsOffset`, and unwraps the new envelope:

```ts
const refreshJobs = useCallback(async (offsetOverride?: number) => {
  const nextOffset = offsetOverride ?? jobsOffset;
  setJobsLoading(true);
  try {
    const response = await JobsAPI.list({ limit: PAGE_SIZE, offset: nextOffset });
    setJobs(Array.isArray(response?.data) ? response.data : []);
    setJobsTotal(typeof response?.total === 'number' ? response.total : 0);
  } catch (err) {
    console.error('Failed to load jobs:', err);
  } finally {
    setJobsLoading(false);
  }
}, [jobsOffset]);
```

5. Replace the initial-load `useEffect` (lines 69–89) with:

```ts
useEffect(() => {
  let mounted = true;
  async function load() {
    try {
      const response = await JobsAPI.list({ limit: PAGE_SIZE, offset: jobsOffset });
      if (!mounted) return;
      setJobs(Array.isArray(response?.data) ? response.data : []);
      setJobsTotal(typeof response?.total === 'number' ? response.total : 0);
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      if (mounted) setJobsLoading(false);
    }
  }
  void load();
  return () => {
    mounted = false;
  };
}, [jobsOffset]);
```

The `jobsOffset` dependency means any page change automatically refetches the new slice.

6. Replace `handleJobCreated` and `handleJobUpdated` (lines 91–97) with a single shared debounced refetch scheduler:

```ts
const scheduleRefresh = useCallback(() => {
  if (refreshTimerRef.current) {
    clearTimeout(refreshTimerRef.current);
  }
  refreshTimerRef.current = setTimeout(() => {
    void refreshJobs();
  }, 400);
}, [refreshJobs]);

useEffect(() => {
  return () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }
  };
}, []);

const handleJobCreated = useCallback(() => {
  scheduleRefresh();
}, [scheduleRefresh]);

const handleJobUpdated = useCallback(() => {
  scheduleRefresh();
}, [scheduleRefresh]);
```

**Do not remove** `setJobs` from the `JobQueueTab` props — `JobQueueTab` still mutates individual rows optimistically inside `cancelJob` / `retryJob`, which is acceptable because those optimistic writes are confined to the currently-displayed slice and a server-sourced refetch follows via socket anyway.

7. Update the `JobQueueTab` props usage (lines 123–130) to pass pagination props:

```tsx
<JobQueueTab
  jobs={jobs}
  setJobs={setJobs}
  jobsLoading={jobsLoading}
  connected={connected}
  onRefreshJobs={() => refreshJobs()}
  pagination={{
    offset: jobsOffset,
    limit: PAGE_SIZE,
    total: jobsTotal,
  }}
  onOffsetChange={setJobsOffset}
/>
```

Leaving `setJobs` in place keeps cancel/retry's optimistic UI working unchanged; the next socket event will trigger the debounced refetch and re-sync.
</action>
<read_first>
- apps/visualizer/frontend/src/pages/ProcessingPage.tsx
- apps/visualizer/frontend/src/services/api.ts (after plan 02 applied)
- apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx
</read_first>
<acceptance_criteria>
- `rg -n "const PAGE_SIZE = 50;" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
- `rg -n "const \[jobsTotal, setJobsTotal\]" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
- `rg -n "const \[jobsOffset, setJobsOffset\]" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
- `rg -n "JobsAPI\.list\(\{ limit: PAGE_SIZE, offset" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches at least 2 lines
- `rg -n "const scheduleRefresh" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
- `rg -n "refreshTimerRef\.current = setTimeout" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
- `rg -n "onOffsetChange=\{setJobsOffset\}" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
</acceptance_criteria>
</task>

<task id="4.2">
<action>
Extend `JobQueueTabProps` in `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` to accept pagination and render the `<Pagination>` primitive **inside** the same `<Card>` as the jobs table (matching `CatalogTab`'s pattern per D-17). The existing `usePagination` hook (`apps/visualizer/frontend/src/hooks/usePagination.ts`) is **not** imported in this plan — see the "Why not `usePagination`" note below.

Add imports (after existing imports):

```ts
import { Pagination } from '../ui/Pagination';
import { JOB_QUEUE_PAGINATION_RANGE } from '../../constants/strings';
```

Extend the props interface (currently lines 30–36):

```ts
export interface JobQueueTabPagination {
  offset: number;
  limit: number;
  total: number;
}

export interface JobQueueTabProps {
  jobs: Job[];
  setJobs: Dispatch<SetStateAction<Job[]>>;
  jobsLoading: boolean;
  connected: boolean;
  onRefreshJobs: () => void | Promise<void>;
  pagination: JobQueueTabPagination;
  onOffsetChange: (offset: number) => void;
}
```

Destructure the two new props in the function signature:

```tsx
export function JobQueueTab({
  jobs,
  setJobs,
  jobsLoading,
  connected,
  onRefreshJobs,
  pagination,
  onOffsetChange,
}: JobQueueTabProps) {
```

**Why not `usePagination`:** D-16 names both the `<Pagination>` primitive and the `usePagination` hook as reusable assets. The hook (see `apps/visualizer/frontend/src/hooks/usePagination.ts`) owns its own `offset` state internally — but Phase 2 needs `offset` to live in `ProcessingPage` (per the pagination ↔ live-updates contract, so socket refetches can target the current slice). Using the hook would require either (a) duplicating state in both places and keeping them in sync, or (b) generalizing the hook to accept an external `offset` / `onOffsetChange` pair. (b) is a cross-cutting refactor that affects other consumers of `usePagination` (Images/Catalog). That refactor is **out of scope for Phase 2**; capture it in the post-phase follow-ups list if it surfaces.

For now, this plan takes the pragmatic route: **use the `<Pagination>` primitive directly and compute `currentPage` / `totalPages` inline** — matching CONTEXT D-16's intent of "reuse the pagination primitive" without forcing a hook contract that doesn't fit lifted state.

Compute derived pagination numbers just below `const [retryingId, setRetryingId] = useState<string | null>(null);` (line 47):

```ts
const currentPage = Math.floor(pagination.offset / pagination.limit) + 1;
const totalPages = Math.max(1, Math.ceil(pagination.total / pagination.limit));
const rangeStart = pagination.total === 0 ? 0 : pagination.offset + 1;
const rangeEnd = Math.min(pagination.offset + jobs.length, pagination.total);
const handlePageChange = (page: number) => {
  const nextOffset = Math.max(0, (page - 1) * pagination.limit);
  if (nextOffset !== pagination.offset) {
    onOffsetChange(nextOffset);
  }
};
```

**Render location (D-17):** the `<Pagination>` lives **inside** the same `<Card padding="none">` that wraps the table. Currently the table card is:

```tsx
<Card padding="none">
  <div className="overflow-x-auto">
    <table className="w-full">
      {/* ...thead + tbody... */}
    </table>
  </div>
</Card>
```

Change it to include a pagination footer inside the card, after the scrollable table container:

```tsx
<Card padding="none">
  <div className="overflow-x-auto">
    <table className="w-full">
      {/* ...thead + tbody... */}
    </table>
  </div>
  {pagination.total > pagination.limit && (
    <div className="flex items-center justify-between gap-4 border-t border-border px-4 py-3">
      <span className="text-xs text-text-secondary">
        {JOB_QUEUE_PAGINATION_RANGE(rangeStart, rangeEnd, pagination.total)}
      </span>
      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={handlePageChange}
        disabled={jobsLoading}
      />
    </div>
  )}
</Card>
```

This keeps pagination visually attached to the table (D-17). The `border-t` separator mirrors the `CatalogTab` footer style. Do **not** render pagination outside the `<Card>` — that's the defect the plan-checker caught in the first revision.

**Do not** render the pagination footer when `pagination.total <= pagination.limit` — matches `Pagination`'s own `totalPages <= 1` early return, avoids an empty footer strip.
</action>
<read_first>
- apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx
- apps/visualizer/frontend/src/components/ui/Pagination.tsx
- apps/visualizer/frontend/src/hooks/usePagination.ts
- apps/visualizer/frontend/src/constants/strings.ts (after plan 02 applied)
</read_first>
<acceptance_criteria>
- `rg -n "import \{ Pagination \} from '\.\./ui/Pagination'" apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` matches 1 line
- `rg -n "import \{ JOB_QUEUE_PAGINATION_RANGE \}" apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` matches 1 line
- `rg -n "pagination: JobQueueTabPagination" apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` matches 1 line
- `rg -n "onOffsetChange: \(offset: number\) => void" apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` matches 1 line
- `rg -n "const handlePageChange = \(page: number\)" apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` matches 1 line
- `rg -n "JOB_QUEUE_PAGINATION_RANGE\(rangeStart, rangeEnd, pagination\.total\)" apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` matches 1 line
- `rg -n "<Pagination" apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` matches 1 line
- **Pagination inside Card** (D-17): the pagination footer `<div>` is inside `<Card padding="none">...</Card>`, not outside. Manual diff review.
- `rg -n "Showing [^{]*\{pagination\." apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` returns no matches (no inline English range label)
</acceptance_criteria>
</task>

<task id="4.3">
<action>
Create `apps/visualizer/frontend/src/components/processing/__tests__/JobQueueTab.test.tsx` (if directory doesn't exist, create it). Cover the three pagination behaviours that matter:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { JobQueueTab } from '../JobQueueTab';
import type { Job } from '../../../types/job';

vi.mock('../../jobs/JobDetailModal', () => ({
  JobDetailModal: () => null,
}));

vi.mock('../../../services/api', () => ({
  JobsAPI: {
    cancel: vi.fn(),
    retry: vi.fn(),
  },
}));

function makeJobs(count: number, offset = 0): Job[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `job-${offset + i}`,
    type: 'matching',
    status: 'completed',
    progress: 1,
    current_step: null,
    logs: [],
    logs_total: 0,
    result: null,
    error: null,
    created_at: new Date().toISOString(),
    started_at: null,
    completed_at: null,
    metadata: {},
  } as Job));
}

describe('JobQueueTab pagination', () => {
  it('hides the Pagination when total <= limit', () => {
    render(
      <JobQueueTab
        jobs={makeJobs(10)}
        setJobs={vi.fn()}
        jobsLoading={false}
        connected={true}
        onRefreshJobs={vi.fn()}
        pagination={{ offset: 0, limit: 50, total: 10 }}
        onOffsetChange={vi.fn()}
      />
    );
    expect(screen.queryByLabelText('Previous page')).toBeNull();
    expect(screen.queryByLabelText('Next page')).toBeNull();
  });

  it('shows the Pagination when total > limit', () => {
    render(
      <JobQueueTab
        jobs={makeJobs(50)}
        setJobs={vi.fn()}
        jobsLoading={false}
        connected={true}
        onRefreshJobs={vi.fn()}
        pagination={{ offset: 0, limit: 50, total: 175 }}
        onOffsetChange={vi.fn()}
      />
    );
    expect(screen.getByLabelText('Next page')).toBeTruthy();
    expect(screen.getByText(/Showing 1–50 of 175/)).toBeTruthy();
  });

  it('clicking Next invokes onOffsetChange with offset + limit', () => {
    const onOffsetChange = vi.fn();
    render(
      <JobQueueTab
        jobs={makeJobs(50)}
        setJobs={vi.fn()}
        jobsLoading={false}
        connected={true}
        onRefreshJobs={vi.fn()}
        pagination={{ offset: 0, limit: 50, total: 175 }}
        onOffsetChange={onOffsetChange}
      />
    );
    fireEvent.click(screen.getByLabelText('Next page'));
    expect(onOffsetChange).toHaveBeenCalledWith(50);
  });

  it('shows correct "Showing X–Y of Z" label on page 2', () => {
    render(
      <JobQueueTab
        jobs={makeJobs(50, 50)}
        setJobs={vi.fn()}
        jobsLoading={false}
        connected={true}
        onRefreshJobs={vi.fn()}
        pagination={{ offset: 50, limit: 50, total: 175 }}
        onOffsetChange={vi.fn()}
      />
    );
    expect(screen.getByText(/Showing 51–100 of 175/)).toBeTruthy();
  });
});
```

Mirror the project's existing test-file style if it differs (e.g. uses `@testing-library/jest-dom` matchers). Read an existing `*.test.tsx` first to confirm the import paths and JSX runtime setup.
</action>
<read_first>
- apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx (after task 4.2 applied)
- apps/visualizer/frontend/src/components/ui/__tests__/Pagination.test.tsx (as style reference)
</read_first>
<acceptance_criteria>
- `test -f apps/visualizer/frontend/src/components/processing/__tests__/JobQueueTab.test.tsx && echo ok` prints `ok`
- `cd apps/visualizer/frontend && npx vitest run src/components/processing/__tests__/JobQueueTab.test.tsx` exits 0
</acceptance_criteria>
</task>

<task id="4.4">
<action>
Verify that `ProcessingPage`'s socket wiring continues to work after the refactor. Specifically, confirm `useJobSocket` still receives `onJobCreated` and `onJobUpdated` callbacks (renamed to `handleJobCreated` / `handleJobUpdated` — both now just call `scheduleRefresh()`), and that `onJobsRecovered` is still wired to set the banner.

If the `useJobSocket` hook's signature requires non-empty callbacks (e.g. throws when they're missing), the debounced refetch callbacks satisfy that contract because they are still defined functions, just with thin bodies.

No code change needed in this task if the wiring from task 4.1 was applied correctly. Grep for the callback wiring to confirm:

```bash
rg -n "useJobSocket\(\{" apps/visualizer/frontend/src/pages/ProcessingPage.tsx
rg -n "onJobCreated: handleJobCreated" apps/visualizer/frontend/src/pages/ProcessingPage.tsx
rg -n "onJobUpdated: handleJobUpdated" apps/visualizer/frontend/src/pages/ProcessingPage.tsx
rg -n "onJobsRecovered:" apps/visualizer/frontend/src/pages/ProcessingPage.tsx
```

If any grep returns no match, re-open `ProcessingPage.tsx` and restore the wiring from task 4.1 step 6 — the three callbacks must all exist and be passed through to `useJobSocket`.
</action>
<read_first>
- apps/visualizer/frontend/src/pages/ProcessingPage.tsx (after task 4.1 applied)
- apps/visualizer/frontend/src/hooks/useJobSocket.ts (to confirm the hook's expected props)
</read_first>
<acceptance_criteria>
- `rg -n "onJobCreated: handleJobCreated" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
- `rg -n "onJobUpdated: handleJobUpdated" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
- `rg -n "onJobsRecovered:" apps/visualizer/frontend/src/pages/ProcessingPage.tsx` matches 1 line
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
- `cd apps/visualizer/frontend && npx vitest run src/components/processing/__tests__/JobQueueTab.test.tsx` exits 0
- `cd apps/visualizer/frontend && npx eslint src/pages/ProcessingPage.tsx src/components/processing/JobQueueTab.tsx` exits 0
- Manual smoke (documented, not enforced): seed >50 jobs, confirm (a) page 1 shows 50 rows + pagination inside the same card, (b) clicking Next loads rows 51–100 without flashing an empty state for >400ms, (c) while paused on page 2 a new job being created does not silently jump you back to page 1 — the "Showing 51–100 of N+1" label updates and a refetch fires for page 2.
</verification>

<must_haves>
- `PAGE_SIZE = 50` (D-15) drives both the API `limit` and the UI page size.
- `ProcessingPage` owns `jobsOffset` and `jobsTotal`; it refetches on any `jobsOffset` change.
- Socket events (`job_created`, `job_updated`) schedule a debounced (400ms trailing, D-22) `refreshJobs()` instead of mutating `jobs` directly.
- `JobQueueTab` renders the existing `Pagination` primitive **inside** the same `<Card>` as the jobs table (D-17), only when `total > limit`.
- The "Showing X–Y of Z" label uses the `JOB_QUEUE_PAGINATION_RANGE` string constant added in plan 02 (D-26 — no inline English).
- Clicking a page number or Next/Prev fires `onOffsetChange(newOffset)`, which triggers the `useEffect`-driven refetch via `jobsOffset` dependency.
- Tab switching (matching ↔ jobs ↔ settings) does not reset `jobsOffset` or clear `jobs` — `ProcessingPage` state persists.
- The cancel/retry optimistic UI inside `JobQueueTab` still works against the current page slice (D-23); it does not attempt cross-page mutation.
- Refresh button re-fetches the current `{limit, offset}` slice — does not jump to page 1 (D-19).
- No new dependencies introduced; debounce is a plain `setTimeout` + `useRef`.
</must_haves>
