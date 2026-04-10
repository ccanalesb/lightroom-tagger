# Plan 02-04 — Job status UX alignment, orphan recovery copy, and handler cancel checks

**Objective:** Align user-facing job status vocabulary (`pending` → “Queued”), match job detail status labels to list badges via `STATUS_LABELS`, clarify orphan recovery after server restart, and add cooperative cancellation checks in long-running handlers (`enrich_catalog`, `batch_describe`, `prepare_catalog`).

## Commits (task order)

| Task | Commit | Message |
|------|--------|---------|
| 1 | `fe23880` | fix(02-04): show pending job status as Queued in STATUS_LABELS |
| 2 | `8f024a9` | fix(02-04): align job detail status badge with STATUS_LABELS |
| 3 | `da05cc3` | fix(02-04): clarify orphan job recovery message on server restart |
| 4 | `90e175c` | fix(02-04): honor cooperative cancel between enrich catalog iterations |
| 5 | `fa21851` | fix(02-04): cooperative cancel for sequential batch describe |
| 6 | `f74e330` | fix(02-04): cooperative cancel for parallel batch describe |
| 7 | `eb8fcbe` | fix(02-04): cooperative cancel for prepare catalog cache executor loop |

### Planning artifacts

| Commit | Message |
|--------|---------|
| `52b938a` | docs(02-04): add plan execution summary |
| `97b4924` | chore(02-04): sync ROADMAP, STATE, and summary after plan completion |

## Implementation notes

- **Frontend:** `STATUS_LABELS.pending` is `Queued`; `JobDetailModal` renders `STATUS_LABELS[displayJob.status] ?? displayJob.status` so detail matches `StatusBadge` (API values unchanged).
- **Orphan recovery:** `_recover_orphaned_jobs` logs a single error-level line explaining the job was running at restart, was marked failed, and that Retry re-runs it.
- **Handlers:** `handle_enrich_catalog` checks `runner.is_cancelled` at the top of each catalog image iteration, then `finalize_cancelled` + return; `finally` still closes the library DB. `handle_batch_describe` sequential path logs `Batch describe stopped: cancel requested` before finalize; parallel path breaks out of `as_completed` with `Batch describe cancel noted; finishing already-running tasks`, then finalizes after the executor context exits. `handle_prepare_catalog` uses the same break pattern with `Prepare catalog cache stopped: cancel requested`, then `finalize_cancelled` before final stats / `complete_job`. `add_job_log` is imported at module scope in `handlers.py` for shared use.

## Deviations

- **`roadmap update-plan-progress`:** The CLI returned `updated: true` but the Phase 2 plan table row for 02-04 remained `Pending` in `.planning/ROADMAP.md`. The row was set to **Done** (2026-04-10) manually to match the completed work (same commit as STATE touch-up).

## Verification

- `cd apps/visualizer/frontend && npm run lint` — exit 0.
- Grep checks from the plan: new orphan message present, old string absent; cancel log strings and `is_cancelled` placements as specified.
