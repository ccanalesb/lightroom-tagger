---
phase: "19"
status: clean
review_depth: standard
created: 2026-05-12
---

# Phase 19 Code Review

## Findings

### Medium — Resolved

**File:** `lightroom_tagger/scripts/match_instagram_dump.py`

After a snapshot was inserted, a cancellation could return before `mark_dump_media_attempted`, leaving `last_attempted_at` null. Because report targets require `last_attempted_at IS NOT NULL`, the snapshot could be invisible to the offline report.

**Fix:** The cancel-after-score path now marks the dump media attempted with the best available result before returning.

**Verification:** `test_match_dump_media_cancel_after_snapshot_marks_attempted` asserts both snapshot persistence and `last_attempted_at` update.

## Low Notes

- Snapshot inserts intentionally commit outside match writeback so diagnostic evidence survives later match write failures.
- Bootstrap and migration DDL are duplicated by existing project convention for greenfield and legacy DB support.
- Report target selection follows "unmatched attempted" scope and does not add extra video filtering beyond the existing attempted row state.
- Hidden debug evidence may include local paths by design; share generated reports accordingly.

## Test Gaps Reviewed

- Added cancel-after-snapshot regression coverage.
- Existing tests cover report HTML/assets, primary path privacy, reconstructed banner, and snapshot persistence.

## Result

No unresolved medium or high findings.
