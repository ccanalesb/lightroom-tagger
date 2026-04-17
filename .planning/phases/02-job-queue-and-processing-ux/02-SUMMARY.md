---
plan: 02
title: Frontend API client and types for paginated jobs and logs_limit
status: completed
wave: 2
commits:
  - 5b917ac
---

# Summary

Updated the frontend API seam to consume the new paginated jobs envelope from Plan 01 and pass an optional `logs_limit` into `JobsAPI.get`. No component behavior was changed in this plan — that's handed off to Plans 03 and 04.

## Changes

- `apps/visualizer/frontend/src/types/job.ts` — added optional `logs_total?: number` field on `Job`.
- `apps/visualizer/frontend/src/services/api.ts`:
  - new exported interfaces `JobsListResponse` and `JobsGetOptions`.
  - `JobsAPI.list` now takes `{ status?, limit?, offset? }` and returns `JobsListResponse`.
  - `JobsAPI.get` takes optional `{ logs_limit }` and forwards it as a query string (including `logs_limit=0`).
- `apps/visualizer/frontend/src/pages/DashboardPage.tsx` — unwraps `r4.value.data` instead of treating the response as `Job[]`.
- `apps/visualizer/frontend/src/pages/DashboardPage.test.tsx` — mock now returns the paginated envelope shape.
- `apps/visualizer/frontend/src/constants/strings.ts` — six new exports (`JOB_DETAILS_LOGS_TRUNCATED_HEADER`, `JOB_DETAILS_LOGS_SHOW_ALL`, `JOB_DETAILS_LOGS_SHOW_ALL_LOADING`, `JOB_DETAILS_LOADING_ARIA`, `JOB_DETAILS_FETCH_ERROR`, `JOB_QUEUE_PAGINATION_RANGE`) for Plans 03 and 04 to consume.
- `apps/visualizer/frontend/src/services/__tests__/api.test.ts` — rewritten around the envelope shape plus new coverage for list query params and `logs_limit` passthrough (including the `logs_limit=0` expand path).

## Verification

- `npx tsc --noEmit` — 0 new errors. Two pre-existing `MatchDetailModal.tsx` Timeout errors remain (out of scope).
- `npx vitest run src/services/__tests__/api.test.ts src/pages/DashboardPage.test.tsx` — 9 tests pass.
- `npx eslint src/services/api.ts src/types/job.ts src/constants/strings.ts` — clean.
- `rg -n "JobsAPI\\.list\\('" apps/visualizer/frontend/src/` — no positional-string callers.

## Follow-ups

- `ProcessingPage.tsx:60,73` still call `JobsAPI.list()` and feed the result into `Array.isArray(data) ? data : []`. It compiles today because the no-args call is valid and the `Array.isArray` guard falls through to `[]` at runtime. Plan 04 replaces that with the paginated envelope path.
- Pre-existing `MatchDetailModal.tsx` `number`-vs-`Timeout` type errors are unrelated to this phase.
