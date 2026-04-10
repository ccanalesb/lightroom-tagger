#!/usr/bin/env python3
"""Direct test of match_dump_media to see what happens"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from lightroom_tagger.core.database import init_database
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media

def test():
    print("=== Testing match_dump_media directly ===\n")
    
    db = init_database("/Users/ccanales/projects/lightroom-tagger/library.db")
    
    def log_cb(level, msg):
        print(f"[{level}] {msg}")
    
    def progress_cb(current, total, msg):
        print(f"Progress: {current}/{total} - {msg}")
    
    print("Calling match_dump_media with last_months=3...")
    print("")
    
    stats, matches = match_dump_media(
        db,
        threshold=0.7,
        last_months=3,
        log_callback=log_cb,
        progress_callback=progress_cb,
        max_workers=1,
        weights={'phash': 0.0, 'description': 0.0, 'vision': 1.0},
        provider_id='ollama',
    )
    
    print(f"\n=== Results ===")
    print(f"Processed: {stats['processed']}")
    print(f"Matched: {stats['matched']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Total matches found: {len(matches)}")
    
    db.close()

if __name__ == "__main__":
    test()
