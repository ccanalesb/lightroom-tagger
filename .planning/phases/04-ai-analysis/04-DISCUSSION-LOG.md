# Phase 4: AI Analysis - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 04-ai-analysis
**Areas discussed:** Provider configuration UX, Description viewing experience, Analyzed vs not-analyzed indicators, Batch job scoping

---

## Provider Configuration UX

| Option | Description | Selected |
|--------|-------------|----------|
| Keep existing card-based list + add connection validation badge | No wizard, just add reachable/unreachable indicator per provider | ✓ |
| Setup wizard | Step-by-step provider configuration flow | |
| Keep as-is (no changes) | Existing provider UI without validation feedback | |

**User's choice:** Keep existing card-based list, add connection validation badge. No wizard.
**Notes:** User explicitly confirmed "no wizard". Current ProvidersTab infrastructure is sufficient for single-photographer use case.

---

## Description Viewing Experience

| Option | Description | Selected |
|--------|-------------|----------|
| Surface in all places (cards, modal, dedicated page) | Three integration points at increasing detail levels | ✓ |
| Dedicated page only | Keep descriptions isolated on the Descriptions page | |
| Modal only | Show descriptions only when opening an image | |

**User's choice:** Surface descriptions in all places — catalog cards (AI badge + score pill), catalog modal (collapsible DescriptionPanel + GenerateButton), and dedicated Descriptions page.
**Notes:** Recommendation based on DESIGN.md patterns. User confirmed "i like it".

---

## Analyzed vs Not-Analyzed Indicators

| Option | Description | Selected |
|--------|-------------|----------|
| Badge-based (accent variant) | "AI" badge on cards/modals + analyzed filter in catalog | ✓ |
| Progress bar / coverage stat | Dashboard-level coverage percentage | |
| Icon overlay on thumbnails | Small AI icon overlaid on image thumbnails | |

**User's choice:** Badges are enough. Accent badge for AI status + analyzed filter in catalog bar.
**Notes:** User chose the simplest option. Fits existing badge row pattern on CatalogImageCard.

---

## Batch Job Scoping

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing filter-based panel (unanalyzed default + rating filter) | Add to current DescriptionsTab, no new multi-select UX | ✓ |
| Multi-select from catalog grid | Let users pick individual photos for batch describe | |
| Smart auto-scoping | System decides which photos to describe based on heuristics | |

**User's choice:** Extend existing filter-based panel with unanalyzed-only default and rating filter.
**Notes:** Multi-select grid deferred to v2. User accepted recommendation.

---

## Claude's Discretion

- Exact placement/sizing of AI badge and score pill on catalog cards
- Catalog modal description panel initial collapsed/expanded state
- Connection test implementation approach
- Rating filter layout integration in DescriptionsTab

## Deferred Ideas

None — discussion stayed within phase scope
