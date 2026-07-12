# ADR-0012: Excusable (not-attempted) perspectives

**Status:** Accepted  
**Date:** 2026-07-02

## Context

`yt-to-photo-prompt-lab` (a subproject) exports recipe dimensions into
lightroom-tagger perspectives. Some dimensions describe *optional*,
source-specific techniques a strong photograph could legitimately skip. That
project already models this as a "not scorable / not attempted" outcome. To use
those recipes faithfully, lightroom-tagger needs to score a perspective as
*excused* rather than forcing a 1-10 judgment on an absent technique.

## Decision

Add an excusable-perspective path across the scoring pipeline, additively.

- **Schema (flag columns, not nullable score).** `perspectives.optional`
  (0/1) marks a perspective as excusable. `image_scores.not_attempted` (0/1)
  marks a row as excused; `score` stays `NOT NULL` 1-10 (the model still returns
  a neutral numeric score, exactly like the source project's not-attempted band).
  Both added via idempotent `_migrate_add_column`.
- **Opt-out is gated on `optional`.** `build_scoring_user_prompt` only invites a
  `not_attempted` response — with "genuinely absent, not weak" / "score low when
  unsure" calibration — for optional perspectives. `ScoreResponse` gains
  `not_attempted: bool = False`.
- **Excused rows are excluded from identity aggregation** (numerator and
  denominator). An image whose current perspectives are all excused has zero
  covered perspectives and is not eligible for ranking.
- **Cross-repo marker contract — the marker is the single source of truth.** A
  perspective is optional iff its markdown carries the HTML comment
  `<!-- optional: true -->`. `optional` is **not** a caller-supplied field: it is
  re-derived from `prompt_markdown` on *every* write of that markdown — factory
  seed, API create, API edit, and reset-to-default — via one parser
  (`markdown_marks_optional`). A removed marker un-sets `optional`; an edit that
  doesn't touch the markdown leaves it. This keeps the file-based contract with the
  yt-to-photo-prompt-lab exporter authoritative and impossible to drift. The
  read API exposes `optional` (read-only) on perspective list/detail rows.
- **Scope.** The excuse is offered wherever an optional perspective is scored,
  including Instagram-dump images; it only *matters* for catalog identity, since
  aggregation is catalog-only. Optionality is a property of the technique, not the
  image source.

## Considered options

- **Nullable score** instead of a `not_attempted` flag — rejected: requires
  rebuilding `image_scores` to drop `NOT NULL` + the `CHECK (score BETWEEN 1 AND
  10)`, a heavier migration, for no added expressiveness.
- **Infer optional-ness** from a "not attempted" band inside the markdown scoring
  section — rejected as fragile; an explicit marker is unambiguous.
- **An explicit `optional` API field / write parameter** alongside the marker —
  rejected: a second way to express optionality can drift from the marker. The
  marker in the markdown is the one contract; writes re-derive from it.
- **Actively clearing excused scores when a perspective turns non-optional** —
  rejected: it mixes "edit a perspective" with "mutate historical scores." Scores
  are versioned and self-heal on the next scoring run (which no longer offers the
  excuse), so a stale excused row simply stays excluded until re-scored.

## Consequences

- Two perspective classes coexist: baseline (always counts) and optional
  (excusable). Existing perspectives default to baseline; nothing breaks.
- Aggregation reflects only techniques the photograph actually attempts, so an
  absent optional technique no longer drags an image's aggregate down.
- lightroom-tagger now understands a marker emitted by another repo; that marker
  is the stable seam between the two projects, re-read on every markdown write.
- A perspective that flips optional→off leaves any prior excused (`not_attempted`)
  scores in place; they remain excluded from aggregation until superseded by a
  re-score. This is intentional (see Considered options) and rare.
