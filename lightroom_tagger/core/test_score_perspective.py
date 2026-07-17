"""Tests for score_perspective validation helpers and NL filter slug parsing."""

from lightroom_tagger.core.catalog_nl_filter import CatalogNlFilter
from lightroom_tagger.core.database import init_database
from lightroom_tagger.core.score_perspective import validate_score_perspective_exists


def test_catalog_nl_filter_accepts_hyphenated_score_perspective() -> None:
    filt = CatalogNlFilter(score_perspective="environmental-context-legibility", sort_by_score="desc")
    assert filt.score_perspective == "environmental-context-legibility"


def test_validate_score_perspective_exists_unknown(tmp_path) -> None:
    conn = init_database(str(tmp_path / "t.db"))
    slug, err = validate_score_perspective_exists(conn, "missing-slug")
    assert slug is None
    assert err == "unknown perspective 'missing-slug'"


def test_validate_score_perspective_exists_inactive_row(tmp_path) -> None:
    conn = init_database(str(tmp_path / "t.db"))
    slug = "inactive-hyphen-test"
    conn.execute(
        """
        INSERT INTO perspectives (slug, display_name, description, prompt_markdown, active)
        VALUES (?, 'Env', '', '', 0)
        """,
        (slug,),
    )
    conn.commit()
    resolved, err = validate_score_perspective_exists(conn, slug)
    assert err is None
    assert resolved == slug
