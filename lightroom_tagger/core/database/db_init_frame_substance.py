"""Frame substance table migrations (#295)."""

from __future__ import annotations

import sqlite3


def _migrate_image_frame_substance(conn: sqlite3.Connection) -> None:
    """Persist per-image frame substance verdicts (overwritten each detection run)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS image_frame_substance (
            image_key TEXT PRIMARY KEY,
            verdict TEXT NOT NULL CHECK (verdict IN ('void','illegible','ok','unknown')),
            unknown_reason TEXT NOT NULL DEFAULT '',
            black_frac_25 REAL,
            blown_frac_235 REAL,
            lap_var REAL,
            tile_max REAL,
            entropy REAL,
            detector_version TEXT NOT NULL,
            judged_at TEXT NOT NULL DEFAULT (datetime('now')),
            run_id INTEGER NOT NULL
        );
        """
    )


def _migrate_frame_substance_overrides(conn: sqlite3.Connection) -> None:
    """Persist user overrides that restore ranking eligibility across re-runs."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS frame_substance_overrides (
            image_key TEXT PRIMARY KEY,
            overridden_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_frame_substance_overrides_overridden_at
            ON frame_substance_overrides(overridden_at DESC);
        """
    )


def _migrate_frame_substance_runs(conn: sqlite3.Connection) -> None:
    """Log frame substance detection runs and blast-radius guard outcomes."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS frame_substance_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            detector_version TEXT NOT NULL,
            count_void INTEGER NOT NULL DEFAULT 0,
            count_illegible INTEGER NOT NULL DEFAULT 0,
            count_ok INTEGER NOT NULL DEFAULT 0,
            count_unknown INTEGER NOT NULL DEFAULT 0,
            breached INTEGER NOT NULL DEFAULT 0,
            breach_reason TEXT NOT NULL DEFAULT ''
        );
        """
    )
