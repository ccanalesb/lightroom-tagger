"""Path resolution utilities for cross-platform file access."""
import os


def normalize_match_filesystem_path(local_path: str | None, mount_point: str) -> str | None:
    """Normalize catalog/dump path for batch matching: UNC, mount join, existence.

    Mirrors the batch-path prelude formerly inlined in score_candidates_with_vision:
    Windows UNC ``//server/share/...`` becomes ``/Volumes/share/...``, relative
    paths join ``mount_point``, then the path must exist on disk.

    Returns the resolved path when it exists, otherwise ``None``.
    """
    if not local_path:
        return None

    # Convert Windows UNC paths to Unix mount points
    # e.g., //NAS/ccanales/... -> /Volumes/ccanales/...
    if local_path.startswith('//'):
        parts = local_path[2:].split('/', 2)  # Skip // and split into [server, share, rest]
        if len(parts) >= 3:
            # For //NAS/ccanales/..., we want /Volumes/ccanales/...
            local_path = f'/Volumes/{parts[1]}/{parts[2]}'

    # Resolve path with mount_point if needed (for relative paths)
    elif not os.path.isabs(local_path):
        local_path = os.path.join(mount_point, local_path)

    if not local_path or not os.path.exists(local_path):
        return None
    return local_path


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
