---
phase: 15
status: has_findings
files_reviewed: 33
findings:
  critical: 1
  warning: 3
  info: 4
  total: 8
---

## Summary

Phase 15 successfully centralizes errors under `lightroom_tagger.core.exceptions`, splits the analyzer into focused modules, extracts `identity_service` and `matcher` subpackages, and encodes boundary rules in `docs/architecture.md`, `scripts/check_core_file_sizes.sh`, and `test_architecture.py`. All reviewed `lightroom_tagger/core/**/*.py` files are at or under the 400-line budget (largest: `matcher/score_with_vision.py` at 398 lines). No inner-module imports of `lightroom_tagger.core.exceptions.*` submodules were found in application code; ADR-0004’s public surface is respected.

There is one **critical** defect: several pipelines add `get_viewable_path()` results to a “temp files” list whenever the path differs from the original, but that path can be a **persistent JPG sidecar** next to a RAW/DNG — `os.unlink` then deletes user data. A few secondary issues cover token-cache keying, leaky abstractions (`matcher` barrel), and minor hygiene (unused parameter, swallowed errors, logging).

## Findings

### CR-001 (critical): Unlink may delete JPG sidecars for RAW inputs
**File:** `lightroom_tagger/core/analyzer/image_prep.py:129-135`, `lightroom_tagger/core/analyzer/vision_compare.py:78-103`, `lightroom_tagger/core/analyzer/description.py:221-255`, `lightroom_tagger/core/scoring_service.py:167-254`  
**Issue:** `get_viewable_path()` returns existing `.jpg` / `.JPG` sidecars for RAW files (`image_prep.py`, lines 129–135). Callers track cleanup with `if viewable != original: temp_files.append(viewable)`, then unconditionally `unlink` those paths in `finally` blocks (`vision_compare.py`, `description.py`, `scoring_service.py`). Sidecars are not temporary files; deleting them is data loss and can break Lightroom workflows. The same mistaken pattern exists elsewhere (e.g. `vision_cache.py`, not in the phase file list).  
**Fix:** Distinguish **managed temp paths** from **borrowed persistent paths**. For example: return `(path, dispose: Literal["noop","unlink"])` or a small dataclass from `get_viewable_path`, or only append paths created by `convert_raw_to_jpg` / `compress_image` (mkstemp outputs). Never unlink when the viewable path is an on-disk sidecar next to the RAW.

---

### WR-002 (warning): `_model_min_tokens` keyed by model id only
**File:** `lightroom_tagger/core/analyzer/vision_compare.py:19`, `176-210`  
**Issue:** Cached minimum `max_tokens` is stored under `_model_min_tokens[mdl]` while `_broken_provider_models` uses `"provider_id:model"` (`provider_key`). If the same model id string is configured on two providers with different behavior, the shared cache can skip needed escalation or apply the wrong minimum.  
**Fix:** Key `_model_min_tokens` the same way as `_broken_provider_models` (e.g. `f"{provider_id}:{mdl}"`) inside `_compare_via_provider`’s closure.

---

### WR-003 (warning): `matcher` package barrel exports implementation details
**File:** `lightroom_tagger/core/matcher/__init__.py:28-51`  
**Issue:** `__all__` includes `os`, `Callable`, and multiple private-ish symbols (`_call_batch_chunk`, `_compute_desc_scores_for_candidates`). That blurs the intended public API of a “service module” boundary and invites unstable imports by downstream code.  
**Fix:** Trim `__all__` (and omit `os` / `typing.Callable`) to stable, documented entry points; keep helpers internal or expose them via explicit submodule imports.

---

### WR-004 (warning): `identity_service` depends on private `_EN_STOPWORDS`
**File:** `lightroom_tagger/core/identity_service/aggregates.py:9`  
**Issue:** Imports `_EN_STOPWORDS` from `lightroom_tagger.core.posting_analytics`, which is a private convention (`_`). Any rename or refactor of posting analytics silently breaks identity aggregation.  
**Fix:** Move stopwords to a small shared module (e.g. `lightroom_tagger/core/text_constants.py`) or expose a documented symbol on `posting_analytics`.

---

### IN-005 (info): Unused `active_count` parameter
**File:** `lightroom_tagger/core/identity_service/aggregates.py:42` (function `_default_min_perspectives`)  
**Issue:** The parameter `active_count` is never used; the function always returns `1`. This is misleading for readers expecting coverage rules to vary with perspective count.  
**Fix:** Prefix with `_active_count` and document “reserved for future policy”, or implement the intended rule from design docs (D-40).

---

### IN-006 (info): Very broad exception handling masks failures
**File:** `lightroom_tagger/core/analyzer/image_inspect.py:9-31`  
**Issue:** `compute_phash` and `extract_exif` catch bare `Exception` and return `None` / `{}` without logging. Silent failure makes diagnosing corrupt files or dependency issues harder.  
**Fix:** Narrow exceptions, log at debug, or propagate as domain errors where callers can react.

---

### IN-007 (info): Tool-result logging may expose catalog snippets
**File:** `lightroom_tagger/core/nl_catalog_search.py:329-330`  
**Issue:** `log_callback("tool_result", f"...{result_str[:200]}")` can write fragments of structured search results (paths, captions, rationales) into logs — low risk locally but inconsistent with minimizing sensitive data in shared logs.  
**Fix:** Log tool name + hash/count only, or gate verbose logging behind a debug flag.

---

### IN-008 (info): Line-budget tests differ subtly from `wc -l`
**File:** `lightroom_tagger/core/test_architecture.py:11-14` vs `docs/architecture.md` / `scripts/check_core_file_sizes.sh`  
**Issue:** `_line_count()` treats a file missing a final newline differently from `wc -l`. Rare edge case; CI could disagree with the shell script on an odd-terminated file.  
**Fix:** Align with `wc -l` (e.g. `len(path.read_text(...).splitlines())` semantics) or document the deviation.
