---
phase: 15
slug: service-modules-boundary-policy
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-06
validated: 2026-05-06
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Plan cross-links: [15-01](./15-01-PLAN.md) · [15-02](./15-02-PLAN.md) · [15-03](./15-03-PLAN.md) · [15-04](./15-04-PLAN.md) · [15-05](./15-05-PLAN.md) · [15-06](./15-06-PLAN.md) · [15-07](./15-07-PLAN.md).

---

## Test infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run (core)** | `pytest lightroom_tagger/core/ -x -q` |
| **Architecture + size gate (post–15-07-T04/T03)** | `pytest lightroom_tagger/core/test_architecture.py -x -q` · `bash scripts/check_core_file_sizes.sh` |
| **Full suite command** | `pytest -x -q` |
| **Estimated runtime** | ~30 seconds (full suite; varies with machine) |

---

## Sampling rate

- **After every task (plans 15-01–15-06):** Run the **Automated Command** for that task in the [Per-Task Verification Map](#per-task-verification-map). If none listed, default to `pytest lightroom_tagger/core/ -x -q`; when a plan’s verification block names `apps/visualizer/backend/tests/`, include that scope.
- **After 15-07-T03:** `bash scripts/check_core_file_sizes.sh` (script added in this task).
- **After 15-07-T04:** `pytest lightroom_tagger/core/test_architecture.py -x -q` (line budget + import rules, including D-06 api sibling rule).
- **After every plan wave:** `pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green; architecture test and size script must pass once 15-07 has landed.
- **Max feedback latency:** ~30 seconds where possible

---

## Per-task verification map

| Task ID | Plan | Wave | Requirement | Test type | Automated command |
|---------|------|------|-------------|-----------|-------------------|
| 15-01-T01 | 15-01 | 1 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_provider_errors.py -x -q` · `python -c "from lightroom_tagger.core.exceptions import ProviderError, RateLimitError, RETRYABLE_ERRORS"` |
| 15-01-T02 | 15-01 | 1 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_database_stacks.py -x -q` · `python -c "from lightroom_tagger.core.database import StackMutationError; from lightroom_tagger.core.exceptions import StackMutationError as E; assert StackMutationError is E"` |
| 15-01-T03 | 15-01 | 1 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_provider_errors.py lightroom_tagger/core/test_fallback.py lightroom_tagger/core/test_retry.py lightroom_tagger/core/test_vision_client.py -x -q` · `pytest lightroom_tagger/core/ -x -q` |
| 15-02-T01 | 15-02 | 2 | REFACTOR-04 | unit | `python -c "from lightroom_tagger.core.config import get_vision_model, get_description_model; from lightroom_tagger.core.analyzer import get_vision_model as gv2; assert gv2 is get_vision_model"` |
| 15-02-T02 | 15-02 | 2 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_matcher.py lightroom_tagger/core/test_analyzer.py lightroom_tagger/core/test_description_service.py -x -q` |
| 15-03-T01 | 15-03 | 3 | REFACTOR-04 | checklist | `test -f .planning/phases/15-service-modules-boundary-policy/15-03-SUMMARY.md` · confirm symbol list per 15-03-T01 acceptance |
| 15-03-T02 | 15-03 | 3 | REFACTOR-04 | unit | `python -c "from lightroom_tagger.core.analyzer import compress_image, compute_phash, compare_with_vision, describe_image, get_vision_model"` · `pytest lightroom_tagger/core/test_analyzer.py -x -q` |
| 15-04-T01 | 15-04 | 3 | REFACTOR-04 | unit | `python -c "from lightroom_tagger.core.analyzer.image_prep import RAW_EXTENSIONS, compress_image; from lightroom_tagger.core.analyzer.image_inspect import compute_phash"` · `pytest lightroom_tagger/core/test_analyzer.py -x -q` |
| 15-04-T02 | 15-04 | 3 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_analyzer.py lightroom_tagger/core/test_vision_client.py -x -q` |
| 15-04-T03 | 15-04 | 3 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_analyzer.py -x -q` |
| 15-04-T04 | 15-04 | 3 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_scoring_service.py lightroom_tagger/core/ -x -q` (fallback: `pytest lightroom_tagger/core/ -x -q` if no `test_scoring_service.py`) |
| 15-04-T05 | 15-04 | 3 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_analyzer.py -x -q` · `rg '\banalyze_image\b' lightroom_tagger apps --glob "*.py"` → no matches |
| 15-04-T06 | 15-04 | 3 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/ -x -q` · `python -c "from lightroom_tagger.core.analyzer import compress_image, compute_phash, compare_with_vision, describe_image, get_vision_model"` |
| 15-05-T01 | 15-05 | 4 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_matcher.py -x -q` · `python -c "from lightroom_tagger.core.matcher import score_candidates_with_vision, find_candidates_by_date, match_image"` |
| 15-05-T02 | 15-05 | 4 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_matcher.py -x -q` |
| 15-05-T03 | 15-05 | 4 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_matcher.py -x -q` |
| 15-05-T04 | 15-05 | 4 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_matcher.py -x -q` |
| 15-05-T05 | 15-05 | 4 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/ -x -q` · `python -c "from lightroom_tagger.core.matcher import match_batch, score_candidates_with_vision"` |
| 15-06-T01 | 15-06 | 5 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_identity_service.py -x -q` · `python -c "from lightroom_tagger.core.identity_service import rank_best_photos, build_style_fingerprint, suggest_what_to_post_next"` |
| 15-06-T02 | 15-06 | 5 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/test_identity_service.py -x -q` |
| 15-06-T03 | 15-06 | 5 | REFACTOR-04 | unit | `pytest lightroom_tagger/core/ apps/visualizer/backend/tests/ -x -q` |
| 15-07-T01 | 15-07 | 6 | REFACTOR-04, REFACTOR-05 | doc | `test -f docs/architecture.md` · headings per 15-07-T01 acceptance |
| 15-07-T02 | 15-07 | 6 | REFACTOR-04, REFACTOR-05 | config | `grep -F "# Module boundary policy: docs/architecture.md (max file size, import layers)." pyproject.toml` |
| 15-07-T03 | 15-07 | 6 | REFACTOR-04, REFACTOR-05 | script | `bash scripts/check_core_file_sizes.sh` |
| 15-07-T04 | 15-07 | 6 | REFACTOR-04, REFACTOR-05 | arch | `pytest lightroom_tagger/core/test_architecture.py -x -q` |
| 15-07-T05 | 15-07 | 6 | REFACTOR-04, REFACTOR-05 | integration | `make check-core-sizes` (runs `bash scripts/check_core_file_sizes.sh`) |

*REFACTOR-05 traceability:* automated enforcement in this phase is the **shell size gate** + **`test_architecture.py`** (see 15-07, **15-07-T03–T04**). **CI (GitHub Actions) wiring is deferred** until `.github/workflows` exists — see [15-07-PLAN.md](./15-07-PLAN.md) Must-Haves.

---

## Wave 0 and enforcement artifacts

Frontmatter **`wave_0_complete: false`** and **`nyquist_compliant: false`** stay **false** until [Validation sign-off](#validation-sign-off) completes.

**Baseline (repo from phase start):** pytest configuration in `pyproject.toml`; use core-scoped runs via the map above.

**Not** available until **wave 6 / plan 15-07:**

| Artifact | Introduced |
|----------|------------|
| `scripts/check_core_file_sizes.sh` | **15-07-T03** (`check_sizes.sh` is not used) |
| `lightroom_tagger/core/test_architecture.py` | **15-07-T04** |

Until those tasks land, omit `bash scripts/check_core_file_sizes.sh` and `pytest …/test_architecture.py` from post-commit sampling.

---

## Manual-only verifications

| Behavior | Requirement | Why manual | Test instructions |
|----------|-------------|------------|-------------------|
| Barrel re-exports preserve caller import paths | REFACTOR-04 | Wide import surfaces | `python -c "import lightroom_tagger.core.analyzer as a; …"` — spot-check expected public names |
| Legacy retirements (`analyze_image`, etc.) | REFACTOR-04 | Indirect call chains | `rg "analyze_image|run_local_agent|run_vision_ollama" lightroom_tagger apps --glob "*.py"` → zero hits when phase complete |

---

## Validation sign-off

- [x] All tasks have an automated command in the map above (or explicit manual-only row)
- [x] Sampling continuity: architecture/size checks run only after **15-07-T03/T04**
- [x] No watch-mode flags
- [x] Feedback latency ~30s where practical
- [x] `nyquist_compliant: true` and `wave_0_complete: true` set in frontmatter

**Approval:** 2026-05-06 — validated by gsd-validate-phase audit

---

## Validation Audit 2026-05-06

| Metric | Count |
|--------|-------|
| Tasks audited | 25 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Status | NYQUIST-COMPLIANT ✓ |

**Evidence collected:**

| Check | Result |
|-------|--------|
| `pytest` 25 core test files (test_provider_errors, test_database_stacks, test_fallback, test_retry, test_vision_client, test_matcher, test_analyzer, test_description_service, test_scoring_service, test_identity_service, test_architecture) | 133 passed ✓ |
| All import-level checks (exceptions, config, analyzer, matcher, identity_service) | All OK ✓ |
| `pytest lightroom_tagger/core/ apps/visualizer/backend/tests/ -x -q` | 611 passed ✓ |
| `pytest lightroom_tagger/core/test_architecture.py -x -q` | 3 passed ✓ |
| `bash scripts/check_core_file_sizes.sh` | exits 0 ✓ |
| `make check-core-sizes` | exits 0 ✓ |
| `docs/architecture.md` exists with required headings + flowchart + 400-line rule + sibling api rule | All present ✓ |
| `pyproject.toml` boundary policy comment above `[tool.ruff]` | Found ✓ |
| Legacy symbol scan (`analyze_image`, `run_local_agent`, `run_vision_ollama`) | Zero hits ✓ |
| `15-03-SUMMARY.md` checklist file | Exists ✓ |
