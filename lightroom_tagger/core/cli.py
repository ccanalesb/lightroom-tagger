import argparse
import sys
from pathlib import Path

from lightroom_tagger.core.config import Config, load_config
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


def _build_parser(commands) -> argparse.ArgumentParser:
    """Build argument parser with global options and registered subcommands."""
    parser = argparse.ArgumentParser(
        prog="lightroom-tagger",
        description="Read Lightroom catalog, index metadata, store in SQLite",
        exit_on_error=False,
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
        type=int,
        default=4,
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

    for command in commands:
        subparser = subparsers.add_parser(command.name, help=command.help)
        command.add_arguments(subparser)

    return parser


def _apply_global_overrides(args, config) -> None:
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


def _has_subcommand(argv, commands) -> bool:
    names = {command.name for command in commands}
    for arg in argv:
        if not arg.startswith("-") and arg in names:
            return True
    return False


def run(argv, config, commands) -> int:
    """Parse argv, apply global overrides, and dispatch via the command registry."""
    parser = _build_parser(commands)
    try:
        args = parser.parse_args(argv)
    except argparse.ArgumentError:
        parser.print_help()
        return 1

    if not args.command:
        parser.print_help()
        return 1

    _apply_global_overrides(args, config)

    handlers = {command.name: command.handler for command in commands}
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args, config)


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


def main():
    """Main entry point."""
    from lightroom_tagger.core.cli_commands import COMMANDS

    argv = sys.argv[1:]
    if not _has_subcommand(argv, COMMANDS):
        return run(argv, Config(), COMMANDS)

    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", default="config.yaml")
    pre_args, _ = pre_parser.parse_known_args(argv)

    try:
        config = load_config(pre_args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1

    return run(argv, config, COMMANDS)


if __name__ == "__main__":
    sys.exit(main())
