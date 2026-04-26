# Phase 1: Matching & review polish - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Smooth the match-confirmation flow in the Matches tab and `MatchDetailModal` so reviewing a batch of candidate matches does not kick the user back to the list on every decision, and so the list prioritises actionable (unvalidated) work over already-reviewed work.

**In scope:**
- Reject behaviour in `MatchDetailModal` (keep modal open, inline ack, auto-advance, auto-close rules)
- Backend sort of `/api/images/matches` so unvalidated groups come before validated, then by newest Instagram `created_at`
- Fallback chain for missing Instagram `created_at` + write-back of catalog capture date on validate
- Subtle bucket divider on the Matches tab between unvalidated and validated + a third tombstone state for fully-rejected groups
- UI copy via `constants/strings.ts` (project convention)

**Out of scope (handed to later phases):**
- Sort-direction toggle and "hide validated" filter on Matches tab — land as Phase 4 (filter framework) consumers of FILTER-01/02
- Undo-reject affordance / backend un-reject endpoint — not requested
- Any toast / notification infrastructure — no toast system exists today and none is being added
- Rejected-history browsing UI — rejected candidates remain hidden forever

Requirements locked by `.planning/REQUIREMENTS.md`:
- **POLISH-01** — Reject keeps modal open, shows rejected state, auto-advances to next candidate in multi-candidate groups
- **POLISH-02** — Matches list shows unvalidated groups first, then by newest photo (Instagram `created_at`) within each bucket

</domain>

<decisions>
## Implementation Decisions

### Reject acknowledgment & modal behaviour

- **D-01:** After a successful reject, do NOT call `onClose()` immediately. The modal stays open and shows a Gmail-style inline "Rejected" label in the modal header (reusing the existing `Badge` component with a neutral/danger variant). No toast, no popup, no Undo affordance.
- **D-02:** The Validate and Reject buttons gray out and become disabled after a reject fires, matching the existing pattern where Reject is disabled once a match is validated. No button swap, no Undo.
- **D-03:** For single-candidate groups, the modal auto-closes ~1.5s after the "Rejected" label appears, giving the user a beat to register the action before returning to the list.
- **D-04:** For multi-candidate groups, after a reject the modal auto-advances to the next candidate in `CandidateTabBar` order (left-to-right). Use the existing `onCandidateChange` plumbing; do not re-sort by score.
- **D-05:** When the rejected candidate was the last remaining candidate in the group (i.e. no more tabs to advance to), behave the same as the single-candidate case: show "Rejected" ~1.5s, then auto-close. The now-empty group is handled by the tombstone rule in D-10, not by removing the group from the list.
- **D-06:** Rejected candidates disappear from `CandidateTabBar` immediately (current `useMatchGroups.handleRejected` behaviour is preserved). No struck-out / disabled tab state.
- **D-07:** Auto-advance does NOT need to skip already-validated candidates — in practice a group only ever has at most one validated candidate, so the linear "next tab" rule is sufficient.

### Sort order & pagination

- **D-08:** Sort is applied on the **backend**, before pagination, in the `/api/images/matches` SQL (`apps/visualizer/backend/api/images.py:558` — `list_matches`). Client-side sort is rejected because it would bury unvalidated groups on later pages.
- **D-09:** Sort key (applied to the grouped result, not the raw `matches` rows):
  1. `has_validated ASC` — unvalidated groups (`has_validated = 0`) first, validated groups (`has_validated = 1`) after
  2. Within each bucket, by the group's resolved "photo date" — see fallback chain in D-11
  3. Direction: newest first (DESC), NULLS LAST
  Rejected-tombstone groups (D-10) sort inside the validated bucket using the same rule.

### Rejected tombstones

- **D-10:** When every candidate in a match group is rejected, the group does NOT disappear. Instead it remains in the list as a "reviewed, no match" tombstone:
  - Rendered as a group card with no candidate thumbnails on the Lightroom side, the Instagram thumbnail visible, and a "No match" badge (new variant — follow Badge primitive conventions)
  - Sorts inside the **validated bucket** using the same newest-first rule — it's "reviewed / done," not actionable
  - `useMatchGroups.handleRejected` must NOT drop the group from `matchGroups` when the last candidate is rejected; it must keep the group with a zero-length (or sentinel) candidates array and mark it in a way the UI can detect (e.g. `has_validated = false`, `candidate_count = 0`, new flag `all_rejected = true` or equivalent)
  - Backend `list_matches` must surface fully-rejected groups (today they naturally appear if there are rejected matches in the `matches` table, but validate that the grouping logic doesn't drop them and that the tombstone flag is emitted)
  - The tombstone group is NOT clickable to open the modal (no candidates left to review)

### Created_at fallback & write-back

- **D-11:** Resolving the "photo date" used for sorting follows this chain:
  1. Instagram `created_at` from the group's `instagram_image` if present
  2. Else catalog `capture_date` from the best candidate's `catalog_image` if a catalog match exists
  3. Else end-of-bucket (NULLS LAST)
- **D-12:** On `validate` (PATCH `/api/images/matches/<catalog_key>/<insta_key>/validate`), if the Instagram record's `created_at` is missing and the matched catalog image has a `capture_date`, **persist** the catalog `capture_date` into the Instagram record's `created_at` field as part of the validate operation. This is a real DB write (to the library DB, not the read-only Lightroom catalog). Future reads see a real date. Wrap in the existing transaction scope of the validate handler.

### Bucket divider UI

- **D-13:** In `MatchesTab.tsx`, render a subtle divider row between the unvalidated bucket and the validated bucket (which includes tombstones). Label: "— Validated —" (use `constants/strings.ts`, e.g. `MATCHES_VALIDATED_DIVIDER_LABEL`). If there are zero validated/tombstone groups, the divider is not rendered. If there are zero unvalidated groups, the divider is not rendered (validated section appears without a divider).

### Copy & constants

- **D-14:** Any new UI strings (inline "Rejected" label, "No match" tombstone badge, "Validated" divider label, ARIA labels) go through `apps/visualizer/frontend/src/constants/strings.ts` per existing convention.

### Claude's Discretion

- Exact spring/fade timing for the "Rejected" label reveal and the ~1.5s auto-close — pick sensible defaults (e.g. CSS transition 150–200ms, 1500ms timeout). Do not introduce a new animation library.
- Exact `Badge` variant palette choice for "Rejected" and "No match" states — pick from existing variants (`danger` / neutral gray) or add one minimal variant if genuinely needed.
- Backend implementation detail: whether "sort the grouped result post-query" or "rewrite the SQL to join & sort before grouping" — planner picks based on performance. Group count is expected to stay modest (hundreds, not millions).
- Exact test structure — backend tests for sort order + write-back, frontend tests for modal reject → label → auto-advance / auto-close, tombstone rendering. Follow existing patterns in `test_match_groups.py`, `test_match_validation.py`.

### Folded Todos

*None — no pending todos matched Phase 1 scope.*

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — POLISH-01 and POLISH-02 wording and acceptance criteria
- `.planning/ROADMAP.md` §"Phase 1: Matching & review polish" — success criteria (3 items)
- `.planning/seeds/SEED-004-keep-modal-open-after-reject.md` — original UX motivation + code breadcrumbs
- `.planning/seeds/SEED-015-matches-sort-unvalidated-first.md` — original sort motivation + risks list

### Codebase conventions
- `.planning/codebase/CONVENTIONS.md` — TS/React + Flask coding standards; note `--max-warnings 0` ESLint gate
- `.planning/codebase/STRUCTURE.md` — monorepo layout
- `.planning/codebase/TESTING.md` — test conventions (backend: pytest, frontend: vitest in `__tests__`)

### Key files touched by this phase
- `apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx` — `handleRejectConfirm` (line ~61) is the primary behaviour change
- `apps/visualizer/frontend/src/components/matching/match-detail-modal/CandidateTabBar.tsx` — already supports programmatic switching via `onSelect`, no API change expected
- `apps/visualizer/frontend/src/components/matching/match-detail-modal/RejectConfirmModal.tsx` — triggers reject; no change expected but read for flow
- `apps/visualizer/frontend/src/hooks/useMatchGroups.ts` — `handleRejected` must be updated to keep empty groups as tombstones instead of dropping them
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx` — bucket divider + tombstone card rendering
- `apps/visualizer/frontend/src/services/api.ts` — `Match`, `MatchGroup`, `InstagramImage` types; may need `all_rejected` (or similar) field on `MatchGroup`
- `apps/visualizer/frontend/src/constants/strings.ts` — new copy constants
- `apps/visualizer/backend/api/images.py` — `list_matches` (line 558) sort rewrite; `validate` handler (line 673) write-back logic
- `apps/visualizer/backend/tests/test_match_groups.py` — extend with sort-order tests
- `apps/visualizer/backend/tests/test_match_validation.py` — extend with created_at write-back test

No external ADRs or specs — requirements fully captured in decisions above and the two seed docs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`Badge` component** (`components/ui/Badge.tsx`) — existing primitive with `success` / `danger` etc. variants; reuse for "Rejected" inline label and "No match" tombstone badge. Phase 6 (UI-01) will consolidate badge primitives; this phase uses them as-is.
- **`CandidateTabBar.onSelect`** — already supports programmatic switching, no API change needed for auto-advance.
- **`useMatchGroups.handleRejected`** — existing removal logic stays for intra-group cleanup; only the "drop empty group" branch changes.
- **Inline state pattern throughout the app** — no toast system exists, and none is being added. All reject acknowledgment stays inline (Gmail-style) in the modal header.
- **Pagination helper `_clamp_pagination`** in `api/images.py` — keep using; sort happens before `[offset:offset+limit]` slice.

### Established Patterns
- **Centralised copy in `constants/strings.ts`** — all new UI strings route through here.
- **Disable-on-action button pattern** — modal already disables Reject when validated; mirror this for the post-reject "buttons gray out" behavior.
- **Container/presenter** — `MatchesTab` fetches + orchestrates; `MatchDetailModal` receives props. Keep that split.
- **Backend response shape** — `list_matches` returns `{ total, total_groups, total_matches, match_groups, matches }`. Additions (e.g. `all_rejected` flag on a group) go inside `match_groups[]`.

### Integration Points
- **Validate write-back** wires `validate` endpoint → catalog lookup → Instagram record update in the library DB (not the read-only Lightroom catalog). Respect the existing read-only invariant on `.lrcat`.
- **No new backend routes** — extend `list_matches` (`GET /api/images/matches`) and `validate` (`PATCH /api/images/matches/<cat>/<insta>/validate`).

</code_context>

<specifics>
## Specific Ideas

- **Gmail-style inline acknowledgment** — the user explicitly called out Gmail as the reference for how "Rejected" should feel: quiet, inline, in the same place you were looking. Avoid popups, banners taking vertical space, or motion-heavy card fades.
- **"Keep it dead simple"** — user rejected Undo affordance, a toast system, and struck-out rejected tabs. Default to the minimal reading of each decision.
- **Fallback chain is deliberate** — "first catalog date, then end-of-bucket" plus the write-back on validate is the user's own formulation, not a Claude suggestion. Preserve this exact semantics.

</specifics>

<deferred>
## Deferred Ideas

- **Sort-direction toggle (newest ↔ oldest) on Matches tab** — land in Phase 4 (filter framework), with Matches tab as an early consumer of FILTER-01/02.
- **"Hide validated" filter on Matches tab** — same: Phase 4 consumer of FILTER-01/02.
- **Rejected-candidate history browsing** — not requested. DB retains rejected rows; no UI surfaces them. Revisit only if a user request emerges.
- **Undo-reject / un-reject backend endpoint** — not requested. If it ever becomes needed, it's a new endpoint + new UI affordance, effectively a small standalone phase.

### Reviewed Todos (not folded)
*None — no pending todos were reviewed or deferred.*

</deferred>

---

*Phase: 01-matching-review-polish*
*Context gathered: 2026-04-17*
