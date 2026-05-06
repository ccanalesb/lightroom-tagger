---
phase: 15-service-modules-boundary-policy
plan: 15-03
subsystem: api
tags: [python, refactoring, package-barrel, ADR-0001]

requires:
  - phase: 15-02
    provides: model getters on config; analyzer re-exports
provides:
  - lightroom_tagger/core/analyzer/ package scaffold (_legacy + four ADR stub modules + barrel)
affects:
  - Follow-on analyzer splits (15-04+); imports of lightroom_tagger.core.analyzer

tech-stack:
  added: []
  patterns:
    - "Analyzer package scaffold: monolith in _legacy.py; explicit from ._legacy import (...) barrel (no star imports)."

key-files:
  created:
    - lightroom_tagger/core/analyzer/__init__.py
    - lightroom_tagger/core/analyzer/_legacy.py
    - lightroom_tagger/core/analyzer/image_prep.py
    - lightroom_tagger/core/analyzer/image_inspect.py
    - lightroom_tagger/core/analyzer/vision_compare.py
    - lightroom_tagger/core/analyzer/description.py
  modified:
    - lightroom_tagger/core/analyzer.py → removed (replaced by package)

key-decisions: []
patterns-established:
  - "ADR-0001 scaffold filenames under analyzer/; behavior remains in _legacy until later plans."

requirements-completed: [REFACTOR-04]

duration: pending
completed: pending
---

# Phase 15 Plan 03: analyzer/ package scaffold — WIP

This file is opened in **15-03-T01** with the export baseline; it will be finalized after all tasks and verification.

## Baseline exports (15-03-T01)

AST-derived top-level definers in `lightroom_tagger/core/analyzer.py` plus `ImportFrom` bindings from `lightroom_tagger.*` only (excludes `typing`, stdlib, third-party). **Count: 30** names (sorted):

`_broken_provider_models`, `_compare_via_provider`, `_DESCRIPTION_FALLBACK`, `_describe_image_via_provider`, `_model_min_tokens`, `analyze_image`, `build_description_prompt`, `compare_with_vision`, `compress_image`, `compute_phash`, `ContextLengthError`, `convert_raw_to_jpg`, `DESCRIPTION_PROMPT`, `describe_image`, `extract_exif`, `get_description_model`, `get_viewable_path`, `get_vision_model`, `load_config`, `MAX_TOKENS_ESCALATION`, `parse_description_response`, `parse_vision_response`, `RAW_EXTENSIONS`, `run_external_agent`, `run_local_agent`, `run_vision_ollama`, `VIDEO_EXTENSIONS`, `VISION_COMPRESS_QUALITY`, `VISION_MAX_DIMENSION`, `vision_score`.

Required spot-check names present: `compress_image`, `compute_phash`, `compare_with_vision`, `describe_image`, `get_vision_model`, `analyze_image`.
