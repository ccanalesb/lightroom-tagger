---
plan: 03
title: JobDetailModal loading skeleton and log truncation UI
status: completed
wave: 2
commits:
  - 5d5ad8e
---

# Summary

Implemented the user-facing behaviors for `JobDetailModal`: a targeted loading skeleton that keeps identity/progress visible, an inline fetch-error banner, and a truncated logs affordance with expand-on-demand.

## Changes

- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx`:
  - Added inline `SkeletonLine` / `SkeletonSection` helpers (reuses existing `animate-pulse` / `bg-surface` vocabulary).
  - Added `loading`, `fetchError`, `logsExpanded`, `expandingLogs` state.
  - Prop-sync effect (`[job.id]`) resets local state when the parent swaps the selected job; separate initial-fetch effect calls `JobsAPI.get(job.id, { logs_limit: 20 })` and flips `loading` on success or failure.
  - Inline `role="alert"` banner renders `JOB_DETAILS_FETCH_ERROR` above heavy sections when the initial fetch fails; the identity row and progress bar always render from the list-row `job` regardless of `loading`.
  - Heavy sections (`current_step`, `metadata`, `Configuration`, `result`, `logs`) gate on `loading` — only they show skeletons.
  - Logs block: renders truncated header `Logs (shown of total)` and a `Show all N logs` button when `logs_total > logs.length`. Button triggers `JobsAPI.get(id, { logs_limit: 0 })` and swaps in the full list; button label flips to `JOB_DETAILS_LOGS_SHOW_ALL_LOADING` during the expand fetch.
  - All new copy pulled from `constants/strings.ts` — no inline English for the new UI.
- `apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx` (new, 7 tests):
  - Identity row visible while loading.
  - Skeleton appears, then disappears after fetch resolves.
  - Fetch-error banner renders with identity row intact on rejection.
  - Initial fetch uses `logs_limit: 20`.
  - Truncated header + Show all button when `logs_total > logs.length`.
  - Clicking Show all refetches with `logs_limit: 0` and hides the button.
  - No button when `logs_total === logs.length`.

## Verification

- `npx tsc --noEmit` — clean (the two pre-existing `MatchDetailModal` Timeout errors remain, unrelated).
- `npx vitest run src/components/jobs/__tests__/JobDetailModal.test.tsx` — 7/7 pass.
- `npx eslint src/components/jobs/JobDetailModal.tsx src/components/jobs/__tests__/JobDetailModal.test.tsx` — clean.

## Notes

- The prop-sync effect intentionally depends only on `[job.id]` (per plan). Added `eslint-disable-next-line react-hooks/exhaustive-deps` on that one line to silence the hint without relaxing the rule globally.
- Socket-driven `job_updated` events continue to update `localJob` but do **not** re-toggle `loading`, preserving D-05/D-08.
