---
id: SEED-020
status: dormant
planted: 2026-04-21
planted_during: v2.1 Phase 8 — Two-stage cascade matching
trigger_when: whenever we touch the backend heavily (new handler or API route)
scope: medium
---

# SEED-020: Backend DRY/KISS refactor — split oversized files and extract shared utils

## Why This Matters

The backend has grown into several very large files that are both hard to navigate
and contain duplicated logic. When one copy of duplicated code gets updated, sibling
copies silently diverge — this is how subtle bugs get introduced.

Current line counts (key offenders):
- `jobs/handlers.py` — 2,176 lines (single file for all job handlers)
- `api/images.py` — 979 lines
- `lightroom_tagger/core/identity_service.py` — 631 lines
- `database.py` — 537 lines

Problems this causes:
- Hard to find the right function when adding a feature or fixing a bug
- Duplicated DB query patterns, error handling, and pagination boilerplate
  across API routes — one fix in one place, but not everywhere
- Handlers mix orchestration logic with low-level I/O, making unit testing hard
- New contributors (or future-Claude) can't understand module boundaries

The fix is to apply DRY and KISS systematically:
1. Split `handlers.py` into per-concern modules (describe, score, match, analyze…)
2. Extract reusable DB query helpers into a shared `utils/queries.py`
3. Extract shared pagination, error-response, and validation patterns
4. Keep each file focused on one responsibility

## When to Surface

**Trigger:** Whenever we touch the backend heavily — adding a new handler, new API
route, or new service — the size and duplication make the work harder than it needs
to be.

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- Milestone involves adding or modifying backend handlers or API routes
- Milestone involves backend performance, reliability, or testing improvements
- Milestone is a technical debt / backend health cycle

## Scope Estimate

**Medium** — A phase or two, needs planning. Likely split into:
1. Audit pass — map duplicated patterns and draw new module boundaries (PLAN)
2. Split `handlers.py` into per-handler modules with shared base utilities
3. Extract `api/images.py` and `identity_service.py` into focused sub-modules
4. Add/update tests to cover the extracted helpers

No behavior changes — pure structural refactor with test coverage as the safety net.

## Breadcrumbs

Key files to refactor:

- `apps/visualizer/backend/jobs/handlers.py` — 2,176 lines, all job handlers in one file
- `apps/visualizer/backend/api/images.py` — 979 lines, catalog + instagram image routes
- `lightroom_tagger/core/identity_service.py` — 631 lines, scoring + reason generation
- `apps/visualizer/backend/database.py` — 537 lines, DB access layer
- `apps/visualizer/backend/jobs/runner.py` — orchestrates handlers, tightly coupled
- `apps/visualizer/backend/utils/responses.py` — existing shared util (good pattern to expand)
- `apps/visualizer/backend/utils/db.py` — existing DB util (good pattern to expand)

## Notes

The `utils/` directory already exists with `responses.py` and `db.py` — the
pattern of extracting shared helpers is already established, just needs to be applied
more broadly. The refactor should follow that existing convention rather than
introducing a new architecture.
