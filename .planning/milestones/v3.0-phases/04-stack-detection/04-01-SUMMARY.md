---
phase: 04-stack-detection
plan: "04-01"
subsystem: database
tags: [sqlite, migration, image_stacks, STACK-01]

requires:
  - phase: prior library DB / init_database patterns
    provides: WAL init, vec0 migration hook point, existing `images` table
provides:
  - Idempotent `image_stacks` and `image_stack_members` tables on every `init_database` open
  - UNIQUE constraints on `representative_key` and `image_stack_members.image_key`
  - `ON DELETE CASCADE` from stacks to members with foreign keys enabled at connection init
affects:
  - 04-stack-detection (downstream stack job and writes must use `library_write`)

tech-stack:
  added: []
  patterns:
    - "Idempotent DDL via CREATE TABLE/INDEX IF NOT EXISTS (no user_version for this migration)"

key-files:
  created: []
  modified:
    - lightroom_tagger/core/database.py

key-decisions:
  - "Followed RESEARCH §8 DDL and index names verbatim; no user_version gate per plan"

patterns-established:
  - "_migrate_image_stacks runs after _migrate_image_text_embeddings_vec0 and before seed_perspectives_from_prompts_dir"

requirements-completed: ["STACK-01"]

duration: 8min
completed: 2026-04-24
---

# Phase 4 Plan 04-01: Library DB schema — image_stacks and image_stack_members Summary

**SQLite library DB now creates `image_stacks` and `image_stack_members` idempotently on `init_database`, with denormalized `stack_size`, `user_modified` scaffold, UNIQUE on `image_key`, and CASCADE deletes — wired after the vec0 migration.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-24T13:55:32Z
- **Completed:** 2026-04-24T14:03:32Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `_migrate_image_stacks` with `CREATE TABLE IF NOT EXISTS` / `CREATE UNIQUE INDEX IF NOT EXISTS` only (no `user_version` branch).
- Invoked from `init_database` immediately after `_migrate_image_text_embeddings_vec0` and before `seed_perspectives_from_prompts_dir`, with ordering noted in a comment (`images` already exists from core DDL).
- Relied on existing `PRAGMA foreign_keys=ON` in `init_database` so `ON DELETE CASCADE` on `image_stack_members.stack_id` is effective.

## Task Commits

Each task was committed atomically:

1. **Task T1: Add _migrate_image_stacks and call from init_database** - `e79926a` (feat)

**Plan metadata:** `docs(04-01): add plan completion summary for library stack schema` (second commit; follows `e79926a`).

_Single-task plan: one feature commit (`e79926a`) and one documentation commit for this summary._

## Files Created/Modified

- `lightroom_tagger/core/database.py` — `_migrate_image_stacks` DDL and `init_database` call

## Decisions Made

- None beyond the plan — DDL matches RESEARCH §8; foreign key pragma was already set globally on the connection, so no duplicate `PRAGMA` was added.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Schema is in place for subsequent `batch_stack_detect` and stack write paths; ensure stack mutations use `library_write` as documented in code.

---
*Phase: 04-stack-detection*
*Completed: 2026-04-24*
