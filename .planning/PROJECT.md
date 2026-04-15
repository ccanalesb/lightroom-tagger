# Lightroom Tagger & Analyzer

## What This Is

A web application that connects your Lightroom catalog with Instagram to track what you've published and provides AI-powered structured artistic analysis of your photography. It scores images across configurable critique perspectives (street, documentary, publisher, color theory), surfaces your photographic identity through style fingerprints and best-photo rankings, analyzes posting patterns, and suggests what to shoot or post next — all from a unified insights dashboard.

## Core Value

Know which catalog images are posted on Instagram and get structured artistic critique that helps you understand your photographic voice and posting strategy.

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
- ~32K LOC across Python backend and React/TypeScript frontend
- Tech stack: Flask + SQLite (catalog read-only, library DB read-write), React 19 + Vite + Recharts + CodeMirror
- 4 configurable critique perspectives with photography-theory rubrics
- Pydantic-validated structured output with deterministic + LLM JSON repair
- Job checkpointing and orphan recovery for crash resilience
- No known tech debt or open blockers

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
*Last updated: 2026-04-15 after v2.0 milestone*
