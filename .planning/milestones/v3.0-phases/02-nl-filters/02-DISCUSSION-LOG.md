# Phase 2: NL filters — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 02-nl-filters
**Areas discussed:** Scope/VIS-02, Endpoint shape, LLM strategy

---

## Scope — VIS-02 removal

| Option | Description | Selected |
|--------|-------------|----------|
| Add manual color/mood filter chips to FilterBar | VIS-02 as written — new `select` descriptors for dominant_colors/mood_tags | |
| Remove VIS-02, fold into NLS-01 LLM | LLM handles color/mood interpretation; no manual chips | ✓ |

**User's choice:** Delete VIS-02 entirely. Manual filter chips are too complicated to maintain. LLM-driven discovery is the right approach — user types "blue moody photos" and the LLM figures out what that means across sentiment, style, and color.

---

## NL input UI placement

| Option | Description | Selected |
|--------|-------------|----------|
| Above FilterBar in CatalogTab | Prominent AI search row | |
| Inline with FilterBar | New search descriptor | |
| Below FilterBar | Separate row | |
| Phase 5 chat panel (NLS-05) | Dedicated search screen, not CatalogTab | ✓ |

**User's choice:** NL search belongs in the Phase 5 chat screen, not CatalogTab. Phase 2 is backend plumbing only.

---

## Response shape

| Option | Description | Selected |
|--------|-------------|----------|
| Results only | Just the catalog rows | |
| Results + derived filter object | Both, so Phase 5 can show "I understood: ..." | ✓ |

**User's choice:** Return both results and the filter object the LLM derived.

---

## Simple query bypass

| Option | Description | Selected |
|--------|-------------|----------|
| Bypass LLM for keyword-only queries | Route to FTS directly | |
| Always call LLM | Let LLM decide whether to use description_search or visual fields | ✓ |

**User's choice:** Always call the LLM. Consistent behavior, LLM decides the right filter combination.

---

## Deferred Ideas

- VIS-02 removed from roadmap
- Frontend NL UI deferred to Phase 5
