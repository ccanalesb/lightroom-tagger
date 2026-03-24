#!/usr/bin/env python3
"""Match Instagram dump media against catalog images using cascade filtering."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lightroom_tagger.core.database import (
    init_database,
    init_instagram_dump_table,
    init_catalog_table,
    get_unprocessed_dump_media,
    mark_dump_media_processed,
    update_instagram_status,
    get_instagram_by_date_filter,
)
from lightroom_tagger.core.matcher import find_candidates_by_date, score_candidates_with_vision
from lightroom_tagger.core.analyzer import compute_phash
from lightroom_tagger.core.path_utils import resolve_catalog_path


def match_dump_media(db, threshold: float = 0.7, batch_size: int = None,
                     month: str = None, year: str = None, last_months: int = None) -> dict:
    """Match Instagram dump media against catalog images using cascade filtering.

    Args:
        db: TinyDB instance
        threshold: Minimum score threshold for match (default 0.7)
        batch_size: Maximum number of unprocessed media to process (None = all)
        month: Filter Instagram by month (e.g., '202603')
        year: Filter Instagram by year (e.g., '2026')
        last_months: Filter Instagram by last N months

    Returns:
        Dict with 'processed', 'matched', 'skipped' counts
    """
    stats = {
        'processed': 0,
        'matched': 0,
        'skipped': 0,
    }

    init_instagram_dump_table(db)
    init_catalog_table(db)

    # Use date filtering if specified
    if month or year or last_months:
        unprocessed = get_instagram_by_date_filter(db, month=month, year=year, last_months=last_months)
        unprocessed = [u for u in unprocessed if not u.get('processed')]
    else:
        unprocessed = get_unprocessed_dump_media(db, limit=batch_size)

    if not unprocessed:
        return stats

    for dump_media in unprocessed:
        stats['processed'] += 1

        # Find candidates within 90-day window before posting
        candidates = find_candidates_by_date(db, dump_media, days_before=90)

        if not candidates:
            mark_dump_media_processed(db, dump_media['media_key'])
            stats['skipped'] += 1
            continue

        dump_image = {
            'key': dump_media['media_key'],
            'local_path': dump_media.get('file_path'),
            'image_hash': None,
            'description': dump_media.get('caption', ''),
        }

        # Compute phash if possible
        if dump_image['local_path'] and os.path.exists(dump_image['local_path']):
            try:
                phash = compute_phash(dump_image['local_path'])
                dump_image['image_hash'] = phash
            except:
                pass

    # Prepare candidates for vision comparison
    vision_candidates = []
    for catalog_img in candidates:
        # Resolve catalog path for WSL/Windows compatibility
        catalog_path = resolve_catalog_path(catalog_img.get('filepath', ''))
        candidate = {
            'key': catalog_img.get('key'),
            'local_path': catalog_path,
            'image_hash': catalog_img.get('phash'),
            'description': catalog_img.get('description', ''),
        }
        vision_candidates.append(candidate)

        results = score_candidates_with_vision(
            db, dump_image, vision_candidates,
            phash_weight=0.4, desc_weight=0.3, vision_weight=0.3
        )

        if results and results[0]['total_score'] >= threshold:
            best_match = results[0]
            matched_catalog_key = best_match['catalog_key']

            mark_dump_media_processed(
                db, dump_media['media_key'],
                matched_catalog_key=matched_catalog_key,
                vision_result=best_match.get('vision_result'),
                vision_score=best_match.get('vision_score')
            )

            update_instagram_status(db, matched_catalog_key, posted=True)

            stats['matched'] += 1
        else:
            mark_dump_media_processed(db, dump_media['media_key'])
            stats['skipped'] += 1

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Match Instagram dump media to catalog')
    parser.add_argument('--db', default='library.db', help='Database path')
    parser.add_argument('--threshold', type=float, default=0.7,
                        help='Minimum score threshold for match')
    parser.add_argument('--batch-size', type=int, default=None,
                        help='Maximum number of unprocessed media to process')
    parser.add_argument('--month', help='Filter by month (e.g., 202603)')
    parser.add_argument('--year', help='Filter by year (e.g., 2026)')
    parser.add_argument('--last-months', type=int, help='Filter by last N months')
    parser.add_argument('--reprocess', action='store_true',
                        help='Re-process already processed media')

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database not found: {args.db}")
        sys.exit(1)

    db = init_database(args.db)

    try:
        stats = match_dump_media(
            db,
            threshold=args.threshold,
            batch_size=args.batch_size,
            month=args.month,
            year=args.year,
            last_months=args.last_months
        )

        print(f"\nProcessed: {stats['processed']}")
        print(f"Matched: {stats['matched']}")
        print(f"Skipped: {stats['skipped']}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
