"""Tests for database initialization and migrations."""

import os
import tempfile
import unittest

from lightroom_tagger.core.database import (
    get_image_count,
    init_database,
    migrate_unified_image_keys,
)
class TestDatabaseDbInit(unittest.TestCase):
    """Tests for database initialization and migrations."""

    def setUp(self):
        """Create temporary database for each test."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tf:
            self.temp_db_path = tf.name
        self.db = init_database(self.temp_db_path)

    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        bak = self.temp_db_path + ".pre-key-migration.bak"
        if os.path.exists(bak):
            os.unlink(bak)
        os.unlink(self.temp_db_path)

    def test_init_database(self):
        """Test database initialization."""
        row = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='images'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(get_image_count(self.db), 0)

    def test_init_database_sqlite_vec_image_text_embeddings(self):
        """sqlite-vec loads and vec0 table exists after init_database (Phase 3 NLS-03)."""
        row = self.db.execute("SELECT vec_version() AS v").fetchone()
        self.assertIsNotNone(row)
        v = row["v"]
        self.assertIsNotNone(v)
        self.assertIsInstance(v, str)
        sql_row = self.db.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'image_text_embeddings'"
        ).fetchone()
        self.assertIsNotNone(sql_row)
        sql = sql_row["sql"] or ""
        self.assertIn("vec0", sql)
        self.assertIn("float[768]", sql)
        clip_row = self.db.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name = 'image_clip_embeddings'"
        ).fetchone()
        self.assertIsNotNone(clip_row)
        clip_sql = clip_row["sql"] or ""
        self.assertIn("vec0", clip_sql)
        self.assertIn("float[512]", clip_sql)
        uv = self.db.execute("PRAGMA user_version").fetchone()
        self.assertEqual(int(uv["user_version"]), 5)

    def test_migrate_unified_image_keys_rewrites_legacy_key(self):
        """Legacy full-datetime composite keys remap to YYYY-MM-DD_filename."""
        self.db.execute("PRAGMA user_version = 0")
        self.db.execute(
            """
            INSERT INTO images (key, id, filename, filepath, date_taken)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "2024-01-15T00:00:00_photo.jpg",
                "0",
                "photo.jpg",
                "",
                "2024-01-15T00:00:00",
            ),
        )
        self.db.commit()
        migrate_unified_image_keys(self.db)
        self.db.commit()
        row = self.db.execute("SELECT key FROM images").fetchone()
        self.assertEqual(row["key"], "2024-01-15_photo.jpg")

    def test_migrate_unified_image_keys_merges_collisions(self):
        """Duplicate rows with different timestamp precision merge instead of crashing."""
        self.db.execute("PRAGMA user_version = 0")
        self.db.execute(
            "INSERT INTO images (key, id, filename, filepath, date_taken, rating) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("2020-12-31T22:24:31__DSF2158", "100", "_DSF2158", "/path/a", "2020-12-31T22:24:31", 3),
        )
        self.db.execute(
            "INSERT INTO images (key, id, filename, filepath, date_taken, rating) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("2020-12-31T22:24:31.000__DSF2158", "100", "_DSF2158", "/path/a", "2020-12-31T22:24:31.000", 0),
        )
        # Both keys present in vision_cache (UNIQUE constraint on key)
        self.db.execute(
            "INSERT INTO vision_cache (key, compressed_path, phash, compressed_at, original_mtime) "
            "VALUES (?, ?, ?, ?, ?)",
            ("2020-12-31T22:24:31__DSF2158", "/cache/a.jpg", "abc", "2021-01-01", 1.0),
        )
        self.db.execute(
            "INSERT INTO vision_cache (key, compressed_path, phash, compressed_at, original_mtime) "
            "VALUES (?, ?, ?, ?, ?)",
            ("2020-12-31T22:24:31.000__DSF2158", "/cache/b.jpg", "def", "2021-01-01", 1.0),
        )
        # Match referencing the loser key
        self.db.execute(
            "INSERT INTO matches (catalog_key, insta_key, total_score) VALUES (?, ?, ?)",
            ("2020-12-31T22:24:31.000__DSF2158", "insta_abc", 0.9),
        )
        self.db.commit()

        migrate_unified_image_keys(self.db)
        self.db.commit()

        rows = self.db.execute("SELECT key FROM images").fetchall()
        self.assertEqual(len(rows), 1, "Collision should leave exactly one row")
        self.assertEqual(rows[0]["key"], "2020-12-31__DSF2158")

        match = self.db.execute(
            "SELECT catalog_key FROM matches WHERE insta_key = 'insta_abc'"
        ).fetchone()
        self.assertIsNotNone(match)
        survivor_key = rows[0]["key"]
        self.assertIn(survivor_key, match["catalog_key"],
                       "Dependent match row should be remapped to survivor key")

        vc_rows = self.db.execute("SELECT key FROM vision_cache").fetchall()
        vc_keys = [r["key"] for r in vc_rows]
        self.assertEqual(len(vc_keys), 1,
                         "vision_cache should have exactly one row after merge")
        self.assertEqual(vc_keys[0], "2020-12-31__DSF2158")
