# Lightroom Tagger

A Python tool to read Lightroom catalog (`.lrcat` SQLite database), index metadata to TinyDB, and export/search your photo library.

## Installation

```bash
pip install tinydb pyyaml
```

## Usage

```bash
# Set PYTHONPATH if running from source
export PYTHONPATH=/path/to/lightroom-tagger

# Scan a catalog
python -m lightroom_tagger scan --catalog "/path/to/Catalog.lrcat" --db ~/lightroom_tagger/library.db

# Search indexed images
python -m lightroom_tagger search --keyword "landscape" --db ~/lightroom_tagger/library.db

# Export to CSV or JSON
python -m lightroom_tagger export --db ~/lightroom_tagger/library.db --output export.csv --format csv

# View stats
python -m lightroom_tagger stats --db ~/lightroom_tagger/library.db
```

## Project Structure

### `lightroom_tagger/config.py`
Configuration module that loads settings from `config.yaml` or environment variables. Handles NAS path resolution (e.g., `//nas/...` → `/mnt/nas/...`) and provides defaults for all settings.

### `lightroom_tagger/schema_explorer.py`
Explores the Lightroom catalog schema. Connects to the SQLite database and lists all tables with their columns. Useful for understanding the catalog structure.

### `lightroom_tagger/catalog_reader.py`
Reads metadata from the Lightroom catalog. Queries the SQLite database and joins these key tables:
- `AgLibraryFile` + `AgLibraryFolder` + `AgLibraryRootFolder` - file paths
- `Adobe_images` - ratings, pick flag, color labels
- `AgLibraryKeywordImage` + `AgLibraryKeyword` - keywords/tags
- `AgHarvestedExifMetadata` - EXIF data (camera, lens, date, GPS)
- `AgLibraryIPTC` - caption, copyright

### `lightroom_tagger/database.py`
TinyDB operations for storing and querying indexed images. Provides functions for:
- `store_image()` / `store_images_batch()` - save records
- `get_image()` / `get_all_images()` - retrieve records
- `search_by_keyword()`, `search_by_rating()`, `search_by_date()` - query filters
- Unique key format: `{date_taken}_{filename}`

### `lightroom_tagger/cli.py`
Command-line interface with subcommands:
- `scan` - Scan catalog, index all images to TinyDB
- `search` - Search indexed images by keyword, rating, date, color label
- `export` - Export to JSON or CSV format
- `init` - Initialize empty database
- `stats` - Show database statistics

### `lightroom_tagger/tagger.py`
Main entry point that ties everything together.

### `lightroom_tagger/__main__.py`
Enables running as: `python -m lightroom_tagger`

## Configuration

Edit `config.yaml` or use environment variables:

```yaml
catalog_path: "//nas/ccanales/Lightroom Server/Catalog.lrcat"
db_path: "~/lightroom_tagger/library.db"
mount_point: "/mnt/nas"
workers: 4
ai_model: "claude-3-5-sonnet-20241022"
skip_ai: false
verbose: false
```

## Data Extracted

Each image record contains:
- `id` - Internal Lightroom ID
- `filename`, `filepath` - File location
- `date_taken` - Capture date (ISO format)
- `rating` - Star rating (0-5)
- `pick` - Pick flag (True/False)
- `color_label` - Color label (Red, Yellow, Green, Blue, Purple)
- `keywords` - List of keywords/tags
- `caption`, `copyright` - IPTC metadata
- `camera_make`, `camera_model`, `lens` - Camera info
- `focal_length`, `aperture`, `shutter_speed`, `iso` - EXIF settings
- `gps_latitude`, `gps_longitude` - GPS coordinates
- `width`, `height` - Image dimensions
- `key` - Unique identifier (`{date_taken}_{filename}`)
