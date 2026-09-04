/**
 * Validate `score_perspective` values by catalog row existence.
 */
import type { Db } from '../db/connection.js';
import { getPerspectiveBySlug } from '../db/library/scores.js';

/**
 * Resolve a `score_perspective` query value.
 *
 * An empty or absent slug is not an error — it means "no perspective filter".
 * Existence is satisfied by any row in `perspectives` regardless of `active`, so a
 * deactivated perspective can still be used to sort or filter historical scores.
 */
export function validateScorePerspectiveExists(
  db: Db,
  slug: string | null | undefined,
): { slug: string | null; error: string | null } {
  const sp = (slug ?? '').trim() || null;
  if (sp === null) return { slug: null, error: null };
  if (getPerspectiveBySlug(db, sp) === null) {
    return { slug: null, error: `unknown perspective '${sp}'` };
  }
  return { slug: sp, error: null };
}
