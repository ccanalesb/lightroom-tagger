"""Initial library DB DDL for `init_database`."""

BASE_LIBRARY_SCHEMA_SQL = '''

        CREATE TABLE IF NOT EXISTS images (
            key TEXT PRIMARY KEY,
            id TEXT,
            filename TEXT,
            filepath TEXT,
            date_taken TEXT,
            rating INTEGER DEFAULT 0,
            pick INTEGER DEFAULT 0,
            color_label TEXT DEFAULT '',
            keywords TEXT DEFAULT '[]',
            title TEXT DEFAULT '',
            caption TEXT DEFAULT '',
            description TEXT DEFAULT '',
            copyright TEXT DEFAULT '',
            camera_make TEXT DEFAULT '',
            camera_model TEXT DEFAULT '',
            lens TEXT DEFAULT '',
            focal_length TEXT DEFAULT '',
            aperture TEXT DEFAULT '',
            shutter_speed TEXT DEFAULT '',
            iso TEXT DEFAULT '',
            gps_latitude REAL,
            gps_longitude REAL,
            width INTEGER,
            height INTEGER,
            file_size INTEGER,
            instagram_posted INTEGER DEFAULT 0,
            instagram_post_date TEXT,
            instagram_url TEXT,
            instagram_index INTEGER DEFAULT 0,
            image_hash TEXT,
            analyzed_at TEXT,
            phash TEXT,
            exif TEXT,
            catalog_path TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS instagram_dump_media (
            media_key TEXT PRIMARY KEY,
            file_path TEXT,
            filename TEXT,
            date_folder TEXT,
            caption TEXT,
            created_at TEXT,
            exif_data TEXT,
            post_url TEXT,
            image_hash TEXT,
            processed INTEGER DEFAULT 0,
            matched_catalog_key TEXT,
            vision_result TEXT,
            vision_score REAL,
            processed_at TEXT,
            last_attempted_at TEXT,
            added_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_dump_media_hash ON instagram_dump_media(image_hash);
        CREATE INDEX IF NOT EXISTS idx_dump_media_date ON instagram_dump_media(date_folder);
        CREATE INDEX IF NOT EXISTS idx_dump_media_processed ON instagram_dump_media(processed);
        CREATE INDEX IF NOT EXISTS idx_dump_media_processed_attempted ON instagram_dump_media(processed, last_attempted_at);

        CREATE TABLE IF NOT EXISTS instagram_images (
            key TEXT PRIMARY KEY,
            local_path TEXT,
            post_url TEXT,
            filename TEXT,
            description TEXT,
            image_hash TEXT,
            instagram_folder TEXT,
            crawled_at TEXT,
            phash TEXT,
            exif TEXT,
            created_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_insta_images_local_path ON instagram_images(local_path);

        CREATE TABLE IF NOT EXISTS matches (
            catalog_key TEXT,
            insta_key TEXT,
            phash_distance INTEGER,
            phash_score REAL,
            desc_similarity REAL,
            vision_result TEXT,
            vision_score REAL,
            total_score REAL,
            matched_at TEXT,
            model_used TEXT,
            validated_at TEXT,
            rank INTEGER DEFAULT 1,
            PRIMARY KEY (catalog_key, insta_key)
        );

        CREATE TABLE IF NOT EXISTS rejected_matches (
            catalog_key TEXT,
            insta_key TEXT,
            rejected_at TEXT,
            PRIMARY KEY (catalog_key, insta_key)
        );

        CREATE TABLE IF NOT EXISTS vision_cache (
            key TEXT PRIMARY KEY,
            compressed_path TEXT,
            phash TEXT,
            compressed_at TEXT,
            original_mtime REAL
        );

        CREATE TABLE IF NOT EXISTS vision_comparisons (
            catalog_key TEXT,
            insta_key TEXT,
            result TEXT,
            vision_score REAL,
            compared_at TEXT,
            model_used TEXT,
            PRIMARY KEY (catalog_key, insta_key)
        );

        CREATE TABLE IF NOT EXISTS image_descriptions (
            image_key TEXT PRIMARY KEY,
            image_type TEXT NOT NULL,
            summary TEXT DEFAULT '',
            composition TEXT DEFAULT '{}',
            perspectives TEXT DEFAULT '{}',
            technical TEXT DEFAULT '{}',
            subjects TEXT DEFAULT '[]',
            best_perspective TEXT DEFAULT '',
            model_used TEXT DEFAULT '',
            described_at TEXT,
            dominant_colors TEXT,
            mood_tags TEXT,
            has_repetition INTEGER,
            description_search_document TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_desc_image_type ON image_descriptions(image_type);

        CREATE TABLE IF NOT EXISTS perspectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            prompt_markdown TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            source_filename TEXT,
            updated_at TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS image_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_key TEXT NOT NULL,
            image_type TEXT NOT NULL DEFAULT 'catalog',
            perspective_slug TEXT NOT NULL,
            score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 10),
            rationale TEXT NOT NULL DEFAULT '',
            model_used TEXT NOT NULL DEFAULT '',
            prompt_version TEXT NOT NULL DEFAULT '',
            scored_at TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 1,
            repaired_from_malformed INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_image_scores_versioned
                UNIQUE (image_key, image_type, perspective_slug, prompt_version)
        );

        CREATE INDEX IF NOT EXISTS idx_image_scores_perspective_score
            ON image_scores(perspective_slug, score);
        CREATE INDEX IF NOT EXISTS idx_image_scores_image
            ON image_scores(image_key, image_type);
        CREATE INDEX IF NOT EXISTS idx_image_scores_current
            ON image_scores(image_key, image_type, perspective_slug, is_current);

        CREATE TABLE IF NOT EXISTS comparison_pool_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            insta_key TEXT NOT NULL,
            captured_at TEXT NOT NULL DEFAULT (datetime('now')),
            source_job_id TEXT,
            threshold REAL NOT NULL,
            clip_top_k INTEGER NOT NULL,
            weights_json TEXT NOT NULL,
            candidate_count INTEGER NOT NULL DEFAULT 0,
            diagnostics_json TEXT NOT NULL DEFAULT '{}',
            insta_asset_path TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_comparison_pool_snapshots_insta_captured
            ON comparison_pool_snapshots(insta_key, captured_at DESC, snapshot_id DESC);

        CREATE INDEX IF NOT EXISTS idx_comparison_pool_snapshots_source_job
            ON comparison_pool_snapshots(source_job_id);

        CREATE TABLE IF NOT EXISTS comparison_pool_snapshot_candidates (
            snapshot_id INTEGER NOT NULL
                REFERENCES comparison_pool_snapshots(snapshot_id) ON DELETE CASCADE,
            rank INTEGER NOT NULL,
            catalog_key TEXT NOT NULL,
            total_score REAL,
            phash_distance REAL,
            phash_score REAL,
            desc_similarity REAL,
            vision_result TEXT,
            vision_score REAL,
            vision_reasoning TEXT,
            model_used TEXT,
            rate_limited INTEGER NOT NULL DEFAULT 0,
            source_path TEXT,
            source_available INTEGER NOT NULL DEFAULT 0,
            asset_path TEXT,
            debug_resolved_path TEXT,
            PRIMARY KEY (snapshot_id, catalog_key)
        );

        CREATE INDEX IF NOT EXISTS idx_comparison_pool_snapshot_candidates_snapshot_rank
            ON comparison_pool_snapshot_candidates(snapshot_id, rank);
'''
