# Phase 5: Identity & Insights Clarity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 05-identity-insights-clarity
**Areas discussed:** Posted badge, Identity page order + intros, Card differentiation, DASH-02 split, DASH-03 filter

---

## Posted badge on BestPhotosGrid cards

| Option | Description | Selected |
|--------|-------------|----------|
| Small "Posted" overlay badge top-right | Reuse `overlayBadges` + `<Badge variant="success">` | ✓ |
| Unposted indicator instead | Show badge only on unposted tiles | |
| Both | Badge on every tile with posted/unposted state | |
| You decide | Claude picks | |

**User's choice:** Option 1 — Posted badge overlay top-right on posted tiles only.

---

## Identity page section order

| Option | Description | Selected |
|--------|-------------|----------|
| Reorder to fingerprint → best → post next | Narrative flow | ✓ |
| Keep current order | Best work up top | |
| You decide | Claude picks | |

**User's choice:** Reorder to fingerprint → best work → post next.

## Section intros

| Option | Description | Selected |
|--------|-------------|----------|
| Add brief intro text per section | 1-2 sentences per section | ✓ |
| Just cleaner headings | Minimal, no prose | |
| You decide | Claude picks | |

**User's choice:** Add 1-2 sentence intros per section.

---

## Differentiated card treatments

| Option | Description | Selected |
|--------|-------------|----------|
| Section label badges | Badge on each section header | |
| Visual accent differentiation | Border/bg treatment on Post Next cards | |
| Both | Labels + accent | |
| Just reorder + intros is enough | No further visual work | ✓ |

**User's choice:** Reorder + intros is sufficient. No additional card differentiation.

---

## DASH-02 + DASH-03: Top Photos treatment

Multiple rounds of discussion.

**Round 1 — Initial options:**

| Option | Description | Selected |
|--------|-------------|----------|
| Two separate strips with headers | Unposted (6) + Posted (4), separate | |
| Single strip with divider | Horizontal strip, separator between sections | |
| Two sections stacked vertically | Unposted larger, posted smaller below | Provisional |
| You decide | Claude picks | |

User initially chose stacked sections, then asked to see ASCII sketches.

**Round 2 — After sketches (options A/B/C/D):**

User found none of the presented options satisfying and asked for more imagination.

**Round 3 — Alternative paradigms:**

| Option | Description | Selected |
|--------|-------------|----------|
| A — Segmented control in header | Compact pill switcher inline with heading | |
| B — Split IS the filter, no filter UI | Visual hierarchy only, no control | |
| C — Filter on Identity page, not Dashboard | Split stays clean, tri-state moves to BestPhotosGrid | |
| D — "Show posted" disclosure toggle | Posted section collapsed by default | |

User suggested tabs instead.

**Round 4 — Tab strip:**

User proposed tabs. Confirmed with ASCII sketch:

```
Top Photos
[Unposted] [Posted] [All]

── "Unposted" (default) ──
[img][img][img][img][img][img][img][img]
```

**User's final choice:** Tab strip (Unposted | Posted | All), default Unposted. Covers both DASH-02 and DASH-03 in one UI element.

---

## Claude's Discretion

- Section intro copy for all three Identity sections
- Number of photos per tab (8 default)
- Tab component choice (existing `<Tabs>` or lightweight inline)
