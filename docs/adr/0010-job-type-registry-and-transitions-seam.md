# ADR-0010: Job-type registry and status-transition seam

**Status:** Accepted  
**Date:** 2026-07-11

## Context

The visualizer job processor grew parallel surfaces for the same knowledge: a
handler dispatch map, a catalog-requirement set, and checkpoint helpers keyed by
job type lived apart from one another; cancel/retry routes embedded status
legality checks and `update_job_status` targets inline (parent initiative #55).

## Decision

Mirror [ADR-0006](0006-cli-command-registry.md)'s explicit registry pattern for
visualizer jobs:

1. **`jobs/registry.py` is the single registration surface.** A `JobType`
   dataclass holds `name`, `handler`, checkpoint co-location
   (`fingerprint`, `resume_loader`, `build_checkpoint_body`,
   `checkpoint_mismatch_message`), and `requires_catalog`. `JOB_TYPES` is an
   explicit, greppable list — no decorators or auto-discovery. Handler bodies
   stay in `jobs/handlers/` (one module per family); the registry imports them.
2. **Derived maps must not be edited.** `JOB_HANDLERS` (`jobs/handlers/__init__.py`)
   and `JOB_TYPES_REQUIRING_CATALOG` (`library_db.py`) are lazy projections from
   `JOB_TYPES` for backward compatibility during migration. Dispatch and
   catalog-gating call `get_job_handler()` / `catalog_requiring_job_types()` or
   the derived constants — never a second literal map or frozenset.
3. **Checkpoint read/write uses registry entries.** `jobs/checkpoint.py` resolves
   per-type checkpoint helpers via `job_type_entry()` / `JOB_TYPES_BY_NAME` so
   fingerprint, resume, and persist logic stay co-located with the handler
   registration, not duplicated at call sites.
4. **Status-transition rules live in `jobs/transitions.py`, not routes.**
   Cancellable, terminal, and retryable status sets, `can_cancel` / `can_retry`,
   and `transition_cancel` / `transition_retry` are pure functions with no
   Flask dependency. `api/jobs.py` delegates to those transitions and maps
   `Outcome` to HTTP — it must not reintroduce status legality literals or
   `update_job_status` targets for cancel/retry.

Static guardrail tests enforce (1)–(2) and (4) with explicit allow-lists.

## Consequences

- New job types are one `JobType` registry entry; dispatch, catalog requirement,
  and checkpoint metadata cannot drift.
- Cancel/retry behaviour is unit-testable without HTTP; route tests cover wiring
  only (socketio emit, `signal_cancel`, status codes).
- Slight indirection via registry lookups; acceptable for one place to audit job
  knowledge.
- `jobs/registry.py` may grow with per-type checkpoint wiring; handler logic
  stays split across `jobs/handlers/*` for the line budget.

## Alternatives considered

- **Parallel `if/elif` on `job_type` in `app.py` or routes** — rejected; duplicates
  names and hides drift between dispatch, catalog gating, and checkpoints.
- **Decorator-based handler auto-discovery** — rejected; registration is harder
  to grep and import order becomes implicit (same rationale as ADR-0006).
- **Inline cancel/retry status checks in `api/jobs.py`** — rejected; HTTP layer
  mixed policy with transport and duplicated rules already tested in isolation.
