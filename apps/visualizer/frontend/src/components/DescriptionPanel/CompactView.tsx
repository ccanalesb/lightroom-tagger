import type { ImageDescription } from '../../services/api'

interface CompactViewProps {
  description: ImageDescription
}

export function CompactView({ description }: CompactViewProps) {
  return (
    <div className="space-y-1">
      {description.summary && (
        <p className="text-xs text-gray-600 line-clamp-2">{description.summary}</p>
      )}
    </div>
  )
}
