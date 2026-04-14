# Lightroom Tagger & Analyzer

## What This Is

A web application that connects your Lightroom catalog with Instagram to track what you've published and provides AI-powered artistic analysis of your photography. It helps you understand your work from multiple critical perspectives, identify patterns in what performs well, and decide what to shoot or post next.

## Core Value

Know which catalog images are posted on Instagram and get artistic critique that helps you understand your photographic voice and posting strategy.

## Current Milestone: v2.0 Advanced Critique & Insights

**Goal:** Deepen AI critique quality with structured scoring and new perspectives, then surface patterns and insights across the catalog and posting history.

**Target features:**
- Refine critique prompts with photography theory; structured scores (composition, narrative, rhythm) as queryable fields
- New critique perspectives beyond street/editor/publisher (e.g., color theory, emotional impact, series coherence)
- Per-perspective numeric scoring persisted and filterable
- Posting frequency and timing pattern analysis from dump timestamps
- Caption/hashtag style analysis
- "Best photos" ranking based on aggregated AI perspective scores
- Photographer identity analysis — recurring themes, style fingerprint across catalog
- "What to post next" suggestions based on catalog analysis vs posting history gaps
- Insights dashboard UI to visualize trends and patterns

## Requirements

### Validated

- [x] Register and browse Lightroom catalog safely with read-only enforcement (Validated in Phase 1: Catalog Management)
- [x] Paginate and filter catalog photos by keyword, rating, date range, color label (Validated in Phase 1: Catalog Management)
- [x] Stable photo identity across sessions via unified composite keys (Validated in Phase 1: Catalog Management)
- [x] Observable job lifecycle with status visible as queued/running/complete/failed (Validated in Phase 2: Jobs & System Reliability)
- [x] Job cancellation with cooperative threading.Event propagation (Validated in Phase 2: Jobs & System Reliability)
- [x] Backup-before-write with timestamped rotation capped at two files (Validated in Phase 2: Jobs & System Reliability)
- [x] Actionable error severity classification with UI badges (Validated in Phase 2: Jobs & System Reliability)
- [x] Lightroom-open guardrail via lock file detection before catalog writes (Validated in Phase 2: Jobs & System Reliability)

- [x] Match Instagram dump images to Lightroom catalog entries (Validated in Phase 3: Instagram Sync)
- [x] Confirm matches and write "posted" keyword back to Lightroom catalog (Validated in Phase 3: Instagram Sync)
- [x] Generate on-demand AI descriptions for catalog images (Validated in Phase 4: AI Analysis)
- [x] On-demand analysis jobs (single image or timeframe-based batches) (Validated in Phase 4: AI Analysis)
- [x] Multi-perspective critique (street photographer, editor, publisher views) (Validated in Phase 4: AI Analysis)

### Validated (v2.0)

- [x] Structured artistic scoring (1-10 per perspective) as queryable fields (Validated in Phase 6: Scoring Pipeline)
- [x] New critique perspectives: color theory added to street/documentary/publisher (Validated in Phase 5: Structured Scoring Foundation)
- [x] Photography-theory-refined prompts with Itten, Freeman, Berger citations (Validated in Phase 5: Structured Scoring Foundation)
- [x] Per-perspective numeric scoring persisted and filterable/sortable in catalog UI (Validated in Phase 6: Scoring Pipeline)
- [x] Posting frequency and timing pattern analysis from Instagram dump timestamps (Validated in Phase 7: Posting Analytics)
- [x] Caption and hashtag style analysis (Validated in Phase 7: Posting Analytics)
- [x] "Best photos" ranking by aggregated AI perspective scores (Validated in Phase 8: Identity & Suggestions)
- [x] Photographer identity analysis — style fingerprint from score patterns (Validated in Phase 8: Identity & Suggestions)
- [x] "What to post next" suggestions based on catalog vs posting gaps (Validated in Phase 8: Identity & Suggestions)
- [x] Insights dashboard with KPI row, score distributions, posting cadence, quick-nav (Validated in Phase 9: Insights Dashboard)

### Deferred (future)

- [ ] Support multiple Lightroom catalogs with context switching
- [ ] Unified photographer identity view across catalogs
- [ ] Instagram engagement data (likes/saves) — requires API or manual entry

### Out of Scope

- Instagram API integration or scraping — Using export-based dumps instead
- Technical EXIF analysis — Focus is artistic critique, not camera settings
- Lightroom plugin — Web app keeps Lightroom as-is, only writes keywords
- Real-time Instagram syncing — Manual dump workflow is sufficient
- Batch analysis of entire catalog upfront — On-demand only to control costs
- Per-post engagement metrics from dumps — Instagram exports don't include likes/saves/comments counts

## Context

### Workflow
The user is a photographer managing work across multiple Lightroom catalogs (personal portfolio, client work like weddings, etc.). They post selectively to Instagram and want to understand both sides of their practice: what they publish vs what stays in the catalog.

### Current State
- v1.0 complete — Phases 1-4: catalog management, jobs, Instagram sync, AI descriptions
- v2.0 complete — Phases 5-9: structured scoring, posting analytics, identity/suggestions, insights dashboard
- Phase 10: bug fixes — batch_score non-force path uses correct image selection, suggestions endpoint wired with offset/total pagination, identity aggregation restricted to catalog-only scores
- Phase 11: verification & documentation — formal VERIFICATION.md for Phases 6-9, all 17 v2 requirements marked Complete with traceability
- Phase 5: image_scores/perspectives schema, Pydantic validation with LLM repair, 4 theory-grounded rubrics, perspectives REST API + CodeMirror UI, job checkpointing, orphan recovery
- Phase 6: scoring pipeline (single_score + batch_score jobs), score REST API, catalog modal scores panel with version history, catalog filter/sort by score
- Phase 7: posting analytics — frequency timeline, day-of-week × hour heatmap, caption/hashtag stats, unposted catalog gap view
- Phase 8: identity service — best photos ranking, style fingerprint (radar chart + rationale tokens), what-to-post-next suggestions with reason codes
- Phase 9: unified Insights dashboard composing KPIs, score distributions, posting cadence, top photos, quick-nav cards
- Read-only catalog enforcement via SQLite URI `mode=ro` prevents accidental writes
- Library DB keys unified with `YYYY-MM-DD_filename` format, migration with backup
- AI providers configurable with health probes and separate description defaults
- Perspectives configurable via Processing UI; critique prompts built dynamically from DB
- Job checkpointing persists progress for crash recovery; orphaned jobs auto-resume if checkpointed

### Instagram Dump Format
User provides Instagram export dumps containing images, captions, timestamps, and EXIF. App matches these to Lightroom catalog entries by comparing images, then writes keywords back to the SQLite catalog file. Note: Instagram exports do NOT include per-post engagement metrics (likes, saves, comments) — analytics are derived from posting patterns and AI scores only.

### Analysis Philosophy
Critique should come from defined perspectives (street photographer, documentary, publisher, color theory) with starting prompts refined by photography theory from books and publications. Perspectives are configurable via the Processing UI with CodeMirror markdown editing. Focus is artistic execution and narrative fit, not technical metrics.

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
*Last updated: 2026-04-14 — Phase 11 complete (verification & documentation update — all v2 requirements formally verified)*
