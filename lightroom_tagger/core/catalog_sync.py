"""Incremental catalog sync — additions-only refresh from .lrcat into library.db."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Callable

from lightroom_tagger.core.database.catalog import store_images_batch
from lightroom_tagger.lightroom.reader import connect_catalog, get_image_by_id, list_catalog_file_ids

CATALOG_LOCK_ACTIONABLE_MSG = (
    "Cannot read Lightroom catalog (locked or unavailable). "
    "Close Lightroom Classic or set LIGHTRoom_CATALOG_LOCKING_MODE=NORMAL and retry."
)


class CatalogSyncError(Exception):
    """Catalog could not be opened or read (typically locked while Lightroom is open)."""


@dataclass(frozen=True)
class CatalogSyncResult:
    added: int
    stale: int
    locking_mode: str
    catalog_total: int
    library_total: int
    missing_ids_count: int


def _current_locking_mode() -> str:
    return os.getenv("LIGHTRoom_CATALOG_LOCKING_MODE", "EXCLUSIVE").upper()


def _is_catalog_unavailable_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "unable to open database file" in msg
        or "database is locked" in msg
        or "disk i/o error" in msg
    )


def list_library_catalog_ids(lib_db: sqlite3.Connection) -> set[int]:
    """Numeric catalog ids already indexed in ``images.id`` (TEXT column).

    Rows with empty or non-numeric ids are skipped so legacy data cannot break sync.
    """
    rows = lib_db.execute("SELECT id FROM images").fetchall()
    ids: set[int] = set()
    for row in rows:
        if isinstance(row, dict):
            raw = row.get('id')
        elif isinstance(row, sqlite3.Row):
            raw = row['id']
        else:
            raw = row[0]
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        try:
            ids.add(int(text))
        except ValueError:
            continue
    return ids


def sync_catalog(
    catalog_path: str,
    lib_db: sqlite3.Connection,
    *,
    log: Callable[[str, str], None] | None = None,
    progress: Callable[[int, str | None], None] | None = None,
) -> CatalogSyncResult:
    """Diff catalog ids against library.db, fetch metadata for missing ids only, upsert.

    Never deletes library rows. Reports stale count (library minus catalog) for logging.
    """
    locking_mode = _current_locking_mode()

    def _log(level: str, message: str) -> None:
        if log is not None:
            log(level, message)

    try:
        catalog_conn = connect_catalog(catalog_path)
    except (sqlite3.Error, OSError) as exc:
        raise CatalogSyncError(CATALOG_LOCK_ACTIONABLE_MSG) from exc

    try:
        try:
            catalog_ids = set(list_catalog_file_ids(catalog_conn))
        except sqlite3.Error as exc:
            if _is_catalog_unavailable_error(exc):
                raise CatalogSyncError(CATALOG_LOCK_ACTIONABLE_MSG) from exc
            raise
    except CatalogSyncError:
        catalog_conn.close()
        raise

    library_ids = list_library_catalog_ids(lib_db)
    missing_ids = sorted(catalog_ids - library_ids)
    stale_count = len(library_ids - catalog_ids)

    _log(
        "info",
        (
            f"[catalog-sync] mode=set_difference locking_mode={locking_mode} "
            f"catalog_total={len(catalog_ids)} library_total={len(library_ids)} "
            f"missing={len(missing_ids)} stale={stale_count}"
        ),
    )

    records: list[dict] = []
    total_missing = len(missing_ids)
    for index, image_id in enumerate(missing_ids):
        record = get_image_by_id(catalog_conn, image_id)
        if record:
            records.append(record)
        if progress is not None and total_missing:
            pct = 5 + int(90 * (index + 1) / total_missing)
            progress(pct, f"Fetching catalog metadata {index + 1}/{total_missing}")

    added = 0
    if records:
        added = store_images_batch(lib_db, records)

    catalog_conn.close()

    if progress is not None:
        progress(100, "Catalog sync complete")

    _log(
        "info",
        (
            f"[catalog-sync] complete added={added} stale={stale_count} "
            f"locking_mode={locking_mode}"
        ),
    )

    return CatalogSyncResult(
        added=added,
        stale=stale_count,
        locking_mode=locking_mode,
        catalog_total=len(catalog_ids),
        library_total=len(library_ids),
        missing_ids_count=len(missing_ids),
    )
