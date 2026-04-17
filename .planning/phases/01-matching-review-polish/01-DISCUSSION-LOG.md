# Phase 1: Matching & review polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 01-matching-review-polish
**Areas discussed:** Reject UX after action fires; Auto-advance behaviour for multi-candidate groups; Unvalidated/validated sort ordering & rendering; Rejected persistence across modal sessions

---

## Reject UX after action fires

### Q1.1 — What does the user see immediately after rejecting?
(Re-asked in plain language after user feedback that questions were too technical.)

| Option | Description | Selected |
|--------|-------------|----------|
| Inline "Rejected" label in modal header (Gmail/GitHub-style) | Quiet, inline, no popup | ✓ |
| Candidate fades out before next appears / modal closes (Photos-style) | More motion, more felt feedback | |
| Banner strip across top of modal body (Gmail archive strip) | More prose, takes vertical space | |
| Other / describe freely | — | |

**User's choice:** Gmail approach, no need to Undo.
**Notes:** User rejected the Undo affordance explicitly — want simplicity.

### Q1.2 — Single-candidate groups: what happens after reject?

| Option | Description | Selected |
|--------|-------------|----------|
| Stay open until user closes | One rule with multi-candidate, no timing magic | |
| Auto-close after ~1.5s | Gives user a beat to register the action | ✓ |
| Stay open + surface "Review next group" button | Proactive but scope expansion | |

**User's choice:** 2 (auto-close ~1.5s)

### Q1.3 — Validate / Reject buttons after reject?

| Option | Description | Selected |
|--------|-------------|----------|
| Swap Reject to "Undo" link | Safety net, requires backend un-reject endpoint | |
| Buttons gray out and disable (matches validated-state pattern) | Simplest, no backend change | ✓ |
| Hide both buttons entirely | Cleanest visual but looks empty pre-close/advance | |

**User's choice:** 1 (gray out + disable)
**Notes:** User confirmed no Undo.

### Q1.4 — Rejected candidates remain in tab bar?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove from tabs (current `handleRejected` behaviour) | Low cognitive load | ✓ |
| Keep in tabs, struck out | Reviewer memory aid; adds state tracking | |

**User's choice:** Keep current behaviour.

---

## Auto-advance behaviour for multi-candidate groups

### Q2.1 — Which candidate after rejecting in a multi-candidate group?

| Option | Description | Selected |
|--------|-------------|----------|
| Next tab in tab-bar order (left-to-right) | Predictable, follows visible order | ✓ |
| Highest-scoring remaining candidate | Smart but may feel like jumping around | |
| Next non-validated, non-rejected candidate | Smartest, skips prior decisions | |

**User's choice:** 1 (next tab in order)

### Q2.2 — Last remaining candidate rejected?

| Option | Description | Selected |
|--------|-------------|----------|
| Show "Rejected" ~1.5s, then auto-close (same as single-candidate rule) | Consistent with Q1.2 | ✓ |
| Stay open showing "all candidates rejected" empty state | Explicit but adds new screen state | |
| Close immediately with no ack | Loses the "Rejected" confirmation | |

**User's choice:** 1 (consistent with single-candidate rule)

### Q2.3 — Skip validated candidates during auto-advance?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, skip validated during auto-advance | Validated = decided, don't revisit | |
| No, advance to them anyway | See validated state, switch tabs manually after | |
| Not applicable — only one candidate ever validated per group in practice | Hypothetical question | ✓ |

**User's choice:** 3 (not applicable in practice)

---

## Unvalidated/validated sort ordering & rendering

### Q3.1 — Where should sort happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Backend sorts first, then paginates | Only correct option with pagination | ✓ |
| Frontend sorts within current page | Broken: buried items stay buried | |

**User's choice:** 1 (backend sort)

### Q3.2 — Visual treatment between buckets?

| Option | Description | Selected |
|--------|-------------|----------|
| Subtle divider row "— Validated —" between buckets (GitHub "Done" style) | Explicit, unambiguous | ✓ |
| No divider; rely on sort + badge | Clean, trust the user | |
| Collapsible "Validated (N)" section | Hides clutter, adds a click | |

**User's choice:** 1 (subtle divider)

### Q3.3 — Fallback for missing Instagram `created_at`?

| Option | Description | Selected |
|--------|-------------|----------|
| End-of-bucket (NULLS LAST) | Simple rule | |
| Fall back to catalog `capture_date` | More effort, more accurate | Partial (tier 1) |
| Fall back to `insta_key` alphabetical | Stable but arbitrary | |

**User's final choice (after clarifying follow-ups):** 3-step chain — Instagram `created_at` → catalog `capture_date` if match exists → end-of-bucket.

### Q3.3b — Write catalog date back into Instagram record on validate?

| Option | Description | Selected |
|--------|-------------|----------|
| Write-back on validate (persist catalog `capture_date` into Instagram `created_at`) | Real DB change; helps every future read | ✓ |
| Read-time only (no persistence) | Simpler, lower risk, same visible result | |

**User's choice:** 1 (write-back on validate)

### Q3.4 — Sort direction and/or filter controls on Matches tab?

(Asked after user originally answered "1 and 2" which were mutually exclusive.)

| Option | Description | Selected |
|--------|-------------|----------|
| Just sort-direction toggle | Newest↔oldest arrow/dropdown | |
| Just filter ("hide validated") | Focus on actionable bucket | |
| Both toggle AND filter | More UI, more power | ✓ |
| Only filter, sort fixed newest-first | Hide-validated is the real need | |

**User's choice:** 3 (both). **Then scope-checked:** user agreed to **defer both to Phase 4 (filter framework)**, with Matches tab as an early consumer of FILTER-01/02. Phase 1 ships newest-first hardcoded with no controls.

---

## Rejected persistence across modal sessions

### Q4.1 — Rejected-candidate visibility across sessions?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current: once rejected, never shown again | Clean, matches Q1.4 | |
| Add "show rejected" toggle on Matches tab | New UI surface, scope creep | |
| Rejected candidates don't come back, but fully-rejected *groups* stay visible as "no match" tombstone | Preserves reviewed-history signal at group level | ✓ |

**User's choice:** 3 (tombstone for fully-rejected groups)

### Q4.1a — Tombstone placement?

| Option | Description | Selected |
|--------|-------------|----------|
| In the validated bucket (reviewed/done, newest-first) | Keeps unvalidated bucket purely actionable | ✓ |
| Own third bucket below validated, new divider | More structure, more UI | |
| Mixed into validated with a different badge | Less structure, relies on badge | |

**User's choice:** 1 (in validated bucket)

---

## Claude's Discretion

- Exact timing for inline "Rejected" label reveal and the ~1.5s auto-close (pick sensible defaults; no new animation library)
- Exact `Badge` variant palette for "Rejected" and "No match" states (pick from existing or add one minimal variant)
- Backend implementation style for sort — post-query sort-then-paginate vs. SQL join+sort (planner's call based on group count)
- Exact test structure (extend existing test files following existing patterns)

## Deferred Ideas

- Sort-direction toggle (newest ↔ oldest) on Matches tab → Phase 4 consumer of FILTER-01/02
- "Hide validated" filter on Matches tab → Phase 4 consumer of FILTER-01/02
- Rejected-candidate history browsing UI — not requested; revisit only if asked
- Undo-reject / un-reject backend endpoint — not requested
