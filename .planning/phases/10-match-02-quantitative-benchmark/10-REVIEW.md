---
phase: 10-match-02-quantitative-benchmark
status: clean
reviewed: 2026-05-02
findings_count:
  critical: 0
  high: 0
  medium: 0
  low: 2
---

# Phase 10 Code Review

## Files Reviewed
- lightroom_tagger/scripts/benchmark_clip_recall.py

## Findings

### [low] Markdown miss table breaks on delimiter characters in keys
File: lightroom_tagger/scripts/benchmark_clip_recall.py
Line: 218–223
Issue: Cell values (`insta_key`, `validated_catalog_key`) are interpolated into a Markdown table without escaping pipes or trimming whitespace. Rare keys containing `|` (or unintended newlines) will corrupt column alignment or confuse renderers.
Recommendation: Escape `|` as `\|` where the renderer supports it, replace internal pipes with a safe substitute, wrap cells in `<code>...</code>` with HTML escaping for the Markdown file, or document that keys are assumed pipe-free.

### [low] `--out-dir` default is relative to current working directory
File: lightroom_tagger/scripts/benchmark_clip_recall.py
Line: 45–51, 165–167
Issue: Default `out-dir` is `.planning/phases/10-match-02-quantitative-benchmark`; artifacts land relative to cwd, not the repo root or the `--db` file location. Running the module from another directory silently writes elsewhere or fails to find the canonical phase folder.
Recommendation: Optionally resolve defaults against `Path(__file__).resolve()` (repo root heuristic) or print the resolved absolute `out-dir`/`csv_path` at startup so operators can verify the destination.

### [info] Redundant list construction around fetchall()
File: lightroom_tagger/scripts/benchmark_clip_recall.py
Line: 61
Issue: `list(db.execute(_MATCH_TRUTH_SQL).fetchall())` duplicates work because `fetchall()` already returns a list.
Recommendation: Assign `truth_rows = db.execute(_MATCH_TRUTH_SQL).fetchall()` unless a tuple view is deliberately required elsewhere.

### [info] “Read-only CLI” vs `init_database()` side effects
File: lightroom_tagger/scripts/benchmark_clip_recall.py (use of init_database throughout)
Issue: Benchmark logic does not INSERT business rows, but `init_database()` may create parent directories for the DB path, run schema DDL (`CREATE TABLE IF NOT EXISTS`), set WAL/journal pragmas, and interact with SQLite sidecar files—the same connector path as operational tools—not a bitwise read-only SQLite URI open.
Recommendation: Leave as-is for consistency with other scripts unless a dedicated `connect_readonly()` helper becomes a project standard; clarify in `--help`/docs for operators using immutable snapshots if needed.

## Summary

The benchmark script aligns with Phase 10 plan and SUMMARY: truth query, `get_rejected_pairs` once per run, production-order filters (`find_candidates_by_date` → rejected → representative grid → CLIP blob pre-check → `shortlist_catalog_candidates_by_clip(..., top_k=50)`), status taxonomy (`hit` / `miss` / `filtered_out` / `skipped_no_embedding`), CSV header and funnel/recall denominators excluding `filtered_out` and skipped rows, plus miss-table content. Row access matches `init_database()`’s dict row factory—no correctness bug here. Security surface is acceptable for an operator-facing local CLI (static SQL; paths are intentional operator inputs). Ruff passes on the file. No medium or higher defects; remaining items are ergonomics and documentation-level concerns.
