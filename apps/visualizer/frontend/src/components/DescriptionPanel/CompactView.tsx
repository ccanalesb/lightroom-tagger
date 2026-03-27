import type { ImageDescription } from '../../services/api'
import { DESC_BEST_FIT } from '../../constants/strings'
import { descriptionScoreColor } from '../../utils/descriptionScoreColor'
import { DESCRIPTION_PERSPECTIVE_LABELS } from './perspectiveLabels'

interface CompactViewProps {
  description: ImageDescription
}

export function CompactView({ description }: CompactViewProps) {
  const best = description.best_perspective
  const perspective = best ? description.perspectives[best as keyof typeof description.perspectives] : null

  return (
    <div className="space-y-1">
      {description.summary && (
        <p className="text-xs text-gray-600 line-clamp-2">{description.summary}</p>
      )}
      {best && perspective && (
        <div className="flex items-center gap-1.5">
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${descriptionScoreColor(perspective.score)}`}>
            {DESCRIPTION_PERSPECTIVE_LABELS[best] || best} {perspective.score}/10
          </span>
          <span className="text-[10px] text-gray-400">{DESC_BEST_FIT}</span>
        </div>
      )}
    </div>
  )
}
