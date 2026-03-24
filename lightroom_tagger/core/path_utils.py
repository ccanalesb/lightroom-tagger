"""Path resolution utilities for cross-platform file access."""
import os


def resolve_catalog_path(filepath: str) -> str:
    """Resolve catalog path across UNC, WSL, and common mount styles.

    Converts Windows UNC paths to WSL/Linux paths for cross-platform access.
    Supports common NAS mounting patterns in WSL (/mnt/, /Volumes/, /media/).

    Returns original path if it already exists.
    Returns empty string if path cannot be resolved.
    """
    if not filepath:
        return ""

    if os.path.exists(filepath):
        return filepath

    normalized = filepath.replace("\\", "/")
    if not normalized.startswith("//"):
        return ""

    # UNC style: //server/share/path/to/file
    parts = [p for p in normalized.split("/") if p]
    if len(parts) < 3:
        return ""

    server, share = parts[0], parts[1]
    rest = "/".join(parts[2:])

    # Special case: tnas has share in the path, not as mount point
    # //tnas/ccanales/Lightroom Server/... -> /mnt/tnas/Lightroom Server/...
    if server == "tnas":
        candidates = [
            f"/mnt/tnas/{rest}",  # WSL mount of tnas directly
            f"/mnt/{share}/{rest}",
        ]
    else:
        candidates = [
            f"/mnt/{share}/{rest}",
            f"/Volumes/{share}/{rest}",
            f"/media/{share}/{rest}",
        ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return ""
