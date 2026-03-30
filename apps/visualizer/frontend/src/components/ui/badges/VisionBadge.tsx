import { visionBadgeClasses } from '../../../utils/visionBadge'

export function VisionBadge({ result }: { result: string | undefined }) {
  const display = result ?? 'UNCERTAIN'
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${visionBadgeClasses(result)}`}>
      {display}
    </span>
  )
}
