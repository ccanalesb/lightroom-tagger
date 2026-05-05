# Requirements — v4.0 Backend Health & E2E Coverage

**Milestone goal:** Refactor oversized backend files, fix two broken operational workflows, and guarantee no flow is broken via a new E2E test layer using browser harness with real examples — single and batch flows.

**Baseline:** 663 backend tests passing as of 2026-05-05. All splits must keep this baseline green after each phase.

---

## Active Requirements

### Structural Refactor

- [ ] **REFACTOR-01**: `handlers.py` (3,830L) split into per-job-family modules with shared orchestration helpers — no behavior change, all tests green after each split
- [ ] **REFACTOR-02**: `database.py` (3,557L) split by domain concern (catalog, instagram, matches, descriptions, scores, jobs, stacks) — `test_database.py` co-split alongside
- [ ] **REFACTOR-03**: `images.py` (1,954L) split by resource group (catalog routes, instagram routes, search routes) — test coverage preserved
- [ ] **REFACTOR-04**: `analyzer.py`, `matcher.py`, `identity_service.py` each under 400L — duplicate logic extracted to shared helpers
- [ ] **REFACTOR-05**: Module boundary policy documented (max file size, what belongs in handler vs service vs repository) — enforced via CI lint check

### Operational Fixes

- [ ] **OPS-01**: Embed job can be triggered directly from the "Visual similarity unavailable" error state — user never needs to know where to find the Processing tab
- [ ] **OPS-02**: Embed job preflight samples file paths before full run — if unreachable rate is high, fails fast with a single actionable message instead of thousands of skip logs
- [ ] **OPS-03**: Embed job result payload includes a "why skipped" summary (counts by: missing file, empty path, no DB row) — UI renders a clear post-job diagnosis
- [ ] **OPS-04**: Backend restart with orphaned `batch_analyze` jobs no longer produces repeated compression logs — resume skips already-compressed work silently
- [ ] **OPS-05**: `test_providers_api::TestDefaults` provider-defaults failure fixed — no pre-existing test failures in the suite

### Test Coverage

- [ ] **TEST-01**: Restart/orphan recovery has focused unit tests — covers resume-after-crash for `batch_analyze`, `batch_describe`, `batch_score`
- [ ] **TEST-02**: Path-failure handling has unit tests — covers missing file, empty path, unreachable network share, high-failure-rate preflight abort
- [ ] **TEST-03**: E2E test suite bootstrapped using browser harness (CDP) against a running local stack — framework in place, real catalog fixture used

### E2E Flows

- [ ] **E2E-01**: Single-image describe flow tested E2E — trigger from UI, job completes, description visible in catalog modal
- [ ] **E2E-02**: Single-image score flow tested E2E — trigger from UI, scores visible in catalog with correct perspectives
- [ ] **E2E-03**: Match review flow tested E2E — Instagram dump loaded, matches appear, confirm/reject actions persist
- [ ] **E2E-04**: Batch analyze flow (describe → score) tested E2E — job runs to completion, progress visible, results queryable
- [ ] **E2E-05**: Batch stack detect flow tested E2E — job runs, stack badges appear in catalog, split/merge actions work
- [ ] **E2E-06**: Catalog cache build flow tested E2E — composite job runs all stages, similarity groups appear in catalog

---

## Future Requirements (deferred)

- Unified vision match + describe in a single model call (SEED-014) — depends on handlers split landing first
- `cli.py` / `lightroom_tagger/core/cli.py` split — lower urgency than API and job layers
- Full rollout of `useFilters` to remaining tabs (MatchesTab, DescriptionsTab, MatchingTab, AnalyticsPage, UnpostedCatalogPanel) — SEED-007

---

## Out of Scope

- New user-facing features — this is a pure health milestone
- Frontend structural refactor — frontend is in good shape; no splitting needed
- Embedding model A/B or provider migration — separate feature milestone
- SEED-014 unified match+describe model call — coordination with REFACTOR-01 required first; defer to v4.1

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REFACTOR-01 | 13 | Pending |
| REFACTOR-02 | 14 | Pending |
| REFACTOR-03 | 14 | Pending |
| REFACTOR-04 | 15 | Pending |
| REFACTOR-05 | 15 | Pending |
| OPS-01 | 12 | Pending |
| OPS-02 | 12 | Pending |
| OPS-03 | 12 | Pending |
| OPS-04 | 12 | Pending |
| OPS-05 | 12 | Pending |
| TEST-01 | 16 | Pending |
| TEST-02 | 16 | Pending |
| TEST-03 | 17 | Pending |
| E2E-01 | 18 | Pending |
| E2E-02 | 18 | Pending |
| E2E-03 | 18 | Pending |
| E2E-04 | 18 | Pending |
| E2E-05 | 18 | Pending |
| E2E-06 | 18 | Pending |
