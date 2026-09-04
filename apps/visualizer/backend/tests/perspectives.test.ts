/**
 * Perspectives route tests.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createApp } from '../src/app.js';
import { LibraryFixture } from './helpers/library-fixture.js';

let fx: LibraryFixture;
const app = createApp();

const json = async <T>(res: Response): Promise<T> => (await res.json()) as T;
const post = (path: string, body: unknown) =>
  app.request(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
const put = (path: string, body: unknown) =>
  app.request(path, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });

beforeEach(() => {
  fx = new LibraryFixture().activate();
});
afterEach(() => fx.cleanup());

describe('GET /api/perspectives/', () => {
  it('lists rows ordered by slug, without prompt_markdown', async () => {
    fx.addPerspectives({ slug: 'zebra' }, { slug: 'alpha' });

    const res = await app.request('/api/perspectives/');
    expect(res.status).toBe(200);
    const body = await json<Record<string, unknown>[]>(res);

    expect(body.map((r) => r.slug)).toEqual(['alpha', 'zebra']);
    expect(body[0]).not.toHaveProperty('prompt_markdown');
    expect(Object.keys(body[0]!).sort()).toEqual([
      'active',
      'description',
      'display_name',
      'id',
      'optional',
      'slug',
      'source_filename',
      'updated_at',
    ]);
  });

  it('filters to active rows only when asked', async () => {
    fx.addPerspectives({ slug: 'on' }, { slug: 'off', active: false });

    const all = await json<{ slug: string }[]>(await app.request('/api/perspectives/'));
    expect(all).toHaveLength(2);

    const active = await json<{ slug: string }[]>(
      await app.request('/api/perspectives/?active_only=true'),
    );
    expect(active.map((r) => r.slug)).toEqual(['on']);
  });

  it('exposes active and optional as booleans', async () => {
    fx.addPerspectives({ slug: 'alpha', active: true, optional: true });
    const body = await json<{ active: unknown; optional: unknown }[]>(
      await app.request('/api/perspectives/'),
    );
    expect(body[0]!.active).toBe(true);
    expect(body[0]!.optional).toBe(true);
  });
});

describe('trailing slash', () => {
  it('308-redirects the bare prefix, as Werkzeug strict_slashes did', async () => {
    const res = await app.request('/api/perspectives');
    expect(res.status).toBe(308);
    expect(res.headers.get('location')).toBe('/api/perspectives/');
  });

  it('preserves the query string across the redirect', async () => {
    const res = await app.request('/api/perspectives?active_only=true');
    expect(res.status).toBe(308);
    // Dropping the query would silently widen the result on the retry.
    expect(res.headers.get('location')).toBe('/api/perspectives/?active_only=true');
  });

  it('redirects non-GET methods too, so the body survives', async () => {
    // 308 (not 302) is what preserves method and body.
    const res = await app.request('/api/perspectives', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ slug: 'x', display_name: 'X', prompt_markdown: 'y' }),
    });
    expect(res.status).toBe(308);
  });
});

describe('GET /api/perspectives/{slug}', () => {
  it('includes prompt_markdown and created_at', async () => {
    fx.addPerspectives({ slug: 'alpha', prompt_markdown: '# hello' });
    const res = await app.request('/api/perspectives/alpha');
    expect(res.status).toBe(200);
    const body = await json<Record<string, unknown>>(res);
    expect(body.prompt_markdown).toBe('# hello');
    expect(body).toHaveProperty('created_at');
  });

  it('404s for an unknown slug', async () => {
    const res = await app.request('/api/perspectives/nope');
    expect(res.status).toBe(404);
    expect(await json(res)).toEqual({ error: 'resource not found' });
  });
});

describe('POST /api/perspectives/', () => {
  it('creates and returns 201 with the detail shape', async () => {
    const res = await post('/api/perspectives/', {
      slug: 'newone',
      display_name: 'New One',
      prompt_markdown: '# prompt',
      description: 'desc',
    });
    expect(res.status).toBe(201);
    const body = await json<Record<string, unknown>>(res);
    expect(body.slug).toBe('newone');
    expect(body.prompt_markdown).toBe('# prompt');
    expect(body.active).toBe(true);
    expect(body.optional).toBe(false);
  });

  it('derives optional from the markdown marker, never from the body', async () => {
    // ADR-0012: the marker is the sole source of truth.
    const res = await post('/api/perspectives/', {
      slug: 'opt',
      display_name: 'Opt',
      prompt_markdown: 'intro\n<!-- optional: true -->\nrest',
      optional: false,
    });
    expect(res.status).toBe(201);
    expect((await json<{ optional: boolean }>(res)).optional).toBe(true);
  });

  it.each([
    [{}, 'slug, display_name, and prompt_markdown are required strings'],
    [{ slug: 'a', display_name: 'A' }, 'slug, display_name, and prompt_markdown are required strings'],
    [{ slug: 'Bad Slug', display_name: 'A', prompt_markdown: 'x' }, 'invalid slug'],
    [
      { slug: 'ok', display_name: 'A', prompt_markdown: 'x', description: 5 },
      'description must be a string',
    ],
    [
      { slug: 'ok', display_name: 'A', prompt_markdown: 'x', active: 'yes' },
      'active must be a boolean',
    ],
  ])('rejects %j with the Flask error text', async (body, message) => {
    const res = await post('/api/perspectives/', body);
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: message });
  });

  it('rejects a prompt over 256KiB', async () => {
    const res = await post('/api/perspectives/', {
      slug: 'big',
      display_name: 'Big',
      prompt_markdown: 'x'.repeat(256 * 1024 + 1),
    });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'prompt too large' });
  });

  it('measures the prompt limit in bytes, not characters', async () => {
    // A 3-byte character means 100k of them exceed 256KiB despite being < 256k chars.
    const res = await post('/api/perspectives/', {
      slug: 'multibyte',
      display_name: 'M',
      prompt_markdown: '☃'.repeat(90_000),
    });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'prompt too large' });
  });

  it('rejects a duplicate slug', async () => {
    fx.addPerspectives({ slug: 'dupe' });
    const res = await post('/api/perspectives/', {
      slug: 'dupe',
      display_name: 'D',
      prompt_markdown: 'x',
    });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'slug already exists' });
  });

  it('rejects a non-object body', async () => {
    const res = await post('/api/perspectives/', [1, 2, 3]);
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'JSON body required' });
  });
});

describe('PUT /api/perspectives/{slug}', () => {
  it('updates one field and leaves the rest alone', async () => {
    fx.addPerspectives({ slug: 'alpha', display_name: 'Old', description: 'keep' });
    const res = await put('/api/perspectives/alpha', { display_name: 'New' });
    expect(res.status).toBe(200);
    const body = await json<{ display_name: string; description: string }>(res);
    expect(body.display_name).toBe('New');
    expect(body.description).toBe('keep');
  });

  it('re-derives optional when the markdown changes', async () => {
    fx.addPerspectives({ slug: 'alpha', optional: true, prompt_markdown: '<!-- optional: true -->' });
    const body = await json<{ optional: boolean }>(
      await put('/api/perspectives/alpha', { prompt_markdown: 'no marker here' }),
    );
    // A removed marker must un-set optional (ADR-0012).
    expect(body.optional).toBe(false);
  });

  it('leaves optional untouched when the markdown is not written', async () => {
    fx.addPerspectives({ slug: 'alpha', optional: true, prompt_markdown: '<!-- optional: true -->' });
    const body = await json<{ optional: boolean }>(
      await put('/api/perspectives/alpha', { display_name: 'Renamed' }),
    );
    expect(body.optional).toBe(true);
  });

  it('404s before validating the body for an unknown slug', async () => {
    const res = await put('/api/perspectives/nope', { display_name: 5 });
    expect(res.status).toBe(404);
    expect(await json(res)).toEqual({ error: 'resource not found' });
  });

  it('requires at least one field', async () => {
    fx.addPerspectives({ slug: 'alpha' });
    const res = await put('/api/perspectives/alpha', {});
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'at least one field required' });
  });

  it('accepts active=false, which is falsy but present', async () => {
    // Guards the `in body` check: a falsy value must still count as supplied.
    fx.addPerspectives({ slug: 'alpha', active: true });
    const res = await put('/api/perspectives/alpha', { active: false });
    expect(res.status).toBe(200);
    expect((await json<{ active: boolean }>(res)).active).toBe(false);
  });
});

describe('DELETE /api/perspectives/{slug}', () => {
  it('returns 204 with no body', async () => {
    fx.addPerspectives({ slug: 'alpha' });
    const res = await app.request('/api/perspectives/alpha', { method: 'DELETE' });
    expect(res.status).toBe(204);
    expect(await res.text()).toBe('');

    expect((await app.request('/api/perspectives/alpha')).status).toBe(404);
  });

  it('404s for an unknown slug', async () => {
    const res = await app.request('/api/perspectives/nope', { method: 'DELETE' });
    expect(res.status).toBe(404);
  });
});

describe('POST /api/perspectives/{slug}/reset-default', () => {
  it('404s for an unknown slug', async () => {
    const res = await app.request('/api/perspectives/nope/reset-default', { method: 'POST' });
    expect(res.status).toBe(404);
    expect(await json(res)).toEqual({ error: 'resource not found' });
  });

  it('404s when no default file exists on disk', async () => {
    fx.addPerspectives({ slug: 'noprompt' });
    const res = await app.request('/api/perspectives/noprompt/reset-default', { method: 'POST' });
    expect(res.status).toBe(404);
    expect(await json(res)).toEqual({ error: 'no default file' });
  });

  it.each([
    '../../../etc/passwd',
    'sub/dir.md',
    'nope.txt',
    '..%2Fescape.md',
  ])('refuses source_filename %s', async (sourceFilename) => {
    // source_filename comes from the database, so the filename regex plus the
    // containment check are the only things preventing an arbitrary file read.
    fx.addPerspectives({ slug: 'evil', source_filename: sourceFilename });
    const res = await app.request('/api/perspectives/evil/reset-default', { method: 'POST' });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'invalid source_filename' });
  });
});
