/**
 * Perspective dimension score chip (e.g. street, documentary) for breakdown
 * panels and score rows. Color-codes known perspective slugs; unknown slugs use
 * the neutral badge style.
 */
import { Badge } from './Badge'

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'accent'

const STREET =
  '!bg-violet-50 dark:!bg-violet-900/20 !text-violet-900 dark:!text-violet-100 !border-violet-200 dark:!border-violet-800'

const DOCUMENTARY =
  '!bg-amber-50 dark:!bg-amber-900/20 !text-amber-900 dark:!text-amber-100 !border-amber-200 dark:!border-amber-800'

const PUBLISHER =
  '!bg-rose-50 dark:!bg-rose-900/20 !text-rose-900 dark:!text-rose-100 !border-rose-200 dark:!border-rose-800'

const COLOR_THEORY =
  '!bg-emerald-50 dark:!bg-emerald-900/20 !text-emerald-900 dark:!text-emerald-100 !border-emerald-200 dark:!border-emerald-800'

function labelFromSlug(normalized: string): string {
  return normalized
    .split('_')
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : w))
    .join(' ')
}

export function PerspectiveBadge({
  perspectiveSlug,
  score,
  displayName,
  className = '',
}: {
  perspectiveSlug: string
  score: number
  displayName?: string
  className?: string
}) {
  const normalized = perspectiveSlug.toLowerCase().replace(/-/g, '_')
  let mappedVariant: BadgeVariant = 'default'
  let colorClass = ''

  switch (normalized) {
    case 'street':
      colorClass = STREET
      break
    case 'documentary':
      colorClass = DOCUMENTARY
      break
    case 'publisher':
      colorClass = PUBLISHER
      break
    case 'color_theory':
      colorClass = COLOR_THEORY
      break
    default:
      break
  }

  const label = displayName ?? labelFromSlug(normalized)
  const scoreStr = score.toFixed(score % 1 === 0 ? 0 : 1)
  const extra = [colorClass, className].filter(Boolean).join(' ')

  return (
    <Badge variant={mappedVariant} className={extra}>
      {label} {scoreStr}
    </Badge>
  )
}
