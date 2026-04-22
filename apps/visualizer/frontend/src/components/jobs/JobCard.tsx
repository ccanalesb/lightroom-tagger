import type { Job } from '../../types/job'
import { ERROR_SEVERITY_LABELS } from '../../constants/strings'
import { formatDateTime } from '../../utils/date'
import { Badge } from '../ui/badges'
import { StatusBadge } from '../ui/badges'

interface JobCardProps {
  job: Job
  onClick?: () => void
}

export function JobCard({ job, onClick }: JobCardProps) {
  return (
    <div
      onClick={onClick}
      className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="font-semibold">{job.type}</h3>
          <p className="text-sm text-gray-500">{job.id.slice(0, 8)}</p>
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
          <div className="flex justify-between text-sm mb-1">
            <span>{job.current_step || 'Processing...'}</span>
            <span>{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      <div className="mt-2 text-xs text-gray-500">
        {formatDateTime(job.created_at)}
      </div>
    </div>
  )
}
