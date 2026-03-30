#!/usr/bin/env python3
"""Test subset matching - specific Instagram posts vs specific catalog images."""

import json
import os

from lightroom_tagger.core.analyzer import compare_with_vision, vision_score
from lightroom_tagger.core.database import init_database


def main():
    db_path = "library.db"
    db = init_database(db_path)

    # Target Instagram folders
    insta_folders = ['C04_udixrGy', 'CxEqSUFoCho']

    # Target catalog images
    catalog_filenames = ['L1007166', 'L1007167', 'L1007168']
    catalog_base_path = "/mnt/tnas/Lightroom Server/Fotos/2026/Street"

    insta_images = []
    for folder in insta_folders:
        images = db.execute(
            "SELECT * FROM instagram_images WHERE instagram_folder = ?", (folder,)
        ).fetchall()
        insta_images.extend(images)

    print(f"Instagram images to test: {len(insta_images)}")
    print(f"From folders: {insta_folders}")
    print()

    # Get catalog images
    catalog_images = []
    for fname in catalog_filenames:
        catalog_path = f"{catalog_base_path}/{fname}.DNG"
        if os.path.exists(catalog_path):
            catalog_images.append({
                'key': f'street_{fname}',
                'filepath': catalog_path,
                'filename': fname
            })
        else:
            print(f"Warning: {catalog_path} not found")

    print(f"Catalog images to test: {len(catalog_images)}")
    print(f"From: {catalog_base_path}")
    print()

    # Run comparisons
    results = {}

    for i, insta_img in enumerate(insta_images, 1):
        insta_key = insta_img.get('key')
        insta_path = insta_img.get('local_path')
        insta_folder = insta_img.get('instagram_folder')
        insta_filename = insta_img.get('filename')

        print(f"[{i}/{len(insta_images)}] {insta_folder}/{insta_filename}")
        print(f"  Path: {insta_path}")

        matches = []

        for j, catalog_img in enumerate(catalog_images, 1):
            catalog_path = catalog_img['filepath']
            catalog_key = catalog_img['key']

            print(f"  [{j}/{len(catalog_images)}] Comparing with {catalog_key}...", end=" ", flush=True)

            try:
                vision_data = compare_with_vision(catalog_path, insta_path)
                score = vision_score(vision_data['confidence'])
                verdict = vision_data['verdict']
                print(f"{verdict} (score: {score})")

                matches.append({
                    'catalog_key': catalog_key,
                    'catalog_path': catalog_path,
                    'vision_result': verdict,
                    'vision_score': score
                })
            except Exception as e:
                print(f"ERROR: {e}")
                matches.append({
                    'catalog_key': catalog_key,
                    'catalog_path': catalog_path,
                    'vision_result': 'ERROR',
                    'vision_score': 0.5
                })

        # Sort by score
        matches.sort(key=lambda x: x['vision_score'], reverse=True)

        results[insta_key] = {
            'insta_image': {
                'key': insta_key,
                'local_path': insta_path,
                'filename': insta_filename,
                'instagram_folder': insta_folder
            },
            'top_matches': matches
        }

        # Show best match
        if matches:
            best = matches[0]
            print(f"  Best match: {best['catalog_key']} - {best['vision_result']}")

        print()

    # Save results
    output_file = 'vision_subset_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"✓ Results saved to {output_file}")

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    same_count = 0
    uncertain_count = 0
    different_count = 0

    for _insta_key, data in results.items():
        best = data['top_matches'][0] if data['top_matches'] else None
        if best:
            result = best['vision_result']
            print(f"{data['insta_image']['instagram_folder']}/{data['insta_image']['filename']}: {result} -> {best['catalog_key']}")

            if result == 'SAME':
                same_count += 1
            elif result == 'UNCERTAIN':
                uncertain_count += 1
            else:
                different_count += 1

    print()
    print(f"SAME: {same_count}")
    print(f"UNCERTAIN: {uncertain_count}")
    print(f"DIFFERENT: {different_count}")
    print(f"Total: {len(results)}")

    db.close()


if __name__ == "__main__":
    main()
