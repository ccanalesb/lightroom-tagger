import { useState, useCallback } from 'react'
import { JobsAPI } from '../services/api'
import type { Job } from '../types/job'

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled'])

export function useBatchJob() {
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isRunning = job !== null && !TERMINAL_STATUSES.has(job.status)

  const start = useCallback(async (type: string, metadata: Record<string, unknown>) => {
    setError(null)
    try {
      const created = await JobsAPI.create(type, metadata)
      setJob(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }, [])

  const onJobUpdate = useCallback((updated: Job) => {
    setJob((prev) => {
      if (!prev || prev.id !== updated.id) return prev
      return updated
    })
  }, [])

  const dismiss = useCallback(() => {
    setJob(null)
    setError(null)
  }, [])

  return { job, error, isRunning, start, onJobUpdate, dismiss }
}
