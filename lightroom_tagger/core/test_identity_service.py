"""Tests for ``identity_service`` (aggregate ranking, fingerprint, suggestions)."""

from __future__ import annotations

import sqlite3

from lightroom_tagger.core.database import (
    init_database,
    insert_image_score,
    store_image,
)
from lightroom_tagger.core.identity_service import (
    build_lens_exemplars,
    build_mirror,
    compute_image_peak_percentile_scores,
    compute_single_image_aggregate_scores,
    compute_within_perspective_percentile_lookup,
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
    not_attempted: int = 0,
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
            "not_attempted": not_attempted,
        },
    )


def test_aggregate_excludes_excused_perspective(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn)
    assert len(slugs) >= 2
    s0, s1 = slugs[0], slugs[1]

    k = store_image(
        conn,
        {"date_taken": "2024-01-10", "filename": "mixed.jpg", "instagram_posted": False},
    )
    _add_score(conn, k, s0, 8)
    _add_score(conn, k, s1, 5, not_attempted=1)
    conn.commit()

    row = compute_single_image_aggregate_scores(conn, k)
    assert row is not None
    assert row["perspectives_covered"] == 1
    assert row["aggregate_score"] == 8.0
    assert [p["perspective_slug"] for p in row["per_perspective"]] == [s0]


def test_image_with_all_perspectives_excused_is_not_scorable(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn)
    s0, s1 = slugs[0], slugs[1]

    k = store_image(
        conn,
        {"date_taken": "2024-01-11", "filename": "allexcused.jpg", "instagram_posted": False},
    )
    _add_score(conn, k, s0, 5, not_attempted=1)
    _add_score(conn, k, s1, 5, not_attempted=1)
    conn.commit()

    row = compute_single_image_aggregate_scores(conn, k)
    assert row is None


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

    items, meta = compute_image_peak_percentile_scores(conn, min_perspectives=2)
    partial_row = next(i for i in items if i["image_key"] == k_partial)
    assert partial_row["eligible"] is False
    assert partial_row["perspectives_covered"] == 1
    assert meta["eligible_count"] == 2

    page, total, _ = rank_best_photos(conn, limit=10, offset=0, min_perspectives=2)
    assert total == 2
    keys = [r["image_key"] for r in page]
    assert k_partial not in keys
    assert keys[0] == k_high
    assert page[0]["peak_percentile"] > page[1]["peak_percentile"]


def test_rank_best_photos_filters_by_posted(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    slugs = _active_slugs(conn)
    assert len(slugs) >= 2
    s0, s1 = slugs[0], slugs[1]

    k_posted = store_image(
        conn,
        {
            "date_taken": "2024-01-10",
            "filename": "posted.jpg",
            "rating": 5,
            "instagram_posted": True,
        },
    )
    k_unposted = store_image(
        conn,
        {
            "date_taken": "2024-01-11",
            "filename": "unposted.jpg",
            "rating": 5,
            "instagram_posted": False,
        },
    )

    _add_score(conn, k_posted, s0, 8)
    _add_score(conn, k_posted, s1, 8)
    _add_score(conn, k_unposted, s0, 7)
    _add_score(conn, k_unposted, s1, 7)
    conn.commit()

    page_true, total_true, _ = rank_best_photos(
        conn, limit=10, offset=0, min_perspectives=2, posted=True
    )
    assert total_true == 1
    assert len(page_true) == 1
    assert page_true[0]["instagram_posted"] is True

    page_false, total_false, _ = rank_best_photos(
        conn, limit=10, offset=0, min_perspectives=2, posted=False
    )
    assert total_false == 1
    assert len(page_false) == 1
    assert page_false[0]["instagram_posted"] is False

    page_all, total_all, _ = rank_best_photos(
        conn, limit=10, offset=0, min_perspectives=2, posted=None
    )
    assert total_all == 2
    assert len(page_all) == 2


def test_mirror_descriptor_log_odds_prefers_lens_specific_tokens(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]

    for i in range(6):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-10-{10 + i:02d}",
                "filename": f"m{i}.jpg",
                "instagram_posted": False,
            },
        )
        _add_score(conn, k, hot, 8 + (i % 2), rationale="kumquat lighting balance frame")
        _add_score(conn, k, cold, 2 + (i % 2), rationale="ordinary street scene")
    conn.commit()

    mirror = build_mirror(conn)
    section = next(s for s in mirror["sections"] if s["perspective_slug"] == hot)
    tokens = {d["token"] for d in section["descriptors"]}
    assert "kumquat" in tokens
    assert all(d["count"] >= 5 for d in section["descriptors"])


def test_mirror_exemplar_ordering_and_purity_tiebreak(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]

    keys: list[str] = []
    # Three images on hot lens; same top raw score but different purity vs cold lens.
    for i, cold_score in enumerate([2, 4, 4]):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-11-{10 + i:02d}",
                "filename": f"ex{i}.jpg",
                "instagram_posted": False,
            },
        )
        keys.append(k)
        _add_score(conn, k, hot, 10)
        _add_score(conn, k, cold, cold_score)
    conn.commit()

    mirror = build_mirror(conn)
    section = next((s for s in mirror["sections"]), None)
    assert section is not None
    exemplars = section["exemplars"]
    assert len(exemplars) >= 2
    # Highest purity on the hot lens should sort ahead at equal hot percentile.
    assert exemplars[0]["purity"] >= exemplars[1]["purity"]


def test_mirror_strength_label_thresholds(tmp_path) -> None:
    from lightroom_tagger.core.identity_service.mirror import _strength_label

    assert _strength_label(z_score=6.0, crowned=True, leading_not_distinctive=False) == (
        "A defining strength"
    )
    assert _strength_label(z_score=3.0, crowned=True, leading_not_distinctive=False) == (
        "A clear strength"
    )
    assert _strength_label(z_score=2.0, crowned=True, leading_not_distinctive=False) == (
        "A strength"
    )
    assert _strength_label(z_score=0.5, crowned=False, leading_not_distinctive=True) == (
        "Leading, but not strongly distinctive"
    )


def test_mirror_crowning_uses_binomial_and_fallback(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]

    for i in range(12):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-12-{10 + i:02d}",
                "filename": f"crown{i}.jpg",
                "instagram_posted": False,
            },
        )
        hot_score = 10 if i < 10 else 5
        cold_score = 2 if i < 10 else 9
        _add_score(conn, k, hot, hot_score)
        _add_score(conn, k, cold, cold_score)
    conn.commit()

    mirror = build_mirror(conn)
    crowned = [s for s in mirror["sections"] if s["crowned"]]
    assert crowned
    assert crowned[0]["perspective_slug"] == hot
    assert crowned[0]["z_score"] > 0

    # Even split → fallback top-1, not crowned.
    conn2 = init_database(str(tmp_path / "even.db"))
    for i in range(8):
        k = store_image(
            conn2,
            {
                "date_taken": f"2025-01-{10 + i:02d}",
                "filename": f"even{i}.jpg",
                "instagram_posted": False,
            },
        )
        _add_score(conn2, k, hot, 5 + (i % 2))
        _add_score(conn2, k, cold, 5 + ((i + 1) % 2))
    conn2.commit()

    even = build_mirror(conn2)
    assert even["meta"]["fallback_active"] is True
    assert len(even["sections"]) == 1
    assert even["sections"][0]["leading_not_distinctive"] is True


def test_mirror_reproduces_multi_crown_shape_with_low_coverage_caveat(tmp_path) -> None:
    """#203 headline shape: two lenses crowned, z-sorted, the lower-coverage one flagged.

    The real catalog crowns more than one technique and marks a low-coverage crown
    with a caveat (spec #207 AC: "crowns Depth & Environmental-Context + Framing,
    Framing with the low-coverage caveat"). This asserts that mechanism on a
    synthetic catalog engineered to that shape. Scores use a two-band {9, 2} layout
    per lens so each image's percentile argmax is unambiguous: the winner lens sits
    in its 9-band (percentile ~0.56) while the other sits in its 2-band (~0.44). The
    anchor groups (C, D) give c/d a high band so their diluter scores in groups A/B
    stay bottom-percentile. See percentiles._midrank_percentile_ranks for the math.
    """
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=4)
    assert len(slugs) >= 4
    a, b, c, d = slugs[0], slugs[1], slugs[2], slugs[3]
    HIGH, LOW = 9, 2

    def _img(name: str) -> str:
        return store_image(
            conn,
            {"date_taken": "2025-03-01", "filename": name, "instagram_posted": False},
        )

    # Group A (16): {a, c} — a spikes, wins every image → high-coverage crown.
    for i in range(16):
        k = _img(f"grpA{i}.jpg")
        _add_score(conn, k, a, HIGH)
        _add_score(conn, k, c, LOW)
    # Group B (12): {b, d} — b spikes, wins every image → crowned but lower coverage.
    for i in range(12):
        k = _img(f"grpB{i}.jpg")
        _add_score(conn, k, b, HIGH)
        _add_score(conn, k, d, LOW)
    # Group C (2): {c, a} — anchors c's high band so group-A c stays bottom-percentile.
    for i in range(2):
        k = _img(f"grpC{i}.jpg")
        _add_score(conn, k, c, HIGH)
        _add_score(conn, k, a, LOW)
    # Group D (2): {d, b} — anchors d's high band; neither c nor d clears the bar.
    for i in range(2):
        k = _img(f"grpD{i}.jpg")
        _add_score(conn, k, d, HIGH)
        _add_score(conn, k, b, LOW)
    conn.commit()

    mirror = build_mirror(conn)
    assert mirror["meta"]["fallback_active"] is False

    crowned = [s for s in mirror["sections"] if s["crowned"]]
    # Two techniques crowned, ordered by descending z.
    assert [s["perspective_slug"] for s in crowned] == [a, b]
    assert crowned[0]["z_score"] >= crowned[1]["z_score"]

    by_slug = {s["perspective_slug"]: s for s in crowned}
    assert by_slug[a]["low_coverage"] is False  # scored on 18/32
    assert by_slug[b]["low_coverage"] is True  # scored on 14/32 → carries the caveat


def test_mirror_reads_percentile_lookup_not_aggregate_scores(tmp_path, monkeypatch) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]
    k = store_image(
        conn,
        {"date_taken": "2025-02-01", "filename": "one.jpg", "instagram_posted": False},
    )
    _add_score(conn, k, hot, 8)
    _add_score(conn, k, cold, 4)
    conn.commit()

    lookup = compute_within_perspective_percentile_lookup(conn)

    def _tracked_lookup(c):
        assert c is conn
        return lookup

    monkeypatch.setattr(
        "lightroom_tagger.core.identity_service.mirror.compute_within_perspective_percentile_lookup",
        _tracked_lookup,
    )

    build_mirror(conn)


def _insert_two_member_stack(conn, rep_key: str, mem_key: str) -> int:
    conn.execute(
        "INSERT INTO image_stacks (representative_key, stack_size) VALUES (?, ?)",
        (rep_key, 2),
    )
    conn.commit()
    row = conn.execute("SELECT last_insert_rowid() AS x").fetchone()
    assert row is not None
    sid = int(row["x"])
    conn.execute(
        "INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)",
        (sid, rep_key),
    )
    conn.execute(
        "INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)",
        (sid, mem_key),
    )
    conn.commit()
    return sid


def test_build_lens_exemplars_pagination_ordering_and_total(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]

    for i in range(5):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-11-{10 + i:02d}",
                "filename": f"page{i}.jpg",
                "instagram_posted": False,
            },
        )
        hot_score = 10 - i
        cold_score = 2 + i
        _add_score(conn, k, hot, hot_score)
        _add_score(conn, k, cold, cold_score)
    conn.commit()

    full = build_lens_exemplars(conn, hot, offset=0, limit=100)
    assert full["total"] == 5
    assert len(full["items"]) == 5
    purities = [row["purity"] for row in full["items"]]
    assert purities == sorted(purities, reverse=True)

    page0 = build_lens_exemplars(conn, hot, offset=0, limit=2)
    page1 = build_lens_exemplars(conn, hot, offset=2, limit=2)
    assert page0["total"] == 5
    assert len(page0["items"]) == 2
    assert len(page1["items"]) == 2
    assert page0["items"][0]["image_key"] != page1["items"][0]["image_key"]
    assert page0["items"][0]["percentile"] >= page1["items"][0]["percentile"]


def test_build_lens_exemplars_collapses_burst_to_representative(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]

    rep = store_image(
        conn,
        {"date_taken": "2024-12-01", "filename": "rep.jpg", "instagram_posted": False},
    )
    mem = store_image(
        conn,
        {"date_taken": "2024-12-02", "filename": "mem.jpg", "instagram_posted": False},
    )
    solo = store_image(
        conn,
        {"date_taken": "2024-12-03", "filename": "solo.jpg", "instagram_posted": False},
    )
    for k, hot_score in [(rep, 10), (mem, 9), (solo, 8)]:
        _add_score(conn, k, hot, hot_score)
        _add_score(conn, k, cold, 2)
    _insert_two_member_stack(conn, rep, mem)
    conn.commit()

    payload = build_lens_exemplars(conn, hot, offset=0, limit=10)
    keys = {row["image_key"] for row in payload["items"]}
    assert payload["total"] == 2
    assert rep in keys
    assert solo in keys
    assert mem not in keys
    rep_row = next(r for r in payload["items"] if r["image_key"] == rep)
    assert rep_row["stack_id"] is not None
    assert rep_row["stack_size"] == 2


def test_mirror_other_lenses_excludes_crowned_and_includes_stats(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=4)
    assert len(slugs) >= 4
    a, b, c, d = slugs[0], slugs[1], slugs[2], slugs[3]
    HIGH, LOW = 9, 2

    def _img(name: str) -> str:
        return store_image(
            conn,
            {"date_taken": "2025-03-01", "filename": name, "instagram_posted": False},
        )

    for i in range(16):
        k = _img(f"grpA{i}.jpg")
        _add_score(conn, k, a, HIGH)
        _add_score(conn, k, c, LOW)
    for i in range(12):
        k = _img(f"grpB{i}.jpg")
        _add_score(conn, k, b, HIGH)
        _add_score(conn, k, d, LOW)
    for i in range(2):
        k = _img(f"grpC{i}.jpg")
        _add_score(conn, k, c, HIGH)
        _add_score(conn, k, a, LOW)
    for i in range(2):
        k = _img(f"grpD{i}.jpg")
        _add_score(conn, k, d, HIGH)
        _add_score(conn, k, b, LOW)
    conn.commit()

    mirror = build_mirror(conn)
    crowned_slugs = {s["perspective_slug"] for s in mirror["sections"] if s["crowned"]}
    assert {a, b} <= crowned_slugs

    other_slugs = {row["perspective_slug"] for row in mirror["other_lenses"]}
    assert a not in other_slugs
    assert b not in other_slugs
    assert c in other_slugs or d in other_slugs
    for row in mirror["other_lenses"]:
        assert "strength_label" in row
        assert "exemplar_total" in row
        assert row["exemplar_total"] >= 0

    for section in mirror["sections"]:
        assert "exemplar_total" in section
        assert section["exemplar_total"] >= len(section["exemplars"])


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


def test_suggestions_ranks_by_peak_percentile(tmp_path) -> None:
    """Suggestions order by peak percentile, not raw mean."""
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]

    for i, (hs, cs) in enumerate([(8, 2), (9, 3), (10, 4), (9, 3)]):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-09-{10 + i:02d}",
                "filename": f"base{i}.jpg",
                "instagram_posted": False,
            },
        )
        _add_score(conn, k, hot, hs)
        _add_score(conn, k, cold, cs)

    mean_winner = store_image(
        conn,
        {"date_taken": "2024-09-20", "filename": "mean.jpg", "instagram_posted": False},
    )
    peak_winner = store_image(
        conn,
        {"date_taken": "2024-09-21", "filename": "peak.jpg", "instagram_posted": False},
    )
    _add_score(conn, mean_winner, hot, 9)
    _add_score(conn, mean_winner, cold, 4)
    _add_score(conn, peak_winner, hot, 10)
    _add_score(conn, peak_winner, cold, 2)
    conn.commit()

    mean_agg = (
        sum(p["score"] for p in compute_single_image_aggregate_scores(conn, mean_winner)["per_perspective"])
        / 2
    )
    peak_agg = (
        sum(p["score"] for p in compute_single_image_aggregate_scores(conn, peak_winner)["per_perspective"])
        / 2
    )
    assert mean_agg > peak_agg

    out = suggest_what_to_post_next(conn, limit=10)
    assert out["candidates"]
    assert out["candidates"][0]["image_key"] == peak_winner
    assert out["candidates"][0]["peak_percentile"] >= out["candidates"][1]["peak_percentile"]
    assert out["meta"]["ranking_key"] == "peak_percentile"


def test_suggestions_offset_returns_second_page(tmp_path) -> None:
    db_path = tmp_path / "library.db"
    conn = init_database(str(db_path))
    slugs = _active_slugs(conn)
    s0, s1 = slugs[0], slugs[1]

    for i, day in enumerate(["2024-08-01", "2024-08-02", "2024-08-03"]):
        k = store_image(
            conn,
            {
                "date_taken": day,
                "filename": f"pg{i}.jpg",
                "instagram_posted": False,
            },
        )
        score = 9 - i
        _add_score(conn, k, s0, score)
        _add_score(conn, k, s1, score)
    conn.commit()

    base = suggest_what_to_post_next(conn, limit=10, offset=0)
    assert base["total"] >= 3
    assert len(base["candidates"]) >= 3
    expected_second = base["candidates"][1]["image_key"]

    out = suggest_what_to_post_next(conn, limit=1, offset=1)
    assert out["total"] >= 3
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["image_key"] == expected_second


def test_midrank_percentile_assigns_tied_scores_same_rank(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=1)
    slug = slugs[0]

    keys: list[str] = []
    for i, score in enumerate([5, 5, 10]):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-06-{10 + i:02d}",
                "filename": f"tie{i}.jpg",
                "instagram_posted": False,
            },
        )
        keys.append(k)
        _add_score(conn, k, slug, score)
    conn.commit()

    lookup = compute_within_perspective_percentile_lookup(conn)
    tied_a = lookup[(keys[0], slug)]
    tied_b = lookup[(keys[1], slug)]
    top = lookup[(keys[2], slug)]

    assert tied_a == tied_b
    assert 0.0 <= tied_a <= 1.0
    assert top == 1.0
    assert tied_a < top


def test_percentile_normalizes_within_each_perspective_independently(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]

    image_keys: list[str] = []
    hot_scores = [8, 9, 10]
    cold_scores = [2, 3, 4]
    for i, (hs, cs) in enumerate(zip(hot_scores, cold_scores)):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-07-{10 + i:02d}",
                "filename": f"norm{i}.jpg",
                "instagram_posted": False,
            },
        )
        image_keys.append(k)
        _add_score(conn, k, hot, hs)
        _add_score(conn, k, cold, cs)
    conn.commit()

    lookup = compute_within_perspective_percentile_lookup(conn)
    # Middle raw score in each distribution should map to the same percentile.
    mid_hot = lookup[(image_keys[1], hot)]
    mid_cold = lookup[(image_keys[1], cold)]
    assert mid_hot == mid_cold == 0.5


def test_percentile_excludes_ineligible_population_from_baseline(tmp_path) -> None:
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=1)
    slug = slugs[0]

    eligible_key = store_image(
        conn,
        {"date_taken": "2024-08-01", "filename": "eligible.jpg", "instagram_posted": False},
    )
    excused_key = store_image(
        conn,
        {"date_taken": "2024-08-02", "filename": "excused.jpg", "instagram_posted": False},
    )
    _add_score(conn, eligible_key, slug, 4)
    _add_score(conn, excused_key, slug, 10, not_attempted=1)
    conn.commit()

    lookup = compute_within_perspective_percentile_lookup(conn)
    assert (excused_key, slug) not in lookup
    assert lookup[(eligible_key, slug)] == 1.0


def test_rank_best_photos_prefers_peak_percentile_over_mean(tmp_path) -> None:
    """High mean on a cold lens loses to a peak on a hot lens after normalization."""
    conn = init_database(str(tmp_path / "library.db"))
    slugs = _active_slugs(conn, limit=2)
    hot, cold = slugs[0], slugs[1]

    # Baseline population for hot lens: mostly 8–10; cold lens: mostly 2–4.
    baseline_keys: list[str] = []
    for i, (hs, cs) in enumerate([(8, 2), (9, 3), (10, 4), (9, 3)]):
        k = store_image(
            conn,
            {
                "date_taken": f"2024-09-{10 + i:02d}",
                "filename": f"base{i}.jpg",
                "instagram_posted": False,
            },
        )
        baseline_keys.append(k)
        _add_score(conn, k, hot, hs)
        _add_score(conn, k, cold, cs)

    mean_winner = store_image(
        conn,
        {"date_taken": "2024-09-20", "filename": "mean.jpg", "instagram_posted": False},
    )
    peak_winner = store_image(
        conn,
        {"date_taken": "2024-09-21", "filename": "peak.jpg", "instagram_posted": False},
    )
    # Higher mean, but only mid-pack on each lens.
    _add_score(conn, mean_winner, hot, 9)
    _add_score(conn, mean_winner, cold, 4)
    # Lower mean, but top of the hot-lens distribution.
    _add_score(conn, peak_winner, hot, 10)
    _add_score(conn, peak_winner, cold, 2)
    conn.commit()

    mean_agg = (
        sum(p["score"] for p in compute_single_image_aggregate_scores(conn, mean_winner)["per_perspective"])
        / 2
    )
    peak_agg = (
        sum(p["score"] for p in compute_single_image_aggregate_scores(conn, peak_winner)["per_perspective"])
        / 2
    )
    assert mean_agg > peak_agg

    page, total, meta = rank_best_photos(conn, limit=10, offset=0, min_perspectives=2)
    assert total >= 2
    assert meta["weighting"] == "peak_within_perspective_percentile"
    assert page[0]["image_key"] == peak_winner
    assert page[0]["peak_percentile"] >= page[1]["peak_percentile"]
