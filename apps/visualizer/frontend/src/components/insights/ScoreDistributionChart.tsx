import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { IDENTITY_FINGERPRINT_DISTRIBUTION, MSG_LOADING } from '../../constants/strings'

const CHART_STROKE = 'var(--color-accent)'
const AXIS_STROKE = 'var(--color-text-tertiary)'
const GRID_STROKE = 'var(--color-border)'

export type ScoreDistributionChartProps = {
  aggregateDistribution: Record<string, number> | null
  note?: string | null
  loading: boolean
  error: string | null
}

export function ScoreDistributionChart({
  aggregateDistribution,
  note,
  loading,
  error,
}: ScoreDistributionChartProps) {
  const rows = useMemo(() => {
    if (!aggregateDistribution) return []
    return Object.entries(aggregateDistribution).map(([label, count]) => ({ label, count }))
  }, [aggregateDistribution])

  if (loading) {
    return (
      <div
        className="flex h-[220px] items-center justify-center rounded-card border border-border bg-surface text-sm text-text-secondary"
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
        className="flex h-[220px] items-center justify-center rounded-card border border-border bg-surface px-4 text-center text-sm text-error"
        role="alert"
      >
        {error}
      </div>
    )
  }

  if (rows.length === 0 || rows.every((r) => r.count === 0)) {
    return (
      <div className="flex h-[220px] items-center justify-center rounded-card border border-dashed border-border bg-surface text-sm text-text-secondary">
        No distribution buckets yet.
      </div>
    )
  }

  return (
    <div className="w-full min-w-0 space-y-2">
      <h3 className="text-sm font-semibold text-text">{IDENTITY_FINGERPRINT_DISTRIBUTION}</h3>
      {note ? <p className="text-xs text-text-tertiary">{note}</p> : null}
      <div className="h-[220px] w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: AXIS_STROKE, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: GRID_STROKE }}
            />
            <YAxis
              tick={{ fill: AXIS_STROKE, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              width={36}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                color: 'var(--color-text)',
              }}
              formatter={(value) => [value ?? '—', 'Images']}
            />
            <Bar dataKey="count" fill={CHART_STROKE} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
