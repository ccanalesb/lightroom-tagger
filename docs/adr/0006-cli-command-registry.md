# ADR-0006: CLI command registry

**Status:** Accepted  
**Date:** 2026-07-06

## Context

The CLI entry point (`lightroom_tagger/core/cli.py`) originally declared each subcommand in three places: flag definitions inside `create_parser()`, handler imports, and an `if/elif` chain in `main()`. That layout made it easy for parser wiring and dispatch to drift apart, and routing could not be tested without running the full CLI (config load, catalog I/O, subprocesses).

## Decision

Introduce an explicit **command registry** in `lightroom_tagger/core/cli_commands.py`:

- Each command is a `Command` dataclass: `name`, `help`, `add_arguments(subparser)`, and `handler(args, config)`.
- `COMMANDS` is a plain list of those entries — no decorators, no import-time auto-discovery.
- `create_parser(commands)` and dispatch both derive from the same list.
- `run(argv, config, commands) -> int` is the testable engine; `main()` loads config and calls `run(sys.argv[1:], config, COMMANDS)`.
- Top-level global flags (`--catalog`, `--db`, `--config`, `--workers`, etc.) and global-arg→config mutation stay in `cli.py`, outside the registry.

Handlers remain in `cli.py` (lightweight) and `cli_cmds_extra.py` (heavyweight); the registry imports them lazily via `_build_commands()` to avoid import cycles.

## Consequences

- Adding or changing a subcommand is a single registry entry instead of three coordinated edits.
- Dispatch tests drive `run()` with a fake registry — no real DB, catalog, or config file required.
- Per-command flag blocks live next to the registry entry; `cli.py` reads as a thin engine.
- We deliberately keep an explicit list rather than an `if/elif` chain or plugin magic so the command surface stays greppable and reviewable.
