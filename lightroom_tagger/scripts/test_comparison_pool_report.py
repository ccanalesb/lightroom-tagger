from pathlib import Path

from PIL import Image

from lightroom_tagger.core.database import init_database, insert_comparison_pool_snapshot
from lightroom_tagger.scripts.generate_comparison_pool_report import (
    write_comparison_pool_report,
)


def _tiny_image(path: Path, color: tuple[int, int, int] = (255, 0, 0)) -> None:
    Image.new("RGB", (1, 1), color=color).save(path)


def _insert_report_fixture(db, tmp_path: Path, *, with_snapshot: bool = True) -> None:
    insta_path = tmp_path / "insta.png"
    catalog_path = tmp_path / "catalog.png"
    _tiny_image(insta_path)
    _tiny_image(catalog_path, color=(0, 255, 0))
    db.execute(
        """
        INSERT INTO instagram_dump_media (
            media_key, file_path, filename, date_folder, caption, processed,
            last_attempted_at
        ) VALUES (?, ?, ?, ?, ?, 0, ?)
        """,
        (
            "fixture/1",
            str(insta_path),
            "insta.png",
            "202601",
            "caption",
            "2026-01-01T00:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO images (key, filepath, date_taken, instagram_posted)
        VALUES (?, ?, ?, 0)
        """,
        ("cat/1", str(catalog_path), "2026-01-01T00:00:00"),
    )
    db.commit()
    if with_snapshot:
        insert_comparison_pool_snapshot(
            db,
            insta_key="fixture/1",
            source_job_id="job-1",
            threshold=0.99,
            clip_top_k=50,
            weights={"phash": 0.4, "description": 0.3, "vision": 0.3},
            vision_candidates=[{"key": "cat/1", "local_path": str(catalog_path)}],
            results=[
                {
                    "catalog_key": "cat/1",
                    "total_score": 0.9,
                    "phash_distance": 1,
                    "phash_score": 0.94,
                    "desc_similarity": 0.5,
                    "vision_result": "UNCERTAIN",
                    "vision_score": 0.5,
                    "vision_reasoning": "fixture reasoning",
                    "model_used": "test-model",
                    "rate_limited": False,
                }
            ],
        )


def test_comparison_pool_report_writes_html_and_assets(tmp_path):
    db = init_database(str(tmp_path / "lib.db"))
    try:
        _insert_report_fixture(db, tmp_path, with_snapshot=True)
        html_path = write_comparison_pool_report(
            str(tmp_path / "out"),
            db,
            month=None,
            job_id=None,
            media_key=None,
            limit=None,
        )
    finally:
        db.close()

    assert html_path.exists()
    assert (tmp_path / "out" / "assets").is_dir()
    html = html_path.read_text()
    assert 'src="assets/' in html


def test_comparison_pool_report_primary_has_no_absolute_paths(tmp_path):
    db = init_database(str(tmp_path / "lib.db"))
    try:
        _insert_report_fixture(db, tmp_path, with_snapshot=True)
        html_path = write_comparison_pool_report(
            str(tmp_path / "out"),
            db,
            month=None,
            job_id=None,
            media_key=None,
            limit=None,
        )
    finally:
        db.close()

    html = html_path.read_text()
    start = html.index('<main id="lt-primary-comparison-pool">')
    end = html.index("</main>", start)
    primary = html[start:end]
    assert "/Users/" not in primary
    assert "/tmp/" not in primary


def test_comparison_pool_report_reconstructed_banner(tmp_path):
    db = init_database(str(tmp_path / "lib.db"))
    try:
        _insert_report_fixture(db, tmp_path, with_snapshot=False)
        html_path = write_comparison_pool_report(
            str(tmp_path / "out"),
            db,
            month=None,
            job_id=None,
            media_key=None,
            limit=None,
        )
    finally:
        db.close()

    assert "Reconstructed — not exact run evidence" in html_path.read_text()
