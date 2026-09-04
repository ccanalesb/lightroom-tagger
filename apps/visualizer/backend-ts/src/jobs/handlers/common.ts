/**
 * Cross-family helpers shared by job handlers. Port of `jobs/handlers/common.py`
 * and the `managed_library_db` lifecycle in `jobs/handlers/db_lifecycle.py`.
 */
import { openLibraryDb, type Db } from '../../db/connection.js';
import type { JobLogLevel } from '../../db/jobs/jobs.js';
import { AuthenticationError, InvalidRequestError } from '../../providers/errors.js';
import type { AnalyzeStage } from '../checkpoint.js';
import { requireLibraryDb } from '../library-db.js';
import type { ErrorSeverity, JobRunner } from '../runner.js';

/**
 * The library DB path, or `null` after failing the job with the reason.
 *
 * Centralized so every catalog-dependent handler reports the same accurate
 * message — the resolution failure is presentable text, not a stack trace.
 */
export function resolveLibraryDbOrFail(runner: JobRunner, jobId: string): string | null {
  try {
    return requireLibraryDb();
  } catch (e) {
    runner.failJob(jobId, e instanceof Error ? e.message : String(e), 'warning');
    return null;
  }
}

/**
 * Open the catalog for the duration of `fn` and always close it.
 *
 * Writable: handlers exist to mutate the catalog, unlike the routes, which open
 * read-only unless they declare otherwise.
 */
export async function withLibraryDb<T>(path: string, fn: (db: Db) => Promise<T>): Promise<T> {
  const db = openLibraryDb(path);
  try {
    return await fn(db);
  } finally {
    db.close();
  }
}

/**
 * How loudly the UI should report a failure.
 *
 * `warning` is for the user's own inputs — a bad key or an expired token is not a
 * defect. `critical` is for the two cases where continuing would be unsafe: the
 * filesystem refusing the process, and a write attempted against a catalog
 * Lightroom still holds open.
 */
export function failureSeverityFromError(e: unknown): ErrorSeverity {
  if (e instanceof AuthenticationError || e instanceof InvalidRequestError) return 'warning';
  // Node reports filesystem and permission failures as an Error carrying both an
  // `errno` and a `code`, which is the closest analogue to Python's `OSError`.
  if (
    typeof e === 'object' &&
    e !== null &&
    typeof (e as { errno?: unknown }).errno === 'number' &&
    typeof (e as { code?: unknown }).code === 'string'
  ) {
    return 'critical';
  }
  if (e instanceof Error && e.message === 'Close Lightroom before writing to catalog.') {
    return 'critical';
  }
  return 'error';
}

/**
 * Narrow a provider `LogCallback` level onto the four the job log stores.
 *
 * The provider layer types its level as a bare string — it is shared with the
 * routes, which log to stdout — so anything it emits outside the enum lands as
 * `info` rather than writing a level the log filters cannot select.
 */
export function jobLogLevel(level: string): JobLogLevel {
  return level === 'debug' || level === 'info' || level === 'warning' || level === 'error'
    ? level
    : 'info';
}

/** Job metadata as a plain object, whatever the column happened to hold. */
export function asMetadata(metadata: unknown): Record<string, unknown> {
  return metadata && typeof metadata === 'object' && !Array.isArray(metadata)
    ? (metadata as Record<string, unknown>)
    : {};
}

/** A metadata value read as an int, or `null` when it is not one. */
export function readIntOrNull(raw: unknown): number | null {
  if (raw === null || raw === undefined || typeof raw === 'boolean') return null;
  const n = typeof raw === 'number' ? raw : Number(String(raw).trim());
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

/**
 * Exclude videos in SQL rather than after the fact, so a worker slot is never
 * spent opening a `.mov` only to discover it is not describable.
 */
const CATALOG_NOT_VIDEO_SQL = [
  '.mov',
  '.mp4',
  '.avi',
  '.mkv',
  '.wmv',
  '.m4v',
  '.3gp',
  '.webm',
  '.mts',
  '.m2ts',
]
  .map((ext) => `LOWER(i.filepath) NOT LIKE '%${ext}'`)
  .join(' AND ');

/**
 * Keep condemned frames out of a scoring selection (#298).
 *
 * `void` only, not the `illegible` half of the flagged pair: an illegible frame
 * still has a subject to judge, while a void one is a lens cap. An override row is
 * the user saying the detector was wrong, which puts the frame back in.
 */
const VOID_SUBSTANCE_SCORING_EXCLUDE_SQL = `
    NOT EXISTS (
        SELECT 1
        FROM image_frame_substance fs
        WHERE fs.image_key = i.key
          AND fs.verdict = 'void'
          AND NOT EXISTS (
              SELECT 1
              FROM frame_substance_overrides o
              WHERE o.image_key = fs.image_key
          )
    )
`;

/**
 * Drop condemned frames from a selection that already exists.
 *
 * `selectCatalogKeys`'s `excludeVoidSubstance` does the same thing in SQL, and is
 * what a standalone `batch_score` uses. `batch_analyze` cannot: its one selection
 * feeds describe first, which has no reason to skip a lens cap, and the verdicts
 * scoring filters on are written by the stage in between.
 */
export function filterVoidSubstanceFromScoringSelection(
  db: Db,
  selection: readonly (readonly [string, string])[],
): (readonly [string, string])[] {
  if (selection.length === 0) return [...selection];
  const keys = selection.map(([k]) => k);
  const rows = db
    .prepare(
      'SELECT fs.image_key AS image_key FROM image_frame_substance fs ' +
        `WHERE fs.image_key IN (${keys.map(() => '?').join(',')}) ` +
        "AND fs.verdict = 'void' " +
        'AND NOT EXISTS (SELECT 1 FROM frame_substance_overrides o WHERE o.image_key = fs.image_key)',
    )
    .all(...(keys as never[])) as { image_key: string }[];
  if (rows.length === 0) return [...selection];
  const condemned = new Set(rows.map((r) => r.image_key));
  return selection.filter(([k]) => !condemned.has(k));
}

/**
 * How a pass reports when it is one stage of a composite job rather than a job.
 *
 * Absent, the pass owns the job: the whole progress bar, unprefixed logs, and it
 * completes the job itself. Present, it owns a slice — progress maps into
 * `progressRange`, logs carry `logPrefix`, and the summary comes back for the
 * caller to combine rather than being written as the job's result.
 *
 * `catalog_cache_build` passes this bare, because its four stages keep no resume
 * state: the chain is re-runnable end to end, and a checkpoint written under the
 * composite's job id would be read back by whichever stage ran last.
 */
export interface StageBand {
  /** The slice of the job's 0–100 bar this pass reports into. */
  progressRange: readonly [number, number];
  logPrefix: string;
}

/**
 * A `StageBand` for the two passes `batch_analyze` composes, which do resume:
 * their processed-unit set lives in a sub-object of the composite's checkpoint.
 *
 * Python spells this as four independent parameters — `progress_range`,
 * `log_prefix`, `finalize`, `nested_analyze_checkpoint` — but only these two
 * combinations of them exist, so one optional argument says the same thing.
 */
export interface PassStage extends StageBand {
  /** Which sub-object of the `batch_analyze` checkpoint holds the resume state. */
  checkpointKey: AnalyzeStage;
}

/** Map a pass's own 0–100 onto the slice of the bar it was given. */
export function mapStageProgress(stage: StageBand | undefined, pct: number): number {
  if (stage === undefined) return pct;
  const [lo, hi] = stage.progressRange;
  return Math.trunc(lo + ((hi - lo) * pct) / 100);
}

/** Legacy `date_filter` tokens, still sent by older clients and checkpoints. */
const LEGACY_DATE_FILTER_MONTHS: Record<string, number> = {
  '3months': 3,
  '6months': 6,
  '12months': 12,
};

export interface DateWindow {
  months: number | null;
  year: string | null;
}

/**
 * Normalize the date-range metadata into `(months, year)`.
 *
 * `last_months` wins over `year` deliberately: ANDing both would silently
 * intersect them into a window narrower than either, which no caller means.
 */
export function resolveDateWindow(metadata: Record<string, unknown>): DateWindow {
  let months: number | null = null;
  let year: string | null = null;

  const rawLastMonths = metadata['last_months'];
  if (typeof rawLastMonths !== 'boolean') {
    const n = readIntOrNull(rawLastMonths);
    if (n !== null && n > 0) months = n;
  }

  if (months === null) {
    const rawYear = metadata['year'];
    if (typeof rawYear === 'number' && rawYear >= 1900 && rawYear <= 9999) {
      year = String(rawYear);
    } else if (typeof rawYear === 'string' && /^\d{4}$/.test(rawYear.trim())) {
      year = rawYear.trim();
    }
  }

  if (months === null && year === null) {
    const dateFilter = String(metadata['date_filter'] ?? 'all');
    months = LEGACY_DATE_FILTER_MONTHS[dateFilter] ?? null;
  }

  return { months, year };
}

export interface CatalogSelectionOptions {
  months: number | null;
  year: string | null;
  minRating: number | null;
  /** Skip images that already carry a catalog description. */
  undescribedOnly: boolean;
  /** Skip frames the detector called void, unless the user overrode it. */
  excludeVoidSubstance?: boolean;
}

/** Newest first, undated last — the order the UI lists the catalog in. */
const CATALOG_SELECTION_ORDER =
  ' ORDER BY (i.date_taken IS NULL) DESC, i.date_taken DESC, i.key DESC';

/** `(key, 'catalog')` pairs matching the window. */
export function selectCatalogKeys(
  db: Db,
  opts: CatalogSelectionOptions,
): [string, string][] {
  const params: unknown[] = [];
  const conditions = [CATALOG_NOT_VIDEO_SQL];

  let sql = opts.undescribedOnly
    ? "SELECT i.key AS key FROM images i " +
      "LEFT JOIN image_descriptions d ON i.key = d.image_key AND d.image_type = 'catalog' " +
      'WHERE d.image_key IS NULL'
    : 'SELECT i.key AS key FROM images i WHERE 1=1';

  if (opts.excludeVoidSubstance) conditions.push(VOID_SUBSTANCE_SCORING_EXCLUDE_SQL);
  if (opts.months) {
    conditions.push("i.date_taken >= date('now', ?)");
    params.push(`-${opts.months} months`);
  }
  if (opts.year !== null) {
    conditions.push("strftime('%Y', i.date_taken) = ?");
    params.push(opts.year);
  }
  if (opts.minRating !== null) {
    conditions.push('i.rating >= ?');
    params.push(opts.minRating);
  }

  sql += ` AND ${conditions.join(' AND ')}${CATALOG_SELECTION_ORDER}`;
  const rows = db.prepare(sql).all(...(params as never[])) as { key: string }[];
  return rows.map((r) => [r.key, 'catalog']);
}

/**
 * Catalog images whose description row predates the visual-tag columns.
 *
 * `dominant_colors IS NULL` is the marker: those rows were written before the
 * colour and mood fields existed, and a backfill re-describes exactly them.
 */
export function selectCatalogKeysMissingVisualTags(
  db: Db,
  opts: Omit<CatalogSelectionOptions, 'undescribedOnly'>,
): [string, string][] {
  const params: unknown[] = [];
  const conditions = [CATALOG_NOT_VIDEO_SQL];

  if (opts.months) {
    conditions.push("i.date_taken >= date('now', ?)");
    params.push(`-${opts.months} months`);
  }
  if (opts.year !== null) {
    conditions.push("strftime('%Y', i.date_taken) = ?");
    params.push(opts.year);
  }
  if (opts.minRating !== null) {
    conditions.push('i.rating >= ?');
    params.push(opts.minRating);
  }

  const sql =
    'SELECT i.key AS key FROM images i WHERE EXISTS (' +
    '  SELECT 1 FROM image_descriptions d' +
    "  WHERE d.image_key = i.key AND d.image_type = 'catalog' AND d.dominant_colors IS NULL" +
    `) AND ${conditions.join(' AND ')}${CATALOG_SELECTION_ORDER}`;
  const rows = db.prepare(sql).all(...(params as never[])) as { key: string }[];
  return rows.map((r) => [r.key, 'catalog']);
}
