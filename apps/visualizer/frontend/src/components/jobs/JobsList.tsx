import type { Job } from '../../types/job'
import { JobCard } from './JobCard'
import { EmptyState } from '../ui/page-states/EmptyState'
import { MSG_NO_JOBS } from '../../constants/strings'

interface JobsListProps {
  jobs: Job[]
  onJobClick?: (job: Job) => void
}

export function JobsList({ jobs, onJobClick }: JobsListProps) {
  if (jobs.length === 0) {
    return <EmptyState message={MSG_NO_JOBS} />
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {jobs.map(job => (
        <JobCard
          key={job.id}
          job={job}
          onClick={() => onJobClick?.(job)}
        />
      ))}
    </div>
  )
}
