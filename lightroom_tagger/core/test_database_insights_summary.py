"""Tests for insights landing-page summary queries."""

from __future__ import annotations

from datetime import datetime, timezone

from lightroom_tagger.core.database import (
    get_insights_summary,
    init_database,
    insert_image_score,
    insert_perspective,
    store_image,
)


def _score(conn, image_key: str, slug: str, score: int) -> None:
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": score,
            "rationale": "r",
            "model_used": "m",
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()


def test_insights_summary_counts_and_coverage(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    conn.execute("DELETE FROM perspectives")
    conn.commit()

    insert_perspective(
        conn,
        slug="alpha",
        display_name="Alpha",
        prompt_markdown="# Alpha",
        active=True,
    )
    insert_perspective(
        conn,
        slug="beta",
        display_name="Beta",
        prompt_markdown="# Beta",
        active=True,
    )
    insert_perspective(
        conn,
        slug="legacy",
        display_name="Legacy",
        prompt_markdown="# Legacy",
        active=False,
    )
    conn.commit()

    k1 = store_image(conn, {"date_taken": "2024-01-01", "filename": "a.jpg"})
    k2 = store_image(conn, {"date_taken": "2024-01-02", "filename": "b.jpg"})
    k3 = store_image(conn, {"date_taken": "2024-01-03", "filename": "c.jpg"})
    conn.commit()

    _score(conn, k1, "alpha", 9)
    _score(conn, k1, "beta", 8)
    _score(conn, k2, "alpha", 7)
    # k3 unscored on both active perspectives

    conn.execute(
        """
        INSERT INTO image_stacks (representative_key, stack_size)
        VALUES (?, 2)
        """,
        (k1,),
    )
    stack_id = conn.execute("SELECT stack_id FROM image_stacks").fetchone()["stack_id"]
    conn.execute(
        "INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?), (?, ?)",
        (stack_id, k1, stack_id, k2),
    )
    conn.commit()

    summary = get_insights_summary(conn)

    assert summary["catalog_images"] == 3
    assert summary["scoring_9_plus"] == 1
    assert summary["burst_stacks"] == 1
    assert summary["pending_stack_suggestions"] == 0
    assert summary["unscored_on_active_perspectives"] == 2  # k2 missing beta, k3 missing both
    assert summary["no_current_score"] == 1

    by_slug = {row["slug"]: row for row in summary["perspective_coverage"]}
    assert by_slug["alpha"]["scored_images"] == 2
    assert by_slug["beta"]["scored_images"] == 1
    assert by_slug["legacy"]["active"] is False
    assert by_slug["legacy"]["scored_images"] == 0

    conn.close()
