"""Tests for image descriptions, FTS payloads, and fts query builder."""

import os
import tempfile
import unittest

from lightroom_tagger.core.database import (
    build_description_fts_query,
    get_image_description,
    get_undescribed_catalog_images,
    get_undescribed_instagram_images,
    init_database,
    init_image_descriptions_table,
    store_image,
    store_image_description,
    store_instagram_dump_media,
)
class TestImageDescriptions(unittest.TestCase):
    """Tests for image_descriptions table functions."""

    def setUp(self):
        fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.db = init_database(self.temp_db_path)

    def tearDown(self):
        self.db.close()
        os.unlink(self.temp_db_path)

    def test_init_descriptions_table(self):
        init_image_descriptions_table(self.db)
        # Should not raise - table already exists from init_database
        self.db.execute("SELECT COUNT(*) FROM image_descriptions")

    def test_store_image_description(self):
        record = {
            'image_key': '2024-01-15_photo.jpg',
            'image_type': 'catalog',
            'summary': 'A street scene at golden hour',
            'composition': {'layers': ['foreground', 'background'], 'techniques': ['rule_of_thirds']},
            'perspectives': {
                'street': {'analysis': 'Strong geometry', 'score': 7},
                'documentary': {'analysis': 'Fair story', 'score': 5},
                'publisher': {'analysis': 'Editorial use', 'score': 6},
            },
            'technical': {'dominant_colors': ['#2b3a4c'], 'mood': 'contemplative'},
            'subjects': ['person', 'architecture'],
            'best_perspective': 'street',
            'model_used': 'gemma3:27b',
        }
        key = store_image_description(self.db, record)
        self.assertEqual(key, '2024-01-15_photo.jpg')

        stored = get_image_description(self.db, '2024-01-15_photo.jpg')
        self.assertIsNotNone(stored)
        self.assertEqual(stored['summary'], 'A street scene at golden hour')
        self.assertEqual(stored['perspectives']['street']['score'], 7)
        self.assertIn('described_at', stored)

    def test_get_image_description_not_found(self):
        self.assertIsNone(get_image_description(self.db, 'nonexistent'))

    def test_store_description_is_idempotent(self):
        store_image_description(self.db, {
            'image_key': 'key1', 'image_type': 'catalog',
            'summary': 'First', 'model_used': 'gemma3:27b',
        })
        store_image_description(self.db, {
            'image_key': 'key1', 'image_type': 'catalog',
            'summary': 'Updated', 'model_used': 'gemma3:27b',
        })
        stored = get_image_description(self.db, 'key1')
        self.assertEqual(stored['summary'], 'Updated')

    def test_get_undescribed_images(self):
        store_image(self.db, {'date_taken': '2024-01-15', 'filename': 'a.jpg'})
        store_image(self.db, {'date_taken': '2024-01-16', 'filename': 'b.jpg'})
        store_image_description(self.db, {
            'image_key': '2024-01-15_a.jpg', 'image_type': 'catalog',
            'summary': 'Described', 'model_used': 'gemma3:27b',
        })
        undescribed = get_undescribed_catalog_images(self.db)
        keys = [img['key'] for img in undescribed]
        self.assertIn('2024-01-16_b.jpg', keys)
        self.assertNotIn('2024-01-15_a.jpg', keys)

    def test_get_undescribed_catalog_images_newest_first(self):
        store_image(self.db, {'date_taken': '2024-01-10', 'filename': 'old.jpg'})
        store_image(self.db, {'date_taken': '2024-06-20', 'filename': 'new.jpg'})
        self.db.execute(
            "INSERT INTO images (key, filename, filepath, date_taken, rating) "
            "VALUES ('undated.jpg', 'undated.jpg', '/u.jpg', NULL, 0)"
        )
        keys = [img['key'] for img in get_undescribed_catalog_images(self.db)]
        self.assertEqual(keys[0], 'undated.jpg')
        self.assertEqual(keys[1:], ['2024-06-20_new.jpg', '2024-01-10_old.jpg'])

    def test_get_undescribed_catalog_images_equal_date_tiebreaker(self):
        store_image(self.db, {'date_taken': '2024-05-01', 'filename': 'aaa.jpg'})
        store_image(self.db, {'date_taken': '2024-05-01', 'filename': 'zzz.jpg'})
        keys = [img['key'] for img in get_undescribed_catalog_images(self.db)]
        self.assertEqual(keys, ['2024-05-01_zzz.jpg', '2024-05-01_aaa.jpg'])

    def test_get_undescribed_catalog_images_ordering_under_filters(self):
        store_image(self.db, {'date_taken': '2024-06-20', 'filename': 'in.jpg', 'rating': 4})
        store_image(self.db, {'date_taken': '2024-06-01', 'filename': 'in2.jpg', 'rating': 5})
        store_image(self.db, {'date_taken': '2024-08-01', 'filename': 'low.jpg', 'rating': 1})
        keys = [
            img['key']
            for img in get_undescribed_catalog_images(self.db, months=120, min_rating=3)
        ]
        self.assertEqual(keys, ['2024-06-20_in.jpg', '2024-06-01_in2.jpg'])

    def test_get_undescribed_instagram_images_newest_first(self):
        store_instagram_dump_media(self.db, {
            'media_key': 'ig/old',
            'file_path': '/ig/old.jpg',
            'filename': 'old.jpg',
            'date_folder': '202401',
            'created_at': '2024-01-10T00:00:00',
        })
        store_instagram_dump_media(self.db, {
            'media_key': 'ig/new',
            'file_path': '/ig/new.jpg',
            'filename': 'new.jpg',
            'date_folder': '202406',
            'created_at': '2024-06-20T00:00:00',
        })
        self.db.execute(
            "INSERT INTO instagram_dump_media "
            "(media_key, file_path, filename, date_folder, created_at, processed) "
            "VALUES ('ig/undated', '/ig/u.jpg', 'u.jpg', '202405', NULL, 0)"
        )
        keys = [img['media_key'] for img in get_undescribed_instagram_images(self.db)]
        self.assertEqual(keys[0], 'ig/undated')
        self.assertEqual(keys[1:], ['ig/new', 'ig/old'])

    def test_get_undescribed_instagram_images_equal_date_tiebreaker(self):
        store_instagram_dump_media(self.db, {
            'media_key': 'ig/aaa',
            'file_path': '/ig/aaa.jpg',
            'filename': 'aaa.jpg',
            'date_folder': '202405',
            'created_at': '2024-05-01T00:00:00',
        })
        store_instagram_dump_media(self.db, {
            'media_key': 'ig/zzz',
            'file_path': '/ig/zzz.jpg',
            'filename': 'zzz.jpg',
            'date_folder': '202405',
            'created_at': '2024-05-01T00:00:00',
        })
        keys = [img['media_key'] for img in get_undescribed_instagram_images(self.db)]
        self.assertEqual(keys, ['ig/zzz', 'ig/aaa'])

    def test_get_undescribed_instagram_images_ordering_under_months_filter(self):
        from datetime import datetime, timedelta

        recent = datetime.now().strftime('%Y-%m-%dT00:00:00')
        mid = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%dT00:00:00')
        old = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%dT00:00:00')
        store_instagram_dump_media(self.db, {
            'media_key': 'ig/recent',
            'file_path': '/ig/recent.jpg',
            'filename': 'recent.jpg',
            'date_folder': datetime.now().strftime('%Y%m'),
            'created_at': recent,
        })
        store_instagram_dump_media(self.db, {
            'media_key': 'ig/mid',
            'file_path': '/ig/mid.jpg',
            'filename': 'mid.jpg',
            'date_folder': datetime.now().strftime('%Y%m'),
            'created_at': mid,
        })
        store_instagram_dump_media(self.db, {
            'media_key': 'ig/stale',
            'file_path': '/ig/stale.jpg',
            'filename': 'stale.jpg',
            'date_folder': '202001',
            'created_at': old,
        })
        keys = [
            img['media_key']
            for img in get_undescribed_instagram_images(self.db, months=12)
        ]
        self.assertEqual(keys, ['ig/recent', 'ig/mid'])

    def test_store_image_description_persists_has_repetition_stringly(self):
        store_image_description(self.db, {
            "image_key": "hr-true", "image_type": "catalog",
            "summary": "s", "model_used": "m", "has_repetition": "true",
        })
        r = self.db.execute(
            "SELECT has_repetition FROM image_descriptions WHERE image_key = ?",
            ("hr-true",),
        ).fetchone()
        self.assertIsNotNone(r)
        self.assertEqual(r["has_repetition"], 1)
        store_image_description(self.db, {
            "image_key": "hr-false", "image_type": "catalog",
            "summary": "s", "model_used": "m", "has_repetition": "false",
        })
        r2 = self.db.execute(
            "SELECT has_repetition FROM image_descriptions WHERE image_key = ?",
            ("hr-false",),
        ).fetchone()
        self.assertIsNotNone(r2)
        self.assertEqual(r2["has_repetition"], 0)

    def test_store_image_description_fts_for_catalog_with_visual_fields(self):
        key = "2024-06-01_fts1.jpg"
        store_image_description(self.db, {
            "image_key": key, "image_type": "catalog",
            "summary": "red  boat", "subjects": ["lake", "dock"],
            "dominant_colors": ["#ff0000"], "mood_tags": ["calm"],
            "has_repetition": 0, "model_used": "m",
        })
        r = self.db.execute(
            "SELECT dominant_colors, mood_tags, has_repetition, description_search_document "
            "FROM image_descriptions WHERE image_key = ?",
            (key,),
        ).fetchone()
        self.assertIsNotNone(r)
        self.assertIn("#ff0000", r["dominant_colors"])
        self.assertIn("calm", r["mood_tags"])
        self.assertEqual(r["has_repetition"], 0)
        doc = r["description_search_document"]
        self.assertIsNotNone(doc)
        self.assertIn("red boat", doc)
        self.assertIn("lake", doc)
        self.assertIn("dock", doc)
        m = self.db.execute(
            "SELECT 1 FROM image_descriptions_fts "
            "WHERE image_descriptions_fts MATCH 'boat AND lake' AND rowid = ("
            "  SELECT rowid FROM image_descriptions WHERE image_key = ?"
            ")",
            (key,),
        ).fetchone()
        self.assertIsNotNone(m)

    def test_store_image_description_fts_cleared_for_non_catalog(self):
        key = "ig-fts-1"
        store_image_description(self.db, {
            "image_key": key, "image_type": "instagram",
            "summary": "should not be indexed in fts",
            "model_used": "m",
        })
        d = self.db.execute(
            "SELECT description_search_document, rowid FROM image_descriptions WHERE image_key = ?",
            (key,),
        ).fetchone()
        self.assertIsNotNone(d)
        self.assertIsNone(d["description_search_document"])
        n = self.db.execute(
            "SELECT COUNT(*) AS n FROM image_descriptions_fts WHERE rowid = ?",
            (d["rowid"],),
        ).fetchone()["n"]
        self.assertEqual(n, 0)


class TestBuildDescriptionFtsQuery(unittest.TestCase):
    """``build_description_fts_query`` — AND tokens, NLS-02 sanitization."""

    def test_build_description_fts_query_strips_sqlish_input(self):
        match, err = build_description_fts_query("hello'; DROP TABLE--")
        self.assertIsNone(err)
        self.assertIsNotNone(match)
        self.assertNotIn(";", match)
        self.assertNotIn("'", match)
        self.assertIn("hello", match)
        self.assertIn("DROP", match)
        self.assertIn("TABLE", match)

    def test_build_description_fts_query_rejects_too_short(self):
        m, err = build_description_fts_query("a")
        self.assertIsNone(m)
        self.assertEqual(err, "description_search must be at least 2 characters")

    def test_build_description_fts_query_none_or_blank_no_match(self):
        self.assertEqual(build_description_fts_query(None), (None, None))
        self.assertEqual(build_description_fts_query(""), (None, None))
        self.assertEqual(build_description_fts_query("   "), (None, None))

    def test_build_description_fts_query_only_punctuation_yields_no_fts(self):
        m, err = build_description_fts_query("++")
        self.assertIsNone(err)
        self.assertIsNone(m)


def test_description_read_helpers(tmp_path) -> None:
    import sqlite3

    from lightroom_tagger.core.database import (
        get_all_image_descriptions,
        get_image_descriptions_by_type,
        init_database,
        store_image_description,
    )

    db = init_database(str(tmp_path / "library.db"))
    store_image_description(db, {
        "image_key": "cat-1",
        "image_type": "catalog",
        "summary": "Catalog shot",
        "subjects": ["tree"],
        "model_used": "m",
    })
    store_image_description(db, {
        "image_key": "ig-1",
        "image_type": "instagram",
        "summary": "IG shot",
        "model_used": "m",
    })

    all_rows = get_all_image_descriptions(db)
    assert len(all_rows) == 2
    assert all(not isinstance(r, sqlite3.Row) for r in all_rows)
    assert all_rows[0]["subjects"] == ["tree"]

    catalog_only = get_image_descriptions_by_type(db, "catalog")
    assert len(catalog_only) == 1
    assert catalog_only[0]["image_key"] == "cat-1"

    assert get_image_descriptions_by_type(db, "instagram")[0]["image_key"] == "ig-1"
    assert get_all_image_descriptions(init_database(str(tmp_path / "empty.db"))) == []
    db.close()
