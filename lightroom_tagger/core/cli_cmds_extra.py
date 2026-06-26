"""Heavyweight CLI subcommands split out to keep :mod:`cli` under the size budget."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from lightroom_tagger.core.database import (
    batch_update_hashes,
    get_all_images,
    get_images_without_hash,
    init_database,
    search_by_color_label,
    search_by_date,
    search_by_keyword,
    search_by_rating,
    update_instagram_status,
)
from lightroom_tagger.core.database import get_image_count as db_get_image_count
from lightroom_tagger.core.hasher import compute_phash
from lightroom_tagger.core.phash import find_matches
from lightroom_tagger.instagram.scraper import crawl_instagram
from lightroom_tagger.lightroom.reader import connect_catalog
from lightroom_tagger.lightroom.writer import add_keyword_to_images_batch


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

            import time

            while True:
                time.sleep(2)
                result = subprocess.run(
                    ["agent-browser", "--session-name", "instagram", "snapshot"],
                    capture_output=True,
                    text=True,
                    timeout=5,
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

            posts, url_to_path = crawl_instagram_browser(
                username, output_dir, limit or 50, session_name="instagram"
            )
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
        get_all_images(db)

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
                    url=match['insta_url'],
                )

        print(f"  Updated {len(matched_keys)} records in database")

        if catalog_path and Path(catalog_path).exists():
            print(f"\nStep 5: Adding keyword '{keyword}' to Lightroom...")
            result = add_keyword_to_images_batch(
                connect_catalog(catalog_path),
                matched_keys,
                keyword,
                dry_run=dry_run,
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
