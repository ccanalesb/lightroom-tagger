import type { ImageView } from '../../services/api'
import { AIDescriptionSection } from '../DescriptionPanel'
import { AIPerspectiveSection } from '../catalog/AIPerspectiveSection'
import { Badge } from '../ui/badges'
import { MetadataRow } from '../ui/MetadataRow'
import {
  DATE_NO_DATE,
  IMAGE_DETAILS_DESCRIPTIVE_TECHNICAL,
  LABEL_CAPTION,
  LABEL_DATE,
  LABEL_DIMENSIONS,
  LABEL_FILENAME,
  LABEL_KEYWORDS,
  LABEL_PATH,
  LABEL_TITLE,
} from '../../constants/strings'

interface CatalogImageDetailSectionsProps {
  image: ImageView
  /** Called when the caller should re-fetch detail (after description
   *  jobs complete) so the modal header / breakdown stay in sync. */
  onDataChanged?: () => void
}

/**
 * Catalog-specific body sections for the consolidated ImageDetailModal.
 * Descriptive/technical content comes from `image_descriptions`; per-perspective
 * scores come from `image_scores` in a separate section with its own regenerate control.
 */
export function CatalogImageDetailSections({
  image,
  onDataChanged,
}: CatalogImageDetailSectionsProps) {
  const dateDisplay = image.date_taken
    ? new Date(image.date_taken).toLocaleString()
    : DATE_NO_DATE
  const keywords = Array.isArray(image.keywords) ? image.keywords : []
  const dimensions =
    image.width && image.height ? `${image.width} × ${image.height}` : null

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <MetadataRow label={LABEL_FILENAME} value={image.filename ?? image.key} />
        <MetadataRow label={LABEL_TITLE} value={image.title} />
        <MetadataRow label={LABEL_DATE} value={dateDisplay} />
        <MetadataRow label={LABEL_PATH} value={image.filepath} mono />
        <MetadataRow label={LABEL_DIMENSIONS} value={dimensions} />
      </div>

      {image.caption ? (
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">{LABEL_CAPTION}</h3>
          <p className="text-sm text-text-secondary">{image.caption}</p>
        </div>
      ) : null}

      {keywords.length > 0 ? (
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">{LABEL_KEYWORDS}</h3>
          <div className="flex flex-wrap gap-2">
            {keywords.map((keyword, idx) => (
              <Badge key={idx} variant="default">
                {keyword}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      <AIDescriptionSection
        imageKey={image.key}
        imageType="catalog"
        titleOverride={IMAGE_DETAILS_DESCRIPTIVE_TECHNICAL}
        onDataChanged={onDataChanged}
      />
      <AIPerspectiveSection
        imageKey={image.key}
        imageType="catalog"
        onDataChanged={onDataChanged}
      />
    </div>
  )
}
