# ADR-0001: Split analyzer.py into focused modules

**Status:** Accepted  
**Date:** 2026-04-29

## Context

`lightroom_tagger/core/analyzer.py` (754 lines) exported 16 symbols spanning five unrelated concerns: model config, image preparation, image inspection, vision comparison, and description generation. Fifteen callers imported different subsets. The interface was nearly as large as the implementation — a shallow grab-bag, not a deep module.

## Decision

Split `analyzer.py` into four focused modules:

- `image_prep.py` — `compress_image`, `convert_raw_to_jpg`, `get_viewable_path`, `RAW_EXTENSIONS`, `VIDEO_EXTENSIONS`
- `image_inspect.py` — `compute_phash`, `extract_exif`
- `vision_compare.py` — comparison pipeline via `_compare_via_provider` only (OpenAI-compat)
- `description.py` — describe pipeline via `_describe_image_via_provider` only (OpenAI-compat)

Model config functions (`get_vision_model`, `get_description_model`) move to `config.py`.

The following are retired (not moved):

- `analyze_image` — legacy monolithic entry point; callers updated to use decomposed pipeline
- `run_local_agent` — legacy direct `ollama.chat` path; superseded by `_describe_image_via_provider`
- `run_vision_ollama` — legacy direct `ollama.chat` compare path; superseded by `_compare_via_provider`

All description and comparison calls route through `vision_client` → `ProviderRegistry`. The `ollama` package is no longer a hard requirement for the core vision path.

## Consequences

- Each module is independently testable through its own interface
- Bugs in image prep are findable in ~100 lines, not buried in 750
- The provider seam is real: swapping Ollama for NIM/OpenRouter requires no changes to core logic
- Tests for `run_vision_ollama` and `run_local_agent` are replaced by tests on `vision_compare.py` and `description.py` interfaces via mocked providers
