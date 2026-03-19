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
  return (
    <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="space-y-3">
        <div className="flex justify-between items-start">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate" title={match.instagram_key}>
              {match.instagram_key.split('_').pop()}
            </p>
            <p className="text-xs text-gray-500 truncate" title={match.catalog_key}>
              {match.catalog_key.split('_').pop()}
            </p>
          </div>
          <div className="ml-2 flex-shrink-0">
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">
              {(match.score * 100).toFixed(0)}%
            </span>
          </div>
        </div>
        
        <div className="text-xs text-gray-400">
          Score: {match.score.toFixed(3)}
        </div>
      </div>
    </div>
  )
}