import { Job } from '../types/job'
import { STATUS_LABELS } from '../constants/strings'

interface JobCardProps {
  job: Job
  onClick?: () => void
}

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
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
        <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[job.status]}`}>
          {STATUS_LABELS[job.status]}
        </span>
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
        {new Date(job.created_at).toLocaleString()}
      </div>
    </div>
  )
}