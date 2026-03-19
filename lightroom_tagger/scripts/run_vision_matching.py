#!/usr/bin/env python3
"""Run vision-only matching between Instagram and catalog images."""

import os
import json
from pathlib import Path
from tinydb import TinyDB, Query
from typing import List, Dict, Any

from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.analyzer import compare_with_vision, vision_score


def get_all_catalog_images(db) -> List[dict]:
    """Get all catalog images (no filtering)."""
    return db.table('images').all()


def get_all_instagram_images(db) -> List[dict]:
    """Get all Instagram images."""
    return db.table('instagram_images').all()


def match_with_vision_only(db, insta_image: dict, catalog_images: list) -> List[dict]:
    """Match Instagram image against all catalog images using vision only."""
    insta_path = insta_image.get('local_path')
    
    if not insta_path or not os.path.exists(insta_path):
        print(f"  Warning: Instagram image not found: {insta_path}")
        return []
    
    results = []
    
    print(f"  Comparing against {len(catalog_images)} catalog images...")
    
    for i, catalog_img in enumerate(catalog_images):
        filepath = catalog_img.get('filepath', '')
        catalog_path = filepath.replace('//tnas/ccanales/', '/mnt/tnas/')
        
        if not catalog_path or not os.path.exists(catalog_path):
            continue
        
        try:
            vision_result = compare_with_vision(catalog_path, insta_path)
            score = vision_score(vision_result)
            
            results.append({
                'catalog_key': catalog_img.get('key'),
                'catalog_path': catalog_path,
                'catalog_date': catalog_img.get('date_taken'),
                'vision_result': vision_result,
                'vision_score': score,
                'insta_path': insta_path,
                'insta_key': insta_image.get('key')
            })
            
            if (i + 1) % 10 == 0:
                print(f"    Processed {i + 1}/{len(catalog_images)}...")
                
        except Exception as e:
            print(f"    Error comparing with {catalog_img.get('key')}: {e}")
            continue
    
    results.sort(key=lambda x: x['vision_score'], reverse=True)
    return results


def main():
    db_path = "library.db"
    db = init_database(db_path)
    
    print("Loading images...")
    catalog_images = get_all_catalog_images(db)
    insta_images = get_all_instagram_images(db)
    
    print(f"Catalog images: {len(catalog_images)}")
    print(f"Instagram images: {len(insta_images)}")
    print()
    
    all_results = {}
    
    for i, insta_img in enumerate(insta_images, 1):
        print(f"[{i}/{len(insta_images)}] Matching: {insta_img.get('filename')}")
        print(f"  Path: {insta_img.get('local_path')}")
        
        matches = match_with_vision_only(db, insta_img, catalog_images)
        
        if matches:
            top_match = matches[0]
            print(f"  Top match: {top_match['catalog_key']}")
            print(f"  Result: {top_match['vision_result']} (score: {top_match['vision_score']})")
            
            all_results[insta_img.get('key')] = {
                'insta_image': insta_img,
                'top_matches': matches[:3]
            }
        else:
            print(f"  No matches found")
        
        print()
    
    with open('vision_matching_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"✓ Matching complete. Results saved to vision_matching_results.json")
    db.close()


if __name__ == "__main__":
    main()