---
plan: 02
title: Frontend API client and types for paginated jobs and logs_limit
wave: 2
depends_on: [01]
files_modified:
  - apps/visualizer/frontend/src/services/api.ts
  - apps/visualizer/frontend/src/types/job.ts
  - apps/visualizer/frontend/src/constants/strings.ts
  - apps/visualizer/frontend/src/pages/DashboardPage.tsx
  - apps/visualizer/frontend/src/services/__tests__/api.test.ts
autonomous: true
requirements:
  - JOB-04
  - JOB-05
---

<objective>
Update the frontend API layer, types, and copy constants so every consumer of `JobsAPI` sees the new paginated envelope shape for `list()`, can pass an optional `logs_limit` into `get()`, and reads the post-truncation `logs_total` off the returned job. Add the new copy strings for the log-expansion affordance. No component behaviour changes in this plan — this is the narrow API/type seam that plans 03 and 04 build on top of.
</objective>

<context>
Implements the API-client half of **D-06**, **D-10**, **D-11** (logs_limit + logs_total flow through the client), **D-12** (paginated envelope on list), and **D-26** (new copy goes through `constants/strings.ts`). Plans 03 (`JobDetailModal`) and 04 (`ProcessingPage` / `JobQueueTab`) consume the shapes defined here.
</context>

<tasks>
<task id="2.1">
<action>
In `apps/visualizer/frontend/src/types/job.ts`, add an optional `logs_total?: number` field to the `Job` interface (currently lines 9–25). Place it directly after the `logs: JobLog[]` line so related fields stay adjacent:

```ts
export interface Job {
  id: string
  type: string
  status: JobStatus
  progress: number
  current_step: string | null
  logs: JobLog[]
  logs_total?: number
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result: any | null
  error: string | null
  error_severity?: 'warning' | 'error' | 'critical' | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata: Record<string, any>
}
```

Optional so older cached instances (or tests that don't populate it) don't become type errors.
</action>
<read_first>
- apps/visualizer/frontend/src/types/job.ts
- apps/visualizer/frontend/src/services/api.ts
- .planning/phases/02-job-queue-and-processing-ux/02-RESEARCH.md
</read_first>
<acceptance_criteria>
- `rg -n "logs_total\?: number" apps/visualizer/frontend/src/types/job.ts` matches 1 line
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</acceptance_criteria>
</task>

<task id="2.2">
<action>
In `apps/visualizer/frontend/src/services/api.ts`, update `JobsAPI.list` and `JobsAPI.get` (lines 110–132) to the new shapes. Existing `PaginationMeta` interface (lines 272–278) is already the correct envelope metadata — reuse it.

Replace the `JobsAPI` object (lines 110–132) with:

```ts
export interface JobsListResponse {
  total: number
  data: Job[]
  pagination: PaginationMeta
}

export interface JobsGetOptions {
  logs_limit?: number
}

export const JobsAPI = {
  list: (params?: { status?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams()
    if (params?.status) sp.set('status', params.status)
    if (params?.limit !== undefined) sp.set('limit', String(params.limit))
    if (params?.offset !== undefined) sp.set('offset', String(params.offset))
    const qs = sp.toString()
    return request<JobsListResponse>(`/jobs/${qs ? `?${qs}` : ''}`)
  },

  get: (id: string, options?: JobsGetOptions) => {
    const sp = new URLSearchParams()
    if (options?.logs_limit !== undefined) {
      sp.set('logs_limit', String(options.logs_limit))
    }
    const qs = sp.toString()
    return request<Job>(`/jobs/${id}${qs ? `?${qs}` : ''}`)
  },

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  create: (type: string, metadata?: Record<string, any>) =>
    request<Job>('/jobs/', {
      method: 'POST',
      body: JSON.stringify({ type, metadata }),
    }),

  getActive: () => request<Job[]>('/jobs/active'),

  cancel: (id: string) => request<void>(`/jobs/${id}`, { method: 'DELETE' }),

  retry: (id: string) => request<Job>(`/jobs/${id}/retry`, { method: 'POST' }),
}
```

**Note on `JobsAPI.list` signature:** the old signature was `list: (status?: string)`. It becomes `list: (params?: { status?: string; limit?: number; offset?: number })`. Any remaining consumer that still calls `JobsAPI.list('pending')` (with a positional string) is a type error and **must** be caught by the tsc gate — see task 2.4. Plan 04 updates `ProcessingPage` to use the new shape; if any other consumer exists outside `ProcessingPage`, update it in this plan (see task 2.3 audit).

`JobsGetOptions` is exported so plan 03 (`JobDetailModal`) can import the option shape without redeclaring.
</action>
<read_first>
- apps/visualizer/frontend/src/services/api.ts
- apps/visualizer/frontend/src/types/job.ts
- .planning/phases/02-job-queue-and-processing-ux/02-RESEARCH.md
</read_first>
<acceptance_criteria>
- `rg -n "export interface JobsListResponse" apps/visualizer/frontend/src/services/api.ts` matches 1 line
- `rg -n "export interface JobsGetOptions" apps/visualizer/frontend/src/services/api.ts` matches 1 line
- `rg -n "list: \(params\?: \{ status\?: string; limit\?: number; offset\?: number \}\)" apps/visualizer/frontend/src/services/api.ts` matches 1 line
- `rg -n "get: \(id: string, options\?: JobsGetOptions\)" apps/visualizer/frontend/src/services/api.ts` matches 1 line
- `rg -n "sp.set\('logs_limit', String\(options.logs_limit\)\)" apps/visualizer/frontend/src/services/api.ts` matches 1 line
</acceptance_criteria>
</task>

<task id="2.3">
<action>
Audit and migrate all call sites of `JobsAPI.list(...)` in the frontend to the new envelope shape. Run:

```bash
rg -n "JobsAPI\.list" apps/visualizer/frontend/src/
```

Known current call sites (from a pre-plan audit):

1. `apps/visualizer/frontend/src/pages/DashboardPage.tsx:107` — inside a `Promise.allSettled`. `r4.value` is treated as `Job[]` at line 155 (`r4.value.filter((job) => job.status === 'pending' || job.status === 'running').length`). **Must be updated in this plan** — leaving it would fail `tsc --noEmit` and break the dashboard's active-jobs counter at runtime.

   Edit `DashboardPage.tsx` around line 154–160. Replace the `r4.status === 'fulfilled'` branch so it unwraps `response.data`:

   ```ts
   if (r4.status === 'fulfilled') {
     const jobsList = Array.isArray(r4.value?.data) ? r4.value.data : [];
     const pending = jobsList.filter(
       (job) => job.status === 'pending' || job.status === 'running',
     ).length;
     setActiveJobs(pending);
   } else {
     setActiveJobs(0);
   }
   ```

   The call site at line 107 can stay as `JobsAPI.list()` (no args) — the change is purely in how the fulfilled value is consumed.

2. `apps/visualizer/frontend/src/pages/ProcessingPage.tsx:60,73` — `await JobsAPI.list()` (no args). Updated by **plan 04**, **not** this plan. Because the plain-no-args call is still valid under the new signature (`params?` is optional), this compiles — plan 04 is responsible for the return-value unwrap.

3. `apps/visualizer/frontend/src/services/__tests__/api.test.ts:19` — inside the existing `describe('JobsAPI', ...)` test `'should list all jobs'`. This test is updated by task **2.5** below (test update, not audit).

If the grep reveals any **other** call site not in the list above (e.g. a new consumer added since the audit, or a positional-string call like `JobsAPI.list('pending')`), update it in this plan — either migrate to `JobsAPI.list({ status: 'pending' })` for a filter, or wrap with `.data` for list-consumers. Those would otherwise fail the tsc gate.
</action>
<read_first>
- apps/visualizer/frontend/src/services/api.ts
- apps/visualizer/frontend/src/pages/DashboardPage.tsx
- apps/visualizer/frontend/src/pages/ProcessingPage.tsx
</read_first>
<acceptance_criteria>
- `rg -n "JobsAPI\.list\('" apps/visualizer/frontend/src/` returns no matches (no positional string call sites remain)
- `rg -n "r4\.value\.filter" apps/visualizer/frontend/src/pages/DashboardPage.tsx` returns no matches (the raw-array access is gone)
- `rg -n "r4\.value\?\.data|Array\.isArray\(r4\.value\?\.data\)" apps/visualizer/frontend/src/pages/DashboardPage.tsx` matches 1 line
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</acceptance_criteria>
</task>

<task id="2.4">
<action>
In `apps/visualizer/frontend/src/constants/strings.ts`, add five new exports. Three live in the `// Job Details Modal` section, next to the existing `JOB_DETAILS_LOGS = 'Logs'` line (currently line 230). Two live near the `// Job Queue` section (or create the section if absent) so plan 04's UI copy also routes through strings.

Job-details additions (directly after `JOB_DETAILS_LOGS`):

```ts
export const JOB_DETAILS_LOGS_TRUNCATED_HEADER = (shown: number, total: number) =>
  `Logs (${shown} of ${total})`
export const JOB_DETAILS_LOGS_SHOW_ALL = (total: number) => `Show all ${total} logs`
export const JOB_DETAILS_LOGS_SHOW_ALL_LOADING = 'Loading…'
export const JOB_DETAILS_LOADING_ARIA = 'Loading job details'
export const JOB_DETAILS_FETCH_ERROR =
  'Could not refresh job details. Showing the last known summary.'
```

Job-queue addition (place in or after the tab-related constants; if a `// Job Queue` section header doesn't yet exist, add one):

```ts
// Job Queue
export const JOB_QUEUE_PAGINATION_RANGE = (start: number, end: number, total: number) =>
  `Showing ${start}–${end} of ${total}`
```

Functions (not plain strings) are used here because the labels interpolate numbers — same pattern used elsewhere in the app for dynamic labels. No existing strings are removed or renamed. `JOB_DETAILS_FETCH_ERROR` is used by plan 03 task 3.3's inline error surface (D-04). `JOB_QUEUE_PAGINATION_RANGE` is used by plan 04 task 4.2's pagination footer.
</action>
<read_first>
- apps/visualizer/frontend/src/constants/strings.ts
- .planning/phases/02-job-queue-and-processing-ux/02-RESEARCH.md
</read_first>
<acceptance_criteria>
- `rg -n "export const JOB_DETAILS_LOGS_TRUNCATED_HEADER" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "export const JOB_DETAILS_LOGS_SHOW_ALL\b" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "export const JOB_DETAILS_LOGS_SHOW_ALL_LOADING" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "export const JOB_DETAILS_LOADING_ARIA" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "export const JOB_DETAILS_FETCH_ERROR" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `rg -n "export const JOB_QUEUE_PAGINATION_RANGE" apps/visualizer/frontend/src/constants/strings.ts` matches 1 line
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
</acceptance_criteria>
</task>

<task id="2.5">
<action>
Update the **existing** `apps/visualizer/frontend/src/services/__tests__/api.test.ts` (currently 72 lines, already has `describe('JobsAPI', ...)` and uses a `fetchMock = vi.fn()` / `globalThis.fetch = fetchMock` pattern). Do **not** create a second file and do **not** nest a second top-level `describe('JobsAPI')`. Reconcile in place.

Existing file structure (lines 1–72):
- Lines 1–5: imports + `fetchMock = vi.fn()` + `globalThis.fetch = fetchMock`
- Line 7 opens `describe('JobsAPI', () => {` with `beforeEach` clearing mocks
- `'should list all jobs'` (lines 12–26) currently expects `mockJobs` as a raw array — **this is now wrong** under the envelope shape
- `'should get job by id'` (28–42), `'should create job'` (44–61), `'should throw on error'` (63–71) are unchanged by Phase 2
- Line 72 closes the `describe`

Concrete edits (keep the existing mocking helper — do **not** swap to `vi.spyOn(globalThis, 'fetch')`):

**Replace** the `'should list all jobs'` test (lines 12–26) with an envelope-aware version, and **add** four new tests for list query params + `get()` `logs_limit`. Insert them contiguous with the existing list test:

```ts
  it('should list all jobs (paginated envelope)', async () => {
    const envelope = {
      total: 1,
      data: [{ id: '1', type: 'test', status: 'pending' }],
      pagination: { offset: 0, limit: 50, current_page: 1, total_pages: 1, has_more: false },
    }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => envelope,
    })

    const result = await JobsAPI.list()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/'),
      expect.objectContaining({ headers: { 'Content-Type': 'application/json' } })
    )
    expect(result).toEqual(envelope)
    expect(result.data).toHaveLength(1)
    expect(result.total).toBe(1)
  })

  it('list() forwards status, limit, and offset as query params', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        total: 0,
        data: [],
        pagination: { offset: 100, limit: 25, current_page: 5, total_pages: 0, has_more: false },
      }),
    })
    await JobsAPI.list({ status: 'pending', limit: 25, offset: 100 })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('status=pending')
    expect(url).toContain('limit=25')
    expect(url).toContain('offset=100')
  })

  it('get(id) without options calls /jobs/<id> with no query string', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', logs: [], logs_total: 0 }),
    })
    await JobsAPI.get('abc')
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toMatch(/\/jobs\/abc$/)
  })

  it('get(id, { logs_limit: 20 }) appends ?logs_limit=20', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', logs: [], logs_total: 0 }),
    })
    await JobsAPI.get('abc', { logs_limit: 20 })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('logs_limit=20')
  })

  it('get(id, { logs_limit: 0 }) still appends ?logs_limit=0 (expand path)', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', logs: [], logs_total: 0 }),
    })
    await JobsAPI.get('abc', { logs_limit: 0 })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('logs_limit=0')
  })
```

Keep the remaining three tests (`'should get job by id'`, `'should create job'`, `'should throw on error'`) unchanged — they still work under the new signatures (the plain `get(id)` / `create(...)` paths haven't changed behaviour).

Do **not** add any new imports; `describe`, `it`, `expect`, `vi`, `beforeEach` are already in the existing file's top import.
</action>
<read_first>
- apps/visualizer/frontend/src/services/__tests__/api.test.ts (all 72 lines)
- apps/visualizer/frontend/src/services/api.ts
</read_first>
<acceptance_criteria>
- `rg -n "'should list all jobs'" apps/visualizer/frontend/src/services/__tests__/api.test.ts` returns **no** matches (old name is gone)
- `rg -n "'should list all jobs \(paginated envelope\)'" apps/visualizer/frontend/src/services/__tests__/api.test.ts` matches 1 line
- `rg -n "'list\(\) forwards status, limit, and offset as query params'" apps/visualizer/frontend/src/services/__tests__/api.test.ts` matches 1 line
- `rg -n "'get\(id, \{ logs_limit: 20 \}\) appends \?logs_limit=20'" apps/visualizer/frontend/src/services/__tests__/api.test.ts` matches 1 line
- `rg -n "'get\(id, \{ logs_limit: 0 \}\) still appends \?logs_limit=0 \(expand path\)'" apps/visualizer/frontend/src/services/__tests__/api.test.ts` matches 1 line
- Only **one** top-level `describe('JobsAPI'` in the file: `rg -c "^describe\('JobsAPI'" apps/visualizer/frontend/src/services/__tests__/api.test.ts` prints `1`
- `cd apps/visualizer/frontend && npx vitest run src/services/__tests__/api.test.ts` exits 0
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npx tsc --noEmit` exits 0
- `cd apps/visualizer/frontend && npx vitest run src/services/__tests__/api.test.ts` exits 0
- `cd apps/visualizer/frontend && npx eslint src/services/api.ts src/types/job.ts src/constants/strings.ts` exits 0
- `rg -n "JobsAPI\.list\('" apps/visualizer/frontend/src/` returns no matches (no stale positional-string callers)
</verification>

<must_haves>
- `JobsAPI.list()` returns `JobsListResponse` (`{ total, data, pagination }`) instead of `Job[]`.
- `JobsAPI.list({ status, limit, offset })` forwards every provided param as a query string.
- `JobsAPI.get(id)` still returns a `Job` but with an optional `logs_total: number` field.
- `JobsAPI.get(id, { logs_limit: N })` appends `?logs_limit=N` — including `N=0` (expand path).
- `Job.logs_total` is a typed optional number on the `Job` interface.
- New copy constants `JOB_DETAILS_LOGS_TRUNCATED_HEADER`, `JOB_DETAILS_LOGS_SHOW_ALL`, `JOB_DETAILS_LOGS_SHOW_ALL_LOADING`, `JOB_DETAILS_LOADING_ARIA`, `JOB_DETAILS_FETCH_ERROR`, `JOB_QUEUE_PAGINATION_RANGE` exist in `constants/strings.ts` so plans 03 and 04 can import them without introducing inline English.
- `DashboardPage.tsx` unwraps `response.data` instead of treating `r4.value` as `Job[]` directly; the active-jobs counter continues to compute correctly.
- All existing frontend tests continue to pass; the new/updated API tests assert the envelope shape and `logs_limit` query-string passthrough on real fetch URLs.
</must_haves>
