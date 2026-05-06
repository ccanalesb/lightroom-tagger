import os
import sqlite3
from collections.abc import Sequence
from datetime import datetime

from .catalog import library_write


def list_clip_embedded_catalog_keys_newest_first(db: sqlite3.Connection) -> list[str]:
    """Catalog keys with CLIP embeddings, ordered newest-to-oldest for batch jobs."""
    rows = db.execute(
        """
        SELECT e.image_key AS key, i.date_taken AS date_taken
        FROM image_clip_embeddings e
        INNER JOIN images i ON i.key = e.image_key
        ORDER BY i.date_taken DESC, i.key DESC
        """
    ).fetchall()
    return [str(r["key"]) for r in rows if r["key"]]


def clear_catalog_similarity_results(db: sqlite3.Connection) -> None:
    """Clear derived catalog similarity job output."""
    db.execute("DELETE FROM catalog_similarity_candidates")
    db.execute("DELETE FROM catalog_similarity_groups")
    db.commit()


def insert_catalog_similarity_group(
    db: sqlite3.Connection,
    *,
    seed_key: str,
    candidates: Sequence[dict],
    job_id: str | None = None,
) -> int:
    """Persist one catalog similarity group and its ranked candidate rows."""
    if not candidates:
        raise ValueError("candidates must not be empty")
    best_similarity = max(float(c.get("similarity") or 0.0) for c in candidates)
    cur = db.execute(
        """
        INSERT INTO catalog_similarity_groups
            (seed_key, candidate_count, best_similarity, job_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            seed_key,
            len(candidates),
            best_similarity,
            job_id,
            datetime.now().isoformat(),
        ),
    )
    group_id = int(cur.lastrowid)
    db.executemany(
        """
        INSERT INTO catalog_similarity_candidates
            (group_id, candidate_key, similarity, rank, why_matched)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                group_id,
                str(c["candidate_key"]),
                float(c["similarity"]),
                int(c.get("rank") or idx + 1),
                str(c.get("why_matched") or ""),
            )
            for idx, c in enumerate(candidates)
        ],
    )
    db.commit()
    return group_id






# ---------------------------------------------------------------------------
# Vision cache
# ---------------------------------------------------------------------------

VISION_CACHE_OVERSIZED_SENTINEL = "__oversized__"


def init_vision_cache_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def init_vision_comparisons_table(db: sqlite3.Connection):
    """No-op: table is created in init_database."""
    pass


def get_vision_cached_image(db: sqlite3.Connection, catalog_key: str) -> dict | None:
    """Get cached compressed image by catalog key."""
    row = db.execute(
        "SELECT * FROM vision_cache WHERE key = ?", (catalog_key,)
    ).fetchone()
    return dict(row) if row else None


def store_vision_cached_image(db: sqlite3.Connection, catalog_key: str,
                               compressed_path: str, phash: str | None,
                               original_mtime: float) -> bool:
    """Store compressed image info in vision cache.

    Routed through :func:`library_write` because this runs on the describe
    worker hot path and previously raced with other workers' commits.
    """
    with library_write(db):
        db.execute("""
            INSERT INTO vision_cache (key, compressed_path, phash, compressed_at, original_mtime)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                compressed_path=excluded.compressed_path, phash=excluded.phash,
                compressed_at=excluded.compressed_at, original_mtime=excluded.original_mtime
        """, (catalog_key, compressed_path, phash, datetime.now().isoformat(), original_mtime))
    return True


def is_vision_cache_valid(db: sqlite3.Connection, catalog_key: str,
                           original_path: str) -> bool:
    """Check if cached image is still valid (mtime unchanged)."""
    cached = get_vision_cached_image(db, catalog_key)
    if not cached:
        return False
    comp = cached.get('compressed_path') or ''

    from lightroom_tagger.core.analyzer import RAW_EXTENSIONS, VIDEO_EXTENSIONS

    ext = os.path.splitext(original_path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return False

    if ext in RAW_EXTENSIONS:
        if comp == original_path:
            return False
        if comp == VISION_CACHE_OVERSIZED_SENTINEL:
            return False

    if comp == VISION_CACHE_OVERSIZED_SENTINEL:
        try:
            current_mtime = os.path.getmtime(original_path)
            return cached.get('original_mtime') == current_mtime
        except OSError:
            return False

    if not comp or not os.path.exists(comp):
        return False
    try:
        current_mtime = os.path.getmtime(original_path)
        return cached.get('original_mtime') == current_mtime
    except OSError:
        return False


def get_cache_stats(db: sqlite3.Connection) -> dict:
    """Get vision cache statistics."""
    total = db.execute("SELECT COUNT(*) as cnt FROM images").fetchone()['cnt']
    cached = db.execute("SELECT COUNT(*) as cnt FROM vision_cache").fetchone()['cnt']

    cache_size_bytes = 0
    rows = db.execute("SELECT compressed_path FROM vision_cache").fetchall()
    for row in rows:
        path = row.get('compressed_path', '')
        if path and os.path.exists(path):
            cache_size_bytes += os.path.getsize(path)

    return {
        'total': total,
        'cached': cached,
        'missing': total - cached,
        'cache_size_mb': cache_size_bytes / (1024 * 1024),
    }


# ---------------------------------------------------------------------------
# Vision comparisons
# ---------------------------------------------------------------------------

def get_vision_comparison(db: sqlite3.Connection, catalog_key: str,
                           insta_key: str) -> dict | None:
    """Get cached vision comparison result."""
    row = db.execute(
        "SELECT * FROM vision_comparisons WHERE catalog_key = ? AND insta_key = ?",
        (catalog_key, insta_key)
    ).fetchone()
    return dict(row) if row else None


def store_vision_comparison(db: sqlite3.Connection, catalog_key: str, insta_key: str,
                            result: str, vision_score: float, model_used: str) -> bool:
    """Store vision comparison result in cache. Never expires."""
    db.execute("""
        INSERT INTO vision_comparisons (catalog_key, insta_key, result, vision_score,
            compared_at, model_used)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(catalog_key, insta_key) DO UPDATE SET
            result=excluded.result, vision_score=excluded.vision_score,
            compared_at=excluded.compared_at, model_used=excluded.model_used
    """, (catalog_key, insta_key, result, vision_score,
          datetime.now().isoformat(), model_used))
    db.commit()
    return True
