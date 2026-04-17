export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface JobLog {
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
}

export interface Job {
  id: string
  type: string
  status: JobStatus
  progress: number
  current_step: string | null
  logs: JobLog[]
  logs_total?: number
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result: any | null
  error: string | null
  error_severity?: 'warning' | 'error' | 'critical' | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata: Record<string, any>
}