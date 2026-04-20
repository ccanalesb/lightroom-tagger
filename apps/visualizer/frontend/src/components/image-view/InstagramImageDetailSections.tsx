import { useState } from 'react'
import type { ImageView } from '../../services/api'
import { MetadataRow } from '../ui/MetadataRow'
import { useMatchOptions } from '../../stores/matchOptionsContext'
import { useSingleMatch } from '../../hooks/useSingleMatch'
import { MatchStatusDisplay } from '../instagram/MatchStatusDisplay'
import { MatchAdvancedOptions } from '../instagram/MatchAdvancedOptions'
import {
  DATE_ESTIMATED_SUFFIX,
  DATE_NO_DATE,
  IMAGE_DETAILS_AI_DESCRIPTION,
  LABEL_CATALOG_MATCH,
  LABEL_DATE,
  LABEL_FILENAME,
  LABEL_FOLDER,
  LABEL_IMAGE_HASH_DISPLAY,
  LABEL_SOURCE,
} from '../../constants/strings'

interface InstagramImageDetailSectionsProps {
  image: ImageView
  onDataChanged?: () => void
}

/**
 * Instagram-specific body sections. Extracted near-verbatim from the
 * legacy `ImageDetailsModal`; the shell owns chrome / header badges.
 *
 * Requires `MatchOptionsProvider` in the tree (same as the legacy modal
 * — the single-match flow reads its options from that context).
 */
export function InstagramImageDetailSections({
  image,
  onDataChanged,
}: InstagramImageDetailSectionsProps) {
  const { options, updateOption, weightsError } = useMatchOptions()
  const { matchState, matchJob, matchResult, matchError, startSingleMatch, resetMatch } =
    useSingleMatch(image.key)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleStartMatch = () => {
    startSingleMatch(image.key)
    onDataChanged?.()
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <MatchStatusDisplay
          state={matchState}
          job={matchJob}
          result={matchResult}
          error={matchError}
          disabled={!options.providerId || weightsError !== null}
          onStart={handleStartMatch}
          onReset={resetMatch}
        />
        <MatchAdvancedOptions
          isOpen={showAdvanced}
          onToggle={() => setShowAdvanced((v) => !v)}
          providerId={options.providerId}
          providerModel={options.providerModel}
          onProviderChange={(providerId, modelId) => {
            updateOption('providerId', providerId)
            updateOption('providerModel', modelId)
          }}
          threshold={options.threshold}
          onThresholdChange={(val) => updateOption('threshold', val)}
          phashWeight={options.phashWeight}
          onPhashWeightChange={(val) => updateOption('phashWeight', val)}
          descWeight={options.descWeight}
          onDescWeightChange={(val) => updateOption('descWeight', val)}
          visionWeight={options.visionWeight}
          onVisionWeightChange={(val) => updateOption('visionWeight', val)}
          weightsError={weightsError}
        />
      </div>

      <div className="space-y-3 pt-4 border-t border-border">
        <MetadataRow label={LABEL_FILENAME} value={image.filename ?? image.key} />
        {image.instagram_folder ? (
          <MetadataRow label={LABEL_FOLDER} value={image.instagram_folder} />
        ) : null}
        {image.source_folder ? (
          <MetadataRow label={LABEL_SOURCE} value={image.source_folder} />
        ) : null}
        <MetadataRow label={LABEL_DATE} value={formatDate(image)} />
        {image.image_hash ? (
          <MetadataRow label={LABEL_IMAGE_HASH_DISPLAY} value={image.image_hash} mono />
        ) : null}
        {image.matched_catalog_key ? (
          <MetadataRow
            label={LABEL_CATALOG_MATCH}
            value={image.matched_catalog_key}
            mono
          />
        ) : null}
      </div>

      {image.description_summary ? (
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">
            {IMAGE_DETAILS_AI_DESCRIPTION}
          </h3>
          <p className="text-sm text-text-secondary">{image.description_summary}</p>
        </div>
      ) : null}

      {image.caption ? (
        <div className="p-4 bg-surface rounded-base border border-border">
          <h3 className="text-sm font-medium text-text mb-2">Instagram Caption</h3>
          <p className="text-sm text-text-secondary">{image.caption}</p>
        </div>
      ) : null}
    </div>
  )
}

function formatDate(image: ImageView): string {
  if (image.created_at) return new Date(image.created_at).toLocaleString()
  if (image.date_folder) {
    return `${image.date_folder.slice(0, 4)}/${image.date_folder.slice(4, 6)} ${DATE_ESTIMATED_SUFFIX}`
  }
  return DATE_NO_DATE
}
