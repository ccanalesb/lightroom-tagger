import argparse
import csv
import json
import sys
from pathlib import Path

from lightroom_tagger.catalog_reader import connect_catalog, get_image_count, get_image_records
from lightroom_tagger.core.analyzer import analyze_image
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import (
    get_catalog_images_needing_analysis,
    init_catalog_table,
    store_catalog_image,
)
from lightroom_tagger.core.vision_cache import get_or_create_cached_image
from lightroom_tagger.database import (
    batch_update_hashes,
    get_all_images,
    get_images_without_hash,
    init_database,
    search_by_color_label,
    search_by_date,
    search_by_keyword,
    search_by_rating,
    store_images_batch,
    update_instagram_status,
)
from lightroom_tagger.database import (
    get_image_count as db_get_image_count,
)
from lightroom_tagger.image_hasher import compute_phash, find_matches
from lightroom_tagger.instagram_scraper import crawl_instagram
from lightroom_tagger.lr_writer import add_keyword_to_images_batch


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="lightroom-tagger",
        description="Read Lightroom catalog, index metadata, store in SQLite"
    )

    parser.add_argument(
        "--catalog", "-c",
        help="Path to .lrcat file"
    )
    parser.add_argument(
        "--db", "-d",
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int, default=4,
        help="Parallel workers (default: 4)"
    )
    parser.add_argument(
        "--ai-model",
        help="AI model for classification"
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip AI classification"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit results"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    scan_parser = subparsers.add_parser("scan", help="Scan catalog, index all images")
    scan_parser.add_argument(
        "--catalog",
        help="Path to .lrcat file (overrides global)"
    )
    scan_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )
    scan_parser.add_argument(
        "--workers",
        type=int,
        help="Parallel workers"
    )
    scan_parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of images to process"
    )

    search_parser = subparsers.add_parser("search", help="Search indexed images")
    search_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )
    search_parser.add_argument(
        "--keyword",
        help="Search by keyword"
    )
    search_parser.add_argument(
        "--rating",
        type=int,
        help="Minimum rating (0-5)"
    )
    search_parser.add_argument(
        "--color-label",
        help="Filter by color label"
    )
    search_parser.add_argument(
        "--date-start",
        help="Start date (ISO format)"
    )
    search_parser.add_argument(
        "--date-end",
        help="End date (ISO format)"
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        help="Limit results"
    )

    export_parser = subparsers.add_parser("export", help="Export to JSON/CSV")
    export_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )
    export_parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output file path"
    )
    export_parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Export format (default: json)"
    )
    export_parser.add_argument(
        "--keyword",
        help="Export only images matching keyword"
    )
    export_parser.add_argument(
        "--rating",
        type=int,
        help="Export only images with minimum rating"
    )
    export_parser.add_argument(
        "--limit",
        type=int,
        help="Limit results"
    )

    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )

    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )

    instagram_parser = subparsers.add_parser("instagram-sync", help="Sync Instagram posts")
    instagram_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )
    instagram_parser.add_argument(
        "--catalog",
        help="Lightroom catalog path for writing keywords"
    )
    instagram_parser.add_argument(
        "--instagram-url",
        help="Instagram profile URL"
    )
    instagram_parser.add_argument(
        "--keyword",
        help="Keyword to add to posted images"
    )
    instagram_parser.add_argument(
        "--hash-threshold",
        type=int,
        default=5,
        help="Hash similarity threshold (0-32, default 5)"
    )
    instagram_parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of Instagram posts to check"
    )
    instagram_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying"
    )
    instagram_parser.add_argument(
        "--output-dir",
        default="/tmp/instagram_images",
        help="Directory to download Instagram images"
    )

    enrich_parser = subparsers.add_parser("enrich-catalog", help="Enrich catalog with metadata")
    enrich_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)"
    )
    enrich_parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of images to process"
    )
    enrich_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed"
    )
    enrich_parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Only update vision cache (incremental, preserves existing cache)"
    )

    return parser


def cmd_scan(args, config):
    """Scan catalog and index images."""
    catalog_path = args.catalog or config.catalog_path
    db_path = args.db or config.db_path
    workers = args.workers or config.workers

    if not catalog_path:
        print("Error: No catalog path provided. Use --catalog or config.yaml")
        return 1

    if not Path(catalog_path).exists():
        print(f"Error: Catalog not found: {catalog_path}")
        return 1

    print(f"Scanning catalog: {catalog_path}")

    try:
        conn = connect_catalog(catalog_path)
        total_in_catalog = get_image_count(conn)

        if args.verbose:
            print(f"Total images in catalog: {total_in_catalog}")

        limit = args.limit
        records = get_image_records(conn, limit=limit, workers=workers)
        conn.close()

        print(f"Retrieved {len(records)} image records")

        db = init_database(db_path)
        count = store_images_batch(db, records)
        db.close()

        print(f"Indexed {count} images to {db_path}")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_search(args, config):
    """Search indexed images."""
    db_path = args.db or config.db_path

    if not db_path:
        print("Error: No database path provided. Use --db or config.yaml")
        return 1

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        return 1

    try:
        db = init_database(db_path)
        results = []

        if args.keyword:
            results = search_by_keyword(db, args.keyword)
        elif args.rating is not None:
            results = search_by_rating(db, args.rating)
        elif args.color_label:
            results = search_by_color_label(db, args.color_label)
        elif args.date_start:
            results = search_by_date(db, args.date_start, args.date_end)
        else:
            results = get_all_images(db)

        if args.limit:
            results = results[:args.limit]

        db.close()

        print(f"Found {len(results)} images")
        for record in results:
            print(f"  {record.get('key')}: {record.get('filename')} (rating: {record.get('rating')})")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_export(args, config):
    """Export to JSON/CSV."""
    db_path = args.db or config.db_path

    if not db_path:
        print("Error: No database path provided. Use --db or config.yaml")
        return 1

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        return 1

    try:
        db = init_database(db_path)
        results = get_all_images(db)

        if args.keyword:
            results = search_by_keyword(db, args.keyword)
        elif args.rating is not None:
            results = search_by_rating(db, args.rating)

        if args.limit:
            results = results[:args.limit]

        db.close()

        output_path = args.output
        output_format = args.format

        if output_format == "json":
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)
        elif output_format == "csv" and results:
            fieldnames = list(results[0].keys())
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

        print(f"Exported {len(results)} images to {output_path}")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_init(args, config):
    """Initialize database."""
    db_path = args.db or config.db_path

    if not db_path:
        print("Error: No database path provided. Use --db or config.yaml")
        return 1

    try:
        db = init_database(db_path)
        db.close()
        print(f"Initialized database at {db_path}")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_stats(args, config):
    """Show database statistics."""
    db_path = args.db or config.db_path

    if not db_path:
        print("Error: No database path provided. Use --db or config.yaml")
        return 1

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        return 1

    try:
        db = init_database(db_path)
        count = db_get_image_count(db)

        ratings = {}
        for record in db.execute("SELECT * FROM images").fetchall():
            rating = record.get("rating", 0)
            ratings[rating] = ratings.get(rating, 0) + 1

        db.close()

        print(f"Database: {db_path}")
        print(f"Total images: {count}")
        print("Ratings breakdown:")
        for rating in sorted(ratings.keys()):
            print(f"  {rating} star: {ratings[rating]}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def enrich_catalog_images(db, limit=None, verbose=False, cache_only=False):
    """Enrich catalog images with metadata and vision cache.

    Args:
        db: sqlite3 connection
        limit: Maximum number of images to process
        verbose: Print progress for every image
        cache_only: Only process images missing from vision cache (incremental update)

    Returns:
        dict with processed, skipped, errors counts
    """
    from lightroom_tagger.core.config import load_config
    from lightroom_tagger.core.database import (
        get_all_images,
        get_catalog_images_missing_cache,
        init_vision_cache_table,
        init_vision_comparisons_table,
    )

    config = load_config()
    processed = 0
    skipped = 0
    errors = 0

    init_catalog_table(db)
    init_vision_comparisons_table(db)
    init_vision_cache_table(db)

    if cache_only:
        print("Running incremental cache update (cache-only mode)...")
    else:
        print("Enriching catalog images...")

    try:
        if cache_only:
            # Only get images missing from vision cache
            catalog_images = get_catalog_images_missing_cache(db)
        else:
            # Get images needing full analysis
            catalog_images = get_catalog_images_needing_analysis(db)

            if not catalog_images:
                print("Catalog table empty, getting from main images table...")
                all_images = get_all_images(db)
                catalog_images = [img for img in all_images if not img.get('analyzed_at')]

        print(f"Found {len(catalog_images)} images to {'cache' if cache_only else 'enrich'}")

        for i, record in enumerate(catalog_images):
            if limit and i >= limit:
                break

            try:
                key = record.get('key')
                filepath = record.get('filepath')

                if not key or not filepath:
                    print(f"Skipping record with missing key/filepath: {record}")
                    skipped += 1
                    continue

                if cache_only:
                    # Cache-only mode: just create compressed image cache
                    if config.vision_cache_enabled:
                        from lightroom_tagger.core.path_utils import resolve_catalog_path
                        resolved_path = resolve_catalog_path(filepath)
                        if resolved_path:
                            get_or_create_cached_image(db, key, resolved_path)
                            processed += 1
                        else:
                            print(f"Skipping {key}: file not found at {filepath}")
                            skipped += 1
                    else:
                        print("Vision cache is disabled in config, nothing to do")
                        break
                else:
                    # Full enrichment mode: analyze and cache
                    analysis = analyze_image(filepath)

                    enriched_record = {
                        'key': key,
                        'filepath': filepath,
                        'analyzed_at': analysis.get('analyzed_at', 'unknown'),
                        'phash': analysis.get('phash'),
                        'exif': analysis.get('exif', {}),
                        'catalog_path': record.get('catalog_path', ''),
                        'date_taken': record.get('date_taken', ''),
                        'filename': record.get('filename', ''),
                        'rating': record.get('rating', 0),
                        'keywords': record.get('keywords', []),
                        'color_label': record.get('color_label', ''),
                        'title': record.get('title', ''),
                        'description': analysis.get('description', record.get('description', '')),
                    }

                    store_catalog_image(db, enriched_record)

                    if config.vision_cache_enabled:
                        get_or_create_cached_image(db, key, filepath)

                    processed += 1

                if verbose or (i + 1) % 10 == 0:
                    print(f"Processed {i + 1}/{len(catalog_images)}")

            except Exception as e:
                print(f"Error processing image {i + 1}: {e}")
                errors += 1

        action = "Cache update" if cache_only else "Enrichment"
        print(f"{action} complete: {processed} processed, {skipped} skipped, {errors} errors")
        return {'processed': processed, 'skipped': skipped, 'errors': errors}

    except Exception as e:
        print(f"Error during enrichment: {e}")
        return {'processed': 0, 'skipped': 0, 'errors': 1}


def cmd_enrich_catalog(args, config):
    """Enrich catalog with metadata."""
    import os
    
    db_path = args.db or config.db_path
    limit = args.limit
    dry_run = args.dry_run
    cache_only = getattr(args, 'cache_only', False)
    verbose = getattr(args, 'verbose', False)

    # Set up NAS path resolution environment variables
    if config.mount_point:
        os.environ['NAS_MOUNT_POINT'] = config.mount_point
    if hasattr(config, 'catalog_path') and config.catalog_path:
        catalog_path = config.catalog_path
        if catalog_path.startswith('//'):
            parts = catalog_path.lstrip('/').split('/')
            if len(parts) >= 2:
                os.environ['NAS_PATH_PREFIX'] = f'//{parts[0]}/{parts[1]}'

    if dry_run:
        print("Dry run mode - will show what would be processed")

    try:
        db = init_database(db_path)
        result = enrich_catalog_images(db, limit=limit, verbose=verbose, cache_only=cache_only)
        db.close()

        print(f"Processed: {result['processed']} images")
        print(f"Skipped: {result['skipped']} images")
        print(f"Errors: {result['errors']} errors")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_instagram_sync(args, config):
    """Match local images to Instagram posts and optionally tag Lightroom."""
    db_path = args.db or config.db_path

    if not db_path:
        print("Error: No database path provided. Use --db or config.yaml")
        return 1

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        return 1

    instagram_url = args.instagram_url or config.instagram_url
    keyword = args.keyword or config.instagram_keyword
    threshold = args.hash_threshold or config.hash_threshold
    catalog_path = args.catalog or config.small_catalog_path
    output_dir = args.output_dir
    dry_run = args.dry_run
    limit = args.limit

    print(f"Instagram URL: {instagram_url}")
    print(f"Keyword: {keyword}")
    print(f"Hash threshold: {threshold}")
    print(f"Catalog: {catalog_path}")
    print(f"Dry run: {dry_run}")
    print()

    try:
        db = init_database(db_path)

        print("Step 1: Computing hashes for local images...")
        local_images = get_all_images(db)

        images_needing_hash = get_images_without_hash(db)
        print(f"  {len(images_needing_hash)} images need hashes")

        hash_updates = []
        for record in images_needing_hash:
            filepath = record.get('filepath')
            if filepath and Path(filepath).exists():
                image_hash = compute_phash(filepath)
                if image_hash:
                    hash_updates.append({'key': record['key'], 'image_hash': image_hash})

        if hash_updates:
            batch_update_hashes(db, hash_updates)
            print(f"  Computed {len(hash_updates)} hashes")

        local_images = get_all_images(db)
        local_with_hash = [img for img in local_images if img.get('image_hash')]
        print(f"  Total images with hash: {len(local_with_hash)}")

        print("\nStep 2: Crawling Instagram...")
        posts, url_to_path = crawl_instagram(config, output_dir, limit=limit or 50)

        if not posts:
            print("No Instagram posts found!")
            return 1

        insta_images = []
        for _i, post in enumerate(posts):
            local_path = url_to_path.get(post.image_url)
            if local_path:
                image_hash = compute_phash(local_path)
                insta_images.append({
                    'url': post.post_url,
                    'local_path': local_path,
                    'image_hash': image_hash,
                    'index': post.index,
                })

        print(f"  Found {len(insta_images)} Instagram images with hashes")

        print("\nStep 3: Finding matches...")
        matches = find_matches(local_with_hash, insta_images, threshold)
        print(f"  Found {len(matches)} matches")

        if not matches:
            print("\nNo matches found!")
            return 0

        print("\nMatches found:")
        for match in matches[:10]:
            print(f"  {match['local_key']} <-> {match['insta_url']} (distance: {match['hash_distance']})")
        if len(matches) > 10:
            print(f"  ... and {len(matches) - 10} more")

        print(f"\nStep 4: {'Preview' if dry_run else 'Applying'} changes...")

        matched_keys = [m['local_key'] for m in matches]

        for match in matches:
            if dry_run:
                print(f"  Would mark as posted: {match['local_key']}")
            else:
                update_instagram_status(
                    db,
                    match['local_key'],
                    posted=True,
                    url=match['insta_url']
                )

        print(f"  Updated {len(matched_keys)} records in database")

        if catalog_path and Path(catalog_path).exists():
            print(f"\nStep 5: Adding keyword '{keyword}' to Lightroom...")
            result = add_keyword_to_images_batch(
                connect_catalog(catalog_path),
                matched_keys,
                keyword,
                dry_run=dry_run
            )
            print(f"  Added: {result['added']}, Skipped: {result['skipped']}, Errors: {result['errors']}")

        db.close()

        print(f"\n{'Done!' if dry_run else 'Complete!'}")
        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        config = load_config(args.config)

        if args.catalog:
            config.catalog_path = args.catalog
        if args.db:
            config.db_path = args.db
        if args.workers:
            config.workers = args.workers
        if args.ai_model:
            config.ai_model = args.ai_model
        if args.skip_ai:
            config.skip_ai = args.skip_ai
        if args.verbose:
            config.verbose = args.verbose
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1

    if args.command == "scan":
        return cmd_scan(args, config)
    elif args.command == "search":
        return cmd_search(args, config)
    elif args.command == "export":
        return cmd_export(args, config)
    elif args.command == "init":
        return cmd_init(args, config)
    elif args.command == "stats":
        return cmd_stats(args, config)
    elif args.command == "instagram-sync":
        return cmd_instagram_sync(args, config)
    elif args.command == "enrich-catalog":
        return cmd_enrich_catalog(args, config)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
