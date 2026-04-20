import type { ImageView } from '../../services/api'
import { DESCRIPTION_PERSPECTIVE_LABELS } from '../DescriptionPanel/perspectiveLabels'
import { Badge } from '../ui/Badge'
import { ScorePill } from '../ui/badges/ScorePill'
import { IDENTITY_LABEL_AGGREGATE } from '../../constants/strings'

/**
 * Source of the primary score pill (CONTEXT Q3):
 *   - `'identity'`: Identity aggregate (Top Photos, Best, Post-next, Unposted,
 *     Analytics non-posted). Pill labeled "Aggregate".
 *   - `'catalog'`: Catalog perspective score when available; falls back to the
 *     description best-perspective score. Used by the catalog browsing views.
 *   - `'none'`: Hide the primary score pill (Instagram tiles).
 */
export type PrimaryScoreSource = 'identity' | 'catalog' | 'none'

interface ImageMetadataBadgesProps {
  image: ImageView
  primaryScoreSource: PrimaryScoreSource
  /** When true, renders without the primary score pill (e.g. modal header
   *  where the breakdown below already owns the aggregate). */
  hidePrimaryScore?: boolean
  className?: string
}

/**
 * Core tile/modal metadata chips + optional primary score pill.
 *
 * Matches the catalog-card chip set (rating ★, Pick, AI, Posted) and adds
 * the CONTEXT-driven primary score pill. Everything wraps via `flex-wrap`
 * so no horizontal scroll trap on narrow screens.
 */
export function ImageMetadataBadges({
  image,
  primaryScoreSource,
  hidePrimaryScore = false,
  className = '',
}: ImageMetadataBadgesProps) {
  const showPrimary = !hidePrimaryScore && primaryScoreSource !== 'none'

  return (
    <div className={`flex items-center gap-2 flex-wrap ${className}`.trim()}>
      {image.instagram_posted ? <Badge variant="success">Posted</Badge> : null}
      {typeof image.rating === 'number' && image.rating > 0 ? (
        <Badge variant="accent">{image.rating}★</Badge>
      ) : null}
      {image.pick ? <Badge variant="accent">Pick</Badge> : null}
      {image.ai_analyzed ? <Badge variant="accent">AI</Badge> : null}
      {showPrimary ? renderPrimaryPill(image, primaryScoreSource) : null}
    </div>
  )
}

function renderPrimaryPill(image: ImageView, source: PrimaryScoreSource) {
  switch (source) {
    case 'identity': {
      const score = image.identity_aggregate_score
      if (typeof score !== 'number') return null
      return <ScorePill score={score} label={IDENTITY_LABEL_AGGREGATE} />
    }
    case 'catalog': {
      const catalog = image.catalog_perspective_score
      if (typeof catalog === 'number') {
        const slug = image.catalog_score_perspective ?? undefined
        return <ScorePill score={catalog} label={shortSlug(slug)} />
      }
      const best = image.description_best_perspective
      const perspectives = image.description_perspectives
      if (
        best &&
        perspectives &&
        typeof perspectives === 'object' &&
        best in perspectives
      ) {
        const p = (perspectives as Record<string, { score?: number } | undefined>)[best]
        if (p && typeof p.score === 'number') {
          return (
            <ScorePill
              score={p.score}
              label={DESCRIPTION_PERSPECTIVE_LABELS[best] || best}
            />
          )
        }
      }
      return null
    }
    case 'none':
      return null
  }
}

function shortSlug(slug: string | undefined): string | undefined {
  if (!slug) return undefined
  return slug.length > 10 ? `${slug.slice(0, 10)}…` : slug
}
