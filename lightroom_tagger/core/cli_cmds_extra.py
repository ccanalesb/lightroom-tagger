"""Heavyweight CLI subcommands split out to keep :mod:`cli` under the size budget."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from lightroom_tagger.core.database import (
    get_all_images,
    init_database,
    search_by_keyword,
    search_by_rating,
)
from lightroom_tagger.core.database import get_image_count as db_get_image_count


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
