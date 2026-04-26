# Phase 7: Stacks in matching & pin similarity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `07-CONTEXT.md` - this log preserves alternatives considered.

**Date:** 2026-04-26
**Phase:** 07-stacks-in-matching-pin-similarity
**Areas discussed:** Representative-only matching behavior, Stack edit operations UX, Pin-to-similar in chat, Edge cases and verification

---

## Representative-only matching behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-apply to full stack immediately | Apply representative match to all members right away | ✓ |
| Representative-only first | Match rep only; user applies to stack manually | |
| Prompt each time | Ask per match whether to apply to full stack | |

**User's choice:** Auto-apply to full stack immediately.
**Notes:** User requested concrete examples to understand conflict behavior, then selected a safe default conflict policy.

### Conflict handling follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| Skip conflicts, apply remainder, report counts | Keep existing conflicting matches; apply non-conflicting members | ✓ |
| Overwrite conflicts | Force replace conflicting member matches | |
| Fail all | Abort if any member conflicts | |

**User's choice:** Skip conflicted members, apply to the rest, and report counts.
**Notes:** User requested a second simplified explanation and selected the non-destructive path.

---

## Stack edit operations UX

| Option | Description | Selected |
|--------|-------------|----------|
| Images stack-expanded view | Inline stack controls in existing Images stack UI | ✓ |
| Dedicated stack manager page | New page for stack administration | |
| Image detail modal only | Stack edits only inside modal view | |

**User's choice:** Images stack-expanded view.
**Notes:** Keep operations close to where users inspect stacks.

### Safety flow follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm modal + undo toast | Two-step safety with recovery window | ✓ |
| Confirm modal only | Confirmation but no undo | |
| No confirmation | Immediate execution | |

**User's choice:** Confirm modal plus undo toast.
**Notes:** User requested DRY behavior and asked to reuse the same interaction model as reject-match flows.

### DRY follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| Shared generic confirm+undo component | One reusable flow for reject-match and stack edits | ✓ |
| Keep reject flow separate | Separate stack-only implementation | |

**User's choice:** Shared generic confirm+undo component.
**Notes:** Explicitly requested "always DRY."

---

## Pin-to-similar in chat

| Option | Description | Selected |
|--------|-------------|----------|
| Single active pin | One pinned image at a time; new pin replaces old | ✓ |
| Multiple pins | Combine multiple pinned anchors | |
| One-shot similar only | No persistent pin state | |

**User's choice:** Single active pin.
**Notes:** User requested ASCII examples before selecting.

### Pin + text combination follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| Intersection-first | Similar-to-pin candidates first, then text refinement/ranking | ✓ |
| Union | Broadly combine pin and text result sets | |
| Pin-only mode | Ignore text while pin is active | |

**User's choice:** Intersection-first behavior.
**Notes:** User asked for a plain-language explanation of "pin" before final selection.

---

## Edge cases and verification

| Option | Description | Selected |
|--------|-------------|----------|
| Non-blocking fallback | Warn and continue with text search; keep inactive pin visible | ✓ |
| Hard error | Block turn until user unpins | |
| Silent fallback | Fallback without warning | |

**User's choice:** Non-blocking fallback.
**Notes:** Preference for resilient behavior with explicit UX feedback.

### Verification follow-up

| Option | Description | Selected |
|--------|-------------|----------|
| Integration + targeted unit tests | End-to-end checks for core flow plus policy edge unit coverage | ✓ |
| Unit tests only | Narrower, faster checks | |
| Manual QA only | No automated enforcement | |

**User's choice:** Integration checks plus targeted unit tests.
**Notes:** Selected strongest confidence option.

---

## Claude's Discretion

- Exact UI copy and final component naming for shared confirm+undo flow.
- Exact metadata field names for conflict/fallback reporting.

## Deferred Ideas

None.
