---
id: SEED-004
status: dormant
planted: 2026-04-15
planted_during: v2.0 (milestone complete)
trigger_when: next UX improvements milestone or matching workflow polish
scope: Small
---

# SEED-004: Keep match detail modal open after rejecting a match

## Why This Matters

When you reject a match in the `MatchDetailModal`, the modal immediately closes (`onClose()` is called in `handleRejectConfirm`). This is jarring — the user was reviewing a match, decided it's wrong, and now they're kicked back to the list. If the match group has multiple candidates, the user likely wants to stay in the modal and review the next candidate. Even for single-candidate groups, closing feels abrupt; an inline confirmation ("Match rejected") would be smoother than losing your context.

## When to Surface

**Trigger:** Next UX improvements milestone or matching workflow polish

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:
- UX polish or interaction improvements to the matching workflow
- Match detail modal redesign
- General modal behavior consistency pass

## Scope Estimate

**Small** — A few hours. The fix is removing the `onClose()` call from `handleRejectConfirm` and instead showing an inline success state or toast. If the match group has other candidates, auto-advancing to the next one would be ideal but is a minor extension.

## Breadcrumbs

Related code and decisions found in the current codebase:

- `apps/visualizer/frontend/src/components/matching/match-detail-modal/MatchDetailModal.tsx` — `handleRejectConfirm` calls `onClose()` at line 66 after the API call succeeds
- `apps/visualizer/frontend/src/components/matching/match-detail-modal/RejectConfirmModal.tsx` — the confirmation sub-modal before reject
- `apps/visualizer/frontend/src/components/matching/match-detail-modal/CandidateTabBar.tsx` — tab bar for multi-candidate groups; could auto-advance to next candidate after reject
- `apps/visualizer/frontend/src/services/api.ts` — `MatchingAPI.reject()` at line 253

## Notes

The simplest fix: remove `onClose()` from `handleRejectConfirm`, show an inline "Rejected" badge or brief toast, and let the user close the modal themselves. For multi-candidate groups, auto-switching to the next candidate after reject would be a nice touch — the `CandidateTabBar` and `onCandidateChange` callback already support this.
