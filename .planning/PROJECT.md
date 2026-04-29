# Lightroom Tagger & Analyzer

## What This Is

A web application that connects your Lightroom catalog with Instagram to track what you've published and provides AI-powered structured artistic analysis of your photography. It scores images across configurable critique perspectives (street, documentary, publisher, color theory), surfaces your photographic identity through style fingerprints and best-photo rankings, analyzes posting patterns, and suggests what to shoot or post next — all from a unified insights dashboard.

## Core Value

Know which catalog images are posted on Instagram and get structured artistic critique that helps you understand your photographic voice and posting strategy.

## Current Milestone: v3.0 Intelligent Discovery

**Goal:** Turn the catalog from a passive archive into a queryable, visually-aware library you can explore by meaning, mood, and similarity.

**Target features:**
- Natural language search — ask questions like "best street photo from December I haven't posted" or "moody cityscapes" (LLM-to-SQL + full-text + semantic embeddings)
- Photo stacking — group burst/near-duplicate shots, score the representative instead of every member (primary driver: cut redundant scoring costs)
- Visual attribute tags — extend describe-time output to extract dominant colors, mood, repetition → filter facets in catalog
- Visual similarity search — image embeddings so you can say "show me more like this photo"

**Seeds incorporated:** SEED-005, SEED-006, SEED-018

## Requirements

### Validated

- ✓ Register and browse Lightroom catalog safely with read-only enforcement — v1.0
- ✓ Paginate and filter catalog photos by keyword, rating, date range, color label — v1.0
- ✓ Stable photo identity across sessions via unified composite keys — v1.0
- ✓ Observable job lifecycle with status visible as queued/running/complete/failed — v1.0
- ✓ Job cancellation with cooperative threading.Event propagation — v1.0
- ✓ Backup-before-write with timestamped rotation capped at two files — v1.0
- ✓ Actionable error severity classification with UI badges — v1.0
- ✓ Lightroom-open guardrail via lock file detection before catalog writes — v1.0
- ✓ Match Instagram dump images to Lightroom catalog entries — v1.0
- ✓ Confirm matches and write "posted" keyword back to Lightroom catalog — v1.0
- ✓ Generate on-demand AI descriptions for catalog images — v1.0
- ✓ On-demand analysis jobs (single image or timeframe-based batches) — v1.0
- ✓ Multi-perspective critique (street photographer, editor, publisher views) — v1.0
- ✓ Structured artistic scoring (1-10 per perspective) as queryable fields — v2.0
- ✓ New critique perspectives: color theory added to street/documentary/publisher — v2.0
- ✓ Photography-theory-refined prompts with Itten, Freeman, Berger citations — v2.0
- ✓ Per-perspective numeric scoring persisted and filterable/sortable in catalog UI — v2.0
- ✓ Posting frequency and timing pattern analysis from Instagram dump timestamps — v2.0
- ✓ Caption and hashtag style analysis — v2.0
- ✓ "Best photos" ranking by aggregated AI perspective scores — v2.0
- ✓ Photographer identity analysis — style fingerprint from score patterns — v2.0
- ✓ "What to post next" suggestions based on catalog vs posting gaps — v2.0
- ✓ Insights dashboard with KPI row, score distributions, posting cadence, quick-nav — v2.0
- ✓ Job checkpoint persistence surviving backend restarts — v2.0
- ✓ Orphaned job auto-recovery on startup — v2.0
- ✓ Match review flow: modal stays open after reject, unvalidated-first sort — v2.1 (POLISH-01, POLISH-02)
- ✓ Job queue UX: skeleton loading, log truncation/expansion, paginated queue — v2.1 (JOB-03..05)
- ✓ Unified Analyze job (describe → score) with advanced separate-stage option — v2.1 (JOB-06)
- ✓ Reusable `useFilters` hook + `<FilterBar>` — CatalogTab + InstagramTab migrated — v2.1 (FILTER-01, FILTER-02)
- ✓ Posted/unposted visibility on BestPhotosGrid and Dashboard Top Photos — v2.1 (IDENT-04, DASH-02, DASH-03)
- ✓ Identity page narrative flow: fingerprint → best → post next with section intros — v2.1 (IDENT-05)
- ✓ Images page badge and match card visual consistency — v2.1 (UI-01..03)
- ✓ React Suspense data layer: zero useEffect fetches, module-level cache, no new deps — v2.1 (DATA-01)
- ✓ Two-stage cascade matching: description + vision weighted scoring, skip_undescribed — v2.1 (MATCH-01..04)
- ✓ Burst shot stacking: `image_stacks` schema, `batch_stack_detect` handler, configurable `stack_burst_delta_ms`, checkpoint resume — v3.0 Phase 4 (STACK-01)
- ✓ Similarity & stack UI: stack representatives collapse primary lists, Catalog/Best Photos expose stack badges + member expansion, and similarity discovery is delivered via job-driven materialized similarity groups on Processing → Catalog cache (post-Phase-6 pivot, quick `260427-f75` 2026-04-27) — v3.0 Phase 6 + Phase 9 cleanup (SIM-02, STACK-03)
- ✓ Stack-aware Instagram matching: compare against representatives and apply confirmed matches stack-wide with non-destructive conflict skips and explicit counters — v3.0 Phase 7 (STACK-04)
- ✓ Stack edit mutations (split, merge, representative change) available in backend API + Images UI with confirm/undo interaction where safe — v3.0 Phase 7 (STACK-05)
- ✓ Search pin-to-similar flow: single active pin, similarity-first refinement, and visible fallback when pin similarity is unavailable — v3.0 Phase 7 (NLS-06)

### Deferred (future)

- [ ] Support multiple Lightroom catalogs with context switching
- [ ] Unified photographer identity view across catalogs
- [ ] Instagram engagement data (likes/saves) — requires API or manual entry
- [ ] Dashboard drill-down (click chart data points to navigate to specific photos)

### Out of Scope

- Instagram API integration or scraping — Using export-based dumps instead
- Technical EXIF analysis — Focus is artistic critique, not camera settings
- Lightroom plugin — Web app keeps Lightroom as-is, only writes keywords
- Real-time Instagram syncing — Manual dump workflow is sufficient
- Batch analysis of entire catalog upfront — On-demand only to control costs
- Per-post engagement metrics from dumps — Instagram exports don't include likes/saves/comments counts
- Embedding-based style fingerprint — Score pattern analysis is sufficient and cheaper

## Context

### Workflow
The user is a photographer managing work across multiple Lightroom catalogs (personal portfolio, client work like weddings, etc.). They post selectively to Instagram and want to understand both sides of their practice: what they publish vs what stays in the catalog.

### Current State
- **v1.0 shipped** (2026-04-11) — 4 phases, 22 requirements: catalog management, jobs, Instagram sync, AI descriptions
- **v2.0 shipped** (2026-04-15) — 7 phases, 17 requirements: structured scoring, posting analytics, identity/suggestions, insights dashboard
- **v2.1 shipped** (2026-04-23) — 9 phases, 20 requirements: matching polish, job queue UX, filter framework, identity clarity, badge/card consistency, React Suspense data layer, two-stage cascade matching
- **v3.0 Phase 4 complete** (2026-04-24) — Stack detection: `image_stacks`/`image_stack_members` schema, `batch_stack_detect` handler with burst grouping by `date_taken`, configurable `stack_burst_delta_ms`, `StackDetectionSettingsPanel` UI, checkpoint resume. STACK-01 shipped.
- **v3.0 Phase 6 complete** (2026-04-25) — Similarity & Stack UI: CLIP-only `GET /api/images/catalog/<key>/similar`, stack member API, catalog/best-photo stack badges + expansion, and `ImageDetailModal` “More like this”. SIM-02 and STACK-03 shipped; NLS-06 chat pin remains Phase 7.
- **v3.0 Phase 7 complete** (2026-04-26) — Stacks in matching + pin similarity: representative-only Instagram candidate scoring, stack-wide apply with conflict skips and counters, stack mutation API (split/merge/representative) plus Catalog/detail UI actions, and chat pin-to-similar orchestration with inactive fallback messaging. STACK-04, STACK-05, and NLS-06 shipped.
- **v3.0 Phase 8 complete** (2026-04-27) — Embedding pre-filter + catalog cache pipeline: CLIP shortlist over date-windowed candidates before LLM judgments, `clip_top_k` plumbed through `vision_match`, `catalog_cache_build` composite job (`batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity`) with stage banners + skip counts, MatchingTab `clip_top_k` input, CatalogCacheTab UI with primary "Build catalog cache" CTA + advanced stage triggers. Quick `260427-f75` (2026-04-27) pivoted SIM-02 UX to materialized similarity groups on the catalog cache surface, removing the on-demand "More like this" entry. CACHE-01 + MATCH-02 (implementation) shipped.
- **v3.0 Phase 9 complete** (2026-04-29) — v3.0 cleanup gap closure: REQUIREMENTS.md body checkboxes + traceability synced (NLS-02, NLS-06, VIS-01, STACK-04, STACK-05 ✓; STACK-02 Descoped 2026-04-24; SIM-02 rewritten for job-driven pivot); 06-VERIFICATION re_verification block annotated; 05.1/05.2 stub VERIFICATION.md created; orphan frontend exports removed (`getCatalogSimilar`, `CatalogSimilarResponse`, 14 `CATALOG_SIMILAR_*` constants); pre-existing lint baseline cleared. SIM-02 + STACK-02 documentation/dead-code closed.
- ~38K LOC across Python backend and React/TypeScript frontend (405 files changed in v2.1)
- Tech stack: Flask + SQLite (catalog read-only, library DB read-write), React 19 + Vite + Recharts + CodeMirror
- 4 configurable critique perspectives with photography-theory rubrics
- Pydantic-validated structured output with deterministic + LLM JSON repair
- Job checkpointing and orphan recovery for crash resilience
- React Suspense data layer: module-level cache, useQuery, invalidate/invalidateAll, ErrorBoundary — zero new npm deps
- Reusable filter framework: `useFilters(schema)` + `<FilterBar>` — CatalogTab + InstagramTab migrated; remaining tabs deferred v3.0
- Pre-existing `test_providers_api.py::TestDefaults` backend test failure (provider default drift, unrelated to v2.1)

### Instagram Dump Format
User provides Instagram export dumps containing images, captions, timestamps, and EXIF. App matches these to Lightroom catalog entries by comparing images, then writes keywords back to the SQLite catalog file. Instagram exports do NOT include per-post engagement metrics — analytics are derived from posting patterns and AI scores only.

### Analysis Philosophy
Critique comes from defined perspectives (street photographer, documentary, publisher, color theory) with prompts refined by photography theory from Freeman, Berger, Hicks, and Itten/Albers. Perspectives are configurable via the Processing UI with CodeMirror markdown editing. Focus is artistic execution and narrative fit, not technical metrics.

## Constraints

- **Database**: Lightroom catalogs are SQLite files — read-only except for keyword writes
- **AI Providers**: Currently Ollama (local/cloud), may expand to OpenRouter/GPT for better analysis
- **Instagram Sync**: Export-based workflow (no API access) — user provides dumps
- **Architecture**: Web application accessed via browser
- **Analysis Approach**: On-demand job triggers, not batch processing
- **Multi-catalog**: Must support switching between multiple .lrcat files while maintaining unified photographer identity view

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Export-based Instagram sync | Avoids API limitations, user owns data | ✓ Good — reliable dump import pipeline |
| Direct SQLite catalog writes | Only way to add keywords to Lightroom | ✓ Good — lock guard + backup make it safe |
| On-demand analysis | Controls AI costs, scales with usage | ✓ Good — batch + single both work well |
| Web app (not plugin) | Keeps Lightroom unchanged, easier deployment | ✓ Good — React visualizer works great |
| Artistic over technical | User wants style/narrative critique, not EXIF analysis | ✓ Good — multi-perspective critique landed |
| Cooperative cancellation via threading.Event | Clean job stop without data corruption | ✓ Good — propagates through all handlers |
| 512KB vision cache ceiling | Prevents disk bloat from large RAW files | ✓ Good — oversized sentinel auto-invalidates |
| Provider health probes | UX shows reachable/unreachable before job start | ✓ Good — prevents wasted job attempts |
| Pydantic score validation with LLM repair | Structured output needs deterministic + fallback repair | ✓ Good — golden fixtures prove all repair paths |
| Parallel API composition for dashboard | Avoids monolithic endpoint; fast SQLite queries | ✓ Good — D-52 confirmed; no measured latency issue |
| Score supersede semantics | Re-run with new rubric preserves history | ✓ Good — version history UI lets users compare |
| Checkpoint-based job resilience | Long batch jobs must survive restarts | ✓ Good — orphan recovery on startup works |
| `useFilters` internal debounce + live rawValue | Simpler API; chips need live values during typing | ✓ Good — CatalogTab migration clean (D-18 preserved) |
| `FilterBar` receives `filters: UseFiltersReturn` (no hook call) | Avoids double-hook anti-pattern | ✓ Good — clean container/presenter split |
| Phase 7: module-level cache (no Context API) | Simpler invalidation, no provider wrapping | ✓ Good — invalidation audit required no component changes |
| Phase 7: class component ErrorBoundary (no dep) | React class boundaries are the only standard option | ✓ Good — zero new deps preserved |
| Two-stage cascade: no weight redistribution | Explicit weights; `vision_weight=0` = no vision, not rebalance | ✓ Good — D-10 test confirmed; no silent bugs |
| Phase 8 added mid-v2.1 | Description signal was broken; fix required for correct matching | ✓ Good — added without disrupting completed phases |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-29 — v3.0 Phase 9 complete (v3.0 cleanup gap closure — SIM-02 docs/dead-code synced, STACK-02 descope formalized, lint baseline cleared)*
