"""Path resolution utilities for cross-platform file access."""
import os


def resolve_catalog_path(filepath: str) -> str:
    """Resolve catalog path across UNC, WSL, and common mount styles.

    Delegates to core.database.resolve_filepath for UNC path resolution,
    which auto-detects macOS SMB mounts under /Volumes/.

    Returns original path if it already exists.
    Returns empty string if path cannot be resolved.
    """
    if not filepath:
        return ""

    if os.path.exists(filepath):
        return filepath

    from lightroom_tagger.core.database import resolve_filepath
    resolved = resolve_filepath(filepath)
    if resolved != filepath and os.path.exists(resolved):
        return resolved

    return ""
