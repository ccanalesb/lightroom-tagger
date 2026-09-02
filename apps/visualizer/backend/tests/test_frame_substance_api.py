"""Frame substance per-image API and flagged catalog filter tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from app import create_app

from lightroom_tagger.core.database import (
    get_frame_substance_verdict,
    has_frame_substance_override,
    init_database,
    insert_frame_substance_override,
    insert_frame_substance_run,
    insert_image_score,
    is_frame_substance_flagged,
    store_image,
    store_vision_cached_image,
    upsert_frame_substance_verdict,
)
from lightroom_tagger.core.frame_substance_detector import detector_version
from lightroom_tagger.core.identity_service import rank_best_photos
from lightroom_tagger.lightroom.writer import (
    CULL_KEYWORD,
    connect_catalog,
    image_has_keyword_by_key,
)


def _make_client(db_path: str):
    import utils.db as db_utils

    db_utils.LIBRARY_DB = db_path
    return create_app().test_client(), db_path


def _seed_verdict(conn, image_key: str, verdict: str, *, unknown_reason: str = "") -> None:
    run_id = insert_frame_substance_run(conn, detector_version=detector_version())
    upsert_frame_substance_verdict(
        conn,
        image_key=image_key,
        verdict=verdict,
        unknown_reason=unknown_reason,
        black_frac_25=0.0,
        blown_frac_235=0.0,
        lap_var=1.0,
        tile_max=10.0,
        entropy=5.0,
        detector_version=detector_version(),
        run_id=run_id,
    )
    conn.commit()


def _finish_run(conn) -> None:
    from lightroom_tagger.core.database import finish_frame_substance_run

    run = conn.execute(
        "SELECT run_id FROM frame_substance_runs ORDER BY run_id DESC LIMIT 1"
    ).fetchone()
    finish_frame_substance_run(
        conn,
        int(run["run_id"]),
        count_void=0,
        count_illegible=0,
        count_ok=0,
        count_unknown=0,
        breached=False,
    )
    conn.commit()


def _add_scores(conn, image_key: str, slugs: list[str], score: int = 8) -> None:
    for slug in slugs:
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
                "scored_at": "2026-01-01T00:00:00+00:00",
                "is_current": 1,
            },
        )
    conn.commit()


def _make_lr_catalog(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY AUTOINCREMENT,
            id_global TEXT,
            name TEXT,
            lc_name TEXT,
            dateCreated TEXT,
            keywordType INTEGER
        );
        CREATE TABLE AgLibraryFile (id_local INTEGER PRIMARY KEY, baseName TEXT);
        CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY, rootFile INTEGER);
        CREATE TABLE AgLibraryKeywordImage (
            id_local INTEGER PRIMARY KEY AUTOINCREMENT,
            image INTEGER,
            tag INTEGER
        );
        INSERT INTO AgLibraryFile (id_local, baseName) VALUES (1, 'photo');
        INSERT INTO Adobe_images (id_local, rootFile) VALUES (100, 1);
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def substance_client(tmp_path, monkeypatch):
    from lightroom_tagger.core.config import Config

    db_path = str(tmp_path / "library.db")
    conn = init_database(db_path)
    key = store_image(
        conn,
        {"date_taken": "2024-06-01", "filename": "photo.jpg", "filepath": "/a.jpg"},
    )
    conn.close()
    client, _ = _make_client(db_path)
    lrcat = tmp_path / "catalog.lrcat"
    _make_lr_catalog(lrcat)
    cfg = Config(catalog_path=str(lrcat))
    monkeypatch.setattr(
        "utils.lr_catalog_write.load_config",
        lambda _path=None: cfg,
    )
    return client, db_path, key, lrcat


def test_get_frame_substance_states(substance_client):
    client, db_path, key, _lrcat = substance_client
    conn = init_database(db_path)

    # No row at all
    resp = client.get(f"/api/images/catalog/{key}/frame-substance")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["verdict"] is None
    assert body["has_detection_run"] is False
    assert body["flagged"] is False

    _seed_verdict(conn, key, "ok")
    _finish_run(conn)
    resp = client.get(f"/api/images/catalog/{key}/frame-substance")
    assert resp.get_json()["verdict"] == "ok"
    assert resp.get_json()["has_detection_run"] is True

    for verdict, reason in [
        ("void", ""),
        ("illegible", ""),
        ("unknown", "no_cache_row"),
    ]:
        k = store_image(
            conn,
            {
                "date_taken": "2024-06-02",
                "filename": f"{verdict}.jpg",
                "filepath": f"/{verdict}.jpg",
            },
        )
        _seed_verdict(conn, k, verdict, unknown_reason=reason)
        payload = client.get(f"/api/images/catalog/{k}/frame-substance").get_json()
        assert payload["verdict"] == verdict
        if verdict == "unknown":
            assert payload["unknown_reason"] == reason
        if verdict in ("void", "illegible"):
            assert payload["instrument"]["kind"] == "pixel_detector"
            assert payload["instrument"]["tier"] == ("A" if verdict == "void" else "B")
    conn.close()


def test_override_round_trip_affects_ranking(substance_client):
    client, db_path, key, _lrcat = substance_client
    conn = init_database(db_path)
    slugs = [
        str(r["slug"])
        for r in conn.execute(
            "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug LIMIT 2"
        ).fetchall()
    ]
    _add_scores(conn, key, slugs)
    _seed_verdict(conn, key, "void")
    _finish_run(conn)
    conn.close()

    conn = init_database(db_path)
    page_before, total_before, _ = rank_best_photos(
        conn, limit=10, offset=0, min_perspectives=2
    )
    assert key not in {row["image_key"] for row in page_before}
    conn.close()

    assert client.post(f"/api/images/catalog/{key}/frame-substance/override").status_code == 200
    conn = init_database(db_path)
    assert has_frame_substance_override(conn, key)
    conn.close()

    conn = init_database(db_path)
    page_after, total_after, _ = rank_best_photos(
        conn, limit=10, offset=0, min_perspectives=2
    )
    assert key in {row["image_key"] for row in page_after}
    assert total_after == total_before + 1
    conn.close()

    assert client.delete(f"/api/images/catalog/{key}/frame-substance/override").status_code == 200
    conn = init_database(db_path)
    assert not has_frame_substance_override(conn, key)
    page_removed, _, _ = rank_best_photos(conn, limit=10, offset=0, min_perspectives=2)
    assert key not in {row["image_key"] for row in page_removed}
    conn.close()


def test_override_survives_detector_rerun(substance_client):
    client, db_path, key, _lrcat = substance_client
    conn = init_database(db_path)
    _seed_verdict(conn, key, "void")
    _finish_run(conn)
    client.post(f"/api/images/catalog/{key}/frame-substance/override")

    run_id = insert_frame_substance_run(conn, detector_version=detector_version())
    upsert_frame_substance_verdict(
        conn,
        image_key=key,
        verdict="illegible",
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
    conn.close()

    conn = init_database(db_path)
    assert has_frame_substance_override(conn, key)
    assert get_frame_substance_verdict(conn, key)["verdict"] == "illegible"
    assert is_frame_substance_flagged(conn, key) is False
    conn.close()


def test_cull_keyword_round_trip(substance_client):
    client, _db_path, key, lrcat = substance_client
    resp = client.post(f"/api/images/catalog/{key}/cull-keyword")
    assert resp.status_code == 200
    assert resp.get_json()["result"] == "added"

    lr = connect_catalog(str(lrcat))
    try:
        assert image_has_keyword_by_key(lr, key, CULL_KEYWORD)
    finally:
        lr.close()

    resp = client.delete(f"/api/images/catalog/{key}/cull-keyword")
    assert resp.get_json()["result"] == "removed"
    lr = connect_catalog(str(lrcat))
    try:
        assert not image_has_keyword_by_key(lr, key, CULL_KEYWORD)
    finally:
        lr.close()


def test_flagged_filter_returns_only_flagged_net_of_overrides(substance_client):
    client, db_path, key, _lrcat = substance_client
    conn = init_database(db_path)
    k_ok = store_image(
        conn,
        {"date_taken": "2024-06-03", "filename": "ok.jpg", "filepath": "/ok.jpg"},
    )
    k_over = store_image(
        conn,
        {"date_taken": "2024-06-04", "filename": "over.jpg", "filepath": "/over.jpg"},
    )
    _seed_verdict(conn, key, "void")
    _seed_verdict(conn, k_over, "illegible")
    insert_frame_substance_override(conn, k_over)
    _seed_verdict(conn, k_ok, "ok")
    _finish_run(conn)
    conn.close()

    payload = client.get("/api/images/catalog?flagged=true&limit=50").get_json()
    keys = {img["key"] for img in payload["images"]}
    assert key in keys
    assert k_over not in keys
    assert k_ok not in keys
    assert payload["total"] == 1


def test_stale_flag_when_preview_newer(substance_client, tmp_path):
    client, db_path, key, _lrcat = substance_client
    conn = init_database(db_path)
    jpeg = tmp_path / "preview.jpg"
    jpeg.write_bytes(b"fake")
    store_vision_cached_image(conn, key, str(jpeg), None, 1.0)
    _seed_verdict(conn, key, "ok")
    _finish_run(conn)
    conn.execute(
        "UPDATE vision_cache SET compressed_at = ? WHERE key = ?",
        ("2099-01-01T00:00:00+00:00", key),
    )
    conn.commit()
    conn.close()

    body = client.get(f"/api/images/catalog/{key}/frame-substance").get_json()
    assert body["is_stale"] is True
