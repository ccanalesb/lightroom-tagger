import type { ReactNode } from 'react'

import type { ImageDescription } from '../services/api'
import {
  DESC_PANEL_SUMMARY,
  DESC_PANEL_COMPOSITION,
  DESC_PANEL_PERSPECTIVES,
  DESC_PANEL_TECHNICAL,
  DESC_PANEL_SUBJECTS,
  DESC_PANEL_MODEL,
  DESC_PANEL_NO_DESCRIPTION,
  DESC_PERSPECTIVE_STREET,
  DESC_PERSPECTIVE_DOCUMENTARY,
  DESC_PERSPECTIVE_PUBLISHER,
  DESC_BEST_FIT,
} from '../constants/strings'

interface DescriptionPanelProps {
  description: ImageDescription | null | undefined
  compact?: boolean
}

const PERSPECTIVE_LABELS: Record<string, string> = {
  street: DESC_PERSPECTIVE_STREET,
  documentary: DESC_PERSPECTIVE_DOCUMENTARY,
  publisher: DESC_PERSPECTIVE_PUBLISHER,
}

function scoreColor(score: number): string {
  if (score >= 7) return 'text-green-700 bg-green-50'
  if (score >= 5) return 'text-yellow-700 bg-yellow-50'
  return 'text-red-700 bg-red-50'
}

export function DescriptionPanel({ description, compact }: DescriptionPanelProps) {
  if (!description) {
    return (
      <p className="text-xs text-gray-400 italic">{DESC_PANEL_NO_DESCRIPTION}</p>
    )
  }

  if (compact) {
    return <CompactView description={description} />
  }

  return <FullView description={description} />
}

function CompactView({ description }: { description: ImageDescription }) {
  const best = description.best_perspective
  const perspective = best ? description.perspectives[best as keyof typeof description.perspectives] : null

  return (
    <div className="space-y-1">
      {description.summary && (
        <p className="text-xs text-gray-600 line-clamp-2">{description.summary}</p>
      )}
      {best && perspective && (
        <div className="flex items-center gap-1.5">
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${scoreColor(perspective.score)}`}>
            {PERSPECTIVE_LABELS[best] || best} {perspective.score}/10
          </span>
          <span className="text-[10px] text-gray-400">{DESC_BEST_FIT}</span>
        </div>
      )}
    </div>
  )
}

function FullView({ description }: { description: ImageDescription }) {
  const { composition, perspectives, technical, subjects } = description

  return (
    <div className="space-y-3 text-sm">
      {/* Summary */}
      {description.summary && (
        <Section title={DESC_PANEL_SUMMARY}>
          <p className="text-gray-700">{description.summary}</p>
        </Section>
      )}

      {/* Perspectives */}
      {perspectives && Object.keys(perspectives).length > 0 && (
        <Section title={DESC_PANEL_PERSPECTIVES}>
          <div className="space-y-2">
            {(Object.entries(perspectives) as [string, { analysis: string; score: number }][]).map(
              ([key, val]) => (
                <div key={key} className="flex gap-2">
                  <div className="flex-shrink-0 w-20">
                    <span className={`inline-block text-xs px-1.5 py-0.5 rounded font-medium ${scoreColor(val.score)}`}>
                      {PERSPECTIVE_LABELS[key] || key} {val.score}
                    </span>
                    {description.best_perspective === key && (
                      <span className="block text-[10px] text-gray-400 mt-0.5">{DESC_BEST_FIT}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-600 flex-1">{val.analysis}</p>
                </div>
              ),
            )}
          </div>
        </Section>
      )}

      {/* Composition */}
      {composition && Object.keys(composition).length > 0 && (
        <Section title={DESC_PANEL_COMPOSITION}>
          <div className="text-xs text-gray-600 space-y-1">
            {composition.techniques && composition.techniques.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {composition.techniques.map((t) => (
                  <span key={t} className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">
                    {t.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}
            {composition.problems && composition.problems.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {composition.problems.map((p) => (
                  <span key={p} className="bg-red-50 text-red-700 px-1.5 py-0.5 rounded">
                    {p}
                  </span>
                ))}
              </div>
            )}
            {composition.depth && <p>Depth: {composition.depth}</p>}
            {composition.balance && <p>Balance: {composition.balance}</p>}
          </div>
        </Section>
      )}

      {/* Technical */}
      {technical && Object.keys(technical).length > 0 && (
        <Section title={DESC_PANEL_TECHNICAL}>
          <div className="text-xs text-gray-600 space-y-1">
            {technical.mood && <p>Mood: {technical.mood}</p>}
            {technical.lighting && <p>Lighting: {technical.lighting.replace(/_/g, ' ')}</p>}
            {technical.time_of_day && <p>Time: {technical.time_of_day.replace(/_/g, ' ')}</p>}
            {technical.dominant_colors && technical.dominant_colors.length > 0 && (
              <div className="flex items-center gap-1">
                <span>Colors:</span>
                {technical.dominant_colors.map((c) => (
                  <span
                    key={c}
                    className="inline-block w-4 h-4 rounded border border-gray-200"
                    style={{ backgroundColor: c }}
                    title={c}
                  />
                ))}
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Subjects */}
      {subjects && subjects.length > 0 && (
        <Section title={DESC_PANEL_SUBJECTS}>
          <div className="flex flex-wrap gap-1">
            {subjects.map((s) => (
              <span key={s} className="bg-blue-50 text-blue-700 text-xs px-1.5 py-0.5 rounded">
                {s}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Model */}
      {description.model_used && (
        <p className="text-[10px] text-gray-400">
          {DESC_PANEL_MODEL}: {description.model_used}
        </p>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
        {title}
      </h5>
      {children}
    </div>
  )
}
