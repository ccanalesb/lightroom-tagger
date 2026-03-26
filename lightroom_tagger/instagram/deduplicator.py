"""Visual duplicate detection for Instagram dump media.

Uses perceptual hashing (pHash) to detect visually identical images,
allowing deduplication while preserving EXIF data from multiple sources.
"""

import os
from collections import defaultdict

from PIL import Image


def compute_image_hash(image_path: str) -> str | None:
    """Compute perceptual hash (pHash) for an image.

    Args:
        image_path: Path to image file

    Returns:
        Hex string hash or None if error
    """
    try:
        import imagehash
        img = Image.open(image_path)
        hash_val = imagehash.phash(img)
        img.close()
        return str(hash_val)
    except Exception:
        return None


def compute_image_hashes(media_files: list[dict]) -> list[dict]:
    """Compute pHash for all media files.

    Args:
        media_files: List of media file dicts with 'file_path' key

    Returns:
        List of media files with added 'image_hash' key
    """
    results = []
    total = len(media_files)

    print(f"Computing hashes for {total} images...")

    for i, media in enumerate(media_files):
        file_path = media.get('file_path', '')

        if os.path.exists(file_path):
            image_hash = compute_image_hash(file_path)
            if image_hash:
                media_with_hash = {**media, 'image_hash': image_hash}
                results.append(media_with_hash)
            else:
                # Include even if hash fails, but mark it
                media_with_hash = {**media, 'image_hash': None}
                results.append(media_with_hash)
        else:
            # File doesn't exist, skip
            media_with_hash = {**media, 'image_hash': None}
            results.append(media_with_hash)

        if (i + 1) % 100 == 0:
            print(f"  Hashed {i + 1}/{total}...")

    # Count successfully hashed
    hashed_count = sum(1 for m in results if m.get('image_hash'))
    print(f"✓ Hashed {hashed_count}/{total} images")

    return results


def group_by_hash(media_files_with_hashes: list[dict]) -> dict[str, list[dict]]:
    """Group media files by their image hash.

    Args:
        media_files_with_hashes: List of media with 'image_hash' key

    Returns:
        Dict mapping hash -> list of media files with that hash
    """
    groups = defaultdict(list)

    for media in media_files_with_hashes:
        hash_val = media.get('image_hash')
        if hash_val:
            groups[hash_val].append(media)
        else:
            # No hash - treat as unique
            groups[f"no_hash_{id(media)}"].append(media)

    return dict(groups)


def is_from_posts_folder(file_path: str) -> bool:
    """Check if file is from posts folder (higher priority)."""
    return '/posts/' in file_path or file_path.split('/media/')[-1].startswith('posts/')


def select_best_version(hash_group: list[dict]) -> dict:
    """Select the best version from a group of duplicates.

    Priority:
    1. Posts folder over archived_posts
    2. If multiple in same folder, pick first (or could use file size/modified date)

    Args:
        hash_group: List of media files with same hash

    Returns:
        Best media file dict
    """
    if len(hash_group) == 1:
        return hash_group[0]

    # Separate into posts and archived
    posts_versions = [m for m in hash_group if is_from_posts_folder(m.get('file_path', ''))]
    archived_versions = [m for m in hash_group if not is_from_posts_folder(m.get('file_path', ''))]

    # Prefer posts
    if posts_versions:
        return posts_versions[0]

    # Otherwise use first archived
    return archived_versions[0] if archived_versions else hash_group[0]


def merge_exif_data(best_version: dict, duplicates: list[dict]) -> dict:
    """Merge EXIF data from all duplicates into the best version.

    Takes EXIF from any duplicate that has it, preferring the best version's EXIF
    but filling in gaps from others.

    Args:
        best_version: The selected best media file
        duplicates: All media files with same hash (including best_version)

    Returns:
        Best version with merged EXIF data
    """
    # Start with best version's metadata
    merged = {**best_version}

    # Look for EXIF data in any duplicate
    for media in duplicates:
        exif = media.get('exif_data')
        if exif:
            # If best version doesn't have EXIF, use this one
            if not merged.get('exif_data'):
                merged['exif_data'] = exif

            # Also merge specific fields if missing
            for field in ['exif_date_time_original', 'exif_latitude', 'exif_longitude',
                         'exif_device_id', 'exif_lens_model', 'exif_iso',
                         'exif_aperture', 'exif_shutter_speed']:
                if not merged.get(field) and media.get(field):
                    merged[field] = media.get(field)

            break  # Found EXIF, no need to check others

    return merged


def select_best_versions(hash_groups: dict[str, list[dict]]) -> list[dict]:
    """Select best version from each hash group and merge EXIF.

    Args:
        hash_groups: Dict mapping hash -> list of duplicates

    Returns:
        List of unique media files (best version from each group)
    """
    results = []

    for _image_hash, group in hash_groups.items():
        best = select_best_version(group)
        best_with_exif = merge_exif_data(best, group)
        results.append(best_with_exif)

    return results


def deduplicate_media(media_files: list[dict]) -> list[dict]:
    """Main deduplication function.

    Takes list of media files, computes hashes, groups by hash,
    selects best version from each group, merges EXIF.

    Args:
        media_files: List of media file dicts with 'file_path' key

    Returns:
        List of deduplicated media files
    """
    # Compute hashes
    with_hashes = compute_image_hashes(media_files)

    # Group by hash
    groups = group_by_hash(with_hashes)

    print(f"Found {len(groups)} unique hashes from {len(media_files)} files")

    # Select best versions
    unique_media = select_best_versions(groups)

    print(f"After deduplication: {len(unique_media)} unique images")

    return unique_media
