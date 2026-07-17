# ADR-0016: Description and scoring are separate pipelines; `image_scores` is the single source of truth for perspective scores

## Status
Accepted (2026-07)

## Context
The description pipeline (`build_description_op_spec` → `image_descriptions`) has always
embedded per-perspective rubric scores inside the `perspectives` JSON blob (`score` +
`analysis`). A later scoring pipeline writes structured rows to `image_scores` with
versioning, supersede semantics, and excusable (`not_attempted`) support (ADR-0012).
The visualizer's `ImageScoresPanel` already reads current scores from `image_scores`
(`api/scores.py`), not from the blob.

On a representative library DB (~38.6k described catalog images), only ~7.9k images had
any current `image_scores` row while ~38.6k carried blob perspective scores — roughly
30.7k images showed no scores in the UI despite having description-era rubric output.
Dual storage also made it unclear which layer owned aggregation, history, and
re-scoring when description and scoring prompts diverge.

This ADR sits above ADR-0014 (one vision-op-and-persist engine): the engine remains
shared infrastructure; this decision splits *what* each op persists. It relates to
ADR-0012 because excusable perspectives and `not_attempted` rows live only in
`image_scores`, not in the legacy blob.

Parent initiative: split description and scoring into two pipelines (issue #184).

## Decision
1. **`image_scores` is the single source of truth** for perspective rubric scores,
   rationale text, model metadata, and prompt versioning. Consumers (API, identity
   aggregation, catalog filters) read scores from `image_scores` only.
2. **Description and scoring are separate pipelines.** Description persists narrative
   fields (`summary`, `composition`, `subjects`, etc.) to `image_descriptions`.
   Scoring persists rubric output to `image_scores` via the scoring op-spec. They may
   share the vision-op engine (ADR-0014) but must not duplicate score state in the
   blob after the transition slices land.
3. **One-time gap-fill migration (slice 1).** Copy each `image_descriptions.perspectives[slug]`
   into `image_scores` with `prompt_version = 'legacy:description'`, `rationale =
   analysis`, `model_used` / `scored_at` from the description row, and `is_current = 1`
   — **only** when no current `image_scores` row exists for that image+perspective.
   Never call `supersede_previous_current_scores` for legacy rows; real scoring-pass
   scores always win.
4. **Legacy rows are labeled, not authoritative.** `prompt_version = 'legacy:description'`
   marks provenance so the UI and operators can distinguish description-era backfill
   from rubric-versioned scoring-pass output. Re-scoring via the scoring pipeline
   supersedes legacy rows through the normal versioned insert path.

## Consequences
- `ImageScoresPanel` immediately shows perspective scores for blob-only images,
  tagged as legacy, without waiting on later pipeline slices.
- Partial overlap is preserved: images already scored by the scoring pass keep their
  real current rows; only missing perspectives are gap-filled.
- Identity aggregation and catalog score filters align on one table; no more
  reconciling blob JSON vs `image_scores`.
- The `perspectives` blob remains until slice 2 stops writing scores there; until
  then, blob scores are redundant for images that received a legacy backfill row.
- Future slices must ensure new description runs do not reintroduce blob scores as a
  competing source (write path change + optional blob cleanup).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Keep dual storage** — UI reads blob when `image_scores` is empty | Perpetuates two sources of truth; aggregation and history stay ambiguous; panel already uses `image_scores`. |
| **Supersede all with legacy backfill** | Would overwrite real scoring-pass scores for ~7.9k overlapping images; violates "scoring pass wins" and loses rubric-version history. |
| **Read blob at API layer as fallback** | Hides the data model split in the API; every consumer would need the same fallback; does not fix aggregation. |
| **Drop blob scores in place without backfill** | Would lose ~30.7k rubric outputs with no `image_scores` replacement; unacceptable data loss. |
| **Nullable scores only in blob** | Does not give versioning, supersede, or `not_attempted` semantics; keeps the wrong table as SSOT. |
