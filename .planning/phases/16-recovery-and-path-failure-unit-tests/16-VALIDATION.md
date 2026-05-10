---
phase: 16
slug: recovery-and-path-failure-unit-tests
status: complete
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-09
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `apps/visualizer/backend/pytest.ini` (none found — standard discovery) |
| **Quick run command** | `cd apps/visualizer/backend && python -m pytest tests/test_handlers_batch_describe.py tests/test_handlers_batch_score.py tests/test_orphan_recovery.py -q` |
| **Full suite command** | `cd apps/visualizer/backend && python -m pytest tests/ -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-T1 | 01 | 1 | TEST-01 | unit | `python -m pytest tests/test_handlers_batch_describe.py::test_batch_describe_checkpoint_skips_already_processed_pairs -q` | ✅ | ✅ green |
| 16-01-T2 | 01 | 1 | TEST-01 | unit | `python -m pytest tests/test_handlers_batch_describe.py::test_batch_describe_fingerprint_mismatch_resets_and_reprocesses -q` | ✅ | ✅ green |
| 16-01-T3 | 01 | 1 | TEST-01 | unit | `python -m pytest tests/test_handlers_batch_describe.py::test_batch_describe_stale_checkpoint_no_work_completes -q` | ✅ | ✅ green |
| 16-02-T1 | 02 | 1 | TEST-01 | unit | `python -m pytest tests/test_handlers_batch_score.py::test_batch_score_fingerprint_mismatch_resets_and_reprocesses -q` | ✅ | ✅ green |
| 16-02-T2 | 02 | 1 | TEST-01 | unit | `python -m pytest tests/test_handlers_batch_score.py::test_batch_score_stale_checkpoint_all_processed_completes -q` | ✅ | ✅ green |
| 16-02-T3 | 02 | 1 | TEST-01 | unit | `python -m pytest tests/test_orphan_recovery.py::test_recover_running_batch_score_with_checkpoint_requeues_pending -q` | ✅ | ✅ green |
| 16-03-T1 | 03 | 2 | TEST-02 | traceability | `rg -n "def test_batch_embed_image_preflight_fails_fast_when_paths_inaccessible" tests/test_handlers_batch_embed_image.py` | ✅ | ✅ green |
| 16-03-T2 | 03 | 2 | TEST-01, TEST-02 | suite | `python -m pytest tests/ -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

**TEST-02 traceability note:** Path-failure / preflight / skip-reason coverage is satisfied by existing Phase 12 tests in `test_handlers_batch_embed_image.py` per decisions D-05/D-06 in `16-CONTEXT.md`. The five relevant functions confirmed present:

| Test | File | Line |
|------|------|------|
| `test_batch_embed_image_preflight_fails_fast_when_paths_inaccessible` | test_handlers_batch_embed_image.py | 590 |
| `test_batch_embed_image_reports_grouped_skip_reason_counts` | test_handlers_batch_embed_image.py | 675 |
| `test_batch_embed_image_preflight_aborts_when_majority_unreachable` | test_handlers_batch_embed_image.py | 826 |
| `test_batch_embed_image_uses_vision_cache_when_original_missing` | test_handlers_batch_embed_image.py | 776 |
| `test_batch_embed_image_preflight_does_not_abort_in_chain_mode` | test_handlers_batch_embed_image.py | 1005 |

`batch_describe` / `batch_score` do not implement embed preflight — zero new embed tests required for Phase 16.

---

## Validation Sign-Off

- [x] All tasks have automated verify
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 not required — existing infrastructure covers all requirements
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Baseline:** 347 tests collected and passing in `apps/visualizer/backend/tests/` (note: D-09 references 663 from a broader monorepo scope — 347 is the correct local backend count).

**Approval:** approved 2026-05-09

---

## Validation Audit 2026-05-09

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

All 8 tasks (6 new test functions + 2 verification tasks) are COVERED. Suite: 347 passed, exit 0.
