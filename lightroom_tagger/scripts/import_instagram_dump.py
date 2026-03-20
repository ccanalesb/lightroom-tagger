#!/usr/bin/env python3
"""Import Instagram dump media into database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lightroom_tagger.core.database import (
    init_database,
    init_instagram_dump_table,
    store_instagram_dump_media,
    get_instagram_dump_media,
)
from lightroom_tagger.instagram.dump_reader import (
    discover_media_files,
    parse_posts_metadata,
)


def import_dump(db, dump_path: str, skip_existing: bool = True) -> int:
    """Import all media files from Instagram dump into database.
    
    Args:
        db: TinyDB instance
        dump_path: Path to instagram-dump directory
        skip_existing: If True, skip files already in database
    
    Returns:
        Number of new media files imported
    """
    # Ensure table exists
    init_instagram_dump_table(db)
    
    # Discover all media files
    media_files = discover_media_files(dump_path)
    print(f"Found {len(media_files)} media files in dump")
    
    # Parse metadata from JSON
    metadata = parse_posts_metadata(dump_path)
    print(f"Parsed metadata for {len(metadata)} files from JSON")
    
    imported = 0
    skipped = 0
    
    for media in media_files:
        media_key = media['media_key']
        
        # Check if already exists
        if skip_existing:
            existing = get_instagram_dump_media(db, media_key)
            if existing:
                skipped += 1
                continue
        
        # Build record
        record = {
            'media_key': media_key,
            'file_path': media['file_path'],
            'filename': media['filename'],
            'date_folder': media['date_folder'],
        }
        
        # Add metadata if available
        meta = metadata.get(media_key, {})
        if meta.get('caption'):
            record['caption'] = meta['caption']
        if meta.get('created_at'):
            record['created_at'] = meta['created_at']
        
        # Store
        store_instagram_dump_media(db, record)
        imported += 1
    
    print(f"Imported {imported} new media files")
    if skipped > 0:
        print(f"Skipped {skipped} existing files")
    
    return imported


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Import Instagram dump into database')
    parser.add_argument('--db', default='library.db', help='Database path')
    parser.add_argument('--dump-path', default=os.environ.get('INSTAGRAM_DUMP_PATH', '/home/cristian/instagram-dump'),
                        help='Path to Instagram dump directory')
    parser.add_argument('--reimport', action='store_true', 
                        help='Re-import all files (ignore existing)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.dump_path):
        print(f"Error: Dump path not found: {args.dump_path}")
        print("Set INSTAGRAM_DUMP_PATH environment variable or use --dump-path")
        sys.exit(1)
    
    db = init_database(args.db)
    
    try:
        count = import_dump(db, args.dump_path, skip_existing=not args.reimport)
        print(f"\n✓ Import complete: {count} files imported")
    finally:
        db.close()


if __name__ == '__main__':
    main()