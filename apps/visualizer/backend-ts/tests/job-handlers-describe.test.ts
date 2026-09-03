/**
 * The `single_describe` job handler, driven through the processor.
 *
 * There is no Python counterpart to mirror: `handle_single_describe` is reached
 * only by `tests/test_handlers_path_diagnostics.py`, which patches the describe
 * call out to assert the skip bucketing. Its outcomes are covered here for real.
 *
 * Deliberately entered via `tick()` and a real `jobs` row rather than by calling
 * the handler directly: the thing worth pinning is that a registry entry, the
 * runner's lifecycle writes and the handler's own `completeJob`/`failJob` calls
 * agree. A direct call would test the handler while leaving the wiring — the part
 * that was `handler: null` until now — unexercised.
 *
 * The provider is a real HTTP server for the same reason `description-generate`
 * uses one, and the three env overrides keep the user's providers, vision cache
 * and catalog out of reach.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import Database from 'better-sqlite3';
import { createServer, type Server } from 'node:http';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import sharp from 'sharp';
import { LibraryFixture } from './helpers/library-fixture.js';
import { createJob, getJob, initJobsDb } from '../src/db/jobs/jobs.js';
import type { Db } from '../src/db/connection.js';
import { JobRunner } from '../src/jobs/runner.js';
import { tick } from '../src/jobs/processor.js';
import { fingerprintBatchDescribe } from '../src/jobs/checkpoint.js';

let fx: LibraryFixture;
let dir: string;
let jobsDbPath: string;
let server: Server;
let port: number;

let reply: { status: number; body: unknown } = { status: 200, body: {} };

/** Fires as each provider call arrives, so a test can cancel mid-run. */
let onRequest: (() => void) | null = null;

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
        onRequest?.();
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

/** Enqueue, run one processor pass, and hand back the settled job. */
async function runJobOfType(type: string, metadata: Record<string, unknown>) {
  return withJobsDb(async (db) => {
    const jobId = createJob(db, type, metadata);
    await tick(db, new JobRunner(db));
    return getJob(db, jobId)!;
  });
}

const runJob = (metadata: Record<string, unknown>) => runJobOfType('single_describe', metadata);
const runBatch = (metadata: Record<string, unknown> = {}) =>
  runJobOfType('batch_describe', metadata);

const logMessages = (job: { logs: { message: string }[] }): string[] =>
  job.logs.map((l) => l.message);

function storedDescription(key: string): Record<string, unknown> | undefined {
  const db = new Database(fx.dbPath, { readonly: true });
  const row = db.prepare('SELECT * FROM image_descriptions WHERE image_key = ?').get(key);
  db.close();
  return row as Record<string, unknown> | undefined;
}

beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'lt-desc-job-'));
  jobsDbPath = join(dir, 'visualizer.db');
  fx = new LibraryFixture().activate();
  onRequest = null;
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

describe('the single_describe handler', () => {
  it('describes the image and completes the job', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'A street scene', subjects: ['bicycle'] }));

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('completed');
    expect(job.progress).toBe(100);
    expect(job.result).toEqual({
      image_key: 'a',
      image_type: 'catalog',
      status: 'described',
      skip_reason_counts: {
        no_row: 0,
        empty_path: 0,
        unresolved_or_missing: 0,
        encode_failed: 0,
      },
    });
    expect(storedDescription('a')?.summary).toBe('A street scene');
  });

  it('fails without touching the catalog when image_key is missing', async () => {
    const job = await runJob({});

    expect(job.status).toBe('failed');
    expect(job.error).toBe('image_key is required in metadata');
  });

  /**
   * The service reports a bare `skipped`; the reason is reconstructed afterwards.
   * Without it the user sees a failed job with no cause, which is the whole point
   * of `diagnoseDescribeSkip`.
   */
  it('reports why a key that is not in the catalog was skipped', async () => {
    const job = await runJob({ image_key: 'missing' });

    expect(job.status).toBe('failed');
    expect(job.error).toBe('Image key not found in catalog');
    // The skip is also bucketed, so a batch run can group thousands of these.
    expect(logMessages(job)).toContain('missing: skipped skipped (catalog/dump row missing)');
  });

  it('reports an already-described image rather than regenerating it', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'First pass', subjects: ['bicycle'] }));
    expect((await runJob({ image_key: 'a' })).status).toBe('completed');

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('failed');
    expect(job.error).toBe('Already described (use force to regenerate)');
    expect(storedDescription('a')?.summary).toBe('First pass');
  });

  it('regenerates when force is set', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = completion(JSON.stringify({ summary: 'First pass', subjects: ['bicycle'] }));
    expect((await runJob({ image_key: 'a' })).status).toBe('completed');

    reply = completion(JSON.stringify({ summary: 'Second pass', subjects: ['canoe'] }));
    const job = await runJob({ image_key: 'a', force: true });

    expect(job.status).toBe('completed');
    expect(storedDescription('a')?.summary).toBe('Second pass');
  });

  /**
   * An unmounted share is the common failure, and it has to be legible: the
   * preflight warns up front and the per-image skip names the path.
   */
  it('warns in preflight and names the missing file when the path is unreachable', async () => {
    fx.addImage({ key: 'a', filepath: join(dir, 'not-there.jpg') });

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('failed');
    expect(job.error).toBe(`File not found: ${join(dir, 'not-there.jpg')}`);
    const messages = logMessages(job);
    expect(
      messages.some((m) => m.includes('single_describe preflight: 1/1 sampled images')),
    ).toBe(true);
    expect(
      messages.some((m) => m.includes('a: skipped skipped (resolved path missing or inaccessible)')),
    ).toBe(true);
  });

  it('fails the job with the provider error when the model call fails', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'a', filepath });
    reply = { status: 500, body: { error: 'upstream exploded' } };

    const job = await runJob({ image_key: 'a' });

    expect(job.status).toBe('failed');
    expect(job.error_severity).toBe('error');
    expect(job.error).toBeTruthy();
  });
});

interface BatchResult {
  described: number;
  skipped: number;
  failed: number;
  total: number;
  skip_reason_counts: Record<string, number>;
}

/** Seed `keys` as catalog images all pointing at one real JPEG. */
async function seedPhotos(...keys: string[]): Promise<void> {
  const filepath = await writePhoto();
  for (const key of keys) fx.addImage({ key, filepath });
}

const describedKeys = (): string[] =>
  fx
    .query<{ image_key: string }>('SELECT image_key FROM image_descriptions ORDER BY image_key')
    .map((r) => r.image_key);

describe('the batch_describe handler', () => {
  it('describes every undescribed catalog image and reports the counts', async () => {
    await seedPhotos('a', 'b');
    reply = completion(JSON.stringify({ summary: 'A street scene', subjects: ['bicycle'] }));

    const job = await runBatch();

    expect(job.status).toBe('completed');
    const result = job.result as unknown as BatchResult;
    expect(result.described).toBe(2);
    expect(result.failed).toBe(0);
    expect(result.total).toBe(2);
    expect(describedKeys()).toEqual(['a', 'b']);
  });

  /**
   * The pre-filter is one SQL query standing in for a provider round-trip per
   * image. On a catalog that is already described it is the difference between a
   * no-op and forty thousand paid calls.
   */
  it('excludes already-described images in SQL rather than one at a time', async () => {
    await seedPhotos('a', 'b');
    reply = completion(JSON.stringify({ summary: 'First pass', subjects: ['bicycle'] }));
    expect((await runJob({ image_key: 'a' })).status).toBe('completed');

    const job = await runBatch();

    expect((job.result as unknown as BatchResult).described).toBe(1);
    expect(fx.query('SELECT summary FROM image_descriptions WHERE image_key = ?', 'a')).toEqual([
      { summary: 'First pass' },
    ]);
  });

  it('re-describes everything when force is set', async () => {
    await seedPhotos('a');
    reply = completion(JSON.stringify({ summary: 'First pass', subjects: ['bicycle'] }));
    expect((await runJob({ image_key: 'a' })).status).toBe('completed');

    reply = completion(JSON.stringify({ summary: 'Second pass', subjects: ['canoe'] }));
    const job = await runBatch({ force: true });

    expect((job.result as unknown as BatchResult).described).toBe(1);
    expect(storedDescription('a')?.summary).toBe('Second pass');
  });

  it('honours the rating window when selecting work', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'low', filepath, rating: 1 });
    fx.addImage({ key: 'high', filepath, rating: 4 });
    reply = completion(JSON.stringify({ summary: 'A street scene', subjects: ['bicycle'] }));

    const job = await runBatch({ min_rating: 3 });

    expect((job.result as unknown as BatchResult).total).toBe(1);
    expect(describedKeys()).toEqual(['high']);
  });

  /** Videos are excluded in SQL so a worker slot is never spent opening one. */
  it('never selects video files', async () => {
    const filepath = await writePhoto();
    fx.addImage({ key: 'photo', filepath });
    fx.addImage({ key: 'clip', filepath: join(dir, 'clip.mov') });
    reply = completion(JSON.stringify({ summary: 'A street scene', subjects: ['bicycle'] }));

    const job = await runBatch();

    expect((job.result as unknown as BatchResult).total).toBe(1);
    expect(describedKeys()).toEqual(['photo']);
  });

  it('completes immediately when there is nothing to describe', async () => {
    const job = await runBatch();

    expect(job.status).toBe('completed');
    expect(job.result).toEqual({
      described: 0,
      skipped: 0,
      failed: 0,
      total: 0,
      skip_reason_counts: {
        no_row: 0,
        empty_path: 0,
        unresolved_or_missing: 0,
        encode_failed: 0,
      },
    });
  });

  it('refuses an image_type other than catalog', async () => {
    const job = await runBatch({ image_type: 'instagram' });

    expect(job.status).toBe('failed');
    expect(job.error).toBe('image_type must be catalog');
  });

  it('clears the checkpoint once the run completes', async () => {
    await seedPhotos('a');
    reply = completion(JSON.stringify({ summary: 'A street scene', subjects: ['bicycle'] }));

    const job = await runBatch();

    expect(job.metadata.checkpoint).toBeNull();
  });

  /**
   * The whole point of the checkpoint: a resumed run must not pay for work a
   * previous run already paid for.
   */
  it('resumes from a checkpoint and skips the pairs already processed', async () => {
    await seedPhotos('a', 'b');
    reply = completion(JSON.stringify({ summary: 'A street scene', subjects: ['bicycle'] }));

    // Selection order is key DESC when no image carries a date.
    const metadata = { force: true };
    const fingerprint = await fingerprintBatchDescribe(metadata, [
      ['b', 'catalog'],
      ['a', 'catalog'],
    ]);
    const job = await runBatch({
      ...metadata,
      checkpoint: {
        checkpoint_version: 1,
        job_type: 'batch_describe',
        fingerprint,
        processed_pairs: ['b|catalog'],
        total_at_start: 2,
      },
    });

    expect((job.result as unknown as BatchResult).described).toBe(1);
    expect(describedKeys()).toEqual(['a']);
  });

  it('discards a checkpoint built from different inputs, and says so', async () => {
    await seedPhotos('a', 'b');
    reply = completion(JSON.stringify({ summary: 'A street scene', subjects: ['bicycle'] }));

    const job = await runBatch({
      force: true,
      checkpoint: {
        checkpoint_version: 1,
        job_type: 'batch_describe',
        fingerprint: 'stale',
        processed_pairs: ['b|catalog'],
        total_at_start: 2,
      },
    });

    expect((job.result as unknown as BatchResult).described).toBe(2);
    expect(logMessages(job)).toContain(
      'checkpoint mismatch: batch_describe fingerprint changed, starting fresh',
    );
  });

  /**
   * Cancel is cooperative: the work already in flight finishes, the rest is
   * abandoned, and the checkpoint keeps what was paid for.
   */
  it('stops at the next image when a cancel arrives mid-run', async () => {
    await seedPhotos('a', 'b', 'c');
    reply = completion(JSON.stringify({ summary: 'A street scene', subjects: ['bicycle'] }));

    await withJobsDb(async (db) => {
      const jobId = createJob(db, 'batch_describe', { max_workers: 1 });
      const runner = new JobRunner(db);
      onRequest = () => runner.signalCancel(jobId);

      await tick(db, runner);

      const job = getJob(db, jobId)!;
      expect(job.status).toBe('cancelled');
      expect(logMessages(job)).toContain(
        'Batch describe cancel noted; finishing already-running tasks',
      );
      // Selection is key DESC, so the one image that ran was the last key.
      expect(describedKeys()).toEqual(['c']);
    });
  });

  /**
   * A dead provider must not burn through the whole catalog before anyone
   * notices, so the run aborts once ten describes fail back to back.
   */
  it('aborts after ten consecutive failures with nothing described', async () => {
    await seedPhotos(...Array.from({ length: 15 }, (_, i) => `k${String(i).padStart(2, '0')}`));
    reply = { status: 500, body: { error: 'upstream exploded' } };

    const job = await runBatch({ max_workers: 1 });

    expect(job.status).toBe('failed');
    expect(job.error).toBe(
      'Aborted after 10 consecutive failures with 0 successful descriptions — ' +
        'check file paths and provider connectivity',
    );
    expect(describedKeys()).toEqual([]);
  });
});
