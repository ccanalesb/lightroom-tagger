/**
 * Create a `library.db`.
 *
 * Python spells the schema as a base DDL script followed by fifteen migration
 * functions, replayed on **every** open. Here it is one script that produces the
 * current shape directly, because the six migrations that do real work only
 * transform data a database below `user_version` 8 can hold, and the one live
 * database has been at 8 for a long time. What is left of the ladder — the tables
 * and indexes the later migrations create — is inlined below, so a fresh database
 * arrives at the same place in one step. See the plan for the case for each.
 *
 * Two deliberate divergences from what Python's `init_database` builds today:
 *
 *   - `image_descriptions_fts` is created as an **external-content** table
 *     (`content='image_descriptions'`), which is what the production database
 *     has. Python's `_migrate_image_descriptions_fts` was rewritten to build a
 *     standalone table but is gated at `user_version` 3, so it never re-ran and
 *     the two shapes have diverged: a Python-initialized database and the real
 *     one need opposite delete statements (see `removeDescriptionFtsRow`). New
 *     databases should match the one everything is actually tested against.
 *   - Nothing is written beside the database. Python's ladder leaves a
 *     `library.db.pre-key-migration.bak` and an `instagram-matching-export.json`
 *     next to a brand-new file, both of them backups of nothing.
 */
import { mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { openLibraryDb, type Db } from '../connection.js';
import { REPO_ROOT } from '../../config.js';
import { nowIsoUtc } from '../../utils/datetime.js';
import { markdownMarksOptional } from './scores.js';

/**
 * The `PRAGMA user_version` a current database carries.
 *
 * Python reaches 8 by stepping 0 → 1 → 3 → 5 → 6 → 7 → 8; a database this module
 * creates is born there.
 */
export const LIBRARY_SCHEMA_VERSION = 8;

const SCHEMA_SQL = `
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

CREATE INDEX IF NOT EXISTS idx_images_filepath ON images(filepath);
CREATE INDEX IF NOT EXISTS idx_images_image_hash ON images(image_hash);
CREATE INDEX IF NOT EXISTS idx_images_date_taken ON images(date_taken);
CREATE INDEX IF NOT EXISTS idx_images_instagram_posted ON images(instagram_posted);

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
    source_filename TEXT,
    updated_at TEXT,
    created_at TEXT,
    -- Last, not up beside "active" where it belongs: production got this column
    -- from an ALTER TABLE, and column order is the key order of a SELECT * row.
    -- Moving it would reorder JSON keys the API already emits.
    optional INTEGER NOT NULL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS image_stacks (
    stack_id INTEGER PRIMARY KEY AUTOINCREMENT,
    representative_key TEXT NOT NULL,
    stack_size INTEGER NOT NULL DEFAULT 0,
    user_modified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_image_stacks_representative
    ON image_stacks(representative_key);

CREATE TABLE IF NOT EXISTS image_stack_members (
    stack_id INTEGER NOT NULL
        REFERENCES image_stacks(stack_id) ON DELETE CASCADE,
    image_key TEXT NOT NULL,
    PRIMARY KEY (stack_id, image_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_image_stack_members_image_key
    ON image_stack_members(image_key);

CREATE TABLE IF NOT EXISTS catalog_similarity_groups (
    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed_key TEXT NOT NULL,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    best_similarity REAL NOT NULL DEFAULT 0,
    job_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_catalog_similarity_groups_created
    ON catalog_similarity_groups(created_at DESC, group_id DESC);
CREATE INDEX IF NOT EXISTS idx_catalog_similarity_groups_seed
    ON catalog_similarity_groups(seed_key);

CREATE TABLE IF NOT EXISTS catalog_similarity_candidates (
    group_id INTEGER NOT NULL
        REFERENCES catalog_similarity_groups(group_id) ON DELETE CASCADE,
    candidate_key TEXT NOT NULL,
    similarity REAL NOT NULL,
    rank INTEGER NOT NULL,
    why_matched TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (group_id, candidate_key)
);

CREATE INDEX IF NOT EXISTS idx_catalog_similarity_candidates_group_rank
    ON catalog_similarity_candidates(group_id, rank);

CREATE TABLE IF NOT EXISTS catalog_similarity_rejections (
    key_a TEXT NOT NULL,
    key_b TEXT NOT NULL,
    rejected_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (key_a, key_b),
    CHECK (key_a < key_b)
);

CREATE INDEX IF NOT EXISTS idx_catalog_similarity_rejections_rejected_at
    ON catalog_similarity_rejections(rejected_at DESC);

CREATE TABLE IF NOT EXISTS image_frame_substance (
    image_key TEXT PRIMARY KEY,
    verdict TEXT NOT NULL CHECK (verdict IN ('void','illegible','ok','unknown')),
    unknown_reason TEXT NOT NULL DEFAULT '',
    black_frac_25 REAL,
    blown_frac_235 REAL,
    lap_var REAL,
    tile_max REAL,
    entropy REAL,
    detector_version TEXT NOT NULL,
    judged_at TEXT NOT NULL DEFAULT (datetime('now')),
    run_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS frame_substance_overrides (
    image_key TEXT PRIMARY KEY,
    overridden_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_frame_substance_overrides_overridden_at
    ON frame_substance_overrides(overridden_at DESC);

CREATE TABLE IF NOT EXISTS frame_substance_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    detector_version TEXT NOT NULL,
    count_void INTEGER NOT NULL DEFAULT 0,
    count_illegible INTEGER NOT NULL DEFAULT 0,
    count_ok INTEGER NOT NULL DEFAULT 0,
    count_unknown INTEGER NOT NULL DEFAULT 0,
    breached INTEGER NOT NULL DEFAULT 0,
    breach_reason TEXT NOT NULL DEFAULT ''
);
`;

/**
 * The two virtual tables, which `CREATE VIRTUAL TABLE IF NOT EXISTS` supports but
 * which are kept out of `SCHEMA_SQL` because each depends on something the plain
 * DDL does not: the FTS5 table on `image_descriptions` existing first, and the
 * `vec0` one on the sqlite-vec extension being loaded.
 */
const VIRTUAL_TABLE_SQL = `
CREATE VIRTUAL TABLE IF NOT EXISTS image_descriptions_fts USING fts5(
    description_search_document,
    tokenize='porter unicode61',
    content='image_descriptions',
    content_rowid='rowid'
);

CREATE VIRTUAL TABLE IF NOT EXISTS image_clip_embeddings USING vec0(
    embedding float[512] distance_metric=cosine,
    image_key TEXT
);
`;

function tableExists(db: Db, name: string): boolean {
  return (
    db
      .prepare("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?")
      .get(name) !== undefined
  );
}

function userVersion(db: Db): number {
  return Number(db.pragma('user_version', { simple: true }));
}

/**
 * Refuse a database that predates the current schema.
 *
 * A path that is not there yet, or an empty file `openLibraryDb` just created,
 * has no `images` table and is simply new. Anything with one and a
 * `user_version` below the current is a legacy database that needs the six data
 * migrations this module does not carry — remapping composite keys, backfilling
 * blob scores, exporting the retired Instagram tables. Saying so is honest;
 * running the current DDL over it would leave a database that claims to be
 * current and is not.
 */
function assertNotLegacy(db: Db, path: string): void {
  const version = userVersion(db);
  if (version >= LIBRARY_SCHEMA_VERSION) return;
  if (!tableExists(db, 'images')) return;
  throw new Error(
    `${path} is at schema version ${version}, below the current ${LIBRARY_SCHEMA_VERSION}. ` +
      'The TypeScript CLI does not carry the upgrade migrations; run the Python ' +
      '`lightroom-tagger init` against it once first.',
  );
}

/**
 * Create every table and index at the current version on an open connection.
 * Idempotent, and seeds nothing.
 *
 * Exported for the test fixture, which needs the production schema without the
 * factory rubrics — most of its tests assert on perspectives they seeded
 * themselves. Everything else should go through `initLibraryDb`.
 */
export function createLibrarySchema(db: Db): void {
  db.exec(SCHEMA_SQL);
  db.exec(VIRTUAL_TABLE_SQL);
  db.pragma(`user_version = ${LIBRARY_SCHEMA_VERSION}`);
}

/**
 * Create (or adopt) `library.db` at `path` with the current schema and the
 * factory perspectives. Idempotent; the caller owns closing the connection.
 */
export function initLibraryDb(path: string): Db {
  // Python's `init_database` does the same `makedirs` first, so `init --db` into
  // a directory that does not exist yet works rather than failing at open.
  mkdirSync(dirname(resolve(path)), { recursive: true });
  const db = openLibraryDb(path);
  try {
    assertNotLegacy(db, path);
    createLibrarySchema(db);
    seedPerspectivesFromPromptsDir(db);
  } catch (e) {
    db.close();
    throw e;
  }
  return db;
}

/** Where the factory perspective rubrics live, as markdown. */
export const PERSPECTIVE_PROMPTS_DIR = join(REPO_ROOT, 'prompts', 'perspectives');

/**
 * Python's `str.title()`: the first letter of every run of letters is uppercased
 * and the rest lowercased, so `environmental-context-legibility` becomes
 * `Environmental-Context-Legibility` rather than the single-capital result
 * JavaScript's usual word-boundary regex would give.
 */
function pythonTitle(s: string): string {
  return s.replace(/\p{L}+/gu, (w) => w[0]!.toUpperCase() + w.slice(1).toLowerCase());
}

/**
 * The value `perspectives.description` is seeded with: the first non-blank body
 * line, skipping a leading `# Heading`.
 *
 * On the rubrics that carry `<!-- optional: true -->` immediately under their
 * heading, that marker *is* the first body line, so it becomes the description.
 * Reproduced rather than fixed: it is what the factory seed has always produced,
 * it is the first thing an owner edits in the UI, and the seed only ever runs
 * once against an empty table.
 */
export function perspectiveSeedDescription(markdown: string): string {
  const lines = markdown.split(/\r\n|\r|\n/);
  let i = 0;
  while (i < lines.length && !lines[i]!.trim()) i += 1;
  if (i >= lines.length) return '';

  const first = lines[i]!.trim();
  if (!first.startsWith('# ')) return first;

  i += 1;
  while (i < lines.length && !lines[i]!.trim()) i += 1;
  if (i >= lines.length) return first.replace(/^#+/, '').trim();
  return lines[i]!.trim();
}

/**
 * Insert the factory perspective rows from `prompts/perspectives/*.md` when
 * `perspectives` is empty. Returns how many were inserted.
 *
 * The emptiness check is the whole contract: the seed is a one-time factory
 * default and the database is authoritative afterwards, so an owner who deletes a
 * rubric does not get it back on the next `init`.
 */
export function seedPerspectivesFromPromptsDir(
  db: Db,
  promptsDir: string = PERSPECTIVE_PROMPTS_DIR,
): number {
  const existing = db.prepare('SELECT COUNT(*) AS cnt FROM perspectives').get() as {
    cnt: number;
  };
  if (Number(existing.cnt) > 0) return 0;

  let entries: string[];
  try {
    if (!statSync(promptsDir).isDirectory()) return 0;
    entries = readdirSync(promptsDir).sort();
  } catch {
    return 0;
  }

  const now = nowIsoUtc();
  const insert = db.prepare(
    `INSERT INTO perspectives (
       slug, display_name, description, prompt_markdown,
       active, optional, source_filename, created_at, updated_at
     ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)`,
  );

  let inserted = 0;
  for (const name of entries) {
    if (extname(name).toLowerCase() !== '.md') continue;
    const full = join(promptsDir, name);
    if (!statSync(full).isFile()) continue;

    const slug = name.slice(0, -extname(name).length);
    const text = readFileSync(full, 'utf8');
    insert.run(
      slug,
      pythonTitle(slug.replaceAll('_', ' ')),
      perspectiveSeedDescription(text),
      text,
      markdownMarksOptional(text) ? 1 : 0,
      name,
      now,
      now,
    );
    inserted += 1;
  }
  return inserted;
}
