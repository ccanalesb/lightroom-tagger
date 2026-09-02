"""Frame substance verdict storage and read helpers (#295)."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from .catalog import library_write
from .frame_substance_sql import FLAGGED_VERDICTS
from .vision_cache import get_vision_cached_image

_INSERT_RUN_SQL = """
    INSERT INTO frame_substance_runs (started_at, detector_version)
    VALUES (?, ?)
"""

_FINISH_RUN_SQL = """
    UPDATE frame_substance_runs
    SET finished_at = ?,
        count_void = ?,
        count_illegible = ?,
        count_ok = ?,
        count_unknown = ?,
        breached = ?,
        breach_reason = ?
    WHERE run_id = ?
"""

_UPSERT_VERDICT_SQL = """
    INSERT INTO image_frame_substance (
        image_key, verdict, unknown_reason,
        black_frac_25, blown_frac_235, lap_var, tile_max, entropy,
        detector_version, judged_at, run_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(image_key) DO UPDATE SET
        verdict = excluded.verdict,
        unknown_reason = excluded.unknown_reason,
        black_frac_25 = excluded.black_frac_25,
        blown_frac_235 = excluded.blown_frac_235,
        lap_var = excluded.lap_var,
        tile_max = excluded.tile_max,
        entropy = excluded.entropy,
        detector_version = excluded.detector_version,
        judged_at = excluded.judged_at,
        run_id = excluded.run_id
"""


def insert_frame_substance_run(db: sqlite3.Connection, *, detector_version: str) -> int:
    """Insert a started detection run and return its ``run_id``."""
    started_at = datetime.now(timezone.utc).isoformat()
    with library_write(db):
        cur = db.execute(_INSERT_RUN_SQL, (started_at, detector_version))
        run_id = int(cur.lastrowid)
    return run_id


def finish_frame_substance_run(
    db: sqlite3.Connection,
    run_id: int,
    *,
    count_void: int,
    count_illegible: int,
    count_ok: int,
    count_unknown: int,
    breached: bool,
    breach_reason: str = "",
) -> None:
    """Finalize a detection run with per-verdict counts and breach metadata."""
    finished_at = datetime.now(timezone.utc).isoformat()
    with library_write(db):
        db.execute(
            _FINISH_RUN_SQL,
            (
                finished_at,
                int(count_void),
                int(count_illegible),
                int(count_ok),
                int(count_unknown),
                1 if breached else 0,
                breach_reason or "",
                int(run_id),
            ),
        )


def upsert_frame_substance_verdict(
    db: sqlite3.Connection,
    *,
    image_key: str,
    verdict: str,
    unknown_reason: str,
    black_frac_25: float | None,
    blown_frac_235: float | None,
    lap_var: float | None,
    tile_max: float | None,
    entropy: float | None,
    detector_version: str,
    run_id: int,
) -> None:
    """Overwrite one image's substance verdict row."""
    judged_at = datetime.now(timezone.utc).isoformat()
    with library_write(db):
        db.execute(
            _UPSERT_VERDICT_SQL,
            (
                image_key,
                verdict,
                unknown_reason or "",
                black_frac_25,
                blown_frac_235,
                lap_var,
                tile_max,
                entropy,
                detector_version,
                judged_at,
                int(run_id),
            ),
        )


def upsert_frame_substance_verdicts(
    db: sqlite3.Connection,
    rows: Sequence[Mapping[str, object]],
) -> None:
    """Batch overwrite substance verdict rows inside one write transaction."""
    if not rows:
        return
    params = [
        (
            str(row["image_key"]),
            str(row["verdict"]),
            str(row.get("unknown_reason") or ""),
            row.get("black_frac_25"),
            row.get("blown_frac_235"),
            row.get("lap_var"),
            row.get("tile_max"),
            row.get("entropy"),
            str(row["detector_version"]),
            str(row.get("judged_at") or datetime.now(timezone.utc).isoformat()),
            int(row["run_id"]),
        )
        for row in rows
    ]
    with library_write(db):
        db.executemany(_UPSERT_VERDICT_SQL, params)


def get_frame_substance_verdict(db: sqlite3.Connection, image_key: str) -> dict | None:
    """Return one detached verdict row, or ``None`` when unjudged."""
    row = db.execute(
        "SELECT * FROM image_frame_substance WHERE image_key = ?",
        (image_key,),
    ).fetchone()
    return dict(row) if row else None


def load_frame_substance_verdict_map(db: sqlite3.Connection) -> dict[str, dict]:
    """Return all current verdict rows keyed by ``image_key``."""
    rows = db.execute("SELECT * FROM image_frame_substance").fetchall()
    return {str(r["image_key"]): dict(r) for r in rows}


def get_latest_finished_frame_substance_run(db: sqlite3.Connection) -> dict | None:
    """Return the most recent completed run row, if any."""
    row = db.execute(
        """
        SELECT *
        FROM frame_substance_runs
        WHERE finished_at IS NOT NULL
        ORDER BY run_id DESC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def count_frame_substance_by_verdict(db: sqlite3.Connection) -> dict[str, int]:
    """Count current verdict rows grouped by ``verdict``."""
    rows = db.execute(
        """
        SELECT verdict, COUNT(*) AS c
        FROM image_frame_substance
        GROUP BY verdict
        """
    ).fetchall()
    return {str(r["verdict"]): int(r["c"]) for r in rows}


def count_frame_substance_by_unknown_reason(db: sqlite3.Connection) -> dict[str, int]:
    """Count ``unknown`` rows grouped by ``unknown_reason``."""
    rows = db.execute(
        """
        SELECT unknown_reason, COUNT(*) AS c
        FROM image_frame_substance
        WHERE verdict = 'unknown'
        GROUP BY unknown_reason
        """
    ).fetchall()
    return {str(r["unknown_reason"]): int(r["c"]) for r in rows}


def count_frame_substance_flagged_net_of_overrides(db: sqlite3.Connection) -> int:
    """Count flagged verdict rows (``void`` + ``illegible``) minus user overrides."""
    row = db.execute(
        """
        SELECT COUNT(*) AS c
        FROM image_frame_substance fs
        WHERE fs.verdict IN ('void', 'illegible')
          AND NOT EXISTS (
              SELECT 1
              FROM frame_substance_overrides o
              WHERE o.image_key = fs.image_key
          )
        """
    ).fetchone()
    return int(row["c"])


def count_frame_substance_never_judged(db: sqlite3.Connection) -> int:
    """Count catalog images with no substance verdict row."""
    row = db.execute(
        """
        SELECT COUNT(*) AS c
        FROM images i
        WHERE NOT EXISTS (
            SELECT 1
            FROM image_frame_substance fs
            WHERE fs.image_key = i.key
        )
        """
    ).fetchone()
    return int(row["c"])


def insert_frame_substance_override(db: sqlite3.Connection, image_key: str) -> None:
    """Persist a user override that restores ranking eligibility."""
    with library_write(db):
        db.execute(
            """
            INSERT INTO frame_substance_overrides (image_key)
            VALUES (?)
            ON CONFLICT(image_key) DO NOTHING
            """,
            (image_key,),
        )


def delete_frame_substance_override(db: sqlite3.Connection, image_key: str) -> bool:
    """Remove a user override. Returns True when a row was deleted."""
    with library_write(db):
        cur = db.execute(
            "DELETE FROM frame_substance_overrides WHERE image_key = ?",
            (image_key,),
        )
    return cur.rowcount > 0


def has_frame_substance_override(db: sqlite3.Connection, image_key: str) -> bool:
    """Return whether the user has overridden the detector for ``image_key``."""
    row = db.execute(
        "SELECT 1 AS o FROM frame_substance_overrides WHERE image_key = ?",
        (image_key,),
    ).fetchone()
    return row is not None


def is_frame_substance_flagged(db: sqlite3.Connection, image_key: str) -> bool:
    """True when the image has a void/illegible verdict and no user override."""
    verdict = get_frame_substance_verdict(db, image_key)
    if verdict is None:
        return False
    if verdict["verdict"] not in FLAGGED_VERDICTS:
        return False
    return not has_frame_substance_override(db, image_key)


def is_frame_substance_verdict_stale(
    db: sqlite3.Connection,
    image_key: str,
    *,
    verdict_row: dict | None = None,
) -> bool:
    """True when the preview cache is newer than the stored verdict timestamp."""
    verdict = (
        verdict_row
        if verdict_row is not None
        else get_frame_substance_verdict(db, image_key)
    )
    if verdict is None:
        return False
    judged_at = verdict.get("judged_at")
    if not judged_at:
        return False
    cache = get_vision_cached_image(db, image_key)
    if not cache or not cache.get("compressed_at"):
        return False
    return str(cache["compressed_at"]) > str(judged_at)


def has_excusal_channel_hint(db: sqlite3.Connection, image_key: str) -> bool:
    """True when every active optional perspective scored ``not_attempted``."""
    optional_count = int(
        db.execute(
            "SELECT COUNT(*) AS c FROM perspectives WHERE optional = 1 AND active = 1"
        ).fetchone()["c"]
    )
    if optional_count == 0:
        return False
    excused_count = int(
        db.execute(
            """
            SELECT COUNT(*) AS c
            FROM perspectives p
            WHERE p.optional = 1
              AND p.active = 1
              AND EXISTS (
                  SELECT 1
                  FROM image_scores s
                  WHERE s.image_key = ?
                    AND s.image_type = 'catalog'
                    AND s.perspective_slug = p.slug
                    AND s.is_current = 1
                    AND s.not_attempted = 1
              )
            """,
            (image_key,),
        ).fetchone()["c"]
    )
    return excused_count == optional_count


def list_catalog_images_for_frame_substance(
    db: sqlite3.Connection,
    *,
    image_keys: set[str] | frozenset[str] | None = None,
    stale_only: bool = False,
) -> list[dict]:
    """Catalog images for detection, optionally scoped and staleness-filtered."""
    conditions: list[str] = []
    params: list[object] = []
    if image_keys is not None:
        if not image_keys:
            return []
        placeholders = ",".join("?" * len(image_keys))
        conditions.append(f"i.key IN ({placeholders})")
        params.extend(sorted(image_keys))
    if stale_only:
        conditions.append(
            "(fs.image_key IS NULL OR vc.compressed_at > fs.judged_at)"
        )
    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)
    rows = db.execute(
        f"""
        SELECT i.key AS image_key, vc.compressed_path AS compressed_path
        FROM images i
        LEFT JOIN vision_cache vc ON vc.key = i.key
        LEFT JOIN image_frame_substance fs ON fs.image_key = i.key
        {where}
        ORDER BY i.key ASC
        """,
        tuple(params),
    ).fetchall()
    return [dict(r) for r in rows]
