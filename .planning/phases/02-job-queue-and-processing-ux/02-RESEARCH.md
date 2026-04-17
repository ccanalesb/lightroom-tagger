# Phase 2: Job queue & processing UX — Research

**Researched:** 2026-04-17
**Status:** Complete
**Scope:** Validate CONTEXT.md decisions against current codebase state; capture concrete line numbers, function signatures, and test-suite entry points that plans will reference.

---

## RESEARCH COMPLETE

## Summary

Phase 2 is a **pure refactor + UX polish** pass. There is **no net-new capability**. All three requirements (JOB-03, JOB-04, JOB-05) consume primitives and response shapes that already exist in the codebase. The single behavioural change that needs care is the pagination ↔ socket reconciliation: `ProcessingPage` currently mutates the `jobs` array on each `job_created` / `job_updated` — after Phase 2 it must debounce a refetch of the current `{limit, offset}` slice instead.

Validation of all 26 locked decisions in CONTEXT.md against current code: **all decisions are implementable with the files and APIs identified, no contradictions found**.

---

## JOB-03: Loading state on `JobDetailModal`

### Current behaviour (apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx)

- Line 77: `const [localJob, setLocalJob] = useState<Job>(job)` — seeded from the list-row `job` prop.
- Lines 81–89: `useEffect(() => { JobsAPI.get(job.id).then(setLocalJob).catch(console.error) }, [job.id])` — fetches the full job (with `logs`, `result`, `metadata`) but **does not track a loading flag**. The modal renders immediately from the list-row data, but any sections driven by heavy fields (`logs`, `result`, `metadata`) render with whatever was on the list row — no visual cue that a fetch is in flight.
- Lines 301–317: the `displayJob.error` block shows errors from the job itself, but there is **no fetch-error** path (the `.catch` just logs).

### What the plan must add

- A `loading` flag set to `true` until the first `JobsAPI.get()` resolves *or* rejects.
- A `fetchError` flag (`string | null`) captured in the `.catch` so the modal can show an inline `text-error` hint per D-04.
- Socket `job_updated` events (lines 91–109) must **not** toggle `loading` back on — they silently update `localJob` (D-05). The existing handler already just calls `setLocalJob`, which is the correct shape — no change needed beyond not gating it on `loading`.
- Skeleton placeholders for the heavy sections (`metadata`, `result`, `logs`) while `loading` is true. Per D-03, reuse the `animate-pulse bg-gray-200 rounded` vocabulary from `components/ui/page-states/SkeletonGrid.tsx` (see lines 17–26 — `CardSkeleton` shape). A small co-located `JobSectionSkeleton` (or inline markup) is acceptable per Claude's Discretion.

### Identity row / progress bar unchanged

Lines 164–187 render id / type / status / created-at / progress from `displayJob` which is already seeded from the list-row — these sections render instantly per D-01/D-02.

---

## JOB-04: Log truncation & expansion

### Backend today (apps/visualizer/backend/api/jobs.py)

- Line 27–34: `get_job_details(job_id)` reads query-string args (currently none) and returns the full job (including all logs) via `jsonify(get_job(...))`.
- Logs are stored JSON-serialized in the `jobs.logs` column (`database.py:42` schema, `database.py:13–22` `_deserialize_job`).

### What the plan must add

- `?logs_limit=N` query param on `GET /api/jobs/<id>`. Parse with `request.args.get('logs_limit', type=int)`. Semantics (D-09, D-10):
  - Missing → return unlimited (back-compat).
  - `0` → return unlimited (expand intent).
  - Positive → clamp to `max(1, min(limit, HARD_CEILING))` where `HARD_CEILING = 10_000` (Claude's Discretion, in line with D-09).
- Response envelope additions (D-11):
  - `logs` field is replaced by truncated tail (last N entries, preserving chronological order).
  - New `logs_total: int` field = original `len(job['logs'])` **before** truncation.
- Implementation note: do the truncation in the route (or a thin helper in `api/jobs.py`) — do **not** push it into `database.get_job` (which is used by several callers that want unlimited logs).

### Frontend today

- `JobsAPI.get()` (services/api.ts:114–115) takes only `id` today. Needs an optional `{ logs_limit?: number }` shape.
- `JobDetailModal.tsx:81–89` calls `JobsAPI.get(job.id)` — bumps to `JobsAPI.get(job.id, { logs_limit: 20 })` per D-07.
- Log render (lines 331–356) currently just maps `displayJob.logs`. Needs:
  - Header reads `"Logs ({shown} of {logs_total})"` when `logs_total > logs.length` (D-11). Otherwise `"Logs"` (or `"Logs (N)"`).
  - "Show all N logs" button rendered below the list when `logs_total > logs.length`. Click → second `JobsAPI.get(id, { logs_limit: 0 })` → `setLocalJob(freshJob)`.
  - When expanded, button disappears (since `logs_total === logs.length` after the second fetch).
- `types/job.ts` grows `logs_total?: number` on `Job`.

### Strings (D-26)

Add to `constants/strings.ts`:
- `JOB_DETAILS_LOGS_SHOW_ALL = 'Show all {count} logs'` (factored into a small formatter helper).
- `JOB_DETAILS_LOGS_HEADER_TRUNCATED = 'Logs ({shown} of {total})'` (or similar — keep close to existing `JOB_DETAILS_LOGS = 'Logs'` on line 230).

---

## JOB-05: Pagination on Job Queue

### Backend today

- `database.list_jobs` (database.py:154–165): takes `status` + `limit=50`. **No `offset`, no `total` count.** The implicit top-50 cap is the behaviour that's changing.
- `api/jobs.py:6–10` `list_all_jobs`: passes `status=` through and returns raw `jsonify(jobs)` (list, not envelope). This is the breaking response shape change.
- `utils/responses.py:57–73` `success_paginated(data, total, offset, limit)` — **already exists, already used by `api/images.py`, `api/analytics.py`, `api/identity.py`**. Produces exactly `{ total, data, pagination: { offset, limit, current_page, total_pages, has_more } }` — the target shape.

### What the plan must add

- New helper `database.count_jobs(db, status=None) -> int` next to `list_jobs` (D-14). Exact SQL: `SELECT COUNT(*) FROM jobs` (no filter) or `SELECT COUNT(*) FROM jobs WHERE status = ?` (filtered). Mirror the branching structure of `list_jobs`.
- Signature update: `list_jobs(db, status=None, limit=50, offset=0)` — keep defaults so internal Python callers that don't pass `offset` still work. Add `OFFSET ?` to both SQL branches.
- Route update: `api/jobs.py:7–10`:
  ```python
  def list_all_jobs():
      status = request.args.get('status')
      limit = request.args.get('limit', default=50, type=int)
      offset = request.args.get('offset', default=0, type=int)
      limit = max(1, min(limit, 500))  # ceiling, Claude's Discretion
      offset = max(0, offset)
      jobs = list_jobs(current_app.db, status=status, limit=limit, offset=offset)
      total = count_jobs(current_app.db, status=status)
      return success_paginated(jobs, total=total, offset=offset, limit=limit)
  ```
- **Back-compat note (D-13):** Callers that hit `/api/jobs/` with no query params get `{ total, data: [...top 50...], pagination: {...} }` — effective behaviour unchanged (top 50), shape changed. `JobsAPI.list()` in the frontend is the only first-party caller and will be updated in the same plan.

### Tests

- `apps/visualizer/backend/tests/test_jobs_api.py` — extend:
  - `test_list_jobs_returns_paginated_envelope` — no params, assert `response.json` has `total`, `data`, `pagination.current_page==1`.
  - `test_list_jobs_respects_limit_and_offset` — seed 4 jobs, query `?limit=2&offset=2`, assert `len(data)==2` and second page.
  - `test_list_jobs_total_count_matches_status_filter` — seed 3 pending + 2 completed, query `?status=pending`, assert `total==3`.
  - `test_list_jobs_default_limit_50` — no params, seed 60 jobs, assert `len(data)==50` and `total==60`.
  - Existing `test_list_jobs` (line 22–25) must be updated — the assertion `assert response.json == []` becomes `assert response.json['data'] == []` and `assert response.json['total'] == 0`.
- New test: `test_get_job_truncates_logs_when_logs_limit_set` — seed a job with 30 logs, `?logs_limit=10`, assert `len(data.logs)==10` and `data.logs_total==30`.
- New test: `test_get_job_logs_limit_zero_returns_all` — seed 5 logs, `?logs_limit=0`, assert all 5 returned and `logs_total==5`.

### Frontend today

- `JobsAPI.list(status?)` (services/api.ts:110–112) returns `Job[]`. Response shape changes to `{ total, data: Job[], pagination: PaginationMeta }` (mirror `ImagesAPI.listInstagram` shape at lines 176–186).
- `ProcessingPage` (pages/ProcessingPage.tsx:48–165): owns `jobs` + `jobsLoading`. Needs to also own `{ total, currentPage, totalPages, pageSize, offset }`.
  - `refreshJobs` (lines 57–67) needs to take the current `offset` / `limit` and stash `total`.
  - Socket handlers (`handleJobCreated` lines 91–93, `handleJobUpdated` lines 95–97) change from array mutation to **debounced refetch** (D-21/D-22). Exact debounce window: **300ms trailing** (Claude's Discretion, inside the 250–500ms D-22 range).
  - The `Refresh` button (`onRefreshJobs` prop → `JobQueueTab:94–103`) triggers an **immediate** refetch of the current page (D-19 / bypass debounce).
  - `useJobSocket` subscription stays wired here; only the callbacks change.
- `JobQueueTab` (components/processing/JobQueueTab.tsx:30–36) prop shape grows:
  - Add `currentPage: number`, `totalPages: number`, `onPageChange: (page: number) => void`.
  - Keep `setJobs` **only** for the two optimistic-update callsites (D-23): `cancelJob` line 54–56 (`setJobs(prev => prev.map(...))`) and `retryJob` line 68–70. Both stay as-is.
  - Render `<Pagination>` below the table (inside the existing `<Card padding="none">` at line 132), mirroring `CatalogTab.tsx:527–533` pattern.
- `hooks/usePagination.ts` — used as-is. `ProcessingPage` calls `usePagination(50, total)` and destructures `{ pagination: { offset, limit, currentPage, totalPages }, goToPage }`.

### Refresh / polling semantics (D-19, D-20, D-22)

| Event | Current behaviour | Phase 2 behaviour |
|---|---|---|
| Page load | `load()` → `setJobs(data)` | `load()` → `setJobs(data.data)`, `setTotal(data.total)` |
| `Refresh` button | `refreshJobs()` → `JobsAPI.list()` full | `refreshJobs(immediate=true)` → fetch **current** `{limit, offset}` slice, bypass debounce |
| `job_created` socket | prepend to `jobs` | schedule debounced refetch of current page (300ms trailing) |
| `job_updated` socket | map-replace in `jobs` | schedule debounced refetch of current page (300ms trailing) |
| `cancelJob` / `retryJob` | optimistic `setJobs(prev => prev.map(...))` | **unchanged** (D-23 carve-out) |
| Page change | N/A | `goToPage(n)` → refetch `offset = (n-1) * limit` |
| `pagination.current_page > total_pages` (page drift after deletes) | N/A | clamp `currentPage` to `max(1, total_pages)` and refetch |

### Page-drift safety (implicit in D-21)

When a refetch returns `total < offset`, the current page has "fallen off the end" (e.g. the user was on page 3 and enough jobs above them got deleted). The fix: if the returned `data.length === 0` and `total > 0`, `goToPage(pagination.total_pages)` and refetch. This is a small wrinkle the plan should handle explicitly.

---

## Validation Architecture (out of scope per config)

`nyquist_validation_enabled = false` in `.planning/config.json`. No VALIDATION.md is required. Standard pytest + vitest coverage is the validation strategy.

---

## Key codebase touchpoints (line-numbered, for planner `read_first`)

### Backend
- `apps/visualizer/backend/api/jobs.py:6–10` (`list_all_jobs`) — route switches to `success_paginated`
- `apps/visualizer/backend/api/jobs.py:27–34` (`get_job_details`) — route grows `logs_limit`
- `apps/visualizer/backend/database.py:154–165` (`list_jobs`) — grows `offset`, new `count_jobs` added next to it
- `apps/visualizer/backend/utils/responses.py:57–73` (`success_paginated`) — reused as-is
- `apps/visualizer/backend/tests/test_jobs_api.py:1–65` — extend

### Frontend
- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx:77–109` (loading + socket); `:331–356` (log section)
- `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx:30–216` (whole component — prop-shape + pagination render)
- `apps/visualizer/frontend/src/pages/ProcessingPage.tsx:48–165` (lift pagination state + debounced refetch)
- `apps/visualizer/frontend/src/services/api.ts:110–132` (`JobsAPI.list` envelope, `JobsAPI.get` params)
- `apps/visualizer/frontend/src/types/job.ts:9–25` (`Job` grows `logs_total?`)
- `apps/visualizer/frontend/src/hooks/usePagination.ts` (used as-is)
- `apps/visualizer/frontend/src/components/ui/Pagination.tsx` (used as-is)
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx:527–533` (pattern to mirror)
- `apps/visualizer/frontend/src/constants/strings.ts:224–230` (extend with log-expansion copy)

### Tests (new / extended)
- `apps/visualizer/backend/tests/test_jobs_api.py` (extended)
- `apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx` (new file — loading, log truncation, expand)
- `apps/visualizer/frontend/src/components/processing/__tests__/JobQueueTab.test.tsx` (new file — pagination render, Refresh-pins-page, filter-reset contract if applicable)
- `apps/visualizer/frontend/src/pages/__tests__/ProcessingPage.test.tsx` (new file — socket debounced refetch, page pinning across job_updated)
- `apps/visualizer/frontend/src/services/__tests__/api.test.ts` (extend — `JobsAPI.list` returns envelope, `JobsAPI.get` appends `logs_limit`)

---

## Open questions resolved during research

| Question | Resolution |
|---|---|
| Does `success_paginated` already handle `total` correctly? | Yes — `utils/responses.py:57–73`, already in use by three other APIs. |
| Is the existing `list_jobs(limit=50)` called from anywhere else that would break? | Used by the route (change together) and the socket-reconnect recovery path — check `hooks/useJobSocket.ts` (it does not call `list_jobs` directly; `ProcessingPage` owns the list fetch). Safe. |
| Is there a tests fixture helper for seeding jobs? | No — tests create jobs via the POST API (see `test_jobs_api.py:27–33`). New tests follow the same pattern or insert directly via `database.create_job` for log-count tests. |
| Does `JobQueueTab` currently assume it gets the full list? | Yes — its empty-state check `jobs.length === 0` (line 109) stays correct per-page; but the `Disconnected`/empty-state copy needs no change. No code depends on "this is everything ever." |

---

*Phase: 02-job-queue-and-processing-ux*
*Research completed: 2026-04-17*
