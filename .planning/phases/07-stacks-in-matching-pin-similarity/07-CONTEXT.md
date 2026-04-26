# Phase 7: Stacks in matching & pin similarity - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver v3.0 Phase 7 behavior for STACK-04, STACK-05, and NLS-06:

- Matching uses stack representatives as the comparison surface, then applies confirmed matches across stack members per policy.
- Users can split, merge, and change representative from the Images stack-expanded experience.
- Search chat supports pinning one active catalog image as a visual anchor for follow-up turns.

Out of scope:
- New matching capabilities outside representative-first stack behavior
- Multi-pin search behavior
- Any new standalone stack management page

</domain>

<decisions>
## Implementation Decisions

### Representative-first matching policy
- **D-01:** Representative matches auto-apply to the full stack immediately (no extra per-match confirmation).
- **D-02:** Conflict policy is partial apply: apply to non-conflicted members, skip conflicted members, and return/report counts.
- **D-03:** Conflict policy never overwrites existing conflicting matches by default.

### Stack editing UX and safety
- **D-04:** Stack edit operations (split, merge, change representative) live in the Images stack-expanded view.
- **D-05:** Destructive edits require confirm modal plus undo toast window.
- **D-06:** Use one shared generic confirm+undo flow/component pattern across reject-match and stack edits (DRY requirement).

### Search pin behavior
- **D-07:** Pin behavior is single active pin only; pinning a new image replaces the previous pin.
- **D-08:** With active pin, use intersection-first search flow: similar-to-pin candidates first, then apply text refinement/ranking inside that set.
- **D-09:** UI must show clear active-pin state (for example, "Pinned to X") so users understand the active anchor.

### Pin failure/degradation behavior
- **D-10:** If pinned similarity cannot run (missing embedding/query failure), use non-blocking fallback to normal text search.
- **D-11:** Fallback must be visible: show warning and keep pin visible in an inactive state.

### Verification expectations
- **D-12:** Phase verification must include integration checks for representative-only matching behavior and pin flow, plus targeted unit tests for policy edges.

### Claude's Discretion
- Exact copy and visual styling for warnings/toasts/labels
- Exact API payload field names for conflict and fallback metadata
- Exact undo timeout duration, as long as the undo affordance is present and consistent

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/ROADMAP.md` - v3.0 Phase 7 scope and success criteria for STACK-04, STACK-05, NLS-06
- `.planning/REQUIREMENTS.md` - detailed requirement language and dependency constraints
- `.planning/STATE.md` - current project phase pointer and milestone status

### Prior phase context
- `.planning/phases/04-stack-detection/04-CONTEXT.md` - stack schema, representative contract, stack job semantics
- `.planning/phases/05-image-embed-search-chat/05-CONTEXT.md` - search/chat architecture and conversation refinement decisions
- `.planning/phases/06-similarity-stack-ui/06-CONTEXT.md` - similarity APIs, stack UI surfaces, and Phase 7 handoff constraints

### Codebase maps
- `.planning/codebase/CONVENTIONS.md` - coding/test/style conventions for backend and frontend
- `.planning/codebase/STRUCTURE.md` - backend/frontend file ownership and extension points
- `.planning/codebase/STACK.md` - runtime stack and tooling constraints

### Backend integration points
- `apps/visualizer/backend/jobs/handlers.py` - vision matching flow and stack-aware apply points
- `apps/visualizer/backend/api/images.py` - similarity/search endpoints and response metadata contracts
- `lightroom_tagger/core/database.py` - stack membership and representative persistence/query helpers

### Frontend integration points
- `apps/visualizer/frontend/src/components/images/MatchesTab.tsx` - matching controls and result rendering
- `apps/visualizer/frontend/src/components/images/CatalogTab.tsx` - stack-expanded interactions in Images UI
- `apps/visualizer/frontend/src/components/image-view/ImageDetailModal.tsx` - image-level action patterns reused by stack actions
- `apps/visualizer/frontend/src/pages/SearchPage.tsx` - chat thread + results panel where pin behavior is surfaced
- `apps/visualizer/frontend/src/services/api.ts` - API contracts and mutation methods for matching/search flows

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing stack metadata and expand/collapse UI from Phase 6 can host edit controls directly.
- Existing match mutation flows already include confirmation and status patterns that can be generalized.
- Existing search page architecture already supports multi-turn refinement; pin state can be added without introducing a new page.

### Established Patterns
- API responses include metadata for degraded states; this supports explicit "pin inactive" fallback signaling.
- Frontend pages use centralized API services and shared UI primitives; stack edit safety should follow that pattern.
- Matching behavior expects observable counters and clear progress/failure messages.

### Integration Points
- Extend representative-match application path to stack-wide apply + conflict accounting.
- Add stack edit actions into stack-expanded image UI, reusing shared confirm+undo flow.
- Add single-pin state and pin-aware query strategy in search request/response path and UI state.

</code_context>

<specifics>
## Specific Ideas

- User preference: keep behavior simple and safe by default, especially around conflict handling and fallback behavior.
- DRY mandate: build one reusable confirm+undo interaction model and apply it across reject-match and stack-edit operations.
- Pin concept should stay understandable for non-technical users: one active visual reference at a time.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 07-stacks-in-matching-pin-similarity*
*Context gathered: 2026-04-26*
