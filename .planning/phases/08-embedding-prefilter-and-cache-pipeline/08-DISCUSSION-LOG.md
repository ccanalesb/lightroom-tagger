# Phase 8: Embedding pre-filter & catalog cache pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `08-CONTEXT.md` — this log preserves alternatives considered.

**Date:** 2026-04-27
**Phase:** 08-embedding-prefilter-and-cache-pipeline
**Areas discussed:** Instagram embedding source, Pre-filter top-k, Pre-filter scope, Catalog cache pipeline UI structure, Wider-search fallback (rejected)

---

## G1 — Instagram media CLIP embedding source

| Option | Description | Selected |
|--------|-------------|----------|
| A. Inline embed during `vision_match` | Compute IG CLIP vector per match run; not cached in DB | |
| B. Extend `batch_embed_image` to also embed `image_type='instagram'` rows | IG embeddings cached in `image_clip_embeddings` alongside catalog | ✓ |
| C. Hybrid | Cache when present, fall back to inline for un-embedded IG | |

**User's choice:** B — Extend `batch_embed_image` so IG embeddings become first-class cached artifacts; matcher reads from DB.
**Notes:** Cleanest fit with the cache-pipeline framing — IG embeddings become catalog-cache artifacts just like catalog embeddings.

---

## G2a — Pre-filter top-k value

| Option | Description | Selected |
|--------|-------------|----------|
| A. Fixed default 50 with UI override | Default k=50; numeric input on matching tab for per-run tuning | ✓ |
| B. Adaptive based on candidate count | k scales with date-window size | |
| C. Fixed at 100 or 200 | Larger fixed default, no UI override | |

**User's choice:** A — Default top-k = 50, exposed as a configurable numeric input on the matching UI.
**Notes:** "I think top 50 make sense, but it can be also config per vision match flow, another param in the ui to control."

---

## G2b — Pre-filter scope

| Option | Description | Selected |
|--------|-------------|----------|
| i. Gates LLM only | Description scoring still runs over the full date-window set | |
| ii. Gates phash + description + LLM | Entire scoring stack runs only on the CLIP shortlist | ✓ |
| iii. Mixed | Description on shortlist, phash on full set, etc. | |

**User's choice:** ii — CLIP shortlist gates phash, description, and final visual LLM judgment.
**Notes:** "Description is also LLM based" — gating only the visual LLM would not deliver the intended cost reduction.

---

## G3 — Catalog cache pipeline UI structure

| Option | Description | Selected |
|--------|-------------|----------|
| A. Single "Build cache" + Advanced for individual | One composite CTA runs the chain; Advanced disclosure exposes individual stage triggers | ✓ |
| B. Always individual buttons | No composite CTA; user runs each stage separately | |
| C. Sequential wizard | Forced step-by-step UI requiring each stage in order | |

**User's choice:** A — Single composite "Build cache" runs the chain (`batch_embed_image` → `batch_stack_detect` → `batch_catalog_similarity`); Advanced section reuses the existing `AdvancedOptions` component for individual job triggers (including the legacy `prepare_catalog`).
**Notes:** "The cache build should run all the process, but we should also have like an advance option (using the same component of vision match, remember dry) with the option to trigger individual jobs." DRY mandate from Phase 7 retained — `AdvancedOptions` is reused, not duplicated.

---

## G4 — Wider-search fallback placement (REJECTED)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Skipped filter in `MatchesTab` with per-row "Search wider" | | |
| B. Force-match action in `InstagramTab` row/detail | | |
| C. Post-job banner linking to A or B | | |
| **D. Drop the requirement entirely** | MATCH-03 was Claude-introduced, not user-requested | ✓ |

**User's choice:** D — Drop. "When did I ask for a UI to retry when there is no candidates? I don't see why are we talking about this."
**Notes:** MATCH-03 was added by Claude as a defensive safety net for the case where the new CLIP shortlist returns zero candidates. The user never requested it. Removed from `REQUIREMENTS.md`, `ROADMAP.md`, and `STATE.md` before the context was finalized. Phase 8 now scopes only MATCH-02 and CACHE-01.

---

## Claude's Discretion

- Exact UI copy for "Build cache" button and Advanced section labels.
- Single composite job handler vs sequential enqueue with dependencies — whichever cleanly preserves resume/cancel semantics.
- Default behavior when prior cache stages are missing/incomplete (block, warn, or auto-trigger).
- Numeric min/max bounds on the per-run top-k override.

## Deferred Ideas

- Embedding model A/B benchmark — `.planning/todos/pending/benchmark-embedding-recall.md`
- Embed job discoverability + path failure follow-up — `.planning/todos/pending/2026-04-26-fixes-for-embed-job-discoverability-and-path-failures.md`
- Backend restart and compression fix — `.planning/todos/pending/2026-04-26-plan-backend-restart-and-compression-fix.md`
