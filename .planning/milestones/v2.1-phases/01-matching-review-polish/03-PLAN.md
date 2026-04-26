---
plan: 03
title: Frontend types and string constants for match polish
wave: 1
depends_on: []
files_modified:
  - apps/visualizer/frontend/src/services/api.ts
  - apps/visualizer/frontend/src/constants/strings.ts
autonomous: true
requirements:
  - POLISH-01
  - POLISH-02
---

<objective>
Add typed support for `all_rejected` on `MatchGroup` and centralize all new user-visible strings for reject acknowledgment, tombstones, and the validated-bucket divider per **D-14**, so later UI plans import constants instead of inline literals.
</objective>

<context>
Implements **D-14** (all new copy flows through `constants/strings.ts`). Types in `api.ts` align the SPA with the extended `list_matches` payload from plan `01` (`all_rejected` on `match_groups[]`).
</context>

<tasks>
<task id="3.1">
<action>In `apps/visualizer/frontend/src/services/api.ts` on `MatchGroup` (interface starts line 772), add optional field `all_rejected?: boolean` (or required `boolean` defaulting interpretation in consumers — pick one style consistent with nearby interfaces). No runtime code change beyond the type surface unless `MatchingAPI.list` response typing needs a narrow cast.</action>
<read_first>
- apps/visualizer/frontend/src/services/api.ts
- apps/visualizer/backend/api/images.py (`list_matches` group dict keys — verify `all_rejected` spelling matches exactly)
</read_first>
<acceptance_criteria>
- `rg -n "all_rejected" apps/visualizer/frontend/src/services/api.ts` shows `all_rejected` inside `MatchGroup`
- `cd apps/visualizer/frontend && npx eslint --max-warnings 0 src/services/api.ts src/constants/strings.ts` exits 0
</acceptance_criteria>
</task>

<task id="3.2">
<action>In `apps/visualizer/frontend/src/constants/strings.ts` near existing `MATCH_*` exports (~472+), add: `MATCH_DETAIL_REJECTED_LABEL = 'Rejected'`; `MATCH_TOMBSTONE_NO_MATCH_BADGE = 'No match'`; `MATCHES_VALIDATED_DIVIDER_LABEL = '— Validated —'` (exact Unicode em dashes per CONTEXT D-13); `MATCH_TOMBSTONE_CARD_ARIA_LABEL` (descriptive string for the non-clickable tombstone card, e.g. "Reviewed Instagram post with no remaining catalog matches"); optional `MATCH_DETAIL_REJECTED_AUTOCLOSE_MS` if you expose the 1500ms delay as a named constant in TS (otherwise plans 04/05 use numeric `1500` with grep acceptance).</action>
<read_first>
- apps/visualizer/frontend/src/constants/strings.ts
- .planning/phases/01-matching-review-polish/01-CONTEXT.md (D-13, D-14)
- apps/visualizer/frontend/DESIGN.md (AGENTS.md design-system pointer — naming only, no styling in this file)
</read_first>
<acceptance_criteria>
- `rg -n "MATCHES_VALIDATED_DIVIDER_LABEL|MATCH_DETAIL_REJECTED_LABEL|MATCH_TOMBSTONE_NO_MATCH_BADGE" apps/visualizer/frontend/src/constants/strings.ts` returns three lines (one per constant)
- `rg "— Validated —" apps/visualizer/frontend/src/constants/strings.ts` returns exactly the divider constant definition line
</acceptance_criteria>
</task>
</tasks>

<verification>
- `rg -n "MATCH_DETAIL_REJECTED_LABEL|MATCHES_VALIDATED_DIVIDER_LABEL" apps/visualizer/frontend/src/constants/strings.ts` exits 0
- `cd apps/visualizer/frontend && npm run lint` exits 0
</verification>

<must_haves>
- `MatchGroup` type documents `all_rejected` for consumers.
- All new Phase 1 match-review strings exist as named exports in `strings.ts` (no raw new user strings in components except re-exports).
- Phase 1 roadmap strings for divider and reject states are centralized per project convention.
</must_haves>
