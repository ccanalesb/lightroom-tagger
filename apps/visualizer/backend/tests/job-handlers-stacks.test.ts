/**
 * The `batch_stack_detect` and `batch_catalog_similarity` handlers, driven through
 * the processor.
 *
 * Nothing is stubbed here. Both jobs are pure SQLite, so the real `vec0` KNN runs
 * against real vectors — which is the point, since the parts most likely to break
 * in the port are the similarity ranking and the burst arithmetic.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { LibraryFixture } from './helpers/library-fixture.js';
import { createJob, getJob, initJobsDb, updateJobField } from '../src/db/jobs/jobs.js';
import type { Db } from '../src/db/connection.js';
import { CHECKPOINT_VERSION, fingerprintBatchStackDetect } from '../src/jobs/checkpoint.js';
import { buildBurstSegments, parseDateTakenUtc } from '../src/jobs/handlers/stacks.js';
import { JobRunner } from '../src/jobs/runner.js';
import { tick } from '../src/jobs/processor.js';

let fx: LibraryFixture;
let dir: string;
let jobsDbPath: string;

interface StackResult {
  stacks_created: number;
  stacks_updated: number;
  images_stacked: number;
  images_skipped_no_date: number;
  images_skipped_already_stacked: number;
}

interface SimilarityResult {
  groups_created: number;
  candidates_created: number;
  embedded_catalog_images: number;
  skipped_non_primary: number;
  skipped_no_embedding: number;
  skipped_flagged_frame: number;
  skipped_rejected: number;
  min_similarity: number;
  limit_per_seed: number;
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
async function runJob(jobType: string, metadata: Record<string, unknown> = {}) {
  return withJobsDb(async (db) => {
    const jobId = createJob(db, jobType, metadata);
    await tick(db, new JobRunner(db));
    return getJob(db, jobId)!;
  });
}

const logMessages = (job: { logs: { message: string }[] }): string[] =>
  job.logs.map((l) => l.message);

const countOf = (table: string): number =>
  Number(fx.query<{ c: number }>(`SELECT COUNT(*) AS c FROM ${table}`)[0]!.c);

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'lt-stacks-job-'));
  jobsDbPath = join(dir, 'visualizer.db');
  fx = new LibraryFixture().activate();
  process.env.DATABASE_PATH = jobsDbPath;
  writeFileSync(join(dir, 'config.yaml'), 'stack_burst_delta_ms: 2000\n');
  process.env.LT_CONFIG_YAML = join(dir, 'config.yaml');
});

afterEach(() => {
  delete process.env.DATABASE_PATH;
  delete process.env.LT_CONFIG_YAML;
  fx.cleanup();
  rmSync(dir, { recursive: true, force: true });
});

describe('parseDateTakenUtc', () => {
  /**
   * The naive case is the one that matters: `new Date('2024-01-15T10:00:00')`
   * reads local time, so on any machine away from Greenwich it would place the
   * same photo hours from where Python does.
   */
  it('reads a naive timestamp as UTC, like fromisoformat plus a UTC stamp', () => {
    expect(parseDateTakenUtc('2024-01-15T10:00:00')).toBe(Date.UTC(2024, 0, 15, 10, 0, 0));
    expect(parseDateTakenUtc('2024-01-15 10:00:00')).toBe(Date.UTC(2024, 0, 15, 10, 0, 0));
    expect(parseDateTakenUtc('2024-01-15')).toBe(Date.UTC(2024, 0, 15));
  });

  it('honours an explicit offset and the Z shorthand', () => {
    expect(parseDateTakenUtc('2024-01-15T10:00:00Z')).toBe(Date.UTC(2024, 0, 15, 10, 0, 0));
    expect(parseDateTakenUtc('2024-01-15T10:00:00+02:00')).toBe(Date.UTC(2024, 0, 15, 8, 0, 0));
    expect(parseDateTakenUtc('2024-01-15T10:00:00-0530')).toBe(Date.UTC(2024, 0, 15, 15, 30, 0));
  });

  /** Sub-millisecond, because the gap is compared against `delta_ms` as a float. */
  it('keeps fractional seconds below the millisecond', () => {
    expect(parseDateTakenUtc('2024-01-15T10:00:00.000500')).toBe(
      Date.UTC(2024, 0, 15, 10, 0, 0) + 0.5,
    );
  });

  it('returns null for anything it cannot read', () => {
    expect(parseDateTakenUtc(null)).toBeNull();
    expect(parseDateTakenUtc('')).toBeNull();
    expect(parseDateTakenUtc('   ')).toBeNull();
    expect(parseDateTakenUtc('not a date')).toBeNull();
    expect(parseDateTakenUtc('15/01/2024')).toBeNull();
  });
});

describe('buildBurstSegments', () => {
  it('returns the newest segment first, each ordered oldest to newest', () => {
    const { segments, skippedNoDate } = buildBurstSegments(
      [
        { key: 'old-1', date_taken: '2024-01-01T10:00:00+00:00' },
        { key: 'old-2', date_taken: '2024-01-01T10:00:00.500000+00:00' },
        { key: 'new-1', date_taken: '2024-01-02T10:00:00+00:00' },
        { key: 'new-2', date_taken: '2024-01-02T10:00:00.500000+00:00' },
      ],
      2000,
    );

    expect(skippedNoDate).toBe(0);
    expect(segments).toEqual([
      ['new-1', 'new-2'],
      ['old-1', 'old-2'],
    ]);
  });

  /** Exactly `delta_ms` apart still belongs to the burst; the split is on `>`. */
  it('splits only once the gap exceeds delta_ms', () => {
    const rows = [
      { key: 'a', date_taken: '2024-01-01T10:00:00' },
      { key: 'b', date_taken: '2024-01-01T10:00:02' },
      { key: 'c', date_taken: '2024-01-01T10:00:04.001' },
    ];
    expect(buildBurstSegments(rows, 2000).segments).toEqual([['c'], ['a', 'b']]);
  });

  it('counts the undated rows instead of guessing where they belong', () => {
    const { segments, skippedNoDate } = buildBurstSegments(
      [
        { key: 'a', date_taken: '2024-01-01T10:00:00' },
        { key: 'b', date_taken: null },
        { key: 'c', date_taken: 'nonsense' },
      ],
      2000,
    );
    expect(segments).toEqual([['a']]);
    expect(skippedNoDate).toBe(2);
  });
});

describe('the batch_stack_detect handler', () => {
  it('completes with zeroes when the catalog is empty', async () => {
    const job = await runJob('batch_stack_detect');

    expect(job.status).toBe('completed');
    expect(job.result).toEqual({
      stacks_created: 0,
      stacks_updated: 0,
      images_stacked: 0,
      images_skipped_no_date: 0,
      images_skipped_already_stacked: 0,
    });
  });

  it('groups one burst into one stack, led by the best-rated frame', async () => {
    fx.addImage({ key: 'a', date_taken: '2024-01-15T10:00:00+00:00', rating: 1 });
    fx.addImage({ key: 'b', date_taken: '2024-01-15T10:00:00.500000+00:00', rating: 5 });
    fx.addImage({ key: 'c', date_taken: '2024-01-15T10:00:01+00:00', rating: 2 });

    const job = await runJob('batch_stack_detect', { delta_ms: 2000 });

    expect(job.status).toBe('completed');
    const result = job.result as unknown as StackResult;
    expect(result.stacks_created).toBe(1);
    expect(result.images_stacked).toBe(3);

    const [stack] = fx.query<{ representative_key: string; stack_size: number }>(
      'SELECT representative_key, stack_size FROM image_stacks',
    );
    expect(stack).toEqual({ representative_key: 'b', stack_size: 3 });
    expect(countOf('image_stack_members')).toBe(3);
  });

  /** A lone image is not a stack, but it still has to be counted as examined. */
  it('leaves an isolated image unstacked', async () => {
    fx.addImage({ key: 'a', date_taken: '2024-01-15T10:00:00' });
    fx.addImage({ key: 'b', date_taken: '2024-01-15T12:00:00' });

    const job = await runJob('batch_stack_detect', { delta_ms: 2000 });

    expect((job.result as unknown as StackResult).stacks_created).toBe(0);
    expect(countOf('image_stacks')).toBe(0);
  });

  it('reports the undated images it could not place', async () => {
    fx.addImage({ key: 'a', date_taken: '2024-01-15T10:00:00' });
    fx.addImage({ key: 'b', date_taken: '2024-01-15T10:00:00.500000' });
    fx.addImage({ key: 'undated', date_taken: null });

    const job = await runJob('batch_stack_detect', { delta_ms: 2000 });

    const result = job.result as unknown as StackResult;
    expect(result.images_skipped_no_date).toBe(1);
    expect(result.stacks_created).toBe(1);
    expect(
      logMessages(job).some((m) => m.includes('images_skipped_no_date=1')),
    ).toBe(true);
  });

  /**
   * Incremental mode measures gaps against the unstacked images alone, so a photo
   * already in a stack is neither re-examined nor allowed to extend a new burst.
   */
  it('skips images that are already stacked', async () => {
    fx.addImage({ key: 'a', date_taken: '2024-01-15T10:00:00' });
    fx.addImage({ key: 'b', date_taken: '2024-01-15T10:00:00.500000' });
    fx.addImage({ key: 'c', date_taken: '2024-01-16T10:00:00' });
    fx.addImage({ key: 'd', date_taken: '2024-01-16T10:00:00.500000' });
    fx.addStack(['a', 'b'], 'a');

    const job = await runJob('batch_stack_detect', { delta_ms: 2000 });

    const result = job.result as unknown as StackResult;
    expect(result.images_skipped_already_stacked).toBe(2);
    expect(result.stacks_created).toBe(1);
    expect(result.images_stacked).toBe(2);
    expect(countOf('image_stacks')).toBe(2);
  });

  it('rebuilds every stack from scratch when force is set', async () => {
    fx.addImage({ key: 'a', date_taken: '2024-01-15T10:00:00', rating: 1 });
    fx.addImage({ key: 'b', date_taken: '2024-01-15T10:00:00.500000', rating: 5 });
    fx.addStack(['a', 'b'], 'a');

    const job = await runJob('batch_stack_detect', { delta_ms: 2000, force: true });

    const result = job.result as unknown as StackResult;
    expect(result.stacks_created).toBe(1);
    // The old stack is gone rather than added to, and the rebuilt one re-picks a
    // representative rather than inheriting the previous choice.
    expect(result.images_skipped_already_stacked).toBe(0);
    expect(countOf('image_stacks')).toBe(1);
    expect(
      fx.query<{ representative_key: string }>('SELECT representative_key FROM image_stacks')[0],
    ).toEqual({ representative_key: 'b' });
  });

  /** `preserve_edited` clears the same way today; `user_modified` is always 0. */
  it('treats preserve_edited as a full rebuild for now', async () => {
    fx.addImage({ key: 'a', date_taken: '2024-01-15T10:00:00' });
    fx.addImage({ key: 'b', date_taken: '2024-01-15T10:00:00.500000' });
    fx.addStack(['a', 'b'], 'a');

    const job = await runJob('batch_stack_detect', { delta_ms: 2000, force: 'preserve_edited' });

    expect((job.result as unknown as StackResult).images_skipped_already_stacked).toBe(0);
    expect(countOf('image_stacks')).toBe(1);
  });

  it('resumes from a checkpoint and only stacks the bursts left over', async () => {
    fx.addImage({ key: 'a1', date_taken: '2024-01-15T10:00:00' });
    fx.addImage({ key: 'a2', date_taken: '2024-01-15T10:00:00.500000' });
    fx.addImage({ key: 'b1', date_taken: '2024-01-15T10:00:10' });
    fx.addImage({ key: 'b2', date_taken: '2024-01-15T10:00:10.500000' });

    const fingerprint = await fingerprintBatchStackDetect(['a1', 'a2', 'b1', 'b2'], {
      resolvedDeltaMs: 2000,
      forceMode: 'incremental',
    });

    const job = await withJobsDb(async (db) => {
      const jobId = createJob(db, 'batch_stack_detect', { delta_ms: 2000 });
      updateJobField(db, jobId, 'metadata', {
        delta_ms: 2000,
        checkpoint: {
          checkpoint_version: CHECKPOINT_VERSION,
          job_type: 'batch_stack_detect',
          fingerprint,
          processed_image_keys: ['a1', 'a2'],
          total_at_start: 4,
        },
      });
      await tick(db, new JobRunner(db));
      return getJob(db, jobId)!;
    });

    expect(job.status).toBe('completed');
    expect(countOf('image_stacks')).toBe(1);
    expect(countOf('image_stack_members')).toBe(2);
    expect(
      fx.query<{ image_key: string }>(
        'SELECT image_key FROM image_stack_members ORDER BY image_key',
      ),
    ).toEqual([{ image_key: 'b1' }, { image_key: 'b2' }]);
  });

  it('discards a checkpoint whose burst gap no longer matches, and says so', async () => {
    fx.addImage({ key: 'a1', date_taken: '2024-01-15T10:00:00' });
    fx.addImage({ key: 'a2', date_taken: '2024-01-15T10:00:00.500000' });

    const stale = await fingerprintBatchStackDetect(['a1', 'a2'], {
      resolvedDeltaMs: 5000,
      forceMode: 'incremental',
    });

    const job = await withJobsDb(async (db) => {
      const jobId = createJob(db, 'batch_stack_detect', { delta_ms: 2000 });
      updateJobField(db, jobId, 'metadata', {
        delta_ms: 2000,
        checkpoint: {
          checkpoint_version: CHECKPOINT_VERSION,
          job_type: 'batch_stack_detect',
          fingerprint: stale,
          processed_image_keys: ['a1', 'a2'],
          total_at_start: 2,
        },
      });
      await tick(db, new JobRunner(db));
      return getJob(db, jobId)!;
    });

    expect(logMessages(job)).toContain(
      'checkpoint mismatch: batch_stack_detect fingerprint changed, starting fresh',
    );
    expect(countOf('image_stacks')).toBe(1);
  });

  it('clears the checkpoint once the run finishes', async () => {
    fx.addImage({ key: 'a', date_taken: '2024-01-15T10:00:00' });
    fx.addImage({ key: 'b', date_taken: '2024-01-15T10:00:00.500000' });

    const job = await runJob('batch_stack_detect', { delta_ms: 2000 });

    expect((job.metadata as Record<string, unknown>)['checkpoint']).toBeNull();
  });

  it('refuses a delta_ms that is not a usable number', async () => {
    const job = await runJob('batch_stack_detect', { delta_ms: 'soon' });

    expect(job.status).toBe('failed');
    expect(job.error).toBe('Invalid delta_ms in metadata (must be integer >= 1)');
    expect(job.error_severity).toBe('warning');
  });

  it('refuses a negative delta_ms', async () => {
    const job = await runJob('batch_stack_detect', { delta_ms: -1 });

    expect(job.status).toBe('failed');
    expect(job.error).toBe('delta_ms override must be >= 1 when non-zero (invalid delta_ms)');
  });

  /** Zero means "not set", the same as omitting the key — not a zero-length gap. */
  it('falls back to the configured gap when delta_ms is 0', async () => {
    writeFileSync(join(dir, 'config.yaml'), 'stack_burst_delta_ms: 60000\n');
    fx.addImage({ key: 'a', date_taken: '2024-01-15T10:00:00' });
    fx.addImage({ key: 'b', date_taken: '2024-01-15T10:00:30' });

    const job = await runJob('batch_stack_detect', { delta_ms: 0 });

    expect(job.status).toBe('completed');
    // 30 s apart: a burst under the configured 60 s, two singletons under 2 s.
    expect((job.result as unknown as StackResult).stacks_created).toBe(1);
  });
});

/* -------------------------------------------------------------------------- */

/**
 * A unit vector `theta` radians off the first axis, so two vectors' cosine
 * similarity is the cosine of the angle between them — which lets a test name the
 * similarity it wants instead of hand-tuning 512 floats.
 */
function vectorAt(theta: number): Float32Array {
  const v = new Float32Array(512);
  v[0] = Math.cos(theta);
  v[1] = Math.sin(theta);
  return v;
}

/** Two vectors whose cosine similarity is `similarity`, centred on the first axis. */
function pairWithSimilarity(similarity: number): [Float32Array, Float32Array] {
  const theta = Math.acos(similarity);
  return [vectorAt(0), vectorAt(theta)];
}

describe('the batch_catalog_similarity handler', () => {
  /** `a` and `b` are 95% alike; `far` is orthogonal to both. */
  function seedThreeImages(similarity = 0.95): void {
    const [va, vb] = pairWithSimilarity(similarity);
    fx.addImage({ key: 'a', date_taken: '2024-01-02' });
    fx.addImage({ key: 'b', date_taken: '2024-01-01' });
    fx.addImage({ key: 'far', date_taken: '2023-01-01' });
    fx.addClipEmbedding('a', va);
    fx.addClipEmbedding('b', vb);
    fx.addClipEmbedding('far', vectorAt(Math.PI / 2));
  }

  it('completes with zeroes when nothing is embedded', async () => {
    const job = await runJob('batch_catalog_similarity');

    expect(job.status).toBe('completed');
    const result = job.result as unknown as SimilarityResult;
    expect(result.groups_created).toBe(0);
    expect(result.embedded_catalog_images).toBe(0);
    expect(result.min_similarity).toBe(0.9);
    expect(result.limit_per_seed).toBe(8);
  });

  it('materializes one group per near-duplicate pair', async () => {
    seedThreeImages();

    const job = await runJob('batch_catalog_similarity');

    expect(job.status).toBe('completed');
    const result = job.result as unknown as SimilarityResult;
    expect(result.groups_created).toBe(1);
    expect(result.candidates_created).toBe(1);
    expect(result.embedded_catalog_images).toBe(3);

    const [group] = fx.query<{ seed_key: string; candidate_count: number; job_id: string }>(
      'SELECT seed_key, candidate_count, job_id FROM catalog_similarity_groups',
    );
    expect(group!.seed_key).toBe('a');
    expect(group!.candidate_count).toBe(1);
    expect(group!.job_id).toBe(job.id);

    const [candidate] = fx.query<{ candidate_key: string; rank: number; why_matched: string }>(
      'SELECT candidate_key, rank, why_matched FROM catalog_similarity_candidates',
    );
    expect(candidate).toEqual({ candidate_key: 'b', rank: 1, why_matched: 'Visual match (95%)' });
  });

  /** The reverse pair is not a second group; `b` seeding `a` finds it already taken. */
  it('records a pair once, from whichever image seeds it first', async () => {
    seedThreeImages();

    await runJob('batch_catalog_similarity');

    expect(countOf('catalog_similarity_groups')).toBe(1);
  });

  it('drops pairs below min_similarity', async () => {
    seedThreeImages();

    const job = await runJob('batch_catalog_similarity', { min_similarity: 0.99 });

    const result = job.result as unknown as SimilarityResult;
    expect(result.groups_created).toBe(0);
    expect(result.min_similarity).toBe(0.99);
  });

  it('clamps min_similarity and limit_per_seed into range', async () => {
    const job = await runJob('batch_catalog_similarity', {
      min_similarity: 5,
      limit_per_seed: 900,
    });

    const result = job.result as unknown as SimilarityResult;
    expect(result.min_similarity).toBe(1);
    expect(result.limit_per_seed).toBe(50);
  });

  /** Rerunning replaces the previous answer rather than appending to it. */
  it('clears the previous run before writing', async () => {
    seedThreeImages();
    fx.addSimilarityGroup({ seed_key: 'stale', candidates: [{ key: 'gone', similarity: 0.99 }] });

    await runJob('batch_catalog_similarity');

    expect(countOf('catalog_similarity_groups')).toBe(1);
    expect(
      fx.query<{ seed_key: string }>('SELECT seed_key FROM catalog_similarity_groups'),
    ).toEqual([{ seed_key: 'a' }]);
  });

  it('skips a frame the substance detector condemned, as seed and as candidate', async () => {
    seedThreeImages();
    fx.addFrameSubstance('a', 'void');

    const job = await runJob('batch_catalog_similarity');

    const result = job.result as unknown as SimilarityResult;
    expect(result.groups_created).toBe(0);
    // Once for `a` as its own seed, once for `a` as `b`'s candidate.
    expect(result.skipped_flagged_frame).toBe(2);
  });

  it('honours a user override of a condemned frame', async () => {
    seedThreeImages();
    fx.addFrameSubstance('a', 'void');
    fx.addFrameSubstanceOverride('a');

    const job = await runJob('batch_catalog_similarity');

    const result = job.result as unknown as SimilarityResult;
    expect(result.skipped_flagged_frame).toBe(0);
    expect(result.groups_created).toBe(1);
  });

  it('does not re-suggest a pair the user already rejected', async () => {
    seedThreeImages();
    fx.addSimilarityRejection('a', 'b');

    const job = await runJob('batch_catalog_similarity');

    const result = job.result as unknown as SimilarityResult;
    expect(result.groups_created).toBe(0);
    expect(result.skipped_rejected).toBe(2);
  });

  /** A non-representative stack member is hidden in the grid, so it is not a seed. */
  it('skips stack members the grid collapses away', async () => {
    seedThreeImages();
    fx.addStack(['a', 'b'], 'a');

    const job = await runJob('batch_catalog_similarity');

    const result = job.result as unknown as SimilarityResult;
    expect(result.skipped_non_primary).toBe(1);
    expect(result.groups_created).toBe(0);
  });

  it('says what the run is scanning before it starts', async () => {
    seedThreeImages();

    const job = await runJob('batch_catalog_similarity');

    expect(logMessages(job)).toContain(
      'batch_catalog_similarity stage=find_similar_photos min_similarity=0.90, ' +
        'limit_per_seed=8, embedded_catalog_images=3',
    );
    expect(logMessages(job).some((m) => m.startsWith('Catalog similarity complete:'))).toBe(true);
  });
});
