---
phase: 14
slug: database-images-api-split
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pytest.ini` or `pyproject.toml` (project root) |
| **Quick run command** | `cd lightroom_tagger && python -m pytest core/database/ -x -q 2>/dev/null || python -m pytest core/test_database*.py -x -q` |
| **Full suite command** | `python -m pytest lightroom_tagger/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (database subpackage tests)
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | REFACTOR-02 | — | N/A | smoke | `python -m pytest lightroom_tagger/ -x -q` | ✅ existing | ⬜ pending |
| 14-01-02 | 01 | 1 | REFACTOR-02 | — | N/A | import | `python -c "from lightroom_tagger.core.database import init_database"` | ❌ W0 | ⬜ pending |
| 14-02-01 | 02 | 2 | REFACTOR-02 | — | N/A | unit | `python -m pytest lightroom_tagger/core/test_database_catalog.py -x -q` | ❌ W0 | ⬜ pending |
| 14-03-01 | 03 | 3 | REFACTOR-03 | — | N/A | smoke | `python -m pytest apps/visualizer/backend/ -x -q 2>/dev/null` | ✅ existing | ⬜ pending |
| 14-03-02 | 03 | 3 | REFACTOR-03 | — | N/A | import | `python -c "from api.images import catalog_bp, stacks_bp, instagram_bp, matches_bp, search_bp"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Scaffold `lightroom_tagger/core/database/` subpackage with empty modules + `__init__.py` re-exporting from original flat file
- [ ] Scaffold `apps/visualizer/backend/api/images/` subpackage with empty modules + `__init__.py`
- [ ] Verify import smoke test passes after each scaffold commit

*Existing pytest infrastructure covers all phase requirements — no new test framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Frontend fetch URLs work after D-09 migration | REFACTOR-03 D-09 | Requires running dev server + browser | Start backend + frontend dev server; navigate to catalog, search, stacks, instagram, matches pages; verify no 404s in network tab |
| Backend API endpoints respond correctly after Blueprint split | REFACTOR-03 | Requires running Flask app | `curl http://localhost:5000/api/images/catalog` → 200; `curl http://localhost:5000/api/images/stacks` → 200 (or empty list) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
