// App
export const APP_TITLE = 'Lightroom Tagger'

// Navigation
export const NAV_INSIGHTS = 'Insights'
export const NAV_INSTAGRAM = 'Instagram'
export const NAV_MATCHING = 'Matching'
export const NAV_DESCRIPTIONS = 'Descriptions'
export const NAV_JOBS = 'Jobs'
export const NAV_IMAGES = 'Images'
export const NAV_CATALOG = 'Catalog'
export const NAV_MATCHES = 'Matches'
export const NAV_PROCESSING = 'Processing'
export const NAV_ANALYTICS = 'Analytics'
export const NAV_IDENTITY = 'Identity'
export const NAV_JOB_QUEUE = 'Job Queue'

// Tab labels
export const TAB_INSTAGRAM = 'Instagram'
export const TAB_CATALOG = 'Catalog'
export const TAB_MATCHES = 'Matches'
export const MATCHES_TAB_EMPTY =
  'No proposed matches yet. Run vision matching from Processing.'
export const TAB_VISION_MATCHING = 'Vision Matching'
export const TAB_DESCRIPTIONS = 'Descriptions'
export const TAB_ANALYZE = 'Analyze'
export const TAB_PERSPECTIVES = 'Perspectives'
export const TAB_CATALOG_CACHE = 'Catalog Cache'
export const TAB_JOB_QUEUE = 'Job Queue'
export const TAB_PROVIDERS = 'Providers'
export const TAB_SETTINGS = 'Settings'

/** Processing — Perspectives tab subtitle (D-10 / SCORE-06). */
export const NAV_PERSPECTIVES_HELP =
  'Edit critique rubrics in the library database. Reset reloads the markdown file from prompts/perspectives for the selected slug.'

// Placeholders
export const PLACEHOLDER_COMING_SOON = 'Coming soon...'
export const PLACEHOLDER_CATALOG_VIEW = 'Catalog image view coming soon'
export const PLACEHOLDER_MATCHES_VIEW = 'Matches view coming soon'

// Badge labels (for variant prop values, not display strings)
export const BADGE_MATCHED = 'Matched'
export const BADGE_DESCRIBED = 'Described'
export const BADGE_PROCESSED = 'Processed'

// Date display
export const DATE_NO_DATE = 'No date'
export const DATE_ESTIMATED_SUFFIX = '(est.)'

// Image details
export const IMAGE_DETAILS_TITLE = 'Image Details'
export const IMAGE_DETAILS_AI_DESCRIPTION = 'AI Description'

// Catalog image modal — critique scores (phase 06-03)
export const SECTION_IMAGE_SCORES = 'Critique scores'
export const ACTION_RUN_SCORING = 'Run scoring'
export const SCORES_LOADING = 'Loading scores…'
export const ACTION_SCORING_IN_PROGRESS = 'Scoring…'
export const LABEL_SCORES_PERSPECTIVES = 'Perspectives'
export const SCORES_LOADING_PERSPECTIVES = 'Loading perspectives…'
export const SCORES_FORCE_SAME_RUBRIC = 'Force re-score same rubric revision'
export const SCORES_EMPTY_HINT =
  'No critique scores for this image yet. Run scoring from the button below or use Processing → Descriptions to batch score.'
export const SCORES_VERSION_HISTORY = 'Version history'
export const SCORES_LOADING_HISTORY = 'Loading history…'
export const SCORES_NO_PRIOR_VERSIONS = 'No prior versions.'
export const SCORES_OUTPUT_REPAIRED = 'Output was repaired before save'
export const SCORES_NO_ACTIVE_PERSPECTIVES =
  'No active perspectives to score. Add perspectives in Processing.'
export const SCORES_FAILED_GENERIC = 'Scoring failed'
export const LABEL_FOLDER = 'Folder'
export const LABEL_SOURCE = 'Source'
export const LABEL_DATE = 'Date'
export const LABEL_IMAGE_HASH_DISPLAY = 'Image Hash'
export const LABEL_CATALOG_MATCH = 'Catalog Match'

// Status Display
export const STATUS_LABELS: Record<string, string> = {
  pending: 'Queued',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

export const ERROR_SEVERITY_LABELS: Record<string, string> = {
  warning: 'Warning',
  error: 'Error',
  critical: 'Critical',
}

// Generic Messages
export const MSG_LOADING = 'Loading...'
export const MSG_UNKNOWN_ERROR = 'Unknown error'
export const MSG_NO_JOBS = 'No jobs found. Start a job to see it here.'
export const MSG_NO_MATCHES = 'No matches found. Run vision matching first.'
export const MSG_CONNECTED = 'Connected'
export const MSG_DISCONNECTED = 'Disconnected'
export const MSG_ERROR_PREFIX = 'Error:'

// Generic Labels
export const LABEL_ID = 'ID:'
export const LABEL_TYPE = 'Type:'
export const LABEL_STATUS = 'Status:'
export const LABEL_CREATED = 'Created:'
export const LABEL_CONFIGURATION = 'Configuration'
export const LABEL_IMAGES = 'images'
export const LABEL_MATCHES = 'matches'
export const LABEL_DAYS = 'days'
export const LABEL_MB = 'MB'
export const LABEL_CACHED = 'cached'
export const LABEL_MODEL = 'model:'
export const LABEL_SCORE = 'score:'

// Dashboard / Insights home (KPI labels shared with legacy dashboard copy)
export const DASHBOARD_CATALOG_IMAGES = 'Catalog Images'
export const DASHBOARD_INSTAGRAM_IMAGES = 'Instagram Images'
export const DASHBOARD_POSTED = 'Posted to Instagram'
export const DASHBOARD_MATCHES = 'Matches Found'
export const DASHBOARD_RECENT_JOBS = 'Recent Jobs'
export const DASHBOARD_NO_JOBS = 'No recent jobs'
export const DASHBOARD_TOTAL_CATALOG = 'Total Catalog Images'
export const DASHBOARD_MISSING = 'Missing'

// Insights home (Phase 9)
export const INSIGHTS_PAGE_TITLE = 'Insights'
export const INSIGHTS_PAGE_SUBTITLE =
  'Critique score summaries, posting cadence, and top catalog highlights — with shortcuts to Analytics, Identity, and Processing.'
export const INSIGHTS_SECTION_SCORES = 'Scores & style'
export const INSIGHTS_SECTION_POSTING = 'Posting cadence'
export const INSIGHTS_SECTION_HIGHLIGHTS = 'Top scored photos'
export const INSIGHTS_SECTION_EXPLORE = 'Explore'
export const INSIGHTS_POSTING_RANGE_NOTE =
  'Last 12 months, monthly buckets (UTC). Adjust range on the Analytics page.'
export const INSIGHTS_FOOTER_TIMEZONE =
  'Timestamps follow the same assumptions as Analytics (often UTC from export). Open Analytics for full filters and notes.'
export const INSIGHTS_EMPTY_FINGERPRINT =
  'Not enough scored catalog data yet. Run scoring from Processing to see distributions and perspective means.'
export const INSIGHTS_QUICK_ANALYTICS_TITLE = 'Analytics'
export const INSIGHTS_QUICK_ANALYTICS_DESC = 'Posting frequency, heatmaps, and caption aggregates.'
export const INSIGHTS_QUICK_IDENTITY_TITLE = 'Identity'
export const INSIGHTS_QUICK_IDENTITY_DESC = 'Best photos, style fingerprint, and post-next suggestions.'
export const INSIGHTS_QUICK_PROCESSING_TITLE = 'Processing'
export const INSIGHTS_QUICK_PROCESSING_DESC = 'Matching, descriptions, scoring jobs, and perspectives.'
export const INSIGHTS_KPI_ACTIVE_JOBS = 'Active jobs'
export const INSIGHTS_KPI_ACTIVE_JOBS_DESC = 'Queued or running'
export const INSIGHTS_CADENCE_RECENT = 'Posts in last 4 weeks'
export const INSIGHTS_CADENCE_PRIOR = 'vs prior 4 weeks'

// Instagram Page
export const INSTAGRAM_DOWNLOADED = 'Downloaded Instagram Images'
export const INSTAGRAM_ERROR_PLACEHOLDER = 'Error'
export const INSTAGRAM_MATCHED_PREFIX = 'Matched:'
export const INSTAGRAM_VIA = 'via'

// Matching Page
export const MATCHING_RESULTS = 'Matching Results'
export const MATCHING_RUN_PROMPT = 'Click "Run Matching" above to start the matching process.'

// Actions
export const ACTION_RUN_MATCHING = 'Run Matching'
export const ACTION_CANCEL = 'Cancel'
export const ACTION_CANCELLING = 'Cancelling...'

export const MSG_FAILED_START_JOB = 'Failed to start job'

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

// Settings — Instagram dump (server path; IG-01)
export const SETTINGS_INSTAGRAM_DUMP_TITLE = 'Instagram export dump'
export const SETTINGS_INSTAGRAM_DUMP_HELP =
  'Path must be reachable by the visualizer server (large folder — not uploaded from the browser).'

// Job Details Modal
export const JOB_DETAILS_TITLE = 'Job Details'
export const JOB_DETAILS_PROGRESS = 'Progress'
export const JOB_DETAILS_CURRENT_STEP = 'Current Step'
export const JOB_DETAILS_METADATA = 'Metadata'
export const JOB_DETAILS_RESULT = 'Result'
export const JOB_DETAILS_ERROR = 'Error'
export const JOB_DETAILS_LOGS = 'Logs'
export const JOB_DETAILS_LOGS_TRUNCATED_HEADER = (shown: number, total: number) =>
  `Logs (${shown} of ${total})`
export const JOB_DETAILS_LOGS_SHOW_ALL = (total: number) => `Show all ${total} logs`
export const JOB_DETAILS_LOGS_SHOW_ALL_LOADING = 'Loading…'
export const JOB_DETAILS_LOADING_ARIA = 'Loading job details'
export const JOB_DETAILS_FETCH_ERROR =
  'Could not refresh job details. Showing the last known summary.'

// Job Queue
export const JOB_QUEUE_PAGINATION_RANGE = (start: number, end: number, total: number) =>
  `Showing ${start}–${end} of ${total}`

// Job Configuration Display
export const JOB_CONFIG_METHOD = 'Matching Method'
export const JOB_CONFIG_DATE_WINDOW = 'Date Window'
export const JOB_CONFIG_VISION_MODEL = 'Vision Model'
export const JOB_CONFIG_THRESHOLD = 'Match Threshold'
export const JOB_CONFIG_WEIGHTS = 'Scoring Weights'

// Job Config Labels
export const JOB_WEIGHT_PHASH = 'pHash:'
export const JOB_WEIGHT_DESC = 'Description:'
export const JOB_WEIGHT_VISION = 'Vision:'

// Matching Page Advanced Options
export const ADVANCED_OPTIONS_TITLE = 'Advanced Options'
export const ADVANCED_DATE_FILTER = 'Date filter'
export const ADVANCED_DATE_ALL = 'All time'
export const ADVANCED_DATE_3MONTHS = 'Last 3 months'
export const ADVANCED_DATE_6MONTHS = 'Last 6 months'
export const ADVANCED_DATE_12MONTHS = 'Last 12 months'
export const ADVANCED_DATE_YEAR_2026 = '2026 only'
export const ADVANCED_DATE_YEAR_2025 = '2025 only'
export const ADVANCED_DATE_YEAR_2024 = '2024 only'
export const ADVANCED_DATE_YEAR_2023 = '2023 only'

export const ADVANCED_MODEL_LABEL = 'Vision Model'
export const ADVANCED_MODEL_DESCRIPTION = 'Model used for vision comparison'
export const ADVANCED_PROVIDER_OVERRIDES_LEGACY_MODEL =
  'Provider-specific model selection overrides the legacy Ollama model below when set.'

export const ADVANCED_THRESHOLD_LABEL = 'Match Threshold'
export const ADVANCED_THRESHOLD_MIN = '0.50 (lenient)'
export const ADVANCED_THRESHOLD_MAX = '0.95 (strict)'
export const ADVANCED_THRESHOLD_DESCRIPTION = 'Minimum score required for a match (default: 0.70)'

export const ADVANCED_WEIGHTS_TITLE = 'Matching Weights'
export const ADVANCED_WEIGHTS_MUST_SUM = 'Weights must sum to 100%'
export const ADVANCED_WEIGHTS_TOTAL = 'Total'

export const ADVANCED_WEIGHT_PHASH = 'Perceptual Hash (pHash)'
export const ADVANCED_WEIGHT_DESC = 'Description Similarity'
export const ADVANCED_WEIGHT_VISION = 'Vision Model'

export const ADVANCED_WORKERS_LABEL = 'Parallel Workers'
export const ADVANCED_WORKERS_DESCRIPTION = 'Process multiple images in parallel (higher = faster, more load)'
export const ADVANCED_WORKERS_MIN = '1 (sequential)'
export const ADVANCED_WORKERS_MAX = '4 (parallel)'

export const ADVANCED_RESET_DEFAULTS = 'Reset to defaults'
export const ADVANCED_FORCE_DESCRIPTIONS = 'Force regenerate AI descriptions'
export const ADVANCED_FORCE_REPROCESS = 'Include already matched images'
export const ADVANCED_FIX_WEIGHTS = 'Please fix weight configuration before starting'
export const MODAL_ALREADY_MATCHED = 'Previously matched to:'
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
export const MATCH_CARD_SCORE_PHASH = 'PHash'
export const MATCH_CARD_SCORE_DESC = 'Desc'
export const MATCH_CARD_SCORE_VISION = 'Vision'
export const MATCH_CARD_SCORE_TOTAL = 'Total:'
export const MATCH_CANDIDATES_OF = 'of'
export const MATCH_CAROUSEL_PREVIOUS = 'Previous candidate'
export const MATCH_CAROUSEL_NEXT = 'Next candidate'
export const MATCH_CANDIDATE_LABEL = 'Candidate'

// Analytics (Phase 7)
export const ANALYTICS_PAGE_TITLE = 'Analytics'
export const ANALYTICS_PAGE_SUBTITLE =
  'Posting cadence, timing patterns, and caption aggregates from validated Instagram dump matches.'
export const ANALYTICS_SECTION_FREQUENCY = 'Posting frequency'
export const ANALYTICS_SECTION_HEATMAP = 'Posting time (day × hour)'
export const ANALYTICS_SECTION_CAPTIONS = 'Captions & hashtags'
export const ANALYTICS_LABEL_DATE_FROM = 'From'
export const ANALYTICS_LABEL_DATE_TO = 'To'
export const ANALYTICS_LABEL_GRANULARITY = 'Granularity'
export const ANALYTICS_GRANULARITY_DAY = 'Daily'
export const ANALYTICS_GRANULARITY_WEEK = 'Weekly'
export const ANALYTICS_GRANULARITY_MONTH = 'Monthly'
export const ANALYTICS_APPLY = 'Apply'
export const ANALYTICS_LOADING = 'Loading analytics…'
export const ANALYTICS_EMPTY_NO_POSTS =
  'No validated posts in this date range. Validate matches on the Images page to populate analytics.'
export const ANALYTICS_EMPTY_NO_DUMP =
  'No posting data yet. Ingest an Instagram export dump and validate matches to see analytics.'
export const ANALYTICS_HEATMAP_LEGEND = 'Darker cells = more posts (UTC hour)'
export const ANALYTICS_TIMEZONE_DISCLAIMER =
  'Times use the server’s assumptions (typically UTC from export timestamps). See the note below for details.'
export const ANALYTICS_CAPTION_TOP_HASHTAGS = 'Top hashtags'
export const ANALYTICS_CAPTION_STATS = 'Caption stats'
export const ANALYTICS_COL_HASHTAG = 'Hashtag'
export const ANALYTICS_COL_COUNT = 'Count'
export const ANALYTICS_STAT_POSTS = 'Posts in range'
export const ANALYTICS_STAT_WITH_CAPTION = 'With non-empty caption'
export const ANALYTICS_STAT_AVG_LEN = 'Avg. caption length (chars)'
export const ANALYTICS_STAT_MEDIAN_LEN = 'Median caption length'
export const ANALYTICS_STAT_POSTS_WITH_TAGS = 'Posts with hashtags'
export const ANALYTICS_STAT_AVG_TAGS = 'Avg. hashtags per post (unique)'

// Identity (Phase 8 / 08-02)
export const IDENTITY_PAGE_TITLE = 'Identity'
export const IDENTITY_PAGE_SUBTITLE =
  'Best scored catalog photos, your style fingerprint from critique scores, and what to post next.'
export const IDENTITY_SECTION_BEST_PHOTOS = 'Best photos'
export const IDENTITY_SECTION_STYLE_FINGERPRINT = 'Style fingerprint'
export const IDENTITY_SECTION_POST_NEXT = 'What to post next'
export const IDENTITY_BEST_PHOTOS_HELP =
  'Ranked by equal-weight aggregate over active perspectives (server order). Expand a row for per-perspective scores and rubric versions.'
export const IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK =
  'No eligible ranked photos yet. Run scoring on more perspectives per image to meet coverage.'
export const IDENTITY_LABEL_AGGREGATE = 'Aggregate'
export const IDENTITY_LABEL_PERSPECTIVES_COVERED = 'Perspectives scored'
export const IDENTITY_ACTION_SHOW_BREAKDOWN = 'Score breakdown'
export const IDENTITY_ACTION_HIDE_BREAKDOWN = 'Hide breakdown'
export const IDENTITY_COL_PERSPECTIVE = 'Perspective'
export const IDENTITY_COL_SCORE = 'Score'
export const IDENTITY_COL_PROMPT_VERSION = 'Prompt version'
export const IDENTITY_COL_MODEL = 'Model'
export const IDENTITY_FINGERPRINT_CHART_TITLE = 'Mean score by perspective (1–10)'
export const IDENTITY_FINGERPRINT_DISTRIBUTION = 'Aggregate score distribution'
export const IDENTITY_FINGERPRINT_TOKENS = 'Top rationale tokens'
export const IDENTITY_FINGERPRINT_EVIDENCE = 'Example images'
export const IDENTITY_FINGERPRINT_EMPTY =
  'Not enough scored catalog data to chart. Score images across active perspectives.'
export const IDENTITY_FINGERPRINT_LOW_DATA = 'Some perspectives have no scores yet.'
export const IDENTITY_POST_NEXT_HELP =
  'Unposted catalog images that meet coverage rules, with reasons from the server.'
export const IDENTITY_POST_NEXT_EMPTY_FALLBACK = 'No suggestions right now.'
export const IDENTITY_ACTION_OPEN_CATALOG = 'Open in catalog'
export const IDENTITY_REASON_CODE_LABELS: Record<string, string> = {
  high_score_unposted: 'High score (unposted)',
  cadence_gap: 'Cadence',
  underrepresented_theme: 'Theme variety',
  eligible_unposted: 'Eligible unposted',
}

// Analytics — not posted catalog (POST-04 / 07-03)
export const ANALYTICS_NOT_POSTED_TITLE = 'Not posted to Instagram'
export const ANALYTICS_NOT_POSTED_HELP =
  'Catalog images with instagram_posted = 0. Filters apply on the server when you click Apply.'
export const ANALYTICS_NOT_POSTED_MIN_RATING = 'Min rating'
export const ANALYTICS_NOT_POSTED_FROM_DATE = 'From date'
export const ANALYTICS_NOT_POSTED_TO_DATE = 'To date'
export const ANALYTICS_NOT_POSTED_MONTH = 'Month'
export const ANALYTICS_NOT_POSTED_EMPTY_ALL_POSTED =
  'All catalog images are marked posted on Instagram.'
export const ANALYTICS_NOT_POSTED_EMPTY_NO_MATCH = 'No images match filters'
export const IMAGES_OPEN_POSTING_ANALYTICS = 'Open posting analytics'

// Cache Status
export const CACHE_TITLE = 'Vision Cache'
export const CACHE_PREPARE_BUTTON = 'Prepare Catalog'
export const CACHE_PREPARING = 'Preparing...'
export const CACHE_STATUS_LOADING = 'Loading cache status...'
export const CACHE_STATUS_CACHED = 'cached'
export const CACHE_STATUS_OF = 'of'
export const CACHE_STATUS_IMAGES = 'images'
export const CACHE_SIZE_LABEL = 'Cache size'
export const CACHE_TOTAL_CATALOG_IMAGES = 'Total Catalog Images'
export const CACHE_MISSING = 'Missing'
export const CACHE_PERCENT_CACHED = (pct: number) => `${pct}% cached`
export const CACHE_REFRESH_BUTTON = 'Refresh'
export const CACHE_JOB_RUNNING = 'Cache preparation in progress...'
export const CACHE_JOB_COMPLETED = 'Cache preparation completed!'
export const CACHE_WARNING_NOT_READY = 'Catalog not fully cached. Matching may be slower.'

// Descriptions Page
export const DESC_PAGE_TITLE = 'AI Descriptions'
export const DESC_PAGE_TAB_ALL = 'All'
export const DESC_PAGE_TAB_CATALOG = 'Catalog'
export const DESC_PAGE_TAB_INSTAGRAM = 'Instagram'
export const DESC_PAGE_BATCH_CATALOG = 'Generate Catalog Descriptions'
export const DESC_PAGE_BATCH_INSTAGRAM = 'Generate Instagram Descriptions'
export const DESC_PAGE_BATCH_ALL = 'Generate All Descriptions'
export const DESC_PAGE_BATCH_RUNNING = 'Generating...'
export const DESC_PAGE_MODEL_LABEL = 'Vision Model'
export const DESC_PAGE_SOURCE_CATALOG = 'Source: catalog file'
export const DESC_PAGE_SOURCE_INSTAGRAM = 'Source: Instagram post'
export const DESC_PAGE_FILTER_ALL = 'All time'
export const DESC_PAGE_FILTER_3M = 'Last 3 months'
export const DESC_PAGE_FILTER_6M = 'Last 6 months'
export const DESC_PAGE_FORCE = 'Force regenerate'
export const DESC_PAGE_GENERATE = 'Generate'
export const DESC_PAGE_REGENERATE = 'Regenerate'
export const DESC_PAGE_GENERATING = 'Generating...'
export const DESC_PAGE_NO_DESCRIPTION = 'No description yet'
export const DESC_PAGE_EMPTY = 'No images found.'

export const DESC_BATCH_JOB_STARTED = (idPrefix: string) => `Job started (ID: ${idPrefix})`
export const DESC_BATCH_VIEW_IN_JOBS = 'View in Jobs'
export const DESC_BATCH_FAILED_PREFIX = 'Failed:'

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

export const DESC_COMPOSITION_DEPTH = 'Depth:'
export const DESC_COMPOSITION_BALANCE = 'Balance:'
export const DESC_TECHNICAL_MOOD = 'Mood:'
export const DESC_TECHNICAL_LIGHTING = 'Lighting:'
export const DESC_TECHNICAL_TIME = 'Time:'
export const DESC_TECHNICAL_COLORS = 'Colors:'

// Match detail modal
export const MATCH_DETAIL_INSTAGRAM = 'Instagram'
export const MATCH_DETAIL_CATALOG = 'Catalog'
export const MATCH_DETAIL_VISION_LABEL = 'Vision:'
export const MATCH_DETAIL_VISION_REASONING = 'Vision model note'
export const MATCH_DETAIL_SCORE_LABEL = 'Score:'
export const MATCH_DETAIL_PHASH_LABEL = 'PHash:'
export const MATCH_DETAIL_MATCH_DETAILS = 'Match Details'
export const MATCH_DETAIL_INSTAGRAM_KEY = 'Instagram Key:'
export const MATCH_DETAIL_CATALOG_KEY = 'Catalog Key:'
export const MATCH_DETAIL_MODEL = 'Model:'
export const MATCH_DETAIL_UNVALIDATE_FIRST = 'Un-validate first to reject'

export const MATCH_VALIDATE = 'Validate'
export const MATCH_VALIDATED = 'Validated'
export const MATCH_REJECT = 'Reject'
export const MATCH_REJECT_TITLE = 'Reject this match?'
export const MATCH_REJECT_BODY = 'This will remove the match and blocklist this pairing. The Instagram image will be free to match other catalog candidates.'
export const MATCH_REJECT_CANCEL = 'Cancel'
export const MATCH_REJECT_CONFIRM = 'Reject Match'

/** Inline header label after a successful reject (modal stays open). */
export const MATCH_DETAIL_REJECTED_LABEL = 'Rejected'
/** Delay before auto-closing the modal after reject when no further candidates (ms). */
export const MATCH_DETAIL_REJECTED_AUTOCLOSE_MS = 1500
/** Badge on fully-rejected tombstone groups (no catalog matches left). */
export const MATCH_TOMBSTONE_NO_MATCH_BADGE = 'No match'
/** Row between unvalidated match groups and validated / tombstone groups on Matches tab. */
export const MATCHES_VALIDATED_DIVIDER_LABEL = '— Validated —'
/** Non-clickable tombstone card: screen readers only. */
export const MATCH_TOMBSTONE_CARD_ARIA_LABEL =
  'Reviewed Instagram post with no remaining catalog matches'

export const MODAL_MATCH_THIS_PHOTO = 'Match This Photo'
export const MODAL_MATCH_RUNNING = 'Matching...'
export const MODAL_MATCH_RESULT_FOUND = 'Match found!'
export const MODAL_MATCH_RESULT_NONE = 'No match found'
export const MODAL_MATCH_VIEW_RESULTS = 'View on Matching page'
export const MODAL_MATCH_RETRY = 'Run Again'
export const MODAL_MATCH_JOB_FAILED_PREFIX = 'Match failed:'

// Providers Page
export const NAV_PROVIDERS = 'Providers'
export const PROVIDER_TITLE = 'Provider Configuration'
export const PROVIDER_STATUS_AVAILABLE = 'Available'
export const PROVIDER_STATUS_UNAVAILABLE = 'Unavailable'
export const PROVIDER_MODELS_HEADING = 'Models'
export const PROVIDER_FALLBACK_HEADING = 'Fallback Order'
export const PROVIDER_FALLBACK_DESCRIPTION = 'When a provider fails, requests cascade in this order.'
export const PROVIDER_SOURCE_CONFIG = 'built-in'
export const PROVIDER_SOURCE_DISCOVERED = 'auto-discovered'
export const PROVIDER_SOURCE_USER = 'user-added'
export const PROVIDER_NO_MODELS = 'No models available'
export const PROVIDER_COL_MODEL = 'Model'
export const PROVIDER_COL_VISION = 'Vision'
export const PROVIDER_COL_SOURCE = 'Source'
export const PROVIDER_COL_ACTIONS = 'Actions'
export const PROVIDER_SELECT_LABEL = 'Provider'
export const PROVIDER_MODEL_SELECT_LABEL = 'Model'
export const PROVIDER_AUTO_DEFAULT = 'Auto (default)'
export const PROVIDER_MODEL_AUTO_FIRST = 'Auto (first available)'
export const PROVIDER_MOVE_UP = 'Move provider up in fallback order'
export const PROVIDER_MOVE_DOWN = 'Move provider down in fallback order'
export const PROVIDER_REMOVE_MODEL = 'Remove user-added model'
export const PROVIDER_ADD_MODEL_ID_LABEL = 'Model ID'
export const PROVIDER_ADD_MODEL_NAME_LABEL = 'Display name'
export const PROVIDER_ADD_MODEL_VISION_LABEL = 'Supports vision'
export const PROVIDER_ADD_MODEL_SUBMIT = 'Add model'
export const PROVIDER_ADD_MODEL_SUBMITTING = 'Adding…'
export const PROVIDER_ADD_MODEL_ERROR = 'Could not add model. Please try again.'

// Generic Buttons
export const BTN_DISMISS = 'Dismiss'
export const BTN_RETRY = 'Retry'

// Provider Inline Labels
export const PROVIDER_STATUS_SUFFIX_UNAVAILABLE = '(unavailable)'

// Description Generation Errors
export const DESC_ERROR_RATE_LIMIT = 'Rate limited — try a different provider or wait.'
export const DESC_ERROR_AUTH = 'Authentication failed — check your API key.'
export const DESC_ERROR_UNAVAILABLE = 'Provider unavailable — try a different provider.'
export const DESC_ERROR_GENERIC = 'Description generation failed.'

// Analyze (Processing → Analyze tab, Phase 3 / JOB-06)
export const ANALYZE_CARD_TITLE = 'Analyze Images'
export const ANALYZE_CARD_SUBTITLE =
  'Run AI description + scoring in a single job. Advanced options let you run stages separately.'
export const ANALYZE_PRIMARY_BUTTON = 'Analyze'
export const ANALYZE_PRIMARY_BUTTON_STARTING = 'Starting…'
export const ANALYZE_ADVANCED_RUN_SEPARATELY_TITLE = 'Run stages separately'
export const ANALYZE_ADVANCED_DESCRIBE_ONLY = 'Generate Descriptions only'
export const ANALYZE_ADVANCED_SCORE_ONLY = 'Run scoring only'
export const ANALYZE_FORCE_DESCRIBE_LABEL = 'Force regenerate descriptions'
export const ANALYZE_FORCE_SCORE_LABEL = 'Force regenerate scores'
export const ANALYZE_JOB_STARTED =
  'Analyze job started! Check Job Queue tab to monitor progress.'
export const ANALYZE_DESCRIBE_JOB_STARTED =
  'Description generation job started! Check Job Queue tab to monitor progress.'
export const ANALYZE_SCORE_JOB_STARTED =
  'Batch scoring job started (1–10 scores + short rationale per perspective). Check Job Queue for progress.'
export const ANALYZE_JOB_FAILED_PREFIX = 'Failed to start job:'
