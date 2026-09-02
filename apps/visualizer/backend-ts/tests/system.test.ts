/**
 * System route tests. Mirrors `tests/test_system_stats_api.py` and
 * `tests/test_system_contract.py`.
 *
 * Fixtures build a real SQLite file rather than mocking the DB layer: the queries
 * are the thing most likely to break in the port, so they must actually run.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import Database from 'better-sqlite3';
import { createApp } from '../src/app.js';

let tmp: string;
let dbPath: string;

/** Minimal `library.db` with just the tables the system routes read. */
function seedLibrary(path: string, opts: { images?: number; posted?: number; cached?: number } = {}) {
  const db = new Database(path);
  db.exec(`
    CREATE TABLE images (
      key TEXT PRIMARY KEY,
      filename TEXT,
      filepath TEXT,
      instagram_posted INTEGER DEFAULT 0
    );
    CREATE TABLE vision_cache (
      key TEXT PRIMARY KEY,
      compressed_path TEXT,
      phash TEXT,
      compressed_at TEXT,
      original_mtime REAL
    );
  `);
  const ins = db.prepare('INSERT INTO images (key, filename, filepath, instagram_posted) VALUES (?, ?, ?, ?)');
  const total = opts.images ?? 0;
  const posted = opts.posted ?? 0;
  for (let i = 0; i < total; i++) ins.run(`k${i}`, `f${i}.jpg`, `/p/f${i}.jpg`, i < posted ? 1 : 0);
  const cins = db.prepare('INSERT INTO vision_cache (key, compressed_path) VALUES (?, ?)');
  for (let i = 0; i < (opts.cached ?? 0); i++) cins.run(`k${i}`, join(tmp, `cache${i}.jpg`));
  db.close();
}

/**
 * Build the app. Config reads env lazily, so a single import is enough — no
 * module-cache busting required.
 */
async function freshApp() {
  return createApp();
}

/** `Response.json()` is `unknown`; assert the shape once here instead of at each use. */
async function jsonOf<T = Record<string, unknown>>(res: Response): Promise<T> {
  return (await res.json()) as T;
}

beforeEach(() => {
  tmp = mkdtempSync(join(tmpdir(), 'lt-sys-'));
  dbPath = join(tmp, 'library.db');
});

afterEach(() => {
  rmSync(tmp, { recursive: true, force: true });
  delete process.env.LIBRARY_DB;
});

describe('GET /api/status', () => {
  it('reports ok', async () => {
    const app = await freshApp();
    const res = await app.request('/api/status');
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: 'ok' });
  });
});

describe('GET /api/stats', () => {
  it('counts catalog images and posted images', async () => {
    seedLibrary(dbPath, { images: 7, posted: 3 });
    process.env.LIBRARY_DB = dbPath;
    const app = await freshApp();

    const res = await app.request('/api/stats');
    expect(res.status).toBe(200);
    const body = await jsonOf<{ catalog_images: number; posted_to_instagram: number; db_path: string }>(res);
    expect(body.catalog_images).toBe(7);
    expect(body.posted_to_instagram).toBe(3);
    expect(body.db_path).toBe(dbPath);
  });

  it('404s when the library database is absent', async () => {
    process.env.LIBRARY_DB = join(tmp, 'nope.db');
    const app = await freshApp();

    const res = await app.request('/api/stats');
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: 'Library database not found' });
  });

  it('returns no extra keys — the schema forbids them', async () => {
    seedLibrary(dbPath, { images: 1 });
    process.env.LIBRARY_DB = dbPath;
    const app = await freshApp();

    const body = await jsonOf(await app.request('/api/stats'));
    expect(Object.keys(body).sort()).toEqual(['catalog_images', 'db_path', 'posted_to_instagram']);
  });
});

describe('GET /api/catalog/status', () => {
  it('reports cached when the vision cache has entries', async () => {
    seedLibrary(dbPath, { images: 4, cached: 2 });
    process.env.LIBRARY_DB = dbPath;
    const app = await freshApp();

    const res = await app.request('/api/catalog/status');
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ cached: true });
  });

  it('reports not cached on an empty vision cache', async () => {
    seedLibrary(dbPath, { images: 4, cached: 0 });
    process.env.LIBRARY_DB = dbPath;
    const app = await freshApp();

    expect(await (await app.request('/api/catalog/status')).json()).toEqual({ cached: false });
  });

  it('reports not cached — not an error — when the database is missing', async () => {
    process.env.LIBRARY_DB = join(tmp, 'nope.db');
    const app = await freshApp();

    const res = await app.request('/api/catalog/status');
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ cached: false });
  });

  it('surfaces a corrupt database as a 500', async () => {
    writeFileSync(dbPath, 'this is not a sqlite file');
    process.env.LIBRARY_DB = dbPath;
    const app = await freshApp();

    const res = await app.request('/api/catalog/status');
    expect(res.status).toBe(500);
    expect(await res.json()).toHaveProperty('error');
  });
});
