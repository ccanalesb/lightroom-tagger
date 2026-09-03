/**
 * Perspective registry and image-score queries.
 * Port of `lightroom_tagger/core/database/scores.py`.
 */
import type { Db } from '../connection.js';
import { nowIsoUtc } from '../../utils/datetime.js';

/**
 * The yt-to-photo-prompt-lab exporter marks an optional (excusable) dimension with
 * an HTML comment in the perspective markdown. This marker is the sole source of
 * truth for `perspectives.optional`: it is re-derived on every write of
 * `prompt_markdown` (seed, create, edit, reset-to-default) so a changed marker
 * always wins and cannot drift. See ADR-0012.
 */
const OPTIONAL_MARKER_RE = /<!--\s*optional\s*:\s*true\s*-->/i;

/** Whether perspective markdown opts into the excusable (not-attempted) contract. */
export function markdownMarksOptional(markdown: string | null | undefined): boolean {
  return OPTIONAL_MARKER_RE.test(markdown ?? '');
}

export interface PerspectiveRow {
  id: number;
  slug: string;
  display_name: string;
  description: string;
  prompt_markdown: string;
  active: number;
  optional: number | null;
  source_filename: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** Perspective rows as dicts ordered by `slug`. */
export function listPerspectives(db: Db, opts: { activeOnly?: boolean } = {}): PerspectiveRow[] {
  let sql = 'SELECT * FROM perspectives';
  if (opts.activeOnly) sql += ' WHERE active = 1';
  sql += ' ORDER BY slug ASC';
  return db.prepare(sql).all() as PerspectiveRow[];
}

export function getPerspectiveBySlug(db: Db, slug: string): PerspectiveRow | null {
  const row = db.prepare('SELECT * FROM perspectives WHERE slug = ? LIMIT 1').get(slug);
  return (row as PerspectiveRow | undefined) ?? null;
}

/**
 * Insert a `perspectives` row. Caller commits.
 *
 * `optional` is derived from the `prompt_markdown` marker, never passed in.
 */
export function insertPerspective(
  db: Db,
  args: {
    slug: string;
    displayName: string;
    promptMarkdown: string;
    description?: string;
    active?: boolean;
    sourceFilename?: string | null;
  },
): void {
  const now = nowIsoUtc();
  const optional = markdownMarksOptional(args.promptMarkdown);
  db.prepare(
    `INSERT INTO perspectives (
       slug, display_name, description, prompt_markdown,
       active, optional, source_filename, created_at, updated_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    args.slug,
    args.displayName,
    args.description ?? '',
    args.promptMarkdown,
    args.active === false ? 0 : 1,
    optional ? 1 : 0,
    args.sourceFilename ?? null,
    now,
    now,
  );
}

/**
 * Partially update a perspective by `slug`. Returns whether a row was updated.
 *
 * `optional` is not a parameter: whenever `prompt_markdown` is written it is
 * re-derived from the marker, so a removed marker un-sets optional. See ADR-0012.
 *
 * Mirrors the Python fallback exactly: a zero `changes` count still reports true
 * when the row exists, because writing identical values is not a failure.
 */
export function updatePerspective(
  db: Db,
  slug: string,
  patch: {
    displayName?: string | null;
    description?: string | null;
    promptMarkdown?: string | null;
    active?: boolean | null;
  },
): boolean {
  const fields: string[] = [];
  const values: (string | number)[] = [];

  if (patch.displayName != null) {
    fields.push('display_name = ?');
    values.push(patch.displayName);
  }
  if (patch.description != null) {
    fields.push('description = ?');
    values.push(patch.description);
  }
  if (patch.promptMarkdown != null) {
    fields.push('prompt_markdown = ?');
    values.push(patch.promptMarkdown);
    fields.push('optional = ?');
    values.push(markdownMarksOptional(patch.promptMarkdown) ? 1 : 0);
  }
  if (patch.active != null) {
    fields.push('active = ?');
    values.push(patch.active ? 1 : 0);
  }
  if (fields.length === 0) return false;

  fields.push('updated_at = ?');
  values.push(nowIsoUtc());
  values.push(slug);

  const info = db
    .prepare(`UPDATE perspectives SET ${fields.join(', ')} WHERE slug = ?`)
    .run(...values);
  if (info.changes > 0) return true;
  return getPerspectiveBySlug(db, slug) !== null;
}

/** Delete a perspective by `slug`. Returns whether a row was removed. */
export function deletePerspective(db: Db, slug: string): boolean {
  return db.prepare('DELETE FROM perspectives WHERE slug = ?').run(slug).changes > 0;
}

export interface ImageScoreRow {
  id: number | null;
  image_key: string;
  image_type: string;
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

/** All `image_scores` rows for this image with `is_current = 1`. */
export function getCurrentScoresForImage(
  db: Db,
  imageKey: string,
  imageType = 'catalog',
): ImageScoreRow[] {
  return db
    .prepare(
      `SELECT * FROM image_scores
       WHERE image_key = ? AND image_type = ? AND is_current = 1
       ORDER BY perspective_slug ASC`,
    )
    .all(imageKey, imageType) as ImageScoreRow[];
}

/**
 * All `image_scores` rows for one image and perspective, newest first.
 *
 * Older rubric versions remain with `is_current = 0` on purpose; consumers use
 * `is_current` to mark the active rubric version.
 */
export function listScoreHistoryForPerspective(
  db: Db,
  imageKey: string,
  imageType: string,
  perspectiveSlug: string,
): ImageScoreRow[] {
  return db
    .prepare(
      `SELECT * FROM image_scores
       WHERE image_key = ? AND image_type = ? AND perspective_slug = ?
       ORDER BY scored_at DESC, id DESC`,
    )
    .all(imageKey, imageType, perspectiveSlug) as ImageScoreRow[];
}
