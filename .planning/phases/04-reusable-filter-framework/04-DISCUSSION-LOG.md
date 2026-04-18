# Phase 4: Reusable filter framework - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `04-CONTEXT.md` — this log preserves the gray areas that were presented and the fact that the user waived detailed discussion.

**Date:** 2026-04-17
**Phase:** 04-reusable-filter-framework
**Mode:** `/gsd-discuss-phase 4` (interactive, no flags)
**Areas discussed:** None selected — user waived detailed discussion after gray-area presentation.

---

## Presentation

Six gray areas were surfaced in the initial presentation:

1. **Schema shape & primitive set** — the declarative contract (primitive types, dependent filters, numberRange?)
2. **State hook semantics** — `useFilters(schema)` return surface, live vs apply mode, debounce source, activeCount semantics, pagination integration
3. **Query-param mapping** — filter values → API params (schema vs adapter, rename, conditional emission)
4. **FilterBar layout & chip affordance** — chips replace vs supplement controls, Clear-all placement
5. **Migration strategy for CatalogTab** — big-bang vs incremental, regression detection, outward-dispatch pattern
6. **AnalyticsPage parity** — does Phase 4 accommodate apply-button flows or scope-lock to live?

## User Response

> "i think im good"

Interpreted as: the gray areas are understood; no interactive walk-through needed. Claude infers decisions from the codebase, REQUIREMENTS.md, and prior-phase patterns, flagging any genuine ambiguity as **Claude's Discretion** for the planner.

## Decisions Inferred (see `04-CONTEXT.md` for the full list)

- **Area 1 (Schema):** Typed discriminated union, 4 primitives (toggle, select, dateRange, search), `enabledBy` for dependents, no `numberRange`, no `dependentGroup` nesting. (D-01 .. D-05)
- **Area 2 (Hook):** Object return with `values`/`rawValues`/`setValue`/`setValues`/`clearAll`/`activeCount`/`toQueryParams`/`isActive`. Live-update only; debounce from schema (350ms default); activeCount ignores disabled dependents; framework doesn't own pagination; dependent clearing is automatic. (D-06 .. D-11)
- **Area 3 (Query params):** `paramName` + `toParam` on each descriptor; snake_case default for `paramName`; no composite mapping. (D-12 .. D-14)
- **Area 4 (Layout):** Chips supplement inline controls (not replace); `Clear all` top-right (current position); per-chip ✕; no popover. (D-15 .. D-18)
- **Area 5 (Migration):** Big-bang in one plan; three-layer regression strategy (existing tests green + new framework tests + manual smoke); outward `onPostedFilterChange` survives unchanged. (D-19 .. D-21)
- **Area 6 (AnalyticsPage):** Scope-locked to live-update only. Apply-button support deferred to a future milestone via a later `mode` option. REQUIREMENTS.md Implementation Guidance is the hard scope anchor. (deferred, `<deferred>` section)

## Claude's Discretion (items left to the planner)

- TS type names for the discriminated union variants
- File/folder layout (`components/filters/` vs `components/ui/filters/`)
- Chip visual treatment (reuse `Badge` vs new component)
- `dateRange` as one descriptor or two linked `date` descriptors
- Timing of the `useDebouncedValue` extraction (same plan vs prep commit)
- Test framework specifics (match existing — Vitest + Testing Library)

## Deferred Ideas

All six items noted in the presentation were deferred per REQUIREMENTS.md Implementation Guidance and the user's scope-lock posture from v2.1 start:

- AnalyticsPage migration (apply-button paradigm)
- InstagramTab / MatchesTab / DescriptionsTab / MatchingTab / UnpostedCatalogPanel migrations
- URL syncing of filter state
- Saved-filter presets
- Natural-language search → schema compilation
- `numberRange` primitive
- `dependentGroup` nested primitive
- Popover / collapsible filter UX
- Framework-level outward value subscription

See `04-CONTEXT.md` `<deferred>` for rationale on each.
