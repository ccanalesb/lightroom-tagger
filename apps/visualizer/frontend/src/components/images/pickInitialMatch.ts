import type { Match, MatchGroup } from '../../services/api';

/**
 * Choose the candidate to surface for a match group's list tile:
 * rank-1 if present, otherwise the highest-scoring candidate.
 * Returns undefined when the group has no candidates.
 */
export function pickInitialMatch(group: MatchGroup): Match | undefined {
  if (group.candidates.length === 0) return undefined;
  const rank1 = group.candidates.find((c) => c.rank === 1);
  if (rank1) return rank1;
  return group.candidates.reduce((best, c) => (c.score > best.score ? c : best));
}
