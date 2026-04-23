# Milestones

## v2.1 Polish & Consolidate (Shipped: 2026-04-23)

**Phases:** 9 (1–4, 4.1, 5–8) | **Plans:** 35 | **Commits:** ~226 | **Timeline:** 7 days (2026-04-17 → 2026-04-23)
**Files changed:** 405 files, 33,639 insertions, 5,848 deletions

**Delivered:** UX friction removed across matching, job queue, and identity. Reusable filter framework (useFilters + FilterBar). React Suspense data layer replacing all useEffect fetches with zero new deps. Two-stage cascade matching (description + vision weighted scoring). All 20 requirements complete (15 original + 5 added mid-milestone: DATA-01, MATCH-01..04).

**Key accomplishments:**

- Matching flow polish: Modal stays open after reject, auto-advances through multi-candidate groups, unvalidated matches sort first by newest Instagram `created_at` (POLISH-01, POLISH-02)
- Job queue UX: Skeleton loading for Job Detail Modal, log truncation + "Show all N logs" expansion, paginated Job Queue with page pinning across polls, unified "Analyze" job (describe → score in sequence with 50/50 progress, sub-checkpoints, `current_step` UI) (JOB-03..06)
- Reusable filter framework: `useFilters(schema)` hook with toggle/select/dateRange/search primitives, internal debouncing, `enabledBy` cascades, `toQueryParams` mapping; `<FilterBar>` with chips + clear-all; CatalogTab + InstagramTab migrated (FILTER-01, FILTER-02)
- Identity & Insights clarity: Posted overlay badge + deduplicated metadata chip on BestPhotosGrid; Identity page narrative reordered (fingerprint → best → post next) with section intros; Dashboard Top Photos Unposted | Posted | All tabs via `useFilters` (IDENT-04, IDENT-05, DASH-02, DASH-03)
- Images page visual consistency: Badge primitives consolidated under consistent CVA-style API; inline-in-description badge pattern; matches rendered as CatalogImageCard-consistent cards (UI-01..03)
- React Suspense data layer: Module-level cache (`src/data/`), `useQuery` Suspense throw-promise, `invalidate`/`invalidateAll`, shared `<ErrorBoundary>` + `<ErrorState>`; full app migration (Identity, Images, Processing, Analytics, Dashboard); 248 tests + tsc + vite build green; zero new npm dependencies (DATA-01)
- Two-stage cascade matching: LEFT JOIN `image_descriptions` → `ai_summary`; `compare_descriptions_batch` text-only API; cascade pipeline (desc → vision, weighted merge); `vision_weight=0` skips all vision calls; `skip_undescribed` option (MATCH-01..04)

**Requirements:** 20/20 v2.1 requirements complete
**Known deferred items at close:** 21 (20 dormant seeds + 1 quick task — see STATE.md Deferred Items)

---

## v2.0 Advanced Critique & Insights (Shipped: 2026-04-15)

**Phases:** 7 | **Plans:** 24 | **Commits:** ~130 | **LOC:** ~32K | **Timeline:** 4 days (2026-04-12 → 2026-04-15)

**Delivered:** Structured artistic scoring, posting analytics, photographer identity analysis, and a unified insights dashboard on top of the v1 catalog + Instagram workflow.

**Key accomplishments:**

- Structured scoring foundation: Pydantic-validated per-perspective scores (1–10) with photography-theory-grounded rubrics (Freeman, Berger, Itten), configurable perspectives via REST API + CodeMirror UI, and LLM JSON repair pipeline
- Scoring pipeline & catalog UX: Single and batch scoring jobs with model/rubric version tracking, score history with supersede semantics, and catalog filter/sort by persisted scores
- Posting analytics: Frequency timeline, day-of-week × hour heatmap, caption/hashtag stats, and unposted catalog gap view from Instagram dump timestamps
- Identity & suggestions: Best photos ranking by aggregated scores, style fingerprint (radar chart + rationale tokens with evidence), and "what to post next" with explainable reason codes
- Insights dashboard: Unified home composing KPI row, score distributions, posting cadence, top-scored photos strip, and quick-nav cards via parallel API composition
- Job resilience: Checkpoint-based progress persistence surviving backend restarts, orphan job auto-recovery on startup with UI notification

**Requirements:** 17/17 v2 requirements complete

---

## v1.0 Lightroom Tagger MVP (Shipped: 2026-04-11)

**Phases:** 4 | **Plans:** 21 | **Commits:** 405 | **LOC:** ~28K | **Timeline:** 28 days

**Delivered:** End-to-end workflow for tracking Instagram-posted photos in Lightroom catalogs with AI-powered artistic critique.

**Key accomplishments:**

- Register and browse 38K+ Lightroom catalog images with 8 filters, pagination, and read-only safety
- Observable job lifecycle with cooperative cancellation, catalog backup rotation, and Lightroom lock guard
- Instagram dump import, vision-based matching to catalog, confirm/reject UI, and posted keyword writeback
- Multi-provider AI descriptions with health probes, on-demand + batch generation, and analyzed filter/badges
- Vision pipeline hardened with SR2 support, 512KB cache ceiling, and pre-flight filtering
- Catalog modal with inline AI description panel and on-demand generate

**Requirements:** 22/22 v1 requirements complete

---
