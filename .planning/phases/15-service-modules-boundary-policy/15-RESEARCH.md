# Phase 15: Service modules & boundary policy — Research

## Summary

- **`matcher.py` and `identity_service.py`** each expose a small set of top-level `def`s (no classes). The bulk of line count is in **`score_candidates_with_vision`** (~453 lines, including nested `_score_and_store`) and in **`suggest_what_to_post_next`** (~190 lines). Splits should isolate **candidate discovery**, **lightweight phash/text scoring**, **vision+batch scoring**, and **high-level match orchestration** for matcher; and **score aggregation**, **ranking/stack enrichment**, **style fingerprint**, and **post-next suggestions** for identity.
- **Phase 14 scaffold** is proven: move the monolith to **`_legacy.py`**, add a **barrel `__init__.py`** with explicit `from ._legacy import (...)` (no star exports), fix **path depth** when code used `Path(__file__).parents[k]` (database seed paths). Analyzer has **no `__file__` anchors** today — lower risk than database.
- **Retirement of `analyze_image`, `run_local_agent`, `run_vision_ollama`** is **not** delete-and-go: multiple **production** call sites still use `analyze_image`; **`scoring_service`** and **`describe_image(..., provider_id=None)`** still use **`run_local_agent`**; **`compare_with_vision`** calls **`run_vision_ollama`** whenever **`provider_id is None`**. Safe sequence: route all paths through **`_describe_image_via_provider` / `_compare_via_provider`** (default provider from `ProviderRegistry`), then delete legacy functions and refresh tests.
- **`exceptions/` (ADR-0004)** should land early: **`provider_errors`** is imported from **15+** production modules; **`StackMutationError`** now lives in **`lightroom_tagger/core/database/stacks.py`** and is barrel-exported from **`database/__init__.py`** — moving it to **`exceptions/db_errors.py`** requires re-exports from **`database`** (and **`api/images/stacks.py`**) so external import surfaces stay stable during transition.
- **CI**: there is **no `.github/workflows/`** in this repo today; **`Makefile`** only wraps dev scripts. A dedicated **`scripts/check_core_file_sizes.sh`** (or similar) keeps the gate portable; **`pytest`** in **`lightroom_tagger/core/test_architecture.py`** duplicates the line budget with **import-graph** rules for regression safety.
- **`pipelines.py` (ADR-0003)** is **not present** in the tree yet — boundary documentation should describe the **target** handler → pipeline → service model without assuming `pipelines.py` exists today.

## Function Inventory: matcher.py

**File size:** 747 lines (`wc -l`).

| Name | Kind | Approx. role | Proposed submodule / grouping |
|------|------|--------------|------------------------------|
| `query_by_exif` | public | Catalog lookup by EXIF camera/lens | **`candidates.py`** (or `candidate_query.py`) — “find catalog rows” |
| `find_candidates_by_date` | public | Date-window SQL + join `image_descriptions` for `ai_summary`, filters `VIDEO_EXTENSIONS` | Same as **`candidates.py`** |
| `text_similarity` | public | Jaccard-like word overlap | **`text_scores.py`** (or `classic_scoring.py`) — shared by `score_candidates` / vision path |
| `score_candidates` | public | Phash + description similarity, no vision | Same as **`text_scores.py`** |
| `BATCH_MAX_TOKENS_ESCALATION` | const | Vision batch token escalation ladder | **`vision_batch.py`** (next to `_call_batch_chunk`) |
| `_compute_desc_scores_for_candidates` | private | Description batch via `compare_descriptions_batch` + `ProviderRegistry` | **`description_batch.py`** or **`vision_scoring.py`** |
| `_call_batch_chunk` | private | `compare_images_batch` + `PayloadTooLargeError` split / `ContextLengthError` escalation | **`vision_batch.py`** |
| `score_candidates_with_vision` | public | Main orchestration: desc scores, Instagram compress, batch path, sequential fallback, cache/DB writes, logging | **`score_with_vision.py`** (largest file; nested `_score_and_store` stays here or becomes a module-private helper) |
| `match_image` | public | `query_by_exif` → `score_candidates_with_vision` → `store_match` | **`matching.py`** (high-level “single image”) |
| `match_batch` | public | Loop over `match_image` | Same as **`matching.py`** |

**Cross-cutting extraction (15-CONTEXT D-02 “aggressive”):**

- **Path prep inside `score_candidates_with_vision`** (UNC `//…` → `/Volumes/…`, `mount_point` join, existence checks) is a strong candidate for **`path_utils.py`** (alongside `resolve_catalog_path`) to shrink **`score_with_vision.py`** and avoid duplicating NAS/UNC rules later.
- **`get_vision_model()`** imports inside matcher should follow ADR-0001 and call **`config.get_vision_model()`** once that move is done.

## Function Inventory: identity_service.py

**File size:** 697 lines.

**Module-level bindings:** `_SCORES_BASE_SQL`, `_WORD_RE`, `_RATIONALE_PREVIEW_MAX`.

| Name | Kind | Approx. role | Proposed submodule / grouping |
|------|------|--------------|------------------------------|
| `_active_perspective_slugs` | private | List active perspective slugs | **`aggregates.py`** (or `sql_support.py` if you prefer thin query constants separated) |
| `_default_min_perspectives` | private | Coverage floor | **`aggregates.py`** |
| `_tokenize_rationale` | private | D-43 rationale tokenization | **`aggregates.py`** or **`rationale_tokens.py`** if reused elsewhere |
| `_truncate_rationale` | private | Preview truncation | **`aggregates.py`** |
| `compute_image_aggregate_scores` | public | Full catalog aggregate pass + meta | **`aggregates.py`** |
| `compute_single_image_aggregate_scores` | public | Single-key aggregate | **`aggregates.py`** |
| `_image_meta_map` | private | Merge catalog + Instagram dump metadata for key lists | **`ranking.py`** (enrichment for ranking/suggestions) |
| `_stack_non_representative_keys` | private | Filter non-representative stack members | **`ranking.py`** |
| `_stack_fields_for_image_keys` | private | Stack fields for API rows | **`ranking.py`** |
| `rank_best_photos` | public | Eligible-only sort, posted filter, pagination | **`ranking.py`** |
| `_aggregate_histogram` | private | Score histogram for fingerprint | **`style_fingerprint.py`** |
| `build_style_fingerprint` | public | Catalog-wide fingerprint (D-42) | **`style_fingerprint.py`** |
| `_posted_catalog_keys_sql` | private | Posted key set SQL (validated + flag) | **`suggest_post.py`** |
| `suggest_what_to_post_next` | public | Unposted suggestions + cadence + theme heuristics | **`suggest_post.py`** |

**Note:** `suggest_what_to_post_next` depends on **`posting_analytics.get_posting_frequency`**; keep that import at the **package edge** (barrel or `suggest_post.py` only) to avoid cycles.

## Phase 14 Scaffold Pattern

**Exact sequence (from `14-01-SUMMARY.md` + plan artifacts):**

1. **Baseline** — Count / record top-level symbols on the monolith (`grep` / AST).
2. **Create package directory** — Same pattern as Phase 14: replace flat `analyzer.py` with package `analyzer/` whose monolith lives in `analyzer/_legacy.py` (no `analyzer.py` file beside the `analyzer/` directory — Python resolves the package).
3. **Stub submodules** — One-line docstring files for each planned domain file (optional but used in Phase 14 for clarity).
4. **Barrel `__init__.py`** — Explicit `from ._legacy import (` … `)` listing every exported name; maintain **`__all__`**.
5. **Green test run** after scaffold — full `pytest lightroom_tagger/core/` (or whole suite) before migrating bodies out of `_legacy`.

**Pitfalls observed:**

- **`Path(__file__).parents[k]` drift** — Nesting `_legacy` one level deeper broke default seed paths until `parents[3]` fix (`14-01-SUMMARY.md`). Re-run any analyzer-relative path logic after package creation (analyzer currently has **no** such usage).
- **Barrel completeness** — Phase 14 exported **128** names including “private” module binds to avoid accidental gaps; Phase 15 should match that discipline for **`analyzer`**, **`matcher`**, **`identity_service`** barrels until intentional API narrowing is agreed.
- **Circular imports** — `_legacy` holds everything until subgraphs move; when moving code, import **from leaf modules into `_legacy`** only during transition, or delete `_legacy` incrementally per ADR-0001 style (analyzer may migrate off `_legacy` faster than database did).

## Shared Utilities Absorption Map

| Helper / concern today | Absorption target | Notes |
|------------------------|-------------------|-------|
| `get_vision_model`, `get_description_model` | **`config.py`** | ADR-0001; update **`vision_client`**, **`matcher`**, **`scoring_service`**, **`description_service`**, scripts |
| `compress_image`, `get_viewable_path`, extensions | **`analyzer/image_prep.py`** (barrel re-exports `analyzer`) | Already used by **`vision_cache`** |
| `compute_phash`, `extract_exif` | **`analyzer/image_inspect.py`** | |
| `build_description_prompt`, `parse_description_response` | **`description.py`** + **`vision_client`** may import from there | Today **`vision_client`** imports these from **`analyzer`** |
| UNC / mount batch path normalization inside matcher | **`path_utils.py`** | New funcs e.g. `normalize_catalog_candidate_path(local_path, mount_point)` — keep DB-free or inject `resolve_filepath` if needed |
| Provider error imports | **`lightroom_tagger.core.exceptions`** | After ADR-0004 migration |

**`path_utils.py` today:** only `resolve_catalog_path` (delegates to `database.resolve_filepath`). It is the right **semantic home** for “make a disk path we can open” helpers.

**`config.py` today:** `Config` dataclass, `load_config`, YAML updaters — no `get_vision_model` yet; those functions currently live **only** in **`analyzer.py`** (lines ~21–40).

## Caller Analysis

### `lightroom_tagger.core.analyzer`

| Area | Callers |
|------|---------|
| **Vision / describe surface** | `vision_client.py` (`build_description_prompt`, `parse_vision_response`), `scoring_service.py` (`compress_image`, `get_viewable_path`, `get_description_model`, `run_local_agent`, `VIDEO_EXTENSIONS`), `description_service.py` (`VIDEO_EXTENSIONS`, `describe_image`, `get_description_model`), `vision_cache.py` (`compress_image`, `compute_phash`, `get_viewable_path`) |
| **Matching** | `matcher.py` (`get_vision_model`, `compare_with_vision`, `vision_score`, `VIDEO_EXTENSIONS`) |
| **Jobs** | `apps/visualizer/backend/jobs/handlers/analyze.py` (`VIDEO_EXTENSIONS`), `handlers/matching.py` (**` analyze_image`**) |
| **Scripts / library** | `cli.py`, `scripts/analyze_instagram_images.py`, `scripts/match_instagram_dump.py`, `scripts/run_vision_matching.py`, `scripts/test_subset_matching.py` |
| **Packages** | `lightroom/enricher.py`, `instagram/crawler.py` (**`analyze_image`**) |
| **Tests** | `core/test_analyzer.py` (broad surface) |

### `lightroom_tagger.core.matcher`

| Area | Callers |
|------|---------|
| **Scripts** | `scripts/match_instagram_dump.py`, `scripts/benchmark_clip_recall.py` |
| **Tests** | `core/test_matcher.py` |

**No** `apps/visualizer/backend/api/*` imports matcher directly in the grep sweep — matching flows likely go through **handlers / pipelines / scripts** (confirm during implementation if a thin API module appears).

### `lightroom_tagger.core.identity_service`

| Area | Callers |
|------|---------|
| **Visualizer API** | `apps/visualizer/backend/api/identity.py` (`build_style_fingerprint`, `rank_best_photos`, `suggest_what_to_post_next`), `api/images/catalog.py` (`compute_single_image_aggregate_scores`) |
| **Tests / core** | `core/test_identity_service.py`, `core/test_database_stacks.py` (`rank_best_photos`) |

## Retirement Analysis

### `analyze_image`

**Active callers (non-test, non-doc):**

- `apps/visualizer/backend/jobs/handlers/matching.py`
- `lightroom_tagger/cli.py`
- `lightroom_tagger/scripts/analyze_instagram_images.py`
- `lightroom_tagger/lightroom/enricher.py`
- `lightroom_tagger/instagram/crawler.py`

**Tests:** `core/test_analyzer.py::test_analyze_image_returns_all_signals`.

**Safe removal sequence:**

1. Introduce a **small composed helper** (in `analyzer` package or `description_service`) that implements the same contract: `compute_phash`, `extract_exif`, `describe_image` with an explicit **default provider** (per registry / config), **not** `agent_type='local'` + `run_local_agent`.
2. **Migrate each caller** to the helper (or inline the three calls with explicit provider).
3. **Deprecate** `analyze_image` in barrel (optional `warnings.warn` one release) or remove immediately once call count is zero.
4. **Rewrite test** to assert the composed pipeline with mocked provider / patched `describe_image` path.

### `run_local_agent`

**Active callers:**

- `lightroom_tagger/core/scoring_service.py` — **production** legacy path when provider scaffolding differs from describe pipeline
- `describe_image` when `provider_id is None` and `agent_type == 'local'` (see `analyzer.py`)
- `lightroom_tagger/core/test_analyzer.py`

**Removal sequence:** migrate **`scoring_service`** to **`_describe_image_via_provider`-style** (or shared “text generation with fixer” via `vision_client`) so **no** code path calls `ollama.chat` directly from `analyzer`; then delete `run_local_agent` and tests that patch it.

### `run_vision_ollama`

**Active callers:**

- `compare_with_vision` when **`provider_id is None`** (`analyzer.py` ~553–554) — **implicitly** all sequential vision matching that doesn’t pass a provider
- `lightroom_tagger/core/test_analyzer.py`

**Removal sequence:** change **`compare_with_vision`** default to **`ProviderRegistry`** default provider (same as `_compare_via_provider` with resolved `provider_id`), **removing the `None` → Ollama shortcut**; update tests to mock **`vision_client.compare_images`** / provider stack instead of `run_vision_ollama`. Only then delete `run_vision_ollama`.

## test_architecture.py Implementation

**Goals (from `15-CONTEXT.md` D-06):**

1. **Line budget** — every tracked file under an agreed set (e.g. `lightroom_tagger/core/**/*.py` excluding tests?) has **≤ 400** lines — **mirror** the shell check policy exactly to avoid drift.
2. **Import rules** — e.g. `apps/visualizer/backend/api/**/*.py` must not import sibling `api` packages via internal absolute paths; `lightroom_tagger/core/*.py` (and subpackages?) must not import `apps.visualizer…`.

**Practical patterns (stdlib-only):**

- **AST walk:** `pathlib.Path.rglob("*.py")` → `ast.parse` → visit `ast.Import` / `ast.ImportFrom` → record `module` string and `level` (relative). Filter by path prefix to assign layer (`api` vs `core`).
- **Rule examples:**
  - For each file under `apps/visualizer/backend/api/`, if any `ImportFrom` targets `api.` or same-package sibling inconsistent with policy, fail.
  - For each file under `lightroom_tagger/core/`, fail if module string starts with `apps.` or `api.` (stricter: forbid `flask` in `core/` except allowlist — only if desired).
- **Line counts:** `path.read_text().count("\n") + 1` or `sum(1 for _ in open(...))` — **exclude** `__init__.py` only if policy says so (`15-CONTEXT` D-06 mentions `wc -l` on `core/*.py`; clarify whether **barrel files** are exempt — recommendation: **barrels count** toward limit or keep barrels **thin** so they stay <400 either way).

**Fixture strategy:** parametrize root paths (`REPO / "apps/visualizer/backend/api"`, `REPO / "lightroom_tagger/core"`) so CI failures name the violating file and rule.

## CI Size Check

| Option | Pros | Cons |
|--------|------|------|
| **`scripts/check_core_file_sizes.sh`** | Works without GitHub; same command locally; easy to add to future workflow | Needs discipline to invoke in CI |
| **`Makefile` target** | One-liner for contributors | Makefile is currently minimal — acceptable to extend |
| **GitHub Actions** | Visible PR gate | **No** `.github/` yet — add when remote CI is wired |

**Recommended:** `scripts/check_core_file_sizes.sh` exiting non-zero on violation, **≤ 400 lines** per `15-CONTEXT`, scanning `lightroom_tagger/core/**/*.py` **excluding** tests (`**/test_*.py`, `**/tests/**`) and optionally **excluding** `**/__init__.py` **only** if barrels are allowed to exceed (better: **keep barrels under 400** with explicit re-export lists).

**Implementation sketch:**

```bash
find lightroom_tagger/core -name '*.py' ! -name '__init__.py' ! -name 'test_*.py' -print0 | xargs -0 wc -l | awk '$1 > 400 { print "FAIL", $0; exit 1 }'
```

Tune globs to match **`test_architecture.py`** expectations.

## exceptions/ Migration Sequence

**Current state:**

- **`lightroom_tagger/core/provider_errors.py`** — canonical implementation today; heavily imported.
- **`StackMutationError`** — **defined in** `lightroom_tagger/core/database/stacks.py`; **re-exported** from `database/__init__.py`. **`apps/visualizer/backend/api/images/stacks.py`** imports **`StackMutationError`** from **`lightroom_tagger.core.database`**.

**Safe step-by-step:**

1. **Create package** `lightroom_tagger/core/exceptions/` with `provider_errors.py` — **move** class definitions from `core/provider_errors.py` (copy-paste preserving `__all__` / retry tables).
2. **`exceptions/db_errors.py`** — define **`StackMutationError`** (or re-export from a single migration step: cut-paste class from `stacks.py` into `db_errors.py`, then **`stacks.py`** does `from lightroom_tagger.core.exceptions import StackMutationError` / `from lightroom_tagger.core.exceptions.db_errors import StackMutationError` — ADR says callers use **`core.exceptions` only**, so **`stacks.py`** should import from the **public** `exceptions` package root re-export).
3. **`exceptions/__init__.py`** — re-export full provider hierarchy + `StackMutationError`.
4. **Shim** `lightroom_tagger/core/provider_errors.py` → `from lightroom_tagger.core.exceptions import *` / explicit names (temporary).
5. **`database/__init__.py`** — continue exporting **`StackMutationError`** by importing from **`lightroom_tagger.core.exceptions`** (stability for `from lightroom_tagger.core.database import StackMutationError`).
6. **Bulk-update imports** (optional second commit): `rg` replace `lightroom_tagger.core.provider_errors` → `lightroom_tagger.core.exceptions` in `core/`, `apps/visualizer/`, `scripts/`.
7. **Remove shim** `core/provider_errors.py` once grep is clean.
8. **Tests:** run `pytest lightroom_tagger/core/test_provider_errors.py` + stacks / API tests unchanged.

**Ordering with splits:** do this **before** splitting `analyzer`/`matcher` so new submodules import **`core.exceptions`** once instead of touching every file twice.

## Recommended Wave Sequence

| Wave | Work | Rationale |
|------|------|-----------|
| **1** | **`exceptions/` package** + shims (`provider_errors`, `database` re-export) | Single new import root; reduces churn in later waves; satisfies **`15-CONTEXT` “prerequisite”** |
| **2** | **`config.py`** gains **`get_vision_model` / `get_description_model`**; **`analyzer.py`** calls into config | **Matcher / vision_client / scoring_service** can drop direct circular reliance on monolithic `analyzer` for model names |
| **3** | **`analyzer/` package** per ADR-0001 + **retire legacy** (`analyze_image` migration, `compare_with_vision` default provider, **`scoring_service` / describe** off `run_local_agent`) | **Largest dependency hub**; **`vision_client`**, **`matcher`**, **`vision_cache`** all depend on it |
| **4** | **`matcher/` package** + path helper extraction | Imports **`analyzer`** barrel and **`config`**; should follow stable analyzer surface |
| **5** | **`identity_service/` package** | Mostly **`database` + posting_analytics**; few analyzer ties — lowest cross-module coupling |
| **6** | **`docs/architecture.md`**, **`pyproject.toml`** comments, **`scripts/check_core_file_sizes.sh`**, **`test_architecture.py`** | Enforcement last so rules match **post-split** tree |

**Note:** If **`analyzer`** retirement drags, **split mechanically** first with `_legacy` + barrel, then **land retirements** in the same phase — still **green tests between commits**.

## Validation Architecture

**Commands:**

- `wc -l` / size script — fails on any offending file.
- `pytest lightroom_tagger/core/test_architecture.py -v` — line + import graph rules.
- `pytest lightroom_tagger/core/` — baseline parity (`14-01` cited **269** core tests; project baseline **663** backend tests in `REQUIREMENTS.md` — re-verify current count in CI).
- `pytest apps/visualizer/backend/tests/` — API + handler integration.
- Smoke imports: `python -c "from lightroom_tagger.core.analyzer import …"` / `matcher` / `identity_service` — same symbols as pre-split checklist.

**Grep checks:**

- `rg "run_vision_ollama|run_local_agent|^def analyze_image" lightroom_tagger` — **zero** definitions (or only shims) after retirement complete.
- `rg "from lightroom_tagger\.core\.provider_errors"` — **zero** after migration (or only shim file).
- `rg "lightroom_tagger/core/analyzer\.py"` in docs — update paths to **`analyzer` package**.

**File existence:**

- `lightroom_tagger/core/exceptions/__init__.py`, `docs/architecture.md`, `scripts/check_core_file_sizes.sh` (or chosen name).

## RESEARCH COMPLETE
