import { useEffect, useState } from 'react'
import { DumpMediaAPI, DumpMedia } from '../services/api'
import {
  MSG_LOADING,
  MSG_ERROR_PREFIX,
} from '../constants/strings'

const PAGE_SIZE = 50

export function DumpMediaPage() {
  const [media, setMedia] = useState<DumpMedia[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'unprocessed' | 'processed' | 'matched' | 'unmatched'>('all')
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    let mounted = true

    async function fetchMedia() {
      setLoading(true)
      try {
        const filters: { processed?: boolean; matched?: boolean; limit?: number; offset?: number } = {
          limit: PAGE_SIZE,
          offset,
        }
        if (filter === 'processed') filters.processed = true
        if (filter === 'unprocessed') filters.processed = false
        if (filter === 'matched') filters.matched = true
        if (filter === 'unmatched') filters.matched = false

        const data = await DumpMediaAPI.list(filters)
        if (mounted) {
          setMedia(data.media)
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

    fetchMedia()
    return () => { mounted = false }
  }, [filter, offset])

  const filterButtons = [
    { key: 'all', label: 'All' },
    { key: 'unprocessed', label: 'Unprocessed' },
    { key: 'processed', label: 'Processed' },
    { key: 'matched', label: 'Matched' },
    { key: 'unmatched', label: 'Unmatched' },
  ] as const

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Instagram Dump Media</h2>
        <p className="text-sm text-gray-500">{total} items</p>
      </div>

      <div className="flex gap-2">
        {filterButtons.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => { setFilter(key); setOffset(0) }}
            className={`px-3 py-1.5 text-sm rounded-md ${
              filter === key
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12">
          <p className="text-gray-500">{MSG_LOADING}</p>
        </div>
      ) : error ? (
        <div className="text-center py-12">
          <p className="text-red-600">{MSG_ERROR_PREFIX} {error}</p>
        </div>
      ) : media.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">No dump media found</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Media Key</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Filename</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Caption</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vision Result</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Matched Key</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {media.map((item) => (
                  <tr key={item.media_key} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                        item.matched_catalog_key
                          ? 'bg-green-100 text-green-800'
                          : item.processed
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                      }`}>
                        {item.matched_catalog_key ? 'Matched' : item.processed ? 'Processed' : 'New'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 font-mono truncate max-w-[200px]" title={item.media_key}>
                      {item.media_key}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 truncate max-w-[150px]" title={item.filename}>
                      {item.filename || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 truncate max-w-[300px]" title={item.caption}>
                      {item.caption ? (item.caption.length > 50 ? `${item.caption.slice(0, 50)}...` : item.caption) : '-'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {item.vision_result && (
                        <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                          item.vision_result === 'SAME' ? 'bg-green-100 text-green-800' :
                          item.vision_result === 'DIFFERENT' ? 'bg-red-100 text-red-800' :
                          item.vision_result === 'UNCERTAIN' ? 'bg-yellow-100 text-yellow-800' :
                          item.vision_result === 'NO_MATCH' ? 'bg-gray-100 text-gray-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {item.vision_result}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 font-mono truncate max-w-[200px]" title={item.matched_catalog_key}>
                      {item.matched_catalog_key || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > PAGE_SIZE && (
            <div className="flex justify-between items-center text-sm text-gray-500">
              <span>
                Showing {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  disabled={offset === 0}
                  className="px-3 py-1 rounded disabled:opacity-50 bg-gray-100 hover:bg-gray-200"
                >
                  Previous
                </button>
                <button
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                  disabled={offset + PAGE_SIZE >= total}
                  className="px-3 py-1 rounded disabled:opacity-50 bg-gray-100 hover:bg-gray-200"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}