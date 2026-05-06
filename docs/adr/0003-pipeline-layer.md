# ADR-0003: Introduce pipeline layer in lightroom_tagger/core

**Status:** Accepted  
**Date:** 2026-04-29

## Context

`apps/visualizer/backend/jobs/handlers.py` (3833 lines) contained two distinct concerns: job lifecycle orchestration (progress mapping, checkpoint loading, pass runners) AND library-level domain logic (matching, describing, scoring). Handlers reached directly into `lightroom_tagger.core.database` via 12 scattered deferred import sites. The library was not independently usable from CLI or other consumers without re-implementing handler logic.

## Decision

Introduce `lightroom_tagger/core/pipelines.py` — a module of top-level functions exposing high-level operations:

```python
ProgressCallback = Callable[[int, str], None]

def run_match_pipeline(db, *, progress_cb: ProgressCallback, checkpoint_cb: Callable[[dict], None], initial_checkpoint: dict | None, ...) -> ...: ...
def run_describe_pipeline(...) -> ...: ...
def run_score_pipeline(...) -> ...: ...
# etc.
```

Design decisions:

- **Functions, not a class** — no shared mutable state between pipeline calls; functions compose better with `FallbackDispatcher` and `library_write`
- **`ProgressCallback = Callable[[int, str], None]`** — pct + message; promotes to `Protocol` only if a second adapter appears
- **Checkpoint ownership moves to pipelines** — `checkpoint_cb: Callable[[dict], None]` for persisting, `initial_checkpoint: dict | None` for resuming. The visualizer handler passes `runner`'s checkpoint save/load as the adapter
- **Handlers become thin adapters** — accept job metadata, call pipeline fn, emit progress; ~100 lines each

## Consequences

- Library is independently usable from CLI, tests, or any future consumer without a running Flask app
- Pipeline fns are testable with a mock db and `lambda pct, msg: None`
- Handlers shrink dramatically; job orchestration complexity concentrates in one place
- The seam between "what the library does" and "how the visualizer runs jobs" becomes explicit
