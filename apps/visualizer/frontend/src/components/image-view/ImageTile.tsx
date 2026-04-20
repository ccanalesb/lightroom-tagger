import type { ReactNode } from 'react'
import type { ImageView } from '../../services/api'
import { ImageMetadataBadges, type PrimaryScoreSource } from './ImageMetadataBadges'
import { imageTileVariantClasses, type ImageTileVariant } from './imageTileVariants'

export type { ImageTileVariant } from './imageTileVariants'

interface ImageTileProps {
  image: ImageView
  variant: ImageTileVariant
  primaryScoreSource: PrimaryScoreSource
  onClick: () => void
  /** Secondary line beneath filename (e.g. folder, "Estimated 2024/05"). */
  subtitle?: string
  /** Optional ReactNode overlayed top-right on the thumbnail (e.g. Instagram
   *  matched/described badges). */
  overlayBadges?: ReactNode
  /** Content rendered below the metadata row (e.g. post-next reason bullets). */
  footer?: ReactNode
  className?: string
}

/**
 * Single tile component for every image surface. Aspect ratio and body
 * density change per variant; badge markup and primary-score logic come
 * from the shared `ImageMetadataBadges` to avoid drift.
 *
 * Thumbnail path is `/api/images/<image_type>/<key>/thumbnail` (matches
 * existing backend route).
 */
export function ImageTile({
  image,
  variant,
  primaryScoreSource,
  onClick,
  subtitle,
  overlayBadges,
  footer,
  className = '',
}: ImageTileProps) {
  const classes = imageTileVariantClasses(variant)
  const imageType = image.image_type
  const dateDisplay = image.date_taken
    ? new Date(image.date_taken).toLocaleDateString()
    : image.created_at
      ? new Date(image.created_at).toLocaleDateString()
      : '—'

  return (
    <div
      className={`group overflow-hidden rounded-card border border-border bg-bg shadow-card transition-all hover:border-border-strong hover:shadow-deep ${classes.root} ${className}`.trim()}
      data-testid="image-tile"
      data-image-key={image.key}
      data-image-type={imageType}
      data-variant={variant}
    >
      <button
        type="button"
        onClick={onClick}
        className={`block w-full text-left focus:outline-none focus:ring-2 focus:ring-accent focus:ring-inset ${classes.button}`}
      >
        <div className={`relative bg-surface ${classes.thumb}`}>
          <img
            src={`/api/images/${imageType}/${encodeURIComponent(image.key)}/thumbnail`}
            alt={image.filename ?? image.key}
            className="absolute inset-0 h-full w-full object-cover"
            loading="lazy"
          />
          {overlayBadges ? (
            <div className="absolute right-2 top-2 flex flex-col gap-1">
              {overlayBadges}
            </div>
          ) : null}
        </div>
      </button>
      <div className={`space-y-1 ${classes.body}`}>
        <p className={`truncate font-medium text-text ${classes.title}`}>
          {image.filename ?? image.key}
        </p>
        {subtitle ? (
          <p className={`truncate text-text-secondary ${classes.subtitle}`}>{subtitle}</p>
        ) : image.title ? (
          <p className={`truncate text-text-secondary ${classes.subtitle}`}>{image.title}</p>
        ) : null}
        <p className={`text-text-tertiary ${classes.meta}`}>{dateDisplay}</p>
        <ImageMetadataBadges
          image={image}
          primaryScoreSource={primaryScoreSource}
        />
        {footer}
      </div>
    </div>
  )
}
