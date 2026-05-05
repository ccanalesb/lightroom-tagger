# Phase 13: Handlers split (per-job-family) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 13-handlers-split-per-job-family
**Areas discussed:** Module naming & grouping, Import compatibility, Shared private helpers, Split order & atomicity

---

## Module naming & grouping

| Option | Description | Selected |
|--------|-------------|----------|
| A — Flat files + facade | `handlers_analyze.py` etc. alongside existing `handlers.py` facade | |
| B — Subpackage | `jobs/handlers/` with `__init__.py` + submodules | ✓ |

**User's choice:** Subpackage (Option B)
**Notes:** Cleaner long-term shape.

---

## Import compatibility (`__init__.py` exposure)

| Option | Description | Selected |
|--------|-------------|----------|
| B1 — Re-export everything | All `handle_*` names re-exported from `__init__.py`; zero test changes | |
| B2 — JOB_HANDLERS only | Only `JOB_HANDLERS` in `__init__.py`; test imports updated to submodules | ✓ |
| B3 — No re-exports | Fully explicit; all imports updated | |

**User's choice:** B2
**Notes:** Sweet spot — `JOB_HANDLERS` stays in `__init__.py` (natural home for `app.py`), tests get updated imports that reflect the new structure. ~60 import lines to update across ~15 test files.

---

## Shared private helpers

| Option | Description | Selected |
|--------|-------------|----------|
| A — Co-locate + common.py | Single-user helpers in their module; cross-family in `common.py` | |
| B — All in common.py | Every non-trivial helper in `common.py` | |
| C — Primary-consumer + common.py | Helpers live with their primary consumer; true cross-cutters in `common.py` | ✓ |

**User's choice:** Option C
**Notes:** `_resolve_library_db_or_fail`, `_failure_severity_from_exception`, `_select_catalog_keys` family, `_resolve_date_window` → `common.py`. Single-consumer helpers stay in their owning module.

---

## JOB_HANDLERS assembly

| Option | Description | Selected |
|--------|-------------|----------|
| 1 — Assembled in __init__.py | Explicit dict built from submodule imports; one place to audit | ✓ |
| 2 — Self-registering submodules | Each submodule appends to shared dict on import | |

**User's choice:** Option 1
**Notes:** Self-registration is over-engineering for a fixed set of 15 known handlers.

---

## Split order & atomicity

| Option | Description | Selected |
|--------|-------------|----------|
| A — One commit per family | Scaffold implicit in first commit | |
| B — All in one commit | Single atomic change | |
| C — Scaffold first, then per-family | Explicit scaffold commit, then 5 family commits, then cleanup | ✓ |

**User's choice:** Option C
**Notes:** Safest for a 3,849-line file. Each commit independently green and bisectable.

---

## Claude's Discretion

- Exact scaffold strategy (transitional shim approach)
- Whether module-level constants move to `common.py` or stay in primary-consumer module
- Order of the 5 family migration commits

## Deferred Ideas

None — discussion stayed within phase scope.
