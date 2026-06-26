"""Persistence helpers for evaluated Instagram comparison-pool snapshots."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from PIL import Image

from lightroom_tagger.core.analyzer.image_prep import RAW_EXTENSIONS


def _sha12(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _db_main_path(db: sqlite3.Connection) -> Path | None:
    try:
        for row in db.execute("PRAGMA database_list"):
            name = row["name"] if hasattr(row, "keys") else row[1]
            db_file = row["file"] if hasattr(row, "keys") else row[2]
            if name == "main" and db_file:
                return Path(str(db_file))
    except Exception:
        return None
    return None


def _default_snapshot_asset_dir(db: sqlite3.Connection) -> Path | None:
    db_path = _db_main_path(db)
    if db_path is None:
        return None
    return db_path.with_name(f"{db_path.name}.comparison_pool_assets")


def _snapshot_viewable_path(src: str | None) -> Path | None:
    if not src:
        return None
    path = Path(src)
    if not path.exists():
        return None
    ext = path.suffix.lower()
    if ext not in RAW_EXTENSIONS:
        return path
    for suffix in (".JPG", ".jpg", ".JPEG", ".jpeg"):
        sidecar = Path(src.rsplit(".", 1)[0] + suffix)
        if sidecar.exists():
            return sidecar
    return None


def _write_snapshot_asset(
    src: str | None,
    asset_dir: Path | None,
    asset_name: str,
    *,
    max_dim: int = 512,
    quality: int = 82,
) -> str | None:
    """Persist a report-ready JPEG evidence asset without doing RAW conversion."""
    viewable_path = _snapshot_viewable_path(src)
    if asset_dir is None or viewable_path is None:
        return None
    dest = asset_dir / asset_name
    if dest.exists():
        return str(dest)
    try:
        asset_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(viewable_path) as img:
            if img.width > max_dim or img.height > max_dim:
                ratio = max_dim / max(img.width, img.height)
                new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(dest, format="JPEG", quality=quality, optimize=True)
    except Exception:
        return None
    return str(dest)


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
    diagnostics: dict | None = None,
    dump_image_path: str | None = None,
    asset_dir: str | None = None,
) -> int:
    """Persist one evaluated comparison pool and its ranked candidate evidence."""
    evidence_asset_dir = Path(asset_dir) if asset_dir else _default_snapshot_asset_dir(db)
    path_by_catalog = {
        str(candidate["key"]): candidate.get("local_path")
        for candidate in vision_candidates
        if candidate.get("key") is not None
    }
    cur = db.execute(
        """
        INSERT INTO comparison_pool_snapshots (
            insta_key, source_job_id, threshold, clip_top_k, weights_json,
            candidate_count, diagnostics_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            insta_key,
            source_job_id,
            float(threshold),
            int(clip_top_k),
            json.dumps(weights, sort_keys=True),
            len(results),
            json.dumps(diagnostics or {}, sort_keys=True, default=str),
        ),
    )
    snapshot_id = int(cur.lastrowid)
    insta_asset_path = _write_snapshot_asset(
        dump_image_path,
        evidence_asset_dir,
        f"snapshot_{snapshot_id}_instagram_{_sha12(insta_key)}.jpg",
    )
    if insta_asset_path:
        db.execute(
            """
            UPDATE comparison_pool_snapshots
            SET insta_asset_path = ?
            WHERE snapshot_id = ?
            """,
            (insta_asset_path, snapshot_id),
        )
    db.executemany(
        """
        INSERT INTO comparison_pool_snapshot_candidates (
            snapshot_id, rank, catalog_key, total_score, phash_distance,
            phash_score, desc_similarity, vision_result, vision_score,
            vision_reasoning, model_used, rate_limited, source_path,
            source_available, asset_path, debug_resolved_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                int(bool(_snapshot_viewable_path(path_by_catalog.get(str(result["catalog_key"]))))),
                _write_snapshot_asset(
                    path_by_catalog.get(str(result["catalog_key"])),
                    evidence_asset_dir,
                    f"snapshot_{snapshot_id}_r{idx}_{_sha12(str(result['catalog_key']))}.jpg",
                ),
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
