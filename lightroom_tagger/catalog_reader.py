import sqlite3
import json
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from lightroom_tagger.config import load_config


def connect_catalog(catalog_path: str) -> sqlite3.Connection:
    """Connect to Lightroom catalog."""
    conn = sqlite3.connect(catalog_path)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parse Lightroom date string to ISO format."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        return dt.isoformat()
    except ValueError:
        return date_str


def _parse_gps(value: Optional[str]) -> Optional[float]:
    """Parse GPS coordinate from Lightroom format."""
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def generate_record_key(record: dict) -> str:
    """Generate unique key: {date_taken}_{filename}"""
    date_taken = record.get("date_taken", "unknown")
    if date_taken:
        date_part = date_taken[:10]
    else:
        date_part = "unknown"
    filename = record.get("filename", "unknown")
    return f"{date_part}_{filename}"


def _get_keywords_for_image(conn: sqlite3.Connection, image_id: int) -> list[str]:
    """Get keywords for a specific image."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT k.name
        FROM AgLibraryKeywordImage ki
        JOIN AgLibraryKeyword k ON ki.tag = k.id_local
        WHERE ki.image = ?
    """, (image_id,))
    return [row[0] for row in cursor.fetchall()]


def _fetch_image_metadata(conn: sqlite3.Connection, image_id: int) -> Optional[dict]:
    """Fetch metadata for a single image by ID."""
    cursor = conn.cursor()
    
    query = """
        SELECT 
            f.id_local as file_id,
            f.baseName as filename,
            f.extension as extension,
            fl.pathFromRoot as folder_path,
            rf.absolutePath as root_path,
            
            img.rating as rating,
            img.pick as pick_flag,
            img.colorLabels as color_label,
            img.fileWidth as width,
            img.fileHeight as height,
            
            img.captureTime as date_taken,
            
            exif.aperture as aperture,
            exif.focalLength as focal_length,
            exif.shutterSpeed as shutter_speed,
            exif.isoSpeedRating as iso,
            exif.gpsLatitude as gps_latitude,
            exif.gpsLongitude as gps_longitude,
            
            iptc.caption as caption,
            iptc.copyright as copyright
            
        FROM AgLibraryFile f
        JOIN AgLibraryFolder fl ON f.folder = fl.id_local
        JOIN AgLibraryRootFolder rf ON fl.rootFolder = rf.id_local
        LEFT JOIN Adobe_images img ON f.id_local = img.rootFile
        LEFT JOIN AgHarvestedExifMetadata exif ON img.id_local = exif.image
        LEFT JOIN AgLibraryIPTC iptc ON img.id_local = iptc.image
        WHERE f.id_local = ?
    """
    
    cursor.execute(query, (image_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
    
    record = {
        "id": row["file_id"],
        "filename": row["filename"] or "",
        "filepath": "",
        "date_taken": "",
        "rating": row["rating"] or 0,
        "pick": bool(row["pick_flag"]) if row["pick_flag"] is not None else False,
        "color_label": row["color_label"] or "",
        "keywords": [],
        "title": "",
        "caption": row["caption"] or "",
        "copyright": row["copyright"] or "",
        "camera_make": "",
        "camera_model": "",
        "lens": "",
        "focal_length": row["focal_length"] or "",
        "aperture": row["aperture"] or "",
        "shutter_speed": row["shutter_speed"] or "",
        "iso": row["iso"] or 0,
        "gps_latitude": _parse_gps(row["gps_latitude"]),
        "gps_longitude": _parse_gps(row["gps_longitude"]),
        "width": row["width"] or 0,
        "height": row["height"] or 0,
        "file_size": 0,
    }
    
    root_path = row["root_path"] or ""
    folder_path = row["folder_path"] or ""
    filename = row["filename"] or ""
    extension = row["extension"] or ""
    
    if extension:
        filename = filename + "." + extension
    
    record["filepath"] = root_path + folder_path + filename
    
    date_taken = _parse_date(row["date_taken"])
    record["date_taken"] = date_taken or ""
    
    keywords = _get_keywords_for_image(conn, image_id)
    record["keywords"] = keywords
    
    record["key"] = generate_record_key(record)
    
    return record


def get_image_by_id(conn: sqlite3.Connection, image_id: int) -> Optional[dict]:
    """Get single image by ID."""
    return _fetch_image_metadata(conn, image_id)


def _process_image_batch(conn: sqlite3.Connection, image_ids: list[int]) -> list[dict]:
    """Process a batch of images and return their records."""
    results = []
    for img_id in image_ids:
        record = _fetch_image_metadata(conn, img_id)
        if record:
            results.append(record)
    return results


def get_image_records(conn: sqlite3.Connection, limit: Optional[int] = None, workers: int = 4) -> list[dict]:
    """Get all image records with full metadata.
    
    Joins:
    - AgLibraryFile + AgLibraryFolder + AgLibraryRootFolder for path
    - Adobe_images for rating, pick flag, color label
    - AgLibraryKeywordImage + AgLibraryKeyword for keywords
    - AgHarvestedExifMetadata for EXIF
    - AgLibraryIPTC for title, caption, copyright
    
    Args:
        conn: SQLite connection to Lightroom catalog
        limit: Optional limit on number of images to process
        workers: Number of parallel workers for processing (default 4)
    """
    cursor = conn.cursor()
    
    if limit:
        cursor.execute("SELECT f.id_local FROM AgLibraryFile f ORDER BY f.id_local LIMIT ?", (limit,))
    else:
        cursor.execute("SELECT f.id_local FROM AgLibraryFile f ORDER BY f.id_local")
    
    image_ids = [row[0] for row in cursor.fetchall()]
    
    if not image_ids:
        return []
    
    all_records = []
    
    if len(image_ids) > 10000 and workers > 1:
        # Note: SQLite connections are not thread-safe
        # For now, process sequentially to avoid issues
        for img_id in image_ids:
            record = _fetch_image_metadata(conn, img_id)
            if record:
                all_records.append(record)
    else:
        for img_id in image_ids:
            record = _fetch_image_metadata(conn, img_id)
            if record:
                all_records.append(record)
    
    return all_records


def get_image_count(conn: sqlite3.Connection) -> int:
    """Get total number of images in catalog."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM AgLibraryFile")
    return cursor.fetchone()[0]


def main():
    """CLI entry point for catalog reading."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Read Lightroom catalog and output image metadata"
    )
    parser.add_argument(
        "--catalog", "-c", help="Path to Lightroom catalog (.lrcat)"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=None,
        help="Limit number of images to process"
    )
    parser.add_argument(
        "--output", "-o", help="Output JSON file path"
    )
    parser.add_argument(
        "--count", action="store_true",
        help="Only print image count"
    )
    parser.add_argument(
        "--id", type=int, default=None,
        help="Get single image by ID"
    )

    args = parser.parse_args()

    catalog_path = args.catalog
    if not catalog_path:
        config = load_config(args.config)
        catalog_path = config.catalog_path

    if not catalog_path:
        print("Error: No catalog path provided. Use --catalog or config.yaml")
        return 1

    if not Path(catalog_path).exists():
        print(f"Error: Catalog not found: {catalog_path}")
        return 1

    print(f"Reading catalog: {catalog_path}")

    try:
        conn = connect_catalog(catalog_path)
        
        if args.count:
            count = get_image_count(conn)
            print(f"Total images: {count}")
            conn.close()
            return 0
        
        if args.id:
            record = get_image_by_id(conn, args.id)
            if record:
                print(json.dumps(record, indent=2))
            else:
                print(f"Image with ID {args.id} not found")
            conn.close()
            return 0
        
        records = get_image_records(conn, limit=args.limit)
        print(f"Retrieved {len(records)} image records")
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump(records, f, indent=2)
            print(f"Output written to: {args.output}")
        else:
            print(json.dumps(records[:3], indent=2))
            if len(records) > 3:
                print(f"... and {len(records) - 3} more records")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
