# Phase 2: Job queue & processing UX - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the Processing page (`ProcessingPage` → `JobQueueTab` → `JobDetailModal`) feel fast and consistent even with hundreds of historical jobs and heavy log payloads, without introducing any net-new capability.

**In scope:**
- Loading UX for `JobDetailModal` when `JobsAPI.get()` is pending (JOB-03)
- Truncated + expandable log rendering on the Job Detail Modal (JOB-04)
- Classic numbered pagination on `JobQueueTab` using the existing `<Pagination>` component (JOB-05)
- Backend `GET /api/jobs/` extension to support `limit` / `offset` and return a total count
- Reconciliation of polling / socket updates (`job_created`, `job_updated`) with a paginated, page-pinned list

**Out of scope (handed to later phases):**
- Unified "Analyze" job that runs describe → score (JOB-06 — that is Phase 3)
- Backend `?fields=` query param for generic field filtering on `GET /api/jobs/<id>` — only the specific `logs_limit` pattern lands here
- Cursor-based pagination — classic numbered pagination is explicitly chosen (SEED-013)
- URL-syncing the current page number — deferred with SEED-010 (persist tab/filter state)
- Migrating the `status` filter on `JobQueueTab` to the reusable filter framework — that's Phase 4
- Pagination of other list endpoints (Catalog, Matches, Instagram, Descriptions) — out of scope for this phase; separate audit if needed
- Any job result payload lazy-loading / disclosure UX — not requested; only logs get the truncate-and-expand treatment
- Backend log retention / trimming policy — logs stay unbounded in storage; only fetch/render changes

Requirements locked by `.planning/REQUIREMENTS.md`:
- **JOB-03** — Loading state on Job Detail Modal so heavy jobs no longer appear frozen while data is fetching
- **JOB-04** — Log list truncates to the most recent N entries with a "show more" expansion for full history
- **JOB-05** — Classic numbered pagination on Job Queue; current page stays pinned across polling refreshes

</domain>

<decisions>
## Implementation Decisions

### Job Detail Modal loading UX (JOB-03)

- **D-01:** When `JobDetailModal` opens, it has two data sources: (a) the job row already in the list (`job` prop — status, progress, timestamps, id/type are already good enough to render), and (b) the full job via `JobsAPI.get(job.id)` which pulls heavy fields (`logs`, `result`, `metadata`). The modal MUST render immediately with (a) — no full-screen spinner, no skeleton over the whole card.
- **D-02:** Only the heavy sections (`logs`, `result`, `metadata` block) show a skeleton placeholder while `JobsAPI.get()` is in flight. The top identity row (id, type, status badge, created-at) and the progress bar render from the list-row data straight away.
- **D-03:** Skeleton style reuses the existing primitive vocabulary in `components/ui/page-states/` (the same `animate-pulse` + `bg-gray-200 rounded` language as `CardSkeleton` / `SkeletonGrid`). Do NOT introduce a new skeleton component unless a genuinely new shape is needed — a thin `JobSectionSkeleton` wrapper is acceptable if it keeps usage clean.
- **D-04:** If `JobsAPI.get()` fails, fall back to the list-row data already shown and surface the error inline (same `text-error` style used elsewhere in the modal). Do NOT close the modal on fetch failure — the user can still see the summary.
- **D-05:** `useEffect` in `JobDetailModal` gains a `loading` state flag (`loading = true` until the first `JobsAPI.get()` resolves or errors). Socket `job_updated` events that arrive after the initial fetch do NOT toggle `loading` back on — they silently update `localJob`.

### Log truncation & expansion (JOB-04)

- **D-06:** Hybrid truncation strategy: backend `GET /api/jobs/<id>` gains an optional `?logs_limit=N` query param. Frontend `JobsAPI.get()` calls it with `logs_limit=20` by default. The response includes both the truncated `logs` array AND a new `logs_total` count on the job payload so the UI knows whether to show an expansion affordance.
- **D-07:** Default initial log cap is **20 entries** (most recent). Refined in planning only if this is clearly wrong for the dataset — 20 is chosen because it fills roughly one modal "page" without scrolling in the current `max-h-48` log container.
- **D-08:** When `logs_total > logs.length`, render a "Show all N logs" button at the bottom of the log list (label via `constants/strings.ts`). Clicking it calls `JobsAPI.get(id, { logs_limit: 0 or omitted })` — a second fetch that returns the full log array, then replaces `localJob.logs`. No partial "load more" pagination inside the log list; it's binary: truncated or full.
- **D-09:** `logs_limit=0` means "no limit — return everything." This matches the intuition of "expand to full history." Any positive integer is clamped to `max(1, min(limit, hard_ceiling))` where `hard_ceiling` is set sensibly in planning (e.g. 10_000) to protect the backend from pathological requests.
- **D-10:** Backwards compatibility: if `logs_limit` is omitted, the backend returns logs unlimited — this preserves existing callers (including any tests) that don't pass the param. Frontend `JobsAPI.get()` is the only caller changed to pass `logs_limit=20` by default.
- **D-11:** The log-count indicator also powers a small header hint on the logs section — e.g. `JOB_DETAILS_LOGS` label reads `"Logs (20 of 347)"` when truncated. This gives the user honest information before they decide to expand.

### Pagination on the Job Queue (JOB-05)

- **D-12:** Backend `GET /api/jobs/` gains `limit` and `offset` query params and returns the paginated response shape via the existing `success_paginated()` helper in `apps/visualizer/backend/utils/responses.py`:
  ```
  { "total": N, "data": [...jobs], "pagination": { offset, limit, current_page, total_pages, has_more } }
  ```
  The pre-existing implicit `LIMIT 50` in `database.list_jobs()` is replaced by the explicit `limit`/`offset` plumbing.
- **D-13:** Backwards compatibility: if no `limit`/`offset` query params are provided, the backend MUST still return something usable. Chosen default: `limit=50, offset=0`, same effective behaviour as today (top 50 most recent), but wrapped in the paginated response envelope. This is a breaking response-shape change for `JobsAPI.list()`; tests and the frontend API wrapper are updated together.
- **D-14:** A new `count_jobs(db, status=None) -> int` helper is added to `apps/visualizer/backend/database.py` next to `list_jobs`. It runs `SELECT COUNT(*) FROM jobs [WHERE status = ?]`, matching the filter shape of `list_jobs`. Used by the API layer to populate `total`.
- **D-15:** Default page size on the frontend is **50** — matches the current implicit server cap and SEED-013's "30 or 50 is typical" guidance. No user-facing page-size control in this phase.
- **D-16:** `JobQueueTab` consumes the existing `<Pagination>` primitive at `components/ui/Pagination.tsx`. It also consumes the `usePagination` hook at `hooks/usePagination.ts` for offset/currentPage/totalPages bookkeeping. No new pagination primitive is introduced.
- **D-17:** The `<Pagination>` component renders under the jobs table, inside the same `<Card>`, matching CatalogTab's pattern (`components/images/CatalogTab.tsx:527`). Hidden automatically when `totalPages <= 1` (existing behaviour).
- **D-18:** Filter-change behaviour: changing the `status` filter (whenever/if it is re-enabled by a later phase, or any future filter on JobQueueTab) MUST reset the page to 1. This is already the idiomatic behaviour around `usePagination.reset()` — wire it into the filter change handler.
- **D-19:** The "Refresh" button in `JobQueueTab` keeps the current page — it re-fetches the current `{limit, offset}` slice, does NOT jump to page 1. This matches the user's mental model that Refresh means "re-check what I'm looking at."

### Pagination ↔ live updates contract

- **D-20:** Page stays pinned across socket events. When `job_created` or `job_updated` fires, the frontend MUST NOT auto-jump to page 1.
- **D-21:** On socket events, the frontend refetches the current `{limit, offset}` slice from the server rather than mutating the local `jobs` array ad-hoc. This keeps `total` and `total_pages` accurate (new jobs shift later pages, completed jobs may leave the visible page, etc.) and prevents drift between client and server state.
- **D-22:** To avoid thrashing on bursty sockets (many `job_updated` events during a running batch), refetches are **debounced** in the socket handler (~250–500 ms trailing debounce — planner picks the exact value). The `Refresh` button triggers an immediate refetch that bypasses the debounce.
- **D-23:** In-place optimistic updates remain allowed for user-initiated actions on rows currently on screen (cancel, retry) — those mutate local state immediately for responsiveness, then reconcile with the next refetch. This preserves the current UX where the Cancel button flips the row to `cancelled` without waiting for the socket echo.
- **D-24:** `ProcessingPage` owns the `{jobs, total, currentPage}` triple and passes the slice into `JobQueueTab`. Lifting pagination state into `ProcessingPage` keeps the container/presenter split (per Phase 1 / `CONVENTIONS.md`) and matches how CatalogTab handles pagination on the images side. `JobQueueTab` becomes a purer presenter plus local UI state (selected row, cancelling id, etc.).
- **D-25:** The `useJobSocket` subscription continues to live on `ProcessingPage`. The `handleJobCreated` / `handleJobUpdated` callbacks change from "mutate array" to "schedule debounced refetch of current page" (plus the optimistic-update carve-out in D-23).

### Copy & constants

- **D-26:** All new UI strings — "Show all N logs" affordance, logs section header with count, the "loading job details" skeleton aria-label, any aria-labels for pagination interactions unique to this tab — go through `apps/visualizer/frontend/src/constants/strings.ts`, continuing the Phase 1 convention (D-14 in Phase 1).

### Claude's Discretion

- Exact debounce window for socket-driven refetch (D-22). Pick something in the 250–500 ms trailing range based on a quick empirical feel; tune if a batch job visibly janks.
- Exact skeleton shape for the logs / result / metadata sections (D-02/D-03) — reuse `animate-pulse` primitives; the visual match is "it looks like the section that will fill in," not pixel-perfect.
- Whether to co-locate the new `JobSectionSkeleton` (or equivalent) next to `JobDetailModal.tsx` or under `components/ui/page-states/`. Planner picks based on reuse potential; default to co-located.
- Backend `hard_ceiling` for `logs_limit` (D-09) — pick a safe upper bound (e.g. 10_000). Must be higher than any realistic log count we've seen, low enough to stop a malicious `logs_limit=10000000` from being pathological.
- Test structure — backend tests for paginated `/api/jobs/` (total count, limit/offset correctness, backwards-compat default), backend test for `?logs_limit=N` truncation on `/api/jobs/<id>`, frontend tests for modal loading state, log expansion toggle, pagination reset on filter change, and page-pinning across socket events. Follow existing patterns in `apps/visualizer/backend/tests/test_jobs_api.py` and `apps/visualizer/frontend/src/components/**/__tests__/`.
- Whether `ProcessingPage` should also expose the current page in a hash/query param for deep-linking. **Default: no** — SEED-013 explicitly marks URL syncing as out of scope for this phase, and SEED-010 owns that work.

### Folded Todos

*None — the single pending todo (vision pipeline safety nets) is unrelated to Phase 2 scope.*

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — JOB-03, JOB-04, JOB-05 exact wording + acceptance conditions
- `.planning/ROADMAP.md` §"Phase 2: Job queue & processing UX" — the four success criteria
- `.planning/seeds/SEED-002-job-modal-loading-ux.md` — loading-state + log truncation motivation, breadcrumbs, recommended "last N with expansion" strategy
- `.planning/seeds/SEED-013-paginate-job-queue.md` — pagination motivation, backend audit checklist, polling-interaction decision log, scope fences

### Codebase conventions
- `.planning/codebase/CONVENTIONS.md` §"API responses (Flask)" — `success_paginated()` is the canonical paginated-response shape; §"Frontend architecture" — container/presenter split, centralized `constants/strings.ts` copy
- `.planning/codebase/STRUCTURE.md` — monorepo layout (`apps/visualizer/{backend,frontend}`)
- `.planning/codebase/TESTING.md` — pytest for backend, vitest in `__tests__/` for frontend
- `.planning/phases/01-matching-review-polish/01-CONTEXT.md` — Phase 1 conventions being carried forward (centralised strings D-14, inline state patterns, container/presenter split)

### Key files touched by this phase

**Backend:**
- `apps/visualizer/backend/database.py` — `list_jobs` (line ~154) grows `limit`/`offset` params; new `count_jobs(db, status=None)` helper added next to it; `get_job` (line ~91) unchanged, but the API wrapper that calls it learns to trim logs
- `apps/visualizer/backend/api/jobs.py` — `list_all_jobs` (line ~6) switches to `success_paginated()`; `get_job_details` (line ~28 per SEED-002 breadcrumbs) grows `logs_limit` query param handling
- `apps/visualizer/backend/utils/responses.py` — `success_paginated()` (line 57) reused as-is
- `apps/visualizer/backend/tests/test_jobs_api.py` — extend with limit/offset, total count, default-behaviour, logs truncation tests

**Frontend:**
- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` — add loading state (D-01..D-05), render skeletons for heavy sections, consume `logs_limit` by default, wire "Show all N logs" affordance
- `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` — consume slice + total from props; render `<Pagination>`; remove the "full list" assumption; optimistic update carve-out per D-23
- `apps/visualizer/frontend/src/pages/ProcessingPage.tsx` — lift pagination state; refetch current slice on socket events (debounced per D-22); pass slice + total + pagination props down into `JobQueueTab`
- `apps/visualizer/frontend/src/services/api.ts` — `JobsAPI.list()` returns the paginated envelope (breaking internal shape change); `JobsAPI.get()` gains optional `logs_limit` and calls with `20` by default
- `apps/visualizer/frontend/src/types/job.ts` (or wherever `Job`/`JobsListResponse` live) — types updated for `logs_total` on the job payload and for the paginated envelope on list
- `apps/visualizer/frontend/src/hooks/usePagination.ts` — reused as-is (already handles offset/limit/current-page bookkeeping)
- `apps/visualizer/frontend/src/components/ui/Pagination.tsx` — reused as-is
- `apps/visualizer/frontend/src/components/ui/page-states/SkeletonGrid.tsx` — skeleton vocabulary to match (don't duplicate — factor `CardSkeleton`-like shapes if needed)
- `apps/visualizer/frontend/src/constants/strings.ts` — add "Show all N logs" and related copy

No external ADRs or specs — requirements fully captured in decisions above and the two seed docs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`<Pagination>`** (`components/ui/Pagination.tsx`) — classic numbered pagination with ellipsis and prev/next, already covered by `__tests__/Pagination.test.tsx`. Consumed by `CatalogTab` today — the pattern to mirror.
- **`usePagination`** (`hooks/usePagination.ts`) — offset/limit/currentPage/totalPages/hasMore bookkeeping + `goToPage`/`nextPage`/`prevPage`/`reset`. Designed exactly for this shape.
- **`success_paginated()`** (`backend/utils/responses.py:57`) — canonical backend response shape; already used by `api/images.py`, `api/analytics.py`, `api/identity.py`. The Job Queue joins that club.
- **Skeleton primitives** (`components/ui/page-states/SkeletonGrid.tsx`) — `animate-pulse` + `bg-gray-200 rounded` vocabulary. Reuse the visual language; wrap in a `JobSectionSkeleton` only if needed for clarity.
- **`useJobSocket`** (`hooks/useJobSocket.ts`) — existing subscription, stays wired to `ProcessingPage`; only the handler bodies change (refetch instead of mutate).
- **`constants/strings.ts`** — project convention, same as Phase 1.
- **`<Card>`**, **`<Badge>`**, **`<Button>`** — existing primitives used throughout the Job UI; no changes.

### Established Patterns
- **Paginated list endpoints return `{ total, data, pagination }`** via `success_paginated()` — `/api/jobs/` joins this pattern.
- **Container/presenter split** — page-level component owns data + pagination state; tab-level component renders rows + UI state (per Phase 1 D-14 lineage).
- **Centralised copy via `constants/strings.ts`** — Phase 1 decision carries forward.
- **Optimistic UI mutations for user-initiated actions** — `cancelJob`/`retryJob` in `JobQueueTab` already mutate local state before the server echo; this phase preserves that carve-out around the new refetch flow.
- **Disable-on-action button pattern** — same `cancellingId` / `retryingId` local state in `JobQueueTab` is kept.

### Integration Points
- **`ProcessingPage` → `JobQueueTab`** — currently passes `{ jobs, setJobs, jobsLoading, connected, onRefreshJobs }`. After this phase it passes `{ jobs, total, currentPage, totalPages, onPageChange, jobsLoading, connected, onRefreshJobs }` (or equivalent). `setJobs` becomes an implementation detail of the page, used for optimistic updates only.
- **`JobDetailModal`** is self-fetching today (`JobsAPI.get()` in its own `useEffect`). Stays self-fetching — only the inner UX changes (loading state, log truncation). No lifting of the fetch into the parent.
- **Socket events** — `job_created`, `job_updated` on `useJobSocket` now drive a debounced refetch instead of direct array mutation. This is the biggest behavioural change.

</code_context>

<specifics>
## Specific Ideas

- **"Keep it dead simple"** — consistent with Phase 1 philosophy. No new pagination style (no infinite scroll, no cursors), no new skeleton library, no toast system. Reuse what exists.
- **Loading UX: honest but unobtrusive** — the user should never stare at a frozen-looking modal, but they also shouldn't see a flash of empty placeholders for data that was already on their screen (the list row). Hence the hybrid: identity/status instant, heavy sections skeleton.
- **"Logs (20 of 347)" header hint** — small detail but gives the user honest signal before they commit to expanding. Same ethos as Phase 1's inline "Rejected" badge: quiet, inline, informative.
- **Refresh semantics** — user's mental model: "Refresh means re-check this page", not "go back to the top." Explicit decision, not a default fallback.

</specifics>

<deferred>
## Deferred Ideas

- **Unified "Analyze" job (describe → score in one)** — JOB-06, Phase 3. Explicitly next phase.
- **URL-syncing the current page number on Job Queue** — rides with SEED-010 (persist tab/filter state) in a later milestone.
- **Filter-framework migration of the Job Queue's status filter** — Phase 4 (FILTER-01/02) consumer work.
- **Generic `?fields=` query param on `GET /api/jobs/<id>`** — out of scope; only the specific `logs_limit` knob lands here. If future heavy fields emerge (e.g. full `result` blobs get huge), consider a separate seed.
- **Result payload lazy-load / disclosure toggle** — SEED-002 mentions it but not a current user pain; deferred until someone reports it.
- **Backend log retention policy (server-side pruning)** — logs stay unbounded on disk; only fetch + render change here. If DB size becomes a problem, a separate seed.
- **Pagination audit of other list endpoints** (Catalog/Matches/Instagram/Descriptions) — separate concern; SEED-013 explicitly marks this out of scope.
- **Per-row "expand this job's logs inline in the list" affordance** — not requested; full detail lives in the modal.
- **"N new jobs — jump to page 1" indicator** — SEED-013 notes it as nice-to-have, out of scope here.

### Reviewed Todos (not folded)
*None — the single pending todo ("Improve vision pipeline safety nets and SR2 support") is unrelated to Phase 2 scope.*

</deferred>

---

*Phase: 02-job-queue-and-processing-ux*
*Context gathered: 2026-04-17*
