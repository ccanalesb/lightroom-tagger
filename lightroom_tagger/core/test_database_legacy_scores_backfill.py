"""Tests for legacy description → image_scores backfill migration."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from lightroom_tagger.core.database import (
    get_current_scores_for_image,
    init_database,
    insert_image_score,
)
from lightroom_tagger.core.database.scores import (
    LEGACY_DESCRIPTION_PROMPT_VERSION,
    backfill_legacy_description_scores_from_blobs,
    migrate_legacy_description_scores_to_image_scores,
)


def _insert_description(
    conn,
    image_key: str,
    *,
    perspectives: dict,
    model_used: str = "ollama/llava",
    described_at: str = "2024-06-01T12:00:00+00:00",
) -> None:
    conn.execute(
        """
        INSERT INTO image_descriptions (
            image_key, image_type, summary, composition, perspectives,
            technical, subjects, best_perspective, model_used, described_at
        ) VALUES (?, 'catalog', '', '{}', ?, '{}', '[]', '', ?, ?)
        """,
        (image_key, json.dumps(perspectives), model_used, described_at),
    )
    conn.commit()


def test_backfill_gap_fill_preserves_real_score_and_fills_missing(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    image_key = "2024-01-01_gap.jpg"
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    _insert_description(
        conn,
        image_key,
        perspectives={
            "street": {"score": 6, "analysis": "blob street"},
            "documentary": {"score": 8, "analysis": "blob documentary"},
        },
    )
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": "street",
            "score": 9,
            "rationale": "real scoring pass",
            "model_used": "openai/gpt-4o",
            "prompt_version": "rubric-v2",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()

    inserted = backfill_legacy_description_scores_from_blobs(conn)
    conn.commit()

    assert inserted == 1
    rows = {r["perspective_slug"]: r for r in get_current_scores_for_image(conn, image_key)}
    assert rows["street"]["prompt_version"] == "rubric-v2"
    assert rows["street"]["score"] == 9
    assert rows["street"]["rationale"] == "real scoring pass"
    assert rows["documentary"]["prompt_version"] == LEGACY_DESCRIPTION_PROMPT_VERSION
    assert rows["documentary"]["score"] == 8
    assert rows["documentary"]["rationale"] == "blob documentary"
    assert rows["documentary"]["model_used"] == "ollama/llava"
    assert rows["documentary"]["scored_at"] == "2024-06-01T12:00:00+00:00"


def test_backfill_blob_only_image_gets_all_legacy_rows(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    image_key = "2024-02-01_blob_only.jpg"

    _insert_description(
        conn,
        image_key,
        perspectives={
            "street": {"score": 7, "analysis": "decisive moment"},
            "publisher": {"score": 5, "analysis": "middling"},
        },
    )

    inserted = backfill_legacy_description_scores_from_blobs(conn)
    conn.commit()

    assert inserted == 2
    rows = get_current_scores_for_image(conn, image_key)
    assert len(rows) == 2
    assert all(r["prompt_version"] == LEGACY_DESCRIPTION_PROMPT_VERSION for r in rows)
    assert all(r["is_current"] == 1 for r in rows)


def test_migration_idempotent_second_run_inserts_nothing(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    _insert_description(
        conn,
        "2024-03-01_once.jpg",
        perspectives={"street": {"score": 6, "analysis": "ok"}},
    )
    conn.execute("PRAGMA user_version = 5")
    conn.execute(
        "DELETE FROM image_scores WHERE prompt_version = ?",
        (LEGACY_DESCRIPTION_PROMPT_VERSION,),
    )
    conn.commit()

    migrate_legacy_description_scores_to_image_scores(conn)
    conn.commit()
    count_after_first = conn.execute("SELECT COUNT(*) AS n FROM image_scores").fetchone()["n"]
    uv_after_first = int(conn.execute("PRAGMA user_version").fetchone()["user_version"])
    assert uv_after_first == 6

    migrate_legacy_description_scores_to_image_scores(conn)
    conn.commit()
    count_after_second = conn.execute("SELECT COUNT(*) AS n FROM image_scores").fetchone()["n"]
    uv_after_second = int(conn.execute("PRAGMA user_version").fetchone()["user_version"])

    assert count_after_second == count_after_first
    assert uv_after_second == 6
