// App
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
export const MSG_NO_IMAGES = 'No images found.'
export const MSG_NO_MATCHES = 'No matches found. Run vision matching first.'
export const MSG_CONNECTED = 'Connected'
export const MSG_DISCONNECTED = 'Disconnected'
export const MSG_ERROR_PREFIX = 'Error:'

// Dashboard
export const DASHBOARD_CATALOG_IMAGES = 'Catalog Images'
export const DASHBOARD_INSTAGRAM_IMAGES = 'Instagram Images'
export const DASHBOARD_POSTED = 'Posted to Instagram'
export const DASHBOARD_MATCHES = 'Matches Found'
export const DASHBOARD_RECENT_JOBS = 'Recent Jobs'
export const DASHBOARD_NO_JOBS = 'No recent jobs'
export const DASHBOARD_START_JOB = 'Start a Job'

// Instagram Page
export const INSTAGRAM_DOWNLOADED = 'Downloaded Instagram Images'
export const INSTAGRAM_POST_URL = 'Post URL'
export const INSTAGRAM_FILE = 'File'
export const INSTAGRAM_CRAWLED = 'Crawled'

// Matching Page
export const MATCHING_RESULTS = 'Matching Results'
export const MATCHING_RUN = 'Run Vision Matching'
export const MATCHING_RUNNING = 'Running matching...'
export const MATCHING_SUCCESS = 'Matching completed successfully'

// Actions
export const ACTION_REFRESH = 'Refresh'
export const ACTION_VIEW = 'View'
export const ACTION_RUN_MATCHING = 'Run Matching'

// API
export const API_DEFAULT_URL = '/api'
export const WS_DEFAULT_URL = ''