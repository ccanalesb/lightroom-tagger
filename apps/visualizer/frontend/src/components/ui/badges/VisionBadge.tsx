/**
 * Compact label for vision comparison outcomes (same / different / uncertain) on
 * match views and image metadata. Uses shared `Badge` tokens for consistent hue
 * with the rest of the UI.
 */
import { Badge } from './Badge'

function visionVariant(result: string | undefined): 'success' | 'error' | 'warning' {
  if (result === 'SAME') return 'success'
  if (result === 'DIFFERENT') return 'error'
  return 'warning'
}

export function VisionBadge({ result }: { result: string | undefined }) {
  const display = result ?? 'UNCERTAIN'
  return <Badge variant={visionVariant(result)}>{display}</Badge>
}
