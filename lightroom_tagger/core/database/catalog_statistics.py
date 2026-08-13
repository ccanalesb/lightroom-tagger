"""Read helpers for catalog-wide statistics and NL-search schema facets."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogSchemaFacets:
    """Aggregated catalog statistics for NL search / schema discovery."""

    total: int
    analyzed: int
    has_rep: int
    rated: int
    posted: int
    with_mood: int
    with_colors: int
    color_labels: dict[str, int]
    top_moods: list[str]
    date_range: dict[str, str]
    perspectives: list[str]


def _scalar_count(db: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = db.execute(sql, params).fetchone()
    return int(row["cnt"]) if row else 0


def get_posted_images_count(db: sqlite3.Connection) -> int:
    """Count catalog images marked as posted to Instagram."""
    return _scalar_count(
        db, "SELECT COUNT(*) AS cnt FROM images WHERE instagram_posted = 1"
    )


def count_catalog_images_with_descriptions(db: sqlite3.Connection) -> int:
    """Count catalog images with an AI description row."""
    return _scalar_count(
        db,
        "SELECT COUNT(*) AS cnt FROM image_descriptions WHERE image_type = 'catalog'",
    )


def count_catalog_images_with_repetition(db: sqlite3.Connection) -> int:
    """Count catalog descriptions flagged with visual repetition."""
    return _scalar_count(
        db,
        "SELECT COUNT(*) AS cnt FROM image_descriptions "
        "WHERE image_type = 'catalog' AND has_repetition = 1",
    )


def count_rated_catalog_images(db: sqlite3.Connection) -> int:
    """Count catalog images with any Lightroom star rating."""
    return _scalar_count(db, "SELECT COUNT(*) AS cnt FROM images WHERE rating >= 1")


def count_images_with_mood_tags(db: sqlite3.Connection) -> int:
    """Count catalog descriptions that carry non-empty mood tags."""
    return _scalar_count(
        db,
        "SELECT COUNT(*) AS cnt FROM image_descriptions "
        "WHERE image_type = 'catalog' AND mood_tags IS NOT NULL "
        "AND mood_tags NOT IN ('[]', 'null', '')",
    )


def count_images_with_dominant_colors(db: sqlite3.Connection) -> int:
    """Count catalog descriptions that carry non-empty dominant colors."""
    return _scalar_count(
        db,
        "SELECT COUNT(*) AS cnt FROM image_descriptions "
        "WHERE image_type = 'catalog' AND dominant_colors IS NOT NULL "
        "AND dominant_colors NOT IN ('[]', 'null', '')",
    )


def get_color_label_statistics(db: sqlite3.Connection) -> dict[str, int]:
    """Lightroom color-label counts keyed by lowercased label."""
    rows = db.execute(
        "SELECT LOWER(color_label) AS lbl, COUNT(*) AS cnt FROM images "
        "WHERE color_label IS NOT NULL AND color_label != '' "
        "GROUP BY LOWER(color_label)"
    ).fetchall()
    return {str(r["lbl"]): int(r["cnt"]) for r in rows if r["lbl"]}


def get_mood_tags_sample(db: sqlite3.Connection, *, limit: int = 2000) -> list[str]:
    """Sample raw ``mood_tags`` JSON column values from catalog descriptions."""
    rows = db.execute(
        "SELECT mood_tags FROM image_descriptions "
        "WHERE image_type = 'catalog' AND mood_tags NOT IN ('[]', 'null', '') "
        "AND mood_tags IS NOT NULL "
        "LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [str(r["mood_tags"]) for r in rows if r["mood_tags"]]


def _top_moods_from_samples(samples: list[str], *, top_n: int = 40) -> list[str]:
    mood_counts: dict[str, int] = {}
    for raw in samples:
        try:
            for tag in json.loads(raw):
                if isinstance(tag, str):
                    mood_counts[tag] = mood_counts.get(tag, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    return sorted(mood_counts, key=lambda t: -mood_counts[t])[:top_n]


def get_catalog_date_range(db: sqlite3.Connection) -> dict[str, str]:
    """Earliest and latest ``date_taken`` values (YYYY-MM-DD prefixes)."""
    row = db.execute(
        "SELECT MIN(date_taken) AS min_d, MAX(date_taken) AS max_d "
        "FROM images WHERE date_taken IS NOT NULL"
    ).fetchone()
    if not row:
        return {"earliest": "", "latest": ""}
    min_d = row["min_d"] or ""
    max_d = row["max_d"] or ""
    return {
        "earliest": str(min_d)[:10] if min_d else "",
        "latest": str(max_d)[:10] if max_d else "",
    }


def get_catalog_months(db: sqlite3.Connection) -> list[str]:
    """Distinct YYYYMM months from catalog ``date_taken``, newest first."""
    rows = db.execute(
        """
        SELECT DISTINCT strftime('%Y%m', date_taken) AS month
        FROM images
        WHERE date_taken IS NOT NULL
        ORDER BY month DESC
        """
    ).fetchall()
    return [str(r["month"]) for r in rows if r["month"]]


def catalog_schema_facets(db: sqlite3.Connection) -> CatalogSchemaFacets:
    """Compose catalog statistics used by NL search schema discovery."""
    total = _scalar_count(db, "SELECT COUNT(*) AS cnt FROM images")
    perspectives_rows = db.execute(
        "SELECT DISTINCT perspective_slug FROM image_scores "
        "WHERE is_current = 1 ORDER BY perspective_slug"
    ).fetchall()
    perspectives = [str(r["perspective_slug"]) for r in perspectives_rows]
    mood_samples = get_mood_tags_sample(db)
    return CatalogSchemaFacets(
        total=total,
        analyzed=count_catalog_images_with_descriptions(db),
        has_rep=count_catalog_images_with_repetition(db),
        rated=count_rated_catalog_images(db),
        posted=get_posted_images_count(db),
        with_mood=count_images_with_mood_tags(db),
        with_colors=count_images_with_dominant_colors(db),
        color_labels=get_color_label_statistics(db),
        top_moods=_top_moods_from_samples(mood_samples),
        date_range=get_catalog_date_range(db),
        perspectives=perspectives,
    )
