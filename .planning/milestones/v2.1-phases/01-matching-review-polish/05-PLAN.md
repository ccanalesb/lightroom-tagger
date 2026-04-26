---
plan: 05
title: MatchesTab bucket divider, tombstone cards, and hook tombstone state
wave: 2
depends_on:
  - "01"
  - "03"
files_modified:
  - apps/visualizer/frontend/src/hooks/useMatchGroups.ts
  - apps/visualizer/frontend/src/hooks/__tests__/useMatchGroups.handleRejected.test.tsx
  - apps/visualizer/frontend/src/components/images/MatchesTab.tsx
autonomous: true
requirements:
  - POLISH-01
  - POLISH-02
---

<objective>
Keep fully-rejected groups visible as non-interactive tombstones, preserve server ordering without client reorder fights, render the validated-bucket divider, and wire modal props so the Phase 1 review flow matches the locked UX decisions end-to-end.
</objective>

<context>
Implements **D-10** (tombstone card: no Lightroom thumbnails, Instagram thumbnail visible, `Badge` “No match”, `all_rejected` / empty candidates retained in hook state, not clickable, `useMatchGroups.handleRejected` keeps group instead of `flatMap` removal when `remaining.length === 0`, do not decrement `total` in that branch). Implements **D-13** (subtle divider row labeled `MATCHES_VALIDATED_DIVIDER_LABEL` only when both buckets non-empty). Depends on plan **01** for API semantics and plan **03** for string exports / `MatchGroup.all_rejected` typing.
</context>

<tasks>
<task id="5.1">
<action>In `apps/visualizer/frontend/src/hooks/useMatchGroups.ts` inside `handleRejected` (starts line 44): when `remaining.length === 0`, return a **single** updated group object `{ ...group, candidates: [], candidate_count: 0, best_score: 0, has_validated: false, all_rejected: true }` wrapped in a one-element array instead of `return []` (lines 56–58); **remove** or bypass the `removedEntireGroup` / `setTotal((c) => c - 1)` branch (lines 70–72) when transitioning to tombstone so `total` stays unchanged. Ensure `fetchGroups` pagination merge (lines 15–22) does not duplicate the same `instagram_key` when refreshing — tombstone replaces prior row by key. Add `apps/visualizer/frontend/src/hooks/__tests__/useMatchGroups.handleRejected.test.tsx` (Vitest + Testing Library) that drives `handleRejected` until the `remaining.length === 0` tombstone path runs and asserts `total` is unchanged across that transition.</action>
<read_first>
- apps/visualizer/frontend/src/hooks/useMatchGroups.ts
- apps/visualizer/frontend/src/services/api.ts (`MatchGroup`)
- .planning/phases/01-matching-review-polish/01-CONTEXT.md (D-10)
</read_first>
<acceptance_criteria>
- `rg -n "all_rejected" apps/visualizer/frontend/src/hooks/useMatchGroups.ts` returns at least one line in `handleRejected`
- `rg -n "remaining.length === 0" apps/visualizer/frontend/src/hooks/useMatchGroups.ts` shows branch returning tombstone object, not `return []`
- `cd apps/visualizer/frontend && npm test -- --run src/hooks/__tests__/useMatchGroups.handleRejected.test.tsx` exits 0; at least one test rejects the last remaining candidate until the group becomes a tombstone (`all_rejected` / empty `candidates`) and asserts `total` (the hook’s `total` / `total_groups` mirror) is **unchanged** from immediately before that final reject — this replaces a non-verifiable “manual read” of `setTotal`
</acceptance_criteria>
</task>

<task id="5.2">
<action>In `apps/visualizer/frontend/src/components/images/MatchesTab.tsx`: (1) Import `MATCHES_VALIDATED_DIVIDER_LABEL`, `MATCH_TOMBSTONE_NO_MATCH_BADGE`, `MATCH_TOMBSTONE_CARD_ARIA_LABEL` from `../../constants/strings`. (2) Before `matchGroups.map`, derive `unvalidatedGroups = matchGroups.filter((g) => !g.has_validated && !g.all_rejected)` and `reviewedGroups = matchGroups.filter((g) => g.has_validated || g.all_rejected)` (adjust if `all_rejected` optional — treat truthy only). (3) Render `unvalidatedGroups` first; if **both** `unvalidatedGroups.length > 0` and `reviewedGroups.length > 0`, insert a full-width subtle divider row between sections with centered text `{MATCHES_VALIDATED_DIVIDER_LABEL}` (**D-13**). (4) Map `reviewedGroups` similarly to current cards but: if `g.all_rejected || g.candidate_count === 0`, render **no** catalog thumbnail strip, keep Instagram thumbnail (`/api/images/instagram/.../thumbnail` pattern lines 83–88), show `Badge variant="error"` with `{MATCH_TOMBSTONE_NO_MATCH_BADGE}`, set root container `aria-label={MATCH_TOMBSTONE_CARD_ARIA_LABEL}`, **omit** the `Button` that calls `openReview` (lines 101–103) so the card is not openable (**D-10**). (5) Update modal mount guard at lines 119–129 so `MatchDetailModal` renders **only** when `liveGroup != null && liveGroup.candidates.length > 0 && liveMatch != null` (adjust for optional fields with `?.` / truthy checks as needed, but preserve this logic: **no** candidates ⇒ **no** modal). When a group becomes a tombstone (`all_rejected === true` and/or `candidates.length === 0`), `liveMatch` must become null (or the guard must otherwise fail) so the modal **does not** stay mounted or re-open on that card — tombstone cards never call `openReview` (**D-10**). Plan 04’s in-modal reject animation finishes while candidates still exist; once the hook flips to tombstone, this guard closes the modal cleanly.</action>
<read_first>
- apps/visualizer/frontend/src/components/images/MatchesTab.tsx
- apps/visualizer/frontend/src/hooks/useMatchGroups.ts
- apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx
- apps/visualizer/frontend/DESIGN.md
- .planning/phases/01-matching-review-polish/01-CONTEXT.md (D-13, D-10)
</read_first>
<acceptance_criteria>
- `rg -n "MATCHES_VALIDATED_DIVIDER_LABEL" apps/visualizer/frontend/src/components/images/MatchesTab.tsx` returns divider render line
- `rg -n "MATCH_TOMBSTONE_NO_MATCH_BADGE|all_rejected" apps/visualizer/frontend/src/components/images/MatchesTab.tsx` returns at least one line each (or `all_rejected` via optional chaining)
- `rg -n "openReview" apps/visualizer/frontend/src/components/images/MatchesTab.tsx` shows `openReview` only on non-tombstone branch (e.g. wrapped in conditional)
- Modal mount guard is grep-verifiable: `rg -n "MatchDetailModal" apps/visualizer/frontend/src/components/images/MatchesTab.tsx` lands on JSX that is wrapped (same line or immediate parent `{... && (` chain) with **both** `liveGroup.candidates.length > 0` (allow `liveGroup?.candidates.length`) **and** `liveMatch` truthy checks — `rg -n "candidates\\.length\\s*>\\s*0" apps/visualizer/frontend/src/components/images/MatchesTab.tsx` and `rg -n "liveMatch" apps/visualizer/frontend/src/components/images/MatchesTab.tsx` each hit the **same** conditional block as the `MatchDetailModal` render (line numbers within a small window, e.g. ≤5 lines apart)
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npm run lint` exits 0
- `cd apps/visualizer/backend && PYTHONPATH=. python -m pytest tests/test_match_groups.py tests/test_match_validation.py -q` exits 0 (regression with backend plan 01/02 landed)
- Manual smoke: open Images → Matches, reject last candidate in a group, confirm card becomes tombstone without disappearing and divider appears when mixed buckets exist
</verification>

<must_haves>
- Matches list visually separates actionable groups from reviewed groups when both exist (roadmap Phase 1 success criterion 3 — UX complement to sort).
- Fully-rejected groups remain visible with a clear “No match” / non-actionable treatment per **D-10**.
- `total` count stays stable when a group becomes a tombstone (no erroneous “Load more” drift solely from local reject).
</must_haves>
