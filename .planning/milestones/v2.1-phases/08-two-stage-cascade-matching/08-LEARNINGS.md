---
phase: 8
phase_name: "Two-stage cascade matching"
project: "Lightroom Tagger & Analyzer"
generated: "2026-04-21"
counts:
  decisions: 7
  lessons: 5
  patterns: 5
  surprises: 3
missing_artifacts:
  - "08-UAT.md"
---

# Phase 8 Learnings: Two-stage cascade matching

## Decisions

### Separate `ai_summary` field — never overwrite Lightroom `description`
The AI-generated image summary from `image_descriptions` is exposed as `ai_summary` on each candidate dict. It is not copied into `description`, which remains the Lightroom/metadata caption. Two parallel text fields with distinct semantics coexist without collision.

**Rationale:** `description` is a user-authored Lightroom caption (metadata field in `images` table). Overwriting it with AI text would silently destroy data and break downstream consumers that rely on the caption for display. A separate key makes the provenance unambiguous and avoids any renaming cascade across the codebase.
**Source:** 08-CONTEXT.md (D-01), 08-01-PLAN.md, 08-01-SUMMARY.md

---

### `compare_descriptions_batch` lives in `vision_client.py` alongside `compare_images_batch`
The new text-only batch comparison function was placed immediately after `compare_images_batch` in `vision_client.py`, sharing the same module rather than a new file.

**Rationale:** Both functions share identical API contracts (`dict[int, float]`, same JSON shape, same error-handling pattern via `_map_openai_error`). Co-location makes the mirror relationship explicit and keeps imports simple for callers.
**Source:** 08-01-PLAN.md, 08-01-SUMMARY.md

---

### Nominal fixed weights — no `weight_sum` redistribution
When description scores are zero (all candidates skipped), the `desc_weight` contribution is simply `desc_weight * 0 = 0`. The weight is not redistributed to vision or pHash. The total score uses the user-defined weights as-is regardless of which stages produced non-zero output.

**Rationale:** Silent redistribution (the old `desc_available` / `weight_sum` pattern) caused scores to shift depending on which candidates happened to have descriptions — making results non-reproducible and hard to reason about. Nominal weights mean the same weights always produce the same scoring math.
**Source:** 08-CONTEXT.md (D-10), 08-02-PLAN.md, 08-02-SUMMARY.md

---

### `skip_undescribed=True` default — no surprise inline-describe API calls
When candidates have no AI summary, the description stage assigns score 0 without making any API call. The `False` path (inline-describe on the fly) exists but is opt-in.

**Rationale:** Inline-describe on every undescribed candidate during matching would make job duration unpredictable and incur silent API costs. The default is conservative — user explicitly opts into the more expensive path by toggling the UI control.
**Source:** 08-CONTEXT.md (D-09, D-13), 08-03-PLAN.md

---

### `skip_undescribed` included in checkpoint fingerprint
The flag is added to the `fingerprint_vision_match` payload so that changing it between runs invalidates the checkpoint and forces a fresh run rather than resuming with stale results.

**Rationale:** A resume that inherits the wrong `skip_undescribed` value would produce silently wrong scores (e.g., resuming a full-describe run with `skip_undescribed=True`). Including it in the fingerprint makes the checkpoint hash sensitive to the flag value.
**Source:** 08-03-PLAN.md, 08-03-SUMMARY.md

---

### UI toggle disabled when `descWeight === 0`
The `skipUndescribed` checkbox in `AdvancedOptions` is disabled (greyed out) whenever the description weight slider is at zero.

**Rationale:** The toggle only affects the description stage — when that stage is off (`descWeight === 0`), the option has no effect. Disabling it prevents confusing active controls that do nothing.
**Source:** 08-CONTEXT.md (D-12), 08-03-PLAN.md

---

### Vision guard covers batch AND sequential fallback paths
The `vision_weight == 0` skip must be applied in both the batch code path and the sequential (non-batch) fallback inside `score_candidates_with_vision`. A guard on only one path would leave the other silently making vision API calls.

**Rationale:** `score_candidates_with_vision` has two execution branches (batch via `_call_batch_chunk` and sequential via `compare_with_vision`). Missing the guard on either branch would mean `vision_weight=0` mode still makes vision API calls under certain concurrency or threshold conditions.
**Source:** 08-02-PLAN.md (task acceptance criteria), 08-VERIFICATION.md (SC-4)

---

## Lessons

### The old `desc_available` renormalization was a silent weight corruption bug
Prior to Phase 8, `score_candidates_with_vision` had `desc_available` logic that would subtract `desc_weight` from the normalizing denominator when a candidate had no description — effectively boosting the remaining weights. This produced different effective weights depending on whether a candidate was described, making the scoring non-reproducible and hard to debug.

**Context:** The bug was only surfaced when writing the Phase 8 spec — it hadn't been caught because the test suite tested totals but not the mathematical invariant that weights should always sum to the same nominal value.
**Source:** 08-02-PLAN.md (acceptance criteria: `rg "desc_available" → no matches`), 08-02-SUMMARY.md

---

### `MATCH_DETAIL_VISION_LABEL` was reused for two semantically distinct badges
`MatchScoreBadges` used `MATCH_DETAIL_VISION_LABEL` for both the vision verdict pill ("Vision: UNCERTAIN") and the vision numeric score pill ("Vision: 100%"). This caused the UI to show two pills with the same prefix but different content — confusing to interpret.

**Context:** Discovered during user review after Phase 8 execution. A match run with `vision_weight=0` still showed "Vision: UNCERTAIN" because the batch path hardcoded `vision_result: 'UNCERTAIN'` as a fallback value even when vision was never used.
**Source:** Post-phase fix commit `fix(match-badges): show desc score, hide vision badges when vision not run`

---

### Vision UNCERTAIN + score 0 is ambiguous — could mean "skipped" or "genuinely uncertain"
When `vision_weight=0`, the batch path stored `vision_result: 'UNCERTAIN'` and `vision_score: 0.0` — the same values that appear when vision ran but returned a genuinely uncertain result. The frontend could not distinguish these two states.

**Context:** The fix was to add `visionWasUsed()` logic: vision badges only render when `vision_result` is SAME/DIFFERENT (a definitive verdict) or `vision_score > 0` (a non-trivial score). This makes the "skipped" state invisible in the UI rather than misleadingly labeled.
**Source:** Post-phase `MatchScoreBadges.tsx` fix

---

### Description score (`desc_similarity`) was in the API type but never surfaced in the UI
The `Match` interface had `desc_similarity?: number` since before Phase 8, but `MatchScoreBadges` never rendered it. Users running description-weighted jobs had no visibility into how much the description signal contributed.

**Context:** Discovered during the same post-phase badge review. Fixed by adding an amber "Description: X%" pill when `desc_similarity > 0`.
**Source:** Post-phase `MatchScoreBadges.tsx` fix, `api.ts` line 906

---

### LEFT JOIN pattern for `image_descriptions` already existed in handlers.py
The exact LEFT JOIN form needed for `find_candidates_by_date` was already established in `handlers.py` (lines 136, 186) for other candidate queries in the same project. The planner could have referenced these as the canonical JOIN template.

**Context:** This reduced implementation uncertainty — rather than designing the join from scratch, the executor could mirror an already-working pattern.
**Source:** 08-CONTEXT.md (Established Patterns section), 08-01-PLAN.md

---

## Patterns

### Mirror function pattern: text-only sibling to a vision batch function
`compare_descriptions_batch` was implemented as a structural mirror of `compare_images_batch`: same signature shape, same return type, same JSON contract, same error handling via `_map_openai_error`, same Claude `extra_body` pattern, same parse-failure all-zeros fallback. The only difference is the content type (text vs. image).

**When to use:** When adding a new modality or variant of an existing LLM batch call — start from the existing function's structure, replace content-type-specific parts, and keep all API contract and error-handling logic identical. This keeps callers symmetric and test patterns transferable.
**Source:** 08-01-PLAN.md (task 02), 08-01-SUMMARY.md

---

### Stage guard pattern: weight > 0 gates the entire stage
Each scoring stage (description, vision) is gated by `if weight > 0:`. When the weight is zero, the stage's entire execution path — including any I/O, compression, API calls, and cache writes — is skipped. The score for that stage is set to `0.0` without any computation.

**When to use:** Any time a scoring or processing stage is optional based on a weight or flag. The guard should cover all I/O in the stage (network calls, disk reads, cache writes), not just the API call itself.
**Source:** 08-02-PLAN.md (SC-4 acceptance criteria), 08-VERIFICATION.md

---

### Nominal linear weighted sum for multi-signal scoring
`total = (w_phash * s_phash) + (w_desc * s_desc) + (w_vision * s_vision)` — fixed weights, no normalization, no redistribution when a stage produces zeros. Each weight's contribution scales linearly with the score for that stage.

**When to use:** Any multi-signal merge where the user specifies relative weights. Avoid normalizing by active weight count — it destroys the user's intent. A zero score from a skipped stage should contribute zero, not cause the other weights to inflate.
**Source:** 08-02-PLAN.md (D-10), 08-02-SUMMARY.md

---

### Fingerprint-includes-all-options pattern for resumable jobs
`fingerprint_vision_match` includes every option that affects job output — weights, threshold, date range, `force_*` flags, and now `skip_undescribed`. Changing any of these invalidates the checkpoint hash and forces a fresh run.

**When to use:** Any job option that changes the computation or output should be included in the fingerprint. Options that only affect logging or display (not results) can be omitted.
**Source:** 08-03-PLAN.md (task 03-handlers-checkpoint), 08-03-SUMMARY.md

---

### Disable-when-irrelevant pattern for coupled UI controls
The `skipUndescribed` checkbox is `disabled={descWeight === 0}` with `opacity-50 cursor-not-allowed` on the wrapper. When a control only applies when another control is in a certain state, disable (not hide) it to communicate the dependency visually.

**When to use:** Prefer `disabled` over `hidden` for coupled controls — hiding removes affordance entirely, while disabled shows the control exists but communicates it is currently inapplicable. Use `opacity-50 cursor-not-allowed` as the visual treatment for greyed-out controls.
**Source:** 08-CONTEXT.md (D-12), 08-03-PLAN.md

---

## Surprises

### Both the batch path and sequential path needed the vision guard — independently
The vision guard (`if vision_weight > 0`) needed to be applied to both execution branches of `score_candidates_with_vision`. The plan correctly anticipated this, but it was a non-obvious requirement: code review of the sequential path separately from the batch path was needed.

**Impact:** If only the batch path had been guarded, the sequential fallback (triggered under certain candidate counts or concurrency settings) would still make vision API calls even with `vision_weight=0`. The test `test_vision_weight_zero_skips_compare_images_and_compression` was written to cover the batch path — a separate review of the sequential path was required.
**Source:** 08-02-PLAN.md (acceptance criteria), 08-VERIFICATION.md (SC-4)

---

### The `vision_result` field silently defaulted to UNCERTAIN everywhere vision was skipped
The batch path's `vision_weight=0` branch hardcoded `'vision_result': 'UNCERTAIN'` on every result row — the same sentinel used when vision ran but couldn't reach a SAME/DIFFERENT decision. This leaked into the UI as an always-present "Vision: UNCERTAIN" badge that users couldn't interpret.

**Impact:** Users had no way to tell whether "UNCERTAIN" meant "vision ran but was unsure" vs. "vision was never used." Required a post-phase fix to the badge rendering logic. The fix (`visionWasUsed()` guard in `MatchScoreBadges`) is straightforward but wouldn't have been needed if the backend had used a distinct sentinel (e.g., `'vision_result': 'SKIPPED'`) for the no-vision path.
**Source:** Post-phase `MatchScoreBadges.tsx` fix, 08-02-SUMMARY.md

---

### `desc_similarity` had been in the `Match` type for multiple phases but was never displayed
The field existed in the frontend `Match` interface (presumably added when description scoring was first introduced) but `MatchScoreBadges` never rendered it. Phase 8 made description scoring meaningful for the first time — which is when the missing badge became noticeable.

**Impact:** Users running description-weighted jobs after Phase 8 would see a match score but no breakdown showing how much description contributed. Fixed post-phase. Going forward: any new scoring signal added to the backend should be simultaneously surfaced in the badge row — the type alone is not sufficient visibility.
**Source:** Post-phase `MatchScoreBadges.tsx` fix, `api.ts` line 906
