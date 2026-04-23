import { useCallback, useEffect, useState } from 'react'
import { invalidate, invalidateAll, patchMatching } from '../data'
import { useSocketStore } from '../stores/socketStore'
import type { Job } from '../types/job'

interface UseJobSocketOptions {
  onJobCreated?: (job: Job) => void
  onJobUpdated?: (job: Job) => void
  onJobsRecovered?: (payload: { job_ids: string[] }) => void
}

export function useJobSocket({
  onJobCreated,
  onJobUpdated,
  onJobsRecovered,
}: UseJobSocketOptions = {}) {
  const socket = useSocketStore((s) => s.socket)
  const connected = useSocketStore((s) => s.connected)
  const connect = useSocketStore((s) => s.connect)
  const [jobListRevision, setJobListRevision] = useState(0)

  const refreshJobList = useCallback(() => {
    invalidateAll(['jobs.list'])
    setJobListRevision((n) => n + 1)
  }, [])

  useEffect(() => {
    connect()
  }, [connect])

  useEffect(() => {
    if (!socket || !connected) return

    const handleJobCreated = (job: Job) => {
      invalidateAll(['jobs.list'])
      setJobListRevision((n) => n + 1)
      onJobCreated?.(job)
    }

    const handleJobUpdated = (job: Job) => {
      const jobsListPrefix = JSON.stringify(['jobs.list']).slice(0, -1)
      if (job.status === 'running' || job.status === 'pending') {
        // Progress update only — patch in-place so useQuery returns cached
        // data immediately (no fetch, no Suspense flash).
        patchMatching(
          (k) => k.startsWith(jobsListPrefix),
          (value) => {
            const resp = value as { data?: Job[] }
            if (!resp?.data) return value
            return { ...resp, data: resp.data.map((j) => (j.id === job.id ? job : j)) }
          },
        )
      } else {
        // Terminal state (completed/failed/cancelled) — need fresh list from server.
        invalidateAll(['jobs.list'])
      }
      invalidate(['jobs.detail', job.id])
      setJobListRevision((n) => n + 1)
      onJobUpdated?.(job)
    }

    const handleJobsRecovered = (payload: { job_ids: string[] }) => {
      invalidateAll(['jobs.list'])
      setJobListRevision((n) => n + 1)
      onJobsRecovered?.(payload)
    }

    socket.on('job_created', handleJobCreated)
    socket.on('job_updated', handleJobUpdated)
    if (onJobsRecovered) socket.on('jobs_recovered', handleJobsRecovered)

    return () => {
      socket.off('job_created', handleJobCreated)
      socket.off('job_updated', handleJobUpdated)
      if (onJobsRecovered) socket.off('jobs_recovered', handleJobsRecovered)
    }
  }, [socket, connected, onJobCreated, onJobUpdated, onJobsRecovered])

  return { connected, socket, jobListRevision, refreshJobList }
}
