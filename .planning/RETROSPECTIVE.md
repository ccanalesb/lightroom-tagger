# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v2.0 — Advanced Critique & Insights

**Shipped:** 2026-04-15
**Phases:** 7 | **Plans:** 24

### What Was Built
- Structured per-perspective scoring (1–10) with Pydantic validation, LLM JSON repair, and photography-theory rubrics
- Configurable perspectives via REST API + CodeMirror markdown editor in Processing UI
- Scoring pipeline: single and batch jobs with version history, supersede semantics, catalog filter/sort by score
- Posting analytics: frequency timeline, day×hour heatmap, caption/hashtag stats, unposted gap view
- Identity service: best photos ranking, style fingerprint (radar + rationale tokens), "what to post next" suggestions with reason codes
- Unified Insights dashboard composing KPIs, score distributions, posting cadence, top photos via parallel API calls
- Job resilience: checkpoint persistence surviving restarts, orphan auto-recovery on startup

### What Worked
- **Phase dependency ordering** — building schema and validation (Phase 5) before pipeline (Phase 6) prevented rework; scoring handlers were thin wiring over solid foundations
- **Gap closure phases (10–11)** — audit-driven bug fix + verification phases caught real integration issues (batch_score selecting wrong images, missing pagination offset) before shipping
- **Parallel API composition (D-52)** — avoiding a monolithic dashboard endpoint kept SQLite queries fast and the frontend decoupled
- **Wave-based execution** — parallel plan execution within phases kept the 4-day timeline tight

### What Was Inefficient
- **SUMMARY.md extraction** — CLI tooling failed to extract meaningful accomplishments from SUMMARY files (parsed headers instead of content); manual curation was needed at milestone close
- **Phase 10–11 late additions** — the milestone audit surfaced bugs that should have been caught during Phase 6 execution; earlier integration testing would have avoided two extra phases
- **Mypy transitive failures** — every plan had to work around pre-existing mypy errors in `database.py` and `analyzer.py` via `--follow-imports=silent`; fixing the root would save cumulative time

### Patterns Established
- **Supersede semantics for versioned data** — `is_current` flag with explicit supersede on re-score; reusable pattern for any versioned analysis
- **Score-based catalog queries** — LEFT JOIN with `(score IS NULL) ASC` ordering pushes unscored items to the end; applicable to future queryable metadata
- **Checkpoint-based job resilience** — fingerprint + processed-set pattern works across all job types; new handlers get resilience by implementing two functions

### Key Lessons
1. Run integration tests across phase boundaries early, not just at milestone audit time — would have caught the batch_score SQL bug during Phase 6
2. Pre-existing lint/type debt compounds across every plan; dedicate one cleanup pass per milestone to reduce per-plan workaround cost
3. Photography-theory-grounded rubrics produced meaningfully different scores from generic prompts — domain-specific prompt engineering pays off

### Cost Observations
- Model mix: balanced profile throughout
- 7 phases executed in ~4 days (2026-04-12 → 2026-04-15)
- Parallel plan execution within phases kept wall-clock time low

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 4 | 21 | Established catalog + jobs + Instagram + AI pipeline |
| v2.0 | 7 | 24 | Added audit-driven gap closure phases; parallel API composition |

### Top Lessons (Verified Across Milestones)

1. Schema and validation foundations first, pipeline wiring second — reduces rework in both v1 (catalog before jobs) and v2 (score schema before scoring pipeline)
2. On-demand analysis with job queue scales better than batch-everything-upfront — validated in both describe (v1) and score (v2) workflows
