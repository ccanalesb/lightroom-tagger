import type { ImageDescription } from '../../services/api'
import { DESC_PANEL_NO_DESCRIPTION } from '../../constants/strings'
import { CompactView } from './CompactView'
import { FullView } from './FullView'

interface DescriptionPanelProps {
  description: ImageDescription | null | undefined
  compact?: boolean
}

export function DescriptionPanel({ description, compact }: DescriptionPanelProps) {
  if (!description) {
    return (
      <p className="text-xs text-gray-400 italic">{DESC_PANEL_NO_DESCRIPTION}</p>
    )
  }

  if (compact) {
    return <CompactView description={description} />
  }

  return <FullView description={description} />
}
