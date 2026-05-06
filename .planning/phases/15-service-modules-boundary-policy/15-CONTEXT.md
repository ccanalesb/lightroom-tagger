# Phase 15: Service modules & boundary policy — Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Slim `analyzer.py` (771L), `matcher.py` (747L), and `identity_service.py` (697L) to under 400 lines each by splitting them into domain sub-packages (consistent with the Phase 14 database pattern). Extract shared and non-core helpers aggressively. Document and enforce the module boundary policy via `docs/architecture.md`, `pyproject.toml` comments, a `wc -l` CI shell check, and a `test_architecture.py` pytest file that asserts both size limits and import-graph layer rules.

**CRITICAL:** Four ADRs are accepted and ready to implement — these are the canonical specification for this phase. Downstream agents MUST read all four before planning.

</domain>

<decisions>
## Implementation Decisions

### D-01: File split structure
Use **domain sub-packages** for each large file — same pattern as Phase 14 (`database/` package). Each file becomes a package directory with internal submodules and a barrel `__init__.py` that re-exports the prior flat module surface unchanged.

- `analyzer.py` → `analyzer/` package (per ADR-0001: `image_prep.py`, `image_inspect.py`, `vision_compare.py`, `description.py`)
- `matcher.py` → `matcher/` package (submodules TBD by planner based on function inventory)
- `identity_service.py` → `identity_service/` package (submodules TBD by planner)

### D-02: Extraction scope — aggressive
Extract **everything non-core domain logic**, even if a helper only lives in one file today. Core domain logic = the central computation of the module (scoring, describing, ranking). Everything else (image path resolution, compression, parsing utilities, provider dispatch boilerplate) moves out to sub-modules or shared helpers.

### D-03: ADR-0001 is the authoritative split map for `analyzer.py`
Follow ADR-0001 exactly:
- `image_prep.py` — `compress_image`, `convert_raw_to_jpg`, `get_viewable_path`, `RAW_EXTENSIONS`, `VIDEO_EXTENSIONS`
- `image_inspect.py` — `compute_phash`, `extract_exif`
- `vision_compare.py` — comparison pipeline (`_compare_via_provider` only)
- `description.py` — describe pipeline (`_describe_image_via_provider` only)
- Model config fns (`get_vision_model`, `get_description_model`) move to `config.py`
- Retire: `analyze_image`, `run_local_agent`, `run_vision_ollama` (legacy paths)

### D-04: ADR-0004 — shared exceptions package
Implement `lightroom_tagger/core/exceptions/` package:
- `__init__.py` — re-exports everything
- `provider_errors.py` — moved from `core/provider_errors.py`
- `db_errors.py` — `StackMutationError` and future DB-layer errors

`core/provider_errors.py` becomes a re-export shim during transition, then removed.

### D-05: Boundary policy location
**`pyproject.toml` comments** (near `[tool.ruff]`) pointing to `docs/architecture.md` as the authoritative policy doc. `docs/architecture.md` is a new file containing:
- Layer diagram (handler → service/pipeline → repository/database)
- Max file size rule (400L)
- What belongs in each layer
- Import rules (handlers import from core/, services don't import from api/)

### D-06: CI enforcement — two-layer
1. **`wc -l` shell check** — fast size gate, fails CI on any tracked `core/*.py` file exceeding 400L; runs before tests
2. **`test_architecture.py` in `lightroom_tagger/core/`** — pytest assertions:
   - Size assertions: each module under 400L (second enforcement point, regression-safe)
   - Import graph assertions: `api/` modules don't import from other `api/` modules; `core/*.py` service files don't import from `api/`

### Claude's Discretion
- Exact submodule names and breakdown for `matcher/` and `identity_service/` packages — planner should derive these from the function inventory, following the same "domain function grouping" principle as ADR-0001
- Whether `matcher/` needs a `find_candidates.py` vs folding date-window queries into the `database/` layer (already split in Phase 14)
- Exact `wc -l` CI script location (`.github/workflows/`, `Makefile` target, or `scripts/check_sizes.sh`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture Decision Records (authoritative specs for this phase)
- `docs/adr/0001-split-analyzer.md` — Exact split map for `analyzer.py` → 4 submodules + retirements
- `docs/adr/0002-split-database.md` — Reference pattern for sub-package splits (already implemented in Phase 14)
- `docs/adr/0003-pipeline-layer.md` — Handler → pipeline → service layer model; boundary rules
- `docs/adr/0004-shared-exceptions.md` — `exceptions/` package layout and migration path

### Prior phase context (established patterns)
- `.planning/phases/14-database-images-api-split/14-01-SUMMARY.md` — Scaffold pattern: `_legacy.py` + barrel `__init__.py` + stub submodules
- `.planning/phases/13-handlers-split-per-job-family/` — Handler split discipline

### Tooling
- `pyproject.toml` — Existing `[tool.ruff]` config; `[tool.pytest.ini_options]` location for test discovery

</canonical_refs>

<code_context>
## Existing Code Insights

### Files being split
- `lightroom_tagger/core/analyzer.py` — 771L; ADR-0001 maps the exact split
- `lightroom_tagger/core/matcher.py` — 747L; no ADR yet, planner derives from function inventory
- `lightroom_tagger/core/identity_service.py` — 697L; no ADR yet, planner derives from function inventory

### Reusable patterns (from Phase 14)
- `database/__init__.py` barrel pattern — explicit `from .submodule import (...)`, no star re-exports
- `database/_legacy.py` → rename → submodule migration sequence — proven safe with full pytest pass at each step
- `deac067` commit — scaffold task template to follow

### Existing shared utilities (may absorb extracted helpers)
- `lightroom_tagger/core/path_utils.py` — already exists; extracted image path helpers could go here
- `lightroom_tagger/core/config.py` — model config functions from ADR-0001 land here
- `lightroom_tagger/core/vision_client.py` — provider dispatch already isolated here

### Integration points
- All callers import from `lightroom_tagger.core.analyzer`, `...matcher`, `...identity_service` — barrel must preserve these exactly
- `apps/visualizer/backend/` handlers import from all three files; no import changes expected post-split
- `lightroom_tagger/core/database/` (Phase 14) is the reference implementation for the barrel pattern

</code_context>

<specifics>
## Specific Ideas

- ADR-0001 explicitly retires `analyze_image`, `run_local_agent`, `run_vision_ollama` — callers must be updated, not just the barrel re-exported
- The `exceptions/` package (ADR-0004) is a prerequisite for clean imports in the split submodules — implement it early in the wave sequence
- `test_architecture.py` should import `ast` or `importlib` to walk import graphs — no third-party dep needed

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 15-service-modules-boundary-policy*
*Context gathered: 2026-05-06*
