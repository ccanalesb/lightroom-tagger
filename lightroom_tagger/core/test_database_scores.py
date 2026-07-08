"""Tests for ``image_scores`` / ``perspectives`` schema and helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from lightroom_tagger.core.database import (
    get_current_scores_for_image,
    get_perspective_by_slug,
    init_database,
    insert_image_score,
    insert_perspective,
    list_score_history_for_perspective,
    query_catalog_images,
    seed_perspectives_from_prompts_dir,
    store_image,
    supersede_previous_current_scores,
    update_perspective,
)


def test_insert_image_score_persists_not_attempted(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    conn.execute(
        """
        INSERT INTO perspectives (slug, display_name, description, prompt_markdown)
        VALUES ('framing', 'Framing', '', '')
        """
    )
    conn.commit()
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    insert_image_score(
        conn,
        {
            "image_key": "2020-01-01_x.jpg",
            "image_type": "catalog",
            "perspective_slug": "framing",
            "score": 5,
            "rationale": "absent",
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
            "not_attempted": 1,
        },
    )
    conn.commit()
    rows = get_current_scores_for_image(conn, "2020-01-01_x.jpg", "catalog")
    assert len(rows) == 1
    assert rows[0]["not_attempted"] == 1


def test_insert_image_score_defaults_not_attempted_zero(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    conn.execute(
        """
        INSERT INTO perspectives (slug, display_name, description, prompt_markdown)
        VALUES ('baseline_persp', 'Baseline', '', '')
        """
    )
    conn.commit()
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    insert_image_score(
        conn,
        {
            "image_key": "2020-01-01_y.jpg",
            "image_type": "catalog",
            "perspective_slug": "baseline_persp",
            "score": 7,
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()
    rows = get_current_scores_for_image(conn, "2020-01-01_y.jpg", "catalog")
    assert rows[0]["not_attempted"] == 0


def test_insert_perspective_derives_optional_from_markdown_marker(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    insert_perspective(
        conn, slug="baseline", display_name="Baseline", prompt_markdown="# no marker"
    )
    insert_perspective(
        conn,
        slug="opt",
        display_name="Opt",
        prompt_markdown="<!-- optional: true -->\n# Framing",
    )
    conn.commit()
    assert get_perspective_by_slug(conn, "baseline")["optional"] == 0
    assert get_perspective_by_slug(conn, "opt")["optional"] == 1


def test_update_perspective_re_derives_optional_when_markdown_written(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    insert_perspective(
        conn, slug="p", display_name="P", prompt_markdown="# plain"
    )
    conn.commit()
    assert get_perspective_by_slug(conn, "p")["optional"] == 0

    # Writing markdown with the marker flips optional on.
    update_perspective(conn, "p", prompt_markdown="<!-- optional: true -->\n# now optional")
    conn.commit()
    assert get_perspective_by_slug(conn, "p")["optional"] == 1

    # Writing markdown without the marker un-sets optional (marker always wins).
    update_perspective(conn, "p", prompt_markdown="# marker removed")
    conn.commit()
    assert get_perspective_by_slug(conn, "p")["optional"] == 0


def test_update_perspective_leaves_optional_untouched_without_markdown(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    insert_perspective(
        conn, slug="p", display_name="P", prompt_markdown="<!-- optional: true -->\n# opt"
    )
    conn.commit()
    assert get_perspective_by_slug(conn, "p")["optional"] == 1

    # Editing a non-markdown field must not disturb the derived optional flag.
    update_perspective(conn, "p", display_name="Renamed")
    conn.commit()
    row = get_perspective_by_slug(conn, "p")
    assert row["display_name"] == "Renamed"
    assert row["optional"] == 1


def test_seed_detects_optional_marker(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    conn.execute("DELETE FROM perspectives")
    conn.commit()
    prompts_dir = tmp_path / "perspectives"
    prompts_dir.mkdir()
    (prompts_dir / "framing.md").write_text(
        "<!-- optional: true -->\n# Framing\nEvaluate the framing device.\n",
        encoding="utf-8",
    )
    (prompts_dir / "street.md").write_text(
        "# Street\nEvaluate geometry.\n", encoding="utf-8"
    )
    seed_perspectives_from_prompts_dir(conn, str(prompts_dir))
    conn.commit()
    assert get_perspective_by_slug(conn, "framing")["optional"] == 1
    assert get_perspective_by_slug(conn, "street")["optional"] == 0


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


def test_list_score_history_orders_newest_scored_at_first(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))

    conn.execute(
        """
        INSERT INTO perspectives (slug, display_name, description, prompt_markdown)
        VALUES ('hist_test', 'Hist test', '', '')
        """
    )
    conn.commit()

    image_key = "album/sub/k1.jpg"
    image_type = "catalog"
    perspective_slug = "hist_test"
    older = "2020-01-01T12:00:00+00:00"
    newer = "2024-06-01T12:00:00+00:00"

    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": image_type,
            "perspective_slug": perspective_slug,
            "score": 3,
            "prompt_version": "v1",
            "scored_at": older,
            "is_current": 0,
        },
    )
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": image_type,
            "perspective_slug": perspective_slug,
            "score": 8,
            "prompt_version": "v2",
            "scored_at": newer,
            "is_current": 1,
        },
    )
    conn.commit()

    rows = list_score_history_for_perspective(conn, image_key, image_type, perspective_slug)
    assert len(rows) == 2
    assert rows[0]["prompt_version"] == "v2"
    assert rows[0]["scored_at"] == newer
    assert rows[1]["prompt_version"] == "v1"
    assert rows[1]["scored_at"] == older


def test_query_catalog_images_sort_by_score_desc(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))

    conn.execute(
        """
        INSERT INTO perspectives (slug, display_name, description, prompt_markdown)
        VALUES ('catalog_q', 'Catalog Q', '', '')
        """
    )
    conn.commit()

    key_low = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "a_low.jpg",
            "rating": 1,
            "id": "1",
        },
    )
    key_high = store_image(
        conn,
        {
            "date_taken": "2024-06-01",
            "filename": "z_high.jpg",
            "rating": 5,
            "id": "2",
        },
    )
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    slug = "catalog_q"
    for key, score in ((key_low, 3), (key_high, 9)):
        insert_image_score(
            conn,
            {
                "image_key": key,
                "image_type": "catalog",
                "perspective_slug": slug,
                "score": score,
                "prompt_version": "v1",
                "scored_at": ts,
                "is_current": 1,
            },
        )
    conn.commit()

    rows, total = query_catalog_images(
        conn,
        score_perspective=slug,
        sort_by_score="desc",
        limit=50,
        offset=0,
    )
    assert total == 2
    assert [r["key"] for r in rows] == [key_high, key_low]
    assert rows[0]["catalog_perspective_score"] == 9
    assert rows[1]["catalog_perspective_score"] == 3


def test_query_catalog_images_min_score_excludes_lower(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))

    conn.execute(
        """
        INSERT INTO perspectives (slug, display_name, description, prompt_markdown)
        VALUES ('min_q', 'Min Q', '', '')
        """
    )
    conn.commit()

    key_low = store_image(
        conn,
        {
            "date_taken": "2024-01-01",
            "filename": "low.jpg",
            "rating": 1,
            "id": "10",
        },
    )
    key_high = store_image(
        conn,
        {
            "date_taken": "2024-02-01",
            "filename": "high.jpg",
            "rating": 5,
            "id": "20",
        },
    )
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    slug = "min_q"
    insert_image_score(
        conn,
        {
            "image_key": key_low,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 5,
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    insert_image_score(
        conn,
        {
            "image_key": key_high,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": 9,
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    conn.commit()

    rows, total = query_catalog_images(
        conn,
        score_perspective=slug,
        min_score=8,
        limit=50,
        offset=0,
    )
    assert total == 1
    assert rows[0]["key"] == key_high
    assert rows[0]["catalog_perspective_score"] == 9


def test_score_read_helpers(tmp_path) -> None:
    from lightroom_tagger.core.database import (
        get_all_current_perspective_slugs,
        get_available_score_perspectives_for_image,
    )

    conn = init_database(str(tmp_path / "library.db"))
    key = store_image(conn, {"date_taken": "2024-01-01", "filename": "s.jpg"})
    for slug in ("alpha", "beta"):
        conn.execute(
            "INSERT INTO perspectives (slug, display_name, description, prompt_markdown) "
            "VALUES (?, ?, '', '')",
            (slug, slug.title()),
        )
    conn.commit()
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    insert_image_score(
        conn,
        {
            "image_key": key,
            "image_type": "catalog",
            "perspective_slug": "alpha",
            "score": 7,
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 1,
        },
    )
    insert_image_score(
        conn,
        {
            "image_key": key,
            "image_type": "catalog",
            "perspective_slug": "beta",
            "score": 6,
            "prompt_version": "v1",
            "scored_at": ts,
            "is_current": 0,
        },
    )
    conn.commit()

    assert get_all_current_perspective_slugs(conn) == ["alpha"]
    assert get_available_score_perspectives_for_image(conn, key) == ["alpha"]
    assert get_available_score_perspectives_for_image(conn, "missing") == []
    assert get_all_current_perspective_slugs(init_database(str(tmp_path / "e.db"))) == []
    conn.close()
