import type { Job } from '../../types/job'
import { ERROR_SEVERITY_LABELS } from '../../constants/strings'
import { formatDateTime } from '../../utils/date'
import { Badge, StatusBadge } from '../ui/badges'
import { Card } from '../ui/Card/Card'

interface JobCardProps {
  job: Job
  onClick?: () => void
}

export function JobCard({ job, onClick }: JobCardProps) {
  return (
    <Card onClick={onClick}>
      <div className="flex justify-between items-start mb-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-text truncate">{job.type}</h3>
          <p className="text-sm text-text-tertiary tabular-nums">{job.id.slice(0, 8)}</p>
        </div>
        <div className="flex flex-row items-center gap-2 shrink-0">
          <StatusBadge status={job.status} />
          {job.status === 'failed' &&
            (job.error_severity === 'warning' ||
              job.error_severity === 'error' ||
              job.error_severity === 'critical') && (
              <Badge
                variant={job.error_severity === 'warning' ? 'warning' : 'error'}
                className={job.error_severity === 'critical' ? 'ring-2 ring-error' : ''}
              >
                {ERROR_SEVERITY_LABELS[job.error_severity]}
              </Badge>
            )}
        </div>
      </div>

      {job.status === 'running' && (
        <div className="mt-2">
          <div className="flex justify-between text-sm mb-1 text-text-secondary">
            <span>{job.current_step || 'Processing...'}</span>
            <span className="tabular-nums">{job.progress}%</span>
          </div>
          <div className="w-full bg-border rounded-full h-2 overflow-hidden">
            <div
              className="bg-accent h-2 rounded-full transition-[width] duration-200"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      <div className="mt-2 text-xs text-text-tertiary">
        {formatDateTime(job.created_at)}
      </div>
    </Card>
  )
}
