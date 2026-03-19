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
  result: any | null
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  metadata: Record<string, any>
}