/**
 * Path preflight and skip-reason diagnostics for path-dependent jobs.
 *
 * Every image job depends on a file that may not be there: the catalog records a
 * path on a NAS that is routinely unmounted. Without this, such a run logs tens of
 * thousands of individual failures and the user has to read them to work out that
 * the share is down. So the classification is bucketed into four reasons, the
 * per-image detail is logged only a handful of times per bucket, and a sample is
 * checked up front to say "your share is probably not mounted" before the work
 * starts.
 */
import { statSync } from 'node:fs';
import type { Db } from '../../db/connection.js';
import { VISION_CACHE_OVERSIZED_SENTINEL, getVisionCachedImage } from '../../db/library/vision-cache.js';
import { resolveFilepath } from '../../utils/path-resolve.js';
import { getOrCreateCachedImage } from '../../vision/vision-cache.js';
import type { JobRunner } from '../runner.js';

const PREFLIGHT_SAMPLE_SIZE = 25;
const SKIP_DETAIL_LOG_LIMIT = 5;
const SUMMARY_LOG_EVERY = 250;

export const SKIP_REASON_BUCKETS = [
  'no_row',
  'empty_path',
  'unresolved_or_missing',
  'encode_failed',
] as const;

export type SkipReason = (typeof SKIP_REASON_BUCKETS)[number];

export type SkipReasonCounts = Record<SkipReason, number>;

const SKIP_REASON_MESSAGES: Record<SkipReason, string> = {
  no_row: 'catalog/dump row missing',
  empty_path: 'filepath is empty',
  unresolved_or_missing: 'resolved path missing or inaccessible',
  encode_failed: 'compression/viewable image unavailable',
};

/** Reasons the preflight sample reports on: the ones a broken mount produces. */
const PREFLIGHT_REASONS = ['no_row', 'empty_path', 'unresolved_or_missing'] as const;

type PreflightReason = (typeof PREFLIGHT_REASONS)[number];

export function emptySkipReasonCounts(): SkipReasonCounts {
  return { no_row: 0, empty_path: 0, unresolved_or_missing: 0, encode_failed: 0 };
}

/**
 * Add up the counters of several passes into one set for a composite job.
 *
 * Tolerant of a missing or malformed part because one caller has one: a
 * `batch_analyze` that resumed past its describe stage synthesizes that stage's
 * summary from the checkpoint, which never held these counts.
 */
export function mergeSkipReasonCounts(...parts: unknown[]): SkipReasonCounts {
  const merged = emptySkipReasonCounts();
  for (const part of parts) {
    if (!part || typeof part !== 'object') continue;
    for (const bucket of SKIP_REASON_BUCKETS) {
      const raw = (part as Record<string, unknown>)[bucket];
      const n = typeof raw === 'number' ? raw : Number(raw);
      if (Number.isFinite(n)) merged[bucket] += Math.trunc(n);
    }
  }
  return merged;
}

export interface PathClassification {
  /** The usable image path, or `null` when `reason` is set. */
  path: string | null;
  reason: SkipReason | null;
  detail: string | null;
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

/** The cached compressed JPEG when it is usable on disk, otherwise `null`. */
export function tryVisionCache(db: Db, imageKey: string): string | null {
  const cached = getVisionCachedImage(db, imageKey);
  if (!cached) return null;
  const comp = (cached.compressed_path ?? '').trim();
  if (!comp || comp === VISION_CACHE_OVERSIZED_SENTINEL) return null;
  if (!isFile(comp)) return null;
  return comp;
}

/**
 * Classify whether an image is reachable, cache first.
 *
 * The cache is consulted before the catalog row because the compressed JPEG is
 * enough for every consumer here, and it survives the original going away.
 */
export async function classifyPath(db: Db, imageKey: string): Promise<PathClassification> {
  const cachedNow = tryVisionCache(db, imageKey);
  if (cachedNow !== null) return { path: cachedNow, reason: null, detail: null };

  const row = db.prepare('SELECT filepath FROM images WHERE key = ?').get(imageKey) as
    | { filepath: string | null }
    | undefined;
  if (!row) return { path: null, reason: 'no_row', detail: null };

  const filepath = (row.filepath ?? '').trim();
  if (!filepath) return { path: null, reason: 'empty_path', detail: null };

  const resolved = resolveFilepath(filepath);
  if (!resolved || !isFile(resolved)) {
    return { path: null, reason: 'unresolved_or_missing', detail: resolved || filepath };
  }

  const cached = await getOrCreateCachedImage(db, imageKey, resolved);
  if (cached && isFile(cached)) return { path: cached, reason: null, detail: null };
  return { path: null, reason: 'encode_failed', detail: resolved };
}

/** `k` distinct members of `items`, via a partial Fisher-Yates shuffle. */
function sample<T>(items: readonly T[], k: number): T[] {
  const pool = [...items];
  const out: T[] = [];
  for (let i = 0; i < k && pool.length > 0; i += 1) {
    const j = Math.floor(Math.random() * pool.length);
    out.push(pool[j]!);
    pool[j] = pool[pool.length - 1]!;
    pool.pop();
  }
  return out;
}

export interface PathSkipDiagnosticsOptions {
  jobLabel: string;
  /** The verb in `<key>: skipped <action> (<reason>)`. */
  logAction?: string;
  sampleSize?: number;
}

/** Preflight sampler and grouped skip-reason counters for one job. */
export class PathSkipDiagnostics {
  readonly skipReasonCounts: SkipReasonCounts = emptySkipReasonCounts();

  private readonly runner: JobRunner;
  private readonly jobId: string;
  private readonly db: Db;
  private readonly jobLabel: string;
  private readonly logAction: string;
  private readonly sampleSize: number;
  private readonly skipDetailLogged: SkipReasonCounts = emptySkipReasonCounts();
  private summaryMarker = 0;

  constructor(runner: JobRunner, jobId: string, db: Db, opts: PathSkipDiagnosticsOptions) {
    this.runner = runner;
    this.jobId = jobId;
    this.db = db;
    this.jobLabel = opts.jobLabel;
    this.logAction = opts.logAction ?? 'skipped';
    this.sampleSize = opts.sampleSize ?? PREFLIGHT_SAMPLE_SIZE;
  }

  classify(imageKey: string): Promise<PathClassification> {
    return classifyPath(this.db, imageKey);
  }

  recordSkip(
    reason: SkipReason,
    imageKey: string,
    opts: { detail?: string | null; logPrefix?: string } = {},
  ): void {
    if (!(reason in this.skipReasonCounts)) return;
    this.skipReasonCounts[reason] += 1;
    const reasonMsg = SKIP_REASON_MESSAGES[reason] ?? reason;
    const detailSuffix = opts.detail ? ` (${opts.detail})` : '';
    const message = `${opts.logPrefix ?? ''}${imageKey}: skipped ${this.logAction} (${reasonMsg})${detailSuffix}`;
    this.maybeLogSkipDetail(reason, message);
  }

  /**
   * A periodic roll-up, so a 40,000-image run leaves a readable log.
   *
   * Always emits on the final item even if fewer than `SUMMARY_LOG_EVERY` have
   * passed, so every run ends with a total.
   */
  maybeLogSummary(
    done: number,
    total: number,
    opts: {
      embedded?: number;
      skipped?: number;
      failed?: number;
      extra?: string;
    } = {},
  ): void {
    if (done - this.summaryMarker < SUMMARY_LOG_EVERY && done !== total) return;
    this.summaryMarker = done;
    const parts = [`done=${done}/${total}`];
    if (opts.embedded !== undefined) parts.push(`embedded=${opts.embedded}`);
    if (opts.skipped !== undefined) parts.push(`skipped=${opts.skipped}`);
    if (opts.failed !== undefined) parts.push(`failed=${opts.failed}`);
    parts.push(`reasons=${formatCounts(this.skipReasonCounts)}`);
    if (opts.extra) parts.push(opts.extra);
    this.runner.log(this.jobId, 'info', `${this.jobLabel}-summary ${parts.join(' ')}`);
  }

  /** Sample keys for reachability and warn once if a share looks unmounted. */
  async runPreflight(keys: readonly string[]): Promise<void> {
    const size = Math.min(keys.length, this.sampleSize);
    if (size <= 0) return;

    const failures: Record<PreflightReason, number> = {
      no_row: 0,
      empty_path: 0,
      unresolved_or_missing: 0,
    };
    const examples: Record<PreflightReason, string[]> = {
      no_row: [],
      empty_path: [],
      unresolved_or_missing: [],
    };

    const sampleKeys = keys.length > size ? sample(keys, size) : [...keys];
    for (const key of sampleKeys) {
      const { reason, detail } = await this.classify(key);
      if (reason !== null && reason in failures) {
        const r = reason as PreflightReason;
        failures[r] += 1;
        if (examples[r].length < 3) {
          examples[r].push(`${key}${detail ? ` (${detail})` : ''}`);
        }
      }
    }

    const failed = failures.no_row + failures.empty_path + failures.unresolved_or_missing;
    if (failed <= 0) return;

    this.runner.log(
      this.jobId,
      'warning',
      `${this.jobLabel} preflight: ${failed}/${size} sampled images have missing or ` +
        `inaccessible paths (no_row=${failures.no_row}, empty_path=${failures.empty_path}, ` +
        `unresolved_or_missing=${failures.unresolved_or_missing}). ` +
        `Examples: no_row=${formatList(examples.no_row)}, ` +
        `empty_path=${formatList(examples.empty_path)}, ` +
        `unresolved_or_missing=${formatList(examples.unresolved_or_missing)}. ` +
        'This usually means your network share is not mounted. ' +
        'Continuing — unreachable images will be skipped individually.',
    );
  }

  /**
   * Log the first few details per bucket, then say once that the rest are
   * suppressed. Counting past the limit is what makes that notice fire once.
   */
  private maybeLogSkipDetail(reason: SkipReason, message: string): void {
    const count = this.skipDetailLogged[reason];
    if (count < SKIP_DETAIL_LOG_LIMIT) {
      this.runner.log(this.jobId, 'warning', message);
      this.skipDetailLogged[reason] = count + 1;
      return;
    }
    if (count === SKIP_DETAIL_LOG_LIMIT) {
      this.runner.log(
        this.jobId,
        'info',
        `additional ${reason} skip logs suppressed after ${SKIP_DETAIL_LOG_LIMIT} samples; ` +
          'see skip_reason_counts',
      );
      this.skipDetailLogged[reason] = count + 1;
    }
  }
}

/** Python renders these counters with `repr(dict)`; the logs are compared by eye. */
function formatCounts(counts: SkipReasonCounts): string {
  const body = SKIP_REASON_BUCKETS.map((k) => `'${k}': ${counts[k]}`).join(', ');
  return `{${body}}`;
}

function formatList(values: readonly string[]): string {
  return `[${values.map((v) => `'${v}'`).join(', ')}]`;
}
