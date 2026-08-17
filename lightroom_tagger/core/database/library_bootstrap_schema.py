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
            image_hash TEXT,
            analyzed_at TEXT,
            phash TEXT,
            exif TEXT,
            catalog_path TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS vision_cache (
            key TEXT PRIMARY KEY,
            compressed_path TEXT,
            phash TEXT,
            compressed_at TEXT,
            original_mtime REAL
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
            optional INTEGER NOT NULL DEFAULT 0,
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
            not_attempted INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT uq_image_scores_versioned
                UNIQUE (image_key, image_type, perspective_slug, prompt_version)
        );

        CREATE INDEX IF NOT EXISTS idx_image_scores_perspective_score
            ON image_scores(perspective_slug, score);
        CREATE INDEX IF NOT EXISTS idx_image_scores_image
            ON image_scores(image_key, image_type);
        CREATE INDEX IF NOT EXISTS idx_image_scores_current
            ON image_scores(image_key, image_type, perspective_slug, is_current);
'''
