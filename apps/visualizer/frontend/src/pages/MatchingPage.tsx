import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MatchingAPI, JobsAPI, Match, Job } from '../services/api'
import { MatchDetailModal } from '../components/MatchDetailModal'
import { useSocketStore } from '../stores/socketStore'
import {
  MSG_LOADING,
  MSG_ERROR_PREFIX,
  MSG_NO_MATCHES,
  MATCHING_RESULTS,
  ACTION_RUN_MATCHING,
} from '../constants/strings'

export function MatchingPage() {
  const [matches, setMatches] = useState<Match[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showTrigger, setShowTrigger] = useState(false)
  const [dateFilter, setDateFilter] = useState<'all' | '3months' | '6months' | '2026'>('all')
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null)
  const [activeJob, setActiveJob] = useState<Job | null>(null)
  const [isStarting, setIsStarting] = useState(false)

  const navigate = useNavigate()
  const { socket, connected } = useSocketStore()

  // Fetch matches and check for active jobs on mount
  useEffect(() => {
    let mounted = true

    async function fetchData() {
      try {
        // Fetch matches
        const data = await MatchingAPI.list(100)
        if (mounted) {
          setMatches(data.matches)
          setTotal(data.total)
        }

        // Check for active vision_match jobs
        const jobsData = await JobsAPI.getActive()
        if (mounted) {
          const activeMatchJob = jobsData.find((job: Job) => 
            job.type === 'vision_match' && ['pending', 'running'].includes(job.status)
          )
          if (activeMatchJob) {
            setActiveJob(activeMatchJob)
          }
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

    fetchData()
    return () => { mounted = false }
  }, [])

  // Subscribe to job updates
  useEffect(() => {
    if (!socket || !connected) return

    const handleJobCreated = (job: Job) => {
      if (job.type === 'vision_match') {
        setActiveJob(job)
        setIsStarting(false)
        setShowTrigger(false)
      }
    }

    const handleJobUpdated = (job: Job) => {
      if (job.id === activeJob?.id) {
        setActiveJob(job)
        // Auto-refresh matches when job completes
        if (job.status === 'completed') {
          setTimeout(() => {
            MatchingAPI.list(100).then(data => {
              setMatches(data.matches)
              setTotal(data.total)
            })
          }, 1000)
        }
      }
    }

    socket.on('job_created', handleJobCreated)
    socket.on('job_updated', handleJobUpdated)

    return () => {
      socket.off('job_created', handleJobCreated)
      socket.off('job_updated', handleJobUpdated)
    }
  }, [socket, connected, activeJob?.id])

  async function startMatching() {
    setIsStarting(true)
    const metadata: Record<string, any> = {}
    if (dateFilter === '3months') metadata.last_months = 3
    else if (dateFilter === '6months') metadata.last_months = 6
    else if (dateFilter === '2026') metadata.year = '2026'

    try {
      const job = await JobsAPI.create('vision_match', metadata)
      setActiveJob(job)
      setIsStarting(false)
      setShowTrigger(false)
    } catch (err) {
      setIsStarting(false)
      alert(`Failed to start matching: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  function viewJobDetails() {
    navigate('/jobs')
  }

  if (loading) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">{MSG_LOADING}</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{MSG_ERROR_PREFIX} {error}</p>
      </div>
    )
  }

  // Status badge color based on job status
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'running': return 'bg-blue-100 text-blue-800'
      case 'completed': return 'bg-green-100 text-green-800'
      case 'failed': return 'bg-red-100 text-red-800'
      case 'pending': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">
          {MATCHING_RESULTS}
        </h2>
        <div className="flex items-center gap-4">
          <p className="text-sm text-gray-500">
            {total} matches
          </p>
          <button
            onClick={() => setShowTrigger(!showTrigger)}
            disabled={isStarting || (activeJob?.status === 'running')}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isStarting ? 'Starting...' : ACTION_RUN_MATCHING}
          </button>
        </div>
      </div>

      {/* Active job status panel */}
      {activeJob && activeJob.status !== 'completed' && (
        <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full" />
              <div>
                <p className="font-medium text-blue-900">
                  Matching in progress...
                </p>
                <p className="text-sm text-blue-700">
                  {activeJob.status === 'pending' ? 'Waiting to start' : 
                   activeJob.progress ? `${activeJob.progress}% complete` : 'Processing...'}
                </p>
              </div>
            </div>
            <button
              onClick={viewJobDetails}
              className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
            >
              View Details
            </button>
          </div>
        </div>
      )}

      {/* Job completed notification */}
      {activeJob?.status === 'completed' && (
        <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <div>
                <p className="font-medium text-green-900">
                  Matching completed!
                </p>
                <p className="text-sm text-green-700">
                  {activeJob.result?.matched || 0} matches found
                </p>
              </div>
            </div>
            <button
              onClick={() => setActiveJob(null)}
              className="text-green-700 hover:text-green-900"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Job failed notification */}
      {activeJob?.status === 'failed' && (
        <div className="bg-red-50 border border-red-200 p-4 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <svg className="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              <div>
                <p className="font-medium text-red-900">
                  Matching failed
                </p>
                <p className="text-sm text-red-700">
                  {activeJob.error || 'Unknown error'}
                </p>
              </div>
            </div>
            <button
              onClick={() => setActiveJob(null)}
              className="text-red-700 hover:text-red-900"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {showTrigger && !activeJob && (
        <div className="bg-gray-50 p-4 rounded-lg border">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-gray-700">Date filter:</label>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value as any)}
              className="px-3 py-2 border rounded text-sm"
            >
              <option value="all">All time</option>
              <option value="3months">Last 3 months</option>
              <option value="6months">Last 6 months</option>
              <option value="2026">2026 only</option>
            </select>
            <button
              onClick={startMatching}
              disabled={isStarting}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-medium disabled:opacity-50"
            >
              {isStarting ? 'Starting...' : 'Start'}
            </button>
          </div>
        </div>
      )}

      {matches.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">{MSG_NO_MATCHES}</p>
          <p className="text-sm text-gray-400 mt-2">
            Click "Run Matching" above to start the matching process.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {matches.map((match, idx) => (
            <MatchCard
              key={`${match.instagram_key}-${idx}`}
              match={match}
              onClick={() => setSelectedMatch(match)}
            />
          ))}
        </div>
      )}

      {/* Match detail modal */}
      {selectedMatch && (
        <MatchDetailModal
          match={selectedMatch}
          onClose={() => setSelectedMatch(null)}
        />
      )}
    </div>
  )
}

function MatchCard({ match, onClick }: { match: Match; onClick?: () => void }) {
  const [instaLoaded, setInstaLoaded] = useState(false)
  const [instaError, setInstaError] = useState(false)
  const [catalogLoaded, setCatalogLoaded] = useState(false)
  const [catalogError, setCatalogError] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)

  const instaThumbnailUrl = `/api/images/instagram/${encodeURIComponent(match.instagram_key)}/thumbnail`
  const catalogThumbnailUrl = `/api/images/catalog/${encodeURIComponent(match.catalog_key)}/thumbnail`

  // Vision result badge colors
  const visionResult = match.vision_result || 'UNCERTAIN'
  const visionBadgeColors = {
    'SAME': 'bg-green-100 text-green-800',
    'DIFFERENT': 'bg-red-100 text-red-800',
    'UNCERTAIN': 'bg-yellow-100 text-yellow-800',
  }
  const visionBadgeColor = visionBadgeColors[visionResult] || visionBadgeColors['UNCERTAIN']

  return (
    <div
      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow bg-white cursor-pointer"
      onClick={onClick}
    >
      {/* Thumbnails side by side */}
      <div className="flex h-32">
        {/* Instagram image */}
        <div className="w-1/2 bg-gray-100 relative">
          {!instaLoaded && !instaError && (
            <div className="absolute inset-0 bg-gray-200 animate-pulse" />
          )}
          {instaError ? (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
              No image
            </div>
          ) : (
            <img
              src={instaThumbnailUrl}
              alt="Instagram"
              className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${instaLoaded ? 'opacity-100' : 'opacity-0'}`}
              loading="lazy"
              onLoad={() => setInstaLoaded(true)}
              onError={() => setInstaError(true)}
            />
          )}
          <div className="absolute top-1 left-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
            IG
          </div>
        </div>

        {/* Catalog image */}
        <div className="w-1/2 bg-gray-100 relative">
          {!catalogLoaded && !catalogError && (
            <div className="absolute inset-0 bg-gray-200 animate-pulse" />
          )}
          {catalogError ? (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
              No image
            </div>
          ) : (
            <img
              src={catalogThumbnailUrl}
              alt="Catalog"
              className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${catalogLoaded ? 'opacity-100' : 'opacity-0'}`}
              loading="lazy"
              onLoad={() => setCatalogLoaded(true)}
              onError={() => setCatalogError(true)}
            />
          )}
          <div className="absolute top-1 right-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
            Cat
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="p-3">
        <div className="flex justify-between items-start mb-2">
          {/* Vision result badge */}
          <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${visionBadgeColor}`}>
            {visionResult}
          </span>

          {/* Score */}
          <div
            className="relative"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800 cursor-help">
              {(match.score * 100).toFixed(0)}%
            </span>

            {/* Score breakdown tooltip */}
            {showTooltip && (match.phash_score !== undefined || match.vision_score !== undefined) && (
              <div className="absolute right-0 top-full mt-1 bg-white border rounded shadow-lg p-2 text-xs z-10 whitespace-nowrap">
                <div className="space-y-1">
                  {match.phash_score !== undefined && (
                    <div className="flex justify-between gap-2">
                      <span className="text-gray-500">PHash:</span>
                      <span className="font-mono">{(match.phash_score * 100).toFixed(0)}%</span>
                    </div>
                  )}
                  {match.desc_similarity !== undefined && (
                    <div className="flex justify-between gap-2">
                      <span className="text-gray-500">Desc:</span>
                      <span className="font-mono">{(match.desc_similarity * 100).toFixed(0)}%</span>
                    </div>
                  )}
                  {match.vision_score !== undefined && (
                    <div className="flex justify-between gap-2">
                      <span className="text-gray-500">Vision:</span>
                      <span className="font-mono">{(match.vision_score * 100).toFixed(0)}%</span>
                    </div>
                  )}
                  <div className="border-t pt-1 mt-1 flex justify-between gap-2 font-medium">
                    <span className="text-gray-600">Total:</span>
                    <span>{(match.score * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* File names */}
        <div className="text-xs space-y-1">
          <p className="text-gray-900 truncate" title={match.instagram_image?.filename || match.instagram_key}>
            IG: {match.instagram_image?.filename || match.instagram_key.split('_').pop()}
          </p>
          <p className="text-gray-600 truncate" title={match.catalog_image?.filename || match.catalog_key}>
            Cat: {match.catalog_image?.filename || match.catalog_key.split('_').pop()}
          </p>
        </div>
      </div>
    </div>
  )
}
