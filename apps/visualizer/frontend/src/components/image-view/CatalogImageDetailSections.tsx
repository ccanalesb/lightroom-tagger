import type { ImageView } from '../../services/api'
import { AIDescriptionSection } from '../DescriptionPanel'
import { Badge } from '../ui/Badge'
import { MetadataRow } from '../ui/MetadataRow'
import { DATE_NO_DATE, LABEL_DATE, LABEL_FILENAME } from '../../constants/strings'

interface CatalogImageDetailSectionsProps {
  image: ImageView
  /** Called when the caller should re-fetch detail (after description
   *  jobs complete) so the modal header / breakdown stay in sync. */
  onDataChanged?: () => void
}

/**
 * Catalog-specific body sections for the consolidated ImageDetailModal.
 * Per-perspective scoring lives inside the AI description (see
 * `AIDescriptionSection` → `DescriptionPanel` → perspectives). The
 * legacy standalone critique-scores panel was removed to avoid
 * duplicate per-perspective data in the modal.
 */
export function CatalogImageDetailSections({
  image,
  onDataChanged,
}: CatalogImageDetailSectionsProps) {
  const dateDisplay = image.date_taken
    ? new Date(image.date_taken).toLocaleString()
    : DATE_NO_DATE
  const keywords = Array.isArray(image.keywords) ? image.keywords : []

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <MetadataRow label={LABEL_FILENAME} value={image.filename ?? image.key} />
        {image.title ? <MetadataRow label="Title" value={image.title} /> : null}
        <MetadataRow label={LABEL_DATE} value={dateDisplay} />
        {image.filepath ? <MetadataRow label="Path" value={image.filepath} mono /> : null}
        {image.width && image.height ? (
          <MetadataRow
            label="Dimensions"
            value={`${image.width} × ${image.height}`}
          />
        ) : null}
      </div>

      {image.caption ? (
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">Caption</h3>
          <p className="text-sm text-text-secondary">{image.caption}</p>
        </div>
      ) : null}

      {keywords.length > 0 ? (
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">Keywords</h3>
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
        onDataChanged={onDataChanged}
      />
    </div>
  )
}
