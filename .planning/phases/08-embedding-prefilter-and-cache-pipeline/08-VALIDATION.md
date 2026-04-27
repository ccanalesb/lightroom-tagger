---
phase: 8
slug: 08-embedding-prefilter-and-cache-pipeline
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-27
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for the CLIP pre-filter cascade in `vision_match` (MATCH-02) and the catalog cache pipeline rewire (CACHE-01). Derived from `08-RESEARCH.md` Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | repo-root pytest defaults; `apps/visualizer/frontend/vitest.config.ts` |
| **Quick run command** | `cd /Users/ccanales/projects/lightroom-tagger && python -m pytest apps/visualizer/backend/tests/test_handlers_batch_embed_image.py apps/visualizer/backend/tests/test_handlers_single_match.py -q --tb=short && cd apps/visualizer/frontend && npm run test -- --run src/components/processing/__tests__/MatchingTab.test.tsx src/components/processing/__tests__/CatalogCacheTab.test.tsx` |
| **Full suite command** | `cd /Users/ccanales/projects/lightroom-tagger && python -m pytest -q && cd apps/visualizer/frontend && npm run test -- --run` |
| **Estimated runtime** | ~300 seconds |

---

## Sampling Rate

- **After every task commit:** Run the targeted backend or frontend test for the task (per task `<verify>` block).
- **After every plan wave:** Run the quick run command above (covers shortlist + embed extension + cache chain + Matching/CatalogCache UI).
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 120 seconds for the quick run.

---

## Per-Task Verification Map

> Plan IDs and task IDs are filled in by the planner during `/gsd-plan-phase`. The rows below are keyed by requirement + capability so the planner can map them onto specific tasks. Status flips to `✅` when the matching task commits green.

| REQ | Capability | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-----|-----------|------------|-----------------|-----------|-------------------|-------------|--------|
| MATCH-02 | CLIP shortlist helper returns ≤ `clip_top_k` and only keys from the input candidate set | T-08-MATCH-01 (Tampering: shortlist leaks non-candidate keys) | Shortlist subset is invariant: `set(shortlist) ⊆ set(candidates)` and `len(shortlist) ≤ clip_top_k` | unit | `python -m pytest lightroom_tagger/core/test_clip_similarity.py -k shortlist -q --tb=short` (extend or new file) | ❌ Wave 0 — new test module/case | ⬜ pending |
| MATCH-02 | D-03 gating: phash + description + LLM all run only on shortlist (not full window) | T-08-MATCH-02 (DoS: scoring runs over full date window) | After shortlist runs, `score_candidates_with_vision` receives the shortlist only | unit | `python -m pytest apps/visualizer/backend/tests/test_handlers_single_match.py -k shortlist -q --tb=short` | ❌ Wave 0 — extend existing test file | ⬜ pending |
| MATCH-02 | `match_dump_media` plumbing accepts `clip_top_k` and emits per-batch summary log lines (D-07) | T-08-MATCH-03 (Information disclosure / log spam) | Throttled per-batch summary `date_window_in=N clip_shortlist_out=M judgments=J` | integration | `python -m pytest apps/visualizer/backend/tests/test_handlers_single_match.py -k summary_log -q --tb=short` | ❌ Wave 0 — new assertion on `add_job_log` capture | ⬜ pending |
| MATCH-02 | `fingerprint_vision_match` includes `clip_top_k` so resume does not mix runs with different shortlist sizes | T-08-MATCH-04 (Stale resume mixing top-k) | Two fingerprints with different `clip_top_k` are not equal | unit | `python -m pytest apps/visualizer/backend/tests/test_checkpoint_fingerprints.py -k vision_match -q --tb=short` | ❌ Wave 0 — extend or create test module | ⬜ pending |
| MATCH-02 | `clip_top_k` server-side clamp 1..500 in `handle_vision_match` | T-08-MATCH-05 (Tampering: out-of-range top-k via direct API) | Out-of-range values clamped or rejected; metadata never feeds raw client value into KNN | unit | `python -m pytest apps/visualizer/backend/tests/test_handlers_single_match.py -k clip_top_k_bounds -q --tb=short` | ❌ Wave 0 — new test case | ⬜ pending |
| CACHE-01 | Composite cache build job runs `embed → stack-detect → catalog-similarity` in order, honors cancel | T-08-CACHE-01 (DoS via long-running job; cancel must propagate) | Single job, single `cancel_scope`; cancellation between stages stops downstream | integration | `python -m pytest apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py -q --tb=short` | ❌ Wave 0 — new test file | ⬜ pending |
| CACHE-01 | Per-stage progress + skip reasons emitted (D-08) | T-08-CACHE-02 (Information disclosure / opacity) | Job log shows ordered stage banners with input/output/skip counts | integration | `python -m pytest apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py -k stage_log -q --tb=short` | ❌ Wave 0 — new assertion via captured `add_job_log` | ⬜ pending |
| CACHE-01 | `batch_embed_image` covers Instagram rows when scope includes them; idempotent under fingerprint | T-08-CACHE-03 (Stale resume skipping new IG rows) | `fingerprint_batch_embed_image` payload differs when IG scope toggles; IG rows persisted via `upsert_image_clip_embedding` | integration | `python -m pytest apps/visualizer/backend/tests/test_handlers_batch_embed_image.py -k instagram -q --tb=short` | ❌ Wave 0 — extend existing test file | ⬜ pending |
| CACHE-01 (D-06) | `MatchingTab` renders no stack-detect / catalog-similarity controls | T-08-UI-01 (Orphan UI surface; mismatched mental model) | Component test: queries for the removed CTAs return null; orphan strings deleted from `strings.ts` | component | `cd apps/visualizer/frontend && npm run test -- --run src/components/processing/__tests__/MatchingTab.test.tsx` | ✅ existing test file | ⬜ pending |
| CACHE-01 (D-04 / D-05) | `CatalogCacheTab` renders one composite "Build catalog cache" CTA + reuses existing `AdvancedOptions` for individual stage triggers + `prepare_catalog` | T-08-UI-02 (Duplicate disclosure / DRY drift) | Component test: a single primary CTA exists, Advanced disclosure is the imported `AdvancedOptions` (not a new component) | component | `cd apps/visualizer/frontend && npm run test -- --run src/components/processing/__tests__/CatalogCacheTab.test.tsx` | ✅ existing test file | ⬜ pending |
| MATCH-02 (UI) | `MatchingTab` exposes a numeric `clip_top_k` input bound 1..500 with default 50; sends value through `JobsAPI.create('vision_match', { clip_top_k })` | T-08-UI-03 (Tampering via UI: out-of-range top-k) | In-app validation rejects out-of-range values with the spec'd error copy; metadata posted matches the validated integer | component | `cd apps/visualizer/frontend && npm run test -- --run src/components/processing/__tests__/MatchingTab.test.tsx` | ✅ existing test file | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠ flaky*

---

## Wave 0 Requirements

- [x] Backend pytest infra is already in place (`apps/visualizer/backend/tests/`).
- [x] Frontend vitest infra is already in place (`apps/visualizer/frontend/vitest.config.ts`).
- [x] `add_job_log` capture pattern is already used in `test_handlers_single_match.py` (mirror for new summary-log assertions).
- [ ] **New test files** the planner must create as part of plan tasks (treated as plan-internal Wave 0):
  - `apps/visualizer/backend/tests/test_handlers_catalog_cache_build.py` (CACHE-01 chain)
  - `apps/visualizer/backend/tests/test_checkpoint_fingerprints.py` if extending fingerprint tests (or extend an existing module — planner decides)
  - `lightroom_tagger/core/test_clip_similarity.py` shortlist case (or extend existing)

Existing infrastructure covers all phase requirements; net-new test modules are scoped tasks inside their respective plans, not a separate Wave 0 setup phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LLM call-count reduction (≥10× vs Phase 7 baseline) on a representative batch | MATCH-02 | Cost reduction is observed across many media via job logs / metrics; not a unit-test target | Run two `vision_match` jobs against the same date window — one with the Phase 7 binary built (or by setting `clip_top_k` very high to approximate "no shortlist"), one at default 50. Compare per-batch summary lines and final job result counts. Confirm ≥10× reduction in `judgments` total without recall loss on user-validated match pairs. |
| Operator narrative for cache chain (`embed → stack → similarity`) | CACHE-01 (D-08) | Log readability and ordering is a UX judgment | Click "Build catalog cache" once on a small catalog. Open Job Queue → job detail → confirm three ordered stage sections in the log with input/output/skip counts; verify cancel button stops the chain mid-stage cleanly. |
| Recall preservation on user-validated match pairs after shortlist enabled | MATCH-02 | Recall against truth set requires a curated truth file outside CI | Take an existing validated-match Instagram-to-catalog pairs list. Run `vision_match` end-to-end and confirm each known true match is in the shortlist for its target media. If any are missed at default `clip_top_k=50`, raise top-k and re-test; record the floor in the embedding-recall benchmark todo. |

---

## Validation Sign-Off

- [x] All planned capabilities have automated verification commands keyed to a requirement
- [x] Sampling continuity established: no three consecutive tasks without automated verify (planner enforces during PLAN.md generation)
- [x] Existing test infra covers referenced files; net-new test modules are explicit and scoped
- [x] No watch-mode flags
- [x] Feedback latency target documented (≤120s quick run)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — flips to approved when planner finalizes plan/task IDs against this map.
