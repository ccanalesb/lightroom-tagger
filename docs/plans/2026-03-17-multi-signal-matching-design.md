# Multi-Signal Image Matching Design

**Date:** 2026-03-17

## Overview

Enhance Instagram sync with multi-signal matching: combine perceptual hashing (phash), agent-generated descriptions, and EXIF metadata for more accurate image matching. All results stored in TinyDB for reuse.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Lightroom       │     │ Instagram        │     │ Matching        │
│ Catalog         │     │ Posts            │     │ Engine          │
└────────┬────────┘     └────────┬─────────┘     └────────┬────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Image Analyzer │     │ Image Analyzer   │     │ Match Results   │
│ (phash+exif+   │     │ (phash+exif+     │     │ (stored in DB)  │
│  description)  │     │  description)    │     │                 │
└────────┬────────┘     └────────┬─────────┘     └────────┬────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         TinyDB                                        │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐    │
│  │ catalog_     │  │ instagram_       │  │ matches            │    │
│  │ images       │  │ images           │  │ (insta↔catalog)    │    │
│  └──────────────┘  └──────────────────┘  └────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

## Modules

### 1. Image Analyzer (`core/analyzer.py`)

**Responsibility:** Extract all signals from a single image.

```python
def analyze_image(path: str) -> ImageAnalysis:
    """
    Returns:
        phash: str (perceptual hash)
        exif: {camera, lens, date_taken, gps, iso, aperture, shutter_speed}
        description: str (agent-generated)
    """
```

### 2. Catalog Enricher (`lightroom/enricher.py`)

**Responsibility:** Process Lightroom catalog images on-demand.

```python
def enrich_catalog_images(catalog_path: str, db_path: str, limit: int = None) -> dict:
    """
    - Query Lightroom for images without analysis
    - Call analyzer on each
    - Store in TinyDB catalog_images table
    - Returns {processed: N, skipped: N, errors: N}
    """
```

### 3. Instagram Crawler (`instagram/crawler.py`)

**Responsibility:** Fetch Instagram images, analyze, store.

```python
def crawl_and_analyze(username: str, output_dir: str, limit: int = 50) -> dict:
    """
    - Pull images from posts (network response)
    - Call analyzer on each
    - Store in TinyDB instagram_images table
    - Returns {processed: N, skipped: N}
    """
```

### 4. Matcher (`core/matcher.py`)

**Responsibility:** Find matches between Instagram and catalog images.

```python
def match_image(insta_key: str, threshold: float = 0.7) -> list[Match]:
    """
    Step 1: Query catalog by EXIF (camera + lens + date within 7 days)
    Step 2: Score candidates: phash_distance + description_similarity
    Step 3: Store match in DB
    
    Returns: [{catalog_key, phash_score, desc_score, total_score}]
    """

def match_batch(insta_keys: list[str], threshold: float = 0.7) -> dict:
    """Match multiple Instagram images."""
```

## Database Schema

```python
# catalog_images table
{
    "key": "2024-01-15_sunset.jpg",      # {date_taken}_{filename}
    "filepath": "/mnt/nas/photos/...",   # Absolute path
    "phash": "a1b2c3d4e5f6g7h8",         # 16-char perceptual hash
    "exif": {
        "camera": "Canon EOS R5",
        "lens": "RF 24-70mm F2.8",
        "date_taken": "2024-01-15T18:30:00",
        "gps": [45.5231, -122.6765],
        "iso": 100,
        "aperture": 2.8,
        "shutter_speed": "1/250"
    },
    "description": "Golden hour sunset over the bay...",  # Agent-generated
    "analyzed_at": "2026-03-17T10:30:00"
}

# instagram_images table
{
    "key": "insta_2026-03-17_post123",   # {source}_{date}_{post_id}
    "post_url": "https://instagram.com/p/...",
    "local_path": "/tmp/insta_abc123.jpg",
    "phash": "a1b2c3d4e5f6g7h8",
    "exif": {...},
    "description": "Beautiful sunset photo...",
    "crawled_at": "2026-03-17T10:30:00"
}

# matches table
{
    "catalog_key": "2024-01-15_sunset.jpg",
    "insta_key": "insta_2026-03-17_post123",
    "phash_distance": 2,                  # Lower is better
    "phash_score": 0.875,                 # Normalized 0-1
    "desc_similarity": 0.82,              # Text similarity 0-1
    "exif_camera_match": True,
    "exif_lens_match": True,
    "total_score": 0.85,
    "matched_at": "2026-03-17T10:35:00"
}
```

## Matching Algorithm

```
weights = {phash: 0.5, description: 0.5}

function match(insta_image, catalog_candidates):
    # Step 1: Filter by EXIF (required)
    candidates = catalog_candidates.filter(
        exif.camera == insta.exif.camera AND
        exif.lens == insta.exif.lens AND
        abs(exif.date - insta.exif.date) < 7 days
    )
    
    # Step 2: Score by phash + description
    for each candidate:
        phash_score = 1 - (hamming_distance / 16)  # Normalize to 0-1
        desc_score = text_similarity(candidate.description, insta.description)
        
        total = (weights.phash * phash_score) + (weights.description * desc_score)
    
    # Step 3: Return matches above threshold
    return candidates.where(total >= threshold).sorted_by(total)
```

## CLI Commands

```bash
# Analyze and store catalog images (run on-demand)
lightroom-tagger enrich-catalog --catalog /path/to/catalog.lrcat --db /path/to/db.json

# Crawl Instagram and analyze images (run on-demand)
lightroom-tagger crawl-instagram --user username --db /path/to/db.json --limit 50

# Match stored Instagram images against catalog
lightroom-tagger match --db /path/to/db.json --threshold 0.7

# Query matches
lightroom-tagger matches --db /path/to/db.json
```

## Design Decisions

1. **On-demand processing**: No background jobs. User runs commands when needed.
2. **Everything in DB**: Enables reprocessing, auditing, and incremental updates.
3. **EXIF as filter, not scorer**: Strict EXIF match required, then weighted scoring.
4. **Local + external agent**: Interface allows swapping local model (LLaVA) for external (Claude API).
5. **Idempotent**: Re-running enrich/crawl skips already-processed images.

## Future Considerations

- Cache agent descriptions (don't regenerate if file unchanged)
- Support for multiple EXIF date windows
- Manual match confirmation workflow
- Export matches to Lightroom keywords
