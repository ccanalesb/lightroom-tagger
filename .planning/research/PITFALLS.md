# Pitfalls Research

**Domain:** Adding structured AI scoring, posting/caption analytics, and insights dashboards to an existing Lightroom + Instagram-dump + on-demand AI critique web app (SQLite catalogs, app DB, batch jobs, React visualizer).  
**Researched:** 2026-04-12 (additive milestone); foundation items retained from 2026-04-10  
**Confidence:** HIGH for integration/perf/UX patterns common in LLM+SQLite products; MEDIUM for model-specific JSON quirks — re-validate per provider and pinned model version

## Critical Pitfalls

### Pitfall 1: Treating free-text critique rows as the same “thing” as structured scores

**What goes wrong:** Filters and rankings silently exclude most images; “best photos” lists look empty or random; users lose trust when some cards show scores and others do not.

**Why it happens:** Phase 4 persisted prose descriptions without a strict numeric contract. New UI assumes every analyzed image has `(perspective, dimension) → number`, but older rows only have text or a different JSON shape.

**How to avoid:** Version the analysis payload (`schema_version`, `prompt_version`, `job_type`). Store scores in explicit nullable columns or a normalized child table keyed by `(asset_id, perspective_id, metric_id, run_id)`. Backfill is a **separate** job with clear “partial coverage” UX. Never treat `0` as “missing”; use `NULL` + “not scored yet.”

**Warning signs:** SQL `WHERE composition_score > 0` drops unscored rows; charts show spikes at zero; aggregate “average score” includes defaulted zeros.

**Phase to address:** **Structured scoring schema & migration** (additive tables/columns, backfill job, nullable semantics, UI empty states).

---

### Pitfall 2: LLM “structured JSON” that parses in the lab but fails in production

**What goes wrong:** Jobs flip to failed or store garbage; intermittent 500s; partial writes leave commentary without scores or vice versa.

**Why it happens:** Ollama and smaller models often wrap JSON in fences, truncate mid-object, use alternate keys (`"Composition"` vs `"composition"`), emit ranges you did not ask for (`8.7/10`), or return arrays where you expected an object. OpenAI-compatible stacks differ on `response_format` / tool-calling support.

**How to avoid:** **Defense in depth:** (1) prompt contract with one worked example and “JSON only, no markdown”; (2) repair pass (strip fences, extract first `{…}` span); (3) **Pydantic validation** with `model_validate_json` after repair; (4) on failure, **one** bounded retry with a “fix your JSON” nudge or a smaller fallback model; (5) persist raw model text on failure for support. Prefer **two-step** flows for brittle models: short JSON-only scoring call, then optional prose call — or tool/function calling where reliably supported.

**Warning signs:** Rising failure rate when users switch models; logs full of `JSONDecodeError`; “successful” jobs with default-filled scores.

**Phase to address:** **LLM output contracts & provider adapters** (parsers, retries, telemetry, golden fixtures per provider).

---

### Pitfall 3: Single mega-prompt that outputs scores + long critique + analytics-style judgments

**What goes wrong:** Truncation wrecks JSON; scores drift with creative temperature; latency and token cost spike; hard to test.

**Why it happens:** One request tries to satisfy UI, dashboard aggregates, and narrative flair at once. Models prioritize fluent text and drop numeric rigor.

**How to avoid:** Split responsibilities: **scoring rubric** (low temperature, tight schema, short) vs **narrative critique** (can be warmer). If you must combine, require scores **first** in the schema so truncation loses tail prose, not numbers — still risky. Align with PROJECT.md: on-demand jobs — keep each job’s output bounded.

**Warning signs:** Parsed JSON missing trailing fields; UI shows scores but empty rationale; cost per image jumps after prompt “improvement.”

**Phase to address:** **Prompt library & job design** (split calls, token budgets, per-job metrics).

---

### Pitfall 4: Schema migration that rewrites hot paths or breaks existing describe jobs

**What goes wrong:** Deploy breaks in-flight jobs; old workers write incompatible rows; rollback is impossible; `.lrcat` untouched but app DB migrations fail mid-flight.

**Why it happens:** Adding columns with `NOT NULL` defaults, renaming JSON keys consumers expect, or migrating without **expand → dual-write → backfill → contract** steps.

**How to avoid:** Additive migrations only; new columns nullable; feature flags for new job handlers; readers tolerate old and new shapes until backfill completes. Coordinate job payload versioning with deployed API + worker. Test migration on a copy of production-sized `library.db`.

**Warning signs:** `OperationalError: no such column` after deploy; duplicate scoring runs; checksum mismatches between API and DB.

**Phase to address:** **Structured scoring schema & migration** (expand/contract, dual-read, migration tests).

---

### Pitfall 5: Analytics computed on every dashboard load from 38K+ row fact tables

**What goes wrong:** Timeouts, UI spinners, SQLite busy errors, whole-server stalls when multiple users refresh (even single-user can hurt if unlucky).

**Why it happens:** Ad-hoc `GROUP BY` over posts × images × scores without indexes; correlated subqueries; loading full time series in one response; ORM-style N+1 from the API layer.

**How to avoid:** Precompute **rollup tables** or nightly/incremental **materialized summaries** (counts by week/hour, caption length buckets, hashtag frequencies). Index foreign keys and filter columns (`posted_at`, `catalog_id`, `perspective_id`). Use **bounded** queries: last N weeks, paginated histograms, server-side downsampling for charts. Run heavy recomputation inside **jobs**, not HTTP handlers.

**Warning signs:** p95 API latency scales with catalog size; `EXPLAIN QUERY PLAN` shows full table scans; WAL grows during browsing.

**Phase to address:** **Analytics computation layer** (rollups, indexes, job-triggered refresh, API limits).

---

### Pitfall 6: Instagram timestamp / timezone semantics breaking “when you post” insights

**What goes wrong:** Heatmaps shift by hours; daylight-saving edges look like spikes; duplicate posts across timezone assumptions.

**Why it happens:** Exports mix UTC and local strings; DST gaps; user travels; parsing with `datetime` without explicit tz.

**How to avoid:** Normalize to **UTC** at ingest; store original offset string if present; document “display in local browser TZ” vs “stored UTC.” Test fixtures across DST boundaries. Deduplicate on stable export IDs, not `(date, caption)`.

**Warning signs:** Users say “I never post at 3am”; counts change after server TZ change; same post double-counted.

**Phase to address:** **Dump ingest & analytics** (ingest normalization, validation report, time-series tests).

---

### Pitfall 7: New scoring job types bolted on without idempotency and pipeline discipline

**What goes wrong:** Double charges (API), duplicate rows, deadlock with describe jobs, cancellation leaving corrupt partials, one stuck job type blocking the queue.

**Why it happens:** Reusing “describe” code paths without a distinct `job_kind`, missing unique constraint on `(asset_id, run_key)`, shared worker pool without fairness.

**How to avoid:** Define **idempotency keys** (asset + perspective set + model + prompt_version). Unique partial indexes or upsert semantics. Separate **queues or weighted fairness** so long vision batches do not starve quick tasks. Cooperative cancellation must roll back or mark partial rows explicitly (align with Phase 2 patterns). Feature-flag new handlers.

**Warning signs:** Retry storms; duplicate score rows; jobs stuck “running” after deploy; user sees interleaved progress for unrelated work.

**Phase to address:** **Jobs & pipeline integration** (job taxonomy, constraints, cancellation, observability).

---

### Pitfall 8: Dashboard that surfaces every chart because engineering could

**What goes wrong:** Cognitive overload; users ignore the product; performance suffers; misleading charts drive wrong conclusions.

**Why it happens:** Each stakeholder asks for one more widget; no primary story; charts share inconsistent date ranges or filters.

**How to avoid:** **One primary insight per view** with drill-down. Global date range + catalog scope controls shared via one context. Show **data coverage** (“scores available for 12% of catalog”) next to aggregates. Prefer a small set of battle-tested chart types (Recharts etc.) with accessible defaults. Empty states explain *why* (no dump, no scores, filter too narrow).

**Warning signs:** Support questions about conflicting numbers on two tabs; users ask “which chart is true?”; Lighthouse scores tank.

**Phase to address:** **Insights dashboard UX** (information architecture, shared filter context, loading skeletons).

---

### Pitfall 9: Scores presented as objective truth instead of model-relative signals

**What goes wrong:** Users argue with numbers; reputational harm; churn when model changes “rewrite history.”

**Why it happens:** UI copies like “quality: 7.2” without model/prompt context; aggregating across incompatible model versions.

**How to avoid:** Label scores as **“AI estimate (model X, vY)”**; freeze **ranking cohorts** to a single model version or show version filter. When the model changes, start a new **scoring generation** rather than overwriting silently (or show “upgraded scoring” badge + diff).

**Warning signs:** Side-by-side same image, different scores, no explanation; historical trends jump after deploy.

**Phase to address:** **Insights dashboard UX** + **LLM output contracts** (version surfacing, cohort rules).

---

### Pitfall 10: Photographer “identity” and caption analytics leaking wrong-catalog or PII-adjacent data

**What goes wrong:** Client wedding themes appear in personal “voice” summary; exported screenshots of dashboards expose private captions.

**Why it happens:** Cross-catalog aggregates without `catalog_id` scope; dashboards that echo raw captions/hashtags without consideration.

**How to avoid:** Default **strict catalog scope** (per PROJECT.md multi-catalog intent). Cross-catalog identity remains explicit opt-in with clear copy. Truncate or aggregate captions for display; avoid logging full caption text at info level.

**Warning signs:** Stats change when switching catalogs in unintuitive ways; logs contain identifiable captions.

**Phase to address:** **Photographer identity & analytics** (scoping rules, privacy review, API guards).

---

### Pitfall 11 (foundation): Treating `.lrcat` as a generic SQLite file

**What goes wrong:** Corruption, locks, or Lightroom UI inconsistency after writes.

**Why it happens:** Adobe-specific schema, WAL, long-lived locks — same as always when extending the app.

**How to avoid:** Read-only default; minimal keyword writes; backup `.lrcat` + `-wal`/`-shm`; do not write while Lightroom holds the catalog without a tested strategy.

**Warning signs:** `database is locked`; Lightroom repair dialogs after tool use.

**Phase to address:** **Catalog & SQLite foundation** (ongoing; unchanged by v2 features except avoiding new write surfaces).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Storing scores only inside a JSON blob | Faster first ship | Unindexed analytics; fragile queries | Spike only; promote hot fields to columns |
| `NOT NULL` score columns default `0` | Simple SQL | Fake zeros break analytics and trust | Never for AI-derived scores |
| Parsing JSON with regex only | Fewer deps | Fragile across models | Never in production hot path |
| Recomputing all aggregates on each request | No migration | Timeouts at 38K+ | Dev-only tiny datasets |
| One job type for describe + score + identity | Less code | Unclear retries, huge payloads, failure blast radius | Early prototype; split before scale |
| Hard-coded chart buckets (e.g., hours) | Quick viz | Wrong for non-local TZ stories | Replace with stored UTC rollup + client TZ |
| Skipping `model_id` / `prompt_version` on score rows | Smaller rows | Cannot explain or reproduce rankings | Never for persisted scores |
| Direct `.lrcat` writes without backup job | Faster MVP | Irrecoverable corruption | Never for production writes |
| Single hard-coded Instagram export path | Quick demo | Breaks other locales | Spike only |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Existing describe jobs | Overwriting text when re-run for scores | Separate columns or child records; idempotent merge rules |
| Job queue | New handler without version gating | Deploy API + worker together; tolerate unknown `job_type` gracefully |
| Ollama | Assuming JSON mode parity with OpenAI | Capability matrix per model; tests on smallest local model you support |
| OpenAI / OpenRouter | Ignoring `response_format` failures | Fallback parser path; log provider error taxonomy |
| SQLite (`library.db`) | Analytics joins without indexes | Index FKs and time dimensions; EXPLAIN before ship |
| React dashboard | Each tab owns date filter state | Lift catalog + range context; sync to URL for shareability |
| Instagram dump | Parsing timestamps as naive local | Normalize to UTC at ingest; carry source tz metadata |
| Socket.IO / progress | Mixing job kinds in one channel without labels | Typed events; UI distinguishes scoring vs describe |
| Pydantic models | Drift between API schema and DB JSON | Single shared package or codegen; contract tests |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full-table scan on scores | Slow filters / “top N” endpoints | Indexes on `(catalog_id, metric, value)` or precomputed ranks | 10k–50k+ rows |
| Correlated subquery per image | API latency ∝ images | JOIN + GROUP BY or rollup table | Medium catalogs |
| Serializing large aggregates to JSON | Huge payloads, slow TTFB | Pagination, downsampling, server-side binning | Year-long minute-level series |
| Opening new DB connection per chart query | CPU churn | Connection pool / single conn per request scope | Concurrent dashboard loads |
| Writing rollups synchronously after each score | Write amplification | Trigger rollup refresh job; debounce batch updates | High job throughput |
| Unbounded “caption NLP” in SQL | LIKE `%foo%` scans | Tokenize at ingest; index tokens or use FTS | Large caption tables |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Scores without model/version context | Mistrust, confusion | Badge + tooltip + filter by scoring generation |
| Mixing analyzed vs unscored in same average | “Why is my average 4?” | Coverage callout; separate “scored subset” metrics |
| Heatmaps without sample size | Misread sparse cells | Show counts per bucket; suppress low-N cells |
| Competing date ranges across tabs | “Numbers don’t match” | Single global range control |
| Dumping raw LLM “insights” as facts | Overconfidence | Softer copy; cite based on which data subset |
| No empty state for dashboard | Feels broken | Explain prerequisites (dump, match, score jobs) |
| Auto-run expensive scoring from dashboard mount | Surprise cost | Explicit actions; show estimates where possible |

## "Looks Done But Isn't" Checklist

- [ ] **Schema:** Old describe rows still readable; new score rows nullable; no silent `0` for missing scores
- [ ] **Parsing:** Golden tests for JSON output across **each** supported provider + at least two models
- [ ] **Jobs:** Idempotency verified — retry does not duplicate scores; cancellation leaves no half-linked rows
- [ ] **Analytics:** `EXPLAIN QUERY PLAN` clean for top dashboards; rollup refresh tested on ≥38K assets
- [ ] **Time:** DST + UTC ingest fixtures pass; heatmap matches user expectation in another TZ (sanity test)
- [ ] **UI:** One shared filter context; “coverage %” shown next to aggregates; empty states for each panel
- [ ] **Ranking:** “Best photos” uses explicit cohort rule (model version + date range + catalog scope)
- [ ] **Performance:** Cold dashboard load acceptable; no full-catalog scan per refresh
- [ ] **Regression:** Existing describe / match / keyword flows unchanged in integration tests
- [ ] **Foundation:** Still true — `.lrcat` read-only except audited keyword writes; backup before write

## Pitfall-to-Phase Mapping

Map the **Prevention track** to your roadmap phase IDs when `ROADMAP.md` is updated for v2.0.

| Pitfall | Prevention track | Verification |
|---------|------------------|--------------|
| Free-text vs structured score semantics | Structured scoring schema & migration | Nullable columns; backfill report; UI coverage indicators |
| LLM JSON parse failures | LLM output contracts & provider adapters | Golden files; failure telemetry; retry bounds |
| Mega-prompt truncation / cost | Prompt library & job design | Token metrics; split-call tests |
| Breaking migrations / dual versions | Structured scoring schema & migration | Migration test on copy DB; expand/contract checklist |
| Heavy ad-hoc aggregates | Analytics computation layer | EXPLAIN plans; load test; rollup freshness job |
| Timestamp / TZ bugs | Dump ingest & analytics | Fixture tests; user-visible validation summary |
| Job pipeline interference | Jobs & pipeline integration | Load + cancel tests; unique constraints |
| Dashboard overload / misleading viz | Insights dashboard UX | UX review; single-story-per-view; sample sizes |
| Model-relative score trust | Insights UX + LLM contracts | Version labels; cohort filters; history jump detection |
| Cross-catalog bleed | Photographer identity & analytics | API scoped by `catalog_id`; opt-in cross-catalog rules |
| `.lrcat` safety (foundation) | Catalog & SQLite foundation | Lock/backup checklist; LR version matrix |

## Sources

- Project intent and v2.0 scope — `.planning/PROJECT.md` (2026-04-11)
- Prior foundation pitfalls — same file lineage 2026-04-10 (Lightroom SQLite, matching, cost control)
- Common LLM production patterns — structured output validation, repair passes, provider capability variance (industry practice; re-verify per provider doc)
- SQLite analytics guidance — indexes, rollups, avoid correlated subqueries at scale (SQLite query planner behavior)
- Codebase integration notes — `.planning/codebase/INTEGRATIONS.md` (if present)

---
*Pitfalls research for: Lightroom Tagger & Analyzer — additive structured scoring, analytics, and insights on an existing catalog + jobs + AI stack*  
*Researched: 2026-04-12*
