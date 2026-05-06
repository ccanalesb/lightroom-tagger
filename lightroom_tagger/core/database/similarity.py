"""Catalog similarity job DB helpers."""

import sqlite3
from collections.abc import Sequence
from datetime import datetime


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
