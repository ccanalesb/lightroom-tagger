"""Tests for ``identity_service`` (aggregate ranking, fingerprint, suggestions)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from lightroom_tagger.core.database import (
    init_database,
    insert_image_score,
    store_image,
    store_instagram_dump_media,
    store_match,
    validate_match,
)
from lightroom_tagger.core.identity_service import (
    build_style_fingerprint,
    compute_image_aggregate_scores,
    rank_best_photos,
    suggest_what_to_post_next,
)


def _active_slugs(conn: sqlite3.Connection, *, limit: int = 4) -> list[str]:
    rows = conn.execute(
        "SELECT slug FROM perspectives WHERE active = 1 ORDER BY slug LIMIT ?",
        (limit,),
    ).fetchall()
    return [str(r["slug"]) for r in rows]


def _add_score(
    conn: sqlite3.Connection,
    image_key: str,
    slug: str,
    score: int,
    *,
    rationale: str = "",
) -> None:
    insert_image_score(
        conn,
        {
            "image_key": image_key,
            "image_type": "catalog",
            "perspective_slug": slug,
            "score": score,
            "rationale": rationale,
            "model_used": "test-model",
            "prompt_version": "v1",
            "scored_at": "2024-06-15T12:00:00+00:00",
            "is_current": 1,
        },
    )


def test_rank_best_photos_orders_by_aggregate_and_excludes_low_coverage(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    slugs = _active_slugs(conn)
    assert len(slugs) >= 2
    s0, s1 = slugs[0], slugs[1]

    k_high = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "high.jpg",
            "rating": 5,
            "instagram_posted": False,
        },
    )
    k_low = store_image(
        conn,
        {
            "date_taken": "2024-01-20",
            "filename": "low.jpg",
            "rating": 5,
            "instagram_posted": False,
        },
    )
    k_partial = store_image(
        conn,
        {
            "date_taken": "2024-02-01",
            "filename": "partial.jpg",
            "rating": 5,
            "instagram_posted": False,
        },
    )

    _add_score(conn, k_high, s0, 9)
    _add_score(conn, k_high, s1, 9)
    _add_score(conn, k_low, s0, 4)
    _add_score(conn, k_low, s1, 4)
    _add_score(conn, k_partial, s0, 10)
    conn.commit()

    items, meta = compute_image_aggregate_scores(conn, min_perspectives=2)
    partial_row = next(i for i in items if i["image_key"] == k_partial)
    assert partial_row["eligible"] is False
    assert partial_row["perspectives_covered"] == 1
    assert meta["eligible_count"] == 2

    page, total, _ = rank_best_photos(conn, limit=10, offset=0, min_perspectives=2)
    assert total == 2
    keys = [r["image_key"] for r in page]
    assert k_partial not in keys
    assert keys[0] == k_high
    assert page[0]["aggregate_score"] > page[1]["aggregate_score"]


def test_style_fingerprint_mean_and_rationale_tokens(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    slugs = _active_slugs(conn, limit=1)
    slug = slugs[0]

    k1 = store_image(
        conn,
        {"date_taken": "2024-03-01", "filename": "a.jpg", "instagram_posted": False},
    )
    k2 = store_image(
        conn,
        {"date_taken": "2024-03-02", "filename": "b.jpg", "instagram_posted": False},
    )
    _add_score(conn, k1, slug, 6, rationale="kumquat lighting balance")
    _add_score(conn, k2, slug, 8, rationale="kumquat framing works well")
    conn.commit()

    fp = build_style_fingerprint(conn)
    per = next(p for p in fp["per_perspective"] if p["perspective_slug"] == slug)
    assert per["mean_score"] == 7.0
    assert per["median_score"] == 7.0
    tokens = {t["token"]: t["count"] for t in fp["top_rationale_tokens"]}
    assert tokens.get("kumquat", 0) >= 2


def test_suggestions_only_unposted_with_reasons(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    slugs = _active_slugs(conn)
    s0, s1 = slugs[0], slugs[1]

    k_posted = store_image(
        conn,
        {
            "date_taken": "2024-04-01",
            "filename": "posted.jpg",
            "instagram_posted": True,
        },
    )
    k_unposted = store_image(
        conn,
        {
            "date_taken": "2024-04-02",
            "filename": "unposted.jpg",
            "instagram_posted": False,
        },
    )
    _add_score(conn, k_posted, s0, 5)
    _add_score(conn, k_posted, s1, 5)
    _add_score(conn, k_unposted, s0, 8)
    _add_score(conn, k_unposted, s1, 8)
    conn.commit()

    out = suggest_what_to_post_next(conn, limit=10)
    cand_keys = [c["image_key"] for c in out["candidates"]]
    assert k_unposted in cand_keys
    assert k_posted not in cand_keys
    assert all(len(c["reasons"]) >= 1 for c in out["candidates"])


def test_suggestions_cadence_gap_meta_optional(tmp_path) -> None:
    """Heavy baseline window vs quiet recent window → cadence hint in meta."""
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    slugs = _active_slugs(conn)
    s0, s1 = slugs[0], slugs[1]

    k_cat = store_image(
        conn,
        {
            "date_taken": "2024-05-01",
            "filename": "cadence_candidate.jpg",
            "instagram_posted": False,
        },
    )
    _add_score(conn, k_cat, s0, 9)
    _add_score(conn, k_cat, s1, 9)
    conn.commit()

    today = datetime.now(timezone.utc).date()
    # Inside baseline window (older than last 30 days), not in recent window.
    baseline_day = today - timedelta(days=55)

    for i in range(20):
        post_day = baseline_day - timedelta(days=i)
        created = f"{post_day.isoformat()}T12:00:00Z"
        yyyymm = post_day.strftime("%Y%m")
        ck = store_image(
            conn,
            {
                "date_taken": post_day.isoformat(),
                "filename": f"hist_{i}.jpg",
                "instagram_posted": True,
            },
        )
        store_instagram_dump_media(
            conn,
            {
                "media_key": f"m{i}",
                "date_folder": yyyymm,
                "caption": "",
                "created_at": created,
            },
        )
        store_match(
            conn,
            {"catalog_key": ck, "insta_key": f"m{i}", "total_score": 1.0},
            commit=False,
        )
        validate_match(conn, ck, f"m{i}")
    conn.commit()

    out = suggest_what_to_post_next(conn, limit=5)
    assert out["candidates"]
    meta = out.get("meta") or {}
    assert meta.get("cadence_gap") is True
    assert meta.get("cadence_note")
