# Lightroom Tagger & Analyzer

## What This Is

A web application that connects your Lightroom catalog with Instagram to track what you've published and provides AI-powered artistic analysis of your photography. It helps you understand your work from multiple critical perspectives, identify patterns in what performs well, and decide what to shoot or post next.

## Core Value

Know which catalog images are posted on Instagram and get artistic critique that helps you understand your photographic voice and posting strategy.

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

### Active

- [ ] Match Instagram dump images to Lightroom catalog entries
- [ ] Confirm matches and write "posted" keyword back to Lightroom catalog
- [ ] Generate on-demand AI descriptions for catalog images
- [ ] Analyze photos from artistic perspectives (composition, narrative, rhythm)
- [ ] Support multiple Lightroom catalogs with context switching
- [ ] Identify "best photos" combining AI scores and Instagram performance
- [ ] Extract and display Instagram analytics from dump data
- [ ] Provide unified photographer identity analysis across all catalogs
- [ ] Multi-perspective critique (street photographer, editor, publisher views)
- [ ] On-demand analysis jobs (single image or timeframe-based batches)

### Out of Scope

- Instagram API integration or scraping — Using export-based dumps instead
- Technical EXIF analysis — Focus is artistic critique, not camera settings
- Lightroom plugin — Web app keeps Lightroom as-is, only writes keywords
- Real-time Instagram syncing — Manual dump workflow is sufficient
- Batch analysis of entire catalog upfront — On-demand only to control costs

## Context

### Workflow
The user is a photographer managing work across multiple Lightroom catalogs (personal portfolio, client work like weddings, etc.). They post selectively to Instagram and want to understand both sides of their practice: what they publish vs what stays in the catalog.

### Current State
- Phase 1 complete — catalog browsing, filtering, and registration working via visualizer UI
- Phase 2 complete — job lifecycle, cooperative cancellation, catalog backup/lock guard, error severity
- Read-only catalog enforcement via SQLite URI `mode=ro` prevents accidental writes
- Library DB keys unified with `YYYY-MM-DD_filename` format, migration with backup
- Instagram presence with analytics data available via export dumps
- Testing phase using cheap AI models (Ollama local/cloud)
- Need to identify posting patterns and improve artistic decision-making

### Instagram Dump Format
User provides Instagram export dumps containing images and analytics. App matches these to Lightroom catalog entries by comparing images, then writes keywords back to the SQLite catalog file.

### Analysis Philosophy
Critique should come from defined perspectives (street photographer, editor, publisher) with starting prompts refined by photography theory from books and publications. Focus is artistic execution and narrative fit, not technical metrics.

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
| Export-based Instagram sync | Avoids API limitations, user owns data | — Pending |
| Direct SQLite catalog writes | Only way to add keywords to Lightroom | — Pending |
| On-demand analysis | Controls AI costs, scales with usage | — Pending |
| Web app (not plugin) | Keeps Lightroom unchanged, easier deployment | — Pending |
| Artistic over technical | User wants style/narrative critique, not EXIF analysis | — Pending |

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
*Last updated: 2026-04-10 after Phase 2 completion*
