---
id: SEED-013
status: dormant
planted: 2026-04-17
planted_during: v2.0 (milestone complete)
trigger_when: Job queue / processing page gets dedicated attention
scope: Small
---

# SEED-013: Paginate the Job Queue

## Why This Matters

The Job Queue tab on the Processing page currently renders every job in a single
flat list. As the job history accumulates (every describe, score, match, and
identity run creates a job), this list:

1. **Gets slow to render.** All rows mount at once; each row has status indicators,
   timestamps, progress, and action buttons. Performance degrades linearly with job
   count.
2. **Pushes expensive payloads over the wire.** If the API returns the full job
   history on every poll/refresh, bandwidth and serialization cost scale with
   history depth even though the user only looks at the most recent.
3. **Will only get worse.** Background batch jobs (batch describe, batch score,
   batch match) produce many jobs per session; a user running the tool regularly
   will hit hundreds or thousands of historical jobs fast.

**Primary pain = performance.** UX browsability is a side benefit but not the
driver — the queue is already sorted by recency, so the top of the list is
usually what the user wants.

The fix is well-understood: paginate the list. The app already has a solid,
reusable `Pagination` component (`components/ui/Pagination.tsx`) with correct
ellipsis behavior for many pages — this seed is mostly about *consuming* it.

## When to Surface

**Trigger:** Job queue / processing page gets dedicated attention

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:

- Processing page or Job Queue redesign
- Performance work on the frontend (slow page renders, long lists)
- Backend API pagination audit (if jobs isn't paginated, other list endpoints may
  have the same problem)
- User feedback about "the jobs page is slow" or "too many old jobs cluttering
  the queue"

## Scope Estimate

**Small** — a few hours to a short phase. Three straightforward pieces:

### Piece 1 — Verify backend pagination support (first task at planning)

Before writing frontend code, audit `apps/visualizer/backend/api/jobs.py`:

- Does the list-jobs endpoint accept `limit` / `offset` (or `page` / `page_size`)?
- Does it return a total count so the frontend can render page numbers?
- If not, add `limit` / `offset` + total count to the response shape. Keep the
  unpaginated default backwards-compatible or version the response.

### Piece 2 — Wire the existing `<Pagination>` component into `JobQueueTab`

- `components/processing/JobQueueTab.tsx` adopts the existing
  `components/ui/Pagination.tsx` (classic numbered pagination with first/last/
  neighbors + ellipsis).
- Pick a default page size (30 or 50 is typical for job-queue rows).
- Pass `currentPage`, `totalPages`, and `onPageChange` into `<Pagination>`.
- Reset to page 1 when filters change (to avoid landing on an out-of-range page).

### Piece 3 — Decide interaction with polling / live updates

The Job Queue polls for updates. Decide:

- **Keep page pinned** — user stays on whatever page they selected; polling only
  refreshes that page's contents.
- **Auto-jump to page 1 on new job creation** — may be surprising; probably reject.
- **Indicator for "N new jobs — jump to page 1"** — nice-to-have, out of scope for
  Small unless trivially cheap.

Default recommendation: keep page pinned. Polling refreshes the current page's
rows; new jobs silently appear on page 1 and the user can navigate to see them.

### Out of scope

- Cursor-based pagination — overkill for this dataset, classic pagination is fine
- URL-syncing the page number — nice but not required (would naturally roll in
  with SEED-007 / SEED-010 work)
- Server-side filtering rework — if current filters work on the full list, they
  need to move server-side when pagination goes in; if they already work
  server-side, no change needed. Verify at planning time.
- Non-job list pagination (if Catalog/Matches/Instagram lists have the same
  unpaginated problem, those are separate seeds — this one stays scoped to jobs)

## Breadcrumbs

### Frontend
- `apps/visualizer/frontend/src/components/processing/JobQueueTab.tsx` — the list
  that needs pagination wired in
- `apps/visualizer/frontend/src/components/ui/Pagination.tsx` — existing, reusable,
  already has tests; consume as-is
- `apps/visualizer/frontend/src/components/ui/__tests__/Pagination.test.tsx` —
  coverage already in place
- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` — unaffected
  but good to sanity-check that opening a job from page N keeps the user on page N

### Backend
- `apps/visualizer/backend/api/jobs.py` — list-jobs endpoint; verify / add
  `limit`/`offset` and total count
- `apps/visualizer/backend/database.py` — job store; may need a `count()` helper
  if one doesn't exist
- `apps/visualizer/backend/jobs/runner.py` — job lifecycle; not changed by this
  seed, just context

### Related seeds
- SEED-007 (reusable filter component) — if job-queue filters get rebuilt against
  the shared framework, pagination should plug into the same state shape
- SEED-010 (persist tab and filter state in-memory) — the job-queue page number
  should probably follow the same persistence rules as filters (in-memory,
  resets on reload)
- SEED-002 (job modal loading UX) — adjacent; same processing area of the app

## Notes

User feedback (2026-04-17):

> "Job queue should be paginated."

Decision log:
- **Primary driver:** performance (heavy render, list grows unbounded).
- **Style:** classic numbered pagination via the existing
  `components/ui/Pagination.tsx`. User explicitly chose to reuse the current
  component rather than introduce infinite scroll or cursor-based.
- **Backend:** unknown whether `jobs.py` paginates today; verify first at
  planning time.
- **Scope:** Small — this is plumbing work with an existing primitive.

Phased rollout (single phase is probably enough):
1. Backend: confirm or add `limit`/`offset` + total to the jobs list endpoint.
2. Frontend: wire `<Pagination>` into `JobQueueTab`, choose default page size,
   reset to page 1 on filter change, keep page pinned across polls.
3. Smoke test with a large synthetic job set (>500 jobs) to confirm render speed
   and correctness.
