"""Tests for frame substance batch detection, guard, and ranking integration."""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest
from PIL import Image

from lightroom_tagger.core.database import (
    init_database,
    insert_image_score,
    insert_frame_substance_override,
    store_image,
    store_vision_cached_image,
)
from lightroom_tagger.core.database.vision_cache import VISION_CACHE_OVERSIZED_SENTINEL
from lightroom_tagger.core.frame_substance_batch import (
    ABSOLUTE_FLAGGED_BOUND,
    evaluate_breach,
    run_frame_substance_detection,
)
from lightroom_tagger.core.identity_service import rank_best_photos


def _active_slugs(conn: sqlite3.Connection, *, limit: int = 2) -> list[str]:
    rows = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug LIMIT ?",
        (limit,),
    ).fetchall()
    return [str(r["slug"]) for r in rows]


def _add_score(conn: sqlite3.Connection, image_key: str, slug: str, score: int) -> None:
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": score,
            "rationale": "",
            "model_used": "test-model",
            "prompt_version": "v1",
            "scored_at": "2024-06-15T12:00:00+00:00",
            "is_current": 1,
        },
    )


def _write_grey_jpeg(path, grey: np.ndarray) -> None:
    Image.fromarray(grey, mode="L").save(path, format="JPEG")


def _seed_scored_image(
    conn: sqlite3.Connection,
    tmp_path,
    *,
    filename: str,
    grey: np.ndarray,
    score: int,
    slugs: list[str],
) -> str:
    jpeg_path = tmp_path / filename
    _write_grey_jpeg(jpeg_path, grey)
    key = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": filename,
            "filepath": f"/photos/{filename}",
            "instagram_posted": False,
        },
    )
    store_vision_cached_image(conn, key, str(jpeg_path), None, 1.0)
    for slug in slugs:
        _add_score(conn, key, slug, score)
    return key


def _flat_black(shape: tuple[int, int] = (128, 128)) -> np.ndarray:
    return np.zeros(shape, dtype=np.uint8)


def _noisy_mid_grey(shape: tuple[int, int] = (128, 128)) -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.integers(80, 176, size=shape, dtype=np.uint8)


def test_void_frame_drops_out_of_ranking_after_detection(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn)
    assert len(slugs) >= 2

    k_good = _seed_scored_image(
        conn,
        tmp_path,
        filename="good.jpg",
        grey=_noisy_mid_grey(),
        score=7,
        slugs=slugs,
    )
    k_void = _seed_scored_image(
        conn,
        tmp_path,
        filename="void.jpg",
        grey=_flat_black(),
        score=10,
        slugs=slugs,
    )
    conn.commit()

    before, total_before, _ = rank_best_photos(
        conn, limit=10, offset=0, min_perspectives=2
    )
    assert total_before == 2
    assert {row["image_key"] for row in before} == {k_good, k_void}

    result = run_frame_substance_detection(conn)
    assert result["count_void"] == 1

    after, total_after, _ = rank_best_photos(
        conn, limit=10, offset=0, min_perspectives=2
    )
    assert total_after == 1
    assert after[0]["image_key"] == k_good


def test_override_restores_void_frame_to_ranking(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn)

    k_void = _seed_scored_image(
        conn,
        tmp_path,
        filename="void.jpg",
        grey=_flat_black(),
        score=10,
        slugs=slugs,
    )
    conn.commit()
    run_frame_substance_detection(conn)

    page, total, _ = rank_best_photos(conn, limit=10, offset=0, min_perspectives=2)
    assert total == 0

    insert_frame_substance_override(conn, k_void)
    conn.commit()

    page, total, _ = rank_best_photos(conn, limit=10, offset=0, min_perspectives=2)
    assert total == 1
    assert page[0]["image_key"] == k_void


def test_override_survives_detector_rerun(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn)

    k_void = _seed_scored_image(
        conn,
        tmp_path,
        filename="void.jpg",
        grey=_flat_black(),
        score=10,
        slugs=slugs,
    )
    conn.commit()
    insert_frame_substance_override(conn, k_void)
    conn.commit()

    run_frame_substance_detection(conn)
    run_frame_substance_detection(conn)

    row = conn.execute(
        "SELECT verdict FROM image_frame_substance WHERE image_key = ?",
        (k_void,),
    ).fetchone()
    assert row is not None
    assert row["verdict"] == "void"
    override = conn.execute(
        "SELECT 1 AS o FROM frame_substance_overrides WHERE image_key = ?",
        (k_void,),
    ).fetchone()
    assert override is not None


def test_unknown_without_cache_row_stays_in_ranking(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn)

    k_unknown = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "missing.jpg",
            "filepath": "/photos/missing.jpg",
            "instagram_posted": False,
        },
    )
    for slug in slugs:
        _add_score(conn, k_unknown, slug, 8)
    conn.commit()

    result = run_frame_substance_detection(conn)
    row = conn.execute(
        "SELECT verdict, unknown_reason FROM image_frame_substance WHERE image_key = ?",
        (k_unknown,),
    ).fetchone()
    assert row["verdict"] == "unknown"
    assert row["unknown_reason"] == "no_cache_row"
    assert result["count_ok"] == 0

    page, total, _ = rank_best_photos(conn, limit=10, offset=0, min_perspectives=2)
    assert total == 1
    assert page[0]["image_key"] == k_unknown


@pytest.mark.parametrize(
    ("compressed_path", "expected_reason"),
    [
        (None, "no_cache_row"),
        ("", "no_cache_row"),
        (VISION_CACHE_OVERSIZED_SENTINEL, "oversized_sentinel"),
    ],
)
def test_unknown_reasons_from_cache_lookup(
    tmp_path, compressed_path, expected_reason
) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    key = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "probe.jpg",
            "filepath": "/photos/probe.jpg",
        },
    )
    if compressed_path is not None:
        store_vision_cached_image(conn, key, compressed_path, None, 1.0)
    conn.commit()

    run_frame_substance_detection(conn)
    row = conn.execute(
        "SELECT verdict, unknown_reason FROM image_frame_substance WHERE image_key = ?",
        (key,),
    ).fetchone()
    assert row["verdict"] == "unknown"
    assert row["unknown_reason"] == expected_reason


def test_unknown_reason_cache_file_missing(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    key = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "gone.jpg",
            "filepath": "/photos/gone.jpg",
        },
    )
    missing = tmp_path / "gone.jpg"
    store_vision_cached_image(conn, key, str(missing), None, 1.0)
    conn.commit()

    run_frame_substance_detection(conn)
    row = conn.execute(
        "SELECT verdict, unknown_reason FROM image_frame_substance WHERE image_key = ?",
        (key,),
    ).fetchone()
    assert row["verdict"] == "unknown"
    assert row["unknown_reason"] == "cache_file_missing"


def test_unknown_reason_decode_failed(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    key = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "bad.jpg",
            "filepath": "/photos/bad.jpg",
        },
    )
    bad_path = tmp_path / "bad.jpg"
    bad_path.write_bytes(b"not-a-jpeg")
    store_vision_cached_image(conn, key, str(bad_path), None, 1.0)
    conn.commit()

    run_frame_substance_detection(conn)
    row = conn.execute(
        "SELECT verdict, unknown_reason FROM image_frame_substance WHERE image_key = ?",
        (key,),
    ).fetchone()
    assert row["verdict"] == "unknown"
    assert row["unknown_reason"] == "decode_failed"


def test_guard_absolute_bound_flags_breach() -> None:
    rows = {
        f"k{i}": {"verdict": "void" if i < ABSOLUTE_FLAGGED_BOUND + 1 else "ok"}
        for i in range(ABSOLUTE_FLAGGED_BOUND + 2)
    }
    breached, reason = evaluate_breach(new_rows=rows, previous_rows={})
    assert breached is True
    assert "absolute bound" in reason


def test_guard_ratio_uses_intersection_not_raw_growth() -> None:
    previous = {
        "a": {"verdict": "void"},
        "b": {"verdict": "ok"},
        "c": {"verdict": "unknown"},
    }
    new = {
        "a": {"verdict": "void"},
        "b": {"verdict": "ok"},
        "c": {"verdict": "void"},
        "d": {"verdict": "void"},
        "e": {"verdict": "void"},
        "f": {"verdict": "void"},
    }
    breached, reason = evaluate_breach(new_rows=new, previous_rows=previous)
    assert breached is False
    assert reason == ""


def test_guard_ratio_trips_on_intersection_growth() -> None:
    previous = {f"k{i}": {"verdict": "ok"} for i in range(5)}
    previous["k0"] = {"verdict": "void"}
    new = dict(previous)
    for i in range(4):
        new[f"k{i}"] = {"verdict": "void"}
    breached, reason = evaluate_breach(new_rows=new, previous_rows=previous)
    assert breached is True
    assert "ratio bound" in reason


def test_first_run_skips_ratio_guard() -> None:
    rows = {f"k{i}": {"verdict": "void"} for i in range(10)}
    breached, reason = evaluate_breach(new_rows=rows, previous_rows={})
    assert breached is False


def test_verdicts_written_even_when_breach_detected(tmp_path, monkeypatch) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    key = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "new.jpg",
            "filepath": "/photos/new.jpg",
        },
    )
    jpeg_path = tmp_path / "new.jpg"
    _write_grey_jpeg(jpeg_path, _flat_black())
    store_vision_cached_image(conn, key, str(jpeg_path), None, 1.0)
    conn.commit()

    monkeypatch.setattr(
        "lightroom_tagger.core.frame_substance_batch.evaluate_breach",
        lambda **kwargs: (True, "forced breach"),
    )

    result = run_frame_substance_detection(conn)
    assert result["breached"] is True
    row = conn.execute(
        "SELECT verdict FROM image_frame_substance WHERE image_key = ?",
        (key,),
    ).fetchone()
    assert row is not None
    assert row["verdict"] == "void"
