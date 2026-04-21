---
phase: 5
plan: "01"
slug: posted-filter-best-photos-api
subsystem: api
tags: [flask, identity, best-photos, instagram_posted]

requires:
  - phase: 4
    provides: Reusable filter framework (query-param patterns)
provides:
  - Optional `posted` tri-state on `rank_best_photos` applied before pagination totals
  - `GET /api/identity/best-photos?posted=` parsing with 400 on invalid values
  - `IdentityAPI.getBestPhotos({ posted })` query string support
affects: [Phase 5 Plans 02–04 (Dashboard + Identity UI)]

tech-stack:
  added: []
  patterns:
    - "Optional query param helpers return `(value, error_response)` tuples consistent with `_parse_sort_by_date`"

key-files:
  created: []
  modified:
    - lightroom_tagger/core/identity_service.py
    - lightroom_tagger/core/test_identity_service.py
    - apps/visualizer/backend/api/identity.py
    - apps/visualizer/backend/tests/test_identity_api.py
    - apps/visualizer/frontend/src/services/api.ts

key-decisions:
  - "Filter enriched ranked rows after sort, before `total`/`offset` slice — preserves correct top-N semantics per posted state."
  - "API accepts true/false via common truthy/falsy strings; invalid values return `posted must be true or false`."

requirements-completed: []

# Metrics — DASH-02/DASH-03 remain open until Plan 04 (UI). This plan delivers the API/client prerequisite listed in 05-CONTEXT Errata.
duration: ~15 min
completed: 2026-04-21T00:00:00Z
---

# Phase 5 Plan 01: Posted filter for best-photos (backend + API client) — Summary

**End-to-end optional `posted` filter for ranked best photos:** core ranking filters after sort, Flask parses `posted` for `/api/identity/best-photos`, and the TypeScript client sends `posted=true|false` only when set (All-tab uses `undefined`).

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-21 (session)
- **Completed:** 2026-04-21
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `rank_best_photos(..., posted: bool | None = None)` narrows eligible rows by `instagram_posted` before `total` and page slice.
- Identity REST route accepts optional `posted` with the same truthy/falsy vocabulary as other flags; garbage values yield 400 with a stable message.
- `IdentityAPI.getBestPhotos` includes `posted?: boolean` and sets `URLSearchParams` only when defined.

## Task Commits

Each task was committed atomically:

1. **Task 01: Filter ranked rows in rank_best_photos** — `200e074` (`feat(05-01): filter rank_best_photos by Instagram posted status`)
2. **Task 02: Parse posted query param and pass into rank_best_photos** — `19af30f` (`feat(05-01): parse posted query param on identity best-photos API`)
3. **Task 03: TypeScript client getBestPhotos posted param** — `3a6c54e` (`feat(05-01): add posted param to IdentityAPI.getBestPhotos`)

## Files Created/Modified

- `lightroom_tagger/core/identity_service.py` — `posted` parameter; filter list comprehension after sort.
- `lightroom_tagger/core/test_identity_service.py` — `test_rank_best_photos_filters_by_posted`.
- `apps/visualizer/backend/api/identity.py` — `_parse_optional_posted`, wire into `best_photos`.
- `apps/visualizer/backend/tests/test_identity_api.py` — `posted=true` 200 shape, `posted=maybe` 400; stricter `total` type on baseline test.
- `apps/visualizer/frontend/src/services/api.ts` — `getBestPhotos` params + `sp.set('posted', ...)`.

## Verification

Repository root (`lightroom-tagger`):

```
$ pytest lightroom_tagger/core/test_identity_service.py -q
......                                                                   [100%]
6 passed in 0.10s

$ cd apps/visualizer/backend && pytest tests/test_identity_api.py -q
......                                                                   [100%]
6 passed in 0.40s

$ cd apps/visualizer/frontend && npx tsc --noEmit && npx vitest run
(38 test files, 220 tests — all passed)
```

## Self-Check: PASSED

All plan `<acceptance_criteria>` and `<verification>` commands were run; outputs logged above.

## Deviations from Plan

None — plan executed exactly as written.

**Requirements note:** PLAN frontmatter lists DASH-02, DASH-03; full dashboard tab UX and filter-framework wiring are **Plan 04**. This plan does not mark those requirements complete in `REQUIREMENTS.md`.

## Next Steps

Ready for **Plan 02** (`best-photos-overlay-posted-badge`, Wave 2, depends on 01).
