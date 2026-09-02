/**
 * Descriptions route tests. Mirrors `tests/test_descriptions_api.py` /
 * `test_descriptions_contract.py`.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import Database from 'better-sqlite3';
import { createApp } from '../src/app.js';
import { LibraryFixture } from './helpers/library-fixture.js';

let fx: LibraryFixture;
const app = createApp();
const json = async <T>(res: Response): Promise<T> => (await res.json()) as T;

/** `image_descriptions` is only needed by this group, so it is created here. */
function withDescriptionsTable(fixture: LibraryFixture): LibraryFixture {
  const db = new Database(fixture.dbPath);
  db.exec(`
    CREATE TABLE image_descriptions (
      image_key TEXT NOT NULL,
      image_type TEXT NOT NULL DEFAULT 'catalog',
      summary TEXT,
      composition TEXT,
      perspectives TEXT,
      technical TEXT,
      subjects TEXT,
      dominant_colors TEXT,
      mood_tags TEXT,
      best_perspective TEXT,
      model_used TEXT,
      described_at TEXT
    );
  `);
  db.close();
  return fixture;
}

function addDescription(
  fixture: LibraryFixture,
  row: {
    image_key: string;
    summary?: string;
    best_perspective?: string;
    model_used?: string;
    described_at?: string | null;
    composition?: string;
    subjects?: string;
    technical?: string;
    perspectives?: string;
  },
): void {
  const db = new Database(fixture.dbPath);
  db.prepare(
    `INSERT INTO image_descriptions
       (image_key, image_type, summary, composition, perspectives, technical,
        subjects, best_perspective, model_used, described_at)
     VALUES (?, 'catalog', ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    row.image_key,
    row.summary ?? 'a summary',
    row.composition ?? '{"depth": "shallow"}',
    row.perspectives ?? '{}',
    row.technical ?? '{"mood": "calm"}',
    row.subjects ?? '["person"]',
    row.best_perspective ?? 'street',
    row.model_used ?? 'test-model',
    row.described_at ?? '2026-02-01T00:00:00+00:00',
  );
  db.close();
}

beforeEach(() => {
  fx = withDescriptionsTable(new LibraryFixture().activate());
});
afterEach(() => fx.cleanup());

describe('GET /api/descriptions/', () => {
  it('lists every image, described or not', async () => {
    fx.addImages('a', 'b');
    addDescription(fx, { image_key: 'a' });

    const res = await app.request('/api/descriptions/');
    expect(res.status).toBe(200);
    const body = await json<{
      total: number;
      items: { image_key: string; has_description: number }[];
    }>(res);

    expect(body.total).toBe(2);
    expect(body.items.map((i) => i.image_key)).toEqual(['a', 'b']);
    expect(body.items.map((i) => i.has_description)).toEqual([1, 0]);
  });

  it('sorts described images before undescribed ones', async () => {
    fx.addImages('undescribed', 'described');
    addDescription(fx, { image_key: 'described' });

    const body = await json<{ items: { image_key: string }[] }>(
      await app.request('/api/descriptions/'),
    );
    // NULL described_at must sort last, or the UI buries the useful rows.
    expect(body.items[0]!.image_key).toBe('described');
  });

  it('filters to described rows only', async () => {
    fx.addImages('a', 'b');
    addDescription(fx, { image_key: 'a' });

    const body = await json<{ total: number; items: unknown[] }>(
      await app.request('/api/descriptions/?described_only=true'),
    );
    expect(body.total).toBe(1);
    expect(body.items).toHaveLength(1);
  });

  it('paginates and reports the envelope', async () => {
    fx.addImages('a', 'b', 'c', 'd', 'e');
    const body = await json<{
      total: number;
      items: unknown[];
      pagination: Record<string, unknown>;
    }>(await app.request('/api/descriptions/?limit=2&offset=2'));

    expect(body.total).toBe(5);
    expect(body.items).toHaveLength(2);
    expect(body.pagination).toEqual({
      offset: 2,
      limit: 2,
      current_page: 2,
      total_pages: 3,
      has_more: true,
    });
  });

  it('reports 0 total_pages for an empty catalog, not 1', async () => {
    // Python guards this with `if total`; a naive ceil would say 1 page of nothing.
    const body = await json<{ total: number; pagination: { total_pages: number } }>(
      await app.request('/api/descriptions/'),
    );
    expect(body.total).toBe(0);
    expect(body.pagination.total_pages).toBe(0);
  });

  it('falls back to defaults for unparseable limit/offset', async () => {
    fx.addImages('a');
    const body = await json<{ pagination: { limit: number; offset: number } }>(
      await app.request('/api/descriptions/?limit=abc&offset=xyz'),
    );
    expect(body.pagination).toMatchObject({ limit: 50, offset: 0 });
  });

  it('rejects a non-catalog image_type', async () => {
    const res = await app.request('/api/descriptions/?image_type=instagram');
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'Invalid image_type: instagram' });
  });

  it('accepts an empty image_type as unset', async () => {
    fx.addImages('a');
    expect((await app.request('/api/descriptions/?image_type=')).status).toBe(200);
  });

  it('308-redirects the bare prefix', async () => {
    const res = await app.request('/api/descriptions');
    expect(res.status).toBe(308);
    expect(res.headers.get('location')).toBe('/api/descriptions/');
  });
});

describe('GET /api/descriptions/{image_key}', () => {
  it('decodes the JSON columns', async () => {
    fx.addImages('a');
    addDescription(fx, {
      image_key: 'a',
      composition: '{"depth": "deep", "layers": ["fg", "bg"]}',
      subjects: '["dog", "beach"]',
    });

    const res = await app.request('/api/descriptions/a');
    expect(res.status).toBe(200);
    const body = await json<{ description: Record<string, unknown> }>(res);

    expect(body.description.composition).toEqual({ depth: 'deep', layers: ['fg', 'bg'] });
    expect(body.description.subjects).toEqual(['dog', 'beach']);
  });

  it('leaves a malformed JSON column as a raw string instead of failing', async () => {
    fx.addImages('a');
    addDescription(fx, { image_key: 'a', composition: 'not json at all' });

    const res = await app.request('/api/descriptions/a');
    expect(res.status).toBe(200);
    const body = await json<{ description: Record<string, unknown> }>(res);
    // One bad legacy row must not take down the panel.
    expect(body.description.composition).toBe('not json at all');
  });

  it('returns description: null with a 200 for an unknown key', async () => {
    const res = await app.request('/api/descriptions/missing');
    expect(res.status).toBe(200);
    expect(await json(res)).toEqual({ description: null });
  });

  it('404s when the library database is missing', async () => {
    process.env.LIBRARY_DB = '/nonexistent/library.db';
    const res = await app.request('/api/descriptions/a');
    expect(res.status).toBe(404);
  });
});
