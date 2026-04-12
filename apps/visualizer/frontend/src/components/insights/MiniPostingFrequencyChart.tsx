import type { PostingFrequencyBucket, PostingFrequencyMeta } from '../../services/api'
import { PostingFrequencyChart } from '../analytics/PostingFrequencyChart'
import {
  INSIGHTS_CADENCE_PRIOR,
  INSIGHTS_CADENCE_RECENT,
} from '../../constants/strings'

export type MiniPostingFrequencyChartProps = {
  buckets: PostingFrequencyBucket[]
  meta: PostingFrequencyMeta | null
  loading: boolean
  error: string | null
  rangeEndIso: string
}

/**
 * Cadence stat: sum `count` for buckets whose `bucket_start` date falls in the last 28 days
 * (relative to `rangeEndIso`) vs the previous 28-day window. Works with monthly buckets as a
 * coarse approximation (whole bucket attributed to its start date).
 */
function cadenceRecentVsPrior(
  buckets: PostingFrequencyBucket[],
  rangeEndIso: string,
): { recent: number; prior: number } {
  const end = new Date(rangeEndIso.includes('T') ? rangeEndIso : `${rangeEndIso}T23:59:59`)
  if (Number.isNaN(end.getTime())) return { recent: 0, prior: 0 }
  const msDay = 86_400_000
  const recentCut = new Date(end.getTime() - 28 * msDay)
  const priorCut = new Date(end.getTime() - 56 * msDay)
  let recent = 0
  let prior = 0
  for (const b of buckets) {
    const d = new Date(b.bucket_start.includes('T') ? b.bucket_start : `${b.bucket_start}T12:00:00`)
    if (Number.isNaN(d.getTime()) || d > end) continue
    if (d > recentCut) recent += b.count
    else if (d > priorCut) prior += b.count
  }
  return { recent, prior }
}

export function MiniPostingFrequencyChart({
  buckets,
  meta,
  loading,
  error,
  rangeEndIso,
}: MiniPostingFrequencyChartProps) {
  const { recent, prior } = cadenceRecentVsPrior(buckets, rangeEndIso)

  return (
    <div className="space-y-3">
      <PostingFrequencyChart
        buckets={buckets}
        meta={meta}
        loading={loading}
        error={error}
        compact
      />
      {!loading && !error && buckets.length > 0 ? (
        <p className="text-xs text-text-secondary">
          <span className="font-medium text-text">{INSIGHTS_CADENCE_RECENT}:</span> {recent}{' '}
          <span className="text-text-tertiary">({INSIGHTS_CADENCE_PRIOR}: {prior})</span>
        </p>
      ) : null}
    </div>
  )
}
