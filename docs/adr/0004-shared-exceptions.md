# ADR-0004: Shared exceptions package

**Status:** Accepted  
**Date:** 2026-04-29

## Context

Exception types were split across two locations: `lightroom_tagger/core/provider_errors.py` (provider error hierarchy) and `StackMutationError` inline in `database.py`. As the codebase grows, error types from new sub-modules would scatter further.

## Decision

Introduce `lightroom_tagger/core/exceptions/` package:

```
lightroom_tagger/core/exceptions/
    __init__.py          # re-exports everything — the one entry point
    provider_errors.py   # moved from core/provider_errors.py
    db_errors.py         # StackMutationError and future DB-layer errors
```

All callers import from `lightroom_tagger.core.exceptions`, never from inner modules. `core/provider_errors.py` becomes a re-export shim pointing at `exceptions.provider_errors` during transition, then removed.

## Consequences

- One canonical place to discover all domain error types
- New error types (e.g. catalog errors, pipeline errors) have a natural home
- Callers are insulated from internal reorganisation of the exceptions package
