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

// Messages
export const MSG_NO_EXIF_DATA = 'No EXIF data available'
export const MSG_CLICK_FOR_DETAILS = 'Click for details'
export const MSG_PAGE_OF = 'Page {current} of {total}'
export const MSG_SHOWING_RANGE = 'Showing {start}-{end} of {total}'

// Modal
export const MODAL_TITLE_IMAGE_DETAILS = 'Image Details'
export const MODAL_CLOSE = 'Close'
export const MODAL_VIEW_ON_INSTAGRAM = 'View on Instagram'
export const MODAL_OPEN_LOCAL_FILE = 'Open Local File'

// Metadata Sections
export const META_SECTION_BASIC_INFO = 'Basic Information'
export const META_SECTION_IMAGE_ANALYSIS = 'Image Analysis'
export const META_SECTION_EXIF_DATA = 'EXIF Data'
export const META_SECTION_CAPTION = 'Caption'
export const META_SECTION_FILE_LOCATION = 'File Location'

// Metadata Labels
export const LABEL_FILENAME = 'Filename'
export const LABEL_MEDIA_KEY = 'Media Key'
export const LABEL_SOURCE_FOLDER = 'Source Folder'
export const LABEL_DATE_FOLDER = 'Date Folder'
export const LABEL_ADDED = 'Added'
export const LABEL_VISUAL_HASH = 'Visual Hash (pHash)'
export const LABEL_GPS_COORDINATES = 'GPS Coordinates'
export const LABEL_DATE_TAKEN = 'Date Taken'
export const LABEL_CAMERA = 'Camera'
export const LABEL_LENS = 'Lens'
export const LABEL_ISO = 'ISO'
export const LABEL_APERTURE = 'Aperture'
export const LABEL_SHUTTER_SPEED = 'Shutter Speed'

// Hash explanation
export const HASH_EXPLANATION = 'This hash is used to detect visually identical images across your collection.'

// Pagination
export const PAGINATION_PREVIOUS = '← Previous'
export const PAGINATION_NEXT = 'Next →'

// Filters
export const FILTER_ALL_DATES = 'All dates'
export const FILTER_CLEAR = 'Clear'

// Config
export const ITEMS_PER_PAGE = 48

// Job Details Modal
export const JOB_DETAILS_TITLE = 'Job Details'
export const JOB_DETAILS_PROGRESS = 'Progress'
export const JOB_DETAILS_CURRENT_STEP = 'Current Step'
export const JOB_DETAILS_METADATA = 'Metadata'
export const JOB_DETAILS_RESULT = 'Result'
export const JOB_DETAILS_ERROR = 'Error'
export const JOB_DETAILS_LOGS = 'Logs'

// Job Actions
export const ACTION_CANCEL = 'Cancel'
export const ACTION_CANCELLING = 'Cancelling...'

// Job Configuration Display
export const JOB_CONFIG_METHOD = 'Matching Method'
export const JOB_CONFIG_DATE_WINDOW = 'Date Window'
export const JOB_CONFIG_VISION_MODEL = 'Vision Model'
export const JOB_CONFIG_THRESHOLD = 'Match Threshold'
export const JOB_CONFIG_WEIGHTS = 'Scoring Weights'

// Matching Page Advanced Options
export const ADVANCED_OPTIONS_TITLE = 'Advanced Options'
export const ADVANCED_DATE_FILTER = 'Date filter'
export const ADVANCED_DATE_ALL = 'All time'
export const ADVANCED_DATE_3MONTHS = 'Last 3 months'
export const ADVANCED_DATE_6MONTHS = 'Last 6 months'
export const ADVANCED_DATE_YEAR_2026 = '2026 only'

export const ADVANCED_MODEL_LABEL = 'Vision Model'
export const ADVANCED_MODEL_DESCRIPTION = 'Model used for vision comparison'

export const ADVANCED_THRESHOLD_LABEL = 'Match Threshold'
export const ADVANCED_THRESHOLD_MIN = '0.50 (lenient)'
export const ADVANCED_THRESHOLD_MAX = '0.95 (strict)'
export const ADVANCED_THRESHOLD_DESCRIPTION = 'Minimum score required for a match (default: 0.70)'

export const ADVANCED_WEIGHTS_TITLE = 'Matching Weights'
export const ADVANCED_WEIGHTS_MUST_SUM = 'Weights must sum to 100%'
export const ADVANCED_WEIGHTS_CURRENT = 'currently'
export const ADVANCED_WEIGHTS_TOTAL = 'Total'

export const ADVANCED_WEIGHT_PHASH = 'Perceptual Hash (pHash)'
export const ADVANCED_WEIGHT_DESC = 'Description Similarity'
export const ADVANCED_WEIGHT_VISION = 'Vision Model'

export const ADVANCED_RESET_DEFAULTS = 'Reset to defaults'
export const ADVANCED_START = 'Start'
export const ADVANCED_STARTING = 'Starting...'

// Matching Status
export const MATCHING_IN_PROGRESS = 'Matching in progress...'
export const MATCHING_WAITING = 'Waiting to start'
export const MATCHING_PERCENT_COMPLETE = '% complete'
export const MATCHING_PROCESSING = 'Processing...'
export const MATCHING_VIEW_DETAILS = 'View Details'
export const MATCHING_COMPLETED = 'Matching completed!'
export const MATCHING_COMPLETED_MATCHES = 'matches found'
export const MATCHING_FAILED = 'Matching failed'
export const MATCHING_FAILED_UNKNOWN = 'Unknown error'
export const MATCHING_DISMISS = 'Dismiss'

// Match Card
export const MATCH_CARD_IG_LABEL = 'IG'
export const MATCH_CARD_CATALOG_LABEL = 'Cat'
export const MATCH_CARD_NO_IMAGE = 'No image'

// Cache Status
export const CACHE_TITLE = 'Vision Cache'
export const CACHE_PREPARE_BUTTON = 'Prepare Catalog'
export const CACHE_PREPARING = 'Preparing...'
export const CACHE_STATUS_LOADING = 'Loading cache status...'
export const CACHE_STATUS_CACHED = 'cached'
export const CACHE_STATUS_OF = 'of'
export const CACHE_STATUS_IMAGES = 'images'
export const CACHE_SIZE_LABEL = 'Cache size'
export const CACHE_REFRESH_BUTTON = 'Refresh'
export const CACHE_JOB_RUNNING = 'Cache preparation in progress...'
export const CACHE_JOB_COMPLETED = 'Cache preparation completed!'
export const CACHE_WARNING_NOT_READY = 'Catalog not fully cached. Matching may be slower.'

// Description Panel
export const DESC_PANEL_TITLE = 'AI Description'
export const DESC_PANEL_SUMMARY = 'Summary'
export const DESC_PANEL_COMPOSITION = 'Composition'
export const DESC_PANEL_PERSPECTIVES = 'Perspectives'
export const DESC_PANEL_TECHNICAL = 'Technical'
export const DESC_PANEL_SUBJECTS = 'Subjects'
export const DESC_PANEL_MODEL = 'Model'
export const DESC_PANEL_NO_DESCRIPTION = 'No AI description available'
export const DESC_PERSPECTIVE_STREET = 'Street'
export const DESC_PERSPECTIVE_DOCUMENTARY = 'Documentary'
export const DESC_PERSPECTIVE_PUBLISHER = 'Publisher'
export const DESC_BEST_FIT = 'Best fit'