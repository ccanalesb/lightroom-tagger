---
phase: 12-operational-baseline-embed-reliability
plan: 12-02
subsystem: ui
tags: [react, vitest, embed-diagnostics, ops]

requires:
  - phase: 12-operational-baseline-embed-reliability
    provides: Backend/embed payload contracts from prior phase work (12-01 dependency).
provides:
  - OPS-01 frontend sweep compliance via centralized `no_clip_embedding` fallback constant co-located with search pin copy.
  - OPS-03 JobDetailModal embed skip breakdown using three user-facing buckets only; zero buckets and encode-only failures hide the diagnostics card.
affects:
  - Phase 12 embed reliability UX and job-detail diagnostics expectations.

tech-stack:
  added: []
  patterns:
    - "Embed skip labels live in `strings.ts` as `JOB_SKIP_*`; modal filters to count > 0 and omits card when no visible bucket."

key-files:
  created: []
  modified:
    - apps/visualizer/frontend/src/constants/strings.ts
    - apps/visualizer/frontend/src/pages/SearchPage.tsx
    - apps/visualizer/frontend/src/pages/__tests__/SearchPage.test.tsx
    - apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx
    - apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx

key-decisions:
  - "OPS-01: `rg \"no_clip_embedding\"` now resolves to `strings.ts` only; SearchPage and tests use `SEARCH_PIN_FALLBACK_REASON_NO_CLIP_EMBEDDING` so the literal stays beside `SEARCH_PIN_HELP_EMBED` (acceptance: co-file with D-02 copy)."
  - "OPS-03: Removed `encode_failed` from UI mapping; diagnostics render only when at least one D-07 bucket count is positive."

patterns-established:
  - "Batch embed job modal reads `skip_reason_counts` keys `no_row`, `empty_path`, `unresolved_or_missing` with labels Missing file / Empty path / No DB row."

requirements-completed: [OPS-01, OPS-03]

duration: ~12 min
completed: 2026-05-05
---

# Phase 12 Plan 12-02: Frontend embed sweep & JobDetailModal skip breakdown Summary

**Embed discoverability strings centralized for OPS-01 rg acceptance; job detail modal shows only positive D-07 skip buckets and hides the entire diagnostics card when `encode_failed` is the sole positive count or all tracked buckets are zero.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-05T12:50:00Z (approx.)
- **Completed:** 2026-05-05T13:02:00Z (approx.)
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Introduced `SEARCH_PIN_FALLBACK_REASON_NO_CLIP_EMBEDDING` and wired SearchPage + tests so frontend source scans for `no_clip_embedding` hit only `strings.ts` (which already exports `SEARCH_PIN_HELP_EMBED`).
- Replaced legacy `JOB_DETAILS_EMBED_REASON_*` strings with `JOB_SKIP_MISSING_FILE`, `JOB_SKIP_EMPTY_PATH`, `JOB_SKIP_NO_DB_ROW`; modal maps three payload keys, filters `count <= 0`, returns null when nothing to show.
- Extended Vitest with encode-only and zero-bucket omission coverage.

## Task Commits

Each task was committed atomically:

1. **Task 12-02-01: OPS-01 frontend sweep** — `d519f5a` (`feat(12-02): OPS-01 centralize no_clip_embedding fallback constant`)
2. **Task 12-02-02: OPS-03 strings + modal + tests** — `9f04d81` (`feat(12-02): OPS-03 JobDetailModal skip breakdown with 3-bucket filter`)


## Files Created/Modified

- `apps/visualizer/frontend/src/constants/strings.ts` — `SEARCH_PIN_FALLBACK_REASON_NO_CLIP_EMBEDDING`; `JOB_SKIP_*` constants; removed `JOB_DETAILS_EMBED_REASON_*`.
- `apps/visualizer/frontend/src/pages/SearchPage.tsx` — compares inactive-pin fallback using shared constant.
- `apps/visualizer/frontend/src/pages/__tests__/SearchPage.test.tsx` — mock metadata uses shared constant.
- `apps/visualizer/frontend/src/components/jobs/JobDetailModal.tsx` — three-bucket `EMBED_REASON_LABELS`, visible-rows filter, null when empty.
- `apps/visualizer/frontend/src/components/jobs/__tests__/JobDetailModal.test.tsx` — updated expectations; two new diagnostics visibility tests.

## Decisions Made

- Followed plan OPS-03 wording exactly for `JOB_SKIP_*` display strings (double-quoted in source per verification grep).
- Did not surface `encode_failed` in the modal per D-09-style UX (zeros hidden; encode bucket excluded from mapping).

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — `npx vitest run` completed with exit code 0.

## User Setup Required

None — no external service configuration required.

## Verification

- `cd apps/visualizer/frontend && npx vitest run` — **PASS** (284 tests).

## Self-Check: PASSED

---

*Phase: 12-operational-baseline-embed-reliability*
*Completed: 2026-05-05*
