import type { ImageView } from '../../services/api'
import { ScorePill } from '../ui/badges'
import { IDENTITY_LABEL_AGGREGATE, IDENTITY_LABEL_PEAK } from '../../constants/strings'

/**
 * Source of the primary score pill (CONTEXT Q3):
 *   - `'identity'`: Identity aggregate (Top Photos, Best, Post-next, Unposted,
 *     Analytics non-posted). Pill labeled "Aggregate".
 *   - `'catalog'`: Max current perspective score from ``image_scores`` (list/detail API).
 *     Used by the catalog browsing views.
 *   - `'none'`: Hide the primary score pill (Instagram tiles).
 */
export type PrimaryScoreSource = 'identity' | 'catalog' | 'none'

interface PrimaryScorePillProps {
  image: ImageView
  source: PrimaryScoreSource
}

/**
 * Resolves the primary score pill for a given `ImageView` according to
 * the caller-provided `PrimaryScoreSource` and renders a `<ScorePill>`.
 * Returns `null` when no score is available (or when `source === 'none'`).
 */
export function PrimaryScorePill({ image, source }: PrimaryScorePillProps) {
  switch (source) {
    case 'identity': {
      const peak = image.identity_peak_percentile
      if (typeof peak === 'number' && Number.isFinite(peak)) {
        return <ScorePill score={peak * 10} label={IDENTITY_LABEL_PEAK} />
      }
      const score = image.identity_aggregate_score
      if (typeof score !== 'number') return null
      return <ScorePill score={score} label={IDENTITY_LABEL_AGGREGATE} />
    }
    case 'catalog': {
      const catalog = image.catalog_perspective_score
      if (typeof catalog !== 'number') return null
      const slug = image.catalog_score_perspective ?? undefined
      return <ScorePill score={catalog} label={shortSlug(slug)} />
    }
    case 'none':
      return null
  }
}

function shortSlug(slug: string | undefined): string | undefined {
  if (!slug) return undefined
  return slug.length > 10 ? `${slug.slice(0, 10)}…` : slug
}
