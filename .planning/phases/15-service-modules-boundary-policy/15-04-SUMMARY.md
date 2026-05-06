---
phase: 15-service-modules-boundary-policy
plan: 15-04
subsystem: api
tags: [python, refactoring, ADR-0001, analyzer, provider-registry]

requires:
  - phase: 15-service-modules-boundary-policy
    provides: analyzer package scaffold (15-03)
provides:
  - Real implementations in analyzer/image_prep, image_inspect, description, vision_compare
  - Retired analyze_image, run_local_agent, run_vision_ollama and deleted _legacy.py
  - scoring_service uses ProviderRegistry defaults when provider_id omitted
  - compare_with_vision(provider_id=None) resolves defaults.vision_comparison or fallback_order
affects:
  - Call sites that inlined the former analyze_image pipeline; tests patching analyzer internals

tech-stack:
  added: []
  patterns:
    - "Describe and compare flows resolve default provider IDs via ProviderRegistry (defaults.description / defaults.vision_comparison, then fallback_order)."
    - "Scoring legacy Ollama branch removed; unified FallbackDispatcher path for score + JSON repair."

key-files:
  created:
  modified:
    - lightroom_tagger/core/analyzer/image_prep.py
    - lightroom_tagger/core/analyzer/image_inspect.py
    - lightroom_tagger/core/analyzer/description.py
    - lightroom_tagger/core/analyzer/vision_compare.py
    - lightroom_tagger/core/analyzer/__init__.py
    - lightroom_tagger/core/vision_client.py
    - lightroom_tagger/core/scoring_service.py
    - lightroom_tagger/core/test_analyzer.py
    - apps/visualizer/backend/jobs/handlers/matching.py
    - lightroom_tagger/cli.py
    - lightroom_tagger/scripts/analyze_instagram_images.py
    - lightroom_tagger/lightroom/enricher.py
    - lightroom_tagger/instagram/crawler.py

key-decisions:
  - "describe_image(provider_id=None) uses registry defaults.description (same resolution pattern as nl_catalog_search) instead of ollama.chat via run_local_agent."
  - "compare_with_vision(provider_id=None) uses defaults.vision_comparison then fallback_order — never legacy HTTP Ollama compare."
  - "run_external_agent stub moved to description.py; _legacy module deleted."

patterns-established:
  - "Vision/compare/describe public API stays on ``lightroom_tagger.core.analyzer`` barrel imports from four submodules + config getters."

requirements-completed: [REFACTOR-04]

duration: ~45min
completed: 2026-05-06
---

# Phase 15 Plan 04: Analyzer submodule population Summary

**Analyzer logic is split into `image_prep`, `image_inspect`, `description`, and `vision_compare`; `analyze_image`, `run_local_agent`, `run_vision_ollama`, and `_legacy.py` are removed; scoring and comparison use the provider registry exclusively.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-06 (approx.)
- **Completed:** 2026-05-06
- **Tasks:** 6
- **Files modified:** 13+

## Accomplishments

- Image prep / inspection live in dedicated modules under `analyzer/`.
- Description pipeline consolidated in `description.py`; local describe uses registry defaults instead of direct Ollama.
- Vision comparison in `vision_compare.py`; `provider_id=None` resolves configured defaults like the explicit-provider path.
- `scoring_service` no longer calls `run_local_agent`; unresolved `provider_id` uses description defaults + `FallbackDispatcher`.
- Production callers former `analyze_image(path)` inlined `compute_phash` / `extract_exif` / `describe_image` with the same result dict keys.
- `lightroom_tagger/core/analyzer/_legacy.py` deleted.

## Task Commits

Each task was committed atomically:

1. **Task 15-04-T01: Extract image_prep and image_inspect** — `a708ea4`
2. **Task 15-04-T02: Extract description pipeline** — `ae31808`
3. **Task 15-04-T03: Extract vision_compare; remove run_vision_ollama** — `928e185`
4. **Task 15-04-T04: Retire run_local_agent; migrate scoring_service** — `604d0f3`
5. **Task 15-04-T05: Retire analyze_image; migrate callers** — `9942d2a`
6. **Task 15-04-T06: Delete _legacy; verify barrel** — `7e8a28d`

## Files Created/Modified

- **`lightroom_tagger/core/analyzer/image_prep.py`** — RAW/extensions, compression, RAW→JPEG, viewable path.
- **`lightroom_tagger/core/analyzer/image_inspect.py`** — pHash and EXIF extraction.
- **`lightroom_tagger/core/analyzer/description.py`** — prompt, parsing, `describe_image`, `_describe_image_via_provider`, stub `run_external_agent`.
- **`lightroom_tagger/core/analyzer/vision_compare.py`** — `compare_with_vision`, `_compare_via_provider`, token escalation, parsers, `vision_score`.
- **`lightroom_tagger/core/analyzer/__init__.py`** — Barrel imports only submodules + config; no `_legacy`.
- **`lightroom_tagger/core/vision_client.py`** — Imports `build_description_prompt` / `parse_vision_response` from submodules.
- **`lightroom_tagger/core/scoring_service.py`** — Single provider path via registry default resolution when `provider_id` is omitted.
- **Call sites** — `matching.py`, `cli.py`, enricher/crawler/script: inlined analyze pipeline.
- **`lightroom_tagger/core/test_analyzer.py`** — Patches target `vision_compare` / barrel symbols; obsolete tests removed.

## Decisions Made

- Default vision-comparison provider when `provider_id` is `None` uses `defaults.vision_comparison` then `fallback_order`.
- Scoring uses `defaults.description` for unresolved `provider_id` so one JSON-repair stack (`complete_chat_text` from the resolved client) applies everywhere.

## Deviations from Plan

None — plan executed as written.

## Issues Encountered

None blocking; test patch targets moved from `_legacy` to `vision_compare` / package-level symbols after module split.

## User Setup Required

None — callers without explicit `provider_id` rely on valid `providers.json` defaults (unchanged expectation for the registry stack).

## Next Phase Readiness

- Analyzer package matches ADR-0001 filenames with real implementations; `_legacy.py` gone.
- **Orchestrator** updates `STATE.md` / `ROADMAP.md` / requirements after wave merge (skipped here per objective).

## Verification log

| Check | Result |
|-------|--------|
| `rg "^def (analyze_image|run_local_agent|run_vision_ollama)\\b" lightroom_tagger` | PASS |
| `rg "analyze_image|run_local_agent|run_vision_ollama" lightroom_tagger apps --glob "*.py"` | PASS |
| `test ! -f analyzer/_legacy.py` | PASS |
| `grep "_legacy"` on `analyzer/__init__.py` | PASS (no matches) |
| `pytest lightroom_tagger/core/ -x -q` | PASS |
| `pytest apps/visualizer/backend/tests/ -x -q` | PASS |
| `python -c "from lightroom_tagger.core.matcher import score_candidates_with_vision"` | PASS |

## Self-Check: PASSED

## Orchestrator note

`STATE.md` and `ROADMAP.md` were **not** updated in this run (executor objective).
