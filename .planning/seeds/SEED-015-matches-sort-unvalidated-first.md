---
id: SEED-015
status: dormant
planted: 2026-04-17
planted_during: v2.0 shipped — planning next milestone
trigger_when: Next UX / review-flow polish milestone
scope: Small
---

# SEED-015: Sort matches list: unvalidated first, then by newest photo

## Why This Matters

The Matches tab serves two distinct user intents:

1. **Confirm matches** — act on pending candidates (validate or reject).
2. **See matches** — browse/scan what's already been confirmed.

Today the list doesn't prioritize either intent: validated and unvalidated groups
are interleaved, and ordering isn't anchored to photo recency. That forces the user
to hunt for actionable items and mentally re-sort to find recent work.

Better UX: put the **actionable bucket first** (unvalidated), then the
**reference/browse bucket** (validated) — and within each bucket sort **newest photo
→ oldest** so recent work is immediately visible. This matches the mental model of
"what still needs me?" followed by "what did I just do?".

## When to Surface

**Trigger:** Next UX / review-flow polish milestone.

Surface this seed during `/gsd-new-milestone` when the milestone scope matches any of:

- Matches tab / review flow improvements
- General UX polish on the visualizer frontend
- Sort / filter / triage UX changes
- Any milestone touching `MatchesTab.tsx` or `useMatchGroups`

## Scope Estimate

**Small** — a few hours.

Expected touch points:

- `MatchingAPI.list` / backend matches endpoint — accept sort params or return in
  the desired order (group-level `has_validated` asc, then photo timestamp desc).
- `useMatchGroups` hook — no ordering logic should fight the server order.
- `MatchesTab.tsx` — optional visual separator between unvalidated and validated
  buckets (nice-to-have, not required).
- Decide which timestamp drives "newest photo": Instagram `created_at` of the
  group vs. catalog capture date of the best candidate. Likely Instagram
  `created_at` since that's what the user was reviewing most recently.

Risks / open questions:

- If both buckets are paginated together, server-side sort is required (can't
  just sort the current page client-side).
- Need to confirm a stable secondary sort when `created_at` is missing/null.

## Breadcrumbs

Related code in the current codebase:

- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx` — renders the list.
- `apps/visualizer/frontend/src/hooks/useMatchGroups.ts` — fetches and maintains
  `matchGroups`; already tracks `has_validated` per group.
- `apps/visualizer/frontend/src/services/api.ts` — `MatchingAPI.list`, `MatchGroup`
  shape, `created_at` fields.
- Backend matches endpoint (find via `MatchingAPI.list` usage) — where the
  server-side ordering would be added.

Related seeds:

- SEED-004 — keep modal open after reject (same review flow).
- SEED-007 — reusable filter component (may interact if filters land first).
- SEED-010 — persist filters and tabs in memory (sort preference could ride along).

## Notes

Captured mid-conversation after v2.0 shipped. Idea is small and self-contained;
worth batching with any other Matches-tab polish rather than shipping alone.
