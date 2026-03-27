#!/usr/bin/env python3
"""Match Instagram dump media against catalog images using cascade filtering."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lightroom_tagger.core.analyzer import compute_phash
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.description_service import describe_matched_image
from lightroom_tagger.core.database import (
    get_instagram_by_date_filter,
    get_unprocessed_dump_media,
    init_catalog_table,
    init_database,
    init_instagram_dump_table,
    mark_dump_media_attempted,
    mark_dump_media_processed,
    update_instagram_status,
)
from lightroom_tagger.core.matcher import find_candidates_by_date, score_candidates_with_vision
from lightroom_tagger.core.path_utils import resolve_catalog_path


def match_dump_media(db, threshold: float = 0.7, batch_size: int = None,
                     month: str = None, year: str = None, last_months: int = None,
                     progress_callback=None, log_callback=None,
                     weights: dict = None, force_descriptions: bool = False) -> tuple:
    """Match Instagram dump media against catalog images using cascade filtering.

    Args:
        db: sqlite3 connection
        threshold: Minimum score threshold for match (default 0.7)
        batch_size: Maximum number of unprocessed media to process (None = all)
        month: Filter Instagram by month (e.g., '202603')
        year: Filter Instagram by year (e.g., '2026')
        last_months: Filter Instagram by last N months
        progress_callback: Optional callback(current, total, message) for progress updates
        log_callback: Optional callback(level, message) for detailed logging
        weights: Optional dict with 'phash', 'description', 'vision' keys for scoring weights
        force_descriptions: If True, regenerate descriptions even when one exists

    Returns:
        Tuple of (stats dict, matches list)
    """
    from datetime import datetime

    default_weights = {'phash': 0.4, 'description': 0.3, 'vision': 0.3}
    weights = weights or default_weights
    run_start = datetime.now().isoformat()
    stats = {
        'processed': 0,
        'matched': 0,
        'skipped': 0,
        'descriptions_generated': 0,
    }
    matches_found = []

    init_instagram_dump_table(db)
    init_catalog_table(db)

    if month or year or last_months:
        unprocessed = get_instagram_by_date_filter(
            db, month=month, year=year, last_months=last_months, run_start=run_start)
    else:
        unprocessed = get_unprocessed_dump_media(db, limit=batch_size, run_start=run_start)

    total = len(unprocessed)
    if not unprocessed:
        return stats, matches_found

    for idx, dump_media in enumerate(unprocessed, 1):
        stats['processed'] += 1

        candidates = find_candidates_by_date(db, dump_media, days_before=90)

        if not candidates:
            mark_dump_media_attempted(db, dump_media['media_key'])
            stats['skipped'] += 1
            continue

        dump_image = {
            'key': dump_media['media_key'],
            'local_path': dump_media.get('file_path'),
            'image_hash': None,
            'description': dump_media.get('caption', ''),
        }

        if dump_image['local_path'] and os.path.exists(dump_image['local_path']):
            try:
                phash = compute_phash(dump_image['local_path'])
                dump_image['image_hash'] = phash
            except Exception:
                pass

        vision_candidates = []
        for catalog_img in candidates:
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
            phash_weight=weights.get('phash', 0.4),
            desc_weight=weights.get('description', 0.3),
            vision_weight=weights.get('vision', 0.3),
            log_callback=log_callback
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
            matches_found.append(best_match)
            try:
                if describe_matched_image(db, matched_catalog_key, force=force_descriptions):
                    stats['descriptions_generated'] += 1
            except Exception as e:
                if log_callback:
                    log_callback('warning', f'Description failed for {matched_catalog_key}: {e}')
        else:
            best = results[0] if results else None
            mark_dump_media_attempted(
                db, dump_media['media_key'],
                vision_result=best.get('vision_result') if best else None,
                vision_score=best.get('vision_score') if best else None,
            )
            stats['skipped'] += 1

        if progress_callback:
            progress_callback(idx, total, f'Processing {dump_media["media_key"]} ({idx}/{total})')

    return stats, matches_found


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
    parser.add_argument('--no-lightroom', action='store_true',
                        help='Skip Lightroom keyword update')

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database not found: {args.db}")
        sys.exit(1)

    db = init_database(args.db)

    try:
        stats, matches = match_dump_media(
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

        # Update Lightroom with "Posted" keyword
        if matches and not args.no_lightroom:
            config = load_config()
            catalog_path = config.catalog_path or config.small_catalog_path
            if catalog_path and os.path.exists(catalog_path):
                from lightroom_tagger.lightroom.writer import update_lightroom_from_matches
                lr_stats = update_lightroom_from_matches(catalog_path, matches)
                print(f"\nLightroom updated: {lr_stats['success']} images tagged with 'Posted'")
                if lr_stats['failed']:
                    print(f"Failed to update: {lr_stats['failed']} images")
            else:
                print(f"\nWarning: Lightroom catalog not found at {catalog_path}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
