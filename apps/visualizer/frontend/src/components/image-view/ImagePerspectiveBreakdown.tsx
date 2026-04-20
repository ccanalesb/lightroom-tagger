import type { IdentityPerPerspectiveScore } from '../../services/api'
import {
  IDENTITY_COL_MODEL,
  IDENTITY_COL_PERSPECTIVE,
  IDENTITY_COL_PROMPT_VERSION,
  IDENTITY_COL_SCORE,
  IDENTITY_LABEL_AGGREGATE,
  IDENTITY_LABEL_PERSPECTIVES_COVERED,
} from '../../constants/strings'
import { ScorePill } from '../ui/badges/ScorePill'

interface ImagePerspectiveBreakdownProps {
  perspectives: IdentityPerPerspectiveScore[] | undefined
  aggregateScore?: number | null
  perspectivesCovered?: number
  /** Hide the aggregate summary row (e.g. when the modal header already shows it). */
  hideSummary?: boolean
  className?: string
}

/**
 * Identity-score breakdown table shown in every modal that renders a
 * catalog-backed image (CONTEXT Q3 — breakdown in every modal regardless
 * of entry point). Also used by `BestPhotosGrid` expand row so both
 * surfaces render the same markup.
 *
 * Renders nothing when `perspectives` is empty — callers can call this
 * unconditionally and let the component decide.
 */
export function ImagePerspectiveBreakdown({
  perspectives,
  aggregateScore,
  perspectivesCovered,
  hideSummary = false,
  className = '',
}: ImagePerspectiveBreakdownProps) {
  if (!perspectives || perspectives.length === 0) return null

  return (
    <div className={`space-y-2 ${className}`.trim()}>
      {hideSummary ? null : (
        <div className="flex flex-wrap items-center gap-2">
          <ScorePill score={aggregateScore} label={IDENTITY_LABEL_AGGREGATE} />
          <span className="rounded-full border border-border px-2 py-0.5 text-xs text-text-secondary">
            {IDENTITY_LABEL_PERSPECTIVES_COVERED}:{' '}
            {perspectivesCovered ?? perspectives.length}
          </span>
        </div>
      )}
      <div className="overflow-x-auto rounded-base border border-border">
        <table className="w-full min-w-[280px] text-left text-xs text-text">
          <thead className="bg-surface text-text-secondary">
            <tr>
              <th className="px-2 py-1.5 font-medium">{IDENTITY_COL_PERSPECTIVE}</th>
              <th className="px-2 py-1.5 font-medium">{IDENTITY_COL_SCORE}</th>
              <th className="px-2 py-1.5 font-medium">{IDENTITY_COL_PROMPT_VERSION}</th>
              <th className="px-2 py-1.5 font-medium">{IDENTITY_COL_MODEL}</th>
            </tr>
          </thead>
          <tbody>
            {perspectives.map((p) => (
              <tr key={p.perspective_slug} className="border-t border-border">
                <td className="px-2 py-1.5">{p.display_name}</td>
                <td className="px-2 py-1.5 font-medium">{p.score}</td>
                <td className="px-2 py-1.5 text-text-secondary">
                  {p.prompt_version || '—'}
                </td>
                <td className="px-2 py-1.5 text-text-secondary">
                  {p.model_used || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
