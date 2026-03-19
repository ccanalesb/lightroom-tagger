# Vision-Based Matching Validation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Analyze all 46 downloaded Instagram images and run vision-based matching against the catalog with side-by-side comparison output for validation.

**Architecture:** Create a validation workflow that populates the instagram_images table, computes hashes/descriptions for all downloaded images, runs vision-only matching (no date/EXIF filtering), and generates an HTML report showing Instagram image vs top 3 catalog matches side-by-side.

**Tech Stack:** Python, TinyDB, PIL/pHash, Ollama vision model (gemma3:27b), HTML report generation

---

## Task 1: Create Instagram Image Analysis Script

**Files:**
- Create: `scripts/analyze_instagram_images.py`

**Step 1: Create script to scan and analyze downloaded Instagram images**

```python
#!/usr/bin/env python3
"""Analyze all downloaded Instagram images and store in database."""

import os
import sys
from pathlib import Path
from tinydb import TinyDB

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import init_database, init_instagram_table, store_instagram_image
from core.analyzer import analyze_image


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
        
        # Analyze image
        analysis = analyze_image(img_info['local_path'])
        
        # Prepare record
        record = {
            'post_url': img_info['post_url'],
            'local_path': img_info['local_path'],
            'filename': img_info['filename'],
            'instagram_folder': img_info['post_id'],
            'phash': analysis.get('phash'),
            'exif': analysis.get('exif'),
            'description': analysis.get('description')
        }
        
        # Store in database
        key = store_instagram_image(db, record)
        print(f"  Stored with key: {key}")
        print(f"  pHash: {analysis.get('phash', 'N/A')}")
        print(f"  Description: {analysis.get('description', 'N/A')[:50]}...")
    
    print(f"\n✓ Analyzed and stored {len(images)} Instagram images")
    db.close()


if __name__ == "__main__":
    main()
```

**Step 2: Make script executable and test**

Run: `chmod +x scripts/analyze_instagram_images.py`

**Step 3: Run the analysis (this will take time - 46 images × ~5-10s each)**

Run: `python3 scripts/analyze_instagram_images.py`

Expected: Progress output showing each image being analyzed and stored

**Step 4: Verify data was stored**

Run: `python3 -c "from tinydb import TinyDB; db = TinyDB('library.db'); print(f'Instagram images: {len(db.table(\"instagram_images\").all())}')"`

Expected: `Instagram images: 46`

**Step 5: Commit**

```bash
git add scripts/analyze_instagram_images.py
git commit -m "feat: add Instagram image analysis script"
```

---

## Task 2: Create Vision-Only Matching Script

**Files:**
- Create: `scripts/run_vision_matching.py`

**Step 1: Create script for vision-only matching (no filtering)**

```python
#!/usr/bin/env python3
"""Run vision-only matching between Instagram and catalog images."""

import os
import sys
from pathlib import Path
from tinydb import TinyDB, Query
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import init_database
from core.analyzer import compare_with_vision, vision_score


def get_all_catalog_images(db) -> List[dict]:
    """Get all catalog images (no filtering)."""
    # The catalog images are in the 'images' table with full metadata
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
        catalog_path = catalog_img.get('filepath', '').replace('//tnas/', '/mnt/tnas/')
        
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
    
    # Sort by vision score descending
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
            
            # Store top 3 matches
            all_results[insta_img.get('key')] = {
                'insta_image': insta_img,
                'top_matches': matches[:3]
            }
        else:
            print(f"  No matches found")
        
        print()
    
    # Save results for report generation
    import json
    with open('vision_matching_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"✓ Matching complete. Results saved to vision_matching_results.json")
    db.close()


if __name__ == "__main__":
    main()
```

**Step 2: Make executable**

Run: `chmod +x scripts/run_vision_matching.py`

**Step 3: Run matching (WARNING: This will take a long time - 46 images × 37 catalog images × ~5-10s per comparison)**

Run: `python3 scripts/run_vision_matching.py`

Expected: Progress showing each Instagram image being compared against all 37 catalog images

**Step 4: Commit**

```bash
git add scripts/run_vision_matching.py
git commit -m "feat: add vision-only matching script"
```

---

## Task 3: Create Side-by-Side HTML Report Generator

**Files:**
- Create: `scripts/generate_validation_report.py`

**Step 1: Create HTML report generator**

```python
#!/usr/bin/env python3
"""Generate HTML report for vision matching validation."""

import json
import base64
from pathlib import Path
from PIL import Image
import io


def image_to_base64(path: str, max_size: int = 400) -> str:
    """Convert image to base64 for HTML embedding, resizing if needed."""
    try:
        with Image.open(path) as img:
            # Resize if too large
            if img.width > max_size or img.height > max_size:
                ratio = max_size / max(img.width, img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        print(f"Error loading image {path}: {e}")
        return ""


def generate_html_report(results_file: str = 'vision_matching_results.json', 
                         output_file: str = 'validation_report.html'):
    """Generate HTML report with side-by-side comparisons."""
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '    <title>Instagram Vision Matching Validation</title>',
        '    <style>',
        '        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }',
        '        .match-card { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }',
        '        .match-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #333; }',
        '        .comparison { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }',
        '        .image-box { text-align: center; }',
        '        .image-box img { max-width: 400px; max-height: 400px; border: 1px solid #ddd; border-radius: 4px; }',
        '        .image-label { font-size: 12px; color: #666; margin-top: 5px; }',
        '        .score-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 14px; }',
        '        .score-same { background: #4caf50; color: white; }',
        '        .score-uncertain { background: #ff9800; color: white; }',
        '        .score-different { background: #f44336; color: white; }',
        '        .match-info { margin-top: 10px; padding: 10px; background: #f9f9f9; border-radius: 4px; }',
        '        .top-matches { margin-top: 15px; }',
        '        .top-match { display: inline-block; margin: 5px; padding: 10px; background: #e3f2fd; border-radius: 4px; }',
        '        .top-match img { max-width: 150px; max-height: 150px; }',
        '        .legend { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }',
        '        .legend-item { display: inline-block; margin-right: 20px; }',
        '    </style>',
        '</head>',
        '<body>',
        '    <h1>Instagram Vision Matching Validation Report</h1>',
        '    <div class="legend">',
        '        <h3>Legend:</h3>',
        '        <div class="legend-item"><span class="score-badge score-same">SAME</span> = Confident match</div>',
        '        <div class="legend-item"><span class="score-badge score-uncertain">UNCERTAIN</span> = Unclear</div>',
        '        <div class="legend-item"><span class="score-badge score-different">DIFFERENT</span> = Not a match</div>',
        '    </div>',
    ]
    
    for insta_key, data in results.items():
        insta_img = data['insta_image']
        top_matches = data['top_matches']
        
        if not top_matches:
            continue
        
        best_match = top_matches[0]
        
        # Determine badge class
        result = best_match['vision_result']
        if result == 'SAME':
            badge_class = 'score-same'
        elif result == 'UNCERTAIN':
            badge_class = 'score-uncertain'
        else:
            badge_class = 'score-different'
        
        html_parts.append('<div class="match-card">')
        html_parts.append(f'    <div class="match-title">Instagram: {insta_img.get("filename")}</div>')
        html_parts.append('    <div class="comparison">')
        
        # Instagram image
        insta_path = insta_img.get('local_path', '')
        insta_b64 = image_to_base64(insta_path)
        html_parts.append('        <div class="image-box">')
        html_parts.append(f'            <img src="{insta_b64}" alt="Instagram">')
        html_parts.append('            <div class="image-label">Instagram Image</div>')
        html_parts.append('        </div>')
        
        # Best catalog match
        catalog_path = best_match.get('catalog_path', '')
        catalog_b64 = image_to_base64(catalog_path)
        html_parts.append('        <div class="image-box">')
        html_parts.append(f'            <img src="{catalog_b64}" alt="Catalog">')
        html_parts.append(f'            <div class="image-label">Best Match: {best_match.get("catalog_key", "Unknown")}</div>')
        html_parts.append('        </div>')
        
        html_parts.append('    </div>')
        
        # Match info
        html_parts.append('    <div class="match-info">')
        html_parts.append(f'        <span class="score-badge {badge_class}">{result}</span>')
        html_parts.append(f'        <span style="margin-left: 10px;">Score: {best_match.get("vision_score", 0)}</span>')
        html_parts.append(f'        <span style="margin-left: 10px;">Catalog Date: {best_match.get("catalog_date", "Unknown")}</span>')
        html_parts.append('    </div>')
        
        # Top 3 matches thumbnails
        if len(top_matches) > 1:
            html_parts.append('    <div class="top-matches">')
            html_parts.append('        <strong>Top 3 Matches:</strong>')
            for j, match in enumerate(top_matches[:3], 1):
                match_path = match.get('catalog_path', '')
                match_b64 = image_to_base64(match_path, max_size=150)
                match_result = match.get('vision_result', 'UNCERTAIN')
                if match_result == 'SAME':
                    match_class = 'score-same'
                elif match_result == 'UNCERTAIN':
                    match_class = 'score-uncertain'
                else:
                    match_class = 'score-different'
                
                html_parts.append(f'        <div class="top-match">')
                html_parts.append(f'            <div>#{j}</div>')
                html_parts.append(f'            <img src="{match_b64}" alt="Match {j}">')
                html_parts.append(f'            <div><span class="score-badge {match_class}">{match_result}</span></div>')
                html_parts.append('        </div>')
            html_parts.append('    </div>')
        
        html_parts.append('</div>')
    
    html_parts.extend([
        '</body>',
        '</html>',
    ])
    
    with open(output_file, 'w') as f:
        f.write('\n'.join(html_parts))
    
    print(f"✓ Report generated: {output_file}")
    print(f"  Open in browser: file://{Path(output_file).absolute()}")


if __name__ == "__main__":
    generate_html_report()
```

**Step 2: Make executable**

Run: `chmod +x scripts/generate_validation_report.py`

**Step 3: Generate report (requires vision_matching_results.json from Task 2)**

Run: `python3 scripts/generate_validation_report.py`

Expected: `Report generated: validation_report.html`

**Step 4: Commit**

```bash
git add scripts/generate_validation_report.py
git commit -m "feat: add validation report generator with side-by-side comparison"
```

---

## Task 4: Create Master Validation Runner Script

**Files:**
- Create: `scripts/run_full_validation.py`

**Step 1: Create master script that runs all steps**

```python
#!/usr/bin/env python3
"""Master script to run full vision-based matching validation workflow."""

import subprocess
import sys
from pathlib import Path


def run_step(name: str, command: list, critical: bool = True):
    """Run a step and handle errors."""
    print(f"\n{'='*60}")
    print(f"STEP: {name}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(command, capture_output=False)
    
    if result.returncode != 0:
        print(f"\n❌ Step failed: {name}")
        if critical:
            sys.exit(1)
        return False
    
    print(f"\n✓ Step completed: {name}")
    return True


def main():
    scripts_dir = Path(__file__).parent
    
    print("Starting Instagram Vision Matching Validation")
    print("This will analyze 46 Instagram images and compare against 37 catalog images")
    print("Estimated time: 2-4 hours (depending on vision model speed)")
    print()
    
    # Step 1: Analyze Instagram images
    run_step(
        "Analyze Instagram Images",
        [sys.executable, str(scripts_dir / "analyze_instagram_images.py")]
    )
    
    # Step 2: Run vision matching
    print("\n" + "="*60)
    print("⚠️  WARNING: This step will take a long time!")
    print("   46 Instagram images × 37 catalog images × ~5-10s each")
    print("   Estimated: 2-4 hours")
    print("="*60)
    
    response = input("\nContinue with vision matching? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return
    
    run_step(
        "Run Vision Matching",
        [sys.executable, str(scripts_dir / "run_vision_matching.py")]
    )
    
    # Step 3: Generate report
    run_step(
        "Generate Validation Report",
        [sys.executable, str(scripts_dir / "generate_validation_report.py")]
    )
    
    print("\n" + "="*60)
    print("✅ VALIDATION COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Open validation_report.html in your browser")
    print("2. Review each match - check if vision model correctly identified same/different")
    print("3. Note any patterns in failures")
    print("4. Adjust matching logic based on findings")
    print()


if __name__ == "__main__":
    main()
```

**Step 2: Make executable**

Run: `chmod +x scripts/run_full_validation.py`

**Step 3: Commit**

```bash
git add scripts/run_full_validation.py
git commit -m "feat: add master validation runner script"
```

---

## Task 5: Run Full Validation (Manual Step)

**Step 1: Execute the full validation workflow**

Run: `python3 scripts/run_full_validation.py`

**Expected Timeline:**
- Instagram analysis: ~5-10 minutes
- Vision matching: ~2-4 hours (46 × 37 × 5-10s)
- Report generation: ~1 minute

**Step 2: Review Results**

Open `validation_report.html` in your browser and review:

1. **Correct matches** (SAME with actual same photo)
2. **False positives** (SAME but different photos)
3. **False negatives** (DIFFERENT but actually same photo)
4. **Uncertain cases** that need human judgment

**Step 3: Document Findings**

Create a summary of:
- How many matches were correct
- Common failure patterns
- Recommended threshold adjustments
- Ideas for improving matching accuracy

---

## Parking Lot (Future Improvements)

1. **Extract Instagram post dates** from HTML/metadata during crawling
2. **Parallelize vision comparisons** using multiprocessing
3. **Cache vision results** to avoid re-comparing same pairs
4. **Interactive validation UI** with approve/reject buttons
5. **Batch size limiting** for large catalogs

---

## Summary

This plan creates a complete validation workflow:

1. **Analyze** all 46 downloaded Instagram images (pHash, description)
2. **Match** each against all 37 catalog images using vision model only
3. **Report** side-by-side comparisons in HTML for easy validation
4. **Review** results to determine if vision-only matching is accurate enough

The key insight: Since Instagram strips EXIF and adds white borders, we're relying entirely on the vision model (gemma3:27b) to determine if two images depict the same scene/subject.
