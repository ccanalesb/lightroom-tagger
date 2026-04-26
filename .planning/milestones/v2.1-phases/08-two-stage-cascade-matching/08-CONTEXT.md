# Phase 8: Two-stage cascade matching — Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the broken description signal in `vision_match` and introduce a proper two-stage cascade per batch of candidates: text-only description comparison first, then vision image comparison, scores merged by weighted average. Adds `compare_descriptions_batch` as a new text-only API call, `skip_undescribed` job option, and UI controls in the existing job launcher. Both backend logic and frontend controls are in scope.

</domain>

<decisions>
## Implementation Decisions

### Description join fix (SC-1)
- **D-01:** `find_candidates_by_date` must join `image_descriptions` so each candidate dict carries its AI summary. The join populates `catalog_img.get('description')` (or equivalent key) for described images — empty string for undescribed ones. Planner decides exact SQL join form (LEFT JOIN on `image_key` or equivalent FK).

### `compare_descriptions_batch` design (SC-2)
- **D-02:** Reference text = the **AI summary of the Instagram image** (from `image_descriptions` table), not the Instagram post caption. This is a catalog-summary-vs-catalog-summary comparison — semantically consistent.
- **D-03:** If the Instagram image has no AI summary yet, **describe it on-the-fly** using the existing description methods (same path as `handle_single_describe` / `generate_description` in `vision_client.py`) before running the description batch. No new describe infrastructure needed.
- **D-04:** Response shape matches `compare_images_batch` exactly: `{"results": [{"id": N, "confidence": 0-100}]}`. Downstream scoring code stays symmetric — same merge logic works for both stages.
- **D-05:** `compare_descriptions_batch` is a text-only call — no image encoding, no base64. Uses the same provider/model as vision (same `client` + `model` args) but sends only text content parts.

### Two-stage pipeline (SC-3, SC-4)
- **D-06:** Per batch of 20 candidates: description stage runs first (if `desc_weight > 0`), vision stage runs second (if `vision_weight > 0`). Scores merged as weighted average — same formula already in `score_candidates_with_vision`.
- **D-07:** When `vision_weight=0`: skip all image compression, vision cache reads/writes, and vision API calls entirely. Zero vision API calls — description-only run.
- **D-08:** Backward-compatible: existing `vision_weight=1, desc_weight=0` behaviour unchanged — description stage is skipped, pipeline is pure vision as before.

### `skip_undescribed` option (SC-5, SC-6)
- **D-09:** `skip_undescribed` is a boolean job option, default `true`. When `true`: candidates without an AI summary receive score 0 on the description stage (no API call, no inline describe). When `false`: the candidate is described inline before the description stage runs.
- **D-10:** No division-by-zero or silent weight redistribution. If description stage produces no usable scores (all skipped), the weight is not redistributed to vision — it stays at 0 contribution. Final weighted average uses the defined weights regardless.

### Frontend controls (SC-8)
- **D-11:** `skip_undescribed` toggle is added to `AdvancedOptions.tsx` alongside the existing `descWeight`, `visionWeight`, `phashWeight` sliders. No new section or component needed.
- **D-12:** Toggle is **disabled (greyed out)** when `descWeight === 0` — the option only matters when the description stage runs.
- **D-13:** Default state: **ON (true)** — skip undescribed candidates. Matches backend default. No surprise inline-describe API calls for the user.
- **D-14:** `matchOptionsContext` grows a `skipUndescribed: boolean` field (default `true`). `useMatchOptions` exposes it via `updateOption`. `MatchingTab` passes it in the job payload as `skip_undescribed`.
- **D-15:** The existing `descWeight` slider is already in `AdvancedOptions.tsx` and wired to the job payload (`weights.description`). No changes needed to the slider itself — it just needs to be verified it's surfaced and functional.

### Claude's Discretion
- Exact SQL join form for description join in `find_candidates_by_date` (LEFT JOIN shape, column alias)
- Whether `compare_descriptions_batch` lives in `vision_client.py` (alongside `compare_images_batch`) or a new file
- Batch size for description stage (may differ from vision batch size of 10/20)
- How inline-describe for the Instagram image is triggered (direct `generate_description` call vs reusing `_run_describe_pass` helper)
- Test file naming and coverage structure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in ROADMAP.md Phase 8 and decisions above.

### Key source files (read before planning)
- `lightroom_tagger/core/matcher.py` — `find_candidates_by_date`, `score_candidates_with_vision`, `match_dump_media` — the core matching pipeline being modified
- `lightroom_tagger/core/vision_client.py` — `compare_images_batch`, `generate_description` — template for `compare_descriptions_batch` and on-the-fly describe
- `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx` — existing weight sliders, where `skip_undescribed` toggle lands
- `apps/visualizer/frontend/src/stores/matchOptionsContext.tsx` — `useMatchOptions` hook, `MatchOptions` type — grows `skipUndescribed` field
- `apps/visualizer/frontend/src/components/processing/MatchingTab.tsx` — job payload assembly, where `skip_undescribed` is passed to backend
- `apps/visualizer/backend/jobs/handlers.py` — `handle_vision_match` — job handler that calls `match_dump_media`

### Success criteria anchor
- `.planning/ROADMAP.md` §"Phase 8" — 8 success criteria (SC-1 through SC-8), all must pass

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `compare_images_batch` (`vision_client.py:172`) — exact template for `compare_descriptions_batch`: same client/model args, same return shape `dict[int, float]`, same error handling pattern
- `generate_description` (`vision_client.py:318`) — existing on-the-fly describe for Instagram image (D-03)
- `score_candidates_with_vision` (`matcher.py:136`) — already has `desc_weight` / `vision_weight` parameters and weighted merge logic; extend in-place rather than rewrite
- `matchOptionsContext.tsx` — already stores `phashWeight`, `descWeight`, `visionWeight`; extend with `skipUndescribed: boolean`
- `AdvancedOptions.tsx` — already renders three weight sliders; `skip_undescribed` toggle appends naturally

### Established Patterns
- `{"results": [{"id": N, "confidence": 0-100}]}` JSON shape — used by `compare_images_batch`; `compare_descriptions_batch` must return the same shape
- `LEFT JOIN image_descriptions d` pattern already appears in `handlers.py` (lines 136, 186) for other candidate queries — same JOIN form for `find_candidates_by_date`
- `updateOption(key, value)` pattern for `matchOptionsContext` — `skipUndescribed` follows the same setter

### Integration Points
- `find_candidates_by_date` → add LEFT JOIN `image_descriptions` so `candidate['description']` (or `'summary'`) is populated
- `score_candidates_with_vision` → description stage runs before vision stage, using `compare_descriptions_batch`
- `handle_vision_match` → reads `skip_undescribed` from `metadata`, passes to `match_dump_media`
- `MatchingTab.tsx` → adds `skip_undescribed: options.skipUndescribed` to job payload

</code_context>

<specifics>
## Specific Ideas

- `compare_descriptions_batch` uses text-content parts only (no `_image_url_part` calls) — pure text API call to the same provider
- `skip_undescribed` toggle in `AdvancedOptions` should be visually grouped near the `descWeight` slider (they are related — both control description-stage behaviour)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-two-stage-cascade-matching*
*Context gathered: 2026-04-21*
