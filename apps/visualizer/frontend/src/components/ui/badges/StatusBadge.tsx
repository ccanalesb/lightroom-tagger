/**
 * Human-readable job or task status (completed, running, failed, etc.) on job
 * cards, queues, and modals. Maps backend status strings to semantic `Badge`
 * variants.
 */
import { Badge } from './Badge'
import { STATUS_LABELS } from '../../../constants/strings'

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'accent'

function statusVariant(status: string): BadgeVariant {
  switch (status) {
    case 'completed':
      return 'success'
    case 'failed':
      return 'error'
    case 'running':
      return 'accent'
    case 'cancelled':
      return 'default'
    default:
      return 'warning'
  }
}

export function StatusBadge({ status, withBorder }: { status: string; withBorder?: boolean }) {
  const borderClass = withBorder ? 'border-2' : ''
  return (
    <Badge variant={statusVariant(status)} className={borderClass}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  )
}
