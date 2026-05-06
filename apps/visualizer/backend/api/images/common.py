"""Cross-cutting helpers for images API routes (D-08)."""

from __future__ import annotations

import os

from utils.pagination import _clamp_pagination


def _canonical_path(path: str) -> str | None:
    if not path or not str(path).strip():
        return None
    try:
        return os.path.realpath(os.path.expanduser(str(path).strip()))
    except OSError:
        return None


def _parent_dir_if_exists(path: str) -> str | None:
    base = _canonical_path(path)
    if not base:
        return None
    parent = os.path.dirname(base)
    if parent and os.path.isdir(parent):
        return parent
    return None


def _is_path_under_allowed_roots(file_path: str, roots: list[str]) -> bool:
    if not file_path or not roots:
        return False
    try:
        real_file = os.path.realpath(file_path)
    except OSError:
        return False
    for root in roots:
        if not root:
            continue
        if real_file == root:
            return True
        prefix = root + os.sep
        if real_file.startswith(prefix):
            return True
    return False


def _instagram_thumbnail_roots() -> list[str]:
    from lightroom_tagger.core.config import load_config

    cfg = load_config()
    dump = (cfg.instagram_dump_path or "").strip()
    if not dump:
        return []
    root = _canonical_path(dump)
    if root and os.path.isdir(root):
        return [root]
    return []


def _catalog_thumbnail_roots() -> list[str]:
    from lightroom_tagger.core.config import load_config

    cfg = load_config()
    roots: list[str] = []
    vc = _canonical_path(cfg.vision_cache_dir)
    if vc:
        roots.append(vc)
    mp = (cfg.mount_point or "").strip()
    if mp:
        mp_real = _canonical_path(mp)
        if mp_real and os.path.isdir(mp_real):
            roots.append(mp_real)
    for p in (cfg.catalog_path, cfg.small_catalog_path):
        par = _parent_dir_if_exists(p)
        if par and par not in roots:
            roots.append(par)
    seen: set[str] = set()
    out: list[str] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _extract_source_folder(file_path):
    """Extract source folder (posts, archived_posts) from file path."""
    if "/media/" in file_path:
        parts = file_path.split("/media/")
        if len(parts) > 1:
            subpath = parts[1].split("/")
            if len(subpath) > 0:
                return subpath[0]
    return "unknown"


def _filter_by_date(images, date_folder, date_from, date_to):
    """Filter images by date parameters."""
    if date_folder:
        return [img for img in images if img["instagram_folder"] == date_folder]

    if date_from:
        images = [
            img
            for img in images
            if img["instagram_folder"] and img["instagram_folder"] >= date_from
        ]
    if date_to:
        images = [
            img for img in images if img["instagram_folder"] and img["instagram_folder"] <= date_to
        ]

    return images


__all__ = (
    "_catalog_thumbnail_roots",
    "_clamp_pagination",
    "_canonical_path",
    "_extract_source_folder",
    "_filter_by_date",
    "_instagram_thumbnail_roots",
    "_is_path_under_allowed_roots",
    "_parent_dir_if_exists",
)
