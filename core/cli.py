import argparse
import json
import csv
import sys
import subprocess
import os
from pathlib import Path

from lightroom_tagger.core.config import load_config
from lightroom_tagger.lightroom.reader import connect_catalog, get_image_records, get_image_count
from lightroom_tagger.core.database import (
    init_database,
    store_images_batch,
    get_image_count as db_get_image_count,
    search_by_keyword,
    search_by_rating,
    search_by_date,
    search_by_color_label,
    get_all_images,
    update_instagram_status,
    get_images_without_hash,
    batch_update_hashes,
)
from lightroom_tagger.instagram.scraper import crawl_instagram
from lightroom_tagger.core.hasher import compute_phash
from lightroom_tagger.core.phash import find_matches
from lightroom_tagger.lightroom.writer import add_keyword_to_images_batch


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="lightroom-tagger",
        description="Read Lightroom catalog, index metadata, store in TinyDB"
    )

    parser.add_argument(
        "--catalog", "-c",
        help="Path to .lrcat file"
    )
    parser.add_argument(
        "--db", "-d",
        help="Path to TinyDB"
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
        help="Path to TinyDB (overrides global)"
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
        help="Path to TinyDB (overrides global)"
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
        help="Path to TinyDB (overrides global)"
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
        help="Path to TinyDB (overrides global)"
    )

    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.add_argument(
        "--db",
        help="Path to TinyDB (overrides global)"
    )

    instagram_parser = subparsers.add_parser("instagram-sync", help="Sync Instagram posts")
    instagram_parser.add_argument(
        "--db",
        help="Path to TinyDB (overrides global)"
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
    instagram_parser.add_argument(
        "--browser",
        action="store_true",
        help="Use browser-based scraping (agent-browser) instead of API"
    )
    instagram_parser.add_argument(
        "--login",
        action="store_true",
        help="Open browser for manual Instagram login (use with --browser)"
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
        elif output_format == "csv":
            if results:
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
        for record in db.all():
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


def cmd_instagram_sync(args, config):
    """Sync Instagram posts with local catalog."""
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
    use_browser = args.browser
    do_login = args.login

    print(f"Instagram URL: {instagram_url}")
    print(f"Keyword: {keyword}")
    print(f"Hash threshold: {threshold}")
    print(f"Catalog: {catalog_path}")
    print(f"Dry run: {dry_run}")
    print(f"Browser mode: {use_browser}")
    print()

    if use_browser:
        from lightroom_tagger.instagram.browser import BrowserAgent
        
        if do_login:
            print("Opening headed browser for Instagram login...")
            print("(A browser window will appear)")
            print("1. Log in to your Instagram account")
            print("2. Close the browser window when done")
            print("The system will wait for the browser to close...")
            agent = BrowserAgent(output_dir, headed=True, session_name="instagram")
            agent.login(instagram_url)
            
            # Wait for browser to be closed by user
            import time
            while True:
                time.sleep(2)
                # Check if browser process is still running by trying a simple command
                result = subprocess.run(
                    ["agent-browser", "--session-name", "instagram", "snapshot"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode != 0:
                    break
            
            print("Browser closed. Verifying session...")
            agent2 = BrowserAgent(output_dir, session_name="instagram")
            if agent2.is_logged_in():
                agent2.close()
                print("Login successful! Session saved.")
            else:
                agent2.close()
                print("Login failed or cancelled. Please try again with --login")
            return 0

        # Check session validity before scraping
        print("Checking session validity...")
        agent = BrowserAgent(output_dir, session_name="instagram")
        if not agent.is_logged_in():
            agent.close()
            print("Not logged in to Instagram.")
            print("Run with --login to authenticate: lightroom-tagger instagram-sync --browser --login")
            return 1
        agent.close()
        print("Session valid. Proceeding with scraping...")

        username = instagram_url.split('/')[-2] if '/' in instagram_url else instagram_url
        print("Using browser-based scraping...")
        
        try:
            from lightroom_tagger.instagram.browser import crawl_instagram_browser
            posts, url_to_path = crawl_instagram_browser(username, output_dir, limit or 50, session_name="instagram")
        except Exception as e:
            print(f"Browser scraping failed: {e}")
            print("Try running with --login first to authenticate")
            return 1
    else:
        print("Using API-based scraping...")
        posts, url_to_path = crawl_instagram(config, output_dir, limit=limit or 50)

    try:
        db = init_database(db_path)
        
        print("Step 1: Computing hashes for local images...")
        local_images = get_all_images(db)
        
        images_needing_hash = get_images_without_hash(db)
        print(f"  {len(images_needing_hash)} images need hashes")
        
        # Load config to resolve NAS paths
        from lightroom_tagger.core.config import load_config
        config = load_config()
        
        hash_updates = []
        for record in images_needing_hash:
            filepath = record.get('filepath')
            if filepath:
                # Resolve NAS path (e.g., //tnas/... -> /mnt/tnas/...)
                resolved_path = config._resolve_path(filepath)
                if resolved_path and Path(resolved_path).exists():
                    image_hash = compute_phash(resolved_path)
                    if image_hash:
                        hash_updates.append({'key': record['key'], 'image_hash': image_hash})
        
        if hash_updates:
            batch_update_hashes(db, hash_updates)
            print(f"  Computed {len(hash_updates)} hashes")
        
        local_images = get_all_images(db)
        local_with_hash = [img for img in local_images if img.get('image_hash')]
        print(f"  Total images with hash: {len(local_with_hash)}")
        
        print("\nStep 2: Crawling Instagram...")
        
        if not posts:
            print("No Instagram posts found!")
            return 1
        
        insta_images = []
        for i, post in enumerate(posts):
            local_paths = url_to_path.get(post.post_url)
            if local_paths:
                for local_path in local_paths:
                    if os.path.exists(local_path):
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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
