"""Lightroom catalog write availability for keyword mutations."""

from __future__ import annotations

import os
from dataclasses import dataclass

from lightroom_tagger.core.config import load_config
from lightroom_tagger.lightroom.writer import (
    CULL_KEYWORD,
    KeywordAddResult,
    KeywordRemoveResult,
    add_keyword_by_key,
    backup_catalog_if_needed,
    connect_catalog,
    image_has_keyword_by_key,
    raise_if_catalog_locked,
    remove_keyword_by_key,
)


@dataclass(frozen=True)
class LrCatalogWriteStatus:
    available: bool
    path: str | None
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "path": self.path,
            "reason": self.reason,
        }


def describe_lr_catalog_write_status() -> LrCatalogWriteStatus:
    """Report whether the configured Lightroom catalog can accept keyword writes."""
    cfg = load_config()
    path = (cfg.catalog_path or "").strip()
    if not path:
        return LrCatalogWriteStatus(
            available=False,
            path=None,
            reason="No Lightroom catalog configured.",
        )
    if not os.path.isfile(path):
        return LrCatalogWriteStatus(
            available=False,
            path=path,
            reason="Lightroom catalog file not found.",
        )
    try:
        raise_if_catalog_locked(path)
    except RuntimeError as exc:
        return LrCatalogWriteStatus(available=False, path=path, reason=str(exc))
    return LrCatalogWriteStatus(available=True, path=path, reason=None)


def read_cull_keyword_present(image_key: str) -> bool | None:
    """Return whether ``lrt-cull`` is on the image, or None when catalog unavailable."""
    status = describe_lr_catalog_write_status()
    if not status.available or not status.path:
        return None
    conn = connect_catalog(status.path)
    try:
        return image_has_keyword_by_key(conn, image_key, CULL_KEYWORD)
    finally:
        conn.close()


def write_cull_keyword(image_key: str) -> KeywordAddResult:
    status = describe_lr_catalog_write_status()
    if not status.available or not status.path:
        raise RuntimeError(status.reason or "Lightroom catalog unavailable.")
    raise_if_catalog_locked(status.path)
    backup_catalog_if_needed(status.path)
    conn = connect_catalog(status.path)
    try:
        return add_keyword_by_key(conn, image_key, CULL_KEYWORD)
    finally:
        conn.close()


def remove_cull_keyword(image_key: str) -> KeywordRemoveResult:
    status = describe_lr_catalog_write_status()
    if not status.available or not status.path:
        raise RuntimeError(status.reason or "Lightroom catalog unavailable.")
    raise_if_catalog_locked(status.path)
    backup_catalog_if_needed(status.path)
    conn = connect_catalog(status.path)
    try:
        return remove_keyword_by_key(conn, image_key, CULL_KEYWORD)
    finally:
        conn.close()
