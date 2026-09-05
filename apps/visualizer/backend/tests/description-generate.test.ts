/**
 * `POST /api/descriptions/{image_key}/generate` and the description service.
 *
 * These run against a real HTTP server rather than a mocked provider client, so
 * the OpenAI-compatible request path, the HTTP-status→`ProviderError` mapping and
 * the route's status mapping are all exercised together. That is the part most
 * likely to drift, and a mock of `generateDescription` would test none of it.
 *
 * Three env overrides keep the user's data out of reach, and all three matter:
 *   - `LT_PROVIDERS_JSON` — otherwise the real provider list is read (and a
 *     describe would hit a real paid API).
 *   - `LT_CONFIG_YAML` — `vision_cache_dir` comes from config, so without this
 *     every test would write JPEGs into the user's real vision cache.
 *   - `LIBRARY_DB` — via `LibraryFixture`.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import Database from 'better-sqlite3';
import { createServer, type Server } from 'node:http';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import sharp from 'sharp';
import { createApp } from '../src/app.js';
import { LibraryFixture } from './helpers/library-fixture.js';
import { storeStructured } from '../src/vision/description-service.js';

const app = createApp();

let fx: LibraryFixture;
let dir: string;
let server: Server;
let port: number;

/** What the fake provider answers next: a body, or a status to fail with. */
let reply: { status: number; body: unknown } = { status: 200, body: {} };
let requests: { path: string; body: Record<string, unknown> }[] = [];

/** An OpenAI-compatible `/chat/completions` reply carrying `content`. */
const completion = (content: string) => ({
  status: 200,
  body: { choices: [{ message: { content } }] },
});

function startServer(): Promise<void> {
  return new Promise((resolve) => {
    server = createServer((req, res) => {
      let raw = '';
      req.on('data', (c) => (raw += c));
      req.on('end', () => {
        requests.push({
          path: req.url ?? '',
          body: raw ? (JSON.parse(raw) as Record<string, unknown>) : {},
        });
        res.writeHead(reply.status, { 'content-type': 'application/json' });
        res.end(JSON.stringify(reply.body));
      });
    });
    server.listen(0, '127.0.0.1', () => {
      port = (server.address() as { port: number }).port;
      resolve();
    });
  });
}

/**
 * A providers.json with one provider pointing at the test server.
 *
 * `auto_discover: false` and an explicit model list keep the registry off the
 * network for discovery; only the describe call itself talks to the server.
 * Deliberately NOT named `ollama`, because `isOllamaClient` would then route to
 * the native `/api/chat` endpoint instead of `/chat/completions`.
 */
function writeProviders(extra: Record<string, unknown> = {}): void {
  writeFileSync(
    join(dir, 'providers.json'),
    JSON.stringify({
      // One try, no backoff: the retry ladder is tested in providers.test.ts, and
      // here a retryable status would otherwise add seconds of real sleeping.
      retry_defaults: { max_retries: 1, backoff_seconds: [0] },
      fallback_order: ['local'],
      defaults: { description: { provider: 'local', model: 'vision-1' } },
      providers: {
        local: {
          name: 'Local',
          base_url: `http://127.0.0.1:${port}/v1`,
          api_key: 'test-key',
          tool_calling: false,
          auto_discover: false,
          models: [{ id: 'vision-1', name: 'Vision One', vision: true }],
        },
        ...extra,
      },
    }),
  );
}

/** A real 8x8 JPEG on disk — `compressImage` and the base64 encode need one. */
async function writePhoto(name = 'photo.jpg'): Promise<string> {
  const path = join(dir, name);
  await sharp({
    create: { width: 8, height: 8, channels: 3, background: { r: 10, g: 20, b: 30 } },
  })
    .jpeg()
    .toFile(path);
  return path;
}

const generate = (key: string, body: unknown = {}) =>
  app.request(`/api/descriptions/${key}/generate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });

const json = async <T>(res: Response): Promise<T> => (await res.json()) as T;

interface GenerateBody {
  generated: boolean;
  description: Record<string, unknown> | null;
}

function storedDescription(key: string): Record<string, unknown> | undefined {
  const db = new Database(fx.dbPath, { readonly: true });
  const row = db.prepare('SELECT * FROM image_descriptions WHERE image_key = ?').get(key);
  db.close();
  return row as Record<string, unknown> | undefined;
}

beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'lt-desc-'));
  fx = new LibraryFixture().activate();
  requests = [];
  await startServer();
  writeProviders();
  writeFileSync(join(dir, 'config.yaml'), `vision_cache_dir: ${join(dir, 'vision')}\n`);
  process.env.LT_PROVIDERS_JSON = join(dir, 'providers.json');
  process.env.LT_CONFIG_YAML = join(dir, 'config.yaml');
});

afterEach(async () => {
  delete process.env.LT_PROVIDERS_JSON;
  delete process.env.LT_CONFIG_YAML;
  delete process.env.VISION_MODEL;
  fx.cleanup();
  rmSync(dir, { recursive: true, force: true });
  await new Promise((resolve) => server.close(resolve));
});

describe('POST /api/descriptions/{image_key}/generate', () => {
  it('describes an image and stores the result', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(
      JSON.stringify({
        summary: 'A street scene',
        composition: { depth: 'shallow' },
        technical: { mood: 'gritty' },
        subjects: ['person', 'bicycle'],
        dominant_colors: ['#112233'],
        mood_tags: ['tense'],
        has_repetition: true,
      }),
    );

    const res = await generate('a');
    expect(res.status).toBe(200);
    const body = await json<GenerateBody>(res);
    expect(body.generated).toBe(true);
    expect(body.description?.summary).toBe('A street scene');

    const row = storedDescription('a');
    expect(row?.summary).toBe('A street scene');
    // The label is `provider:model` for what actually served the call, not what
    // was requested.
    expect(row?.model_used).toBe('local:vision-1');
    expect(row?.dominant_colors).toBe('["#112233"]');
    expect(row?.mood_tags).toBe('["tense"]');
    expect(row?.has_repetition).toBe(1);

    // The request really went to the OpenAI-compatible endpoint with the image.
    expect(requests).toHaveLength(1);
    expect(requests[0]!.path).toBe('/v1/chat/completions');
    expect(requests[0]!.body.model).toBe('vision-1');
    expect(JSON.stringify(requests[0]!.body)).toContain('data:image/jpeg;base64,');
  });

  it('writes the FTS row so the new description is searchable', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'A red bicycle', subjects: ['bicycle'] }));

    expect((await generate('a')).status).toBe(200);

    // `image_descriptions_fts` is external-content with no triggers, so nothing
    // populates it unless the writer does it by hand.
    const db = new Database(fx.dbPath, { readonly: true });
    const hit = db
      .prepare(
        'SELECT d.image_key FROM image_descriptions d ' +
          'JOIN image_descriptions_fts f ON f.rowid = d.rowid ' +
          'WHERE image_descriptions_fts MATCH ?',
      )
      .get('"bicycle"') as { image_key: string } | undefined;
    db.close();
    expect(hit?.image_key).toBe('a');
  });

  /**
   * Re-describing must retire the old terms, not just add the new ones.
   *
   * Removal has to go through FTS5's `'delete'` command carrying the previously
   * indexed text. The obvious `DELETE FROM image_descriptions_fts WHERE rowid = ?`
   * looks right and even passes an `integrity-check`, but on an external-content
   * table it re-tokenizes whatever the content table holds *now* — so it strips
   * the new terms and leaves the old ones searchable for ever.
   */
  it('retires the previous terms when a description is regenerated', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'A red bicycle', subjects: ['bicycle'] }));
    expect((await generate('a')).status).toBe(200);

    reply = completion(JSON.stringify({ summary: 'A blue canoe', subjects: ['canoe'] }));
    expect((await generate('a', { force: true })).status).toBe(200);

    const db = new Database(fx.dbPath, { readonly: true });
    const matches = (term: string) =>
      (
        db
          .prepare(
            'SELECT count(*) AS n FROM image_descriptions d ' +
              'JOIN image_descriptions_fts f ON f.rowid = d.rowid ' +
              'WHERE image_descriptions_fts MATCH ?',
          )
          .get(term) as { n: number }
      ).n;
    const stale = matches('"bicycle"');
    const fresh = matches('"canoe"');
    db.close();

    expect(stale).toBe(0);
    expect(fresh).toBe(1);
  });

  it('skips an image that already has a description and returns the existing one', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'First pass' }));
    await generate('a');
    requests = [];

    reply = completion(JSON.stringify({ summary: 'Second pass' }));
    const body = await json<GenerateBody>(await generate('a'));

    expect(body.generated).toBe(false);
    expect(body.description?.summary).toBe('First pass');
    // The provider must not be contacted at all — this is the guard that keeps a
    // re-run of a batch from re-billing every already-described image.
    expect(requests).toHaveLength(0);
  });

  it('regenerates when force is true', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'First pass' }));
    await generate('a');

    reply = completion(JSON.stringify({ summary: 'Second pass' }));
    const body = await json<GenerateBody>(await generate('a', { force: true }));

    expect(body.generated).toBe(true);
    expect(body.description?.summary).toBe('Second pass');
  });

  it('does not store an empty summary, and leaves an existing one intact', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'Good text' }));
    await generate('a');

    // A blank summary must fail the accept gate rather than overwrite: stored, it
    // would look like a real description and the image would never be retried.
    reply = completion(JSON.stringify({ summary: '   ' }));
    const body = await json<GenerateBody>(await generate('a', { force: true }));

    expect(body.generated).toBe(false);
    expect(body.description?.summary).toBe('Good text');
    expect(storedDescription('a')?.summary).toBe('Good text');
  });

  it('returns generated=false with a null description for an unknown image', async () => {
    const body = await json<GenerateBody>(await generate('missing'));
    expect(body).toEqual({ generated: false, description: null });
    expect(requests).toHaveLength(0);
  });

  it('returns generated=false when the file is gone and nothing is cached', async () => {
    fx.addImage({ key: 'a', filepath: join(dir, 'not-there.jpg') });
    const body = await json<GenerateBody>(await generate('a'));
    expect(body).toEqual({ generated: false, description: null });
    expect(requests).toHaveLength(0);
  });

  it('skips a video without calling the provider, even with force', async () => {
    const filepath = join(dir, 'clip.mov');
    writeFileSync(filepath, 'not really a movie');
    fx.addImage({ key: 'a', filepath });

    const body = await json<GenerateBody>(await generate('a', { force: true }));
    expect(body).toEqual({ generated: false, description: null });
    // The point of the short-circuit: compressImage silently passes a .mov
    // through, so without it the raw file would be sent to the model and stall
    // the worker on retry backoffs.
    expect(requests).toHaveLength(0);
  });

  it('rejects a non-catalog image_type with 400', async () => {
    fx.addImages('a');
    const res = await generate('a', { image_type: 'instagram' });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'Invalid image_type: instagram' });
  });

  it('accepts an empty image_type', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'ok' }));
    expect((await generate('a', { image_type: '' })).status).toBe(200);
  });

  /**
   * Unknown provider_id is only rejected after the model ladder bottoms out: no
   * provider_model, no defaults.description.model, and VISION_MODEL cleared so the
   * config fallback is empty too.
   */
  it('returns 400 when an explicitly requested provider is unknown', async () => {
    writeFileSync(
      join(dir, 'providers.json'),
      JSON.stringify({
        retry_defaults: { max_retries: 1, backoff_seconds: [0] },
        fallback_order: ['local'],
        providers: {
          local: {
            name: 'Local',
            base_url: `http://127.0.0.1:${port}/v1`,
            api_key: 'test-key',
            tool_calling: false,
            auto_discover: false,
            models: [{ id: 'vision-1', name: 'Vision One', vision: true }],
          },
        },
      }),
    );
    process.env.VISION_MODEL = '';

    // Needs a real file: `describeMatchedImage` skips a missing one before it ever
    // resolves a provider, so without this the route answers 200 regardless.
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    const res = await generate('a', { provider_id: 'nope' });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({
      error: 'invalid_provider',
      message: 'Unknown provider: nope',
    });
  });

  describe('provider failures map onto declared statuses', () => {
    const cases = [
      { status: 429, error: 'rate_limit', expected: 429 },
      { status: 401, error: 'auth_error', expected: 401 },
      { status: 503, error: 'provider_unavailable', expected: 503 },
    ];

    for (const c of cases) {
      it(`turns a provider ${c.status} into ${c.expected} ${c.error}`, async () => {
        const filepath = await writePhoto();
        fx.addImage({ key: 'a', filepath });
        reply = { status: c.status, body: { error: { message: 'upstream said no' } } };

        const res = await generate('a', { provider_id: 'local' });
        expect(res.status).toBe(c.expected);
        const body = await json<{ error: string; provider: string | null }>(res);
        expect(body.error).toBe(c.error);
        // `provider` falls back to the requested id when the exception carries none.
        expect(body.provider).toBe('local');
        expect(storedDescription('a')).toBeUndefined();
      });
    }
  });

  it('sends provider_model as the model when given', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'ok' }));

    await generate('a', { provider_id: 'local', provider_model: 'vision-9' });
    expect(requests[0]!.body.model).toBe('vision-9');
  });

  it('uses a bare model when no provider_id is given', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'ok' }));

    await generate('a', { model: 'vision-7' });
    expect(requests[0]!.body.model).toBe('vision-7');
    // Bare model is passed as an argument; DESCRIPTION_VISION_MODEL env is untouched.
    expect(process.env.DESCRIPTION_VISION_MODEL).toBeUndefined();
  });

  it('ignores a bare model when provider_id is given', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'ok' }));

    await generate('a', { provider_id: 'local', model: 'vision-7' });
    expect(requests[0]!.body.model).toBe('vision-1');
  });
});

describe('storeStructured', () => {
  beforeEach(() => fx.addImages('a'));

  const store = (structured: Record<string, unknown>) => {
    const db = new Database(fx.dbPath);
    storeStructured(db, 'a', 'catalog', structured, 'test:model');
    db.close();
    return storedDescription('a')!;
  };

  it('falls back to technical.dominant_colors when the root list is absent', () => {
    const row = store({ summary: 's', technical: { dominant_colors: ['#aabbcc'] } });
    expect(row.dominant_colors).toBe('["#aabbcc"]');
  });

  it('falls back to technical.dominant_colors when the root list is empty', () => {
    // An empty root list and an omitted one mean the same thing for indexing, so
    // both fall through.
    const row = store({
      summary: 's',
      dominant_colors: [],
      technical: { dominant_colors: ['#aabbcc'] },
    });
    expect(row.dominant_colors).toBe('["#aabbcc"]');
  });

  it('prefers the root dominant_colors over technical', () => {
    const row = store({
      summary: 's',
      dominant_colors: ['#111111'],
      technical: { dominant_colors: ['#aabbcc'] },
    });
    expect(row.dominant_colors).toBe('["#111111"]');
  });

  it('derives mood_tags from technical.mood when absent', () => {
    const row = store({ summary: 's', technical: { mood: '  gritty  ' } });
    expect(row.mood_tags).toBe('["gritty"]');
  });

  it('keeps an empty mood_tags list rather than falling back', () => {
    // Unlike dominant_colors, an empty mood_tags list is taken as a deliberate
    // "no tags" and does NOT fall through to technical.mood.
    const row = store({ summary: 's', mood_tags: [], technical: { mood: 'gritty' } });
    expect(row.mood_tags).toBe('[]');
  });

  it('leaves mood_tags null when neither source has anything usable', () => {
    const row = store({ summary: 's', technical: { mood: '   ' } });
    expect(row.mood_tags).toBeNull();
  });

  it('stores has_repetition as null only when it is absent', () => {
    expect(store({ summary: 's' }).has_repetition).toBeNull();
  });

  it('coerces a loose has_repetition to 0/1', () => {
    expect(store({ summary: 's', has_repetition: 'yes' }).has_repetition).toBe(1);
    expect(store({ summary: 's', has_repetition: 'maybe' }).has_repetition).toBe(0);
    expect(store({ summary: 's', has_repetition: false }).has_repetition).toBe(0);
  });

  it('ignores a non-object technical rather than throwing', () => {
    const row = store({ summary: 's', technical: 'not an object' });
    expect(row.dominant_colors).toBeNull();
    expect(row.mood_tags).toBeNull();
  });
});
