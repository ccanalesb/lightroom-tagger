# Phase 2: Job queue & processing UX - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `02-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 02-job-queue-and-processing-ux
**Areas discussed:** Pagination ↔ live updates contract, Log truncation strategy, JobDetailModal loading UX, Page size & reset-on-filter behaviour

---

## Pagination ↔ live updates contract

How should socket `job_created` / `job_updated` events interact with a paginated backend list? SEED-013 says "keep page pinned" — but does a new job on page 1 update the visible row count on page 3? Should we refetch on socket events or mutate locally?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep page pinned + refetch current slice on socket events (debounced) | User stays on whatever page they selected; socket events trigger a debounced refetch of the current `{limit, offset}` slice so `total` / `total_pages` stay accurate | ✓ |
| Keep page pinned + mutate local array only | Never refetch; apply socket event deltas directly to the in-memory `jobs` array | |
| Auto-jump to page 1 on `job_created` | Surprising; probably rejected (explicitly flagged in SEED-013) | |

**User's choice:** Recommended option (refetch current slice, debounced)
**Notes:** Preserves optimistic-update carve-out for user-initiated actions (cancel/retry) so the UI stays responsive. Debounce window left to planner (250–500 ms trailing range).

---

## Log truncation strategy (JOB-04)

Three strategies with different wire-cost / complexity tradeoffs.

| Option | Description | Selected |
|--------|-------------|----------|
| Frontend-only truncation | Backend returns all logs always; frontend shows last N with "Show all" toggle | |
| Backend query param (`?logs_limit=N`) | Lighter initial fetch; "Show all" refetches with no limit | |
| Hybrid: return last 20 inline + `logs_total` count; expansion triggers separate fetch | Best of both — snappy default, explicit user choice to expand, honest "20 of 347" hint | ✓ |

**User's choice:** Recommended option (hybrid)
**Notes:** Default `logs_limit=20` inline; `logs_limit=0` or omission returns unlimited for "Show all." Backwards-compat: omitted param still returns full logs so existing callers are not broken. Hard ceiling chosen by planner (~10_000).

---

## JobDetailModal loading UX (JOB-03)

What does the modal show while `JobsAPI.get()` is resolving?

| Option | Description | Selected |
|--------|-------------|----------|
| Full-modal skeleton | Skeleton the entire modal body while the fetch resolves — most honest signal, but flashes empty where the list row already had data | |
| Stale data + small spinner/progress strip | Keep the list-row data visible, add a tiny spinner; no empty flash but data is stale-looking | |
| Hybrid: identity/status/progress instant from list row, skeleton the heavy sections only (logs, result, metadata) | Fastest honest signal — user sees the job identity immediately, heavy sections animate in as they arrive | ✓ |

**User's choice:** Recommended option (hybrid)
**Notes:** If `JobsAPI.get()` fails, fall back to the list-row data and surface the error inline. Do not close the modal on fetch failure. Socket events after the initial fetch silently update without re-toggling loading.

---

## Page size & reset-on-filter behaviour (JOB-05)

SEED-013 suggests 30 or 50. Current backend hardcodes `LIMIT 50`. Filter changes and Refresh button semantics need locking in.

| Option | Description | Selected |
|--------|-------------|----------|
| Page size 50, reset to page 1 on status-filter change, Refresh keeps current page | Matches current implicit cap, mental model "Refresh = re-check this page" | ✓ |
| Page size 30, reset to page 1 on filter, Refresh jumps to page 1 | Smaller page, Refresh == "go to top" | |
| Page size 50, reset to page 1 on filter, Refresh jumps to page 1 | Hybrid — same size but Refresh always goes top | |

**User's choice:** Recommended option (50 / reset-on-filter / Refresh pins page)
**Notes:** Any future filter on Job Queue (e.g. the status filter, or later a filter-framework consumer in Phase 4) resets to page 1. Refresh re-fetches the current slice, does NOT jump to page 1.

---

## Claude's Discretion

- Exact debounce window for socket-driven refetch (250–500 ms trailing range).
- Exact skeleton shape for the heavy sections — reuse `animate-pulse` + `bg-gray-200 rounded` language from `SkeletonGrid` / `CardSkeleton`.
- Whether to co-locate `JobSectionSkeleton` next to `JobDetailModal.tsx` or under `components/ui/page-states/` — planner picks based on reuse potential.
- Hard ceiling for `logs_limit` (pick a safe upper bound, e.g. 10_000).
- Test structure — mirror existing patterns in `test_jobs_api.py` and frontend `__tests__/`.

## Deferred Ideas

- JOB-06 unified Analyze job (Phase 3).
- URL-syncing current page (rides with SEED-010 later).
- Filter-framework migration of the status filter (Phase 4).
- Generic `?fields=` query param (scoped out — only `logs_limit` lands).
- Result payload lazy-load / disclosure toggle.
- Backend log retention policy (logs stay unbounded on disk).
- Pagination audit of other list endpoints.
- "N new jobs — jump to page 1" indicator.
