/**
 * The `single_score` job handler and the scoring service behind it.
 *
 * Driven through `tick()` and a real `jobs` row, like the describe suite, so the
 * registry entry, the runner's lifecycle writes and the handler's own outcome
 * calls are all exercised together.
 *
 * The provider is a real HTTP server serving a queue of replies, because the
 * repair path needs a *second* call to answer differently from the first — that
 * is the whole mechanism `repaired_from_malformed` records, and mocking the
 * client would test the mock.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createServer, type Server } from 'node:http';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import sharp from 'sharp';
import { LibraryFixture } from './helpers/library-fixture.js';
import { createJob, getJob, initJobsDb } from '../src/db/jobs/jobs.js';
import type { Db } from '../src/db/connection.js';
import { JobRunner } from '../src/jobs/runner.js';
import { tick } from '../src/jobs/processor.js';
import { computePromptVersion } from '../src/vision/scoring-service.js';

let fx: LibraryFixture;
let dir: string;
let jobsDbPath: string;
let server: Server;
let port: number;

/** Replies are consumed in order; the last one repeats once the queue drains. */
let replies: { status: number; body: unknown }[] = [];
let requestBodies: string[] = [];

const completion = (content: string) => ({
  status: 200,
  body: { choices: [{ message: { content } }] },
});

const scoreJson = (
  slug: string,
  score: number,
  extra: Record<string, unknown> = {},
): string => JSON.stringify({ perspective_slug: slug, score, rationale: 'because', ...extra });

function startServer(): Promise<void> {
  return new Promise((resolve) => {
    server = createServer((req, res) => {
      let raw = '';
      req.on('data', (c) => (raw += c));
      req.on('end', () => {
        requestBodies.push(raw);
        const reply = replies.length > 1 ? replies.shift()! : (replies[0] ?? completion('{}'));
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

function writeProviders(): void {
  writeFileSync(
    join(dir, 'providers.json'),
    JSON.stringify({
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
      },
    }),
  );
}

async function writePhoto(name = 'photo.jpg'): Promise<string> {
  const path = join(dir, name);
  await sharp({
    create: { width: 8, height: 8, channels: 3, background: { r: 10, g: 20, b: 30 } },
  })
    .jpeg()
    .toFile(path);
  return path;
}

async function withJobsDb<T>(fn: (db: Db) => Promise<T>): Promise<T> {
  const db = initJobsDb(jobsDbPath);
  try {
    return await fn(db);
  } finally {
    db.close();
  }
}

async function runJob(metadata: Record<string, unknown>) {
  return withJobsDb(async (db) => {
    const jobId = createJob(db, 'single_score', metadata);
    await tick(db, new JobRunner(db));
    return getJob(db, jobId)!;
  });
}

const logMessages = (job: { logs: { message: string }[] }): string[] =>
  job.logs.map((l) => l.message);

interface StoredScore {
  perspective_slug: string;
  score: number;
  rationale: string | null;
  model_used: string | null;
  prompt_version: string;
  scored_at: string;
  is_current: number;
  repaired_from_malformed: number;
  not_attempted: number;
}

const storedScores = (key: string): StoredScore[] =>
  fx.query<StoredScore>(
    'SELECT * FROM image_scores WHERE image_key = ? ORDER BY id ASC',
    key,
  );

const emptySkipCounts = {
  no_row: 0,
  empty_path: 0,
  unresolved_or_missing: 0,
  encode_failed: 0,
};

beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'lt-score-job-'));
  jobsDbPath = join(dir, 'visualizer.db');
  fx = new LibraryFixture().activate();
  replies = [completion(scoreJson('street', 7))];
  requestBodies = [];
  process.env.DATABASE_PATH = jobsDbPath;
  await startServer();
  writeProviders();
  writeFileSync(join(dir, 'config.yaml'), `vision_cache_dir: ${join(dir, 'vision')}\n`);
  process.env.LT_PROVIDERS_JSON = join(dir, 'providers.json');
  process.env.LT_CONFIG_YAML = join(dir, 'config.yaml');
});

afterEach(async () => {
  delete process.env.DATABASE_PATH;
  delete process.env.LT_PROVIDERS_JSON;
  delete process.env.LT_CONFIG_YAML;
  fx.cleanup();
  rmSync(dir, { recursive: true, force: true });
  await new Promise((resolve) => server.close(resolve));
});

describe('computePromptVersion', () => {
  /**
   * The rubric id is what decides whether a score is stale, so it is pinned to
   * the digest Python computes rather than to whatever this implementation
   * produces — a drift here would silently rescore the whole catalog, or
   * silently refuse to.
   */
  it('is the slug and the first 16 hex of the markdown sha256', () => {
    const markdown = '# Street\nIs the moment decisive?';
    const expected = createHash('sha256').update(markdown, 'utf8').digest('hex').slice(0, 16);
    expect(computePromptVersion({ slug: 'street', prompt_markdown: markdown })).toBe(
      `street:${expected}`,
    );
  });

  it('treats absent markdown as empty rather than throwing', () => {
    expect(computePromptVersion({ slug: 'street', prompt_markdown: '' })).toBe(
      'street:' + createHash('sha256').update('', 'utf8').digest('hex').slice(0, 16),
    );
  });
});

describe('the single_score handler', () => {
  it('scores the image and completes the job', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' });

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('completed');
    expect(job.progress).toBe(100);
    expect(job.result).toEqual({
      image_key: 'a',
      image_type: 'catalog',
      scored: 1,
      skipped: 0,
      failed: 0,
      skip_reason_counts: emptySkipCounts,
    });

    const rows = storedScores('a');
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      perspective_slug: 'street',
      score: 7,
      rationale: 'because',
      model_used: 'local:vision-1',
      is_current: 1,
      repaired_from_malformed: 0,
      not_attempted: 0,
    });
  });

  /**
   * `scored_at` is written to whole seconds, not milliseconds. The column is
   * sorted and compared as text against rows Python already wrote, so a stray
   * `.123` would order a new score before an older one written in the same second.
   */
  it('writes scored_at in the second-precision UTC shape Python uses', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' });

    await runJob({ image_key: 'a' });

    expect(storedScores('a')[0]!.scored_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$/);
  });

  it('sends the perspective rubric as the user prompt', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({
      slug: 'street',
      display_name: 'Street',
      prompt_markdown: '# Street\nIs the moment decisive?',
    });

    await runJob({ image_key: 'a' });

    expect(requestBodies[0]).toContain('Is the moment decisive?');
    expect(requestBodies[0]).toContain('perspective_slug');
  });

  it('scores every active perspective when none are named', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives(
      { slug: 'street' },
      { slug: 'light' },
      { slug: 'retired', active: false },
    );
    replies = [completion(scoreJson('street', 7))];

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('completed');
    expect(job.result).toMatchObject({ scored: 2, skipped: 0 });
    // Ordered by slug, because that is the order `listPerspectives` returns.
    expect(storedScores('a').map((r) => r.perspective_slug)).toEqual(['light', 'street']);
  });

  it('fails without touching the catalog when image_key is missing', async () => {
    const job = await runJob({});

    expect(job.status).toBe('failed');
    expect(job.error).toBe('image_key is required in metadata');
  });

  it('refuses a non-catalog image_type', async () => {
    const job = await runJob({ image_key: 'a', image_type: 'dump' });

    expect(job.status).toBe('failed');
    expect(job.error).toBe('image_type must be catalog');
  });

  /**
   * Not a silent success: "scored 0 perspectives, completed" is indistinguishable
   * in the UI from a scored image, so an empty rubric set has to be an error.
   */
  it('fails when there is nothing to score against', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('failed');
    expect(job.error).toContain('No perspectives to score');
  });

  it('fails on an unknown perspective slug', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' });

    const job = await runJob({ image_key: 'a', perspective_slugs: ['nope'] });

    expect(job.status).toBe('failed');
    expect(job.error).toBe("Unknown perspective slug: 'nope'");
  });

  it('fails on an explicitly named inactive perspective', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'retired', active: false });

    const job = await runJob({ image_key: 'a', perspective_slugs: ['retired'] });

    expect(job.status).toBe('failed');
    expect(job.error).toBe("Perspective 'retired' is not active");
  });

  /** The first hard failure stops the run; a half-scored image is worse than none. */
  it('stops at the first failing perspective', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' }, { slug: 'light' });

    const job = await runJob({ image_key: 'a', perspective_slugs: ['nope', 'street'] });

    expect(job.status).toBe('failed');
    expect(storedScores('a')).toHaveLength(0);
  });

  it('skips an image whose key is not in the catalog', async () => {
    fx.addPerspectives({ slug: 'street' });

    const job = await runJob({ image_key: 'missing' });

    expect(job.status).toBe('completed');
    expect(job.result).toMatchObject({ scored: 0, skipped: 1 });
  });

  it('skips a video file without calling the provider', async () => {
    fx.addImage({ key: 'a', filepath: join(dir, 'clip.mov') }).addPerspectives({ slug: 'street' });

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('completed');
    expect(job.result).toMatchObject({ scored: 0, skipped: 1 });
    expect(requestBodies).toHaveLength(0);
  });
});

describe('re-scoring', () => {
  it('skips an image already scored under the same rubric version', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' });
    expect((await runJob({ image_key: 'a' })).status).toBe('completed');
    requestBodies = [];

    const job = await runJob({ image_key: 'a' });

    expect(job.result).toMatchObject({ scored: 0, skipped: 1 });
    expect(requestBodies).toHaveLength(0);
    expect(storedScores('a')).toHaveLength(1);
  });

  /**
   * Force replaces the row for *this* rubric version rather than stacking a
   * second current one beside it, which the `is_current` filter could not choose
   * between.
   */
  it('replaces the existing row when forced', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' });
    await runJob({ image_key: 'a' });
    replies = [completion(scoreJson('street', 3))];

    const job = await runJob({ image_key: 'a', force: true });

    expect(job.result).toMatchObject({ scored: 1, skipped: 0 });
    const rows = storedScores('a');
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ score: 3, is_current: 1 });
  });

  /**
   * Editing the rubric makes the old score stale without deleting it: the history
   * view still shows what the previous wording produced, but only the new row is
   * current.
   */
  it('supersedes a score written under an older rubric', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({
      slug: 'street',
      prompt_markdown: '# v1',
    });
    await runJob({ image_key: 'a' });

    fx.exec("UPDATE perspectives SET prompt_markdown = '# v2' WHERE slug = 'street'");
    replies = [completion(scoreJson('street', 9))];
    const job = await runJob({ image_key: 'a' });

    expect(job.result).toMatchObject({ scored: 1 });
    const rows = storedScores('a');
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ score: 7, is_current: 0 });
    expect(rows[1]).toMatchObject({ score: 9, is_current: 1 });
    expect(rows[0]!.prompt_version).not.toBe(rows[1]!.prompt_version);
  });
});

describe('frame substance', () => {
  it('skips a frame the detector called void', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath })
      .addPerspectives({ slug: 'street' })
      .addFrameSubstance('a', 'void');

    const job = await runJob({ image_key: 'a' });

    expect(job.result).toMatchObject({ scored: 0, skipped: 1 });
    expect(requestBodies).toHaveLength(0);
  });

  it('scores a void frame the user reinstated', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath })
      .addPerspectives({ slug: 'street' })
      .addFrameSubstance('a', 'void')
      .addFrameSubstanceOverride('a');

    const job = await runJob({ image_key: 'a' });

    expect(job.result).toMatchObject({ scored: 1, skipped: 0 });
  });

  it('scores a frame with any other verdict', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath })
      .addPerspectives({ slug: 'street' })
      .addFrameSubstance('a', 'illegible');

    expect((await runJob({ image_key: 'a' })).result).toMatchObject({ scored: 1 });
  });
});

describe('malformed model output', () => {
  it('repairs invalid JSON through a second call and records that it did', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' });
    replies = [completion('here you go: {{{ not json'), completion(scoreJson('street', 4))];

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('completed');
    expect(storedScores('a')[0]).toMatchObject({ score: 4, repaired_from_malformed: 1 });
    // The repair prompt goes to the same provider and model that failed.
    expect(requestBodies).toHaveLength(2);
    expect(requestBodies[1]).toContain('JSON repair tool');
  });

  it('fails the job when the repair is also invalid', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' });
    replies = [completion('{{{ not json')];

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('failed');
    expect(job.error).toContain('Score response validation failed');
    expect(storedScores('a')).toHaveLength(0);
  });

  it('rejects a score outside 1–10 rather than clamping it', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street' });
    replies = [completion(scoreJson('street', 42))];

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('failed');
    expect(storedScores('a')).toHaveLength(0);
  });

  /**
   * Only one perspective was requested and the score is always stored under it,
   * so an echoed slug that does not match is a logged discrepancy, not a reason
   * to throw away a provider call that produced a usable judgment.
   */
  it('persists under the requested slug when the model echoes a different one', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({
      slug: 'street',
      display_name: 'Street Photography (documentary)',
    });
    replies = [completion(scoreJson('Street Photography (documentary)', 6))];

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('completed');
    expect(storedScores('a')[0]).toMatchObject({ perspective_slug: 'street', score: 6 });
    expect(logMessages(job).some((m) => m.includes('Slug mismatch'))).toBe(true);
  });

  it('stores not_attempted when the model excuses an optional perspective', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath }).addPerspectives({ slug: 'street', optional: true });
    replies = [completion(scoreJson('street', 2, { not_attempted: true }))];

    await runJob({ image_key: 'a' });

    expect(storedScores('a')[0]).toMatchObject({ not_attempted: 1, score: 2 });
  });
});
