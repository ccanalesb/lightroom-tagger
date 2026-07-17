"""Tests for CLIP embedding persistence (sqlite-vec)."""

import os
import tempfile
import unittest

import sqlite_vec

from lightroom_tagger.core.database import (
    init_database,
    library_write,
    store_image,
    upsert_image_clip_embedding,
)
class TestDatabaseEmbeddings(unittest.TestCase):
    """Tests for CLIP embedding storage (vec0 round-trip)."""

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

    def test_init_database_image_clip_embedding_roundtrip(self):
        """CLIP vec0 row round-trip via library_write and upsert (Phase 5 SIM-01)."""
        uv = self.db.execute("PRAGMA user_version").fetchone()
        self.assertEqual(int(uv["user_version"]), 6)
        key = store_image(
            self.db,
            {
                "date_taken": "2024-01-15",
                "filename": "clip_rt.jpg",
                "filepath": "/tmp/clip_rt.jpg",
            },
        )
        blob = sqlite_vec.serialize_float32([0.0] * 512)
        self.assertEqual(len(blob), 2048)
        with library_write(self.db):
            upsert_image_clip_embedding(self.db, key, blob)
        row = self.db.execute(
            "SELECT embedding FROM image_clip_embeddings WHERE image_key = ?",
            (key,),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(len(row["embedding"]), 2048)
