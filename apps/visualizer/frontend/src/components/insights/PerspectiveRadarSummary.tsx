import { useMemo } from 'react'
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import type { StyleFingerprintPerPerspective } from '../../services/api'
import {
  IDENTITY_FINGERPRINT_CHART_TITLE,
  IDENTITY_FINGERPRINT_LOW_DATA,
  MSG_LOADING,
} from '../../constants/strings'

const CHART_STROKE = 'var(--color-accent)'
const CHART_FILL = 'var(--color-accent-light)'
const AXIS_STROKE = 'var(--color-text-tertiary)'
const GRID_STROKE = 'var(--color-border)'

export type PerspectiveRadarSummaryProps = {
  perPerspective: StyleFingerprintPerPerspective[] | null
  loading: boolean
  error: string | null
}

export function PerspectiveRadarSummary({
  perPerspective,
  loading,
  error,
}: PerspectiveRadarSummaryProps) {
  const radarRows = useMemo(() => {
    if (!perPerspective) return []
    return perPerspective
      .filter((p) => p.mean_score != null && p.count_scores > 0)
      .map((p) => ({
        axis: p.perspective_slug.replace(/_/g, ' '),
        mean: Number(p.mean_score),
      }))
  }, [perPerspective])

  const showLowDataHint =
    perPerspective &&
    perPerspective.some((p) => p.count_scores === 0) &&
    radarRows.length > 0

  if (loading) {
    return (
      <div
        className="flex h-[260px] items-center justify-center rounded-card border border-border bg-surface text-sm text-text-secondary"
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
        className="flex h-[260px] items-center justify-center rounded-card border border-border bg-surface px-4 text-center text-sm text-error"
        role="alert"
      >
        {error}
      </div>
    )
  }

  if (radarRows.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center rounded-card border border-dashed border-border bg-surface text-sm text-text-secondary">
        No perspective means to chart yet.
      </div>
    )
  }

  return (
    <div className="w-full min-w-0 space-y-2">
      <h3 className="text-sm font-semibold text-text">{IDENTITY_FINGERPRINT_CHART_TITLE}</h3>
      {showLowDataHint ? (
        <p className="text-xs text-text-secondary" role="status">
          {IDENTITY_FINGERPRINT_LOW_DATA}
        </p>
      ) : null}
      <div className="h-[260px] w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarRows} margin={{ top: 16, right: 24, bottom: 16, left: 24 }}>
            <PolarGrid stroke={GRID_STROKE} />
            <PolarAngleAxis dataKey="axis" tick={{ fill: AXIS_STROKE, fontSize: 11 }} />
            <Radar
              name="Mean"
              dataKey="mean"
              stroke={CHART_STROKE}
              fill={CHART_FILL}
              fillOpacity={0.45}
              strokeWidth={2}
              isAnimationActive={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                color: 'var(--color-text)',
              }}
              formatter={(value) => {
                const n = typeof value === 'number' ? value : Number(value)
                return [Number.isFinite(n) ? n.toFixed(2) : '—', 'Mean score']
              }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
