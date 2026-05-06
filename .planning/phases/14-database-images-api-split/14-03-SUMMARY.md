---
phase: 14-database-images-api-split
plan: 14-03
subsystem: database
tags:
  [
    sqlite,
    refactor,
    module-split,
    descriptions,
    embeddings,
    similarity,
    vision-cache,
  ]

requires:
  - phase: 14-database-images-api-split (14-02)
    provides: First `_legacy.py` carve-out (catalog, instagram, matches, stacks, db_init wiring)
provides:
  - Descriptions FTS + CRUD helpers in `database/descriptions.py`
  - Perspectives and structured scores in `database/scores.py`
  - Text/CLIP embedding helpers in `database/embeddings.py`
  - Catalog similarity job persistence in `database/similarity.py`
  - Vision cache and comparison helpers in `database/vision_cache.py`
  - `database/__init__.py` re-exports entirely from topical modules (`from ._legacy import` removed)
  - `_legacy.py` retained as empty shim (plan 14-07 owns deletion)

affects:
  - Anyone importing `lightroom_tagger.core.database` (surface unchanged via barrel)
  - Phase 14-04..14-06 work that touches database layout

tech-stack:
  added: []
  patterns:
    - "Relative imports only inside DB subpackages (`from .db_init …`, `from ..analyzer …`)"
    - "Barrel aggregates explicit submodule imports instead of transitional `_legacy`"

key-files:
  created: []
  modified:
    [
      lightroom_tagger/core/database/descriptions.py,
      lightroom_tagger/core/database/scores.py,
      lightroom_tagger/core/database/embeddings.py,
      lightroom_tagger/core/database/similarity.py,
      lightroom_tagger/core/database/vision_cache.py,
      lightroom_tagger/core/database/__init__.py,
      lightroom_tagger/core/database/_legacy.py,
      lightroom_tagger/core/database/catalog.py,
      lightroom_tagger/core/database/db_init.py,
    ]

key-decisions:
  - '`is_vision_cache_valid` pulls `RAW_EXTENSIONS` / `VIDEO_EXTENSIONS` via `from ..analyzer import` (replacing legacy absolute import)'
  - "Internal FTS/search lazy imports rerouted `catalog.py` → `descriptions`; `db_init._migrate_image_descriptions_fts` → `descriptions`"

patterns-established:
  - "Wave-3 domain order invariant: descriptions → scores → embeddings → similarity → vision_cache"

requirements-completed: [REFACTOR-02]

duration: ~54m
started: 2026-05-06T13:50:00Z
completed: 2026-05-06T14:44:04Z
---

# Phase 14 Plan 03: `_legacy.py` remainder → domain modules Summary

**All remaining database symbols exited `_legacy.py` across five topical modules while preserving the barrel import surface (`from lightroom_tagger.core.database import …`).**

## Performance

- **Duration:** ~54 min (session estimate)
- **Started:** 2026-05-06T13:50:00Z
- **Completed:** 2026-05-06T14:44:04Z
- **Tasks:** 5 (one commit each: descriptions → scores → embeddings → similarity → vision\_cache)
- **Files touched:** 8 tracked paths (`descriptions/scores/embeddings/similarity/vision_cache`, `__init__`, `_legacy`, plus `catalog` + `db_init` import fixes after wave 1)

## Accomplishments

- Five sequential migrations emptied `_legacy.py` **definitions** entirely (`grep -Ec '^(def |class )' …/_legacy.py` → **0**).
- Barrel now imports **`vision_cache`** (and sibling modules); **no `from ._legacy import`** remaining in `__init__.py`.
- Top-level `def`/`class` count across `lightroom_tagger/core/database/*.py` held at **124** (code motion only).

## Task Commits

1. **Task descriptions** — `39f5f1d` (`feat`)
2. **Task scores** — `6383f1f` (`feat`)
3. **Task embeddings** — `1318908` (`feat`)
4. **Task similarity** — `e84f6d8` (`feat`)
5. **Task vision\_cache** — `07f8dfa` (`feat`)

## Files Created/Modified

| Path | Notes |
|------|-------|
| `lightroom_tagger/core/database/descriptions.py` | FTS helpers, description CRUD, undescribed listings, grouped query |
| `lightroom_tagger/core/database/scores.py` | Perspectives CRUD + `image_scores` helpers |
| `lightroom_tagger/core/database/embeddings.py` | Text/CLIP vec0 upserts and key listing pipelines |
| `lightroom_tagger/core/database/similarity.py` | CLIP-order listing + similarity group persistence |
| `lightroom_tagger/core/database/vision_cache.py` | Vision cache sentinel, cache rows, comparisons |
| `lightroom_tagger/core/database/__init__.py` | Re-exports from submodules only (no `_legacy` imports) |
| `lightroom_tagger/core/database/_legacy.py` | Empty transitional shim awaiting 14-07 removal |
| `lightroom_tagger/core/database/catalog.py` | Lazy `build_description_fts_query` import points at `.descriptions` |
| `lightroom_tagger/core/database/db_init.py` | FTS migration pulls `build_description_search_document` from `.descriptions` |

## Decisions Made

- **Analyzer extensions for cache validity** — Imported with `from ..analyzer import RAW_EXTENSIONS, VIDEO_EXTENSIONS` inside `vision_cache.py` to satisfy submodule-relative rule and preserve behavior.
- **Internal import rewiring alongside wave 1** — Moved description helper lazy imports off `_legacy` into `catalog`/`db_init` so tests and migrations resolve without cyclic failures.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 — Blocking test failures] Wired internal lazy imports away from emptied `_legacy`**

- **Found during:** Commit A (`descriptions`): `catalog._append_query_catalog_image_filters`, `db_init._migrate_image_descriptions_fts` still imported from `._legacy`.
- **Fix:** Point lazy imports at `descriptions.build_description_*`. No API change.
- **Files modified:** `catalog.py`, `db_init.py` (same commit bucket as descriptions wave).
- **Verification:** `pytest lightroom_tagger/core/` green (269 passed).
- **Committed in:** `39f5f1d`.

---

**Total deviations:** 1 auto-fixed (blocking correctness / import breakage)

**Impact on plan:** Necessary parity fix; narrow scope (~2 callsites).

## Issues Encountered

None beyond the importer churn above.

## User Setup Required

None.

## Next Phase Readiness

- Wave-3 complete; **`_legacy.py` has zero defs/classes**, ready for 14-07 deletion/cleanup orchestration.
- `STATE.md` / `ROADMAP.md` deliberately **not** updated here (orchestrator-owned per objective).

---

## Verification (self-check)

| Check | Command / criterion | Result |
|-------|---------------------|--------|
| Legacy empty of defs/classes | `grep -Ec '^(def \|class )' lightroom_tagger/core/database/_legacy.py` | **0** |
| Barrel independence | No `from ._legacy import` in `database/__init__.py` | **PASS** (`rg` confirms absent) |
| Symbol count invariant | Sum of `grep -Ec '^(def \|class )'` across `database/*.py` | **124** |
| Core tests | `pytest lightroom_tagger/core/` | **269 passed** |

## Self-Check: PASSED

---
_Phase: 14-database-images-api-split · Plan: 14-03_
