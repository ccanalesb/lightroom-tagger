"""Resolve the Lightroom catalog SQLite mirror path used by job handlers.

Resolution order (first hit wins):
    1. ``LIBRARY_DB`` environment variable (backward compatible).
    2. ``db_path`` from the repo-level ``config.yaml`` loaded via
       ``lightroom_tagger.core.config.load_config``.
    3. ``'library.db'`` relative to the current working directory (legacy default).

``describe_library_db()`` never raises — it returns a structured dict suitable
for a health endpoint or a startup log line, including why resolution failed.
Job types that cannot run without the catalog should call
``require_library_db()``; endpoints that merely inspect state should call
``describe_library_db()``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from lightroom_tagger.core.config import load_config as _load_lt_config
except Exception:  # pragma: no cover - defensive import guard
    _load_lt_config = None  # type: ignore[assignment]


# Resolve repo root (…/lightroom-tagger) by walking up from this file. The
# backend cwd is usually ``apps/visualizer/backend`` where no config.yaml
# exists, which is why the old relative-path default broke job handlers.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..')
)
_REPO_CONFIG_YAML = os.path.join(_REPO_ROOT, 'config.yaml')


# Job types whose handlers open the Lightroom catalog SQLite mirror. Keep this
# list in sync with ``jobs/handlers.py`` — if a handler calls ``init_database``
# with ``LIBRARY_DB``, its job type belongs here.
JOB_TYPES_REQUIRING_CATALOG: frozenset[str] = frozenset(
    {
        'vision_match',
        'enrich_catalog',
        'prepare_catalog',
        'batch_describe',
        'batch_score',
        'batch_analyze',
        'single_describe',
        'single_score',
        'instagram_import',
    }
)


@dataclass(frozen=True)
class LibraryDbStatus:
    path: str | None
    source: str  # 'env' | 'config' | 'default' | 'none'
    exists: bool
    reason: str | None  # human-readable explanation when unavailable

    def to_dict(self) -> dict:
        return {
            'path': self.path,
            'source': self.source,
            'exists': self.exists,
            'reason': self.reason,
        }


def describe_library_db() -> LibraryDbStatus:
    """Resolve the library DB path and report whether it exists."""
    env_value = os.getenv('LIBRARY_DB')
    if env_value:
        exists = os.path.isfile(env_value)
        return LibraryDbStatus(
            path=env_value,
            source='env',
            exists=exists,
            reason=None if exists else f"LIBRARY_DB is set to {env_value!r} but that file does not exist.",
        )

    if _load_lt_config is not None:
        try:
            cfg = _load_lt_config(_REPO_CONFIG_YAML)
        except Exception as e:  # pragma: no cover - defensive
            return LibraryDbStatus(
                path=None,
                source='none',
                exists=False,
                reason=f"Failed to load {_REPO_CONFIG_YAML}: {e}",
            )
        if cfg.db_path:
            exists = os.path.isfile(cfg.db_path)
            return LibraryDbStatus(
                path=cfg.db_path,
                source='config',
                exists=exists,
                reason=None if exists else (
                    f"config.yaml db_path is {cfg.db_path!r} but that file does not exist. "
                    f"Run the catalog import to create it, or set LIBRARY_DB to override."
                ),
            )

    default_path = 'library.db'
    exists = os.path.isfile(default_path)
    return LibraryDbStatus(
        path=default_path if exists else None,
        source='default' if exists else 'none',
        exists=exists,
        reason=None if exists else (
            "No LIBRARY_DB env var, no db_path in config.yaml, and no library.db in the "
            "current working directory. Set LIBRARY_DB or configure db_path in config.yaml."
        ),
    )


def resolve_library_db() -> str | None:
    """Return the resolved path if it exists, otherwise None."""
    status = describe_library_db()
    return status.path if status.exists else None


def require_library_db() -> str:
    """Return the resolved path, or raise ``FileNotFoundError`` with a clear reason."""
    status = describe_library_db()
    if status.exists and status.path:
        return status.path
    raise FileNotFoundError(status.reason or 'Library database is not configured.')
