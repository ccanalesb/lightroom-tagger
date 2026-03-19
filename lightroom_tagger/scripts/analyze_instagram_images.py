#!/usr/bin/env python3
"""Analyze all downloaded Instagram images and store in database."""

import os
from pathlib import Path
from tinydb import TinyDB

from lightroom_tagger.core.database import init_database, init_instagram_table, store_instagram_image
from lightroom_tagger.core.analyzer import analyze_image


def scan_instagram_folder(base_path: str = "/tmp/instagram_images"):
    """Scan Instagram download folder and return list of image info."""
    images = []
    base = Path(base_path)
    
    if not base.exists():
        print(f"Error: {base_path} does not exist")
        return []
    
    for post_folder in base.iterdir():
        if not post_folder.is_dir():
            continue
        
        post_id = post_folder.name
        
        for img_file in sorted(post_folder.glob("img_*.jpg")):
            images.append({
                'post_id': post_id,
                'local_path': str(img_file),
                'filename': img_file.name,
                'post_url': f"https://www.instagram.com/p/{post_id}/"
            })
    
    return images


def main():
    db_path = "library.db"
    db = init_database(db_path)
    init_instagram_table(db)
    
    print("Scanning Instagram download folder...")
    images = scan_instagram_folder()
    print(f"Found {len(images)} images")
    
    for i, img_info in enumerate(images, 1):
        print(f"\n[{i}/{len(images)}] Analyzing: {img_info['filename']}")
        
        analysis = analyze_image(img_info['local_path'])
        
        record = {
            'post_url': img_info['post_url'],
            'local_path': img_info['local_path'],
            'filename': img_info['filename'],
            'instagram_folder': img_info['post_id'],
            'phash': analysis.get('phash'),
            'exif': analysis.get('exif'),
            'description': analysis.get('description')
        }
        
        key = store_instagram_image(db, record)
        print(f"  Stored with key: {key}")
        print(f"  pHash: {analysis.get('phash', 'N/A')}")
        if analysis.get('description'):
            print(f"  Description: {analysis.get('description')[:50]}...")
    
    print(f"\n✓ Analyzed and stored {len(images)} Instagram images")
    db.close()


if __name__ == "__main__":
    main()