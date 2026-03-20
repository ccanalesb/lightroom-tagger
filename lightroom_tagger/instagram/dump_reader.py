"""Instagram dump reader - discovers and parses Instagram data dump files."""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


def discover_media_files(dump_path: str) -> List[Dict]:
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

            if date_folder:
                filename_without_ext = file_path.stem
                media_key = f"{date_folder}/{filename_without_ext}"

                media_files.append({
                    'media_key': media_key,
                    'file_path': str(file_path),
                    'relative_path': str(rel_path),
                    'filename': file_path.name,
                    'date_folder': date_folder,
                })

    return sorted(media_files, key=lambda x: x['media_key'])


def parse_posts_metadata(dump_path: str) -> Dict[str, Dict]:
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
        with open(posts_json, 'r', encoding='utf-8') as f:
            posts = json.load(f)
    except (json.JSONDecodeError, IOError):
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

                if date_folder and parts:
                    filename = parts[-1]
                    filename_without_ext = filename.split('.')[0]
                    media_key = f"{date_folder}/{filename_without_ext}"

                    # Convert timestamp to ISO format
                    creation_ts = media.get('creation_timestamp') or post_timestamp
                    created_at = None
                    if creation_ts:
                        try:
                            created_at = datetime.fromtimestamp(creation_ts).isoformat()
                        except (ValueError, OSError):
                            pass

                    # Use media title if available, otherwise post title
                    caption = media.get('title', '') or post_caption

                    metadata[media_key] = {
                        'caption': caption,
                        'created_at': created_at,
                        'creation_timestamp': creation_ts,
                    }

    return metadata
