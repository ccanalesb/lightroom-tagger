"""Tests for ``image_scores`` / ``perspectives`` schema and helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from lightroom_tagger.core.database import (
    get_current_scores_for_image,
    init_database,
    insert_image_score,
    supersede_previous_current_scores,
)


def test_should_keep_only_latest_prompt_version_as_current(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))

    conn.execute(
        """
        INSERT INTO perspectives (slug, display_name, description, prompt_markdown)
        VALUES ('test_persp', 'Test perspective', '', '')
        """
    )
    conn.commit()

    image_key = "2020-01-01_foo.jpg"
    image_type = "catalog"
    perspective_slug = "test_persp"
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": image_type,
            "perspective_slug": perspective_slug,
            "score": 4,
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()

    supersede_previous_current_scores(
        conn, image_key, image_type, perspective_slug, "v2"
    )
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": image_type,
            "perspective_slug": perspective_slug,
            "score": 7,
            "prompt_version": "v2",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()

    rows = get_current_scores_for_image(conn, image_key, image_type)
    assert len(rows) == 1
    assert rows[0]["prompt_version"] == "v2"
    assert rows[0]["score"] == 7
