/**
 * Resume checkpoints. Mirrors `tests/test_job_checkpoint.py`.
 *
 * The fingerprint digests below were produced by running Python's
 * `jobs.checkpoint.fingerprint_batch_describe` over the same inputs, and they are
 * golden values on purpose: a job checkpointed by the Flask backend has to resume
 * under this one at cutover rather than re-describing everything, and that holds
 * only while both sides hash identical bytes. `JSON.stringify` differs from
 * `json.dumps` in two ways that matter — key order and non-ASCII escaping — so the
 * last case deliberately carries accented and CJK keys.
 */
import { describe, expect, it } from 'vitest';
import {
  CHECKPOINT_VERSION,
  buildBatchDescribeCheckpointBody,
  buildBatchEmbedImageCheckpointBody,
  buildBatchStackDetectCheckpointBody,
  canonicalJson,
  fingerprintBatchDescribe,
  fingerprintBatchEmbedImage,
  fingerprintBatchStackDetect,
  loadResumeState,
} from '../src/jobs/checkpoint.js';

const MISMATCH = 'checkpoint mismatch: batch_describe fingerprint changed, starting fresh';

const loadPairs = (
  metadata: Record<string, unknown>,
  fingerprint: string,
  log: (m: string) => void = () => {},
): Set<string> =>
  loadResumeState({
    metadata,
    jobType: 'batch_describe',
    resumeKey: 'processed_pairs',
    fingerprint,
    mismatchMessage: MISMATCH,
    log,
  });

describe('canonicalJson', () => {
  it('sorts keys and escapes non-ASCII the way json.dumps does', () => {
    expect(canonicalJson({ b: 1, a: { d: 2, c: 3 } })).toBe('{"a":{"c":3,"d":2},"b":1}');
    expect(canonicalJson({ k: 'Café' })).toBe('{"k":"Caf\\u00e9"}');
    // Astral characters escape as the surrogate pair, matching Python.
    expect(canonicalJson({ k: '\u{1F600}' })).toBe('{"k":"\\ud83d\\ude00"}');
  });
});

describe('fingerprintBatchDescribe', () => {
  it('matches the digests Python produces for the same inputs', async () => {
    await expect(fingerprintBatchDescribe({}, [])).resolves.toBe(
      'a98980d082036758489667bce9bd2543b182f830b86d2c346ede5c837aabd241',
    );
    await expect(
      fingerprintBatchDescribe(
        { force: true, min_rating: '3', date_filter: '6months', max_workers: 8 },
        [
          ['2020-03-08__CC14833', 'catalog'],
          ['a', 'catalog'],
        ],
      ),
    ).resolves.toBe('774cea8be6bb652d121676c4b1a939833e553210d1925a23cdae9ef2cd7e371a');
    await expect(
      fingerprintBatchDescribe(
        {
          perspective_slugs: ['street', 'abstract'],
          provider_id: 'local',
          provider_model: 'vision-1',
          backfill_visual_tags: true,
        },
        [['k1', 'catalog']],
      ),
    ).resolves.toBe('8e6cd6e60ba2d432abfa049d1c1091c3000164b2f6e3f42be03f8628b5a7acf2');
    await expect(
      fingerprintBatchDescribe({ min_rating: 'not-a-number', perspective_slugs: [] }, [
        ['Café__ñ', 'catalog'],
        ['日本', 'catalog'],
      ]),
    ).resolves.toBe('f5e6d8bb6259ffe620b980287ff80eed0d2e60f88259004ce998c1ee333810b5');
  });

  it('changes when the work list changes', async () => {
    const a = await fingerprintBatchDescribe({}, [['k1', 'catalog']]);
    const b = await fingerprintBatchDescribe({}, [['k2', 'catalog']]);
    expect(a).not.toBe(b);
  });

  /** An empty list means "not specified", so it must not read as a distinct run. */
  it('treats an empty perspective_slugs list as absent', async () => {
    const empty = await fingerprintBatchDescribe({ perspective_slugs: [] }, []);
    const absent = await fingerprintBatchDescribe({}, []);
    expect(empty).toBe(absent);
  });
});

describe('fingerprintBatchEmbedImage', () => {
  const noWindow = { resolvedMonths: null, resolvedYear: null };

  it('matches the digests Python produces for the same inputs', async () => {
    await expect(fingerprintBatchEmbedImage({}, [], noWindow)).resolves.toBe(
      'fe6a73865c32858e8090ded4f6fee96197abf1331225b5c850b6d6dfded8d9c6',
    );
    await expect(
      fingerprintBatchEmbedImage({ force: true, min_rating: '3' }, ['b', 'a'], {
        resolvedMonths: 6,
        resolvedYear: null,
      }),
    ).resolves.toBe('ef0759fe43429139bf2640ec1bb79e063405b655052b60f7693f3ebcfeeb6ed6');
    await expect(
      fingerprintBatchEmbedImage({ min_rating: 'not-a-number' }, ['Café__ñ', '日本'], {
        resolvedMonths: null,
        resolvedYear: '2024',
      }),
    ).resolves.toBe('b805ee423c6843488bb3152dd85b9d0c8fefde7896ce41cdfed0f0708d8ae062');
  });

  /**
   * The window is fingerprinted after resolution, so the several spellings of one
   * window do not each discard the previous run's checkpoint.
   */
  it('ignores how the date window was spelled, and notices when it changes', async () => {
    const sixMonths = { resolvedMonths: 6, resolvedYear: null };
    await expect(fingerprintBatchEmbedImage({ date_filter: '6months' }, ['a'], sixMonths)).resolves.toBe(
      await fingerprintBatchEmbedImage({ last_months: 6 }, ['a'], sixMonths),
    );
    await expect(fingerprintBatchEmbedImage({}, ['a'], sixMonths)).resolves.not.toBe(
      await fingerprintBatchEmbedImage({}, ['a'], { resolvedMonths: 3, resolvedYear: null }),
    );
  });

  it('does not depend on the order the work list arrives in', async () => {
    await expect(fingerprintBatchEmbedImage({}, ['b', 'a'], noWindow)).resolves.toBe(
      await fingerprintBatchEmbedImage({}, ['a', 'b'], noWindow),
    );
  });
});

describe('fingerprintBatchStackDetect', () => {
  it('matches the digests Python produces for the same inputs', async () => {
    await expect(
      fingerprintBatchStackDetect([], { resolvedDeltaMs: 2000, forceMode: 'incremental' }),
    ).resolves.toBe('bb8c918ab959d1d0075e25ec09614709de73c034155294043e94ccc13e15e944');
    await expect(
      fingerprintBatchStackDetect(['b', 'a', 'c'], { resolvedDeltaMs: 1500, forceMode: 'full' }),
    ).resolves.toBe('984368b5ae78677b565122a56eca7a31bf358c57df7c21c8bf2b30181dbfa74a');
    await expect(
      fingerprintBatchStackDetect(['2024-01-01__café', 'z'], {
        resolvedDeltaMs: 2000,
        forceMode: 'preserve_edited',
      }),
    ).resolves.toBe('15f2b6ad444c54dfb06a96ac039e81742bf9c2b366e3424dfcb8463b74df33a1');
  });

  /**
   * Both are resolved rather than raw metadata: `delta_ms` falls back to
   * `config.yaml` and an absent `force` means incremental, so a run whose grouping
   * changed for either reason has to discard the checkpoint.
   */
  it('changes when the burst gap or the force mode does', async () => {
    const base = { resolvedDeltaMs: 2000, forceMode: 'incremental' };
    const baseline = await fingerprintBatchStackDetect(['a'], base);
    await expect(
      fingerprintBatchStackDetect(['a'], { ...base, resolvedDeltaMs: 2001 }),
    ).resolves.not.toBe(baseline);
    await expect(fingerprintBatchStackDetect(['a'], { ...base, forceMode: 'full' })).resolves.not.toBe(
      baseline,
    );
  });
});

describe('loadResumeState', () => {
  const body = (over: Record<string, unknown> = {}) => ({
    checkpoint: {
      checkpoint_version: CHECKPOINT_VERSION,
      job_type: 'batch_describe',
      fingerprint: 'fp',
      processed_pairs: ['a|catalog', 'b|catalog'],
      total_at_start: 2,
      ...over,
    },
  });

  it('returns the processed set when the fingerprint agrees', () => {
    expect(loadPairs(body(), 'fp')).toEqual(new Set(['a|catalog', 'b|catalog']));
  });

  it('discards the checkpoint and says so when the inputs changed', () => {
    const logs: string[] = [];
    expect(loadPairs(body(), 'different', (m) => logs.push(m)).size).toBe(0);
    expect(logs).toEqual([MISMATCH]);
  });

  /** Nothing to tell the user about a first run or an old-format checkpoint. */
  it('is silent when there is no usable checkpoint', () => {
    const logs: string[] = [];
    const push = (m: string) => logs.push(m);
    expect(loadPairs({}, 'fp', push).size).toBe(0);
    expect(loadPairs(body({ checkpoint_version: 99 }), 'fp', push).size).toBe(0);
    expect(loadPairs(body({ job_type: 'batch_score' }), 'fp', push).size).toBe(0);
    expect(logs).toEqual([]);
  });
});

describe('buildBatchDescribeCheckpointBody', () => {
  it('sorts the processed pairs so the stored body is stable', () => {
    expect(
      buildBatchDescribeCheckpointBody({
        fingerprint: 'fp',
        processed: new Set(['b|catalog', 'a|catalog']),
        totalAtStart: 5,
      }),
    ).toEqual({
      job_type: 'batch_describe',
      fingerprint: 'fp',
      processed_pairs: ['a|catalog', 'b|catalog'],
      total_at_start: 5,
    });
  });
});

describe('buildBatchEmbedImageCheckpointBody', () => {
  /** `processed_pairs` holding bare keys is the shape Flask already wrote. */
  it('stores bare catalog keys under the processed_pairs name', () => {
    expect(
      buildBatchEmbedImageCheckpointBody({
        fingerprint: 'fp',
        processed: new Set(['b', 'a']),
        totalAtStart: 2,
      }),
    ).toEqual({
      job_type: 'batch_embed_image',
      fingerprint: 'fp',
      processed_pairs: ['a', 'b'],
      total_at_start: 2,
    });
  });
});

describe('buildBatchStackDetectCheckpointBody', () => {
  /** A third name for the same list, again because Flask wrote it that way. */
  it('stores catalog keys under processed_image_keys', () => {
    expect(
      buildBatchStackDetectCheckpointBody({
        fingerprint: 'fp',
        processed: new Set(['b', 'a']),
        totalAtStart: 2,
      }),
    ).toEqual({
      job_type: 'batch_stack_detect',
      fingerprint: 'fp',
      processed_image_keys: ['a', 'b'],
      total_at_start: 2,
    });
  });
});
