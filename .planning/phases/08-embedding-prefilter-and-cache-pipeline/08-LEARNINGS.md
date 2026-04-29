---
phase: 8
phase_name: "embedding-prefilter-and-cache-pipeline"
project: "Lightroom Tagger & Analyzer"
generated: "2026-04-29"
counts:
  decisions: 7
  lessons: 5
  patterns: 6
  surprises: 3
missing_artifacts: []
---

# Phase 8 Learnings: Embedding Pre-filter & Catalog Cache Pipeline

## Decisions

### Gate the entire scoring stack behind CLIP shortlist, not just LLM vision
The CLIP cosine shortlist gates phash, description, and visual LLM judgment — all three scoring stages run only on the shortlisted candidates.

**Rationale:** Description scoring is itself LLM-driven. Gating only the visual LLM pass would not deliver the intended cost reduction; the shortlist must prevent all downstream scoring work for the full speedup to materialise.
**Source:** 08-CONTEXT.md (D-03)

---

### Omit `clip_top_k` from fingerprint JSON when value is the default (50)
When `clip_top_k` equals 50, the key is excluded from the checkpoint fingerprint canonical JSON so in-flight checkpoints from pre-Phase-8 builds still match and can resume correctly.

**Rationale:** Fingerprint divergence would orphan all live jobs at deploy time. Conditional omission is a zero-cost backward-compat guarantee — the handler reads the fingerprint, sees no top-k key, and uses 50 as the default.
**Source:** 08-02-SUMMARY.md, 08-CONTEXT.md (D-02)

---

### Run the catalog cache chain as one composite in-process handler, not via dependent job enqueues
`catalog_cache_build` is a single composite handler that runs embed → stack_detect → catalog_similarity in-process with `_CatalogCacheStageRunner` proxying progress and cancel checks between stages.

**Rationale:** Sequential enqueues would require polling + dependency tracking, complicate cancel propagation, and produce three separate job rows. A single in-process chain gives clean cancel-between-stages semantics, one job row, and one progress bar mapped in thirds.
**Source:** 08-04-SUMMARY.md, 08-CONTEXT.md (D-04)

---

### Warn-and-proceed when prior embedding stage has incomplete backlog
After the embed stage, if any catalog or Instagram keys are still missing CLIP embeddings, log a `warning=incomplete_embeddings count=N proceeding` entry and continue into stack_detect rather than aborting.

**Rationale:** Aborting downstream stages because a handful of images failed to embed is more harmful than running stack/similarity with a slightly incomplete embedding set. Observable warnings make the gap operator-visible without preventing the rest of the pipeline from completing.
**Source:** 08-04-SUMMARY.md, 08-CONTEXT.md (Claude's Discretion)

---

### Drop MATCH-03 wider-search fallback from scope
The empty-shortlist fallback (MATCH-03) was removed from Phase 8 scope on 2026-04-27.

**Rationale:** MATCH-03 was introduced by Claude during requirements drafting, not user-requested. Delivering it without validation that empty-shortlist cases are a real problem would be premature complexity. The fallback is deferred pending Phase 8 verification data.
**Source:** 08-CONTEXT.md (Deferred section)

---

### Move stack-detect and catalog-similarity UI triggers from MatchingTab to CatalogCacheTab
Stack-detect and catalog-similarity CTAs were removed from `MatchingTab` and become Advanced disclosure actions on `CatalogCacheTab`.

**Rationale:** These operations are catalog maintenance work, not per-match configuration. Consolidating them under the catalog cache surface reduces cognitive load on the matching workflow and makes the semantic grouping accurate.
**Source:** 08-CONTEXT.md (D-06), 08-05-SUMMARY.md

---

### Store `clip_top_k` draft as a digits-only string with blur-time clamping
MatchingTab stores the top-k field as a digit-filtered string during editing; the blur handler coerces empty or out-of-range input back to 1..500 before sending to `JobsAPI.create`.

**Rationale:** Controlled numeric input without a native `type=number` spinner avoids cross-browser quirks and gives the user live digit validation while keeping a clean integer in the job payload. Empty input defaults to 50 rather than NaN.
**Source:** 08-05-SUMMARY.md

---

## Lessons

### Full-table Python `set` materialisation inside a DB helper is a scalability anti-pattern
`list_instagram_dump_keys_needing_clip_embedding` initially loaded the entire `image_clip_embeddings` table into a Python `set` to compute the backlog, then scanned dump rows in Python. This is O(N) memory and CPU per call and would spike on large catalogs.

**Context:** The code review (WR-08-02) caught this before it caused production issues. Fix: replace the Python set with an SQL `LEFT JOIN … WHERE ce.image_key IS NULL` anti-join, which pushes the work into SQLite's indexed query engine.
**Source:** 08-REVIEW.md (WR-08-02), 08-REVIEW-FIX.md

---

### Removing a job's result surface requires adding a replacement in the same phase
Phase 8 removed `CatalogSimilarityGroupsPreview` from `MatchingTab` but did not add a replacement on `CatalogCacheTab`. This violated the `job-ui-contract.mdc` rule that each job type must have a visible result surface in the Processing area.

**Context:** The code review (WR-08-01) caught the discoverability regression. Fix: restore a compact "Latest similarity groups" preview on the primary CatalogCache card with a "View all" link. Any future phase that removes a UI result surface must ensure the surface migrates, not disappears.
**Source:** 08-REVIEW.md (WR-08-01), 08-REVIEW-FIX.md

---

### Silent metadata coercion hides client bugs and complicates post-hoc debugging
Non-numeric `clip_top_k` values were silently coerced to the default 50. The job ran correctly, but operators and API clients had no visibility into whether their intended top-k was applied.

**Context:** WR-08-03 added a `warning`-level job log when coercion fires. The lesson generalises: any server-side fallback on invalid input should emit an observable signal at the point it occurs.
**Source:** 08-REVIEW.md (WR-08-03), 08-REVIEW-FIX.md

---

### Tests patching a module-level import must patch at the correct binding site
`add_job_log` is imported at module scope in `handlers.py`. Tests that patched `database.add_job_log` did not intercept the function as called by `_emit_prefilter_summary`. The correct patch target is `jobs.handlers.add_job_log`.

**Context:** Discovered while writing the prefilter summary throttle test (Plan 08-02). The fix is straightforward, but the confusion cost time. Binding-site awareness is important for any module-level import in handler files.
**Source:** 08-02-SUMMARY.md (Issues Encountered)

---

### Adding a new Vitest mock for one API method can break unrelated providers if the entire module is replaced
`CatalogCacheTab.test.tsx` initially mocked all of `services/api`, which broke `ProvidersAPI.getDefaults` inside `MatchOptionsProvider` (unrelated to the test's focus). Fix: use `importOriginal` to partially mock only `JobsAPI.create`, then add fetch stubs for `/providers/*`.

**Context:** Whole-module mocking is the default reflex in test setup but silently kills any code-under-test that depends on other exports of the same module. Prefer surgical partial mocks (Vitest `importOriginal`) for large API service modules.
**Source:** 08-06-SUMMARY.md (Issues Encountered)

---

## Patterns

### Over-fetch KNN + intersect with allowed key set
Fetch more KNN candidates than needed (`KNN_K_MAX = 500`), then intersect with the externally-constrained allowed key list (e.g. date-windowed representative-only keys from Phase 7), and cap the intersection to `clip_top_k`.

**When to use:** Whenever a cosine KNN query must respect an upstream filter (date window, representative key set, user-selected subset). Over-fetching avoids a second query; the intersection is pure Python set ops. This is the same pattern as `list_pin_similarity_candidate_keys`.
**Source:** 08-01-SUMMARY.md (patterns-established), 08-CONTEXT.md (Existing Code Insights)

---

### Passthrough mock for shortlist in tests that lack seed embeddings
When integration tests were written before Instagram CLIP embeddings existed, patch `shortlist_catalog_candidates_by_clip` with a passthrough (`keys[:top_k]`) so existing scenarios continue exercising the full scoring path without requiring embedded data.

**When to use:** Any time a new gating/filtering step is inserted into a pipeline and existing tests lack the upstream prerequisite data. Passthrough mocks preserve the existing test contract while the gating step has dedicated unit tests of its own.
**Source:** 08-01-SUMMARY.md (patterns-established, Issues Encountered)

---

### Composite in-process stage runner with thirds-based progress mapping
Implement a `_CatalogCacheStageRunner` wrapper that proxies an inner stage's `5–100%` progress signal onto a one-third slice of the composite job's progress bar. Each stage occupies a third; the wrapper also captures `complete_job`/`finalize_cancelled` per stage so the outer handler retains control of the composite job row.

**When to use:** Multi-stage composite jobs where each stage is a self-contained handler that already manages its own progress. Avoids rewriting handlers; provides a clean cancel-check gate between stages.
**Source:** 08-04-SUMMARY.md (patterns-established, key-decisions)

---

### Skip standalone checkpoint load/persist when nested under composite job
Add a `_catalog_cache_chain` branch in inner handler functions that suppresses standalone checkpoint blobs when the stage is running under a composite `catalog_cache_build` job ID. The composite handler manages idempotency at the outer level.

**When to use:** Reusable inner handlers that are called both standalone and from a composite chain. Preventing double-checkpoint avoids stale checkpoint collisions and keeps the composite job's fingerprint canonical.
**Source:** 08-04-SUMMARY.md (key-decisions)

---

### `AdvancedOptions` children slot for tab-specific pipeline buttons
Extend `AdvancedOptions` with an optional `children` prop rendered below "Reset to defaults." Tabs inject their unique stage triggers (embed, stack, similarity, prepare) into the slot without creating a second disclosure component.

**When to use:** When two or more Processing tabs share the same Advanced disclosure toggle but need different inner controls. The pattern keeps the single-disclosure convention consistent (DRY from Phase 7) while allowing per-tab customisation.
**Source:** 08-06-SUMMARY.md (patterns-established), 08-CONTEXT.md (D-05)

---

### Deep-link route constants in `strings.ts` for cross-tab navigation
Define `PROCESSING_CATALOG_CACHE_ROUTE` (and `PROCESSING_JOB_QUEUE_ROUTE`) as exported string constants in `constants/strings.ts`. Use them in both the anchor `href` and test assertions.

**When to use:** Any cross-tab or cross-page link originating from a Processing tab. Centralised route constants ensure the link target survives a tab rename and make test assertions DRY.
**Source:** 08-05-SUMMARY.md (patterns-established)

---

## Surprises

### CLIP shortlist returned empty lists for all existing integration tests
Once the shortlist step was inserted into `match_dump_media`, existing integration tests that had no Instagram CLIP embeddings received empty shortlists, causing them to skip all scoring. This was not anticipated during planning — the CLIP table was assumed populated in tests.

**Impact:** Required a retroactive passthrough mock (`keys[:top_k]`) at every affected callsite before tests could pass. Added time to Plan 01 and established the passthrough mock pattern. Future gating steps inserted into the matching pipeline should audit upstream data availability in all existing test fixtures before landing.
**Source:** 08-01-SUMMARY.md (Issues Encountered)

---

### `vision_match` with zero Instagram CLIP embeddings emits `clip_shortlist_out=0` and silently skips
In live validation, `clip_shortlist_out=0` appeared for all IG rows because Instagram embeddings had not yet been built (the `catalog_and_instagram` embed job hadn't run). The job exited the skip path gracefully with no MATCH-03 fallback. Operators may mistake this for a bug.

**Impact:** No code regression, but the operator UX is confusing: the job completes successfully having done no matching work. The observability logs (`CLIP shortlist: date_window_in=505 clip_shortlist_out=0` + `Skipped - no candidates found`) provide enough signal if the operator reads them, but there is no UI-level "run the cache build first" affordance.
**Source:** 08-VERIFICATION.md (API live validation)

---

### Vitest `tsconfig.json` missing `ES2022` lib caused `Array.prototype.at` type errors
Adding the `ES2022` lib entry to `apps/visualizer/frontend/tsconfig.json` was required to make pre-existing `SearchPage.test.tsx` usages of `Array.prototype.at` type-check under `tsc --noEmit`. This was a pre-existing gap, not a Phase 8 regression, but it surfaced during Phase 8 work.

**Impact:** Zero runtime impact; the type error would have blocked CI `tsc --noEmit` checks on any subsequent PR touching those test files. Fixed as a drive-by in Plan 05.
**Source:** 08-05-SUMMARY.md (Deviations from Plan)
