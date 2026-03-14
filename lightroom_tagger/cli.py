import argparse
import json
import csv
import sys
from pathlib import Path

from lightroom_tagger.config import load_config
from lightroom_tagger.catalog_reader import connect_catalog, get_image_records, get_image_count
from lightroom_tagger.database import (
    init_database,
    store_images_batch,
    get_image_count as db_get_image_count,
    search_by_keyword,
    search_by_rating,
    search_by_date,
    search_by_color_label,
    get_all_images,
)


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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
