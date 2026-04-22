import type { ImageView } from '../../services/api'
import { Badge } from '../ui/badges'
import { PrimaryScorePill, type PrimaryScoreSource } from './PrimaryScorePill'

export type { PrimaryScoreSource }

interface ImageMetadataBadgesProps {
  image: ImageView
  primaryScoreSource: PrimaryScoreSource
  /** When true, renders without the primary score pill (e.g. modal header
   *  where the breakdown below already owns the aggregate). */
  hidePrimaryScore?: boolean
  /** When true, omits the green "Posted" chip (e.g. when shown as overlay on the thumbnail). */
  hidePostedBadge?: boolean
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
  hidePostedBadge = false,
  className = '',
}: ImageMetadataBadgesProps) {
  const showPrimary = !hidePrimaryScore && primaryScoreSource !== 'none'
  const showPostedChip = image.instagram_posted && !hidePostedBadge

  return (
    <div className={`flex items-center gap-2 flex-wrap ${className}`.trim()}>
      {showPostedChip ? <Badge variant="success">Posted</Badge> : null}
      {typeof image.rating === 'number' && image.rating > 0 ? (
        <Badge variant="accent">{image.rating}★</Badge>
      ) : null}
      {image.pick ? <Badge variant="accent">Pick</Badge> : null}
      {image.ai_analyzed ? <Badge variant="accent">AI</Badge> : null}
      {showPrimary ? <PrimaryScorePill image={image} source={primaryScoreSource} /> : null}
    </div>
  )
}
