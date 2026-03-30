import type { CacheStatus } from '../../services/api'
import {
  CACHE_TITLE,
  CACHE_STATUS_CACHED,
  CACHE_STATUS_OF,
  CACHE_STATUS_IMAGES,
  CACHE_SIZE_LABEL,
  CACHE_TOTAL_CATALOG_IMAGES,
  CACHE_MISSING,
  CACHE_PERCENT_CACHED,
  LABEL_MB,
} from '../../constants/strings';

export function CacheStatusCard({ cacheStatus }: { cacheStatus: CacheStatus }) {
  const pct = cacheStatus.total_images > 0
    ? Math.round((cacheStatus.cached_images / cacheStatus.total_images) * 100)
    : 0

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-3">{CACHE_TITLE}</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <p className="text-sm text-gray-600">{CACHE_TOTAL_CATALOG_IMAGES}</p>
          <p className="text-lg font-bold">{cacheStatus.total_images}</p>
        </div>
        <div>
          <p className="text-sm text-gray-600">{CACHE_STATUS_CACHED}</p>
          <p className="text-lg font-bold text-green-600">
            {cacheStatus.cached_images} {CACHE_STATUS_OF} {cacheStatus.total_images} {CACHE_STATUS_IMAGES}
          </p>
        </div>
        <div>
          <p className="text-sm text-gray-600">{CACHE_MISSING}</p>
          <p className="text-lg font-bold text-red-600">{cacheStatus.missing}</p>
        </div>
        <div>
          <p className="text-sm text-gray-600">{CACHE_SIZE_LABEL}</p>
          <p className="text-lg font-bold">{cacheStatus.cache_size_mb} {LABEL_MB}</p>
        </div>
      </div>
      <div className="mt-3">
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-green-500 h-2 rounded-full transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">{CACHE_PERCENT_CACHED(pct)}</p>
      </div>
    </div>
  )
}
