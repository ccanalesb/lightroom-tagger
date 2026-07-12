"""Catalog sync job handler."""

from __future__ import annotations

import os

from database import add_job_log

from lightroom_tagger.core import cancel_scope
from lightroom_tagger.core.catalog_sync import (
    CATALOG_LOCK_ACTIONABLE_MSG,
    CatalogSyncError,
    sync_catalog,
)
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import init_database

from .db_lifecycle import make_managed_library_db
from .common import _failure_severity_from_exception, _resolve_library_db_or_fail

managed_library_db = make_managed_library_db(lambda p: init_database(p))


def _resolve_catalog_path(metadata: dict) -> str | None:
    catalog_path = metadata.get('catalog_path')
    if catalog_path:
        return str(catalog_path)
    config = load_config()
    return config.catalog_path


def _handle_catalog_sync_inner(
    runner,
    job_id: str,
    metadata: dict,
    *,
    chain_mode: bool = False,
) -> dict | None:
    """Run incremental catalog sync. Returns result dict on success; None after standalone failure."""
    db_path = _resolve_library_db_or_fail(runner, job_id)
    if db_path is None:
        return None

    catalog_path = _resolve_catalog_path(metadata)
    if not catalog_path:
        msg = 'No catalog path configured. Set catalog_path in config.yaml.'
        if chain_mode:
            add_job_log(runner.db, job_id, 'warning', f'[catalog-cache-build] stage=sync status=skipped {msg}')
            return {'skipped': True, 'error': msg, 'added': 0, 'stale': 0}
        runner.fail_job(job_id, msg, severity='warning')
        return None

    if not os.path.exists(catalog_path):
        msg = f'Catalog not found: {catalog_path}'
        if chain_mode:
            add_job_log(runner.db, job_id, 'warning', f'[catalog-cache-build] stage=sync status=skipped {msg}')
            return {'skipped': True, 'error': msg, 'added': 0, 'stale': 0}
        runner.fail_job(job_id, msg, severity='warning')
        return None

    if not chain_mode:
        runner.update_progress(job_id, 5, 'Connecting to Lightroom catalog...')

    with managed_library_db(db_path) as lib_db:
        try:
            def log_cb(level: str, message: str) -> None:
                add_job_log(runner.db, job_id, level, message)

            def progress_cb(pct: int, msg: str | None) -> None:
                runner.update_progress(job_id, pct, msg)

            result = sync_catalog(
                catalog_path,
                lib_db,
                log=log_cb,
                progress=progress_cb if not chain_mode else None,
            )
        except CatalogSyncError as exc:
            msg = str(exc) or CATALOG_LOCK_ACTIONABLE_MSG
            if chain_mode:
                add_job_log(
                    runner.db,
                    job_id,
                    'warning',
                    f'[catalog-cache-build] stage=sync status=failed error={msg}',
                )
                return {'failed': True, 'error': msg, 'added': 0, 'stale': 0}
            runner.fail_job(job_id, msg, severity='warning')
            return None
        except Exception as exc:
            severity = _failure_severity_from_exception(exc)
            if chain_mode:
                add_job_log(
                    runner.db,
                    job_id,
                    'warning',
                    f'[catalog-cache-build] stage=sync status=failed error={exc}',
                )
                return {'failed': True, 'error': str(exc), 'added': 0, 'stale': 0}
            runner.fail_job(job_id, str(exc), severity=severity)
            return None

        payload = {
            'added': result.added,
            'stale': result.stale,
            'locking_mode': result.locking_mode,
            'catalog_total': result.catalog_total,
            'library_total': result.library_total,
            'missing_ids_count': result.missing_ids_count,
        }
        runner.complete_job(job_id, payload)
        return payload


def handle_catalog_sync(runner, job_id: str, metadata: dict) -> None:
    """Standalone catalog sync — failures are fatal."""
    with cancel_scope.install(lambda: runner.is_cancelled(job_id)):
        _handle_catalog_sync_inner(runner, job_id, metadata, chain_mode=False)
