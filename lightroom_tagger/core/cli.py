import argparse
import sys
from pathlib import Path

from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.database import (
    get_all_images,
    init_database,
    search_by_color_label,
    search_by_date,
    search_by_keyword,
    search_by_rating,
    store_images_batch,
)
from lightroom_tagger.core.catalog_sync import CatalogSyncError, sync_catalog
from lightroom_tagger.lightroom.reader import connect_catalog, get_image_count, get_image_records


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

    sync_parser = subparsers.add_parser(
        "sync",
        help="Incremental catalog sync — add missing images to library.db",
    )
    sync_parser.add_argument(
        "--catalog",
        help="Path to .lrcat file (overrides global)",
    )
    sync_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
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

    enrich_parser = subparsers.add_parser(
        "enrich-catalog",
        help="Enrich catalog images or pre-warm vision cache",
    )
    enrich_parser.add_argument(
        "--db",
        help="Path to SQLite database (overrides global)",
    )
    enrich_parser.add_argument(
        "--catalog",
        help="Path to .lrcat file (overrides global)",
    )
    enrich_parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of images to process",
    )
    enrich_parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Only pre-warm vision cache (skip full enrichment)",
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


def cmd_sync(args, config):
    """Incremental catalog sync — additions only."""
    catalog_path = args.catalog or config.catalog_path
    db_path = args.db or config.db_path

    if not catalog_path:
        print("Error: No catalog path provided. Use --catalog or config.yaml")
        return 1

    if not Path(catalog_path).exists():
        print(f"Error: Catalog not found: {catalog_path}")
        return 1

    if not db_path:
        print("Error: No database path provided. Use --db or config.yaml")
        return 1

    print(f"Syncing catalog: {catalog_path}")

    try:
        db = init_database(db_path)
        result = sync_catalog(catalog_path, db)
        db.close()
        print(
            f"Added {result.added} images; {result.stale} stale in library "
            f"(locking_mode={result.locking_mode})"
        )
        return 0
    except CatalogSyncError as e:
        print(f"Error: {e}")
        return 1
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


from lightroom_tagger.core.cli_cmds_extra import (
    cmd_enrich_catalog,
    cmd_export,
    cmd_init,
    cmd_stats,
)


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
    elif args.command == "sync":
        return cmd_sync(args, config)
    elif args.command == "search":
        return cmd_search(args, config)
    elif args.command == "export":
        return cmd_export(args, config)
    elif args.command == "init":
        return cmd_init(args, config)
    elif args.command == "stats":
        return cmd_stats(args, config)
    elif args.command == "enrich-catalog":
        return cmd_enrich_catalog(args, config)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
