import { useEffect, useState } from 'react'
import { MatchingAPI, Match } from '../services/api'
import {
  MSG_LOADING,
  MSG_ERROR_PREFIX,
  MSG_NO_MATCHES,
  MATCHING_RESULTS,
} from '../constants/strings'

export function MatchingPage() {
  const [matches, setMatches] = useState<Match[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    async function fetchMatches() {
      try {
        const data = await MatchingAPI.list(100)
        if (mounted) {
          setMatches(data.matches)
          setTotal(data.total)
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

    fetchMatches()
    return () => { mounted = false }
  }, [])

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

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">
          {MATCHING_RESULTS}
        </h2>
        <p className="text-sm text-gray-500">
          {total} matches
        </p>
      </div>

      {matches.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">{MSG_NO_MATCHES}</p>
          <p className="text-sm text-gray-400 mt-2">
            Run <code className="bg-gray-100 px-2 py-1 rounded">python -m lightroom_tagger match --db library.db</code> from the command line.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {matches.map((match, idx) => (
            <MatchCard key={`${match.instagram_key}-${idx}`} match={match} />
          ))}
        </div>
      )}
    </div>
  )
}

function MatchCard({ match }: { match: Match }) {
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
    <div className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow bg-white">
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