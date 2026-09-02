"""Tests for frame substance database helpers and migrations."""

from __future__ import annotations

from lightroom_tagger.core.database import (
    count_frame_substance_by_unknown_reason,
    count_frame_substance_by_verdict,
    get_frame_substance_verdict,
    init_database,
    insert_frame_substance_override,
    insert_frame_substance_run,
    is_frame_substance_flagged,
    store_image,
    upsert_frame_substance_verdict,
)
from lightroom_tagger.core.frame_substance_detector import detector_version


def test_frame_substance_migrations_are_idempotent(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn1 = init_database(str(db_path))
    key = store_image(
        conn1,
        {
            "date_taken": "2024-01-10",
            "filename": "a.jpg",
            "filepath": "/a.jpg",
        },
    )
    run_id = insert_frame_substance_run(conn1, detector_version=detector_version())
    upsert_frame_substance_verdict(
        conn1,
        image_key=key,
        verdict="ok",
        unknown_reason="",
        black_frac_25=0.0,
        blown_frac_235=0.0,
        lap_var=1.0,
        tile_max=10.0,
        entropy=5.0,
        detector_version=detector_version(),
        run_id=run_id,
    )
    insert_frame_substance_override(conn1, key)
    conn1.commit()
    conn1.close()

    conn2 = init_database(str(db_path))
    try:
        assert get_frame_substance_verdict(conn2, key)["verdict"] == "ok"
        assert count_frame_substance_by_verdict(conn2) == {"ok": 1}
        assert count_frame_substance_by_unknown_reason(conn2) == {}
        tables = {
            row["name"]
            for row in conn2.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "image_frame_substance" in tables
        assert "frame_substance_overrides" in tables
        assert "frame_substance_runs" in tables
    finally:
        conn2.close()


def test_is_frame_substance_flagged_respects_verdict_and_override(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    key = store_image(
        conn,
        {"date_taken": "2024-01-10", "filename": "a.jpg", "filepath": "/a.jpg"},
    )
    run_id = insert_frame_substance_run(conn, detector_version=detector_version())
    upsert_frame_substance_verdict(
        conn,
        image_key=key,
        verdict="void",
        unknown_reason="",
        black_frac_25=0.0,
        blown_frac_235=0.0,
        lap_var=1.0,
        tile_max=10.0,
        entropy=5.0,
        detector_version=detector_version(),
        run_id=run_id,
    )
    conn.commit()

    assert is_frame_substance_flagged(conn, key) is True
    insert_frame_substance_override(conn, key)
    conn.commit()
    assert is_frame_substance_flagged(conn, key) is False
    conn.close()
