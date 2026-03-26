import json
import sqlite3
from pathlib import Path

from lightroom_tagger.config import load_config

KEY_TABLES = [
    "Adobe_images",
    "AgLibraryFile",
    "AgLibraryFolder",
    "AgLibraryKeyword",
    "AgLibraryKeywordImage",
    "AgHarvestedExifMetadata",
    "AgLibraryIPTC",
]


def explore_catalog(catalog_path: str) -> dict:
    """Connect to catalog and return schema info."""
    schema = {"catalog_path": catalog_path, "tables": {}}

    try:
        conn = sqlite3.connect(catalog_path)
        schema["tables"] = get_key_tables(conn)
        conn.close()
    except sqlite3.Error as e:
        schema["error"] = str(e)

    return schema


def list_tables(conn: sqlite3.Connection) -> list[str]:
    """List all tables in the database."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    )
    return [row[0] for row in cursor.fetchall()]


def get_table_schema(conn: sqlite3.Connection, table_name: str) -> list[dict]:
    """Get column info for a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = []
    for row in cursor.fetchall():
        columns.append({
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default_value": row[4],
            "pk": bool(row[5]),
        })
    return columns


def get_key_tables(conn: sqlite3.Connection) -> dict:
    """Get schema for all key tables."""
    schema = {}
    for table_name in KEY_TABLES:
        try:
            schema[table_name] = get_table_schema(conn, table_name)
        except sqlite3.Error:
            schema[table_name] = None
    return schema


def export_schema_json(schema: dict, output_path: str):
    """Export schema to JSON file."""
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)


def print_schema_summary(schema: dict):
    """Print a human-readable summary of the schema."""
    print(f"Catalog: {schema.get('catalog_path', 'N/A')}")
    print("\nKey Tables Found:")
    print("-" * 60)

    tables = schema.get("tables", {})
    for table_name, columns in tables.items():
        if columns is None:
            print(f"  {table_name}: NOT FOUND")
        else:
            print(f"  {table_name}: {len(columns)} columns")
            for col in columns[:5]:
                pk_mark = " [PK]" if col["pk"] else ""
                print(f"    - {col['name']} ({col['type']}){pk_mark}")
            if len(columns) > 5:
                print(f"    ... and {len(columns) - 5} more columns")
    print("-" * 60)


def main():
    """CLI entry point for schema exploration."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Explore Lightroom catalog schema"
    )
    parser.add_argument(
        "--catalog", "-c", help="Path to Lightroom catalog (.lrcat)"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--output", "-o", help="Output JSON file path"
    )
    parser.add_argument(
        "--all-tables", "-a", action="store_true",
        help="List all tables instead of just key tables"
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

    print(f"Exploring catalog: {catalog_path}")

    try:
        conn = sqlite3.connect(catalog_path)

        if args.all_tables:
            tables = list_tables(conn)
            print(f"\nAll tables ({len(tables)}):")
            for table in tables:
                print(f"  - {table}")
        else:
            schema = explore_catalog(catalog_path)
            print_schema_summary(schema)

            if args.output:
                export_schema_json(schema, args.output)
                print(f"\nSchema exported to: {args.output}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
