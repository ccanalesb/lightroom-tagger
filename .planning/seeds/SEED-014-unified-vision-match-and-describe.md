---
id: SEED-014
status: dormant
planted: 2026-04-17
planted_during: v2.0 (milestone complete) — planning next milestone
trigger_when: Next milestone touches matching/vision pipeline, batch processing, or description generation
scope: Medium
---

# SEED-014: Have the vision model return description + match score in a single batch call

## Why This Matters

Today the matching UI shows only match percentages — there is no AI description of
the image surfaced alongside a match. Reviewing matches is tedious because to see
why two images might be the same you have to:

1. Run a `batch_describe` job to generate descriptions for catalog images.
2. Run a separate `vision_match` / batch job to get percentage scores.
3. Cross-reference the two in the UI.

The root cause is in the matching pipeline: `compare_images_batch` in
`lightroom_tagger/core/vision_client.py` returns `dict[int, float]` — only
per-candidate percentages. Descriptions are produced by a totally separate path
(`describe_image` in `lightroom_tagger/core/analyzer.py`, orchestrated by
`lightroom_tagger/core/description_service.py`). The same catalog images get
compressed and sent to a vision model twice for two different outputs.

In previous conversations we decided a single call couldn't reliably return both
because of (a) output token limits for multi-image batches, (b) weak structured
output guarantees, and (c) reliability concerns with larger JSON payloads per
candidate. Those constraints were real when the batch path was designed
(see `docs/plans/2026-04-06-parallel-batch-vision-matching.md`), but modern vision
models (GPT-4o, Claude 3.5/3.7 Sonnet, Gemini 1.5/2.x) handle multi-image +
structured JSON output materially better, and the batch code already has
adaptive `max_tokens` escalation (`BATCH_MAX_TOKENS_ESCALATION = [4096, 32768, 65536]`)
and payload-size recovery. It's worth re-running the experiment: ask the model
to return `{candidate_id, match_score, description}` per candidate in one call,
and fall back to the existing percentage-only schema on failure.

If it works, matching becomes a one-shot analysis: describe + score together,
descriptions instantly visible in the match review UI, and users stop having to
run two jobs sequentially over the same photos.

## When to Surface

**Trigger:** When the next milestone focuses on the matching experience, vision
pipeline improvements, batch processing performance, or unifying the
describe/score/match flows.

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- Matching UX or match-review UI improvements
- Vision pipeline redesign or provider/model migration
- Batch processing optimization (reducing duplicate model calls)
- Any milestone that expands on SEED-001 (unified batch job) — these two
  seeds are complementary
- Description-generation pipeline changes

## Scope Estimate

**Medium** — A phase or two. Work breaks down roughly as:

1. **Prompt + schema design.** Extend the batch comparison prompt to request a
   description field per candidate. Define structured-output schema. Decide
   whether the description is full-quality (matching `describe_image`'s
   structured output) or a lightweight "match-context" variant.
2. **Response parsing.** Update `compare_images_batch` return type from
   `dict[int, float]` to something like `dict[int, {score, description}]`.
3. **Persistence.** Wire description writes into the matching path via
   `description_service.store_image_description` so descriptions generated during
   matching are reused later (and vice-versa: don't redescribe if one exists).
4. **Fallback.** Keep percentage-only as a graceful degradation when the richer
   schema fails validation or exceeds token budgets. The existing
   `_call_batch_chunk` adaptive recovery is the right place to hook this.
5. **Benchmarking.** Re-measure token usage, latency, and reliability across
   providers (OpenAI-compatible, Anthropic, Gemini) at realistic batch sizes
   (`batch_size=10`, `batch_threshold=5` are the current defaults).
6. **UI.** Surface descriptions in the match review modal alongside the score
   bar.

## Breadcrumbs

Related code and decisions found in the current codebase:

- `lightroom_tagger/core/vision_client.py` — `compare_images_batch` (returns `dict[int, float]`, lines 172+)
- `lightroom_tagger/core/matcher.py` — `_call_batch_chunk`, `match_batch`, adaptive token escalation (lines 83, 86, 143, 579)
- `lightroom_tagger/core/analyzer.py` — `describe_image` (line 317), `compare_with_vision` (line 442) — the two separate paths today
- `lightroom_tagger/core/description_service.py` — where descriptions are persisted; natural integration point
- `lightroom_tagger/core/prompt_builder.py` — `build_description_user_prompt`; describe prompt lives here
- `apps/visualizer/backend/jobs/handlers.py` — `batch_describe` and batch match handlers (today these are separate jobs)
- `apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx` — match review UI that would gain a description section
- `apps/visualizer/frontend/src/components/matching/ScoreTooltip.tsx` — percentage-only score display today
- `docs/plans/2026-04-06-parallel-batch-vision-matching.md` — original batch design, contains the prior reasoning about why percentages-only
- `docs/plans/2026-03-30-provider-registry.md` — provider abstraction; schema changes need to stay provider-portable
- `.planning/seeds/SEED-001-unified-batch-job.md` — complementary seed (unify describe + score job UX); this seed unifies at the **model-call** layer, SEED-001 unifies at the **job** layer

## Notes

- Relationship to SEED-001: SEED-001 collapses two user-visible jobs into one
  "Analyze" job. SEED-014 collapses two model calls per photo into one. Done
  together they remove ~half the vision API traffic for a full analysis and
  make match review descriptive out of the box.
- The adaptive `max_tokens` escalation (4096 → 32768 → 65536) already exists
  and the 413 / too-large recovery that splits chunks in half is already in
  `_call_batch_chunk`. Adding descriptions per candidate will push payloads
  bigger — the existing safety nets should cover most cases, but real
  benchmarking is required.
- Consider a "lite" description variant for the matching path (1–2 sentences,
  focused on subjects/scene) vs. the full structured description used by
  `describe_image`. The matching UI probably doesn't need full perspective
  data, and keeping it small protects the batch payload budget.
- Fallback strategy: if structured output validation fails on the combined
  schema, re-request just scores for that chunk. Descriptions are a bonus,
  matching must not regress.
