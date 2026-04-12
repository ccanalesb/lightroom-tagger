# Research Summary — v2.0 Advanced Critique & Insights

**Milestone:** v2.0 Advanced Critique & Insights  
**Synthesized:** 2026-04-12  
**Inputs:** `STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `.planning/PROJECT.md`

---

## Executive Summary

The v2.0 milestone extends Lightroom Tagger’s validated foundation—Flask + dual SQLite, background jobs, multi-perspective vision critique, and Instagram dump matching—with **structured numeric rubrics**, **photography-theory-grounded prompts**, **posting and caption analytics** derived from export data (not engagement metrics), and an **insights dashboard** in the existing React visualizer. Research agrees that the core runtime should stay intact: scores and aggregates live in **library.db** alongside `images`, `matches`, `instagram_dump_media`, and `image_descriptions`; job orchestration remains in **visualizer.db**; and all AI outcomes should continue through a **single write funnel** (`store_image_description` or a thin extension) so catalog filters and charts see one consistent truth.

Product and technical research converge on a **bounded** first release: a strict JSON contract per perspective (axes + scores + short rationales + `prompt_version` / rubric identity), **queryable** persisted fields for filter/sort, at least one **new critique perspective** end-to-end, **posting cadence / timing** visualization from matched dump timestamps, and a **thin insights surface** (a few high-signal charts with drill-down to the catalog). Heavier items—full multi-perspective comparison matrices, evidence-linked identity synthesis, explainable “what to post next,” and rich caption NLP—are sequenced **after** scores and aggregates are stable, because they depend on coverage, version cohorts, and trustworthy rollups.

The main risks are **semantic** (mixing legacy prose-only rows with new scores), **operational** (LLM JSON drift, mega-prompts, migration breakage), and **scale** (ad-hoc analytics over tens of thousands of rows, timezone semantics on dumps). Mitigations map cleanly to phased work: versioned payloads, nullable score columns or a normalized score table, defense-in-depth parsing, additive migrations, pre-aggregated or job-refreshed rollups, UTC-normalized ingest, idempotent job keys, and dashboard UX that shows **coverage** and **model/prompt context** rather than implying objective “quality” or unavailable engagement data.

---

## Key Findings

### Recommended Stack

- **Backend:** **Pydantic** (e.g. ≥2.12.5) as the canonical contract for critique payloads and API shapes; **openai** Python SDK upgraded to the v2 line (e.g. ≥2.31.0) for structured parsing where the endpoint supports it. Optional: **instructor** for uniform retry/validation across providers, **json-repair** for salvage parsing on weaker local models, **pandas** when SQL-only aggregates become unwieldy (watch Python floor vs pandas 3.x).
- **Frontend:** **Recharts** for dashboard charts; **TanStack Query** for caching/refetch of many insight endpoints; **date-fns** for browser-side bucketing when needed; **Zod** (or stay on 3.x if peers require) to validate critical DTOs at the UI boundary.
- **Explicit non-goals for this milestone:** LangChain/LlamaIndex for this bounded flow; Prophet / separate TSDB for exploratory posting analytics; full OpenAPI codegen until contracts stabilize; image embeddings as the first “style fingerprint” implementation.

### Expected Features

- **Table stakes:** Scores **with** visible rationales; **consistent rubric and scale** with stored `prompt_version` / `rubric_id`; **perspective-scoped** axes; **re-run / supersede** semantics; catalog **filter & sort** on scores; honest labeling of **posting behavior** (not reach); job/error visibility consistent with existing describe jobs.
- **Differentiators:** Queryable multi-axis scores plus narrative; theory-grounded rubrics; additional perspectives (color, emotion, series); posting patterns **without** the Instagram API; **catalog ↔ posted** gap analysis via match keys; optional identity and “what to post next” with **evidence** and explainability.
- **Anti-patterns to avoid:** Single “master quality” score; scores without coverage/confidence awareness; engagement optimization from dumps; mandatory full-catalog scoring; opaque recommenders; vague identity labels without examples.
- **MVP (v2) vs later:** Launch with schema + persistence + filters, refined prompts, one new perspective, posting timing viz, thin dashboard; defer full perspective sets, caption panels, weighted “best photos,” identity, and suggestions until validation.

### Architecture Approach

- **Placement:** Extend `analyzer.py` / `vision_client.py` / `description_service.py` / `database.py`; add **`scoring_schema.py`** (validation/coercion), optional **`prompt_templates.py`**, **`insights` service** (pure SQL + Python rollups) and **`api/insights.py`**; **Insights UI** as `/insights` or an expanded dashboard; optional **`insights_cache`** in library.db if rollups are hot.
- **Patterns:** Hybrid storage—keep rich JSON in existing columns; add **indexed** columns or a **child table** for hot filters; persist **prompt_version** (and optionally schema version) for cohort-safe aggregations; read-only analytics on **library.db**; backfill via jobs mirroring batch describe.
- **Build order (dependency-respecting):** (1) prompt + schema + tests, (2) library DB migration + `store_image_description`, (3) wire pipeline and jobs, (4) catalog API + UI filters, (5) insights API (posting + score histograms), (6) insights UI + chart deps, (7) higher-level ranking/identity/caption AI on top.

### Critical Pitfalls

1. **Treating legacy free-text rows like full structured scores** → nullable semantics, backfill jobs, explicit “not scored” UX; never use `0` for missing.
2. **Fragile LLM JSON in production** → repair pass, Pydantic validation, bounded retries, golden tests per provider/model; consider split scoring vs narrative calls.
3. **Mega-prompts** → truncation and cost; split responsibilities and keep scoring tight.
4. **Breaking migrations / dual worker versions** → additive columns, dual-read, expand/contract, test on copy DBs.
5. **Heavy aggregates on every dashboard load** → indexes, bounded queries, rollup tables, heavy work in jobs not HTTP handlers.
6. **Instagram timestamp / timezone bugs** → normalize to UTC at ingest; document display policy; dedupe on stable IDs.
7. **New job types without idempotency** → keys on asset + perspective set + model + `prompt_version`; fairness/cancellation aligned with Phase 2.
8. **Dashboard sprawl** → one primary story per view, shared filter context, coverage indicators, strong empty states.
9. **Scores sold as objective truth** → label model + prompt version; cohort filters; avoid silent overwrites across generations.
10. **Cross-catalog / PII-adjacent leakage** in identity and caption surfaces → strict `catalog_id` scope; truncate/aggregate captions in UI; careful logging.
11. **Foundation:** `.lrcat` remains read-only by default; avoid widening `image_key` / `image_type` consistency gaps when extending `image_descriptions`.

---

## Implications for Roadmap

### Suggested phases (with rationale)

| Phase theme | Rationale |
|-------------|-----------|
| **Structured scoring schema & migration** | Unlocks every filter, ranking, and chart; prevents silent exclusion of legacy rows; implements nullable score semantics and backfill path. |
| **LLM output contracts & provider adapters** | Addresses parse failures, retries, and telemetry; golden fixtures per provider reduce production surprises. |
| **Prompt library & job design** | Mitigates mega-prompt truncation/cost; enables rubric versioning and optional split calls (scores vs prose). |
| **Catalog API & UI: score filters/sort** | Delivers user-visible value from persisted scores; validates indexing and query paths early. |
| **Analytics computation layer** | Indexes, rollups, and job-triggered refresh avoid dashboard-time full scans at 38k+ rows. |
| **Dump ingest & posting analytics** | UTC normalization, validation reports, and time-series tests underpin trustworthy heatmaps/histograms. |
| **Jobs & pipeline integration** | Idempotency, job taxonomy, and cancellation for new work types without starving or corrupting existing queues. |
| **Insights API + dashboard UX** | Small set of chart endpoints + Recharts/Query UI; shared scope/range; drill-down to catalog. |
| **v2.x follow-ons** | Caption/hashtag panels, weighted “best photos,” evidence-linked identity, explainable “what to post next,” full perspective comparison UI—each depends on stable scores + aggregates. |

### Phase ordering rationale

**Data contract and persistence before visualization:** The architecture research ordering and pitfall mapping both require **schema + validation + write path** before relying on aggregates or UI rankings. **Analytics infrastructure** (indexes/rollups) should land **before or alongside** the first heavy dashboard, not after timeouts appear. **Posting analytics** depend on ingest correctness (timezone, dedupe), so normalization work belongs **before** or **in parallel** with chart endpoints that consume timestamps. **Identity and recommendations** need minimum coverage and explicit scoping—appropriately **late** in the milestone after core scoring and posting views work.

### Research flags

- **Re-validate per environment:** OpenAI-compatible `response_format` / JSON-mode behavior differs by host and model; maintain a small capability matrix and tests on the smallest supported local model.
- **Schema strategy open:** Flat columns vs normalized `image_critique_scores` vs hybrid—pick based on filter patterns and perspective cardinality; watch existing `image_descriptions` key/`image_type` caveats in codebase concerns.
- **Optional dependencies:** Instructor vs hand-rolled parse/retry; pandas vs SQL-only—revisit when aggregate complexity or Python minimum version changes.
- **Product confidence:** Feature prioritization assumes DAM/BI-style expectations but **lacks cited primary user research**—treat table-stakes list as hypothesis to validate in UAT.

---

## Confidence Assessment

| Research output | Confidence | Notes |
|-----------------|------------|--------|
| Stack (core: Pydantic, OpenAI SDK v2, Recharts, TanStack Query) | **HIGH** | Versions cross-checked via PyPI/npm registry JSON (2026-04-12). |
| Stack (optional: Instructor, pandas 3.x vs 2.x, json-repair) | **MEDIUM** | Trade-offs on dependency surface and Python floor. |
| Features (landscape, MVP vs v2.x, anti-features) | **MEDIUM** | Strong alignment with PROJECT.md; no primary user interviews cited. |
| Architecture (integration points, dual-DB, build order) | **HIGH** (integration) / **MEDIUM** (exact schema) | Repo paths and roles verified; SQLite shape is product-dependent. |
| Pitfalls (LLM JSON, migrations, analytics perf, TZ, jobs, UX trust) | **HIGH** (patterns) / **MEDIUM** (model-specific quirks) | Re-verify per pinned model and provider. |

---

## Gaps to Address

- **Primary user research:** Quantitative usage and interviews not cited in feature research—validate rubric usefulness and dashboard stories with real workflows.
- **Final persistence shape:** Choose flat vs normalized vs hybrid score storage after catalog filter/sort requirements are fixed; add migration tests on production-sized `library.db` copies.
- **Provider/model matrix:** Document JSON reliability and context limits for each supported endpoint; expand golden parser fixtures as new models ship.
- **Timezone policy UX:** Confirm whether posting charts are “export UTC” vs “user local” and reflect that consistently in labels and docs.
- **Cross-catalog rules:** PROJECT.md defers multi-catalog switching; identity and analytics phases need explicit opt-in and API guards when that lands.

---

## Sources

- **Internal:** `.planning/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md` (all dated 2026-04-12); `.planning/PROJECT.md` (v2.0 goals and constraints, updated 2026-04-11).
- **Registries:** PyPI JSON API and npm registry (package versions as cited in STACK.md).
- **Codebase references (architecture/pitfalls):** `lightroom_tagger/core/database.py`, `analyzer.py`, `description_service.py`, `vision_client.py`; `apps/visualizer/backend/api/*`, `jobs/handlers.py`; `.planning/codebase/ARCHITECTURE.md`, `CONCERNS.md`.
- **Industry practice:** Structured LLM output validation, SQLite analytics patterns (indexes, rollups, avoiding correlated subqueries)—re-verify against current provider documentation.

---

*Unified summary for milestone planning; see sibling research files for depth and citations.*
