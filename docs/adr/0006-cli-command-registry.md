# ADR-0006: CLI dispatch via explicit command registry

**Status:** Accepted  
**Date:** 2026-07-06

## Context

The live CLI (`lightroom_tagger/core/cli.py`) grew a hand-maintained `create_parser()` flag block and a parallel `if/elif` dispatch chain. Adding or renaming a command required touching two distant sites, and subcommand flags were easy to drift from their handlers (PRD #40).

## Decision

Introduce `lightroom_tagger/core/cli_commands.py` as the single registration surface for CLI subcommands:

- A `Command` dataclass holds `name`, `help`, `add_arguments(subparser)`, and `handler(args, config)`.
- `COMMANDS` is an explicit, greppable list — no decorators or auto-discovery.
- Existing `cmd_*` handler bodies stay in `cli.py` and `cli_cmds_extra.py`; the registry imports them.
- `run(argv, config, commands) -> int` in `cli.py` builds the parser from the registry, parses argv, applies global-arg→config overrides, and dispatches by name.
- `main()` loads config, then calls `run(sys.argv[1:], config, COMMANDS)`.
- Top-level global args (`--catalog`, `--db`, `--config`, `--workers`, `--verbose`, `--limit`, `--ai-model`, `--skip-ai`) and their config mutation remain in the engine, outside the registry.

## Consequences

- New commands are one registry entry; parser and dispatch cannot diverge.
- `cli_commands.py` may grow with per-command flag definitions; heavyweight handler logic stays split across `cli.py` / `cli_cmds_extra.py` for the line budget.
- Tests can drive `run()` with a fake registry and stub config without touching real catalogs, databases, or subprocesses.

## Alternatives considered

- **`if/elif` dispatch** — rejected; duplicates command names and hides drift between parser and handler routing.
- **Decorator-based auto-discovery** — rejected; registration is harder to grep and import order becomes implicit.
