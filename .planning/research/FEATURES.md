# Feature Research

**Domain:** Structured AI critique scoring, photography-theory-grounded analysis, Instagram posting pattern analytics, photographer identity synthesis, and insights dashboards — building on an existing Lightroom catalog + dump-matched Instagram workflow  
**Researched:** 2026-04-12  
**Confidence:** MEDIUM (product/category patterns + photography education norms + PROJECT.md alignment; no primary user interviews cited)

## Feature Landscape

### Table Stakes (Users Expect These)

Features that serious “AI critique + library insights” experiences must satisfy once numeric scores and dashboards exist. Missing them undermines trust faster than missing a flashy chart.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Scores tied to visible rationale** | Photographers reject naked numbers; every axis needs a short justification in the same UI affordance as the score. | LOW–MEDIUM | Structured output: `{axis, score, rationale_snippet}` per perspective; not prose-only blobs. |
| **Consistent rubric & scale** | Mixed 1–5 vs 1–10 or undefined “composition” makes filtering and ranking meaningless. | MEDIUM | Version prompts + schema; store `prompt_version` / `rubric_id` with each result for drift control. |
| **Perspective-scoped scores** | A “publisher” composition score ≠ a “street photographer” composition score; users expect the persona to frame the metric. | MEDIUM | Same named axes can differ by perspective; UI must label perspective + axis. |
| **Re-run / supersede analysis** | Models and rubrics change; users expect “analyze again” without orphan rows confusing the UI. | MEDIUM | Idempotent job keys + latest-wins or history with explicit “active” row. |
| **Filter & sort in catalog UI** | If scores are persisted, they must behave like rating/color-label filters (range queries, null handling). | MEDIUM | Indexed app DB fields; clear “not yet analyzed” state. |
| **Honest limits on “performance”** | Export dumps lack likes/saves; dashboards must not imply engagement where data does not exist. | LOW | Label charts as **posting behavior** (when/how often/caption patterns), not reach. |
| **Job + error visibility for enrichment** | Batch scoring is still async AI; same job lifecycle expectations as description jobs. | LOW | Reuse cancellation, severity, provider health patterns. |

### Differentiators (Competitive Advantage)

Features that distinguish this product when table stakes are met — especially **Lightroom row linkage**, **dump-based posting truth**, and **artistic (not EXIF) theory**.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Queryable multi-axis scores + narrative** | Turns critique from ephemeral chat into **library intelligence** — rank, filter, compare sets. | HIGH | Requires JSON schema, migrations, and UI binding; core v2 bet. |
| **Photography-theory-grounded rubrics** | Anchors scores to recognizable craft language (figure–ground, rhythm, color relationships, sequence read) instead of vague “nice shot.” | MEDIUM–HIGH | Prompt engineering + reference texts in system context; periodic rubric versioning. |
| **Additional perspectives (color, emotion, series)** | Mimics a **room of critics** rather than one model tone; matches serious practitioners’ mental model. | MEDIUM | Mostly prompt + schema extensions on the same vision pipeline. |
| **Posting pattern analytics without API** | Heatmaps / histograms of **post time**, **frequency gaps**, **caption & hashtag motifs** from dump timestamps and text — still valuable without engagement metrics. | MEDIUM–HIGH | Parser stability + normalization of time zones; text clustering optional. |
| **Catalog ↔ posted gap analysis** | “Strong in catalog, rarely posted” and inverse — unique when **match keys** tie IG posts to LRCAT rows. | HIGH | Needs reliable match state + score rollups per asset. |
| **Photographer identity / style fingerprint** | Aggregated themes, palettes (from vision text), recurring subjects, and consistency signals across thousands of frames. | HIGH | Risk of vacuous generalities; needs careful prompting + optional user “north star” tags. |
| **“What to post next” suggestions** | Action layer on top of gaps + scores + series coherence (e.g. break repetition, complete a sequence). | HIGH | Must expose **why** each suggestion; avoid black-box recommender feel. |
| **Insights dashboard as first-class surface** | Cohesive charts + drill-down to assets — not buried modals. | MEDIUM | Recharts (or equivalent) + shared query layer with catalog filters. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Single “master quality” leaderboard** | Simple sorting. | Collapses genres and intents; contradicts multi-perspective philosophy; hard to defend. | Weighted **per-perspective** composites with toggles; always show breakdown. |
| **Scores without confidence / coverage flags** | Cleaner UI. | Vision crops, night shots, and abstracts produce noisy scores; users blame the product. | Optional low-confidence flag; axis-level “not applicable” or null. |
| **Automated posting or scheduling** | “Close the loop.” | Different product category, compliance, and expectations; dilutes catalog + critique story. | Export caption ideas or copy-to-clipboard only. |
| **Engagement-driven optimization from dumps** | “Tell me what Instagram liked.” | **Data not in export** (per PROJECT.md); faking it erodes trust. | Explicitly scope insights to **posting cadence + caption style + AI critique**. |
| **Full-catalog mandatory scoring** | “Index everything.” | Cost explosion and stale rubrics; blocks prompt iteration. | Time-boxed batches, min_rating filters, user selections — same as analysis philosophy today. |
| **Overfitted identity labels** | Users want a catchy “you are a X photographer.” | Stereotyping, wrong for hybrid practice; hard to correct. | **Evidence-linked** traits (“recurring: high contrast B&W night geometry”) with example thumbnails. |
| **Opaque suggestion engine** | Feels magical. | No learning path; user cannot disagree or tune. | Rule-based + LLM explanations with **user-adjustable weights** (e.g. favor series completion vs novelty). |

## Feature Dependencies

```
[Existing: multi-perspective text critique jobs + vision pipeline]
    └──requires──> [Provider registry, health probes, job lifecycle]  ✓ built
    └──extends──> [Structured critique JSON schema (scores + rationale + perspective + versions)]

[Structured scoring persistence]
    └──requires──> [Structured critique schema]
    └──requires──> [App DB columns or JSON index strategy for filter/sort]
    └──requires──> [Prompt/rubric versioning on each stored row]

[Catalog UI: score filters & “best photos” views]
    └──requires──> [Structured scoring persistence]
    └──requires──> [Null / not-analyzed semantics + indexed queries]

[New perspectives (color, emotional, series)]
    └──requires──> [Structured scoring schema extension or parallel axes]
    └──enhances──> [Same job runner + vision client — new prompt templates only]

[Photography-theory prompt refinement]
    └──requires──> [Rubric text + examples in system/developer prompts]
    └──couples──> [Version bumps invalidate comparability — store rubric_id]

[Posting frequency / timing analytics]
    └──requires──> [Instagram dump ingest + normalized post timestamps]  ✓ built path
    └──requires──> [Match: post ↔ catalog asset]  ✓ built path
    └──optional──> [Time zone handling policy documented in UI]

[Caption / hashtag style analysis]
    └──requires──> [Dump text fields in canonical post rows]
    └──optional──> [NLP clustering / embeddings in app DB — heavier than regex summaries]

[Photographer identity / fingerprint]
    └──requires──> [Corpus of critiques or embeddings across analyzed assets]
    └──requires──> [Aggregation job or incremental rollups]
    └──conflicts──> [Sparse analysis coverage — identity weak until enough scored images]

[“What to post next” suggestions]
    └──requires──> [Scores + posting history + optional series/cluster tags]
    └──requires──> [Explicit rules or LLM with structured rationale output]
    └──enhances──> [Insights dashboard surfacing]

[Insights dashboard]
    └──requires──> [Chart-friendly aggregates API over app DB]
    └──requires──> [Posting analytics + score rollups + (optional) identity snapshot]
    └──enhances──> [Discovery of batch scoring jobs — user sees “why run more analysis”]
```

### Dependency Notes

- **Structured scoring is an extension of the description pipeline**, not a parallel system: same image preparation, provider calls, caching limits, and job records — add **schema validation** (e.g. Pydantic) and **persisted numeric fields** for UI queries.
- **Comparability across time** requires stored **model + prompt/rubric version**; aggregations and “best photos” should default to **single-version cohorts** or show a warning when mixing.
- **Posting insights** depend on **match quality**; unmatched posts should appear in analytics as **unlinked** so users do not confuse catalog coverage with Instagram coverage.
- **Identity and suggestions** need **minimum sample thresholds**; without them, the UX should defer or show “analyze N more from this era.”

## MVP Definition

### Launch With (v2)

Minimum scope to validate **“scores make the library more navigable, and posting patterns are understandable without engagement data.”**

- [ ] **Structured output contract** per perspective: fixed axes (e.g. composition, narrative, rhythm) + numeric scores + short rationales + `rubric_version` / `prompt_version`.
- [ ] **Persist scores in app DB** with catalog asset foreign keys; **filter/sort** in existing catalog UI for at least one perspective.
- [ ] **Photography-theory-informed system prompts** for existing + new perspectives (documented rubric snippets, not opaque prose).
- [ ] **At least one new perspective** shipped end-to-end (e.g. color theory **or** emotional impact **or** series coherence) with its own axis set.
- [ ] **Posting cadence / timing visualization** from matched dump timestamps (e.g. histogram or heatmap by hour/weekday).
- [ ] **Thin insights dashboard** landing: 2–4 high-signal charts + links into filtered catalog views (not a separate siloed app).

### Add After Validation (v2.x)

Once users trust scores and charts are stable.

- [ ] **Full new-perspective set** (all planned dimensions) with UI to compare perspectives side-by-side.
- [ ] **Caption & hashtag style panels** — readability, length, emoji/use, top tags, simple clustering.
- [ ] **“Best photos” composite** with user-tunable weights per perspective/axis.
- [ ] **Photographer identity summary** with evidence links (example images per claim).
- [ ] **“What to post next”** v1: rule-heavy, explainable suggestions; optional LLM phrasing layer.

### Future Consideration (post–v2)

- [ ] **Cross-catalog identity** (per PROJECT.md deferred) — unified fingerprint when multi-catalog switching matures.
- [ ] **Engagement fusion** — only if likes/saves enter via API or manual CSV; treat as optional overlay, not core truth.
- [ ] **Re-import diff / multi-dump history** for longitudinal posting trend accuracy.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Structured score schema + persistence + catalog filters | HIGH | HIGH | P1 |
| Rubric versioning + re-run semantics | MEDIUM | MEDIUM | P1 |
| Photography-theory prompt refinement (existing perspectives) | HIGH | MEDIUM | P1 |
| Posting timing / frequency charts (matched posts) | HIGH | MEDIUM | P1 |
| Minimal insights dashboard (drill-down to catalog) | HIGH | MEDIUM | P1 |
| One new critique perspective (end-to-end) | MEDIUM | MEDIUM | P2 |
| Caption / hashtag analytics | MEDIUM | MEDIUM | P2 |
| “Best photos” weighted ranking | MEDIUM | MEDIUM | P2 |
| Photographer identity synthesis w/ evidence | HIGH | HIGH | P2 |
| “What to post next” suggestions (explainable) | HIGH | HIGH | P2 |
| Full multi-perspective score comparison matrix UI | MEDIUM | MEDIUM | P2 |
| Advanced series coherence (sequence-aware jobs) | MEDIUM | HIGH | P3 |

**Priority key:** P1 = v2 launch core; P2 = immediately after validation; P3 = stretch / higher research cost.

## Expected User Behaviors

- **Batch by intent, not by “whole catalog”:** Users run scoring on **recent work**, **portfolio shortlists**, or **high-rated** subsets — same pattern as current on-demand analysis; structured scoring amplifies the need for **scoped jobs** to control cost.
- **Tune via re-analysis:** After rubric changes, users **re-run** key portfolios; the product should make **version cohorts** obvious so old scores are not mixed casually in ranking.
- **Cross-check scores with prose:** Users read **rationales** when a score surprises; table-stakes UX is **score + snippet + jump to full critique**.
- **Dashboard as triage:** Users open the insights page to spot **cadence gaps**, **overused caption patterns**, or **clusters of high composition / low narrative**, then **filter the catalog** from a chart click — navigation depth matters more than chart count.
- **Skepticism toward identity labels:** Users accept **evidence-backed** summaries (“these 12 images share X”) and reject **vague personas**; suggestions succeed when **reasons** align with their own goals (series vs reach vs craft).
- **Posting analytics without vanity metrics:** Users mentally substitute **“when I post”** and **“what I say”** for performance until engagement data exists — copy must avoid implying **reach**.

## Sources

- **Internal:** `.planning/PROJECT.md` (v2.0 goals, dump limitations, on-demand analysis philosophy, out-of-scope engagement).
- **Photography pedagogy (general):** Critique norms in workshops and MFA-style feedback — multi-axis verbal critique (composition, light, color, intent, edit) rather than single grades; aligns with per-perspective rubrics.
- **Product patterns:** DAM and photo-manager expectations for **filterable metadata**; BI-style dashboards for **behavioral** (timestamp) analytics where **outcome metrics** are absent.
- **Gap:** Primary user interviews and quantitative usage study not cited — confidence MEDIUM.

---
*Feature research for: v2 Advanced Critique & Insights (structured scoring, analytics, identity, dashboard)*  
*Researched: 2026-04-12*
