import type { Match } from '../../../services/api';

/**
 * Return the candidate to surface after the current one is rejected.
 * Prefers the candidate *after* the rejected one; wraps to the previous
 * entry if we're at the end; returns undefined when the list has only
 * the rejected candidate left.
 */
export function findNextCandidateInOrder(
  candidates: Match[],
  current: Match,
): Match | undefined {
  const idx = candidates.findIndex(
    (c) => c.catalog_key === current.catalog_key && c.instagram_key === current.instagram_key,
  );
  if (idx === -1) return candidates[0];
  if (idx < candidates.length - 1) return candidates[idx + 1];
  if (candidates.length > 1) return candidates[idx - 1];
  return undefined;
}
