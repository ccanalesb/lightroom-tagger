#!/usr/bin/env python3
"""Match Instagram dump with cascade filtering."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lightroom_tagger.core.database import init_database, get_instagram_by_date_filter
from lightroom_tagger.core.matcher import find_candidates_by_date, score_candidates_with_vision

def match_with_cascade(db, month=None, year=None, last_months=None, threshold=0.7):
    """Run cascade matching with date filtering."""
    stats = {'processed': 0, 'matched': 0}
    matches_found = []

    unprocessed = get_instagram_by_date_filter(db, month=month, year=year,
                                               last_months=last_months)
    unprocessed = [u for u in unprocessed if not u.get('processed')]

    for dump_media in unprocessed:
        stats['processed'] += 1
        candidates = find_candidates_by_date(db, dump_media)

        if candidates:
            dump_image = {
                'key': dump_media['media_key'],
                'local_path': dump_media.get('file_path'),
                'image_hash': dump_media.get('image_hash'),
                'description': dump_media.get('caption', ''),
            }

            vision_candidates = [{
                'key': c['key'],
                'local_path': c.get('filepath'),
                'image_hash': c.get('phash'),
                'description': '',
            } for c in candidates]

            results = score_candidates_with_vision(
                db, dump_image, vision_candidates,
                phash_weight=0.0, desc_weight=0.0, vision_weight=1.0
            )

            if results and results[0]['total_score'] >= threshold:
                stats['matched'] += 1
                matches_found.append(results[0])

    return stats, matches_found

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='library.db')
    parser.add_argument('--month')
    parser.add_argument('--year')
    parser.add_argument('--last-months', type=int)
    args = parser.parse_args()

    db = init_database(args.db)
    stats, matches = match_with_cascade(db, month=args.month, year=args.year,
                                       last_months=args.last_months)
    print(f"Processed: {stats['processed']}, Matched: {stats['matched']}")
    db.close()
