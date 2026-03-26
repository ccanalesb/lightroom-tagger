"""Instagram dump reader - discovers and parses Instagram data dump files."""
import contextlib
import json
from datetime import datetime
from pathlib import Path


def discover_media_files(dump_path: str) -> list[dict]:
    """Discover all media files in Instagram dump directory.

    Args:
        dump_path: Root path to instagram-dump directory

    Returns:
        List of dicts with media_key, file_path, relative_path
    """
    media_files = []
    media_dir = Path(dump_path) / 'media'

    if not media_dir.exists():
        return media_files

    # Supported image extensions
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    video_exts = {'.mp4', '.mov', '.avi', '.mkv'}
    supported_exts = image_exts | video_exts

    for file_path in media_dir.rglob('*'):
        if not file_path.is_file():
            continue

        # Skip Zone.Identifier files and other metadata
        if ':Zone.Identifier' in file_path.name:
            continue

        # Skip stories, reels, and other - they are not relevant for catalog matching
        path_str = str(file_path)
        rel_parts = list(file_path.relative_to(media_dir).parts)
        if '/stories/' in path_str or rel_parts[0] == 'stories':
            continue
        if '/reels/' in path_str or rel_parts[0] == 'reels':
            continue
        if '/other/' in path_str or rel_parts[0] == 'other':
            continue

        # Check extension
        ext = file_path.suffix.lower()
        if ext not in supported_exts:
            continue

        # Calculate relative path from media directory
        try:
            rel_path = file_path.relative_to(media_dir)
        except ValueError:
            continue

        # Extract date folder and filename for key
        # Path like: posts/202603/17940060624158613.jpg
        # Key: 202603/17940060624158613
        parts = list(rel_path.parts)
        if len(parts) >= 2:
            # Assume structure: [subfolder]/YYYYMM/filename.jpg
            # or just: YYYYMM/filename.jpg
            date_folder = None
            for part in parts[:-1]:
                if len(part) == 6 and part.isdigit():
                    date_folder = part
                    break

            filename_without_ext = file_path.stem

            if date_folder:
                # Standard case: posts/202603/17940060624158613.jpg
                media_key = f"{date_folder}/{filename_without_ext}"
            else:
                # No date folder: media/other/17980178165618670.jpg
                # Use folder/filename: other/17980178165618670
                folder = parts[0] if parts else 'unknown'
                media_key = f"{folder}/{filename_without_ext}"

            media_files.append({
                'media_key': media_key,
                'file_path': str(file_path),
                'relative_path': str(rel_path),
                'filename': file_path.name,
                'date_folder': date_folder,
            })

    return sorted(media_files, key=lambda x: x['media_key'])


def parse_posts_metadata(dump_path: str) -> dict[str, dict]:
    """Parse posts_1.json to extract metadata for each media file.

    Args:
        dump_path: Root path to instagram-dump directory

    Returns:
        Dict mapping media_key -> metadata (caption, timestamp)
    """
    metadata = {}

    # Possible locations for posts JSON
    json_paths = [
        Path(dump_path) / 'your_instagram_activity' / 'media' / 'posts_1.json',
        Path(dump_path) / 'media' / 'posts_1.json',
    ]

    posts_json = None
    for path in json_paths:
        if path.exists():
            posts_json = path
            break

    if not posts_json:
        return metadata

    try:
        with open(posts_json, encoding='utf-8') as f:
            posts = json.load(f)
    except (OSError, json.JSONDecodeError):
        return metadata

    for post in posts:
        # Post-level data
        post_caption = post.get('title', '')
        post_timestamp = post.get('creation_timestamp')

        # Process each media in the post
        for media in post.get('media', []):
            uri = media.get('uri', '')
            if not uri:
                continue

        # Extract media_key from URI
        # URI: media/posts/202603/17940060624158613.jpg
        # Key: 202603/17940060624158613
        parts = uri.replace('\\', '/').split('/')
        if len(parts) >= 2:
            # Find date folder (6 digits)
            date_folder = None
            for part in parts:
                if len(part) == 6 and part.isdigit():
                    date_folder = part
                    break

        if parts:
            filename = parts[-1]
            filename_without_ext = filename.split('.')[0]
            if date_folder:
                media_key = f"{date_folder}/{filename_without_ext}"
            else:
                # For URIs like media/other/17980178165618670.jpg (no date folder)
                # Use the folder name and filename: other/17980178165618670
                folder = parts[-2] if len(parts) >= 2 else 'unknown'
                media_key = f"{folder}/{filename_without_ext}"

            # Convert timestamp to ISO format
            creation_ts = media.get('creation_timestamp') or post_timestamp
            created_at = None
            if creation_ts:
                with contextlib.suppress(ValueError, OSError):
                    created_at = datetime.fromtimestamp(creation_ts).isoformat()

            # Use media title if available, otherwise post title
            caption = media.get('title', '') or post_caption

            # Get EXIF data if present
            exif_data = {}
            media_metadata = media.get('media_metadata', {})
            if 'photo_metadata' in media_metadata:
                exif_list = media_metadata['photo_metadata'].get('exif_data', [])
                if exif_list:
                    exif_data = exif_list[0]

            # Build record with EXIF fields
            record = {
                'caption': caption,
                'created_at': created_at,
                'creation_timestamp': creation_ts,
                'exif_data': exif_data if exif_data else None,
            }

            # Extract specific EXIF fields if available
            if exif_data:
                record['exif_date_time_original'] = exif_data.get('date_time_original')
                record['exif_latitude'] = exif_data.get('latitude')
                record['exif_longitude'] = exif_data.get('longitude')
                record['exif_device_id'] = exif_data.get('device_id')
                record['exif_lens_model'] = exif_data.get('lens_model')
                record['exif_iso'] = exif_data.get('iso')
                record['exif_aperture'] = exif_data.get('aperture')
                record['exif_shutter_speed'] = exif_data.get('shutter_speed')
                record['exif_focal_length'] = exif_data.get('focal_length')
                record['exif_lens_make'] = exif_data.get('lens_make')

            metadata[media_key] = record

    return metadata


def _extract_media_key_from_uri(uri: str) -> str | None:
    """Extract media_key from URI like media/posts/202603/17940060624158613.jpg."""
    parts = uri.replace('\\', '/').split('/')
    if len(parts) >= 2:
        # Find date folder (6 digits)
        date_folder = None
        for part in parts:
            if len(part) == 6 and part.isdigit():
                date_folder = part
                break

        if date_folder and parts:
            filename = parts[-1]
            filename_without_ext = filename.split('.')[0]
            return f"{date_folder}/{filename_without_ext}"
    return None


def parse_archived_posts_metadata(dump_path: str) -> dict[str, dict]:
    """Parse archived_posts.json to extract EXIF-rich metadata.

    Args:
        dump_path: Root path to instagram-dump directory

    Returns:
        Dict mapping media_key -> metadata with EXIF data
    """
    metadata = {}

    json_path = Path(dump_path) / 'your_instagram_activity' / 'media' / 'archived_posts.json'
    if not json_path.exists():
        return metadata

    try:
        with open(json_path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return metadata

    archived_posts = data.get('ig_archived_post_media', [])

    for post in archived_posts:
        post_caption = post.get('title', '')
        post_timestamp = post.get('creation_timestamp')

        for media in post.get('media', []):
            uri = media.get('uri', '')
            if not uri:
                continue

            media_key = _extract_media_key_from_uri(uri)
            if not media_key:
                continue

            exif_data = {}
            media_metadata = media.get('media_metadata', {})
            if 'photo_metadata' in media_metadata:
                exif_list = media_metadata['photo_metadata'].get('exif_data', [])
                if exif_list:
                    exif_data = exif_list[0]

            creation_ts = media.get('creation_timestamp') or post_timestamp
            created_at = None
            if creation_ts:
                with contextlib.suppress(ValueError, OSError):
                    created_at = datetime.fromtimestamp(creation_ts).isoformat()

            caption = media.get('title', '') or post_caption

            record = {
                'caption': caption,
                'created_at': created_at,
                'creation_timestamp': creation_ts,
                'exif_data': exif_data if exif_data else None,
            }

            if exif_data:
                record['exif_date_time_original'] = exif_data.get('date_time_original')
                record['exif_latitude'] = exif_data.get('latitude')
                record['exif_longitude'] = exif_data.get('longitude')
                record['exif_device_id'] = exif_data.get('device_id')
                record['exif_lens_model'] = exif_data.get('lens_model')
                record['exif_iso'] = exif_data.get('iso')
                record['exif_aperture'] = exif_data.get('aperture')
                record['exif_shutter_speed'] = exif_data.get('shutter_speed')
                record['exif_focal_length'] = exif_data.get('focal_length')
                record['exif_lens_make'] = exif_data.get('lens_make')

            metadata[media_key] = record

    return metadata


def parse_other_content_metadata(dump_path: str) -> dict[str, dict]:
    """Parse other_content.json to extract metadata.

    Args:
        dump_path: Root path to instagram-dump directory

    Returns:
        Dict mapping media_key -> metadata (minimal, no EXIF)
    """
    metadata = {}

    json_path = Path(dump_path) / 'your_instagram_activity' / 'media' / 'other_content.json'
    if not json_path.exists():
        return metadata

    try:
        with open(json_path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return metadata

    other_posts = data.get('ig_other_media', [])

    for post in other_posts:
        post_caption = post.get('title', '')
        post_timestamp = post.get('creation_timestamp')

        for media in post.get('media', []):
            uri = media.get('uri', '')
            if not uri:
                continue

            media_key = _extract_media_key_from_uri(uri)
            if not media_key:
                continue

            creation_ts = media.get('creation_timestamp') or post_timestamp
            created_at = None
            if creation_ts:
                with contextlib.suppress(ValueError, OSError):
                    created_at = datetime.fromtimestamp(creation_ts).isoformat()

            caption = media.get('title', '') or post_caption

            metadata[media_key] = {
                'caption': caption,
                'created_at': created_at,
                'creation_timestamp': creation_ts,
                'exif_data': None,
            }

    return metadata


def parse_saved_and_reposted_urls(dump_path: str) -> dict[int, str]:
    """Parse saved_posts.json and reposts.json to extract Instagram URLs.

    Matches by creation_timestamp to link URLs to dump media.

    Args:
        dump_path: Root path to instagram-dump directory

    Returns:
        Dict mapping creation_timestamp -> Instagram URL
    """
    url_lookup = {}

    saved_path = Path(dump_path) / 'your_instagram_activity' / 'saved' / 'saved_posts.json'
    if saved_path.exists():
        try:
            with open(saved_path, encoding='utf-8') as f:
                data = json.load(f)

            saved_media = data.get('saved_saved_media', [])
            for item in saved_media:
                string_map = item.get('string_map_data', {})
                saved_on = string_map.get('Saved on', {})

                url = saved_on.get('href', '')
                timestamp = saved_on.get('timestamp')

                if url and timestamp:
                    url_lookup[timestamp] = url
        except (OSError, json.JSONDecodeError):
            pass

    reposts_path = Path(dump_path) / 'your_instagram_activity' / 'media' / 'reposts.json'
    if reposts_path.exists():
        try:
            with open(reposts_path, encoding='utf-8') as f:
                reposts = json.load(f)

            for repost in reposts:
                timestamp = repost.get('timestamp')
                label_values = repost.get('label_values', [])

                if len(label_values) >= 3:
                    media_section = label_values[2]
                    if 'dict' in media_section and len(media_section['dict']) > 0:
                        first_dict = media_section['dict'][0]
                        if 'dict' in first_dict and len(first_dict['dict']) > 0:
                            url_entry = first_dict['dict'][0]
                            url = url_entry.get('href', '')

                            if url and timestamp:
                                url_lookup[timestamp] = url
        except (OSError, json.JSONDecodeError):
            pass

    return url_lookup
