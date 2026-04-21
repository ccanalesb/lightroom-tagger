---
id: SEED-019
status: dormant
planted: 2026-04-21
planted_during: v2.1 Phase 8 — Two-stage cascade matching
trigger_when: when we start a Post Next / Identity improvement milestone
scope: medium
---

# SEED-019: Per-image differentiated reasoning for "What to Post Next"

## Why This Matters

Currently every "What to Post Next" suggestion shows the same generic reason codes
(e.g. "high aesthetic score", "not recently posted"). Users can't tell why one photo
is meaningfully better to post than another — the list feels arbitrary and loses trust.

The fix is to generate **per-image, differentiated reasoning** that is specific and
non-repeating across candidates. Examples of what good looks like:

- "Your followers engage most with blue-toned landscapes — this fits that pattern"
- "This fills a 3-week gap in your outdoor shots series"
- "Your last 5 posts were portraits; this adds visual variety"
- "Technically your strongest unposted image from this trip"

The reasoning should make each card feel hand-picked, not ranked-by-formula.

## When to Surface

**Trigger:** When starting a milestone focused on Post Next, Identity, or posting strategy

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- Milestone involves the Identity page or "What to Post Next" feature
- Milestone involves AI-generated descriptions or reasoning quality
- Milestone involves posting strategy, cadence, or engagement analysis

## Scope Estimate

**Medium** — A phase or two, needs planning. Likely involves:
1. Enriching the scoring model with per-image signal aggregation
2. Updating the reasoning generation (prompt or rule-based) to produce
   differentiated, non-repeating strings across the candidate list
3. Possibly a backend pass to deduplicate reason strings across results

## Breadcrumbs

Related code found in the codebase:

- `lightroom_tagger/core/identity_service.py` — scoring logic and reason_codes generation
- `apps/visualizer/frontend/src/components/identity/PostNextSuggestionsPanel.tsx` — renders `row.reasons` as a bullet list per card
- `apps/visualizer/frontend/src/services/api.ts` — `PostNextCandidate` type with `reasons: string[]` and `reason_codes: string[]`
- `apps/visualizer/frontend/src/constants/strings.ts` — `IDENTITY_REASON_CODE_LABELS` map

## Notes

Observed during v2.1: all suggestion cards show identical or near-identical reason
strings, making the ranked list feel like a filter result rather than a curated
recommendation. The UI infrastructure (bullet list per card) is already in place —
the gap is in the backend reasoning quality.
