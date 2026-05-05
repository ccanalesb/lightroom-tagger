---
phase: 12
slug: operational-baseline-embed-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend), vitest (frontend) |
| **Config file** | `apps/visualizer/backend/pytest.ini` / `apps/visualizer/frontend/vitest.config.ts` |
| **Quick run command** | `cd apps/visualizer/backend && pytest tests/test_handlers_batch_embed_image.py tests/test_orphan_recovery.py -x -q` |
| **Full suite command** | `cd apps/visualizer/backend && pytest -x -q && cd ../frontend && npx vitest run` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| OPS-02 preflight threshold | backend | 1 | OPS-02 | unit | `pytest tests/test_handlers_batch_embed_image.py -k preflight -x -q` | ⬜ pending |
| OPS-03 skip payload | backend | 1 | OPS-03 | unit | `pytest tests/test_handlers_batch_embed_image.py -k skip -x -q` | ⬜ pending |
| OPS-04 compression noise | backend | 1 | OPS-04 | unit | `pytest tests/test_orphan_recovery.py -x -q` | ⬜ pending |
| OPS-05 TestDefaults | backend | 1 | OPS-05 | unit | `pytest tests/test_providers_api.py::TestDefaults -x -q` | ⬜ pending |
| OPS-01 frontend discoverability | frontend | 2 | OPS-01 | unit | `cd apps/visualizer/frontend && npx vitest run` | ⬜ pending |
| OPS-03 JobDetailModal UI | frontend | 2 | OPS-03 | unit | `cd apps/visualizer/frontend && npx vitest run --reporter=verbose` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — no new test infrastructure needs installing.

- `apps/visualizer/backend/tests/test_handlers_batch_embed_image.py` — extend with >50% preflight abort test
- `apps/visualizer/backend/tests/test_orphan_recovery.py` — extend with OPS-04 compression noise suppression test

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OPS-01 embed link renders in non-Search surfaces | OPS-01 | Requires live UI with no_clip_embedding state | Load a surface that shows similarity-unavailable, verify link to Catalog cache renders |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
