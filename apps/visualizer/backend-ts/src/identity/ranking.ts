/**
 * Best-photo ranking with stack enrichment.
 * Port of `core/identity_service/ranking.py`.
 */
import type { Db } from '../db/connection.js';
import { computeImagePeakPercentileScores, type PeakPercentileItem, type PeakPercentileMeta } from './percentiles.js';

/**
 * Maximum keys per `IN (...)` list.
 *
 * These helpers are called with *every* scored image in the catalog — the Mirror
 * passes all ~29,000 at once — and one bound parameter per key blows SQLite's
 * variable limit. Python got away with it because CPython's bundled SQLite is built
 * with a high `SQLITE_MAX_VARIABLE_NUMBER`; better-sqlite3's answers "too many SQL
 * variables". 900 is under the 999 floor that any SQLite build guarantees.
 */
const KEY_CHUNK = 900;

/** Run `query` over `keys` in batches, concatenating the rows. */
function inChunks<T>(keys: readonly string[], query: (batch: string[]) => T[]): T[] {
  const out: T[] = [];
  for (let i = 0; i < keys.length; i += KEY_CHUNK) {
    out.push(...query([...keys.slice(i, i + KEY_CHUNK)]));
  }
  return out;
}

export interface ImageMeta {
  filename: string;
  date_taken: string;
  rating: number;
  instagram_posted: boolean;
  image_type: 'catalog';
}

export interface StackFields {
  stack_id: number | null;
  stack_member_count: number | null;
  is_stack_representative: boolean;
}

/** Catalog metadata for the ranked keys, keyed by image key. */
export function imageMetaMap(db: Db, keys: readonly string[]): Map<string, ImageMeta> {
  if (keys.length === 0) return new Map();
  const out = new Map<string, ImageMeta>();
  const rows = inChunks(keys, (batch) =>
    db
      .prepare(
        `SELECT key, filename, date_taken, rating, instagram_posted FROM images ` +
          `WHERE key IN (${batch.map(() => '?').join(',')})`,
      )
      .all(...batch) as {
      key: string;
      filename: string | null;
      date_taken: string | null;
      rating: number | null;
      instagram_posted: number | null;
    }[],
  );
  for (const r of rows) {
    out.set(String(r.key), {
      filename: r.filename || '',
      date_taken: r.date_taken || '',
      rating: Math.trunc(r.rating || 0),
      instagram_posted: Boolean(r.instagram_posted),
      image_type: 'catalog',
    });
  }
  return out;
}

/**
 * Keys that are stack members but not the representative.
 *
 * These are dropped from every identity ranking: a burst of twenty near-identical
 * frames would otherwise fill the whole page.
 */
export function stackNonRepresentativeKeys(db: Db, keys: readonly string[]): Set<string> {
  if (keys.length === 0) return new Set();
  const rows = inChunks(keys, (batch) =>
    db
      .prepare(
        `
        SELECT m.image_key FROM image_stack_members m
        INNER JOIN image_stacks s ON s.stack_id = m.stack_id
        WHERE m.image_key IN (${batch.map(() => '?').join(',')}) AND m.image_key <> s.representative_key
        `,
      )
      .all(...batch) as { image_key: string }[],
  );
  return new Set(rows.map((r) => String(r.image_key)));
}

/**
 * Stack columns for the given keys.
 *
 * `stack_member_count` comes from the denormalized `image_stacks.stack_size` here,
 * unlike `stackMetadataForApi`, which counts live membership. Kept as-is so the
 * identity payload matches what Flask sent.
 */
export function stackFieldsForImageKeys(
  db: Db,
  keys: readonly string[],
): Map<string, StackFields> {
  if (keys.length === 0) return new Map();
  const rows = inChunks(keys, (batch) =>
    db
      .prepare(
        `
        SELECT m.image_key, s.stack_id, s.representative_key, s.stack_size
        FROM image_stack_members m
        INNER JOIN image_stacks s ON s.stack_id = m.stack_id
        WHERE m.image_key IN (${batch.map(() => '?').join(',')})
        `,
      )
      .all(...batch) as {
      image_key: string;
      stack_id: number;
      representative_key: string;
      stack_size: number;
    }[],
  );
  const out = new Map<string, StackFields>();
  for (const r of rows) {
    const k = String(r.image_key);
    out.set(k, {
      stack_id: Math.trunc(r.stack_id),
      stack_member_count: Math.trunc(r.stack_size),
      is_stack_representative: k === String(r.representative_key),
    });
  }
  return out;
}

export type RankedItem = PeakPercentileItem & Partial<ImageMeta> & Partial<StackFields>;

/** Compare two strings the way Python's `<` does for ASCII keys. */
function cmpStr(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * Eligible images only, ordered by `ranking_percentile` descending.
 *
 * `sortByDate` only moves the *tiebreaker*: the corroboration-vetoed ranking
 * percentile stays the primary key, so asking for "oldest" reorders equally-ranked
 * photos rather than turning this into a date listing.
 *
 * The three successive stable sorts reproduce Python's exactly — key ascending,
 * then date, then ranking — which is not the same as one comparator with three
 * clauses when equal ranking values arise from different rounding paths.
 */
export function rankBestPhotos(
  db: Db,
  opts: {
    limit: number;
    offset: number;
    minPerspectives?: number | null;
    sortByDate?: 'newest' | 'oldest' | null;
    posted?: boolean | null;
  },
): { items: RankedItem[]; total: number; meta: PeakPercentileMeta } {
  const sortByDate = opts.sortByDate ?? null;
  if (sortByDate !== null && sortByDate !== 'newest' && sortByDate !== 'oldest') {
    throw new RangeError("sort_by_date must be 'newest' or 'oldest'");
  }

  const { items, meta } = computeImagePeakPercentileScores(db, {
    minPerspectives: opts.minPerspectives ?? null,
    includeIneligible: false,
  });
  const eligible = items.filter((i) => i.eligible);
  const imgMeta = imageMetaMap(db, eligible.map((i) => String(i.image_key)));

  let enriched: RankedItem[] = eligible.map((i) => ({
    ...i,
    ...(imgMeta.get(String(i.image_key)) ?? {}),
  }));

  const dropKeys = stackNonRepresentativeKeys(db, enriched.map((r) => String(r.image_key)));
  enriched = enriched.filter((r) => !dropKeys.has(String(r.image_key)));

  if (enriched.length > 0) {
    const stackByKey = stackFieldsForImageKeys(db, enriched.map((r) => String(r.image_key)));
    for (const r of enriched) {
      const fields = stackByKey.get(String(r.image_key));
      if (fields) Object.assign(r, fields);
      else {
        r.stack_id = null;
        r.stack_member_count = null;
        r.is_stack_representative = false;
      }
    }
  }

  const dateDescending = sortByDate !== 'oldest';
  enriched.sort((a, b) => cmpStr(String(a.image_key), String(b.image_key)));
  enriched.sort((a, b) => {
    const c = cmpStr(a.date_taken ?? '', b.date_taken ?? '');
    return dateDescending ? -c : c;
  });
  enriched.sort((a, b) => b.ranking_percentile - a.ranking_percentile);

  if (opts.posted === true) enriched = enriched.filter((r) => r.instagram_posted === true);
  else if (opts.posted === false) enriched = enriched.filter((r) => !r.instagram_posted);

  const total = enriched.length;
  return { items: enriched.slice(opts.offset, opts.offset + opts.limit), total, meta };
}
