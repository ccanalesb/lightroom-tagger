#!/usr/bin/env python3
"""Match Instagram dump media against catalog images using cascade filtering."""

import json
import logging
import os
import sys
from collections.abc import Callable

logger = logging.getLogger(__name__)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lightroom_tagger.core.analyzer import compute_phash
from lightroom_tagger.core.config import load_config
from lightroom_tagger.core.description_service import (
    describe_instagram_image,
    describe_matched_image,
)
from lightroom_tagger.core.analyzer import get_vision_model
from lightroom_tagger.core.database import (
    delete_matches_for_insta_key,
    get_image_description,
    get_instagram_by_date_filter,
    get_rejected_pairs,
    get_unprocessed_dump_media,
    init_catalog_table,
    init_database,
    init_instagram_dump_table,
    mark_dump_media_attempted,
    mark_dump_media_processed,
    store_image_description,
    store_match,
    update_instagram_status,
)
from lightroom_tagger.core.matcher import find_candidates_by_date, score_candidates_with_vision
from lightroom_tagger.core.provider_registry import ProviderRegistry
from lightroom_tagger.core.vision_client import generate_description
from lightroom_tagger.core.path_utils import resolve_catalog_path


def match_dump_media(db, threshold: float = 0.7, batch_size: int = None,
                     month: str = None, year: str = None, last_months: int = None,
                     progress_callback=None, log_callback=None,
                     weights: dict = None, media_key: str = None,
                     force_descriptions: bool = False,
                     force_reprocess: bool = False,
                     provider_id: str | None = None,
                     provider_model: str | None = None,
                     max_workers: int = 1,
                     skip_undescribed: bool = True,
                     *, should_cancel: Callable[[], bool] | None = None,
                     resume_processed_keys: set[str] | None = None,
                     on_media_complete: Callable[[str], None] | None = None,
                     batch_progress_callback: Callable[[int, int, int, int], None] | None = None) -> tuple:
    """Match Instagram dump media against catalog images using cascade filtering.

    Args:
        db: sqlite3 connection
        threshold: Minimum score threshold for match (default 0.7)
        batch_size: Maximum number of unprocessed media to process (None = all)
        month: Filter Instagram by month (e.g., '202603')
        year: Filter Instagram by year (e.g., '2026')
        last_months: Filter Instagram by last N months
        media_key: If set, process only this Instagram dump row (ignores batch/date filters)
        force_reprocess: If True, include already-processed images in the batch
        provider_id: Optional vision provider id (registry key); None uses defaults
        provider_model: Optional model id for that provider; None uses provider default
        progress_callback: Optional callback(current, total, message) for progress updates
        log_callback: Optional callback(level, message) for detailed logging
        weights: Optional dict with 'phash', 'description', 'vision' keys for scoring weights
        force_descriptions: If True, regenerate descriptions even when one exists
        skip_undescribed: If True, candidates without AI summaries get description score 0
            without inline describe; if False, missing summaries may be generated on the fly
        should_cancel: If set, called before each item; return True to stop early
        resume_processed_keys: If set, skip dump rows whose ``media_key`` is in this set
            (no stats increment for skipped rows).
        on_media_complete: If set, invoked once per media row after its iteration finishes.

    Returns:
        Tuple of (stats dict, matches list)
    """
    from datetime import datetime

    config = load_config()
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

    if media_key:
        row = db.execute(
            "SELECT * FROM instagram_dump_media WHERE media_key = ?",
            (media_key,),
        ).fetchone()
        if not row:
            return stats, matches_found
        unprocessed = [dict(row) if not isinstance(row, dict) else row]
    elif month or year or last_months:
        unprocessed = get_instagram_by_date_filter(
            db, month=month, year=year, last_months=last_months,
            run_start=run_start, include_processed=force_reprocess)
    else:
        unprocessed = get_unprocessed_dump_media(
            db, limit=batch_size, run_start=run_start,
            include_processed=force_reprocess)

    total = len(unprocessed)
    if log_callback:
        log_callback('info', f'Found {total} images to process (filters: month={month}, year={year}, last_months={last_months}, media_key={media_key})')
    if not unprocessed:
        if log_callback:
            log_callback('warning', 'No unprocessed images found matching filters')
        return stats, matches_found

    rejected = get_rejected_pairs(db)

    for idx, dump_media in enumerate(unprocessed, 1):
        if should_cancel is not None and should_cancel():
            if log_callback:
                log_callback('info', 'Matching stopped: cancel requested')
            return stats, matches_found
        media_key = dump_media['media_key']
        if resume_processed_keys is not None and media_key in resume_processed_keys:
            continue
        stats['processed'] += 1

        candidates = find_candidates_by_date(db, dump_media, days_before=90)
        initial_candidate_count = len(candidates)

        if rejected:
            candidates = [
                c for c in candidates
                if (c.get('key'), media_key) not in rejected
            ]

        if log_callback and idx <= 3:
            log_callback('debug', f'[{media_key}] Found {initial_candidate_count} candidates by date, {len(candidates)} after filters')

        if not candidates:
            mark_dump_media_attempted(db, dump_media['media_key'])
            stats['skipped'] += 1
            if log_callback and idx <= 3:
                log_callback('warning', f'[{media_key}] Skipped - no candidates found')
            continue

        dump_image = {
            'key': dump_media['media_key'],
            'local_path': dump_media.get('file_path'),
            'image_hash': None,
            'description': dump_media.get('caption', ''),
        }

        insta_desc_row = get_image_description(db, dump_media['media_key'])
        if insta_desc_row and (insta_desc_row.get('summary') or '').strip():
            dump_image['ai_summary'] = (insta_desc_row.get('summary') or '').strip()
        else:
            dump_image['ai_summary'] = ''

        if (
            not dump_image['ai_summary']
            and not skip_undescribed
            and dump_image.get('local_path')
            and os.path.exists(dump_image['local_path'])
        ):
            registry = ProviderRegistry()
            pid = provider_id or registry.fallback_order[0]
            client = registry.get_client(pid)
            model = provider_model or get_vision_model()
            raw = generate_description(
                client, model, dump_image['local_path'], log_callback=log_callback,
            )
            text = (raw or '').strip()
            summary = text
            if text.startswith('{') or text.startswith('['):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict) and parsed.get('summary'):
                        summary = str(parsed['summary'])
                except (json.JSONDecodeError, TypeError):
                    pass
            model_label = f'{pid}:{model}' if provider_id else model
            store_image_description(db, {
                'image_key': dump_media['media_key'],
                'image_type': 'instagram',
                'summary': summary,
                'composition': {},
                'perspectives': {},
                'technical': {},
                'subjects': [],
                'best_perspective': '',
                'model_used': model_label,
            })
            dump_image['ai_summary'] = summary

        if dump_image['local_path'] and os.path.exists(dump_image['local_path']):
            try:
                phash = compute_phash(dump_image['local_path'])
                dump_image['image_hash'] = phash
            except Exception:
                pass

        vision_candidates = []
        for catalog_img in candidates:
            catalog_path = resolve_catalog_path(catalog_img.get('filepath', ''))
            ai_summary = catalog_img.get('ai_summary', '')
            candidate = {
                'key': catalog_img.get('key'),
                'local_path': catalog_path,
                'image_hash': catalog_img.get('phash'),
                'description': catalog_img.get('description', ''),
                'ai_summary': ai_summary,
            }
            if (
                not (candidate.get('ai_summary') or '').strip()
                and not skip_undescribed
                and catalog_path
                and os.path.exists(catalog_path)
            ):
                registry = ProviderRegistry()
                pid = provider_id or registry.fallback_order[0]
                client = registry.get_client(pid)
                model = provider_model or get_vision_model()
                raw = generate_description(
                    client, model, catalog_path, log_callback=log_callback,
                )
                text = (raw or '').strip()
                summary = text
                if text.startswith('{') or text.startswith('['):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict) and parsed.get('summary'):
                            summary = str(parsed['summary'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                model_label = f'{pid}:{model}' if provider_id else model
                store_image_description(db, {
                    'image_key': catalog_img.get('key'),
                    'image_type': 'catalog',
                    'summary': summary,
                    'composition': {},
                    'perspectives': {},
                    'technical': {},
                    'subjects': [],
                    'best_perspective': '',
                    'model_used': model_label,
                })
                candidate['ai_summary'] = summary
            vision_candidates.append(candidate)

        def _make_batch_cb(item_idx, item_total):
            def _cb(chunk, num_chunks):
                if batch_progress_callback:
                    batch_progress_callback(item_idx, item_total, chunk, num_chunks)
            return _cb

        results = score_candidates_with_vision(
            db, dump_image, vision_candidates,
            phash_weight=weights.get('phash', 0.4),
            desc_weight=weights.get('description', 0.3),
            vision_weight=weights.get('vision', 0.3),
            threshold=threshold,
            log_callback=log_callback,
            provider_id=provider_id,
            model=provider_model,
            batch_size=config.vision_batch_size,
            batch_threshold=config.vision_batch_threshold,
            skip_undescribed=skip_undescribed,
            should_cancel=should_cancel,
            batch_progress_callback=_make_batch_cb(idx, total),
        )

        if should_cancel is not None and should_cancel():
            if log_callback:
                log_callback('info', 'Matching stopped: cancel requested')
            return stats, matches_found

        above_threshold = [r for r in results if r['total_score'] >= threshold]

        if above_threshold:
            best_match = above_threshold[0]
            matched_catalog_key = best_match['catalog_key']

            with db:
                delete_matches_for_insta_key(db, dump_media['media_key'], commit=False)
                for rank, candidate in enumerate(above_threshold, 1):
                    candidate['rank'] = rank
                    store_match(db, candidate, commit=False)

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
                if describe_instagram_image(db, dump_media['media_key'], force=force_descriptions):
                    stats['descriptions_generated'] += 1
            except Exception as e:
                msg = f'Description failed for {matched_catalog_key}: {e}'
                if log_callback:
                    log_callback('warning', msg)
                else:
                    logger.warning(msg)
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
        if on_media_complete is not None:
            on_media_complete(dump_media['media_key'])

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
            last_months=args.last_months,
            force_reprocess=args.reprocess,
        )

        print(f"\nProcessed: {stats['processed']}")
        print(f"Matched: {stats['matched']}")
        print(f"Skipped: {stats['skipped']}")

        # Update Lightroom with configured Instagram keyword
        if matches and not args.no_lightroom:
            config = load_config()
            catalog_path = config.catalog_path or config.small_catalog_path
            if catalog_path and os.path.exists(catalog_path):
                from lightroom_tagger.lightroom.writer import update_lightroom_from_matches
                lr_stats = update_lightroom_from_matches(catalog_path, matches)
                print(f"\nLightroom updated: {lr_stats['success']} images tagged with {config.instagram_keyword!r}")
                if lr_stats['failed']:
                    print(f"Failed to update: {lr_stats['failed']} images")
            else:
                print(f"\nWarning: Lightroom catalog not found at {catalog_path}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
