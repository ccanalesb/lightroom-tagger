# Phase 11: v3.0 Deferred Polish — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 11-v3-deferred-polish
**Areas discussed:** stack_size resolution, tool-calling pin schema, vision_judgments_total rename, embed discoverability CTA scope

---

## stack_size resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Keep synced | Audit mutations, add assertion or test that column matches live count | |
| Drop column | Always compute from live members via stack_metadata_for_api; removes drift risk | |
| Document and accept | Add code comment explaining pre-existing drift risk, no behavior change | ✓ |

**User's choice:** Document and accept
**Notes:** Drift is theoretical — no known real occurrence. stack_metadata_for_api is already the authoritative source for API responses.

---

## Tool-calling pin schema tightening

| Option | Description | Selected |
|--------|-------------|----------|
| Scope stats to pin set | Filter get_catalog_schema response to pin-restricted counts when pin is active | |
| Rewrite description text only | Add note in schema response warning LLM about pin scope, keep numbers global | |
| Document and defer | Add code comment, no behavior change — Phase 7 called this "optional future hardening" | ✓ |

**User's choice:** Document and defer
**Notes:** Execution is correctly restricted by restrict_to_keys at runtime; schema inaccuracy is cosmetic.

---

## vision_judgments_total rename

| Option | Description | Selected |
|--------|-------------|----------|
| Rename to candidate_evaluations | Precise, but breaking change for log parsers | |
| Add inline comment only | Explain what the counter tracks, keep key name unchanged | ✓ |
| Rename log label only | Change human-readable output only, keep stats dict key | |

**User's choice:** Add inline comment only
**Notes:** Avoids breaking any log parsers or monitoring that grep for the existing key name.

---

## Embed discoverability CTA scope

| Option | Description | Selected |
|--------|-------------|----------|
| Inline enqueue CTA | Build Start embed button in SearchPage that enqueues batch_embed_image directly | |
| Navigation links only | Warning + help text + Open Catalog Cache + Open Job Queue links only | ✓ |

**User's choice:** Navigation links only
**Notes:** User navigates to Processing tab to start the job. Less code, same outcome.

---

## Claude's Discretion

- Exact wording of stack_size and get_catalog_schema code comments
- Exact strings.ts key names for embed discoverability copy
- Whether to add type="button" to AdvancedOptions disclosure button (UI-SPEC marks as defensive/optional)

## Deferred Ideas

- CollapsibleSection aria-expanded pattern — later pass
- Tool-calling schema stat scoping — future phase if needed
- vision_judgments_total full rename — deferred (log parser risk)
- Backend preflight + grouped skip counts — not in Phase 11 scope
- Inline Start embed CTA in SearchPage — deferred
