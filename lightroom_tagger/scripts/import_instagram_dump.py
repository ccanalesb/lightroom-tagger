#!/usr/bin/env python3
"""Import Instagram dump media into database with EXIF and URL extraction."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lightroom_tagger.core.database import (
    get_instagram_dump_media,
    init_database,
    init_instagram_dump_table,
    store_instagram_dump_media,
)
from lightroom_tagger.instagram.deduplicator import (
    compute_image_hashes,
    group_by_hash,
    select_best_versions,
)
from lightroom_tagger.instagram.dump_reader import (
    discover_media_files,
    parse_archived_posts_metadata,
    parse_other_content_metadata,
    parse_posts_metadata,
    parse_saved_and_reposted_urls,
)


def combine_metadata(posts_meta, archived_meta, other_meta):
    """Combine metadata from all JSON sources (aggregative)."""
    combined = {}

    # Start with posts metadata
    for key, data in posts_meta.items():
        combined[key] = data.copy()

    # Merge archived posts (has best EXIF data)
    for key, data in archived_meta.items():
        if key in combined:
            # Merge: EXIF from archived takes precedence
            combined[key].update(data)
        else:
            combined[key] = data.copy()

    # Merge other content (minimal data)
    for key, data in other_meta.items():
        if key in combined:
            combined[key].update(data)
        else:
            combined[key] = data.copy()

    return combined


def import_dump(db, dump_path: str, skip_existing: bool = True, skip_dedup: bool = False) -> int:
    """Import all media files from Instagram dump into database with enhanced metadata.

    Prioritizes posts over archived_posts - if same media exists in both, use posts version
    but merge archived metadata (which has better EXIF data).

    Args:
        db: sqlite3 connection
        dump_path: Path to instagram-dump directory
        skip_existing: If True, skip files already in database
        skip_dedup: If True, skip visual duplicate detection

    Returns:
        Number of new media files imported
    """
    # Ensure table exists
    init_instagram_dump_table(db)

    # Step 1: Discover all media files from filesystem
    print("Step 1: Discovering media files...")
    media_files = discover_media_files(dump_path)
    print(f"  Found {len(media_files)} media files")

    # Step 2: Visual deduplication
    print("\nStep 2: Computing image hashes for visual duplicate detection...")
    if skip_dedup:
        print("  Skipping (--skip-dedup flag set)")
        deduplicated_media = media_files
    else:
        media_with_hashes = compute_image_hashes(media_files)
        hash_groups = group_by_hash(media_with_hashes)
        print(f"  Found {len(hash_groups)} unique visual hashes")

        print("  Selecting best versions and merging EXIF data...")
        deduplicated_media = select_best_versions(hash_groups)
        duplicates_removed = len(media_files) - len(deduplicated_media)
        print(f"  After deduplication: {len(deduplicated_media)} unique images")
        print(f"  (Removed {duplicates_removed} visual duplicates)")

    # Step 3: Parse metadata from all JSON sources
    print("\nStep 3: Parsing JSON metadata...")
    posts_metadata = parse_posts_metadata(dump_path)
    print(f"  posts_1.json: {len(posts_metadata)} items")

    archived_metadata = parse_archived_posts_metadata(dump_path)
    print(f"  archived_posts.json: {len(archived_metadata)} items")

    other_metadata = parse_other_content_metadata(dump_path)
    print(f"  other_content.json: {len(other_metadata)} items")

    # Combine metadata (aggregative)
    combined_metadata = combine_metadata(posts_metadata, archived_metadata, other_metadata)
    print(f"  Combined unique metadata: {len(combined_metadata)} items")

    # Step 4: Extract URLs from saved/reposted content
    print("\nStep 4: Extracting Instagram URLs...")
    url_lookup = parse_saved_and_reposted_urls(dump_path)
    print(f"  Found {len(url_lookup)} URLs")

    # Step 5: Import media
    print("\nStep 5: Importing media...")
    imported = 0
    skipped = 0
    with_exif = 0
    with_urls = 0

    for media in deduplicated_media:
        media_key = media['media_key']

        # Check if already exists
        if skip_existing:
            existing = get_instagram_dump_media(db, media_key)
            if existing:
                skipped += 1
                continue

        # Build base record from filesystem
        record = {
            'media_key': media_key,
            'file_path': media['file_path'],
            'filename': media['filename'],
            'date_folder': media['date_folder'],
            'image_hash': media.get('image_hash'),  # Store the visual hash
        }

        # Add metadata from JSON if available
        meta = combined_metadata.get(media_key, {})
        if meta:
            record.update(meta)
            if meta.get('exif_data'):
                with_exif += 1

        # Match URL by timestamp
        creation_ts = record.get('creation_timestamp')
        if creation_ts and creation_ts in url_lookup:
            record['post_url'] = url_lookup[creation_ts]
            with_urls += 1

        # Store
        store_instagram_dump_media(db, record)
        imported += 1

        if imported % 500 == 0:
            print(f"  Imported {imported}...")

    print("\n✓ Import complete!")
    print(f"  Imported: {imported} new media files")
    print(f"  Skipped: {skipped} existing files")
    print(f"  With EXIF data: {with_exif}")
    print(f"  With URLs: {with_urls}")

    return imported


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import Instagram dump with EXIF extraction')
    parser.add_argument('--db', default='library.db', help='Database path')
    parser.add_argument('--dump-path', default=os.environ.get('INSTAGRAM_DUMP_PATH', '/home/cristian/instagram-dump'),
                        help='Path to Instagram dump directory')
    parser.add_argument('--reimport', action='store_true',
                        help='Re-import all files (ignore existing)')
    parser.add_argument('--skip-dedup', action='store_true',
                        help='Skip visual duplicate detection')

    args = parser.parse_args()

    if not os.path.exists(args.dump_path):
        print(f"Error: Dump path not found: {args.dump_path}")
        print("Set INSTAGRAM_DUMP_PATH environment variable or use --dump-path")
        sys.exit(1)

    db = init_database(args.db)

    try:
        count = import_dump(db, args.dump_path, skip_existing=not args.reimport, skip_dedup=args.skip_dedup)
        print(f"\n✓ Import complete: {count} files imported")
    finally:
        db.close()


if __name__ == '__main__':
    main()
