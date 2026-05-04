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

## Milestone: v2.1 — Polish & Consolidate

**Shipped:** 2026-04-23
**Phases:** 9 (including 4.1 + Phase 8 added mid-milestone) | **Plans:** 35 | **Timeline:** 7 days

### What Was Built
- Matching flow polish: modal stays open on reject, auto-advances multi-candidate groups, unvalidated-first sort by newest Instagram `created_at`
- Job queue UX: skeleton loading, log truncation + expansion, paginated queue with pinned page, unified Analyze job (describe → score with sub-checkpoints + 50/50 progress)
- Reusable filter framework: `useFilters(schema)` with 4 primitive types, `enabledBy` cascades, internal debounce, `toQueryParams`; `<FilterBar>` with chips + clear-all; CatalogTab + InstagramTab migrated
- Identity & Insights clarity: posted overlay badge on BestPhotosGrid, narrative reorder (fingerprint → best → post next) with section intros, Dashboard Top Photos Unposted | Posted | All tabs
- Images page badge/card unification: consolidated badge API, inline-in-description pattern, match cards consistent with CatalogImageCard
- React Suspense data layer: module-level cache, `useQuery` throw-promise, `invalidate`/`invalidateAll`, `<ErrorBoundary>` + `<ErrorState>`; full app migration (Identity, Images, Processing, Analytics, Dashboard); zero new npm deps
- Two-stage cascade matching: LEFT JOIN ai_summary, `compare_descriptions_batch`, description→vision cascade with weighted merge, `skip_undescribed` option

### What Worked
- **Inserting Phase 4.1 mid-milestone** — adding InstagramTab filter migration as a decimal phase kept the filter framework phase (4) focused while immediately proving the framework on a second real consumer; minimal disruption
- **Adding Phase 8 mid-milestone** — recognizing the broken description signal was blocking correct match scoring and inserting a fix phase cleanly; demonstrates the GSD roadmap is appendable without disrupting completed work
- **React Suspense data layer as standalone phase** — treating DATA-01 as cross-cutting with no roadmap deps kept it isolated; 6-wave execution was clean because the primitives (wave 1) were small and the migrations (waves 2–5) were mechanical
- **`useFilters` live rawValue + committed debounced value duality** — the two-value approach (chips show live, queries use committed) solved the debounce UX correctly without special-casing; discovered while writing Phase 4 CONTEXT

### What Was Inefficient
- **Backlog entry 999.1 was stale at close** — Phase 7 plans deferred to backlog were later executed, but the backlog entry was never cleaned up; should delete resolved backlog items when the work is done rather than accumulating stale entries
- **Phase 3 missing SUMMARY.md files** — execution was confirmed complete (VERIFICATION.md status: complete, STATE.md, git commits) but individual plan SUMMARY.md files were never written; VERIFICATION.md adequately proves completion but creates an asymmetry with other phases
- **REQUIREMENTS.md traceability table not updated during execution** — JOB-03..06 and FILTER-01..02 stayed "Pending" in the table even after phases 2–4 completed; should update the table immediately after each phase closes, not defer to milestone close
- **Phase 7 re-execution after backlog deferral** — Phase 7 was planned, deferred to backlog 999.1 when Phase 5 was prioritized, then later re-executed from scratch; the original PLAN.md was not reused; some duplicate planning effort

### Patterns Established
- **Decimal phases for mid-milestone insertions** — `4.1` naming clearly signals insertion order and milestone membership without renumbering subsequent phases
- **`useFilters` container/presenter split** — `FilterBar` receives a `UseFiltersReturn`, it never calls `useFilters` itself; composable pattern applicable to any future filterable list
- **React Suspense data layer pattern** — module-level `Map` cache + throw-promise `useQuery` + class `ErrorBoundary` + `invalidate(key)` mutations; zero-dep, zero-Context, pure React; reusable for any data-heavy frontend
- **Phase 7 wave structure** — primitives wave → per-page migration waves → audit wave; applicable to any cross-cutting infrastructure migration with a clear before/after inventory

### Key Lessons
1. Clean up backlog entries when the underlying work is completed — stale 999.x entries accumulate noise and can mislead future `/gsd-next` detection
2. Write plan SUMMARY.md files immediately after each plan executes, not after the phase; VERIFICATION.md is sufficient but breaks the pattern expected by future tooling
3. Update REQUIREMENTS.md traceability after each phase closes, not only at milestone archive time — reduces the "cleanup debt" at close
4. The filter framework `useFilters` / `FilterBar` split is the right abstraction: future tab migrations are purely mechanical (swap useState with useMemo schema + useFilters + FilterBar)

### Cost Observations
- Model mix: balanced profile throughout
- 9 phases executed in 7 days (2026-04-17 → 2026-04-23)
- Phase 8 (cascade matching) added mid-milestone without disrupting prior completed phases
- Sessions: multiple daily sessions; Phase 7 executed in one focused session

---

## Milestone: v3.0 — Intelligent Discovery

**Shipped:** 2026-05-04
**Phases:** 14 (1–11 + 5.1, 5.2, 7.1) | **Plans:** 56 | **Timeline:** 12 days (2026-04-23 → 2026-05-04)

### What Was Built
- Natural language search: NL-to-SQL filter (Pydantic-validated), FTS5 keyword search, semantic hybrid search (text embeddings + RRF), multi-tool chat search with typed tools and capability detection
- Photo stacking: burst grouping by `date_taken`, `image_stacks`/`image_stack_members` schema, three-tier representative selection, split/merge/change-rep UI with confirm/undo
- Visual attribute tags: `dominant_colors`, `mood_tags`, `has_repetition` extracted at describe time; catalog filter facets
- CLIP visual similarity: sqlite-vec KNN, materialized similarity groups in catalog cache pipeline, stack badges + expand/collapse in Images UI
- Stack-aware Instagram matching: compare against representatives, apply confirmed matches stack-wide, non-destructive conflict skips
- Catalog cache pipeline: `catalog_cache_build` composite job (embed → stack-detect → similarity) with stage banners, per-stage re-run, observable candidate counts
- Phase 7.1 remediation: 3 targeted fixes for production-safety regressions from Phase 7
- Phases 9–11 gap closure: REQUIREMENTS.md sync, dead code cleanup, CLIP recall benchmark (100.0% on 239 pairs), deferred polish (a11y, copy centralization, discoverability)

### What Worked
- **Milestone audit + gap closure pattern** — running `/gsd-audit-milestone` before declaring v3.0 done surfaced real gaps (SIM-02 pivot documentation, MATCH-02 unquantified, Phase 7/8 deferred debt); gap closure phases 9–11 cleared everything cleanly
- **sqlite-vec as CLIP store** — no FAISS required; KNN recall at 100% on 239 validated pairs; avoids native build complexity on macOS/NAS environments
- **Recall-first shortlist design** — generous `clip_top_k` default (50) + measured recall before tightening; the right order of operations for embedding pre-filters
- **Code review inline fix rule** — workspace rule requiring medium+ findings be fixed before phase close caught real bugs (Instagram cohort mismatch, ConfirmModalFrame missing dialog semantics) that would otherwise have shipped as debt
- **Decimal phases (5.1, 5.2, 7.1)** — inserted without renumbering; 5.1 for Search UI polish, 5.2 for tool-calling search architecture pivot, 7.1 for urgent Phase 7 production fixes; all three proved the insertion pattern reliable

### What Was Inefficient
- **Phase 7 → 7.1 rework cycle** — Phase 7 shipped with production-safety defects that required a full remediation phase (7.1); more rigorous plan-checker iteration on Phase 7 would have caught these inline
- **SIM-02 pivot mid-milestone** — quick task `260427-f75` pivoted the "More like this" UX from on-demand to materialized after Phase 6 verified on-demand; the pivot was correct but required retroactive REQUIREMENTS.md and VERIFICATION.md surgery in Phase 9
- **v3.0 roadmap grew to 14 phases** — 3 of the 14 were inserted gap-closure phases; could have been avoided with sharper requirements on SIM-02 UX and earlier MATCH-02 quantification
- **SUMMARY.md accomplishment extraction** — CLI still extracts headers/labels instead of content for some plan types; manual curation required at milestone close (same issue as v2.0)

### Patterns Established
- **Catalog cache pipeline** — `batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity` chain with per-stage re-run; pattern reusable for future multi-stage pipeline jobs
- **CLIP shortlist as pre-filter contract** — `shortlist_catalog_candidates_by_clip(top_k)` intersects KNN with allowed keys; insert before any costly judgment; measure recall before tuning `top_k`
- **Milestone audit → gap closure phases** — run `/gsd-audit-milestone` after last functional phase; create numbered gap-closure phases (9, 10, 11) for docs, quantitative validation, and deferred polish; cleaner than open-ended "cleanup"
- **Code review inline fix rule** — workspace rule `.cursor/rules/gsd-code-review-fix.mdc` enforces medium+ findings are fixed before close; this caught real bugs in Phase 11

### Key Lessons
1. Plan-checker rigor on complex phases pays more than extra verification phases later — Phase 7 defects that generated Phase 7.1 would have been caught with one more plan-checker iteration
2. Quantify claims before calling a requirement complete — MATCH-02 "≥10× fewer candidates" shipped unverified; Phase 10 benchmark was needed to replace the placeholder with measured 100% recall
3. Pivot decisions mid-milestone (like SIM-02 UX) are fine but require explicit re_verification block annotation and REQUIREMENTS.md text update; don't assume VERIFICATION.md is correct after a post-verification code change
4. sqlite-vec + sentence-transformers is sufficient for personal-catalog scale; skip the FAISS evaluation until a measured latency problem exists

### Cost Observations
- 14 phases executed in 12 days (2026-04-23 → 2026-05-04)
- 3 phases were gap closure (phases 9, 10, 11) — ~21% of phases were debt paydown
- Phase 7.1 (remediation) added ~1 day of recovery time; avoidable with stricter plan-checking on Phase 7
- 289 commits total; wave-based parallel execution kept wall-clock time under 2 weeks for a very large feature set

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 4 | 21 | Established catalog + jobs + Instagram + AI pipeline |
| v2.0 | 7 | 24 | Added audit-driven gap closure phases; parallel API composition |
| v2.1 | 9 | 35 | Polish + reusable framework + Suspense data layer + cascade matching |
| v3.0 | 14 | 56 | NL search + stacking + CLIP similarity + catalog cache pipeline; 3 gap-closure phases (21% of total) |

### Top Lessons (Verified Across Milestones)

1. Schema and validation foundations first, pipeline wiring second — reduces rework in both v1 (catalog before jobs) and v2 (score schema before scoring pipeline)
2. On-demand analysis with job queue scales better than batch-everything-upfront — validated in both describe (v1) and score (v2) workflows
3. Decimal phases (4.1) and mid-milestone appendable phases (Phase 8) work cleanly — GSD roadmap is mutable without disrupting completed work
4. Keep planning artifacts current (traceability table, backlog cleanup, SUMMARY.md) during execution, not as end-of-milestone debt — accumulation makes milestone close messier than it needs to be
5. Plan-checker rigor on complex phases > recovery phases later — Phase 7 defects requiring Phase 7.1 were avoidable with one more checker iteration
6. Quantify requirement claims before marking complete; `≥10×` unverified placeholders create debt that must be paid at milestone audit time
