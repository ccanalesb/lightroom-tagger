---
plan: 04
title: MatchDetailModal reject flow — keep open, inline ack, advance, auto-close
wave: 2
depends_on:
  - "03"
files_modified:
  - apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx
autonomous: true
requirements:
  - POLISH-01
---

<objective>
Replace the post-reject `onClose()` in `handleRejectConfirm` (today lines 61–70) with the locked Gmail-style flow: stay in-modal, show a header `Badge`, disable Validate/Reject after success, auto-advance to the next `CandidateTabBar` candidate when one exists, and auto-close after ~1.5s when there is no next candidate or the group was single-candidate.
</objective>

<context>
Implements **D-01** (no immediate `onClose`, inline `Badge` acknowledgment), **D-02** (gray out / disable Validate + Reject after reject succeeds), **D-03** (~1.5s delayed auto-close for single-candidate), **D-04** (advance using existing `onCandidateChange` / tab order, no score re-sort), **D-05** (last candidate → same delayed close as single), **D-06** (rejected row disappears from tab bar via parent `handleRejected` — no struck-out tabs), **D-07** (linear next-tab rule; no skip-validated special case).
</context>

<tasks>
<task id="4.1">
<action>In `apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx`: (1) Import `Badge` from `../../ui/Badge` and `MATCH_DETAIL_REJECTED_LABEL` from `../../../constants/strings` (plus `MODAL_CLOSE` already present). (2) Add `useRef`/`useState`/`useEffect` as needed: state `rejectedAck: boolean` default `false`; optional `autoCloseTimerRef` / `rejectAdvanceTimerRef` to clear timers on unmount. (3) Define a **named constant** (e.g. `MULTI_CANDIDATE_REJECT_ADVANCE_MS = 800` in module scope or next to the existing `1500` auto-close constant) for the delay before advancing after a multi-candidate reject — shorter than the single-candidate `1500` auto-close because the modal stays open and advances rather than closes. (4) Rewrite `async function handleRejectConfirm` at lines 61–70: after `await MatchingAPI.reject(...)`, compute `nextCandidate` from **pre-reject** `resolvedGroup.candidates` order (same order as `CandidateTabBar` maps at lines 15–37 of `CandidateTabBar.tsx`) as the candidate after the rejected `match.catalog_key` / `match.instagram_key` pair; call `onRejected?.(match)` so parent state removes the rejected row; **remove** the immediate `onClose()` on line 66. **Multi-candidate branch** ( `nextCandidate` exists and `onCandidateChange` is defined): set `rejectedAck` **true** immediately so the Gmail-style inline `Badge` renders and **D-02** applies — both Validate and Reject use `disabled={busy || validated || rejectedAck}` (same as single-candidate ack). Do **not** call `onCandidateChange` in the same tick. Schedule `window.setTimeout(() => { onCandidateChange(nextCandidate); }, MULTI_CANDIDATE_REJECT_ADVANCE_MS)` (**D-04**, **POLISH-01** timing discretion). **Single-candidate / last-candidate branch** (no `nextCandidate`): set `rejectedAck` true and `window.setTimeout(() => { onClose(); }, 1500)` (**D-03**, **D-05**). (5) In the header row (~86–121), when `rejectedAck` is true, render `Badge` with `variant="error"` and children `{MATCH_DETAIL_REJECTED_LABEL}` adjacent to the title area per **D-01** — this path MUST run for multi-candidate rejects too, not only the terminal auto-close case. (6) On candidate change (`useEffect` keyed by the active match identity, e.g. `catalog_key` + `instagram_key` or stable match id): reset `rejectedAck` to `false` for the newly selected candidate so each tab gets a fresh ack state; if the newly shown candidate is already validated or already rejected per its own flags, keep buttons in the correct state from those flags alone (do not force `rejectedAck` true).</action>
<read_first>
- apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx
- apps/visualizer/frontend/src/components/matching/match-detail-modal/CandidateTabBar.tsx
- apps/visualizer/frontend/src/components/ui/Badge/Badge.tsx (variants: `default` | `success` | `warning` | `error` | `accent`)
- apps/visualizer/frontend/src/constants/strings.ts (`MATCH_DETAIL_REJECTED_LABEL` from plan 03)
- apps/visualizer/frontend/DESIGN.md (semantic classes for any new header layout)
</read_first>
<acceptance_criteria>
- `rg -n "handleRejectConfirm" apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx` shows function body where `onClose()` is **not** invoked immediately after `MatchingAPI.reject` (grep `onClose` inside `handleRejectConfirm` returns 0 matches, or only inside timeout callback)
- `rg -n "MATCH_DETAIL_REJECTED_LABEL|Badge" apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx` returns at least two lines, and the same `rejectedAck` (or equivalent) condition that gates the `Badge` is not wrapped in a `!nextCandidate` / "only single candidate" guard — the Rejected `Badge` must be renderable on the multi-candidate reject path before auto-advance
- `rg -n "MULTI_CANDIDATE_REJECT_ADVANCE_MS|REJECT_ADVANCE_MS" apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx` returns a named constant used as the `setTimeout` delay for `onCandidateChange(next)` (not a bare `800` inline)
- `rg -n "1500" apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx` returns the auto-close timeout line
- `rg -n "rejectedAck" apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx` shows disabled logic on Validate and Reject buttons
- Vitest in task **4.2** test file covers multi-candidate reject: after confirm, Rejected `Badge` is present, both action buttons are disabled, fake timers advance by `MULTI_CANDIDATE_REJECT_ADVANCE_MS` (or the chosen constant name), then `onCandidateChange` is called with the next candidate (and not before)
</acceptance_criteria>
</task>

<task id="4.2">
<action>Add `apps/visualizer/frontend/src/components/matching/match-detail-modal/__tests__/MatchDetailModal.reject.test.tsx` (or colocated `__tests__` per TESTING.md): render `MatchDetailModal` with mocked `MatchingAPI.reject` resolving, two synthetic `Match` candidates in `group.candidates`, spy on `onCandidateChange` and `onClose`. **Multi-candidate:** after confirm handler fires, assert Rejected `Badge` / `MATCH_DETAIL_REJECTED_LABEL` is present, both Validate and Reject buttons are disabled, `onCandidateChange` is **not** called on the same tick, then advance fake timers by `MULTI_CANDIDATE_REJECT_ADVANCE_MS` (import or read the same constant the component uses) and assert `onCandidateChange` was called with the second candidate; `onClose` must not run until any terminal single-candidate timer path. **Single-candidate fixture:** confirm `onClose` called after fake timers advance 1500ms. Use Vitest `vi.useFakeTimers()` + `userEvent` from Testing Library per existing frontend test patterns.</action>
<read_first>
- apps/visualizer/frontend/vite.config.ts (test environment)
- apps/visualizer/frontend/src/test/setup.ts
- apps/visualizer/frontend/src/pages/__tests__/MatchingPage.test.tsx or similar for `MatchingAPI` mock pattern
- apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx
- apps/visualizer/frontend/src/components/matching/match-detail-modal/__tests__/MatchDetailModal.test.tsx (colocated suite entrypoint if present; create only if splitting from `reject` tests)
- apps/visualizer/frontend/src/components/matching/match-detail-modal/__tests__/MatchDetailModal.reject.test.tsx (primary new file for task 4.2)
- .planning/codebase/TESTING.md
</read_first>
<acceptance_criteria>
- `cd apps/visualizer/frontend && npm test -- --run src/components/matching/match-detail-modal/__tests__/MatchDetailModal.reject.test.tsx` exits 0
- Test file path exists on disk (`test -f` or glob lists the file)
</acceptance_criteria>
</task>
</tasks>

<verification>
- `cd apps/visualizer/frontend && npm run lint` exits 0
- `cd apps/visualizer/frontend && npm test -- --run src/components/matching/match-detail-modal/__tests__/MatchDetailModal.reject.test.tsx` exits 0
</verification>

<must_haves>
- Rejecting a match no longer kicks the user straight back to the list without acknowledgment (roadmap Phase 1 success criterion 1).
- Multi-candidate groups advance to the next tab after reject when a next candidate exists (roadmap Phase 1 success criterion 2).
- Validate and Reject are both disabled after a successful reject until the modal advances or begins its close timer.
</must_haves>
