import { useCallback, useEffect, useState } from 'react'
import type { Job } from '../types/job'
import { JobsAPI } from '../services/api'
import { useJobSocket } from '../hooks/useJobSocket'
import { JobDetailModal } from '../components/jobs/JobDetailModal'
import { PageLoading, PageError, EmptyState } from '../components/ui/page-states'
import { StatusBadge } from '../components/ui/badges'
import { formatDateTime } from '../utils/date'
import {
  MSG_CONNECTED,
  MSG_DISCONNECTED,
  MSG_NO_JOBS,
  ACTION_CANCEL,
  ACTION_CANCELLING,
} from '../constants/strings'

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [cancellingId, setCancellingId] = useState<string | null>(null)

  const cancelJob = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setCancellingId(jobId)
    try {
      await JobsAPI.cancel(jobId)
      setJobs(prev => prev.map(job =>
        job.id === jobId ? { ...job, status: 'cancelled' as const } : job
      ))
    } catch (err) {
      alert(`Failed to cancel job: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setCancellingId(null)
    }
  }

  useEffect(() => {
    let mounted = true

    async function fetchJobs() {
      try {
        const fetchedJobs = await JobsAPI.list()
        if (mounted) {
          setJobs(fetchedJobs)
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Unknown error')
        }
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    fetchJobs()
    return () => { mounted = false }
  }, [])

  const handleJobCreated = useCallback((job: Job) => {
    setJobs(prev => [job, ...prev])
  }, [])

  const handleJobUpdated = useCallback((updatedJob: Job) => {
    setJobs(prev => prev.map(job =>
      job.id === updatedJob.id ? updatedJob : job
    ))
  }, [])

  const { connected } = useJobSocket({
    onJobCreated: handleJobCreated,
    onJobUpdated: handleJobUpdated,
  })

  if (loading) return <PageLoading />
  if (error) return <PageError message={error} />

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">Jobs</h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-600">
            {connected ? MSG_CONNECTED : MSG_DISCONNECTED}
          </span>
        </div>
      </div>

      {jobs.length === 0 ? (
        <EmptyState message={MSG_NO_JOBS} />
      ) : (
        <div className="space-y-4">
          {jobs.map(job => (
            <div
              key={job.id}
              className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => setSelectedJob(job)}
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{job.type}</h3>
                  <p className="text-sm text-gray-500">{job.id.slice(0, 8)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={job.status} />
                  {(job.status === 'pending' || job.status === 'running') && (
                    <button
                      onClick={(e) => cancelJob(job.id, e)}
                      disabled={cancellingId === job.id}
                      className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                    >
                      {cancellingId === job.id ? ACTION_CANCELLING : ACTION_CANCEL}
                    </button>
                  )}
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {formatDateTime(job.created_at)}
              </p>
            </div>
          ))}
        </div>
      )}

      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onJobUpdate={(updatedJob) => {
            setJobs(prev => prev.map(job =>
              job.id === updatedJob.id ? updatedJob : job
            ))
          }}
        />
      )}
    </div>
  )
}
