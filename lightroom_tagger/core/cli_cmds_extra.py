"""Heavyweight CLI subcommands split out to keep :mod:`cli` under the size budget."""

from __future__ import annotations

import csv
import json

from lightroom_tagger.core.cli_library_db import with_library_db
from lightroom_tagger.core.database import (
    get_all_images,
    search_by_keyword,
    search_by_rating,
)
from lightroom_tagger.core.database import get_image_count as db_get_image_count


@with_library_db(must_exist=True)
def cmd_export(args, config, db):
    """Export to JSON/CSV."""
    results = get_all_images(db)

    if args.keyword:
        results = search_by_keyword(db, args.keyword)
    elif args.rating is not None:
        results = search_by_rating(db, args.rating)

    if args.limit:
        results = results[:args.limit]

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


@with_library_db(must_exist=False)
def cmd_init(args, config, db):
    """Initialize database."""
    db_path = args.db or config.db_path
    print(f"Initialized database at {db_path}")
    return 0


@with_library_db(must_exist=True)
def cmd_enrich_catalog(args, config, db):
    """Enrich catalog images or warm the vision cache."""
    from lightroom_tagger.core.vision_cache import warm_vision_cache
    from lightroom_tagger.lightroom.enricher import enrich_catalog_images

    if args.cache_only:
        result = warm_vision_cache(db, limit=args.limit)
    else:
        catalog_path = args.catalog or config.catalog_path
        result = enrich_catalog_images(db, catalog_path, limit=args.limit)

    print(f"Processed: {result['processed']}")
    print(f"Skipped: {result['skipped']}")
    print(f"Errors: {result['errors']}")
    return 0


@with_library_db(must_exist=True)
def cmd_stats(args, config, db):
    """Show database statistics."""
    db_path = args.db or config.db_path
    count = db_get_image_count(db)

    ratings = {}
    for record in db.execute("SELECT * FROM images").fetchall():
        rating = record.get("rating", 0)
        ratings[rating] = ratings.get(rating, 0) + 1

    print(f"Database: {db_path}")
    print(f"Total images: {count}")
    print("Ratings breakdown:")
    for rating in sorted(ratings.keys()):
        print(f"  {rating} star: {ratings[rating]}")

    return 0
