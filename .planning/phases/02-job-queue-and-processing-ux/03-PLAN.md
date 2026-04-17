---
plan: 03
title: JobDetailModal loading skeleton and log truncation UI
wave: 2
depends_on: [02]
files_modified:
  - apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
  - apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx
autonomous: true
requirements:
  - JOB-03
  - JOB-04
---

<objective>
Deliver the two user-facing behaviours that make the job detail modal feel real: (1) a **targeted** loading state that keeps the top identity row and progress bar populated from the list-row data but skeletons only the heavy sections (`metadata`, `result`, `logs`) while `JobsAPI.get()` is in flight (JOB-03); and (2) a truncated logs section that defaults to the last 20 entries via `?logs_limit=20`, surfaces a `"Logs (20 of N)"` header, and reveals the full list on demand via a `"Show all N logs"` affordance that triggers a refetch with `logs_limit=0` (JOB-04).
</objective>

<context>
Implements the UI half of **D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11** (and feeds the expansion-label contract used by D-26):
- **D-01:** The modal must render **immediately** using `job` prop data (id, type, status badge, created-at, progress) — no full-card spinner, no card-wide skeleton.
- **D-02:** Only `metadata`, `result`, and `logs` sections gate on `loading`. Top identity row and progress bar always render from the list-row `job`.
- **D-03:** Skeletons reuse the existing `animate-pulse` + `bg-surface` / `bg-gray-200` vocabulary. Do not introduce new skeleton primitives — inline skeleton blocks inside each heavy section are fine.
- **D-04:** If `JobsAPI.get()` fails, show an inline error message (reusing `text-error` style) above the heavy sections — do **not** close the modal, do **not** hide the identity row.
- **D-05:** `loading` starts `true`, flips `false` on the first `JobsAPI.get` resolution (success **or** failure). Subsequent socket `job_updated` events never re-trigger it.
- **D-07:** First `JobsAPI.get` passes `logs_limit: 20`.
- **D-08:** Socket `job_updated` updates `localJob` but does **not** toggle `loading`.
- **D-11:** `"Show all"` button issues a second `JobsAPI.get` with `logs_limit: 0` and swaps `displayJob.logs`.
- **D-24:** When `logs_total > displayJob.logs.length`, the logs header shows the truncated label; when they match, the plain `"Logs"` label remains.
- All new copy lives in `constants/strings.ts` via the symbols added in plan 02 (D-26).
- **Lifecycle safety:** the modal's internal state (`loading`, `logsExpanded`, `expandingLogs`, `fetchError`, `localJob`) must reset when the parent swaps to a different job. Achieved **inside the component** via a dedicated `[job.id]` prop-sync `useEffect` (task 3.7) — not via a `key` prop at call sites. This keeps the contract self-contained and avoids churning the socket-subscription effect on every row click.
</context>

<tasks>
<task id="3.1">
<action>
In `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx`, extend the imports from `../../constants/strings` (line 2–18) to include the three new symbols added in plan 02:

```ts
import {
  JOB_CONFIG_DATE_WINDOW,
  JOB_CONFIG_METHOD,
  JOB_CONFIG_THRESHOLD,
  JOB_CONFIG_VISION_MODEL,
  JOB_CONFIG_WEIGHTS,
  JOB_DETAILS_CURRENT_STEP,
  JOB_DETAILS_ERROR,
  ERROR_SEVERITY_LABELS,
  JOB_DETAILS_LOGS,
  JOB_DETAILS_LOGS_TRUNCATED_HEADER,
  JOB_DETAILS_LOGS_SHOW_ALL,
  JOB_DETAILS_LOGS_SHOW_ALL_LOADING,
  JOB_DETAILS_LOADING_ARIA,
  JOB_DETAILS_FETCH_ERROR,
  JOB_DETAILS_METADATA,
  JOB_DETAILS_PROGRESS,
  JOB_DETAILS_RESULT,
  JOB_DETAILS_TITLE,
  MODAL_CLOSE,
  STATUS_LABELS,
} from '../../constants/strings';
```

Do not touch any other imports.
</action>
<read_first>
- apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
- apps/visualizer/frontend/src/constants/strings.ts (after plan 02 applied)
</read_first>
<acceptance_criteria>
- `rg -n "JOB_DETAILS_LOGS_TRUNCATED_HEADER" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "JOB_DETAILS_LOGS_SHOW_ALL\b" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "JOB_DETAILS_LOGS_SHOW_ALL_LOADING" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "JOB_DETAILS_LOADING_ARIA" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "JOB_DETAILS_FETCH_ERROR" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
</acceptance_criteria>
</task>

<task id="3.2">
<action>
Add four state variables to the `JobDetailModal` component (insert after `const [retrying, setRetrying] = useState(false);` on line 78). Name matches CONTEXT D-05 (`loading`):

```ts
const [loading, setLoading] = useState(true);
const [fetchError, setFetchError] = useState<string | null>(null);
const [logsExpanded, setLogsExpanded] = useState(false);
const [expandingLogs, setExpandingLogs] = useState(false);
```

- `loading` gates the heavy-section skeletons only (D-02). Starts `true`; flips to `false` inside the first `JobsAPI.get` resolution (success or failure) — **never** toggled by socket events (D-05, D-08).
- `fetchError` holds a user-facing copy string when the initial fetch fails (D-04). Rendered as an inline banner in task 3.5; cleared on subsequent successful retries (but this plan does **not** add a retry button for the fetch error itself — the socket updates or a parent-triggered reopen are the recovery paths).
- `logsExpanded` tracks whether the user requested full logs. When `true`, re-renders skip the truncated header and the `"Show all"` button.
- `expandingLogs` disables the `"Show all"` button while the expand-fetch is in flight.
</action>
<read_first>
- apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
- .planning/phases/02-job-queue-and-processing-ux/02-CONTEXT.md (D-01..D-05)
</read_first>
<acceptance_criteria>
- `rg -n "const \[loading, setLoading\] = useState\(true\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "const \[fetchError, setFetchError\] = useState<string \| null>\(null\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "const \[logsExpanded, setLogsExpanded\]" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "const \[expandingLogs, setExpandingLogs\]" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
</acceptance_criteria>
</task>

<task id="3.3">
<action>
Replace the initial-fetch `useEffect` (currently lines 81–89) with a version that (a) passes `logs_limit: 20` by default, (b) flips `loading` to `false` on success **and** failure, (c) sets `fetchError` copy on failure (D-04), and (d) guards against setting state after unmount:

```ts
useEffect(() => {
  let cancelled = false;
  setLoading(true);
  setFetchError(null);
  JobsAPI.get(job.id, { logs_limit: 20 })
    .then((freshJob) => {
      if (cancelled) return;
      setLocalJob(freshJob);
    })
    .catch((err) => {
      if (cancelled) return;
      console.error('Failed to fetch job details:', err);
      setFetchError(JOB_DETAILS_FETCH_ERROR);
    })
    .finally(() => {
      if (cancelled) return;
      setLoading(false);
    });
  return () => {
    cancelled = true;
  };
}, [job.id]);
```

**Important:**
- Dependency is only `[job.id]`. Full-log expansion is driven by its own one-shot fetch in task 3.4, not by re-running this effect. Re-entering this effect would (wrongly) toggle `loading=true` and flash the skeleton a second time — which D-08 forbids (socket/expansion flows must not re-trigger the skeleton).
- The `cancelled` flag prevents the classic race where the modal closes before the fetch resolves.
- On the error path we still clear the loading state; the inline `fetchError` banner (task 3.5) surfaces the failure while the identity row + progress remain visible (D-04).
</action>
<read_first>
- apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
- apps/visualizer/frontend/src/services/api.ts (after plan 02 applied)
- apps/visualizer/frontend/src/constants/strings.ts (after plan 02 applied)
</read_first>
<acceptance_criteria>
- `rg -n "JobsAPI\.get\(job\.id, \{ logs_limit: 20 \}\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "setLoading\(false\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches at least 1 line
- `rg -n "setFetchError\(JOB_DETAILS_FETCH_ERROR\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "\}, \[job\.id\]\);" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches at least 1 line (initial-fetch effect dep array)
</acceptance_criteria>
</task>

<task id="3.4">
<action>
Add a handler for the expand-logs action. Insert just before `const renderProgress = () => {` (currently line 126):

```ts
const handleExpandLogs = async () => {
  if (logsExpanded || expandingLogs) return;
  setExpandingLogs(true);
  try {
    const fullJob = await JobsAPI.get(displayJob.id, { logs_limit: 0 });
    setLocalJob(fullJob);
    setLogsExpanded(true);
  } catch (err) {
    console.error('Failed to load full logs:', err);
  } finally {
    setExpandingLogs(false);
  }
};
```

Note: we call `setLogsExpanded(true)` **after** the successful fetch. This keeps the `useEffect` in task 3.3 from firing a second overlapping fetch for the same data.
</action>
<read_first>
- apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
</read_first>
<acceptance_criteria>
- `rg -n "const handleExpandLogs = async \(\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "JobsAPI\.get\(displayJob\.id, \{ logs_limit: 0 \}\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
</acceptance_criteria>
</task>

<task id="3.5">
<action>
Apply **targeted** skeletons to only the heavy sections per D-01/D-02. The top identity grid (ID/Type/Status/Created) and the `renderProgress()` bar **always render** from the list-row `job` — even while `loading === true`. Only `metadata`, `current_step`, `result`, and `logs` sections swap to skeletons while loading.

Add a small inline `SkeletonBlock` helper at the top of the modal file body (just after `function progressFillClass` / before the `interface JobDetailModalProps`) to avoid repetition:

```tsx
function SkeletonLine({ widthClass }: { widthClass: string }) {
  return <div className={`h-3 ${widthClass} rounded-base bg-surface animate-pulse`} />;
}

function SkeletonSection({ label }: { label: string }) {
  return (
    <div
      className="space-y-2 rounded-base border border-border p-3"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div className="h-4 w-32 rounded-base bg-surface animate-pulse" />
      <SkeletonLine widthClass="w-full" />
      <SkeletonLine widthClass="w-5/6" />
      <SkeletonLine widthClass="w-2/3" />
    </div>
  );
}
```

Inside the scrollable container (the `<div className="p-4 space-y-4 overflow-y-auto">` at line 163), changes section-by-section:

1. **Keep identity grid unchanged** (lines 164–185). Renders from `displayJob` regardless of `loading`.

2. **Keep `{renderProgress()}` unchanged** (line 187). Renders from `displayJob.progress`/`displayJob.status` (both present on list-row `job`).

3. **Insert the inline error banner** directly above `{displayJob.current_step && ...}` (before line 189). Only rendered when `fetchError` is set:

   ```tsx
   {fetchError && (
     <div
       className="rounded-base border border-error/50 bg-red-50 dark:bg-red-950/30 p-3"
       role="alert"
     >
       <p className="text-sm text-error">{fetchError}</p>
     </div>
   )}
   ```

4. **`current_step` block** (lines 189–194): show skeleton while `loading` — but only if the list-row `job.current_step` is `null` (i.e. we have nothing to fall back on). Replace with:

   ```tsx
   {loading && !displayJob.current_step ? (
     <div
       className="rounded-base border border-border bg-accent-light p-3"
       role="status"
       aria-label={JOB_DETAILS_LOADING_ARIA}
     >
       <SkeletonLine widthClass="w-24" />
       <div className="mt-2 h-3 w-2/3 rounded-base bg-accent/20 animate-pulse" />
     </div>
   ) : displayJob.current_step ? (
     <div className="rounded-base border border-border bg-accent-light p-3">
       <span className="text-sm font-medium text-accent">{JOB_DETAILS_CURRENT_STEP}:</span>
       <p className="text-sm text-text mt-1">{displayJob.current_step}</p>
     </div>
   ) : null}
   ```

5. **`metadata` block** (lines 196–203): gate on `loading`:

   ```tsx
   {loading ? (
     <SkeletonSection label={JOB_DETAILS_LOADING_ARIA} />
   ) : displayJob.metadata && Object.keys(displayJob.metadata).length > 0 ? (
     <div className="rounded-base border border-border p-3">
       <h4 className="font-medium text-sm mb-2 text-text">{JOB_DETAILS_METADATA}</h4>
       <pre className="text-xs bg-surface p-2 rounded-base overflow-x-auto text-text border border-border">
         {JSON.stringify(displayJob.metadata, null, 2)}
       </pre>
     </div>
   ) : null}
   ```

6. **Configuration block** (lines 205–290): wrap with `{!loading && (` at the top and a closing `)}` at the end. The configuration block reads from `metadata.method`, `result.method`, etc. — all nested under fields that might be undefined until the full fetch returns. Gating it on `!loading` prevents a partial render.

7. **`result` block** (lines 292–299): same pattern — gate the existing block with `{!loading && displayJob.result && (...)}` (change the opening check from `{displayJob.result && (` to `{!loading && displayJob.result && (`).

8. **`error` block** (lines 301–317): keep rendering while loading — an error from the list-row is still valid info. **No change**.

9. **Retry button** (lines 319–329): keep rendering while loading — no change. (Retry is a user action; the list-row status already tells us whether the job is retryable.)

10. **`logs` block** (lines 331–356): replaced entirely by task 3.6 below, which internally handles the `loading` case.

**Do not** add a single top-level `{loading ? <fullSkeleton> : <fullContent>}` wrapper. Doing so would violate D-01 (which requires the identity row to render immediately from the list-row data).

All skeleton visual vocabulary reuses existing `animate-pulse` + `bg-surface` + `bg-gray-200`-family classes already present in the codebase (per D-03); no new Tailwind classes introduced.
</action>
<read_first>
- apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
- .planning/phases/02-job-queue-and-processing-ux/02-CONTEXT.md (D-01..D-05)
</read_first>
<acceptance_criteria>
- `rg -n "function SkeletonSection" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "\{fetchError && \(" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "role=\"alert\"" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches at least 1 line
- `rg -n "\{loading && !displayJob\.current_step \?" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "\{loading \? \(" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches at least 1 line (metadata skeleton switch)
- `rg -n "\{!loading && displayJob\.result && \(" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- Identity grid preserved: `rg -n "Status:" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` still matches; `rg -n "\{renderProgress\(\)\}" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` still matches 1 line
- **Top-level wrapper forbidden:** `rg -n "\{loading \? \([^}]*<div className=\"grid grid-cols-2" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` returns no matches (no card-wide skeleton)
- `rg -n "JOB_DETAILS_METADATA" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` still matches 1 line
</acceptance_criteria>
</task>

<task id="3.6">
<action>
Replace the logs-rendering block (currently lines 331–356) with a version that (a) shows a skeleton while `loading`, (b) switches the header label when truncated, and (c) adds the `"Show all N logs"` button using the `JOB_DETAILS_LOGS_SHOW_ALL_LOADING` constant (no inline English).

Compute `logsTotal` as `displayJob.logs_total ?? displayJob.logs?.length ?? 0` so it degrades gracefully if the backend omits the field.

```tsx
{loading ? (
  <SkeletonSection label={JOB_DETAILS_LOADING_ARIA} />
) : displayJob.logs && displayJob.logs.length > 0 ? (() => {
  const logsShown = displayJob.logs.length;
  const logsTotal = displayJob.logs_total ?? logsShown;
  const isTruncated = logsTotal > logsShown;
  return (
    <div className="rounded-base border border-border p-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-sm text-text">
          {isTruncated ? JOB_DETAILS_LOGS_TRUNCATED_HEADER(logsShown, logsTotal) : JOB_DETAILS_LOGS}
        </h4>
        {isTruncated && !logsExpanded && (
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={() => {
              void handleExpandLogs();
            }}
            disabled={expandingLogs}
          >
            {expandingLogs ? JOB_DETAILS_LOGS_SHOW_ALL_LOADING : JOB_DETAILS_LOGS_SHOW_ALL(logsTotal)}
          </Button>
        )}
      </div>
      <div className="bg-surface text-text p-3 rounded-base font-mono text-xs max-h-48 overflow-y-auto border border-border">
        {displayJob.logs.map((log, idx) => (
          <div key={idx} className="mb-1">
            <span className="text-text-tertiary">
              {new Date(log.timestamp).toLocaleTimeString()}
            </span>
            <span
              className={`ml-2 ${
                log.level === 'error'
                  ? 'text-error'
                  : log.level === 'warning'
                    ? 'text-warning'
                    : 'text-success'
              }`}
            >
              [{log.level}]
            </span>
            <span className="ml-2">{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
})() : null}
```

The IIFE pattern is used because the header-vs-button decision depends on derived values (`logsShown`, `logsTotal`, `isTruncated`) that aren't worth hoisting to component-level `useMemo`. This pattern already exists in other detail views of the codebase.
</action>
<read_first>
- apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
- apps/visualizer/frontend/src/types/job.ts (after plan 02 applied)
- apps/visualizer/frontend/src/constants/strings.ts (after plan 02 applied)
</read_first>
<acceptance_criteria>
- `rg -n "const logsTotal = displayJob\.logs_total \?\? logsShown" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "JOB_DETAILS_LOGS_TRUNCATED_HEADER\(logsShown, logsTotal\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "JOB_DETAILS_LOGS_SHOW_ALL\(logsTotal\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "expandingLogs \? JOB_DETAILS_LOGS_SHOW_ALL_LOADING" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "'Loading…'|'Loading\.\.\.'" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` returns no matches (no inline English for the expand button's loading label)
- `rg -n "void handleExpandLogs\(\);" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
</acceptance_criteria>
</task>

<task id="3.7">
<action>
Ensure internal modal state (`loading`, `fetchError`, `logsExpanded`, `expandingLogs`, `localJob`) resets when the parent swaps to a different job. The cleanest approach is to make the component self-healing instead of requiring `key={job.id}` at every call site — the initial-fetch `useEffect` in task 3.3 already depends on `[job.id]` and re-runs, but it only resets `loading` and `fetchError`. We additionally need to reset `logsExpanded` and `expandingLogs` and re-seed `localJob` from the new `job` prop.

Add **one more `useEffect`** immediately after the initial-fetch effect from task 3.3:

```ts
useEffect(() => {
  setLocalJob(job);
  setLogsExpanded(false);
  setExpandingLogs(false);
}, [job.id]);
```

Why a separate effect instead of folding into task 3.3's effect:
- Single-responsibility per effect (initial-fetch vs prop-sync).
- Makes it obvious in diffs that prop-sync is intentional and lifecycle-bound.
- The two effects run in order: prop-sync first (because declared first? React actually runs them in declaration order, so declare this **before** the initial-fetch effect if you want `localJob` reseeded before the fetch resolves). Place this effect **before** the initial-fetch effect from task 3.3.

**Do not** add `key={job.id}` at the call site — the `JobQueueTab` reuses the same `selectedJob` slot for every row click, and `key`-resetting there would also churn socket subscriptions unnecessarily. The self-healing effect is the right grain.
</action>
<read_first>
- apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
</read_first>
<acceptance_criteria>
- `rg -n "setLocalJob\(job\);\s*$" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "setLogsExpanded\(false\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- `rg -n "setExpandingLogs\(false\)" apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` matches 1 line
- Exactly two `useEffect` blocks in the component depend on `[job.id]` alone (the prop-sync effect + the initial-fetch effect). The socket-subscribe effect's dep array is `[socket, job.id, onJobUpdate]` and stays unchanged.
</acceptance_criteria>
</task>

<task id="3.8">
<action>
Create `apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx` with tests that cover the user-visible guarantees. Check first whether the `__tests__` directory and test file already exist — if the file exists, append the `describe` block instead of overwriting.

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { JobDetailModal } from '../JobDetailModal';
import type { Job } from '../../../types/job';

const mockGet = vi.fn();
vi.mock('../../../services/api', () => ({
  JobsAPI: {
    get: (...args: unknown[]) => mockGet(...args),
    retry: vi.fn(),
  },
}));

vi.mock('../../../stores/socketStore', () => ({
  useSocketStore: () => null,
}));

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 'job-1',
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
    ...overrides,
  } as Job;
}

describe('JobDetailModal', () => {
  beforeEach(() => {
    mockGet.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders identity row (id, type, status) immediately from the list-row job, even while loading', () => {
    mockGet.mockImplementation(() => new Promise<Job>(() => {}));
    const job = makeJob({ id: 'abc-123', type: 'matching', status: 'running' });
    render(<JobDetailModal job={job} onClose={() => {}} />);
    expect(screen.getByText('abc-123')).toBeTruthy();
    expect(screen.getByText('matching')).toBeTruthy();
    expect(screen.getByText(/running/i)).toBeTruthy();
  });

  it('shows a skeleton for heavy sections while the initial fetch is in flight', async () => {
    let resolveFetch: (value: Job) => void = () => {};
    mockGet.mockImplementationOnce(
      () => new Promise<Job>((resolve) => { resolveFetch = resolve; })
    );
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    expect(screen.getAllByLabelText(/loading job details/i).length).toBeGreaterThan(0);
    resolveFetch(makeJob({ logs_total: 0 }));
    await waitFor(() => {
      expect(screen.queryAllByLabelText(/loading job details/i).length).toBe(0);
    });
  });

  it('shows an inline fetch-error banner when the initial GET fails, keeping identity row visible', async () => {
    mockGet.mockRejectedValueOnce(new Error('500 Internal Server Error'));
    const job = makeJob({ id: 'id-err', type: 'matching', status: 'failed' });
    render(<JobDetailModal job={job} onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
    expect(screen.getByText(/could not refresh job details/i)).toBeTruthy();
    expect(screen.getByText('id-err')).toBeTruthy();
  });

  it('initial fetch passes logs_limit: 20', async () => {
    mockGet.mockResolvedValue(makeJob({ logs_total: 5 }));
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('job-1', { logs_limit: 20 });
    });
  });

  it('renders truncated header and Show all button when logs_total > logs.length', async () => {
    const truncatedJob = makeJob({
      logs: Array.from({ length: 20 }, (_, i) => ({
        timestamp: new Date().toISOString(),
        level: 'info' as const,
        message: `m${i}`,
      })),
      logs_total: 137,
    });
    mockGet.mockResolvedValue(truncatedJob);
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/Logs \(20 of 137\)/)).toBeTruthy();
    });
    expect(screen.getByText(/Show all 137 logs/)).toBeTruthy();
  });

  it('clicking Show all refetches with logs_limit: 0 and hides the button', async () => {
    const truncatedJob = makeJob({
      logs: Array.from({ length: 20 }, (_, i) => ({
        timestamp: new Date().toISOString(),
        level: 'info' as const,
        message: `m${i}`,
      })),
      logs_total: 50,
    });
    const fullJob = makeJob({
      logs: Array.from({ length: 50 }, (_, i) => ({
        timestamp: new Date().toISOString(),
        level: 'info' as const,
        message: `m${i}`,
      })),
      logs_total: 50,
    });
    mockGet
      .mockResolvedValueOnce(truncatedJob)
      .mockResolvedValueOnce(fullJob);
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    const showAll = await screen.findByText(/Show all 50 logs/);
    fireEvent.click(showAll);
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('job-1', { logs_limit: 0 });
    });
    await waitFor(() => {
      expect(screen.queryByText(/Show all 50 logs/)).toBeNull();
    });
  });

  it('does not render the Show all button when logs_total equals logs.length', async () => {
    const exactJob = makeJob({
      logs: Array.from({ length: 5 }, (_, i) => ({
        timestamp: new Date().toISOString(),
        level: 'info' as const,
        message: `m${i}`,
      })),
      logs_total: 5,
    });
    mockGet.mockResolvedValue(exactJob);
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/^Logs$/)).toBeTruthy();
    });
    expect(screen.queryByText(/Show all/)).toBeNull();
  });
});
```

If the project's vitest config requires a different render/testing-library import path (e.g. happy-dom jsx runtime), mirror the style of an existing `*.test.tsx` in `apps/visualizer/frontend/src` before writing — but the assertion structure stays the same.
</action>
<read_first>
- apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx (after tasks 3.1–3.6 applied)
- apps/visualizer/frontend/src/pages/DashboardPage.test.tsx (as a style reference)
</read_first>
<acceptance_criteria>
- `test -f apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx && echo ok` prints `ok`
- `rg -n "renders identity row .* immediately" apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx` matches 1 line
- `rg -n "inline fetch-error banner" apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx` matches 1 line
- `cd apps/visualizer/frontend && npx vitest run src/components/jobs/__tests__/JobDetailModal.test.tsx` exits 0
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
- `cd apps/visualizer/frontend && npx vitest run src/components/jobs/__tests__/JobDetailModal.test.tsx` exits 0
- `cd apps/visualizer/frontend && npx eslint src/components/jobs/JobDetailModal.tsx` exits 0
- Manual smoke (documented, not enforced): open a running job in the UI and confirm (a) identity row + progress render immediately from the list row, (b) heavy sections show skeletons and swap to real content once the fetch resolves, (c) a job with >20 log lines shows `Logs (20 of N)` and a Show all button, (d) clicking Show all reveals the full list and hides the button, (e) simulating a fetch failure shows the inline error banner and keeps the modal open.
</verification>

<must_haves>
- **Identity row + progress bar always visible** from the list-row `job` — even while `loading === true` (D-01).
- **Only heavy sections skeleton** while loading: `current_step` (if null on list row), `metadata`, `configuration`, `result`, and `logs`. The top identity grid and the progress bar are never skeletoned (D-02).
- Skeleton renders **only** during the initial `JobsAPI.get` fetch; subsequent socket-driven updates and log-expansion fetches never trigger it (D-05, D-08).
- On initial-fetch failure, an inline `role="alert"` banner renders with `JOB_DETAILS_FETCH_ERROR`; modal stays open; identity row stays populated (D-04).
- `JobsAPI.get` first call always includes `logs_limit: 20` (D-07).
- When `logs_total > logs.length`, the logs card header reads `Logs (<shown> of <total>)` and a `Show all <total> logs` button is visible (D-11, D-24).
- When `logs_total === logs.length` (or `logs_total` is undefined), the header stays the plain `Logs` and no button renders.
- Clicking Show all re-fetches with `logs_limit: 0`, updates `displayJob.logs`, sets `logsExpanded`, and removes the button. While that fetch is in flight, the button text is `JOB_DETAILS_LOGS_SHOW_ALL_LOADING` (no inline English).
- **Self-healing on job.id change:** a dedicated prop-sync `useEffect` resets `localJob`, `logsExpanded`, and `expandingLogs` whenever `job.id` changes, so the modal is safe to reuse across row selections without a parent `key` prop.
- All new copy comes from `constants/strings.ts` (no inline English).
- No regression: existing sections (metadata, configuration, result, error, retry button) render identically after initial load.
</must_haves>
