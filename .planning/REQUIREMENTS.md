# Requirements — Milestone v2.1 Polish & Consolidate

**Goal:** Tighten v2.0's shipped surface — remove UX friction, fix inconsistencies, consolidate redundant workflows, and lay reusable filter foundations — before net-new capability in v3.0.

**Started:** 2026-04-17
**Status:** Defining requirements
**Seeds incorporated:** SEED-001, SEED-002, SEED-003, SEED-004, SEED-007, SEED-008, SEED-009, SEED-013, SEED-015

---

## v2.1 Requirements

### Matching & review flow polish

- [x] **POLISH-01**: User can reject a match without losing context — modal stays open, shows rejected state, auto-advances to the next candidate when the match group has multiple candidates _(SEED-004)_ — completed 2026-04-17 (Phase 1)
- [x] **POLISH-02**: User sees matches sorted with unvalidated groups first, then by newest photo (Instagram `created_at`) within each bucket _(SEED-015)_ — completed 2026-04-17 (Phase 1)

### Job queue & processing UX

- [ ] **JOB-03**: User sees a loading state when opening the Job Detail Modal so heavy jobs no longer appear frozen while data is fetching _(SEED-002)_
- [ ] **JOB-04**: User can browse long job logs without frontend slowdown — logs truncate to the most recent N entries with a "show more" expansion for full history _(SEED-002)_
- [ ] **JOB-05**: User can paginate the Job Queue with classic numbered pagination; current page stays pinned across polling refreshes _(SEED-013)_
- [ ] **JOB-06**: User can launch a single unified "Analyze" job that runs description + scoring together, with an advanced toggle to run them separately _(SEED-001)_

### Reusable filter framework

- [ ] **FILTER-01**: Developer can declare a filter schema (toggle, select, date-range, search) and get a fully-working `<FilterBar>` with consistent visual treatment (active chips, clear-all, active count) _(SEED-007)_
- [ ] **FILTER-02**: Developer gets centralized filter state via a `useFilters(schema)` hook returning values, setters, clear-all, active count, and query-param mapping — with debouncing handled internally _(SEED-007)_

### Identity page clarity

- [ ] **IDENT-04**: User sees posted vs unposted status visually on every BestPhotosGrid card _(SEED-003)_
- [ ] **IDENT-05**: Identity page presents a clear narrative flow from style fingerprint → best work → what to post next, with section intros and differentiated card treatments for Best Photos vs Post Next Suggestions _(SEED-003)_

### Insights dashboard

- [ ] **DASH-02**: User sees Insights "Top Scored Photos" split into two labeled sections — Top unposted (primary, prominent) and Top already posted (secondary) _(SEED-009 Piece A)_
- [ ] **DASH-03**: User can filter the Top Photos strip by posted status (tri-state: posted / unposted / all) using the shared filter framework _(SEED-009 Piece B; depends on FILTER-01, FILTER-02)_

### Images page visual consistency

- [ ] **UI-01**: Badge primitives (Badge, VisionBadge, StatusBadge, ImageTypeBadge, PerspectiveBadge) are consolidated under a consistent API and documented usage guidelines _(SEED-008)_
- [ ] **UI-02**: Images page badges adopt an inline-in-description pattern where appropriate, matching Catalog's scannable style _(SEED-008)_
- [ ] **UI-03**: Matches on the Images page render as cards consistent with Catalog's card affordance _(SEED-008)_

---

## Future Requirements

These requirements were considered but deferred to a later milestone.

- SEED-007 full rollout — migrate InstagramTab, MatchesTab, DescriptionsTab, MatchingTab, AnalyticsPage `AppliedFilters` to the filter framework (beyond CatalogTab which lands as part of FILTER-01/02 validation)
- URL syncing of filter state — rolls in naturally with SEED-010 (persist tab/filter state)
- SEED-014 — Unified vision match + describe in a single batch call → v3.0 alongside stacking work
- SEED-010 — Persist tab and filter state in-memory across navigation
- SEED-011 — Adopt CVA (class-variance-authority) for Tailwind variant composition
- SEED-012 — Skeleton loading + reusable image-grid primitive
- SEED-016 — Rotate catalog images in match card and catalog views
- SEED-017 — Break up oversized backend files (DRY + KISS pass)

## Out of Scope (v2.1)

- Net-new capabilities (natural language search SEED-005, photo stacking SEED-006) — explicitly v3.0 territory
- Multi-catalog context switching — long-deferred, still not the bottleneck
- Instagram engagement data (likes/saves) — requires API or manual entry
- Dashboard drill-down interactions — deferred per PROJECT.md
- URL-synced filter state — possible but rides with SEED-010 later
- Backend file-size refactor — tracked as SEED-017, pure tech debt, not user-facing

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| POLISH-01 | Phase 1 | Complete |
| POLISH-02 | Phase 1 | Complete |
| JOB-03 | Phase 2 | Pending |
| JOB-04 | Phase 2 | Pending |
| JOB-05 | Phase 2 | Pending |
| JOB-06 | Phase 3 | Pending |
| FILTER-01 | Phase 4 | Pending |
| FILTER-02 | Phase 4 | Pending |
| IDENT-04 | Phase 5 | Pending |
| IDENT-05 | Phase 5 | Pending |
| DASH-02 | Phase 5 | Pending |
| DASH-03 | Phase 5 | Pending |
| UI-01 | Phase 6 | Pending |
| UI-02 | Phase 6 | Pending |
| UI-03 | Phase 6 | Pending |

**Total:** 15 requirements across 6 phases.

---

## Dependencies

- **DASH-03** depends on **FILTER-01** and **FILTER-02** — the posted tri-state filter consumed by the Top Photos strip must come from the shared framework, not a bespoke implementation.
- **UI-02, UI-03** implicitly benefit from a stable badge primitive (**UI-01**) landing first.

## Implementation Guidance (non-requirement)

- FILTER-01/02 are validated by migrating **CatalogTab** as the first real consumer (most complex filter set in the app — 11+ filter pieces). This is an acceptance condition on the FILTER phase, not a separate requirement.
- Migration of remaining tabs (Instagram, Matches, Descriptions, Matching, Analytics) is explicitly **out of scope** for v2.1 to keep the milestone focused on polish, not a full design-system rollout.

---

*Requirements defined: 2026-04-17*
