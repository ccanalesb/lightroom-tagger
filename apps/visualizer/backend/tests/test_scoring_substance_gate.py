"""Tests for Tier-A void gating on scoring selection and single-image path."""

from __future__ import annotations

from lightroom_tagger.core.database import (
    init_database,
    insert_frame_substance_override,
    insert_frame_substance_run,
    store_image,
    upsert_frame_substance_verdict,
)
from lightroom_tagger.core.frame_substance_detector import detector_version
from lightroom_tagger.core.scoring_service import score_image_for_perspective
from lightroom_tagger.core.vision_op import VisionOpOutcome


def _seed_verdict(
    conn,
    image_key: str,
    verdict: str,
    *,
    override: bool = False,
) -> None:
    run_id = insert_frame_substance_run(conn, detector_version=detector_version())
    upsert_frame_substance_verdict(
        conn,
        image_key=image_key,
        verdict=verdict,
        unknown_reason="",
        black_frac_25=0.0,
        blown_frac_235=0.0,
        lap_var=1.0,
        tile_max=10.0,
        entropy=5.0,
        detector_version=detector_version(),
        run_id=run_id,
    )
    if override:
        insert_frame_substance_override(conn, image_key)
    conn.commit()



def test_void_absent_from_scoring_selection_illegible_present(tmp_path) -> None:
    from jobs.handlers.common import _select_catalog_keys

    conn = init_database(str(tmp_path / "library.db"))
    k_void = store_image(conn, {"date_taken": "2024-01-01", "filename": "void.jpg"})
    k_illegible = store_image(conn, {"date_taken": "2024-01-02", "filename": "illeg.jpg"})
    k_unknown = store_image(conn, {"date_taken": "2024-01-03", "filename": "unk.jpg"})
    conn.commit()
    _seed_verdict(conn, k_void, "void")
    _seed_verdict(conn, k_illegible, "illegible")
    _seed_verdict(conn, k_unknown, "unknown")

    keys = {
        k
        for k, _ in _select_catalog_keys(
            conn,
            months=None,
            year=None,
            min_rating=None,
            undescribed_only=False,
            exclude_void_substance=True,
        )
    }
    assert k_void not in keys
    assert k_illegible in keys
    assert k_unknown in keys


def test_overridden_void_present_in_scoring_selection(tmp_path) -> None:
    from jobs.handlers.common import _select_catalog_keys

    conn = init_database(str(tmp_path / "library.db"))
    k_void = store_image(conn, {"date_taken": "2024-01-01", "filename": "void.jpg"})
    conn.commit()
    _seed_verdict(conn, k_void, "void", override=True)

    keys = {
        k
        for k, _ in _select_catalog_keys(
            conn,
            months=None,
            year=None,
            min_rating=None,
            undescribed_only=False,
            exclude_void_substance=True,
        )
    }
    assert k_void in keys


def test_describe_selection_includes_void(tmp_path) -> None:
    from jobs.handlers.common import _select_catalog_keys

    conn = init_database(str(tmp_path / "library.db"))
    k_void = store_image(conn, {"date_taken": "2024-01-01", "filename": "void.jpg"})
    conn.commit()
    _seed_verdict(conn, k_void, "void")

    keys = {
        k
        for k, _ in _select_catalog_keys(
            conn,
            months=None,
            year=None,
            min_rating=None,
            undescribed_only=False,
            exclude_void_substance=False,
        )
    }
    assert k_void in keys


def test_single_image_skips_void_not_illegible(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slug = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug LIMIT 1"
    ).fetchone()["slug"]
    k_void = store_image(
        conn,
        {"date_taken": "2024-01-01", "filename": "void.jpg", "filepath": "/x/void.jpg"},
    )
    k_illegible = store_image(
        conn,
        {"date_taken": "2024-01-02", "filename": "illeg.jpg", "filepath": "/x/illeg.jpg"},
    )
    conn.commit()
    _seed_verdict(conn, k_void, "void")
    _seed_verdict(conn, k_illegible, "illegible")

    void_outcome = score_image_for_perspective(
        conn,
        image_key=k_void,
        image_type="catalog",
        perspective_slug=str(slug),
        force=False,
        provider_id=None,
        model=None,
    )
    assert void_outcome.status == "skipped"
    assert void_outcome.reason == "Frame substance verdict: void"

    illeg_outcome = score_image_for_perspective(
        conn,
        image_key=k_illegible,
        image_type="catalog",
        perspective_slug=str(slug),
        force=False,
        provider_id=None,
        model=None,
    )
    assert illeg_outcome.status != "skipped" or "void" not in (illeg_outcome.reason or "")


def test_filter_void_from_scoring_selection(tmp_path) -> None:
    from jobs.handlers.common import _filter_void_substance_from_scoring_selection

    conn = init_database(str(tmp_path / "library.db"))
    k_void = store_image(conn, {"date_taken": "2024-01-01", "filename": "void.jpg"})
    k_ok = store_image(conn, {"date_taken": "2024-01-02", "filename": "ok.jpg"})
    conn.commit()
    _seed_verdict(conn, k_void, "void")

    filtered = _filter_void_substance_from_scoring_selection(
        conn,
        [(k_void, "catalog"), (k_ok, "catalog")],
    )
    assert filtered == [(k_ok, "catalog")]
