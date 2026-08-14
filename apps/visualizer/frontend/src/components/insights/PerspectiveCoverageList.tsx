import type { PerspectiveCoverageRow } from '../../services/api'
import { Badge } from '../ui/badges'
import { Card, CardContent } from '../ui/Card'
import { INSIGHTS_COVERAGE_INACTIVE } from '../../constants/strings'

export type PerspectiveCoverageListProps = {
  rows: PerspectiveCoverageRow[]
  catalogImages: number
}

function barWidth(scored: number, catalogImages: number): number {
  if (catalogImages <= 0) return 0
  return Math.min(100, Math.round((scored / catalogImages) * 100))
}

function barTone(scored: number, catalogImages: number, active: boolean): string {
  if (!active) return 'bg-text-tertiary'
  const pct = catalogImages > 0 ? scored / catalogImages : 0
  if (pct >= 0.9) return 'bg-accent'
  if (pct >= 0.5) return 'bg-warning'
  return 'bg-error'
}

export function PerspectiveCoverageList({ rows, catalogImages }: PerspectiveCoverageListProps) {
  const maxScored = rows.reduce((max, row) => Math.max(max, row.scored_images), 0)

  return (
    <Card padding="md">
      <CardContent className="!text-text">
        <table className="w-full border-collapse text-sm">
          <tbody>
            {rows.map((row) => {
              const width = barWidth(row.scored_images, maxScored || catalogImages)
              return (
                <tr key={row.slug}>
                  <td className="py-1.5 pr-3 text-text-secondary">
                    <span className="inline-flex items-center gap-2">
                      <span>{row.display_name || row.slug}</span>
                      {!row.active ? (
                        <Badge variant="default">{INSIGHTS_COVERAGE_INACTIVE}</Badge>
                      ) : null}
                    </span>
                  </td>
                  <td className="w-[4.5rem] py-1.5 text-right font-semibold tabular-nums text-text">
                    {row.scored_images.toLocaleString()}
                  </td>
                  <td className="w-[46%] py-1.5 pl-3.5">
                    <div className="h-1.5 overflow-hidden rounded-full bg-surface">
                      <div
                        className={`h-full rounded-full ${barTone(row.scored_images, catalogImages, row.active)}`}
                        style={{ width: `${width}%` }}
                      />
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
