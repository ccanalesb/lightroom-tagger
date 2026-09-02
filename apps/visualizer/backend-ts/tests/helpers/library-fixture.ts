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
        filename TEXT,
        filepath TEXT,
        date_taken TEXT,
        rating INTEGER,
        instagram_posted INTEGER DEFAULT 0
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
