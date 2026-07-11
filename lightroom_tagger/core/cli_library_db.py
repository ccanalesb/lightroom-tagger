"""CLI adapter for library-DB path resolution and managed connection lifecycle."""

from __future__ import annotations

import functools
from collections.abc import Callable
from pathlib import Path

from lightroom_tagger.core.managed_connections import managed_library_db


class CliError(Exception):
    """CLI-facing error; printed as ``Error: <message>`` by adapters."""


_MISSING_DB_PATH_MSG = "No database path provided. Use --db or config.yaml"


def resolve_library_db_path(args, config, *, must_exist: bool = False) -> str:
    """Resolve ``args.db or config.db_path`` with optional existence guard."""
    db_path = args.db or config.db_path
    if not db_path:
        raise CliError(_MISSING_DB_PATH_MSG)
    if must_exist and not Path(db_path).exists():
        raise CliError(f"Database not found: {db_path}")
    return db_path


def _handle_cli_failure(exc: BaseException) -> int:
    print(f"Error: {exc}")
    return 1


def map_cli_errors(handler: Callable[..., int]) -> Callable[..., int]:
    """Map :class:`CliError` and body exceptions to ``Error: …`` + exit code 1."""

    @functools.wraps(handler)
    def wrapper(*args, **kwargs) -> int:
        try:
            return handler(*args, **kwargs)
        except CliError as exc:
            return _handle_cli_failure(exc)
        except Exception as exc:
            return _handle_cli_failure(exc)

    return wrapper


def with_library_db(
    *,
    must_exist: bool = False,
    require_path: bool = True,
) -> Callable[[Callable[..., int]], Callable[..., int]]:
    """Open a managed library DB, invoke ``handler(args, config, db)``, map errors."""

    def decorator(handler: Callable[..., int]) -> Callable[..., int]:
        @functools.wraps(handler)
        def wrapper(args, config) -> int:
            try:
                if require_path:
                    db_path = resolve_library_db_path(args, config, must_exist=must_exist)
                else:
                    db_path = args.db or config.db_path
                with managed_library_db(db_path) as db:
                    return handler(args, config, db)
            except CliError as exc:
                return _handle_cli_failure(exc)
            except Exception as exc:
                return _handle_cli_failure(exc)

        return wrapper

    return decorator
