import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type {
  PostingFrequencyBucket,
  PostingFrequencyMeta,
} from '../../services/api'
import { MSG_LOADING } from '../../constants/strings'

const CHART_STROKE = 'var(--color-accent)'
const CHART_FILL = 'var(--color-accent-light)'
const AXIS_STROKE = 'var(--color-text-tertiary)'
const GRID_STROKE = 'var(--color-border)'

export interface PostingFrequencyChartProps {
  buckets: PostingFrequencyBucket[]
  meta: PostingFrequencyMeta | null
  loading: boolean
  error: string | null
  /** Smaller chart area for dashboard / embedded use */
  compact?: boolean
}

function formatBucketLabel(iso: string): string {
  const d = new Date(iso.includes('T') ? iso : `${iso}T12:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export function PostingFrequencyChart({
  buckets,
  meta,
  loading,
  error,
  compact = false,
}: PostingFrequencyChartProps) {
  const data = buckets.map((b) => ({
    ...b,
    label: formatBucketLabel(b.bucket_start),
  }))

  const minH = compact ? 'min-h-[180px]' : 'min-h-[280px]'
  const chartH = compact ? 'h-[200px]' : 'h-[320px]'

  if (loading) {
    return (
      <div
        className={`flex ${minH} items-center justify-center rounded-card border border-border bg-surface text-sm text-text-secondary`}
        role="status"
        aria-live="polite"
      >
        {MSG_LOADING}
      </div>
    )
  }

  if (error) {
    return (
      <div
        className={`flex ${minH} items-center justify-center rounded-card border border-border bg-surface px-4 text-center text-sm text-error`}
        role="alert"
      >
        {error}
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div
        className={`flex ${minH} items-center justify-center rounded-card border border-dashed border-border bg-surface text-sm text-text-secondary`}
      >
        No buckets in this range.
      </div>
    )
  }

  return (
    <div className="w-full min-w-0 space-y-2">
      <div className={`${chartH} w-full`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: AXIS_STROKE, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: GRID_STROKE }}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            tick={{ fill: AXIS_STROKE, fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              color: 'var(--color-text)',
            }}
            labelStyle={{ color: 'var(--color-text-secondary)' }}
            formatter={(value) => [value ?? '—', 'Posts']}
            labelFormatter={(_, payload) => {
              const p = payload?.[0]?.payload as { bucket_start?: string } | undefined
              return p?.bucket_start ?? ''
            }}
          />
          <Area
            type="monotone"
            dataKey="count"
            name="Posts"
            stroke={CHART_STROKE}
            fill={CHART_FILL}
            fillOpacity={0.35}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
      </div>
      {meta?.granularity ? (
        <p className="text-xs text-text-tertiary">
          Bucket: <span className="text-text-secondary">{meta.granularity}</span>
          {meta.timestamp_source ? (
            <>
              {' '}
              · Source: <span className="text-text-secondary">{meta.timestamp_source}</span>
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  )
}
