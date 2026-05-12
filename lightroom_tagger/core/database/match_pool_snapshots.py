"""Persistence helpers for evaluated Instagram comparison-pool snapshots."""

from __future__ import annotations

import json
import sqlite3


def insert_comparison_pool_snapshot(
    db: sqlite3.Connection,
    *,
    insta_key: str,
    source_job_id: str | None,
    threshold: float,
    clip_top_k: int,
    weights: dict,
    vision_candidates: list[dict],
    results: list[dict],
) -> int:
    """Persist one evaluated comparison pool and its ranked candidate evidence."""
    path_by_catalog = {
        str(candidate["key"]): candidate.get("local_path")
        for candidate in vision_candidates
        if candidate.get("key") is not None
    }
    cur = db.execute(
        """
        INSERT INTO comparison_pool_snapshots (
            insta_key, source_job_id, threshold, clip_top_k, weights_json,
            candidate_count
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            insta_key,
            source_job_id,
            float(threshold),
            int(clip_top_k),
            json.dumps(weights, sort_keys=True),
            len(results),
        ),
    )
    snapshot_id = int(cur.lastrowid)
    db.executemany(
        """
        INSERT INTO comparison_pool_snapshot_candidates (
            snapshot_id, rank, catalog_key, total_score, phash_distance,
            phash_score, desc_similarity, vision_result, vision_score,
            vision_reasoning, model_used, rate_limited, debug_resolved_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                snapshot_id,
                idx,
                str(result["catalog_key"]),
                result.get("total_score"),
                result.get("phash_distance"),
                result.get("phash_score"),
                result.get("desc_similarity"),
                result.get("vision_result"),
                result.get("vision_score"),
                result.get("vision_reasoning"),
                result.get("model_used"),
                int(bool(result.get("rate_limited"))),
                path_by_catalog.get(str(result["catalog_key"])),
            )
            for idx, result in enumerate(results)
        ],
    )
    db.commit()
    return snapshot_id


def fetch_comparison_pool_snapshot_bundle(
    db: sqlite3.Connection,
    insta_key: str,
    *,
    source_job_id: str | None = None,
) -> tuple[dict | None, list[dict]]:
    """Fetch the latest snapshot parent and rank-ordered children for an Instagram row."""
    if source_job_id is None:
        parent = db.execute(
            """
            SELECT *
            FROM comparison_pool_snapshots
            WHERE insta_key = ?
            ORDER BY captured_at DESC, snapshot_id DESC
            LIMIT 1
            """,
            (insta_key,),
        ).fetchone()
    else:
        parent = db.execute(
            """
            SELECT *
            FROM comparison_pool_snapshots
            WHERE insta_key = ? AND source_job_id = ?
            ORDER BY captured_at DESC, snapshot_id DESC
            LIMIT 1
            """,
            (insta_key, source_job_id),
        ).fetchone()

    if parent is None:
        return None, []

    parent_dict = dict(parent)
    children = db.execute(
        """
        SELECT *
        FROM comparison_pool_snapshot_candidates
        WHERE snapshot_id = ?
        ORDER BY rank ASC
        """,
        (parent_dict["snapshot_id"],),
    ).fetchall()
    return parent_dict, [dict(child) for child in children]
