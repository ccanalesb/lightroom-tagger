---
phase: 01-matching-review-polish
plan: 01
subsystem: api
tags: [flask, sqlite, pytest, match-groups, pagination]

requires: []
provides:
  - Ordered GET /api/images/match_groups with actionable bucket first, reviewed bucket second, and synthetic tombstone rows for rejected-only Instagram keys
affects: [matching-review-polish, matches-tab, match-detail-modal]

tech-stack:
  added: []
  patterns:
    - Post-group Python sort before pagination slice for match_groups

key-files:
  created: []
  modified:
    - apps/visualizer/backend/api/images.py
    - apps/visualizer/backend/tests/test_match_groups.py

key-decisions:
  - Applied two-bucket ordering with sort_bucket=1 when has_validated or all_rejected (D-09/D-10), newest-first via negated parsed timestamps with NULLS LAST (D-11)
  - Tombstone keys loaded into dump_instagram_by_key on demand when absent from match-driven fetch

patterns-established:
  - list_matches enriches tombstone-only insta_keys from instagram_dump_media before serialization

requirements-completed: [POLISH-02]

duration: 20min
completed: 2026-04-17T18:45:00Z
---

# Phase 01: Matching & review polish — Plan 01 summary

**Server-side two-bucket match sort with tombstone groups for rejected Instagram keys**

## Performance

- **Duration:** 20 min (estimate)
- **Started:** 2026-04-17T18:25:00Z
- **Completed:** 2026-04-17T18:45:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `list_match` groups are sorted before `_clamp_pagination`: unvalidated groups first, then reviewed (validated or all-rejected tombstones), newest-first by Instagram `created_at` with catalog `date_taken` fallback and NULLS LAST
- Synthetic groups for `rejected_matches` keys with no `matches` rows include `all_rejected: true` and empty `candidates`
- Regression tests cover bucket ordering and tombstone placement after a validated group

## Task commits

Each task was committed atomically:

1. **Task 1.1: Backend sort, tombstones, and `all_rejected` on groups** — `7d4bff4` (feat)
2. **Task 1.2: Pytest coverage for sort and tombstone serialization** — `5167ae9` (test)

3. **Plan documentation (`01-SUMMARY.md`)** — `621ee5e` (docs: complete plan)

## Files created/modified

- `apps/visualizer/backend/api/images.py` — `list_matches` post-processing, tombstone query, sort key, pagination on sorted list
- `apps/visualizer/backend/tests/test_match_groups.py` — sort and tombstone API tests

## Decisions made

None beyond the written plan: mechanical implementation of D-08, D-09, D-11, and synthetic tombstones per POLISH-02.

## Deviations from plan

None — plan executed exactly as written.

## Issues encountered

System `python` was not on PATH; verification used `uv run python` / `uv run pytest` from the repo `.venv` (equivalent to project dev workflow).

## User setup required

None.

## Next phase readiness

Backend contract for ordered groups and `all_rejected` is in place for Matches tab and `useMatchGroups` consumers in later plans.

## Self-Check: PASSED

Re-ran after all tasks:

- `rg -n "all_rejected" apps/visualizer/backend/api/images.py` — PASS (matches inside `list_matches`)
- `rg -n "sort_bucket|photo_ts" apps/visualizer/backend/api/images.py` — PASS
- `uv run pytest apps/visualizer/backend/tests/test_match_groups.py -k "sorts_unvalidated or tombstone"` — PASS (2 tests)
- `cd apps/visualizer/backend && PYTHONPATH=. uv run python -m pytest tests/test_match_groups.py -v` — PASS (5 tests)
- `cd apps/visualizer/backend && PYTHONPATH=. uv run python -m pytest tests/test_match_groups.py -k sort` — PASS (1 test)

---
*Phase: 01-matching-review-polish*
*Completed: 2026-04-17*
