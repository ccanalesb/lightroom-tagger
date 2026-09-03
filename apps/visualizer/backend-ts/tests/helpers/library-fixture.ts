/**
 * Builds a real `library.db` for route tests.
 *
 * Deliberately a real SQLite file rather than a mocked DB layer: the queries are
 * the part most likely to break in the port, so they have to actually execute. The
 * schema here mirrors the columns the routes read — where a column's SQLite type
 * matters (0/1 integers that the API contract exposes as booleans), it is declared
 * the same way the production migrations declare it.
 */
import Database from 'better-sqlite3';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export interface PerspectiveSeed {
  slug: string;
  display_name?: string;
  description?: string;
  prompt_markdown?: string;
  active?: boolean;
  optional?: boolean;
  source_filename?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ScoreSeed {
  image_key: string;
  perspective_slug: string;
  score: number;
  image_type?: string;
  rationale?: string | null;
  model_used?: string | null;
  prompt_version?: string;
  scored_at?: string;
  is_current?: boolean;
  repaired_from_malformed?: boolean;
  not_attempted?: boolean;
}

export interface ImageSeed {
  key: string;
  id?: string | null;
  filename?: string;
  filepath?: string;
  date_taken?: string | null;
  rating?: number;
  pick?: number;
  color_label?: string;
  /** Stored as JSON text, the way the catalog sync writes it. */
  keywords?: string;
  title?: string;
  description?: string;
  instagram_posted?: boolean;
  width?: number;
  height?: number;
}

export class LibraryFixture {
  readonly dir: string;
  readonly dbPath: string;

  constructor() {
    this.dir = mkdtempSync(join(tmpdir(), 'lt-lib-'));
    this.dbPath = join(this.dir, 'library.db');
    const db = new Database(this.dbPath);
    db.exec(`
      CREATE TABLE images (
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
      CREATE TABLE image_stacks (
        stack_id INTEGER PRIMARY KEY AUTOINCREMENT,
        representative_key TEXT NOT NULL,
        stack_size INTEGER NOT NULL DEFAULT 0,
        user_modified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE image_stack_members (
        stack_id INTEGER NOT NULL
          REFERENCES image_stacks(stack_id) ON DELETE CASCADE,
        image_key TEXT NOT NULL,
        PRIMARY KEY (stack_id, image_key)
      );
      CREATE UNIQUE INDEX uq_image_stack_members_image_key
        ON image_stack_members(image_key);
      CREATE TABLE catalog_similarity_groups (
        group_id INTEGER PRIMARY KEY AUTOINCREMENT,
        seed_key TEXT NOT NULL,
        candidate_count INTEGER NOT NULL DEFAULT 0,
        best_similarity REAL NOT NULL DEFAULT 0,
        job_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE catalog_similarity_candidates (
        group_id INTEGER NOT NULL
          REFERENCES catalog_similarity_groups(group_id) ON DELETE CASCADE,
        candidate_key TEXT NOT NULL,
        similarity REAL NOT NULL,
        rank INTEGER NOT NULL,
        why_matched TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (group_id, candidate_key)
      );
      CREATE TABLE catalog_similarity_rejections (
        key_a TEXT NOT NULL,
        key_b TEXT NOT NULL,
        rejected_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (key_a, key_b),
        CHECK (key_a < key_b)
      );
      CREATE TABLE image_frame_substance (
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
      CREATE TABLE frame_substance_overrides (
        image_key TEXT PRIMARY KEY,
        overridden_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE vision_cache (
        key TEXT PRIMARY KEY,
        compressed_path TEXT,
        phash TEXT,
        compressed_at TEXT,
        original_mtime REAL
      );
      CREATE TABLE perspectives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        prompt_markdown TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        optional INTEGER NOT NULL DEFAULT 0,
        source_filename TEXT,
        created_at TEXT,
        updated_at TEXT
      );
      CREATE TABLE image_descriptions (
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
      CREATE VIRTUAL TABLE image_descriptions_fts USING fts5(
        description_search_document,
        tokenize='porter unicode61',
        content='image_descriptions',
        content_rowid='rowid'
      );
      CREATE TABLE image_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_key TEXT NOT NULL,
        image_type TEXT NOT NULL DEFAULT 'catalog',
        perspective_slug TEXT NOT NULL,
        score INTEGER NOT NULL,
        rationale TEXT,
        model_used TEXT,
        prompt_version TEXT NOT NULL DEFAULT '',
        scored_at TEXT NOT NULL,
        is_current INTEGER NOT NULL DEFAULT 1,
        repaired_from_malformed INTEGER NOT NULL DEFAULT 0,
        not_attempted INTEGER NOT NULL DEFAULT 0
      );
    `);
    db.close();
  }

  private open(): Database.Database {
    return new Database(this.dbPath);
  }

  addPerspectives(...seeds: PerspectiveSeed[]): this {
    const db = this.open();
    const stmt = db.prepare(
      `INSERT INTO perspectives
         (slug, display_name, description, prompt_markdown, active, optional,
          source_filename, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    );
    for (const s of seeds) {
      stmt.run(
        s.slug,
        s.display_name ?? s.slug,
        s.description ?? '',
        s.prompt_markdown ?? `# ${s.slug}`,
        s.active === false ? 0 : 1,
        s.optional ? 1 : 0,
        s.source_filename ?? null,
        s.created_at ?? '2026-01-01T00:00:00+00:00',
        s.updated_at ?? '2026-01-02T00:00:00+00:00',
      );
    }
    db.close();
    return this;
  }

  addScores(...seeds: ScoreSeed[]): this {
    const db = this.open();
    const stmt = db.prepare(
      `INSERT INTO image_scores
         (image_key, image_type, perspective_slug, score, rationale, model_used,
          prompt_version, scored_at, is_current, repaired_from_malformed, not_attempted)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    );
    for (const s of seeds) {
      stmt.run(
        s.image_key,
        s.image_type ?? 'catalog',
        s.perspective_slug,
        s.score,
        s.rationale ?? null,
        s.model_used ?? null,
        s.prompt_version ?? 'v1',
        s.scored_at ?? '2026-01-01T00:00:00+00:00',
        s.is_current === false ? 0 : 1,
        s.repaired_from_malformed ? 1 : 0,
        s.not_attempted ? 1 : 0,
      );
    }
    db.close();
    return this;
  }

  addImages(...keys: string[]): this {
    const db = this.open();
    const stmt = db.prepare('INSERT INTO images (key, filename, filepath) VALUES (?, ?, ?)');
    for (const k of keys) stmt.run(k, `${k}.jpg`, `/photos/${k}.jpg`);
    db.close();
    return this;
  }

  /** An image with explicit column values, for tests that filter or sort on them. */
  addImage(seed: ImageSeed): this {
    const db = this.open();
    db.prepare(
      `INSERT INTO images
         (key, id, filename, filepath, date_taken, rating, pick, color_label,
          keywords, title, description, instagram_posted, width, height)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      seed.key,
      seed.id ?? null,
      seed.filename ?? `${seed.key}.jpg`,
      seed.filepath ?? `/photos/${seed.key}.jpg`,
      seed.date_taken ?? null,
      seed.rating ?? 0,
      seed.pick ?? 0,
      seed.color_label ?? '',
      seed.keywords ?? '[]',
      seed.title ?? '',
      seed.description ?? '',
      seed.instagram_posted ? 1 : 0,
      seed.width ?? null,
      seed.height ?? null,
    );
    db.close();
    return this;
  }

  /**
   * Create a stack over `memberKeys`, with the first as representative unless
   * `representative` says otherwise. Returns the fixture; read the id with
   * `stackIdFor`.
   */
  addStack(memberKeys: string[], representative?: string): number {
    const db = this.open();
    const rep = representative ?? memberKeys[0]!;
    const info = db
      .prepare('INSERT INTO image_stacks (representative_key, stack_size) VALUES (?, ?)')
      .run(rep, memberKeys.length);
    const stackId = Number(info.lastInsertRowid);
    const stmt = db.prepare(
      'INSERT INTO image_stack_members (stack_id, image_key) VALUES (?, ?)',
    );
    for (const k of memberKeys) stmt.run(stackId, k);
    db.close();
    return stackId;
  }

  /** A similarity group with ranked candidates. Returns the group id. */
  addSimilarityGroup(seed: {
    seed_key: string;
    candidates: { key: string; similarity: number; why_matched?: string }[];
    job_id?: string | null;
    created_at?: string;
  }): number {
    const db = this.open();
    const best = Math.max(...seed.candidates.map((c) => c.similarity));
    const info = db
      .prepare(
        `INSERT INTO catalog_similarity_groups
           (seed_key, candidate_count, best_similarity, job_id, created_at)
         VALUES (?, ?, ?, ?, ?)`,
      )
      .run(
        seed.seed_key,
        seed.candidates.length,
        best,
        seed.job_id ?? null,
        seed.created_at ?? '2026-02-01T00:00:00',
      );
    const groupId = Number(info.lastInsertRowid);
    const stmt = db.prepare(
      `INSERT INTO catalog_similarity_candidates
         (group_id, candidate_key, similarity, rank, why_matched)
       VALUES (?, ?, ?, ?, ?)`,
    );
    seed.candidates.forEach((cand, i) => {
      stmt.run(groupId, cand.key, cand.similarity, i + 1, cand.why_matched ?? '');
    });
    db.close();
    return groupId;
  }

  /** Condemn a frame, which removes it from suggestions and the flagged filter. */
  addFrameSubstance(imageKey: string, verdict: 'void' | 'illegible' | 'ok' | 'unknown'): this {
    const db = this.open();
    db.prepare(
      `INSERT INTO image_frame_substance (image_key, verdict, detector_version, run_id)
       VALUES (?, ?, 'test', 1)`,
    ).run(imageKey, verdict);
    db.close();
    return this;
  }

  /** A user override, which un-condemns a flagged frame. */
  addFrameSubstanceOverride(imageKey: string): this {
    const db = this.open();
    db.prepare('INSERT INTO frame_substance_overrides (image_key) VALUES (?)').run(imageKey);
    db.close();
    return this;
  }

  /** Direct SQL, for the handful of assertions that need to inspect writes. */
  query<T = Record<string, unknown>>(sql: string, ...params: unknown[]): T[] {
    const db = this.open();
    try {
      return db.prepare(sql).all(...(params as never[])) as T[];
    } finally {
      db.close();
    }
  }

  /** Point the app at this database for the duration of a test. */
  activate(): this {
    process.env.LIBRARY_DB = this.dbPath;
    return this;
  }

  cleanup(): void {
    delete process.env.LIBRARY_DB;
    rmSync(this.dir, { recursive: true, force: true });
  }
}
