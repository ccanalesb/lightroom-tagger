"""Tests for image descriptions, FTS payloads, and fts query builder."""

import os
import tempfile
import unittest

from lightroom_tagger.core.database import (
    build_description_fts_query,
    get_image_description,
    get_undescribed_catalog_images,
    init_database,
    init_image_descriptions_table,
    store_image,
    store_image_description,
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
