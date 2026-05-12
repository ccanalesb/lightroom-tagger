from unittest.mock import MagicMock, Mock, patch

from PIL import Image

from lightroom_tagger.core.database import init_database
from lightroom_tagger.scripts.match_instagram_dump import match_dump_media


@patch('lightroom_tagger.scripts.match_instagram_dump.init_catalog_table')
@patch('lightroom_tagger.scripts.match_instagram_dump.init_instagram_dump_table')
@patch('lightroom_tagger.scripts.match_instagram_dump.get_unprocessed_dump_media')
@patch('lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date')
@patch('lightroom_tagger.scripts.match_instagram_dump.mark_dump_media_attempted')
def test_media_key_filters_to_single_image(
    mock_mark_attempted, mock_find, mock_get_unprocessed, mock_init_insta, mock_init_catalog
):
    """When media_key is provided, only that image is processed."""
    db = MagicMock()
    target_row = {
        'media_key': '202603/12345',
        'file_path': '/tmp/test.jpg',
        'caption': '',
        'date_folder': '202603',
    }
    db.execute.return_value.fetchone.return_value = target_row

    mock_find.return_value = []

    stats, matches = match_dump_media(db, media_key='202603/12345')

    mock_get_unprocessed.assert_not_called()
    assert stats['processed'] == 1


def test_match_dump_media_persists_comparison_pool_snapshot(tmp_path):
    """A scored but unmatched media row persists the full comparison pool."""
    insta_path = tmp_path / "insta.png"
    catalog_1 = tmp_path / "catalog-1.png"
    catalog_2 = tmp_path / "catalog-2.png"
    Image.new("RGB", (1, 1), color=(255, 0, 0)).save(insta_path)
    Image.new("RGB", (1, 1), color=(0, 255, 0)).save(catalog_1)
    Image.new("RGB", (1, 1), color=(0, 0, 255)).save(catalog_2)

    db = init_database(str(tmp_path / "lib.db"))
    try:
        db.execute(
            """
            INSERT INTO instagram_dump_media (
                media_key, file_path, filename, date_folder, processed
            ) VALUES (?, ?, ?, ?, 0)
            """,
            ("fixture/1", str(insta_path), "insta.png", "202601"),
        )
        db.execute(
            "INSERT INTO images (key, filepath, date_taken, instagram_posted) VALUES (?, ?, ?, 0)",
            ("cat/1", str(catalog_1), "2026-01-01T00:00:00"),
        )
        db.execute(
            "INSERT INTO images (key, filepath, date_taken, instagram_posted) VALUES (?, ?, ?, 0)",
            ("cat/2", str(catalog_2), "2026-01-02T00:00:00"),
        )
        db.commit()

        fake_candidates = [
            {"key": "cat/1", "filepath": str(catalog_1), "phash": "", "description": ""},
            {"key": "cat/2", "filepath": str(catalog_2), "phash": "", "description": ""},
        ]
        fake_results = [
            {
                "catalog_key": "cat/1",
                "total_score": 0.9,
                "phash_distance": 1,
                "phash_score": 0.94,
                "desc_similarity": 0.5,
                "vision_result": "UNCERTAIN",
                "vision_score": 0.5,
                "vision_reasoning": "first",
                "model_used": "test-model",
                "rate_limited": False,
            },
            {
                "catalog_key": "cat/2",
                "total_score": 0.5,
                "phash_distance": 4,
                "phash_score": 0.75,
                "desc_similarity": 0.2,
                "vision_result": "DIFFERENT",
                "vision_score": 0.0,
                "vision_reasoning": "second",
                "model_used": "test-model",
                "rate_limited": False,
            },
        ]

        with (
            patch(
                "lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date",
                return_value=fake_candidates,
            ),
            patch(
                "lightroom_tagger.scripts.match_instagram_dump.catalog_key_is_primary_grid_row",
                return_value=True,
            ),
            patch(
                "lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip",
                return_value=["cat/1", "cat/2"],
            ),
            patch(
                "lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision",
                return_value=fake_results,
            ),
        ):
            stats, matches = match_dump_media(
                db,
                media_key="fixture/1",
                threshold=0.99,
            )

        snapshot_count = db.execute(
            "SELECT COUNT(*) AS c FROM comparison_pool_snapshots"
        ).fetchone()["c"]
        candidate_count = db.execute(
            "SELECT COUNT(*) AS c FROM comparison_pool_snapshot_candidates"
        ).fetchone()["c"]

        assert stats["processed"] == 1
        assert matches == []
        assert snapshot_count == 1
        assert candidate_count == 2
    finally:
        db.close()


def test_match_dump_media_cancel_after_snapshot_marks_attempted(tmp_path):
    """Cancel after scoring leaves the captured snapshot report-eligible."""
    insta_path = tmp_path / "insta.png"
    catalog_path = tmp_path / "catalog.png"
    Image.new("RGB", (1, 1), color=(255, 0, 0)).save(insta_path)
    Image.new("RGB", (1, 1), color=(0, 255, 0)).save(catalog_path)

    db = init_database(str(tmp_path / "lib.db"))
    try:
        db.execute(
            """
            INSERT INTO instagram_dump_media (
                media_key, file_path, filename, date_folder, processed
            ) VALUES (?, ?, ?, ?, 0)
            """,
            ("fixture/1", str(insta_path), "insta.png", "202601"),
        )
        db.execute(
            "INSERT INTO images (key, filepath, date_taken, instagram_posted) VALUES (?, ?, ?, 0)",
            ("cat/1", str(catalog_path), "2026-01-01T00:00:00"),
        )
        db.commit()

        fake_candidates = [
            {"key": "cat/1", "filepath": str(catalog_path), "phash": "", "description": ""},
        ]
        fake_results = [
            {
                "catalog_key": "cat/1",
                "total_score": 0.5,
                "phash_distance": 4,
                "phash_score": 0.75,
                "desc_similarity": 0.2,
                "vision_result": "DIFFERENT",
                "vision_score": 0.0,
                "vision_reasoning": "cancelled",
                "model_used": "test-model",
                "rate_limited": False,
            },
        ]
        should_cancel = Mock(side_effect=[False, True])

        with (
            patch(
                "lightroom_tagger.scripts.match_instagram_dump.find_candidates_by_date",
                return_value=fake_candidates,
            ),
            patch(
                "lightroom_tagger.scripts.match_instagram_dump.catalog_key_is_primary_grid_row",
                return_value=True,
            ),
            patch(
                "lightroom_tagger.scripts.match_instagram_dump.shortlist_catalog_candidates_by_clip",
                return_value=["cat/1"],
            ),
            patch(
                "lightroom_tagger.scripts.match_instagram_dump.score_candidates_with_vision",
                return_value=fake_results,
            ),
        ):
            match_dump_media(
                db,
                media_key="fixture/1",
                threshold=0.99,
                should_cancel=should_cancel,
            )

        snapshot_count = db.execute(
            "SELECT COUNT(*) AS c FROM comparison_pool_snapshots"
        ).fetchone()["c"]
        attempted_at = db.execute(
            "SELECT last_attempted_at FROM instagram_dump_media WHERE media_key = ?",
            ("fixture/1",),
        ).fetchone()["last_attempted_at"]

        assert snapshot_count == 1
        assert attempted_at is not None
    finally:
        db.close()
