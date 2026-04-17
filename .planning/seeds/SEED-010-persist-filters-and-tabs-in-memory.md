---
id: SEED-010
status: dormant
planted: 2026-04-17
planted_during: v2.0 (milestone complete)
trigger_when: Next UX improvements milestone, or any navigation/routing/filters work
scope: Medium
related: SEED-007
---

# SEED-010: Persist active tab and filter state in-memory across navigation

## Why This Matters

Right now, every time the user navigates away from a page (e.g., Images → Analytics
→ back to Images), both the **active tab** and **all filter state** are reset to
defaults. This creates real friction in common workflows:

- User filters the Catalog tab down to "posted = false, rating ≥ 4, month = March",
  clicks into a photo, opens the Analytics page to cross-reference, comes back to
  Images — filters are gone, back on the Instagram tab, starts over.
- Multi-tab exploration on the Images page (Catalog → Matches → Instagram → back to
  Catalog) resets every filter on every switch if the user leaves the page in
  between.

The data is already in React state — it just doesn't survive unmount when the route
changes. A lightweight in-memory store (React context, Zustand, or equivalent) that
outlives individual page components would fix this with minimal infrastructure.

**Scope of persistence (explicitly chosen):**

- **In-memory only.** State persists across navigation within a single session.
- **Does NOT persist across page reloads, tab closes, or fresh browser windows.**
  This is an intentional simplicity tradeoff — no URL noise, no localStorage/storage
  decisions, no migration concerns. If reload-survival becomes desired later, it can
  be layered on (localStorage, URL sync via SEED-007, etc.) without changing the
  in-memory API.

## When to Surface

**Trigger:** Next UX improvements milestone, or any navigation/routing/filter work

This seed should be presented during `/gsd-new-milestone` when the milestone
scope matches any of these conditions:

- UX improvements / friction-reduction milestone
- Navigation or routing refactor
- Filter framework work (SEED-007) — these are complementary, see "Relationship to
  SEED-007" below
- Complaints about "my filters keep resetting" or "I keep ending up on the wrong
  tab" from user feedback

## Scope Estimate

**Medium** — a phase or two.

1. **Decide the persistence mechanism.** Options: React context provider near the
   router root, Zustand store, or a purpose-built hook. Must outlive individual
   route components. Prefer the smallest thing that works (context likely enough).
2. **Persist active-tab state.**
   - Images page: `activeTab` (catalog / instagram / matches)
   - Processing page: active sub-tab if applicable
   - Any other tabbed surface (audit and enumerate during planning)
3. **Persist filter state per page.**
   - Images → Catalog tab: the 11+ filter pieces currently in `CatalogTab.tsx`
   - Images → Instagram tab: month filter
   - Images → Matches tab: (currently none, but reserve)
   - Analytics page: `AppliedFilters` (from/to/granularity) in `AnalyticsPage.tsx`
   - Processing tabs: relevant filter state
4. **Scope state correctly.** A clear answer to "when does state reset?" — probably:
   - Never on navigation (the whole point)
   - Reset on explicit user "Clear all" action
   - Reset on hard reload (since it's in-memory)
   - Consider: should switching accounts / catalogs reset? (Likely yes.)
5. **No breaking changes to components.** Components should still accept
   `value`/`onChange` props and work standalone (for tests, storybook, etc.); the
   persistence layer sits above them.

### Explicit non-goals

- **No URL sync.** That's SEED-007's territory if it's pursued (and was explicitly
  deferred here to keep scope focused).
- **No localStorage.** Filters do **not** survive page reloads. User chose in-memory
  only.
- **No saved-filter presets.** Out of scope; possible follow-up.

## Breadcrumbs

### Where state currently lives (and dies on navigation)

- `apps/visualizer/frontend/src/pages/ImagesPage.tsx` — `useState` for
  `catalogPostedFilter` and other tab state (line 29+); all reset on unmount
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` — 11+ useState
  filter hooks, all scoped to the component and lost on navigation away from
  Images
- `apps/visualizer/frontend/src/components/images/InstagramTab.tsx` — month filter
  state, same issue
- `apps/visualizer/frontend/src/pages/AnalyticsPage.tsx` — `AppliedFilters` state
  (from/to/granularity, line 45+); same issue
- Active-tab state on Images page: driven by local state / URL hash; audit during
  planning to confirm the current mechanism

### Infrastructure that could host persistent state

- `apps/visualizer/frontend/src/stores/matchOptionsContext.tsx` — existing pattern
  of a React context provider at the app level holding cross-page state; the new
  persistence layer can follow the same pattern
- `apps/visualizer/frontend/src/App.tsx` — where a top-level provider would be
  mounted

### Related seeds

- **SEED-007 (reusable filter component)** — *complementary, not a dependency*. If
  SEED-007 ships first, this seed becomes trivial: persist the single
  `useFilters(schema)` value per page instead of dozens of individual useStates. If
  this ships first, SEED-007 consumes the persistence layer when it lands. Either
  order works; they meet in the middle.
- SEED-003 (rethink Identity page) — Identity page filters would also benefit
- SEED-009 (posted vs unposted on Insights) — any filter added there should also be
  persisted

## Notes

User feedback (2026-04-17):

> "I want the filters to persist after navigation. Now every time I navigate away,
> neither the tabs nor the filter state are saved."

Decision log from the planting conversation:

- **Mechanism:** in-memory / route state (not URL, not localStorage). User
  explicitly chose simplicity over reload-survival.
- **Relationship to SEED-007:** the user specifically chose **not to merge** this
  into SEED-007. Rationale: tab persistence is a routing concern separate from the
  filter framework, and the user wants this on the roadmap even if SEED-007 slips.
  The two should cooperate when both ship, but neither blocks the other.
- **Scope:** Medium — needs to cover all tabbed surfaces and all filter-bearing
  pages, plus a clear story for when state should reset.

Possible future layer (out of scope here): once in-memory persistence is in place,
adding an opt-in `persist: true` flag that mirrors specific pieces of state to
localStorage is a cheap upgrade. Mentioned here only so future maintainers don't
re-architect from scratch to add it.
