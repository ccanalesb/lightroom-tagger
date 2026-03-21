"""Enhanced Instagram dump importer with EXIF and URL extraction."""
import argparse
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from lightroom_tagger.core.database import init_database, init_instagram_dump_table, store_instagram_dump_media
from lightroom_tagger.instagram.dump_reader import (
    discover_media_files,
    parse_posts_metadata,
    parse_archived_posts_metadata,
    parse_other_content_metadata,
    parse_saved_and_reposted_urls,
)


def combine_metadata(posts_meta, archived_meta, other_meta):
    """Combine metadata from all JSON sources (aggregative)."""
    combined = {}

    # Start with posts metadata
    for key, data in posts_meta.items():
        combined[key] = data.copy()

    # Merge archived posts (has EXIF data)
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


def import_dump(db_path: str, dump_path: str) -> int:
    """Import Instagram dump with enhanced metadata.

    Args:
        db_path: Path to database file
        dump_path: Path to Instagram dump directory

    Returns:
        Number of media imported
    """
    print(f"Importing from {dump_path}...")

    # Initialize database
    db = init_database(db_path)
    init_instagram_dump_table(db)

    # Step 1: Discover all media files from filesystem
    print("Discovering media files...")
    media_files = discover_media_files(dump_path)
    print(f"Found {len(media_files)} media files")

    # Step 2: Parse all JSON metadata
    print("Parsing JSON metadata...")
    posts_metadata = parse_posts_metadata(dump_path)
    print(f"  posts_1.json: {len(posts_metadata)} items")

    archived_metadata = parse_archived_posts_metadata(dump_path)
    print(f"  archived_posts.json: {len(archived_metadata)} items")

    other_metadata = parse_other_content_metadata(dump_path)
    print(f"  other_content.json: {len(other_metadata)} items")

    # Step 3: Combine metadata (aggregative)
    combined_metadata = combine_metadata(posts_metadata, archived_metadata, other_metadata)
    print(f"Combined unique metadata: {len(combined_metadata)} items")

    # Step 4: Extract URLs from saved/reposted
    print("Extracting Instagram URLs...")
    url_lookup = parse_saved_and_reposted_urls(dump_path)
    print(f"  Found {len(url_lookup)} URLs")

    # Step 5: Import all media
    imported_count = 0
    with_exif = 0
    with_urls = 0

    print("Importing media...")
    for media_file in media_files:
        key = media_file['media_key']

        # Base record from filesystem
        record = {
            'media_key': key,
            'file_path': media_file['file_path'],
            'filename': media_file['filename'],
            'date_folder': media_file['date_folder'],
        }

        # Add metadata from JSON if available
        if key in combined_metadata:
            meta = combined_metadata[key]
            record.update(meta)

        # Add URL if matched by timestamp
        creation_ts = record.get('creation_timestamp')
        if creation_ts and creation_ts in url_lookup:
            record['post_url'] = url_lookup[creation_ts]
            with_urls += 1

        # Track EXIF
        if record.get('exif_data'):
            with_exif += 1

        # Store in database
        store_instagram_dump_media(db, record)
        imported_count += 1

        if imported_count % 500 == 0:
            print(f"  Imported {imported_count}...")

    db.close()

    print(f"\nImport complete!")
    print(f"  Total imported: {imported_count}")
    print(f"  With EXIF data: {with_exif}")
    print(f"  With URLs: {with_urls}")

    return imported_count


def main():
    parser = argparse.ArgumentParser(description='Import Instagram dump with EXIF')
    parser.add_argument('--dump-path', required=True, help='Path to Instagram dump')
    parser.add_argument('--db', default='library.db', help='Database file path')

    args = parser.parse_args()

    import_dump(args.db, args.dump_path)


if __name__ == '__main__':
    main()
