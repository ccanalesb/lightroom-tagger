---
phase: 07-stacks-in-matching-pin-similarity
plan: 2
subsystem: api / database
requirements-completed:
  - STACK-05
duration: "~20 min"
completed: "2026-04-26T20:00:00Z"
---

# Phase 7 Plan 2: STACK-05 — stack split, merge, change representative (backend)

**One-liner:** Library DB now exposes transactional `stack_split_member_out`, `stack_merge_into`, and `stack_set_representative` helpers plus three JSON POST endpoints under `/api/images/stacks/…`, with rollback-safe `library_write` usage and tests for happy paths, 4xx errors, and aborted transactions.

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | `bbcef61` | feat(07-02): transactional stack split/merge/representative DB helpers |
| 2 | `c1eb50b` | feat(07-02): stack mutation REST endpoints |
| 3 | `3448b3a` | test(07-02): stack mutation API and invariant tests |

## Key files

| File | Role |
|------|------|
| `lightroom_tagger/core/database.py` | `StackMutationError`; `select_stack_representative_key_for_keys`; `stack_metadata_for_api`; `stack_split_member_out` (dissolve when ≤1 member left); `stack_merge_into`; `stack_set_representative` |
| `apps/visualizer/backend/api/images.py` | `POST .../stacks/<id>/split-member`, `POST .../stacks/<id>/merge`, `POST .../stacks/<id>/representative` |
| `apps/visualizer/backend/tests/test_images_stacks_api.py` | API + DB rollback tests; failure cases per endpoint |

## API contracts (success)

- **split-member** → `{ split_out_key, remaining_stack | null, dissolved }` where `remaining_stack` matches `stack_metadata_for_api` shape (`stack_id`, `representative_key`, `stack_member_count`, `member_keys`).
- **merge** → `{ stack, merged_stack_id }`.
- **representative** → `{ stack }`.

Invalid JSON / missing fields → 400. Unknown stack → 404. Member mismatch → 400 with explicit message.

## Deviations from Plan

None — plan executed as written.

## Verification

Commands from `07-02-PLAN.md` (run 2026-04-26, project venv `.venv/bin/python`):

```text
pytest apps/visualizer/backend/tests/test_images_stacks_api.py -k split -q --tb=short
  → 5 passed, 8 deselected

pytest apps/visualizer/backend/tests/test_images_stacks_api.py -k representative -q --tb=short
  → 4 passed, 9 deselected

pytest apps/visualizer/backend/tests/test_images_stacks_api.py -q --tb=short
  → 13 passed
```

## Self-Check: PASSED

- Mutations run inside `library_write`; explicit rollback tests show no partial writes on abort.
- `stack_member_count` / `stack_size` resynced after representative change; merge/split update counts and representative when the old rep leaves the stack.
- At least one failure test per mutation endpoint (split: not member + unknown stack; merge: self-merge + missing source; representative: non-member + unknown stack).
