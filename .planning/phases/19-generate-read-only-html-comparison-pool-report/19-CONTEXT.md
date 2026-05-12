# Phase 19: Generate Read-Only HTML Comparison-Pool Report - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Create an offline, read-only investigation report for diagnosing Instagram-to-catalog match misses. The report shows unmatched Instagram dump images beside the catalog candidates the matcher actually considered, so a human can tell whether the expected catalog photo was present but scored poorly, absent from the candidate pool, or not visually obvious.

This phase is not a product screen and does not add match-labeling or writeback behavior. It is a diagnostic artifact for the existing matching pipeline.

</domain>

<decisions>
## Implementation Decisions

### Candidate Pool Fidelity
- **D-01:** The report should use exact saved candidate-pool snapshots for future matching runs.
- **D-02:** Older unmatched rows may be supported via best-effort reconstruction from the current DB and code path, but those sections must be visibly labeled as reconstructed / not exact.
- **D-03:** Planning should add durable pool capture around the matching path because current code stores final `matches` / `vision_comparisons`, but not the exact evaluated candidate list for unmatched rows.

### Invocation Model
- **D-04:** Generate the report through a CLI/offline command only, not a backend debug endpoint and not a product UI.
- **D-05:** The command should produce files that can be opened locally without running the app frontend.

### Report Contents
- **D-06:** For each unmatched Instagram image, show the Instagram preview, stable Instagram identifier, every candidate thumbnail in its evaluated pool, and stable catalog identifiers.
- **D-07:** Include scoring evidence inline: rank, total score, pHash score/distance, description score, vision score/verdict, model used, and other structured evidence available from the matching run.
- **D-08:** Include full debug evidence when available, including prompt response, reasoning, log excerpts, and local paths, but hide it from the primary view behind a collapsible details section or modal-like expandable panel.

### Scope Controls
- **D-09:** Default CLI behavior is all unmatched attempted Instagram images.
- **D-10:** CLI supports filters so reports can be narrowed: `--month`, `--job-id`, `--media-key`, and `--limit`.

### Output Safety
- **D-11:** Output should be a report folder containing `report.html` plus an `assets/` directory, rather than directly referencing original local image paths.
- **D-12:** Always compress copied report images / thumbnails before writing assets.
- **D-13:** Full original local paths may appear only inside hidden debug details, not in the primary visible report.

### Folded Todos
- **D-14:** Folded todo `2026-05-06-generate-read-only-html-comparison-pool-report.md` into this phase. It defines the diagnostic need: avoid prompt changes until unmatched cases can be inspected against the actual evaluated candidate pools.

### Claude's Discretion
- Exact CLI module name and argument spelling beyond the locked filters.
- Exact HTML styling and layout, as long as it is scannable offline and keeps debug evidence hidden by default.
- Exact thumbnail dimensions and compression quality, as long as generated assets stay reasonably small and readable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/todos/pending/2026-05-06-generate-read-only-html-comparison-pool-report.md` — Source todo defining the problem, report shape, constraints, and success criteria.
- `.planning/ROADMAP.md` — Phase 19 placeholder and dependency context.
- `.planning/PROJECT.md` — Project constraints, match workflow, and milestone goal.

### Matching Pipeline
- `lightroom_tagger/scripts/match_instagram_dump.py` — Main bulk Instagram-to-catalog matching flow; selects date-window candidates, applies rejected / representative filters, CLIP shortlist, builds `vision_candidates`, scores, stores matches, and marks attempted unmatched media.
- `lightroom_tagger/core/matcher/candidates.py` — Date-window candidate discovery.
- `lightroom_tagger/core/matcher/score_with_vision.py` — Scoring result shape and evidence fields: pHash, description, vision verdict/score, model, total score.
- `lightroom_tagger/core/clip_similarity.py` — CLIP shortlist behavior used before scoring.

### Persistence
- `lightroom_tagger/core/database/library_bootstrap_schema.py` — Existing schema for `instagram_dump_media`, `matches`, `rejected_matches`, and `vision_comparisons`.
- `lightroom_tagger/core/database/matches.py` — Match persistence and validation/rejection behavior.
- `lightroom_tagger/core/database/vision_cache.py` — Stored vision comparison evidence currently available by `(catalog_key, insta_key)`.

### Existing Report-Like Surfaces
- `apps/visualizer/backend/api/images/catalog.py` — Existing catalog image serialization and catalog similarity group shape; useful for thumbnail URL / image metadata patterns but this phase stays CLI/offline.
- `lightroom_tagger/core/database/similarity.py` — Existing materialized group/candidate persistence pattern for catalog similarity jobs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `match_instagram_dump.match_dump_media` already has the exact point where the evaluated candidate list exists: after rejected-pair filtering, representative-only filtering, CLIP shortlisting, and candidate hydration into `vision_candidates`.
- `score_candidates_with_vision` returns structured evidence suitable for report rows: candidate key, Instagram key, pHash distance/score, description similarity, vision result/score/reasoning, total score, model, and rate-limit flag.
- `vision_comparisons` can provide partial historical evidence for `(catalog_key, insta_key)` pairs, but it does not prove which candidates were in the actual pool for an unmatched run.

### Established Patterns
- Diagnostic/generated artifacts should stay outside product UI when the requirement says investigation-only.
- Existing similarity group tables show a simple parent/child persistence pattern for ranked candidate lists, but Phase 19 needs Instagram-keyed pool snapshots and per-run match evidence, not catalog-to-catalog groups.
- Existing image-serving APIs know how to resolve thumbnails, but the report should copy compressed assets so it opens without the running app.

### Integration Points
- Add pool capture in or near the matching flow where `vision_candidates` and `results` are both available.
- Add a CLI/offline generator that reads the library DB, selected unmatched attempted Instagram rows, saved pool snapshots when present, and reconstructed pools only as a fallback with a visible warning.
- The generator should write `report.html` and compressed assets under a caller-provided output directory.

</code_context>

<specifics>
## Specific Ideas

- Primary report view should answer visually first: “Was the expected catalog image among the candidates?”
- Debug details should be available but hidden by default via collapsible panels or modal-like expandable sections.
- Reconstructed old pools are allowed, but must not be presented as exact historical evidence.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-26-fixes-for-embed-job-discoverability-and-path-failures.md` — Relevant to UI / embed operations, but not part of this offline report phase.
- `2026-04-26-plan-backend-restart-and-compression-fix.md` — Tooling / restart concern, not part of this report phase.

No new product UI, labeling workflow, or writeback behavior in this phase.

</deferred>

---

*Phase: 19-generate-read-only-html-comparison-pool-report*
*Context gathered: 2026-05-12*
