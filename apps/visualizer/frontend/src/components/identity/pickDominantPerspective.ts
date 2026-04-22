import type { IdentityPerPerspectiveScore } from '../../services/api'

export function pickDominantPerspective(
  entries: IdentityPerPerspectiveScore[] | undefined | null,
): IdentityPerPerspectiveScore | null {
  if (!entries || entries.length === 0) return null
  return entries.reduce((best, entry) =>
    Number.isFinite(entry.score) && entry.score > (Number.isFinite(best.score) ? best.score : -Infinity)
      ? entry
      : best,
  )
}
