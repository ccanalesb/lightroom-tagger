/**
 * Scores route tests. Mirrors `tests/test_scores_api.py` / `test_scores_contract.py`.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createApp } from '../src/app.js';
import { LibraryFixture } from './helpers/library-fixture.js';

let fx: LibraryFixture;
const app = createApp();

const json = async <T>(res: Response): Promise<T> => (await res.json()) as T;

beforeEach(() => {
  fx = new LibraryFixture().activate();
});
afterEach(() => fx.cleanup());

describe('GET /api/scores/{image_key}', () => {
  it('returns only current rows, ordered by perspective slug', async () => {
    fx.addScores(
      { image_key: 'img1', perspective_slug: 'zebra', score: 7 },
      { image_key: 'img1', perspective_slug: 'alpha', score: 9 },
      // A superseded row differs from the current one by `prompt_version`; the
      // unique constraint is on that tuple, so there is no other way to hold two.
      { image_key: 'img1', perspective_slug: 'alpha', score: 3, prompt_version: 'v0', is_current: false },
      { image_key: 'other', perspective_slug: 'alpha', score: 1 },
    );

    const res = await app.request('/api/scores/img1');
    expect(res.status).toBe(200);
    const body = await json<{
      image_key: string;
      image_type: string;
      current: { perspective_slug: string; score: number; is_current: boolean }[];
    }>(res);

    expect(body.image_key).toBe('img1');
    expect(body.image_type).toBe('catalog');
    expect(body.current.map((r) => r.perspective_slug)).toEqual(['alpha', 'zebra']);
    expect(body.current.map((r) => r.score)).toEqual([9, 7]);
  });

  it('exposes SQLite 0/1 flags as booleans', async () => {
    fx.addScores({
      image_key: 'img1',
      perspective_slug: 'alpha',
      score: 5,
      repaired_from_malformed: true,
      not_attempted: false,
    });

    const body = await json<{ current: Record<string, unknown>[] }>(
      await app.request('/api/scores/img1'),
    );
    const row = body.current[0]!;
    expect(row.is_current).toBe(true);
    expect(row.repaired_from_malformed).toBe(true);
    expect(row.not_attempted).toBe(false);
  });

  it('returns an empty list for an image with no scores', async () => {
    const body = await json<{ current: unknown[] }>(await app.request('/api/scores/nope'));
    expect(body.current).toEqual([]);
  });

  it('rejects a non-catalog image_type', async () => {
    const res = await app.request('/api/scores/img1?image_type=instagram');
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'image_type must be catalog' });
  });

  it('accepts an explicit catalog image_type', async () => {
    fx.addScores({ image_key: 'img1', perspective_slug: 'alpha', score: 5 });
    const res = await app.request('/api/scores/img1?image_type=CATALOG');
    expect(res.status).toBe(200);
  });

  it('handles keys containing spaces and parentheses', async () => {
    // Real catalog keys use these characters; only slashes are absent.
    const key = 'IMG 0421 (1)';
    fx.addScores({ image_key: key, perspective_slug: 'alpha', score: 4 });
    const res = await app.request(`/api/scores/${encodeURIComponent(key)}`);
    expect(res.status).toBe(200);
    expect((await json<{ image_key: string }>(res)).image_key).toBe(key);
  });

  it('404s when the library database is missing', async () => {
    process.env.LIBRARY_DB = '/nonexistent/library.db';
    const res = await app.request('/api/scores/img1');
    expect(res.status).toBe(404);
    expect(await json(res)).toEqual({ error: 'Library database not found' });
  });
});

describe('GET /api/scores/{image_key}/history', () => {
  it('returns history newest first, including superseded rows', async () => {
    fx.addScores(
      {
        image_key: 'img1',
        perspective_slug: 'alpha',
        score: 3,
        scored_at: '2026-01-01T00:00:00+00:00',
        prompt_version: 'v0',
        is_current: false,
      },
      {
        image_key: 'img1',
        perspective_slug: 'alpha',
        score: 8,
        scored_at: '2026-03-01T00:00:00+00:00',
      },
      { image_key: 'img1', perspective_slug: 'beta', score: 1 },
    );

    const res = await app.request('/api/scores/img1/history?perspective_slug=alpha');
    expect(res.status).toBe(200);
    const body = await json<{
      perspective_slug: string;
      history: { score: number; is_current: boolean }[];
    }>(res);

    expect(body.perspective_slug).toBe('alpha');
    expect(body.history.map((r) => r.score)).toEqual([8, 3]);
    expect(body.history.map((r) => r.is_current)).toEqual([true, false]);
  });

  it('requires perspective_slug', async () => {
    const res = await app.request('/api/scores/img1/history');
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'perspective_slug is required' });
  });

  it('rejects a malformed perspective_slug', async () => {
    const res = await app.request('/api/scores/img1/history?perspective_slug=Not-A-Slug');
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'invalid perspective_slug' });
  });

  it('rejects a non-catalog image_type before touching the slug', async () => {
    const res = await app.request(
      '/api/scores/img1/history?image_type=instagram&perspective_slug=alpha',
    );
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'image_type must be catalog' });
  });

  it('does not let the image key swallow the /history segment', async () => {
    // Guards the routing hazard noted in api/scores.ts: a greedy path parameter
    // would match "img1/history" as the key and never reach this route.
    fx.addScores({ image_key: 'img1', perspective_slug: 'alpha', score: 5 });
    const body = await json<{ history: unknown[] }>(
      await app.request('/api/scores/img1/history?perspective_slug=alpha'),
    );
    expect(body.history).toHaveLength(1);
  });
});
