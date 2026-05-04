---
phase: 07-stacks-in-matching-pin-similarity
plan: 1
subsystem: instagram-matching / stacks
requirements-completed:
  - STACK-04
duration: "~25 min"
completed: "2026-04-26T00:00:00Z"
---

# Phase 7 Plan 1: STACK-04 backend — representative matching & stack apply

**One-liner:** Instagram vision matching now scores only stack representatives (or solo catalog rows), then applies a confirmed representative match across stack members with non-destructive conflict skips, explicit counters, and Lightroom writes for all applied keys.

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | `f89be21` | feat(07-01): representative-only Instagram match candidates |
| 2 | `ec93ffa` | feat(07-01): stack-wide Instagram match apply with conflict skips |
| 3 | `6ca14ed` | test(07-01): stack apply success path and handler result counters |

## Key files

| File | Role |
|------|------|
| `lightroom_tagger/scripts/match_instagram_dump.py` | Representative-only candidate filter; stack member `store_match` + stats; `_lightroom_catalog_keys` on best match |
| `lightroom_tagger/core/database.py` | `list_catalog_stack_member_keys`, `catalog_has_instagram_match_conflict`, `apply_instagram_match_to_stack_members` |
| `apps/visualizer/backend/jobs/handlers.py` | `_expand_matches_for_lightroom_writes`; job logs; `stack_apply_*` in `complete_job` payload |
| `apps/visualizer/backend/tests/test_handlers_single_match.py` | Representative-only, conflict partial-apply, full apply, handler payload tests |

## Deviations from Plan

- **Implementation path:** Plan frontmatter listed `lightroom_tagger/core/match_instagram_dump.py`; the live module is `lightroom_tagger/scripts/match_instagram_dump.py` (existing import path from handlers). Behavior matches the plan; only the path differs from the YAML hint.

## Verification

Commands from `07-01-PLAN.md` (run 2026-04-26):

```text
pytest apps/visualizer/backend/tests/test_handlers_single_match.py -k representative -q --tb=short  → 1 passed
pytest apps/visualizer/backend/tests/test_handlers_single_match.py -k conflict -q --tb=short       → 2 passed
pytest apps/visualizer/backend/tests/test_handlers_single_match.py -q --tb=short                   → 7 passed
```

## Self-Check: PASSED

- Representative-only filtering covered with mixed rep/member fixtures; scoring receives representative keys only.
- Stack apply returns `applied_count` / `skipped_conflicts_count` / `skipped_other_count`; job result exposes `stack_apply_applied`, `stack_apply_skipped_conflicts`, `stack_apply_skipped_other`.
- Conflicting members keep prior `matches` rows; no row for `(member, new_insta)` when another `insta_key` is already stored.
- Handler logs cumulative non-representative filter count and stack apply summary lines.
