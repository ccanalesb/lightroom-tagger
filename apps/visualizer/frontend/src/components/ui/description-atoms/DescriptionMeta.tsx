import {
  DESC_PAGE_SOURCE_CATALOG,
  DESC_PAGE_SOURCE_INSTAGRAM,
} from '../../../constants/strings'
import { formatDate } from '../../../utils/date'

interface DescriptionMetaProps {
  model?: string
  describedAt?: string
  imageType?: 'catalog' | 'instagram'
  hasDescription?: boolean
  bestPerspective?: string
  dateRef?: string
}

export function DescriptionMeta({ model, describedAt, imageType, hasDescription, bestPerspective, dateRef }: DescriptionMetaProps) {
  const parts: React.ReactNode[] = []

  if (bestPerspective) {
    parts.push(
      <span key="persp" className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 font-medium">
        {bestPerspective}
      </span>
    )
  }

  if (hasDescription && imageType) {
    parts.push(
      <span key="src" className="text-gray-500">
        {imageType === 'catalog' ? DESC_PAGE_SOURCE_CATALOG : DESC_PAGE_SOURCE_INSTAGRAM}
      </span>
    )
  }

  if (model) {
    parts.push(<span key="model">model: {model}</span>)
  }

  if (describedAt) {
    parts.push(<span key="date">{formatDate(describedAt)}</span>)
  }

  if (dateRef) {
    parts.push(<span key="ref" className="ml-auto">{dateRef}</span>)
  }

  if (parts.length === 0) return null

  return (
    <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
      {parts}
    </div>
  )
}
