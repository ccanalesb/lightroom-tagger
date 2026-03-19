//App
export const APP_TITLE = 'Lightroom Tagger'

// Navigation
export const NAV_DASHBOARD = 'Dashboard'
export const NAV_INSTAGRAM = 'Instagram'
export const NAV_MATCHING = 'Matching'
export const NAV_JOBS = 'Jobs'

// Status
export const STATUS_PENDING = 'pending'
export const STATUS_RUNNING = 'running'
export const STATUS_COMPLETED = 'completed'
export const STATUS_FAILED = 'failed'
export const STATUS_CANCELLED = 'cancelled'

// Status Display
export const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

// Messages
export const MSG_LOADING = 'Loading...'
export const MSG_NO_JOBS = 'No jobs found. Start a job to see it here.'
export const MSG_CONNECTED = 'Connected'
export const MSG_DISCONNECTED = 'Disconnected'
export const MSG_ERROR_PREFIX = 'Error:'

// API
export const API_DEFAULT_URL = 'http://localhost:5000/api'
export const WS_DEFAULT_URL = 'http://localhost:5000'