/**
 * Burst stack membership and mutations. Port of `core/database/stacks.py`.
 *
 * Every mutation here must run inside `libraryWrite` so it is one atomic
 * transaction — a half-applied split leaves `image_stacks.stack_size` disagreeing
 * with `image_stack_members`, which the grid reads as a phantom stack.
 */
import type { Db } from '../connection.js';

/** Invalid stack edit; `statusCode` is the HTTP status the API maps it to. */
export class StackMutationError extends Error {
  readonly statusCode: number;

  constructor(message: string, statusCode = 400) {
    super(message);
    this.name = 'StackMutationError';
    this.statusCode = statusCode;
  }
}

export interface StackMetadata {
  stack_id: number;
  representative_key: string;
  stack_member_count: number;
  member_keys: string[];
}

/**
 * Lexicographically largest key, the last-resort representative.
 *
 * Python used `sorted(keys)[-1]`, which orders by Unicode code point; JavaScript's
 * default sort orders by UTF-16 code unit. The two differ only above the BMP, and
 * every key in this catalog is drawn from alphanumerics, `-`, `_`, space and
 * parentheses, so they agree here.
 */
function largestKey(keys: readonly string[]): string {
  return [...keys].sort()[keys.length - 1]!;
}

export function stackExists(db: Db, stackId: number): boolean {
  const row = db
    .prepare('SELECT 1 AS o FROM image_stacks WHERE stack_id = ? LIMIT 1')
    .get(stackId);
  return row !== undefined;
}

/** Member keys for `stackId`, ascending. */
export function listStackMemberKeys(db: Db, stackId: number): string[] {
  const rows = db
    .prepare(
      `
        SELECT image_key FROM image_stack_members
        WHERE stack_id = ?
        ORDER BY image_key ASC
        `,
    )
    .all(stackId) as { image_key: string }[];
  return rows.map((r) => String(r.image_key));
}

/**
 * All keys in the stack containing `catalogKey`, or `[catalogKey]` when it is a
 * solo image.
 */
export function listCatalogStackMemberKeys(db: Db, catalogKey: string): string[] {
  const row = db
    .prepare('SELECT stack_id FROM image_stack_members WHERE image_key = ? LIMIT 1')
    .get(catalogKey) as { stack_id: number } | undefined;
  if (!row) return [catalogKey];
  return listStackMemberKeys(db, Math.trunc(row.stack_id));
}

/**
 * Pick a representative using the same ranking as the `batch_stack_detect` job:
 * rated images first, then higher rating, then higher mean active-perspective
 * score, then newest, then largest key.
 */
export function selectStackRepresentativeKeyForKeys(
  db: Db,
  keys: readonly string[],
): string | null {
  const burstKeys = keys.filter(Boolean).map(String);
  if (burstKeys.length === 0) return null;
  const ph = burstKeys.map(() => '?').join(',');
  const row = db
    .prepare(
      'SELECT i.key AS k FROM images i ' +
        'LEFT JOIN ( ' +
        '  SELECT s.image_key AS image_key, AVG(s.score) AS ai_score ' +
        '  FROM image_scores s ' +
        '  INNER JOIN perspectives p ON p.slug = s.perspective_slug AND p.active = 1 ' +
        "  WHERE s.is_current = 1 AND s.image_type = 'catalog' " +
        '  GROUP BY s.image_key ' +
        ') agg ON agg.image_key = i.key ' +
        `WHERE i.key IN (${ph}) ` +
        'ORDER BY (i.rating > 0) DESC, i.rating DESC, COALESCE(agg.ai_score, 0) DESC, ' +
        'i.date_taken DESC, i.key DESC LIMIT 1',
    )
    .get(...burstKeys) as { k: string | null } | undefined;
  if (!row || row.k === null || row.k === undefined) return null;
  return String(row.k);
}

/**
 * Stack row plus member keys.
 *
 * `stack_member_count` comes from live membership rather than the stored
 * `stack_size`, which is why this is the authoritative shape for API responses.
 */
export function stackMetadataForApi(db: Db, stackId: number): StackMetadata | null {
  const row = db
    .prepare(
      `
        SELECT stack_id, representative_key, stack_size
        FROM image_stacks
        WHERE stack_id = ?
        `,
    )
    .get(stackId) as { stack_id: number; representative_key: string } | undefined;
  if (!row) return null;
  const memberKeys = listStackMemberKeys(db, stackId);
  return {
    stack_id: Math.trunc(row.stack_id),
    representative_key: String(row.representative_key),
    stack_member_count: memberKeys.length,
    member_keys: memberKeys,
  };
}

export interface StackRowFields {
  stack_id: number | null;
  stack_member_count: number | null;
  is_stack_representative: boolean;
}

/**
 * Stack columns aligned with the catalog list / by-keys rows, so the detail API
 * reports the same stack state the grid does.
 */
export function catalogImageStackRowFields(db: Db, imageKey: string): StackRowFields {
  const row = db
    .prepare(
      `
        SELECT st.stack_id AS stack_id, st.stack_size AS stack_member_count,
        CASE WHEN st.stack_id IS NOT NULL AND i.key = st.representative_key
             THEN 1 ELSE 0 END AS is_stack_representative
        FROM images i
        LEFT JOIN image_stack_members AS m_st ON m_st.image_key = i.key
        LEFT JOIN image_stacks AS st ON st.stack_id = m_st.stack_id
        WHERE i.key = ?
        `,
    )
    .get(imageKey) as
    | { stack_id: number | null; stack_member_count: number | null; is_stack_representative: number }
    | undefined;
  if (!row || row.stack_id === null) {
    return { stack_id: null, stack_member_count: null, is_stack_representative: false };
  }
  return {
    stack_id: Math.trunc(row.stack_id),
    stack_member_count: row.stack_member_count === null ? null : Math.trunc(row.stack_member_count),
    is_stack_representative: Boolean(row.is_stack_representative),
  };
}

export interface SplitMemberResult {
  split_out_key: string;
  remaining_stack: StackMetadata | null;
  dissolved: boolean;
}

/**
 * Remove `imageKey` from `stackId`, dissolving singleton remnants back to solo
 * images. Call inside `libraryWrite`.
 *
 * A one-member stack is not a stack, so removing the second-to-last member deletes
 * the stack row as well and reports `dissolved: true`.
 */
export function stackSplitMemberOut(
  db: Db,
  stackId: number,
  imageKey: string,
): SplitMemberResult {
  const stackRow = db
    .prepare('SELECT stack_id, representative_key FROM image_stacks WHERE stack_id = ?')
    .get(stackId) as { representative_key: string } | undefined;
  if (!stackRow) throw new StackMutationError('stack not found', 404);

  const mem = db
    .prepare('SELECT 1 AS o FROM image_stack_members WHERE stack_id = ? AND image_key = ?')
    .get(stackId, imageKey);
  if (!mem) throw new StackMutationError('image_key is not a member of this stack', 400);

  db.prepare('DELETE FROM image_stack_members WHERE stack_id = ? AND image_key = ?').run(
    stackId,
    imageKey,
  );

  const remainingKeys = listStackMemberKeys(db, stackId);

  if (remainingKeys.length === 0) {
    db.prepare('DELETE FROM image_stacks WHERE stack_id = ?').run(stackId);
    return { split_out_key: imageKey, remaining_stack: null, dissolved: true };
  }

  if (remainingKeys.length === 1) {
    db.prepare('DELETE FROM image_stack_members WHERE stack_id = ? AND image_key = ?').run(
      stackId,
      remainingKeys[0]!,
    );
    db.prepare('DELETE FROM image_stacks WHERE stack_id = ?').run(stackId);
    return { split_out_key: imageKey, remaining_stack: null, dissolved: true };
  }

  const oldRep = String(stackRow.representative_key);
  let newRep = remainingKeys.includes(oldRep)
    ? oldRep
    : selectStackRepresentativeKeyForKeys(db, remainingKeys);
  if (!newRep || !remainingKeys.includes(newRep)) newRep = largestKey(remainingKeys);

  db.prepare(
    `
        UPDATE image_stacks
        SET representative_key = ?, stack_size = ?, user_modified = 1
        WHERE stack_id = ?
        `,
  ).run(newRep, remainingKeys.length, stackId);

  const meta = stackMetadataForApi(db, stackId);
  if (!meta) throw new StackMutationError('stack disappeared during split', 500);
  return { split_out_key: imageKey, remaining_stack: meta, dissolved: false };
}

export interface MergeResult {
  stack: StackMetadata;
  merged_stack_id: number;
}

/**
 * Move every member of `sourceStackId` into `targetStackId` and delete the source
 * stack row. Call inside `libraryWrite`.
 */
export function stackMergeInto(
  db: Db,
  targetStackId: number,
  sourceStackId: number,
): MergeResult {
  if (targetStackId === sourceStackId) {
    throw new StackMutationError('cannot merge a stack into itself', 400);
  }

  const tRow = db
    .prepare('SELECT stack_id, representative_key FROM image_stacks WHERE stack_id = ?')
    .get(targetStackId) as { representative_key: string } | undefined;
  const sRow = db
    .prepare('SELECT stack_id FROM image_stacks WHERE stack_id = ?')
    .get(sourceStackId);
  if (!tRow || !sRow) throw new StackMutationError('stack not found', 404);

  db.prepare('UPDATE image_stack_members SET stack_id = ? WHERE stack_id = ?').run(
    targetStackId,
    sourceStackId,
  );
  db.prepare('DELETE FROM image_stacks WHERE stack_id = ?').run(sourceStackId);

  const keys = listStackMemberKeys(db, targetStackId);
  if (keys.length === 0) {
    db.prepare('DELETE FROM image_stacks WHERE stack_id = ?').run(targetStackId);
    throw new StackMutationError('merge produced an empty stack', 500);
  }

  const oldRep = String(tRow.representative_key);
  let newRep = keys.includes(oldRep) ? oldRep : selectStackRepresentativeKeyForKeys(db, keys);
  if (!newRep || !keys.includes(newRep)) newRep = largestKey(keys);

  db.prepare(
    `
        UPDATE image_stacks
        SET representative_key = ?, stack_size = ?, user_modified = 1
        WHERE stack_id = ?
        `,
  ).run(newRep, keys.length, targetStackId);

  const meta = stackMetadataForApi(db, targetStackId);
  if (!meta) throw new StackMutationError('stack disappeared during merge', 500);
  return { stack: meta, merged_stack_id: sourceStackId };
}

/** The stack containing `imageKey`, or `null` for a solo image. */
export function stackIdForImageKey(db: Db, imageKey: string): number | null {
  const row = db
    .prepare('SELECT stack_id FROM image_stack_members WHERE image_key = ? LIMIT 1')
    .get(imageKey) as { stack_id: number } | undefined;
  return row ? Math.trunc(row.stack_id) : null;
}

/**
 * Point `stackId` at a new representative, which must already be a member.
 * Call inside `libraryWrite`.
 */
export function stackSetRepresentative(
  db: Db,
  stackId: number,
  newRepresentativeKey: string,
): { stack: StackMetadata } {
  const stackRow = db
    .prepare('SELECT stack_id FROM image_stacks WHERE stack_id = ?')
    .get(stackId);
  if (!stackRow) throw new StackMutationError('stack not found', 404);

  const mem = db
    .prepare('SELECT 1 AS o FROM image_stack_members WHERE stack_id = ? AND image_key = ?')
    .get(stackId, newRepresentativeKey);
  if (!mem) throw new StackMutationError('image_key is not a member of this stack', 400);

  db.prepare(
    'UPDATE image_stacks SET representative_key = ?, user_modified = 1 WHERE stack_id = ?',
  ).run(newRepresentativeKey, stackId);

  // Realign the denormalized stack_size with actual membership while we hold the
  // writer seat; a stale value here shows a wrong badge count in the grid.
  const cntRow = db
    .prepare('SELECT COUNT(*) AS c FROM image_stack_members WHERE stack_id = ?')
    .get(stackId) as { c: number } | undefined;
  db.prepare('UPDATE image_stacks SET stack_size = ? WHERE stack_id = ?').run(
    cntRow ? Math.trunc(cntRow.c) : 0,
    stackId,
  );

  const meta = stackMetadataForApi(db, stackId);
  if (!meta) throw new StackMutationError('stack disappeared during update', 500);
  return { stack: meta };
}
