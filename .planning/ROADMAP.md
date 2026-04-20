# Roadmap: Lightroom Tagger & Analyzer

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-04-11) · [archive](./milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Advanced Critique & Insights** — Phases 5–11 (shipped 2026-04-15) · [archive](./milestones/v2.0-ROADMAP.md)
- 🚧 **v2.1 Polish & Consolidate** — Phases 1–6 (in progress, started 2026-04-17) · phase numbering reset

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-04-11</summary>

- [x] Phase 1: Catalog management (CAT-01..05) — completed 2026-04-10
- [x] Phase 2: Jobs & system reliability (SYS-01..05) — completed 2026-04-10
- [x] Phase 3: Instagram sync (IG-01..06) — completed 2026-04-10
- [x] Phase 4: AI analysis (AI-01..06) — completed 2026-04-11

</details>

<details>
<summary>✅ v2.0 Advanced Critique & Insights (Phases 5–11) — SHIPPED 2026-04-15</summary>

- [x] Phase 5: Structured scoring foundation (6 plans) — SCORE-02, SCORE-05, SCORE-06, SCORE-07, JOB-01, JOB-02
- [x] Phase 6: Scoring pipeline & catalog score UX (4 plans) — SCORE-01, SCORE-03, SCORE-04
- [x] Phase 7: Posting analytics (4 plans) — POST-01, POST-02, POST-03, POST-04
- [x] Phase 8: Identity & suggestions (3 plans) — IDENT-01, IDENT-02, IDENT-03
- [x] Phase 9: Insights dashboard (3 plans) — DASH-01
- [x] Phase 10: Batch scoring fix & integration bugs (2 plans) — gap closure
- [x] Phase 11: Verification & documentation update (2 plans) — gap closure

</details>

### 🚧 v2.1 Polish & Consolidate (Phases 1–6) — IN PROGRESS

Phase numbering was reset for v2.1. The phases below are v2.1 Phase 1–6, not a continuation of v2.0.

- [x] Phase 1: Matching & review polish — POLISH-01, POLISH-02 — completed 2026-04-17
- [x] Phase 2: Job queue & processing UX — JOB-03, JOB-04, JOB-05 — completed 2026-04-17
- [x] Phase 3: Unified Analyze job — JOB-06 — completed 2026-04-17
- [x] Phase 4: Reusable filter framework — FILTER-01, FILTER-02 — completed 2026-04-17
- [x] Phase 4.1 (INSERTED 2026-04-17): InstagramTab filter migration — FILTER-02 — completed 2026-04-17
- [ ] Phase 5: Identity & Insights clarity — IDENT-04, IDENT-05, DASH-02, DASH-03 _(depends on Phase 4)_
- [ ] Phase 6: Images page visual consistency — UI-01, UI-02, UI-03
- [ ] Phase 7: React Suspense data layer (no deps) — DATA-01 _(cross-cutting; no roadmap deps)_

## Progress (v2.1)

| Phase | Goal | Requirements | Success criteria | Status |
|-------|------|--------------|------------------|--------|
| 1. Matching & review polish | Smooth the match-review flow | POLISH-01, POLISH-02 | 3 | ✅ Complete (2026-04-17) |
| 2. Job queue & processing UX | Make heavy jobs and long queues feel fast | JOB-03, JOB-04, JOB-05 | 4 | ✅ Complete (2026-04-17) |
| 3. Unified Analyze job | One default flow for full AI analysis | JOB-06 | 3 | ✅ Complete (2026-04-17) |
| 4. Reusable filter framework | Declarative filter foundation (proved by CatalogTab) | FILTER-01, FILTER-02 | 4 | ✅ Complete (2026-04-17) |
| 4.1. InstagramTab filter migration | Migrate InstagramTab onto the Phase 4 framework (INSERTED) | FILTER-02 | 3 | ✅ Complete (2026-04-17) |
| 5. Identity & Insights clarity | Posted/unposted visibility + narrative flow | IDENT-04, IDENT-05, DASH-02, DASH-03 | 4 | Pending |
| 6. Images page visual consistency | Unify badge + card language on Images page | UI-01, UI-02, UI-03 | 3 | Pending |
| 7. React Suspense data layer | Replace useEffect+setState fetches with React-only Suspense/ErrorBoundary + module cache, no deps | DATA-01 | 8 | Pending |

## Phase Details (v2.1)

### Phase 1: Matching & review polish

**Goal:** Eliminate friction in the match confirmation flow so reviewing a batch no longer kicks the user back to the list on every decision.

**Requirements:** POLISH-01, POLISH-02

**Success criteria:**
1. Rejecting a match keeps the modal open and surfaces a "Rejected" state
2. Multi-candidate groups auto-advance to the next candidate after reject
3. Matches list shows all unvalidated groups above validated ones, sorted by newest photo (Instagram `created_at`)

### Phase 2: Job queue & processing UX

**Goal:** Make the Processing page feel fast even with hundreds of historical jobs and heavy log payloads.

**Requirements:** JOB-03, JOB-04, JOB-05

**Success criteria:**
1. Opening a heavy Job Detail Modal shows a loading skeleton before data arrives
2. Jobs with 100+ log entries render without noticeable DOM slowdown (truncated + expandable)
3. Job Queue paginates via existing `<Pagination>` with current page pinned across polls
4. Backend jobs list endpoint supports `limit`/`offset` with total count

### Phase 3: Unified Analyze job

**Goal:** Replace the two-flow "describe then score" UX with a single default "Analyze" job, preserving separate flows as advanced options.

**Requirements:** JOB-06

**Success criteria:**
1. `batch_analyze` job type runs describe → score in sequence with shared selection criteria
2. Default UI path launches Analyze; advanced toggle exposes separate describe/score
3. Existing `batch_describe` and `batch_score` tests continue to pass

### Phase 4: Reusable filter framework

**Goal:** Replace ad-hoc `useState`-driven filters with a declarative schema + hook, proven by migrating CatalogTab as the first real consumer.

**Requirements:** FILTER-01, FILTER-02

**Success criteria:**
1. `<FilterBar>` renders toggle / select / date-range / search primitives from a declarative schema
2. `useFilters(schema)` provides values, setters, clear-all, active count, and query-param mapping with debouncing handled internally
3. Active filters display as removable chips with a consistent "Clear all" affordance
4. CatalogTab migrated end-to-end to the framework with no functional regression (stress test for the primitive set)

### Phase 5: Identity & Insights clarity

**Goal:** Surface posted vs unposted everywhere it matters and give the Identity page a clear narrative from style → best work → post next.

**Requirements:** IDENT-04, IDENT-05, DASH-02, DASH-03

**Depends on:** Phase 4 (DASH-03 consumes the FILTER framework)

**Success criteria:**
1. BestPhotosGrid cards show posted vs unposted status visually at a glance
2. Identity page presents a narrative flow from fingerprint → best work → post next, with differentiated card treatments for Best Photos vs Post Next Suggestions
3. Insights Top Scored Photos splits into two labeled sections — Top unposted (primary, prominent) and Top already posted (secondary)
4. Top Photos strip exposes a tri-state posted filter built on the shared filter framework from Phase 4

### Phase 6: Images page visual consistency

**Goal:** Unify the visual language on the Images page so badges, matches, and descriptions feel designed, not stitched together.

**Requirements:** UI-01, UI-02, UI-03

**Success criteria:**
1. Badge primitives (Badge, VisionBadge, StatusBadge, ImageTypeBadge, PerspectiveBadge) consolidated under a consistent API with documented usage guidelines
2. Images page badges adopt an inline-in-description pattern where appropriate, matching Catalog's scannable style
3. Matches on the Images page render as cards with affordance consistent with CatalogImageCard

### Phase 7: React Suspense data layer (no deps)

**Goal:** Replace the ~24 hand-rolled `useEffect` + `setState` + API call sites in `apps/visualizer/frontend` with a tiny React-only Suspense data layer (module-level cache + `use(promise)` + `<ErrorBoundary>`), eliminating duplicate requests, unifying loading UI, and centralizing error handling without adding any external dependency.

**Requirements:** DATA-01 (new — see `phases/07-react-suspense-data-layer/CONTEXT.md`)

**Decisions:** Full migration in one phase (no pilot). Manual invalidation via `invalidate(key)`. No TTL/LRU eviction — cache lives for the tab. Page-level `<ErrorBoundary>` + shared `<ErrorState>`. Zero new npm dependencies.

**Success criteria:**
1. Zero `useEffect` blocks whose sole purpose is data fetching remain in the frontend.
2. Every page route wraps children in `<ErrorBoundary><Suspense>` with a shared `<SkeletonGrid>` fallback.
3. `/api/providers/defaults` (and every other endpoint) fires at most once per unique cache key per tab session (verified via backend log audit).
4. Mutations invalidate cache via `invalidate(key)` / `invalidateAll(prefix)`; no components keep manual `load()`/`refetch()` helpers.
5. Shared `<ErrorState>` fallback replaces every per-component error text node.
6. `npx tsc --noEmit`, `npx vitest run`, `npx vite build` all green.
7. `package.json` dependency count is unchanged (no new runtime deps).
8. No user-visible regression across Identity, Images (all tabs), Processing, Analytics, Dashboard.

---

*Roadmap created: 2026-04-10 · v1.0 shipped: 2026-04-11 · v2.0 shipped: 2026-04-15 · v2.1 started: 2026-04-17*
