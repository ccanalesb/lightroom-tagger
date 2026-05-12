---
phase: 19
slug: generate-read-only-html-comparison-pool-report
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-12
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest lightroom_tagger/scripts/test_match_instagram_dump.py -q` |
| **Full suite command** | `pytest lightroom_tagger/scripts/test_match_instagram_dump.py apps/visualizer/backend/tests/test_handlers_single_match.py -q -k "match_dump or comparison_pool"` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest lightroom_tagger/scripts/test_match_instagram_dump.py -q`
- **After every plan wave:** Run `pytest lightroom_tagger/scripts/test_match_instagram_dump.py apps/visualizer/backend/tests/test_handlers_single_match.py -q -k "match_dump or comparison_pool"`
- **Before `/gsd-verify-work`:** Full scoped suite plus generated report smoke check must pass
- **Max feedback latency:** 60 seconds for scoped automated feedback

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | D-01, D-03 | T-19-01 | Snapshot persistence never mutates matches or rejections | unit | `pytest lightroom_tagger/scripts/test_match_instagram_dump.py -q -k "snapshot or comparison_pool"` | No | pending |
| 19-02-01 | 02 | 1 | D-06, D-07, D-09, D-10 | T-19-02 | Report queries only unmatched attempted media and honors filters | unit | `pytest -q -k "comparison_pool_report"` | No | pending |
| 19-03-01 | 03 | 2 | D-05, D-08, D-11, D-12, D-13 | T-19-03 | Primary HTML uses relative compressed assets; local paths appear only in hidden debug | unit + smoke | `pytest -q -k "comparison_pool_report"` | No | pending |
| 19-04-01 | 04 | 2 | D-02 | T-19-04 | Reconstructed pools are visibly labeled as non-exact | unit + manual | `pytest -q -k "comparison_pool_report"` | No | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] Add pytest fixtures for a temp library DB with unmatched attempted Instagram media, scored candidate snapshots, missing snapshots, and missing image files.
- [ ] Add CLI smoke fixture that writes `report.html` plus `assets/` under a temp output directory.
- [ ] Existing pytest infrastructure covers the phase; no framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Offline visual inspection | D-05, D-06, D-08 | Automated tests can verify files and strings, but not the human diagnostic usefulness of the grid | Open generated `report.html` from `file://`, confirm Instagram image and candidate thumbnails load, candidate evidence is visible, and debug details expand for one row |
| Path privacy review | D-13 | HTML primary/debug separation is easiest to spot with generated output | Search visible report body for absolute paths; confirm any full original paths appear only inside collapsed debug details |

---

## Validation Sign-Off

- [ ] All tasks have automated verification or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all missing fixture references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
