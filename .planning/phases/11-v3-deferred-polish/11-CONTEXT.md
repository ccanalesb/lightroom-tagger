# Phase 11: v3.0 Deferred Polish — Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Close 7 deferred low-severity items from Phase 7 and Phase 8 reviews, plus the embed-job discoverability todo. No new features. No design changes to the matching cascade or cache pipeline. No broader refactors.

</domain>

<decisions>
## Implementation Decisions

### stack_size drift (Phase 7 review low #5)
- **D-01:** Document and accept. `image_stacks.stack_size` is updated on every known mutation (set_representative, split, merge). Drift is theoretical — no known real occurrence. Add a code comment in `database.py` near the column definition and mutation sites explaining the pre-existing drift risk and why `stack_metadata_for_api` is the authoritative source for API responses. No behavior change.

### Tool-calling pin schema (Phase 7 review low #3)
- **D-02:** Document and defer. `get_catalog_schema` continues to return global catalog counts even when a pin is active. Add a code comment explaining that results are restricted by `restrict_to_keys` at execution time despite schema showing global stats. No changes to schema output. Phase 7 review already classified this as "optional future hardening."

### `vision_judgments_total` label (Phase 8 IN-08-03)
- **D-03:** Add inline comment only. Keep the stats dict key `vision_judgments_total` and log label `judgments=` unchanged to avoid breaking any log parsers or monitoring. Add an inline comment in `handlers.py` explaining that this counter tracks shortlisted catalog candidates processed through `score_candidates_with_vision`, not a count of LLM HTTP calls.

### Embed discoverability CTA scope
- **D-04:** Navigation links only. `SearchPage.tsx` shows warning text + help line + "Open Catalog Cache" link + "Open Job Queue" link when `pin_state: 'inactive'` with `fallback_reason: 'no_clip_embedding'`. No inline enqueue button in `SearchPage`. User navigates to Processing tab to start the job.

### Claude's Discretion
- Exact wording of the `stack_size` and `get_catalog_schema` code comments — keep them concise, operator-facing.
- Exact strings.ts key names for the embed discoverability help line and navigation links (follow UI-SPEC naming conventions: `SEARCH_PIN_WARN_NO_CLIP`, `PROCESSING_CATALOG_CACHE_ROUTE`, `PROCESSING_OPEN_JOB_QUEUE`).
- Whether to add `type="button"` to the AdvancedOptions disclosure button (UI-SPEC marks as defensive/optional).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and deferred items
- `.planning/ROADMAP.md` §Phase 11 — canonical list of 7 gap-closure items and success criteria
- `.planning/phases/11-v3-deferred-polish/11-UI-SPEC.md` — full visual/interaction/copywriting contract; approved 2026-05-02. **MUST read before touching any frontend file.**

### Source files to change
- `apps/visualizer/frontend/src/components/matching/AdvancedOptions.tsx` — aria-expanded fix (IN-08-01)
- `apps/visualizer/frontend/src/components/processing/CatalogCacheTab.tsx` — inline copy centralization (IN-08-02) + NAS troubleshooting copy
- `apps/visualizer/frontend/src/constants/strings.ts` — all copy additions/moves for Phase 11
- `apps/visualizer/frontend/src/components/ui/ConfirmUndoAction.tsx` — useUndoToast message-only fix (Phase 7 low #4)
- `apps/visualizer/backend/jobs/handlers.py` — vision_judgments_total comment (IN-08-03)
- `lightroom_tagger/core/database.py` — stack_size comment (Phase 7 low #5)
- `apps/visualizer/frontend/src/components/search/SearchPage.tsx` — embed discoverability warning + links

### Prior phase artifacts
- `.planning/phases/08-embedding-prefilter-and-cache-pipeline/08-REVIEW.md` — original IN-08-01, IN-08-02, IN-08-03 text
- `.planning/phases/07-stacks-in-matching-pin-similarity/07-REVIEW.md` — original Phase 7 low #3, #4, #5 text
- `.planning/phases/08-embedding-prefilter-and-cache-pipeline/08-UI-SPEC.md` — design system inherited by Phase 11

### Embed job discoverability todo
- `.planning/todos/pending/2026-04-26-fixes-for-embed-job-discoverability-and-path-failures.md` — full problem description and solution items 1–6

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useUndoToast` + `UndoToastBar` in `ConfirmUndoAction.tsx` — the bug is in `offerUndo`: when `onUndo` is omitted it immediately calls `setToast({ kind: 'hidden' })` instead of showing a timed message-only toast. Fix is a branch in that early-return block.
- `CatalogCacheTab.tsx` enqueue pattern (success row + Open Job Queue button) — **not** being reused in SearchPage per D-04, but useful reference for how the job queue navigation is done.
- `strings.ts` already has `PROCESSING_OPEN_JOB_QUEUE`, `PROCESSING_JOB_QUEUE_ROUTE`, `CATALOG_CACHE_*` constants — reuse these for embed discoverability links.

### Established Patterns
- All user-visible copy in `strings.ts` — Phase 11 must move CatalogCacheTab inline strings and add SearchPage embed-discoverability strings there.
- `aria-expanded={isOpen}` + `aria-controls` disclosure pattern — not yet used in AdvancedOptions; add it. See UI-SPEC for exact attribute contract.
- Amber utility classes (`text-amber-600` / `dark:text-amber-400`) for pin/embed warnings — already used in SearchPage; do not introduce new warning tokens.

### Integration Points
- `SearchPage.tsx` reads `pin_state` and `fallback_reason` from API response — warning block already exists; extend it with help line + navigation links.
- `image_stacks.stack_size` is updated in `database.py` at lines ~1906, ~1980, ~2031 — comment goes near these mutation sites and the column definition (~839).
- `vision_judgments_total` accumulation is in `handlers.py` around `stats['vision_judgments_total'] += len(vision_candidates)` — comment goes inline there.

</code_context>

<specifics>
## Specific Ideas

- UI-SPEC approved 2026-05-02 with one non-blocking flag: finalize exact strings.ts key names for the embed help line before execution. Names suggested: `SEARCH_PIN_WARN_NO_CLIP` (warning text), `SEARCH_PIN_HELP_EMBED` (help line), `SEARCH_PIN_LINK_CACHE` (link label), `SEARCH_PIN_LINK_JOBS` (link label).
- Embed discoverability secondary surface: add ≤40-word NAS troubleshooting paragraph to `CatalogCacheTab` (below stats or cache-location footnote area) as a single `strings.ts` constant.
- `useUndoToast` fix: the message-only toast must use `role="status"` and `aria-live="polite"` per UI-SPEC — same as the existing undo bar.

</specifics>

<deferred>
## Deferred Ideas

- `CollapsibleSection` (processing pipeline disclosure) — UI-SPEC explicitly defers aria-expanded/aria-controls pattern there to a later pass.
- Tool-calling pin schema stat scoping (D-02) — deferred to a future phase if it becomes a real LLM accuracy issue.
- `vision_judgments_total` full rename to `candidate_evaluations` (D-03) — deferred; would require log parser updates.
- Backend preflight path-check and grouped skip-count summary (embed todo items 3–4) — not in Phase 11 scope; todo item 6 (virtual stacking decision) was resolved in Phase 8.
- Inline Start embed CTA in SearchPage (D-04) — deferred; navigation links are sufficient for now.

</deferred>

---

*Phase: 11-v3-deferred-polish*
*Context gathered: 2026-05-04*
