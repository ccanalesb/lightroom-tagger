/**
 * The Lightroom reader, the incremental sync driver and the `catalog_sync` job.
 * Mirrors `core/test_catalog_sync.py` and `tests/test_handlers_catalog_sync.py`.
 *
 * Python mocks `connect_catalog` and `get_image_by_id` out; here the `.lrcat` is a
 * real SQLite file with the tables the metadata join actually reads. That costs a
 * fixture and buys the half of the port most likely to be wrong — the join, the
 * `or`-coalescing of every column, and the key the record ends up under, which has
 * to match the 43,451 keys Python already wrote.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { stringify as stringifyYaml } from 'yaml';
import { makeFakeCatalog, type CatalogFile } from './helpers/fake-catalog.js';
import { LibraryFixture } from './helpers/library-fixture.js';
import { openLibraryDb, type Db } from '../src/db/connection.js';
import { createJob, getJob, initJobsDb } from '../src/db/jobs/jobs.js';
import { JobRunner } from '../src/jobs/runner.js';
import { tick } from '../src/jobs/processor.js';
import {
  CATALOG_LOCKED_MSG,
  CatalogSyncError,
  catalogSyncErrorMessage,
  listLibraryCatalogIds,
  syncCatalog,
} from '../src/lightroom/catalog-sync.js';
import {
  connectCatalogReadOnly,
  generateRecordKey,
  getImageById,
  listCatalogFileIds,
  parseCatalogDate,
  parseGps,
  resolveCatalogLockingMode,
} from '../src/lightroom/reader.js';

let fx: LibraryFixture;
let dir: string;
let lrcatPath: string;
let cfgPath: string;
let jobsDbPath: string;

function withCatalog<T>(fn: (conn: Db) => T): T {
  const conn = connectCatalogReadOnly(lrcatPath);
  try {
    return fn(conn);
  } finally {
    conn.close();
  }
}

function withLibrary<T>(fn: (db: Db) => T): T {
  const db = openLibraryDb(fx.dbPath);
  try {
    return fn(db);
  } finally {
    db.close();
  }
}

/** A library row carrying an explicit `images.id`, the column the diff reads. */
const seedLibraryImage = (key: string, catalogId: string | null) =>
  fx.addImage({ key, id: catalogId });

const syncedImages = () =>
  fx.query<{ key: string; id: string; filepath: string; keywords: string }>(
    'SELECT key, id, filepath, keywords FROM images ORDER BY key',
  );

beforeEach(() => {
  fx = new LibraryFixture().activate();
  dir = mkdtempSync(join(tmpdir(), 'lt-sync-'));
  lrcatPath = join(dir, 'Test Catalog.lrcat');
  cfgPath = join(dir, 'config.yaml');
  jobsDbPath = join(dir, 'visualizer.db');
  process.env.LT_CONFIG_YAML = cfgPath;
  writeFileSync(cfgPath, stringifyYaml({ catalog_path: lrcatPath }));
});

afterEach(() => {
  fx.cleanup();
  delete process.env.LT_CONFIG_YAML;
  delete process.env.LIGHTROOM_CATALOG_LOCKING_MODE;
  delete process.env.LIGHTROOM_CATALOG_READONLY_URI;
  rmSync(dir, { recursive: true, force: true });
});

describe('lightroom reader', () => {
  it('builds the record the library stores, key and path included', () => {
    makeFakeCatalog(lrcatPath, [
      { id: 100, baseName: 'L1007168', extension: 'DNG', keywords: ['sunset', 'maine'] },
    ]);

    const record = withCatalog((conn) => getImageById(conn, 100))!;

    expect(record).toMatchObject({
      id: 100,
      key: '2024-06-01_L1007168',
      filename: 'L1007168',
      // Root and folder both carry their own trailing slash; the reader concatenates.
      filepath: '/Volumes/photos/2024/L1007168.DNG',
      date_taken: '2024-06-01T12:00:00',
      color_label: 'blue',
      caption: '',
      iso: 400,
      width: 6000,
      height: 4000,
      gps_latitude: 42.36,
      gps_longitude: -70.65,
    });
  });

  it('finds no keywords, because the join uses the file id (see reader.ts)', () => {
    makeFakeCatalog(lrcatPath, [
      { id: 100, baseName: 'L1007168', keywords: ['sunset', 'maine'] },
    ]);
    // `AgLibraryKeywordImage.image` is an `Adobe_images.id_local`, and the reader
    // passes an `AgLibraryFile.id_local`. Pinned so a "fix" is a deliberate change
    // with a backfill behind it, not an accident. See #304.
    expect(withCatalog((conn) => getImageById(conn, 100))!.keywords).toEqual([]);
  });

  it('coalesces on falsiness the way Python does', () => {
    makeFakeCatalog(lrcatPath, [
      { id: 100, baseName: 'zeroes', rating: 0, pick: -1, focalLength: 0, gpsLatitude: 0 },
    ]);

    const record = withCatalog((conn) => getImageById(conn, 100))!;

    // A rejected pick is -1 in the catalog, and `bool(-1)` is true.
    expect(record.pick).toBe(true);
    expect(record.rating).toBe(0);
    // Not 0: Python's `row[...] or ''` turns a zero focal length into empty text.
    expect(record.focal_length).toBe('');
    // Not 0 either: Null Island reads as "no coordinate".
    expect(record.gps_latitude).toBeNull();
  });

  it('returns null for a file id the catalog does not have', () => {
    makeFakeCatalog(lrcatPath, [{ id: 100, baseName: 'a' }]);
    expect(withCatalog((conn) => getImageById(conn, 999))).toBeNull();
  });

  it('lists every file id', () => {
    makeFakeCatalog(lrcatPath, [
      { id: 100, baseName: 'a' },
      { id: 38887, baseName: 'b' },
    ]);
    expect(withCatalog(listCatalogFileIds).sort((a, b) => a - b)).toEqual([100, 38887]);
  });

  it('opens the catalog read-only', () => {
    makeFakeCatalog(lrcatPath, [{ id: 100, baseName: 'a' }]);
    expect(() =>
      withCatalog((conn) => conn.prepare('DELETE FROM AgLibraryFile').run()),
    ).toThrow(/readonly/i);
  });

  it('defaults locking mode by open mode, and honours the override', () => {
    expect(resolveCatalogLockingMode(true)).toBe('NORMAL');
    expect(resolveCatalogLockingMode(false)).toBe('EXCLUSIVE');
    process.env.LIGHTROOM_CATALOG_LOCKING_MODE = 'exclusive';
    expect(resolveCatalogLockingMode(true)).toBe('EXCLUSIVE');
  });

  it('zero-pads a capture time so the key matches what Python wrote', () => {
    expect(parseCatalogDate('2024-1-5T9:07:00')).toBe('2024-01-05T09:07:00');
    expect(parseCatalogDate('2024-06-01T12:00:00')).toBe('2024-06-01T12:00:00');
    // Anything the format cannot read comes back untouched, as strptime's caller does.
    expect(parseCatalogDate('sometime in June')).toBe('sometime in June');
    expect(parseCatalogDate(null)).toBeNull();
  });

  it('keys an undated image under "unknown"', () => {
    expect(generateRecordKey({ date_taken: '', filename: 'a' })).toBe('unknown_a');
    expect(parseGps('not a number')).toBeNull();
  });
});

describe('listLibraryCatalogIds', () => {
  it('skips empty and non-numeric ids', () => {
    seedLibraryImage('a', '100');
    seedLibraryImage('b', '');
    seedLibraryImage('c', null);
    seedLibraryImage('d', 'not-a-number');
    seedLibraryImage('e', '9999');

    expect(withLibrary(listLibraryCatalogIds)).toEqual(new Set([100, 9999]));
  });
});

describe('syncCatalog', () => {
  it('fetches only the ids the library is missing', () => {
    makeFakeCatalog(
      lrcatPath,
      [1, 2, 3, 5, 99999].map((id) => ({ id, baseName: `img${id}` })),
    );
    seedLibraryImage('existing', '1');
    seedLibraryImage('gap', '5');

    const { result } = withLibrary((db) => syncCatalog(lrcatPath, db));

    expect(result).toMatchObject({
      added: 3,
      stale: 0,
      missing_ids_count: 3,
      catalog_total: 5,
      library_total: 2,
    });
    expect(syncedImages().map((r) => r.key)).toEqual([
      '2024-06-01_img2',
      '2024-06-01_img3',
      '2024-06-01_img99999',
      'existing',
      'gap',
    ]);
  });

  it('reports stale library rows without deleting them', () => {
    makeFakeCatalog(lrcatPath, []);
    seedLibraryImage('gone', '42');

    const { result } = withLibrary((db) => syncCatalog(lrcatPath, db));

    expect(result).toMatchObject({ added: 0, stale: 1 });
    expect(syncedImages()).toHaveLength(1);
  });

  it('diffs ids numerically, not lexicographically', () => {
    makeFakeCatalog(lrcatPath, [
      { id: 38887, baseName: 'have' },
      { id: 99999, baseName: 'new' },
    ]);
    seedLibraryImage('high', '38887');

    const { result } = withLibrary((db) => syncCatalog(lrcatPath, db));

    expect(result).toMatchObject({ added: 1, missing_ids_count: 1 });
    expect(syncedImages().map((r) => r.key)).toContain('2024-06-01_new');
  });

  it('stores the catalog id as an integer, not as a REAL bind', () => {
    makeFakeCatalog(lrcatPath, [{ id: 100, baseName: 'a' }]);

    withLibrary((db) => syncCatalog(lrcatPath, db));

    // `'100.0'` here would parse back as no id at all, so the next sync would
    // re-fetch the whole catalog, forever.
    expect(syncedImages()[0]!.id).toBe('100');
  });

  it('does not re-fetch an image it already has', () => {
    makeFakeCatalog(lrcatPath, [{ id: 1, baseName: 'once' }]);
    withLibrary((db) => syncCatalog(lrcatPath, db));

    // Same id, so the second run sees nothing missing and writes nothing.
    const { result } = withLibrary((db) => syncCatalog(lrcatPath, db));

    expect(result).toMatchObject({ added: 0, missing_ids_count: 0, library_total: 1 });
    expect(syncedImages()).toHaveLength(1);
  });

  it('raises an actionable error when the catalog cannot be opened', () => {
    expect(() => withLibrary((db) => syncCatalog(join(dir, 'absent.lrcat'), db))).toThrow(
      CatalogSyncError,
    );
  });

  it('translates the three failures the user can act on', () => {
    expect(catalogSyncErrorMessage(new Error('database is locked'))).toBe(CATALOG_LOCKED_MSG);
    expect(catalogSyncErrorMessage(new Error('unable to open database file'))).toContain(
      'LIGHTROOM_CATALOG_LOCKING_MODE=EXCLUSIVE',
    );
    expect(catalogSyncErrorMessage(new Error('file is not a database'))).toBe(
      'Cannot read Lightroom catalog: file is not a database',
    );
  });

  it('reports progress and logs the set-difference summary', () => {
    makeFakeCatalog(lrcatPath, [
      { id: 1, baseName: 'a' },
      { id: 2, baseName: 'b' },
    ]);
    const progress: [number, string][] = [];
    const logs: string[] = [];

    withLibrary((db) =>
      syncCatalog(lrcatPath, db, {
        progress: (pct, msg) => progress.push([pct, msg]),
        log: (_level, msg) => logs.push(msg),
      }),
    );

    expect(progress).toEqual([
      [50, 'Fetching catalog metadata 1/2'],
      [95, 'Fetching catalog metadata 2/2'],
      [100, 'Catalog sync complete'],
    ]);
    expect(logs[0]).toContain('catalog_total=2 library_total=0 missing=2 stale=0');
    expect(logs[1]).toContain('complete added=2 stale=0');
  });

  it('stops on cancellation and keeps what it already fetched', () => {
    makeFakeCatalog(
      lrcatPath,
      [1, 2, 3, 4].map((id) => ({ id, baseName: `img${id}` })),
    );
    let seen = 0;

    const { result, cancelled } = withLibrary((db) =>
      syncCatalog(lrcatPath, db, {
        isCancelled: () => {
          seen += 1;
          return seen > 2;
        },
      }),
    );

    expect(cancelled).toBe(true);
    expect(result.added).toBe(2);
    expect(syncedImages()).toHaveLength(2);
  });
});

describe('catalog_sync handler', () => {
  /** Enqueue, run one processor pass, and hand back the settled job. */
  async function runJob(metadata: Record<string, unknown> = {}) {
    const db = initJobsDb(jobsDbPath);
    try {
      const jobId = createJob(db, 'catalog_sync', metadata);
      await tick(db, new JobRunner(db));
      return getJob(db, jobId)!;
    } finally {
      db.close();
    }
  }

  it('completes with the sync result', async () => {
    makeFakeCatalog(lrcatPath, [
      { id: 1, baseName: 'a' },
      { id: 2, baseName: 'b' },
    ]);

    const job = await runJob();

    expect(job.status).toBe('completed');
    expect(job.result).toMatchObject({
      added: 2,
      stale: 0,
      locking_mode: 'NORMAL',
      catalog_total: 2,
      library_total: 0,
      missing_ids_count: 2,
    });
    expect(syncedImages()).toHaveLength(2);
  });

  it('takes the catalog path from the job metadata over config.yaml', async () => {
    const other = join(dir, 'Other.lrcat');
    makeFakeCatalog(lrcatPath, [{ id: 1, baseName: 'from-config' }]);
    makeFakeCatalog(other, [{ id: 2, baseName: 'from-metadata' }]);

    await runJob({ catalog_path: other });

    expect(syncedImages().map((r) => r.key)).toEqual(['2024-06-01_from-metadata']);
  });

  it('fails as a warning when no catalog is configured', async () => {
    writeFileSync(cfgPath, stringifyYaml({ workers: 4 }));

    const job = await runJob();

    expect(job.status).toBe('failed');
    expect(job.error).toBe('No catalog path configured. Set catalog_path in config.yaml.');
    expect(job.error_severity).toBe('warning');
  });

  it('fails as a warning when the configured catalog is not there', async () => {
    const missing = join(dir, 'absent.lrcat');
    writeFileSync(cfgPath, stringifyYaml({ catalog_path: missing }));

    const job = await runJob();

    expect(job.status).toBe('failed');
    expect(job.error).toBe(`Catalog not found: ${missing}`);
    expect(job.error_severity).toBe('warning');
  });

  it('fails on a file that is not a catalog, with SQLite\u2019s own words', async () => {
    writeFileSync(lrcatPath, 'this is not a Lightroom catalog');

    const job = await runJob();

    expect(job.status).toBe('failed');
    // Not the friendly "Cannot read Lightroom catalog: …" text, because a
    // read-only open succeeds and the header check fires on the first query —
    // and only the *open* is wrapped. Faithful to Python, quirk included.
    expect(job.error).toBe('file is not a database');
    expect(job.error_severity).toBe('error');
  });
});
