# Plan 02-02 — Summary

**Title:** Catalog backup rotation and Lightroom lock guard before writes  
**Phase:** 02 — Jobs & system reliability  
**Requirements:** SYS-03, SYS-05

## Outcome

- **Lock guard:** `_catalog_lock_candidates` checks `{stem}.lrcat-lock` and `{name}.lock` under the catalog parent; `raise_if_catalog_locked` raises `RuntimeError("Close Lightroom before writing to catalog.")` if any candidate exists as a file or directory.
- **Backup:** `backup_catalog_if_needed` copies the catalog with `shutil.copy2` to `{catalog_name}.backup-{YYYY-MM-DDTHH-MM-SS}` in the catalog directory, deletes oldest matches until fewer than `max_backups` exist, then adds the new file (default `max_backups=2`). Logs with prefix `Catalog backup created:`.
- **Write path:** `update_lightroom_from_matches` calls lock check then backup before `connect_catalog`.
- **Jobs:** `handle_vision_match` catches that exact lock `RuntimeError`, logs at error level, calls `runner.fail_job`, and returns; other `RuntimeError` values are re-raised for the outer handler.

## Commits (atomic per task)

| Task | Commit | Message |
|------|--------|---------|
| 1 | `b5f6f82` | feat(02-02): add catalog lock detection before Lightroom writes |
| 2 | `ac0cb41` | feat(02-02): add rotated timestamped catalog backup helper |
| 3 | `7f1465b` | feat(02-02): run lock check and backup before catalog SQLite writes |
| 4 | `aee3f70` | feat(02-02): fail vision_match job when catalog is locked |
| — | `d06fe3d` | docs(02-02): add plan execution summary |
| — | `465a754` | chore(02-02): advance STATE and ROADMAP after plan completion |
| — | `f5b336a` | docs(02-02): extend summary with planning sync and commit refs |

## Verification

- `raise_if_catalog_locked` with a temp `.lrcat` and `t.lrcat-lock` file raises `RuntimeError` with the exact agreed message.
- Backup rotation: with 1s between calls (distinct timestamps), glob `*.backup-*` count stays at most 2 across four backup calls.

## Note

Backup filenames use second-resolution timestamps per plan; multiple backups in the same second target the same path and overwrite (rare in real job runs).

## Planning sync

- `STATE.md`: added **GSD progression** fields so `gsd-tools state advance-plan` can run (project STATE previously lacked **Current Plan** / **Total Plans in Phase**). After completion: **Current Plan:** 3 (next: 02-03), progress `completed_plans: 7`, `percent: 78`.
- `ROADMAP.md`: Phase 2 execution table marks **02-02** **Done** (2026-04-10); `roadmap update-plan-progress 02` re-run after `02-02-SUMMARY.md` existed (2/4 summaries).
