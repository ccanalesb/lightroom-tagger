import type { IdentityPerPerspectiveScore } from '../../services/api'

function perspectiveRankMetric(entry: IdentityPerPerspectiveScore): number {
  if (typeof entry.percentile === 'number' && Number.isFinite(entry.percentile)) {
    return entry.percentile
  }
  return entry.score
}

export function pickDominantPerspective(
  entries: IdentityPerPerspectiveScore[] | undefined | null,
): IdentityPerPerspectiveScore | null {
  if (!entries || entries.length === 0) return null
  return entries.reduce((best, entry) =>
    perspectiveRankMetric(entry) >
    (Number.isFinite(perspectiveRankMetric(best)) ? perspectiveRankMetric(best) : -Infinity)
      ? entry
      : best,
  )
}
