---
phase: 13
slug: handlers-split-per-job-family
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `apps/visualizer/backend/pytest.ini` (or `pyproject.toml`) |
| **Quick run command** | `cd apps/visualizer/backend && pytest -x -q` |
| **Full suite command** | `cd apps/visualizer/backend && pytest` |
| **Estimated runtime** | ~30–60 seconds (663 tests baseline) |

---

## Sampling Rate

- **After every task commit:** Run `cd apps/visualizer/backend && pytest -x -q`
- **After every plan wave:** Run `cd apps/visualizer/backend && pytest`
- **Before `/gsd-verify-work`:** Full suite must be green (663 tests, 0 failures)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | REFACTOR-01 | — | N/A | import smoke | `python -c "from jobs.handlers import JOB_HANDLERS"` | ✅ | ⬜ pending |
| 13-01-02 | 01 | 1 | REFACTOR-01 | — | N/A | unit | `cd apps/visualizer/backend && pytest -x -q` | ✅ | ⬜ pending |
| 13-02-01 | 02 | 2 | REFACTOR-01 | — | N/A | unit | `cd apps/visualizer/backend && pytest -x -q` | ✅ | ⬜ pending |
| 13-03-01 | 03 | 3 | REFACTOR-01 | — | N/A | unit | `cd apps/visualizer/backend && pytest -x -q` | ✅ | ⬜ pending |
| 13-04-01 | 04 | 4 | REFACTOR-01 | — | N/A | unit | `cd apps/visualizer/backend && pytest -x -q` | ✅ | ⬜ pending |
| 13-05-01 | 05 | 5 | REFACTOR-01 | — | N/A | unit | `cd apps/visualizer/backend && pytest -x -q` | ✅ | ⬜ pending |
| 13-06-01 | 06 | 6 | REFACTOR-01 | — | N/A | unit | `cd apps/visualizer/backend && pytest` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files needed — this is a pure refactor; existing 663 tests are the verification harness.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `app.py` import path unchanged | REFACTOR-01 | Import smoke is automated, but confirm Flask app starts correctly | `cd apps/visualizer/backend && python -c "import app"` — must not raise ImportError |
| Patch strings in tests updated | REFACTOR-01 | grep-verifiable | `grep -r "patch('jobs.handlers\." tests/` — after final commit, no patches should target `jobs.handlers.<name>` (the old flat module); all should target `jobs.handlers.<family>.<name>` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
