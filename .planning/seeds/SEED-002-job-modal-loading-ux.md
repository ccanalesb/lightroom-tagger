---
id: SEED-002
status: dormant
planted: 2026-04-15
planted_during: v2.0 (milestone complete)
trigger_when: next UX improvements milestone or job detail modal redesign
scope: Medium
---

# SEED-002: Improve job detail modal loading UX for large jobs

## Why This Matters

Some jobs accumulate hundreds of log entries and large result payloads (e.g. batch describe/score with many images). When a user clicks to open the `JobDetailModal`, it fires `JobsAPI.get(job.id)` and renders stale data until the full response arrives — with no loading indicator. For heavy jobs like `381715a6-a8fb-458c-882f-01d602d717f7`, this means the modal appears frozen or incomplete for several seconds. The experience feels broken even though the data is just slow to arrive.

Beyond the missing loading state, the modal dumps every log line into a single scrollable div, which balloons the DOM and slows rendering for long-running jobs that generate hundreds of entries.

## When to Surface

**Trigger:** Next UX improvements milestone or job detail modal redesign

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- UX polish or loading state improvements across the visualizer
- Job detail modal or job queue UI redesign
- Performance improvements for data-heavy views

## Scope Estimate

**Medium** — A phase or two. The work involves:
1. Adding a loading/skeleton state to `JobDetailModal` while the API call resolves
2. Paginating or truncating the logs section (show last N entries, "Load more" or expand)
3. Potentially lazy-loading the full `result` JSON behind a disclosure toggle instead of rendering it immediately
4. Optionally adding a backend `?fields=` or `?logs_limit=` query param to `GET /api/jobs/<id>` so the initial fetch is lighter

## Breadcrumbs

Related code and decisions found in the current codebase:

- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` — the modal component; fetches full job on mount (line 82), renders all logs in a single div (line 335)
- `apps/visualizer/frontend/src/services/api.ts` — `JobsAPI.get()` returns the full job object with no field filtering (line 110)
- `apps/visualizer/backend/api/jobs.py` — `get_job_details` endpoint returns the entire job row including all logs and result (line 28)
- `apps/visualizer/backend/database.py` — `get_job()` deserializes the full row with no truncation (line 91)
- `apps/visualizer/backend/jobs/runner.py` — `add_job_log` appends to the logs array unbounded (line 33)
- `apps/visualizer/frontend/src/components/ui/Thumbnail.tsx` — existing skeleton/loading pattern in the project

## Notes

The simplest win is a loading skeleton in the modal — the data flow already works, it just lacks visual feedback. The bigger improvement is not sending or rendering all logs by default: cap the initial response at the last ~20 log entries and add a "Show all logs" expansion. This keeps the modal snappy for the 90% case while preserving full detail for debugging.
