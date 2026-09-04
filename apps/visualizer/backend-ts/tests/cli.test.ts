/**
 * The `lightroom-tagger` CLI: parsing, dispatch, error mapping, and the three
 * read-only commands.
 *
 * Driven through `run()` rather than a subprocess, so a failing assertion points
 * at a line instead of at a captured stream. `run()` is the whole program below
 * `bin.ts`, so nothing about dispatch or exit codes is stubbed out.
 */
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { loadLibraryConfig, type LibraryConfig } from '../src/config.js';
import { openLibraryDb } from '../src/db/connection.js';
import { LIBRARY_SCHEMA_VERSION } from '../src/db/library/bootstrap.js';
import { parseArgv, UsageError } from '../src/cli/parse.js';
import { COMMANDS } from '../src/cli/registry.js';
import { run } from '../src/cli/main.js';
import { makeFakeCatalog } from './helpers/fake-catalog.js';
import { LibraryFixture } from './helpers/library-fixture.js';

/** Config with nothing in it: every path has to come from a flag. */
const EMPTY_CONFIG = (): LibraryConfig => loadLibraryConfig('/nonexistent/config.yaml');

interface Outcome {
  code: number;
  lines: string[];
  text: string;
}

function cli(argv: string[], config: LibraryConfig = EMPTY_CONFIG()): Outcome {
  const lines: string[] = [];
  const code = run(argv, { out: (line) => lines.push(line), config });
  return { code, lines, text: lines.join('\n') };
}

describe('argv parsing', () => {
  it('splits global flags from the subcommand’s own', () => {
    const args = parseArgv(['--db', 'g.db', 'search', '--keyword', 'sunset'], COMMANDS);
    expect(args.command).toBe('search');
    expect(args.global['db']).toBe('g.db');
    expect(args.local['keyword']).toBe('sunset');
  });

  it('accepts short aliases and --flag=value for globals', () => {
    const args = parseArgv(['-d', 'g.db', '--config=other.yaml', 'stats'], COMMANDS);
    expect(args.global['db']).toBe('g.db');
    expect(args.global['config']).toBe('other.yaml');
  });

  it('parses int flags as numbers and boolean flags as switches', () => {
    const args = parseArgv(['enrich-catalog', '--limit', '25', '--cache-only'], COMMANDS);
    expect(args.local['limit']).toBe(25);
    expect(args.local['cache-only']).toBe(true);
  });

  /**
   * The divergence from Python. argparse reparses a subcommand into a fresh
   * namespace and copies all of it back, so an absent subcommand `--db`
   * overwrites the global one with `None` and `--db X search` silently reads
   * `config.yaml` instead. Both positions work here.
   */
  it('lets a subcommand flag override a global one, and honours the global alone', () => {
    const overridden = parseArgv(['--db', 'global.db', 'search', '--db', 'local.db'], COMMANDS);
    const globalOnly = parseArgv(['--db', 'global.db', 'search'], COMMANDS);
    expect(overridden.local['db'] ?? overridden.global['db']).toBe('local.db');
    expect(globalOnly.local['db'] ?? globalOnly.global['db']).toBe('global.db');
  });

  it.each([
    [[], 'no command given'],
    [['nope'], 'unknown command: nope'],
    [['search', '--nope'], 'unrecognized arguments: --nope'],
    [['search', '--keyword'], 'argument --keyword: expected one argument'],
    [['search', '--rating', 'high'], "argument --rating: invalid int value: 'high'"],
    [['export', '--format', 'xml'], "argument --format: invalid choice: 'xml'"],
    [['export'], 'the following arguments are required: --output'],
    [['search', 'stray'], 'unexpected argument: stray'],
  ])('rejects %j', (argv, message) => {
    expect(() => parseArgv(argv, COMMANDS)).toThrow(UsageError);
    expect(() => parseArgv(argv, COMMANDS)).toThrow(message);
  });
});

describe('run', () => {
  it('prints help and exits 1 when no command is given', () => {
    const r = cli([]);
    expect(r.code).toBe(1);
    expect(r.text).toContain('usage: lightroom-tagger');
    expect(r.text).toContain('enrich-catalog');
  });

  it('reports an unported command as such, not as an unknown one', () => {
    const r = cli(['enrich-catalog', '--db', '/tmp/x.db']);
    expect(r.code).toBe(1);
    expect(r.text).toBe('Error: enrich-catalog is not ported to the TypeScript CLI yet');
  });

  it('refuses a command with no database path anywhere', () => {
    const r = cli(['stats']);
    expect(r.code).toBe(1);
    expect(r.text).toBe('Error: No database path provided. Use --db or config.yaml');
  });

  it.each(['search', 'export', 'stats'])('refuses %s when the database is absent', (name) => {
    const missing = '/nonexistent/library.db';
    const argv = name === 'export' ? [name, '--output', '/tmp/x.json'] : [name];
    const r = cli([...argv, '--db', missing]);
    expect(r.code).toBe(1);
    expect(r.text).toBe(`Error: Database not found: ${missing}`);
  });

  it('maps an unexpected throw to Error: … and exit 1', () => {
    // A directory is a path that exists, so it clears the must-exist guard and
    // fails inside the command — the case Python's bare `except Exception` covers.
    const fixture = new LibraryFixture();
    try {
      const r = cli(['stats', '--db', fixture.dir]);
      expect(r.code).toBe(1);
      expect(r.lines[0]).toMatch(/^Error: /);
    } finally {
      fixture.cleanup();
    }
  });
});

describe('read-only commands', () => {
  let fixture: LibraryFixture;

  beforeEach(() => {
    fixture = new LibraryFixture();
    fixture
      .addImage({
        key: '2026-01-01_a.jpg',
        filename: 'a.jpg',
        rating: 5,
        color_label: 'Red',
        date_taken: '2026-01-01T10:00:00',
        keywords: '["sunset","beach"]',
      })
      .addImage({
        key: '2026-02-01_b.jpg',
        filename: 'b.jpg',
        rating: 3,
        color_label: 'blue',
        date_taken: '2026-02-01T10:00:00',
        keywords: '["forest"]',
      })
      .addImage({
        key: '2026-03-01_c.jpg',
        filename: 'c.jpg',
        rating: 0,
        date_taken: '2026-03-01T10:00:00',
      });
  });

  afterEach(() => fixture.cleanup());

  const search = (...flags: string[]): Outcome =>
    cli(['search', '--db', fixture.dbPath, ...flags]);

  it('lists every image when given no filter', () => {
    const r = search();
    expect(r.code).toBe(0);
    expect(r.lines[0]).toBe('Found 3 images');
    expect(r.lines[1]).toBe('  2026-01-01_a.jpg: a.jpg (rating: 5)');
  });

  /**
   * `--keyword` is seeded with real `keywords` JSON here, which no row in the
   * live `library.db` has: the reader's id mix-up means that column is `[]` on
   * all 43,794 of them, so the `keywords LIKE` half has never matched in
   * production. Seeded anyway, because the query is what is under test.
   */
  it.each([
    [['--keyword', 'sunset'], 1],
    [['--keyword', 'forest'], 1],
    [['--keyword', 'b.jpg'], 1],
    [['--rating', '3'], 2],
    [['--rating', '0'], 3],
    [['--color-label', 'RED'], 1],
    [['--date-start', '2026-02-01'], 2],
    [['--date-start', '2026-01-01', '--date-end', '2026-02-28'], 2],
  ])('filters with %j', (flags, expected) => {
    expect(search(...flags).lines[0]).toBe(`Found ${expected} images`);
  });

  it('applies the first filter given rather than intersecting them', () => {
    // `--keyword` is checked before `--rating`, so the rating is not consulted.
    expect(search('--keyword', 'sunset', '--rating', '5').lines[0]).toBe('Found 1 images');
    expect(search('--keyword', 'forest', '--rating', '5').lines[0]).toBe('Found 1 images');
  });

  it('truncates with --limit, and treats --limit 0 as no limit', () => {
    expect(search('--limit', '2').lines[0]).toBe('Found 2 images');
    expect(search('--limit', '0').lines[0]).toBe('Found 3 images');
  });

  it('honours --db written before the subcommand', () => {
    const r = cli(['--db', fixture.dbPath, 'search']);
    expect(r.code).toBe(0);
    expect(r.lines[0]).toBe('Found 3 images');
  });

  it('falls back to db_path from config.yaml', () => {
    const config = { ...EMPTY_CONFIG(), dbPath: fixture.dbPath };
    expect(cli(['search'], config).lines[0]).toBe('Found 3 images');
  });

  it('reports counts and a rating histogram for stats', () => {
    const r = cli(['stats', '--db', fixture.dbPath]);
    expect(r.code).toBe(0);
    expect(r.lines).toEqual([
      `Database: ${fixture.dbPath}`,
      'Total images: 3',
      'Ratings breakdown:',
      '  0 star: 1',
      '  3 star: 1',
      '  5 star: 1',
    ]);
  });

  it('exports JSON with the decoded keyword column', () => {
    const out = join(fixture.dir, 'export.json');
    const r = cli(['export', '--db', fixture.dbPath, '--output', out]);
    expect(r.code).toBe(0);
    expect(r.text).toBe(`Exported 3 images to ${out}`);

    const parsed = JSON.parse(readFileSync(out, 'utf8')) as Record<string, unknown>[];
    expect(parsed).toHaveLength(3);
    expect(parsed[0]!['keywords']).toEqual(['sunset', 'beach']);
    expect(parsed[0]!['instagram_posted']).toBe(false);
  });

  it('exports CSV with a header row and one line per image', () => {
    const out = join(fixture.dir, 'export.csv');
    const r = cli([
      'export',
      '--db',
      fixture.dbPath,
      '--output',
      out,
      '--format',
      'csv',
      '--rating',
      '3',
    ]);
    expect(r.code).toBe(0);
    expect(r.text).toBe(`Exported 2 images to ${out}`);

    const rows = readFileSync(out, 'utf8').trimEnd().split('\r\n');
    expect(rows).toHaveLength(3);
    expect(rows[0]!.split(',')[0]).toBe('key');
    expect(rows[1]).toContain('2026-01-01_a.jpg');
  });

  /**
   * The one place the CLI does not match Python byte-for-byte. `csv.DictWriter`
   * `str()`s a decoded column, so Python writes `['sunset', 'beach']` and
   * `False` where these write JSON and `false`. Asserted so the divergence stays
   * a decision rather than becoming a surprise.
   */
  it('writes JSON and lowercase booleans in CSV where Python writes reprs', () => {
    const out = join(fixture.dir, 'repr.csv');
    cli(['export', '--db', fixture.dbPath, '--output', out, '--format', 'csv']);
    const body = readFileSync(out, 'utf8');
    expect(body).toContain('"[""sunset"",""beach""]"');
    expect(body).not.toContain("['sunset', 'beach']");
    expect(body).toContain(',false,');
  });

  it('writes no file for an empty CSV export, as Python does', () => {
    const out = join(fixture.dir, 'empty.csv');
    const r = cli([
      'export',
      '--db',
      fixture.dbPath,
      '--output',
      out,
      '--format',
      'csv',
      '--keyword',
      'nothingmatchesthis',
    ]);
    expect(r.code).toBe(0);
    expect(r.text).toBe(`Exported 0 images to ${out}`);
    expect(() => readFileSync(out, 'utf8')).toThrow();
  });
});

describe('scan and sync', () => {
  let fixture: LibraryFixture;
  let catalogPath: string;

  beforeEach(() => {
    fixture = new LibraryFixture();
    catalogPath = join(fixture.dir, 'Catalog.lrcat');
    makeFakeCatalog(catalogPath, [
      { id: 101, baseName: 'DSC_0001', captureTime: '2024-06-01T12:00:00', rating: 4 },
      { id: 102, baseName: 'DSC_0002', captureTime: '2024-06-02T12:00:00', rating: 2 },
      { id: 103, baseName: 'DSC_0003', captureTime: '2024-06-03T12:00:00' },
    ]);
  });

  afterEach(() => fixture.cleanup());

  const scan = (...flags: string[]): Outcome =>
    cli(['scan', '--catalog', catalogPath, '--db', fixture.dbPath, ...flags]);
  const sync = (...flags: string[]): Outcome =>
    cli(['sync', '--catalog', catalogPath, '--db', fixture.dbPath, ...flags]);

  it('indexes every catalog image', () => {
    const r = scan();
    expect(r.code).toBe(0);
    expect(r.lines).toEqual([
      `Scanning catalog: ${catalogPath}`,
      'Retrieved 3 image records',
      `Indexed 3 images to ${fixture.dbPath}`,
    ]);
    expect(fixture.query('SELECT key, rating FROM images ORDER BY key')).toEqual([
      // The key is built from `AgLibraryFile.baseName`, so no extension.
      { key: '2024-06-01_DSC_0001', rating: 4 },
      { key: '2024-06-02_DSC_0002', rating: 2 },
      { key: '2024-06-03_DSC_0003', rating: 0 },
    ]);
  });

  it('stores the catalog id as an integer, not a float', () => {
    // A JS number binds as REAL, which would write '101.0' into the TEXT `id`
    // column and make every later sync re-fetch the whole catalog.
    scan();
    expect(fixture.query<{ id: string }>('SELECT id FROM images ORDER BY key')[0]!.id).toBe('101');
  });

  it('honours --limit and prints the catalog total under --verbose', () => {
    const r = scan('--limit', '2');
    expect(r.lines[1]).toBe('Retrieved 2 image records');
    expect(fixture.query('SELECT key FROM images')).toHaveLength(2);

    // `--verbose` is a global flag no subcommand redeclares, so it goes first.
    const v = cli(['--verbose', 'scan', '--catalog', catalogPath, '--db', fixture.dbPath]);
    expect(v.lines[1]).toBe('Total images in catalog: 3');
  });

  it('accepts --workers and ignores it, as Python does', () => {
    const r = scan('--workers', '8');
    expect(r.code).toBe(0);
    expect(r.lines[1]).toBe('Retrieved 3 image records');
  });

  it('re-scanning upserts rather than duplicating', () => {
    scan();
    const r = scan();
    expect(r.code).toBe(0);
    expect(fixture.query('SELECT key FROM images')).toHaveLength(3);
  });

  it('adds every image on a first sync and nothing on a second', () => {
    const first = sync();
    expect(first.code).toBe(0);
    expect(first.lines[0]).toBe(`Syncing catalog: ${catalogPath}`);
    expect(first.lines[1]).toMatch(/^Added 3 images; 0 stale in library \(locking_mode=\w+\)$/);

    expect(sync().lines[1]).toMatch(/^Added 0 images; 0 stale in library/);
  });

  it('counts a library row the catalog no longer has as stale', () => {
    sync();
    fixture.exec("INSERT INTO images (key, id, filename) VALUES ('orphan', '999', 'x.jpg')");
    expect(sync().lines[1]).toMatch(/^Added 0 images; 1 stale in library/);
  });

  it.each(['scan', 'sync'])('%s refuses a catalog that is not there', (name) => {
    const r = cli([name, '--catalog', '/nonexistent/Catalog.lrcat', '--db', fixture.dbPath]);
    expect(r.code).toBe(1);
    expect(r.text).toBe('Error: Catalog not found: /nonexistent/Catalog.lrcat');
  });

  it.each(['scan', 'sync'])('%s refuses when no catalog path is configured', (name) => {
    const r = cli([name, '--db', fixture.dbPath]);
    expect(r.code).toBe(1);
    expect(r.text).toBe('Error: No catalog path provided. Use --catalog or config.yaml');
  });

  /**
   * `must_exist=False` means "create the schema" in Python, because
   * `managed_library_db` runs `init_database` on the way in. Both commands
   * therefore have to work against a path that is not there yet.
   */
  it.each(['scan', 'sync'])('%s creates the library it is pointed at', (name) => {
    const fresh = join(fixture.dir, 'fresh.db');
    const r = cli([name, '--catalog', catalogPath, '--db', fresh]);
    expect(r.code).toBe(0);
    const db = openLibraryDb(fresh);
    try {
      expect(db.pragma('user_version', { simple: true })).toBe(LIBRARY_SCHEMA_VERSION);
      expect(
        db.prepare('SELECT COUNT(*) AS cnt FROM images').get(),
      ).toEqual({ cnt: 3 });
    } finally {
      db.close();
    }
  });

  it('reports an unreadable catalog without a stack trace', () => {
    const notACatalog = join(fixture.dir, 'junk.lrcat');
    writeFileSync(notACatalog, 'this is not a database');
    const r = cli(['sync', '--catalog', notACatalog, '--db', fixture.dbPath]);
    expect(r.code).toBe(1);
    expect(r.lines.at(-1)).toMatch(/^Error: /);
  });

  it('leaves the library untouched when a scan cannot finish', () => {
    // A directory in place of the catalog fails at open, after the first line is
    // printed and before anything is written.
    const r = cli(['scan', '--catalog', fixture.dir, '--db', fixture.dbPath]);
    expect(r.code).toBe(1);
    expect(fixture.query('SELECT key FROM images')).toHaveLength(0);
  });
});

describe('init', () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'lt-init-'));
  });

  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it('creates a database and says where, and only that', () => {
    const dbPath = join(dir, 'library.db');
    const r = cli(['init', '--db', dbPath]);
    expect(r.code).toBe(0);
    expect(r.lines).toEqual([`Initialized database at ${dbPath}`]);
    // Python's ladder drops a `.pre-key-migration.bak` and an
    // `instagram-matching-export.json` beside a brand-new file, both backups of
    // nothing. Nothing here writes anything but the database.
    expect(readdirSync(dir)).toEqual(['library.db']);
  });

  it('creates the parent directory when it is not there', () => {
    const dbPath = join(dir, 'nested', 'deeper', 'library.db');
    expect(cli(['init', '--db', dbPath]).code).toBe(0);
    expect(existsSync(dbPath)).toBe(true);
  });

  it('is idempotent, and does not re-seed perspectives an owner deleted', () => {
    const dbPath = join(dir, 'library.db');
    cli(['init', '--db', dbPath]);

    const db = openLibraryDb(dbPath);
    const seeded = (db.prepare('SELECT COUNT(*) AS cnt FROM perspectives').get() as { cnt: number })
      .cnt;
    db.prepare("DELETE FROM perspectives WHERE slug = 'street'").run();
    db.close();
    expect(seeded).toBeGreaterThan(0);

    const again = cli(['init', '--db', dbPath]);
    expect(again.code).toBe(0);
    expect(again.lines).toEqual([`Initialized database at ${dbPath}`]);

    const reopened = openLibraryDb(dbPath);
    expect(
      (reopened.prepare('SELECT COUNT(*) AS cnt FROM perspectives').get() as { cnt: number }).cnt,
    ).toBe(seeded - 1);
    reopened.close();
  });
});

