# Milestones

## v3.0 Intelligent Discovery (Shipped: 2026-05-04)

**Phases completed:** 14 phases, 56 plans, 54 tasks

**Key accomplishments:**

- Plan verification
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- SQLite library DB now creates `image_stacks` and `image_stack_members` idempotently on `init_database`, with denormalized `stack_size`, `user_modified` scaffold, UNIQUE on `image_key`, and CASCADE deletes — wired after the vec0 migration.
- Default burst window `stack_burst_delta_ms` (2000 ms) is loaded from `Config`/`config.yaml`, exposed via `GET/PUT /api/config/stack-detection`, and editable in Processing → Settings with the same load/save/error pattern as the catalog path panel.
- `batch_stack_detect` job handler: burst grouping by `date_taken`, three-tier SQL representative (`rating` + `image_scores`/`perspectives` + tie-breaks), `fingerprint_batch_stack_detect` for resume, and `JOB_HANDLERS` + catalog job-type registration with five integer result fields.
- Automated tests for `batch_stack_detect`, `fingerprint_batch_stack_detect`, health/config registration, and stack-detection routes; one production fix for `image_stacks` INSERT bind count found while exercising the handler.
- One-liner:
- Completed:
- Completed:
- Status:
- Status:
- Completed:
- Catalog and Best Photos primary lists now collapse non-representative stack members and expose stack_id, stack_member_count, and is_stack_representative for representative (or solo) rows, with pytest coverage.
- CLIP-only sqlite-vec KNN on `image_clip_embeddings`, order-preserving filters via `filter_order_keys_in_catalog`, and `NoClipEmbeddingError` for seeds missing embeddings — ready for Flask wiring in 06-03.
- Flask routes for CLIP-only similar images and stack member strips, with catalog DTOs carrying stack metadata and pytest coverage for 404/200 contracts.
- CLIP similar and stack members are wired through `ImagesAPI`, with stack badges and expandable member strips on Catalog and Best Photos, and a “More like this” flow in the catalog image detail modal including Visually similar results and documented empty/error states.
- One-liner:
- One-liner:
- Shipped stack split/merge/representative controls in the catalog stack strip and catalog detail modal, with a reusable confirm shell (used by reject-match) and a timed undo path for representative changes.
- Delivered:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- CLIP cosine shortlist intersects Phase-7 representative date-window keys before any phash/description/vision scoring; `match_dump_media` exposes `clip_top_k` (default 50) with `clip_shortlist_applied` observability.
- Job layer clamps `clip_top_k`, folds it into resume fingerprints when non-default, forwards into `match_dump_media`, aggregates prefilter/judgment totals from matcher stats, and emits throttled `vision-match-prefilter-summary` lines plus cumulative result keys on completion.
- Instagram dump media keys gain first-class CLIP vec0 rows via `batch_embed_image` (`catalog_and_instagram`), with DB backlog helpers and fingerprint scope so catalog-only checkpoints cannot resume union runs.
- Adds `catalog_cache_build` job type so operators run catalog+Instagram CLIP embedding, burst stack detection, and catalog similarity grouping in one cancel scope, with `[catalog-cache-build]` stage banners and backlog warnings instead of aborting downstream stages.
- Matching posts integer `clip_top_k` on `vision_match`, removes stack/similarity discovery UI from Matching, and links operators to the Catalog cache tab.
- Catalog cache tab ships a composite “Build catalog cache” job trigger, Job Queue success affordance, and Advanced panel reuse (`AdvancedOptions` + pipeline buttons) aligned with D-04/D-05.
- v3.0 REQUIREMENTS body, traceability, and dependency lines synced to as-shipped status: 5 reqs flipped to complete, SIM-02 rewritten for job-driven pivot, STACK-02 descoped, STACK-04 dependency on STACK-02 removed.
- Phase 6 re_verification annotated with SIM-02 job-driven pivot rationale (truth #8 deliberate revert via 260427-f75); 05.1 and 05.2 sub-phase stub VERIFICATION.md files created pointing to parent Phase 5 verification with `walkthrough_exempt: true`.
- Phase 9 final gates green: tsc --noEmit clean, npm run lint clean (after clearing 5 pre-existing errors + 4 warnings inline), backend pytest 338 passed, core pytest 267 passed, all orphan-symbol greps exit 1, walkthrough disposition handed off to gsd-verifier.
- Read-only CLI that replays validated `(insta_key, catalog_key)` pairs through date-window filtering, rejection and primary-grid trims, optional CLIP shortlist (`top_k=50`), then emits funnel metrics plus CSV/trace markdown.
- Phase 11 prep copy and operator documentation:
- Matching Advanced Options now exposes a proper disclosure control; message-only undo notifications stay visible for the full timeout; Catalog Cache tab copy and NAS guidance live in `strings.ts` constants.
- Chat Search shows centralized inactive-pin copy with Processing deep-links when the backend reports `no_clip_embedding`, using one `role="status"` live region per warning and Vitest coverage for copy and `href`s.

---

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
