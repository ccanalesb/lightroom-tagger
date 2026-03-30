import { STATUS_LABELS } from '../../../constants/strings'
import { statusBadgeClasses } from '../../../utils/jobStatus'

export function StatusBadge({ status, withBorder }: { status: string; withBorder?: boolean }) {
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${statusBadgeClasses(status, { withBorder })}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}
