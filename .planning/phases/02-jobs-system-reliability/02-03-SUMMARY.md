# Plan 02-03 — Job failure severity in API and UI badges

**Objective:** Persist `warning` / `error` / `critical` alongside free-text `error`, set from `fail_job` and handler exception classification, surface in API JSON and job UI badges without changing raw error message text.

## Commits (task order)

| Task | Commit | Message |
|------|--------|---------|
| 1 | `d0237fe` | feat(02-03): add jobs.error_severity column and migration |
| 2 | `a8824be` | feat(02-03): persist error_severity in fail_job and clear on complete |
| 3 | `0789af1` | fix(02-03): clear error_severity on job retry |
| 4 | `a84bf19` | feat(02-03): classify job failure severity in handlers |
| 5 | `e5891c5` | feat(02-03): add error_severity to Job type |
| 6 | `22d5f49` | feat(02-03): add ERROR_SEVERITY_LABELS for job badges |
| 7 | `8bb1e1d` | feat(02-03): show error severity badge in job detail modal |
| 8 | `ed2465e` | feat(02-03): show severity badge on failed job cards |

### Planning artifacts

| Commit | Message |
|--------|---------|
| `0ea9d0c` | docs(02-03): add plan execution summary |
| `6e0011a` | chore(02-03): advance STATE and mark plan done in ROADMAP |
| `bb34540` | docs(02-03): note metadata commits in summary |
| `b5c2474` | fix(02-03): read PRAGMA table_info name from dict rows |

## Implementation notes

- **Schema:** `jobs.error_severity TEXT`; idempotent `ALTER` after `PRAGMA table_info(jobs)`; helper `clear_job_failure_details` in `database.py` for future use (retry uses explicit `UPDATE` per plan).
- **Runner:** `fail_job(..., *, severity='error')` validates allowed values; single `UPDATE` sets `error` + `error_severity`; `complete_job` clears `error_severity`.
- **Handlers:** Shared `_failure_severity_from_exception` maps auth/invalid-request → warning, `PermissionError`/`OSError` → critical, Lightroom lock `RuntimeError` → critical; vision_match lock path uses `severity='critical'` explicitly.
- **UI:** `Badge` variants per DESIGN.md: `warning` / `error`; critical uses `error` + `ring-2 ring-error`.

## Deviations

- **Bug (Rule 1):** Initial migration used `row[1]` on `PRAGMA table_info` results; the connection uses `_dict_factory`, so rows are dicts. Fixed to `row[\"name\"]` (follow-up commit after task 1).

## Verification

- `cd apps/visualizer/frontend && npm run lint` — exit 0.
- Backend: `init_db` smoke test on fresh DB and pre-existing `jobs` table without `error_severity` — column present after init.
