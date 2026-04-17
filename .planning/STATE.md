---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Polish & Consolidate
status: Phase 3 complete — ready to plan Phase 4
last_updated: "2026-04-17T23:59:00.000Z"
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 17
  completed_plans: 13
---

# Planning state

**Project:** Lightroom Tagger & Analyzer
**Roadmap:** [.planning/ROADMAP.md](./ROADMAP.md) (v2.1 — Phase 1 complete)

## Current focus

| Field | Value |
|-------|--------|
| Active milestone | v2.1 Polish & Consolidate |
| Phase | Phase 3 — Unified Analyze job (✅ complete) |
| Status | Phase 3 complete — 4 plans / 3 waves / 4 commits; JOB-06 shipped; ready to plan Phase 4 (Reusable filter framework) |
| Last activity | 2026-04-17 — Phase 3 execution + verification complete |

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-17)

**Core value:** Know which catalog images are posted on Instagram and get structured artistic critique that helps you understand your photographic voice and posting strategy.
**Current focus:** v2.1 — Polish & consolidate v2.0's shipped surface before net-new capability in v3.0.

## Accumulated Context

- **v1.0 shipped** (2026-04-11) — Phases 1–4, 22 requirements
- **v2.0 shipped** (2026-04-15) — Phases 5–11, 17 requirements. Archived to [milestones/v2.0-ROADMAP.md](./milestones/v2.0-ROADMAP.md) and [milestones/v2.0-REQUIREMENTS.md](./milestones/v2.0-REQUIREMENTS.md).
- **v2.1 Phase 1 complete** (2026-04-17) — Matching & review polish. Backend two-bucket sort with tombstone serialization (D-08/09/11), validate-transaction created_at backfill (D-12), frontend string constants + MatchGroup.all_rejected (D-14), MatchDetailModal locked reject flow (D-01..D-07), MatchesTab tombstone cards + validated divider.

## Traceability

| Req | Phase | Status |
|-----|-------|--------|
| POLISH-01 | Phase 1 | ✅ Complete (2026-04-17) |
| POLISH-02 | Phase 1 | ✅ Complete (2026-04-17) |
| JOB-03..05 | Phase 2 | ✅ Complete (2026-04-17) |
| JOB-06 | Phase 3 | ✅ Complete (2026-04-17) |
| FILTER-01, 02 | Phase 4 | Pending |
| IDENT-04, 05, DASH-02, 03 | Phase 5 | Pending |
| UI-01, 02, 03 | Phase 6 | Pending |

## Last update

- **2026-04-17:** Phase 3 execution complete. 4 plans / 3 waves / 4 code commits. **Wave 1 (d0aa5fd):** extracted `_run_describe_pass` / `_run_score_pass` helpers; existing `handle_batch_describe` / `handle_batch_score` are thin wrappers — SC-3 preserved (tests for both handlers unchanged and green). **Wave 2 (1f96bd2):** implemented `handle_batch_analyze` with nested `describe` + `score` checkpoints keyed by `stage`, 50/50 progress split via `_map_job_progress`, `current_step` transitions via `update_job_field` (added `'current_step'` to `_ALLOWED_JOB_UPDATE_FIELDS`), `JOB_HANDLERS['batch_analyze']` registration, `checkpoint.py` docstring update for D-18. **Wave 3 (b5e1299, 60e9eae):** new `test_handlers_batch_analyze.py` (6 tests covering zero-work, describe→score, partial-describe + full-score, current_step ordering, resume skip, fingerprint mismatch reset) + `batch_analyze` orphan recovery test; frontend full rename `DescriptionsTab.tsx` → `AnalyzeTab.tsx` via `git mv`, `?tab=analyze` slug, `ANALYZE_*` / `TAB_ANALYZE` strings, primary Analyze CTA, "Run stages separately" inside Advanced disclosure, two independent force checkboxes. Drive-by TS fix in `MatchDetailModal.tsx` (pre-existing `window.setTimeout` → `setTimeout`) to clear the plan AC `tsc --noEmit exit 0`. Verification: 21/21 Phase 3 tests pass, full backend 138 pass (1 pre-existing provider-defaults failure unrelated), 121 frontend tests pass.
- **2026-04-17:** Phase 3 planning complete. 4 PLAN.md files written in 3 waves. **Wave 1:** 01-PLAN (extract `_run_describe_pass` / `_run_score_pass` helpers; rewire existing handlers as thin wrappers — SC-3 guard via unchanged describe/score test files). **Wave 2:** 02-PLAN (`handle_batch_analyze` orchestration, nested `describe`+`score` checkpoints with `stage` field, D-06 combined result keys, D-07 50/50 progress split, D-08 `current_step` via `update_job_field`, `JOB_HANDLERS` registration, `checkpoint.py` docstring for D-18 — orphan recovery stays checkpoint-version-based with no allowlist edits). **Wave 3 (parallel):** 03-PLAN (new `test_handlers_batch_analyze.py` covering zero-work, sequencing, per-stage resume, partial-describe-does-not-block-score, shared selection, `current_step` transitions; plus `batch_analyze` orphan recovery test), 04-PLAN (`git mv` DescriptionsTab→AnalyzeTab, `?tab=analyze` slug, `ANALYZE_*` string constants, primary Analyze CTA, "Run stages separately" in Advanced disclosure with D-11 force-checkbox translation to flat `force` for legacy handlers). Plan-checker: PASS on iteration 1 (all SC-1/SC-2/SC-3 satisfied, D-01..D-18 covered, frontmatter valid, `depends_on` 01→02→{03,04}).
- **2026-04-17:** Phase 3 context gathered. All 6 gray areas discussed (orchestration model, failure handling, progress reporting, UI surface, tab rename, checkpoint semantics). 18 decisions captured in `.planning/phases/03-unified-analyze-job/03-CONTEXT.md`. Backend: extract `_run_describe_pass` / `_run_score_pass` helpers; existing handlers become thin wrappers with zero behavior change (SC-3 guarantee). New `handle_batch_analyze` queries shared selection once, calls both passes in sequence, 50/50 progress split, `current_step` = "Describing" / "Scoring". Per-stage sub-checkpoints reuse existing fingerprint helpers unchanged. Frontend: full rename `DescriptionsTab.tsx` → `AnalyzeTab.tsx` (file, component, nav label, URL slug, tests); primary "Analyze" button + separate-stage buttons inside Advanced disclosure; two independent force checkboxes (`force_describe` / `force_score`).
- **2026-04-17:** Phase 2 execution complete. 4 plans / 2 waves / 5 code commits. Backend: paginated `/api/jobs/` envelope + `count_jobs` helper + `logs_limit` truncation with clamp tests (14 jobs-api tests pass). Frontend: `JobsAPI` envelope + `logs_limit` opt, `DashboardPage` migration, `JobDetailModal` targeted skeleton + D-04 fetch-error + "Show all N logs" expansion + prop-sync for status/progress/current_step, `ProcessingPage` lifted pagination (PAGE_SIZE=50) + debounced refetch + request-seq in-flight guard, `JobQueueTab` pagination inside Card (11 frontend tests added). Code review: APPROVED with medium follow-ups addressed inline (prop-sync staleness, request-seq guard, clamp tests).
- **2026-04-17:** Phase 2 planning complete. 4 PLAN.md files written in 2 waves. **Wave 1 (backend):** 01-PLAN (pagination + `logs_limit` + `count_jobs` + test extensions). **Wave 2 (frontend, depends on 01):** 02-PLAN (API client envelope + types + strings + DashboardPage migration), 03-PLAN (JobDetailModal targeted skeleton + D-04 inline error + log truncation/expansion + `[job.id]` prop-sync), 04-PLAN (ProcessingPage lifted pagination state + debounced refetch + JobQueueTab pagination inside Card). Plan-checker: PASS after 1 revision (9 findings resolved — DashboardPage call site, skeleton scope, D-04 fetch-error, job.id reset, PAGE_SIZE=50, Pagination inside Card, strings.ts constants for "Showing X–Y of Z" and "Loading…", test describe collision).
- **2026-04-17:** Phase 2 context gathered. 4 gray areas discussed (pagination ↔ live updates, log truncation, modal loading UX, page size & refresh semantics). 26 decisions captured in `.planning/phases/02-job-queue-and-processing-ux/02-CONTEXT.md`. Backend: `list_jobs` grows `limit`/`offset` + new `count_jobs` helper + `success_paginated` envelope; `get_job` grows `?logs_limit=N`. Frontend: `ProcessingPage` lifts pagination state, debounced refetch on socket events, hybrid skeleton in `JobDetailModal`, "Show all N logs" expansion, `<Pagination>` wired into `JobQueueTab` (page size 50, reset on filter, Refresh pins page).
- **2026-04-17:** Phase 1 execution complete. 5 plans / 2 waves / 10 code commits. All automated checks green (13 backend phase tests, 106 frontend tests, lint clean). Pre-existing `test_providers_api.py::TestDefaults` failure noted, unrelated to Phase 1. Verification: 17/17 must-haves passed.
- **2026-04-17:** Phase 1 planning complete. 5 plans in 2 waves. POLISH-01/02 covered; D-01..D-14 all mapped. Plan-checker passed on iteration 2.
- **2026-04-17:** v2.1 roadmap approved — 6 phases, 15 requirements. Phase 5 depends on Phase 4 (filter framework). Ready to discuss Phase 1.
- **2026-04-17:** v2.1 milestone started. Scope: 9 seeds (polish, consolidation, reusable filter foundation). Phase numbering reset to 1.

---
*This file is the canonical planning pointer for "where we are" between phase transitions.*
