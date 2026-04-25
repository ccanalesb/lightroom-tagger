# Phase 6: Similarity & Stack UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 06-similarity-stack-ui
**Areas discussed:** Phase 7 handoff

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Similarity entry behavior | Where "More like this" appears and what result surface it opens. | |
| Similarity result contract | How strict ranking, filters, missing embeddings, and explanation metadata should behave. | |
| Stack display and expansion | How representatives, count badges, and member browsing appear in Catalog and Best Photos. | |
| Phase 7 handoff | What minimal hooks to leave for chat pin and stack-aware matching without implementing those future capabilities. | ✓ |

**User's choice:** Phase 7 handoff.
**Notes:** User chose to discuss only the future handoff boundary.

---

## Phase 7 Handoff

| Option | Description | Selected |
|--------|-------------|----------|
| Only build the visible Phase 6 features | Future chat pin and matching can be handled later. | |
| Build visible Phase 6 features plus small reusable plumbing | Add small reusable helpers/types/data shapes if they naturally help future chat pin or matching. | ✓ |
| You decide | Keep Phase 6 clean and avoid overbuilding. | |

**User's choice:** Build visible Phase 6 features plus small reusable plumbing if it naturally helps future chat pin/matching.
**Notes:** Initial technical questions were confusing, so the decision was restated in plain product terms. The locked decision is to avoid overbuilding while keeping reusable seams where they naturally fall out of the visible Phase 6 implementation.

---

## Claude's Discretion

- Exact placement of the "More like this" control.
- Exact stack member expansion UI, provided it follows existing tile/grid patterns.
- Exact helper/type shape for future Phase 7 reuse, provided it is used by Phase 6 and not speculative.

## Deferred Ideas

- Chat pin-to-image UI and behavior — Phase 7.
- Stack-aware Instagram matching — Phase 7.
- Split, merge, and change representative controls — Phase 7.
- pHash near-duplicate stack clustering — dropped, not deferred.
