import { descriptionScoreColor } from '../../../utils/scoreColorClasses'

interface ScorePillProps {
  /** Numeric score, 1–10. When `null`/`undefined`, pill renders as a muted
   *  "no score" state rather than hiding — callers decide whether to render. */
  score: number | null | undefined
  /** Short prefix label (e.g. "Identity", "Street", "Best"). */
  label?: string
  /** Optional extra Tailwind classes. */
  className?: string
}

/**
 * Score pill used across image tiles, breakdowns, and modal headers.
 *
 * Reuses `descriptionScoreColor` so color thresholds (7+ green, 5–6 yellow,
 * <5 red) stay consistent with the existing description panel atoms.
 */
export function ScorePill({ score, label, className = '' }: ScorePillProps) {
  const hasScore = typeof score === 'number' && Number.isFinite(score)
  const display = hasScore ? score.toFixed(score % 1 === 0 ? 0 : 1) : '—'
  const colorClasses = hasScore
    ? descriptionScoreColor(score)
    : 'bg-surface text-text-secondary'

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${colorClasses} ${className}`.trim()}
      aria-label={label ? `${label} score ${display}` : `Score ${display}`}
    >
      {label ? <span className="font-normal opacity-80">{label}</span> : null}
      <span className="tabular-nums font-semibold">{display}</span>
    </span>
  )
}
