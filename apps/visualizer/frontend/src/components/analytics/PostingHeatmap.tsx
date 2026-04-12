import { useMemo } from 'react'
import type { HeatmapCell, PostingHeatmapMeta } from '../../services/api'
import { ANALYTICS_HEATMAP_LEGEND, MSG_LOADING } from '../../constants/strings'

const DEFAULT_DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export interface PostingHeatmapProps {
  cells: HeatmapCell[]
  meta: PostingHeatmapMeta | null
  loading: boolean
  error: string | null
}

function cellKey(dow: number, hour: number) {
  return `${dow}-${hour}`
}

export function PostingHeatmap({ cells, meta, loading, error }: PostingHeatmapProps) {
  const { max, matrix } = useMemo(() => {
    let maxCount = 0
    const map = new Map<string, number>()
    for (const c of cells) {
      map.set(cellKey(c.dow, c.hour), c.count)
      if (c.count > maxCount) maxCount = c.count
    }
    return { max: maxCount, matrix: map }
  }, [cells])

  const rowLabels = meta?.dow_labels?.length === 7 ? meta.dow_labels : DEFAULT_DOW

  if (loading) {
    return (
      <div
        className="flex min-h-[200px] items-center justify-center rounded-card border border-border bg-surface text-sm text-text-secondary"
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
        className="flex min-h-[200px] items-center justify-center rounded-card border border-border bg-surface px-4 text-center text-sm text-error"
        role="alert"
      >
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-3 overflow-x-auto">
      <div
        className="inline-grid gap-px rounded-card border border-border bg-border p-1"
        style={{
          gridTemplateColumns: `2.75rem repeat(24, minmax(0.65rem, 1fr))`,
        }}
        role="grid"
        aria-label="Posting counts by day of week and hour"
      >
        <div />
        {Array.from({ length: 24 }, (_, h) => (
          <div
            key={`h-${h}`}
            className="flex items-end justify-center pb-0.5 text-[10px] font-medium text-text-tertiary"
          >
            {h % 6 === 0 ? h : ''}
          </div>
        ))}
        {rowLabels.map((label, dow) => (
          <div key={label} className="contents">
            <div className="flex items-center pr-1 text-xs font-medium text-text-secondary">{label}</div>
            {Array.from({ length: 24 }, (_, hour) => {
              const count = matrix.get(cellKey(dow, hour)) ?? 0
              const intensity = max > 0 ? count / max : 0
              const alpha = 0.08 + intensity * 0.92
              return (
                <div
                  key={`${dow}-${hour}`}
                  role="gridcell"
                  title={`${label} ${hour}:00 — ${count} post${count === 1 ? '' : 's'} (UTC)`}
                  className="aspect-square min-h-[14px] min-w-[14px] rounded-sm border border-border/40"
                  style={{
                    backgroundColor: `color-mix(in srgb, var(--color-accent) ${Math.round(alpha * 100)}%, transparent)`,
                  }}
                />
              )
            })}
          </div>
        ))}
      </div>
      <p className="text-xs text-text-tertiary">{ANALYTICS_HEATMAP_LEGEND}</p>
    </div>
  )
}
